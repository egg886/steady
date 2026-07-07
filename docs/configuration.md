# Configuration guide

steady works **without any configuration** — it falls back to AST-based line
removal out of the box. This guide covers how to enable AI-powered repairs,
tune retry behaviour, and plug in custom LLM backends.

---

## At a glance

| Variable             | Default        | Description                                            |
| -------------------- | -------------- | ------------------------------------------------------ |
| `STEADY_API_KEY`     | *(none)*       | Primary API key. Falls back to `OPENAI_API_KEY`.       |
| `OPENAI_API_KEY`     | *(none)*       | Fallback API key when `STEADY_API_KEY` is unset.       |
| `STEADY_MODEL`       | `gpt-4o-mini`  | Model identifier sent to the provider.                |
| `STEADY_PROVIDER`    | `openai`       | `openai` or `anthropic`.                              |
| `STEADY_MAX_RETRIES` | `3`            | Maximum repair attempts per error.                     |
| `STEADY_ENABLED`     | `true`         | Master switch (`false`/`0` disables steady).            |

---

## 1. Environment variables

steady reads configuration directly from `os.environ`. It **never** reads
`.env` files itself — that is left to your application.

```bash
export STEADY_API_KEY="sk-..."
# or, reuse an existing OpenAI key:
export OPENAI_API_KEY="sk-..."

export STEADY_PROVIDER="anthropic"   # or "openai" (default)
export STEADY_MODEL="claude-3-5-sonnet-20241022"
export STEADY_MAX_RETRIES=5
export STEADY_ENABLED=true           # set to "false" to disable
```

### API key resolution

`STEADY_API_KEY` takes priority. If it is unset, steady falls back to
`OPENAI_API_KEY`. This lets you reuse an existing OpenAI key without any
extra setup:

```bash
# Only OPENAI_API_KEY is set — steady picks it up automatically.
export OPENAI_API_KEY="sk-..."
```

### Truthy values

For boolean environment variables (`STEADY_ENABLED`), the following
case-insensitive values are interpreted as `True`:

```
1, true, yes, on, y, t
```

Anything else (including the empty string) is `False`.

---

## 2. Programmatic configuration

Configure steady from Python code. This takes precedence over environment
variables for any field you set.

```python
from steady import steady

steady.configure(
    api_key="sk-...",
    model="gpt-4o",
    provider="openai",     # or "anthropic"
    max_retries=5,
    enabled=True,
)
```

Only the keyword arguments you provide are applied — existing values are
preserved:

```python
# Change just the model, leave everything else as-is.
steady.configure(model="gpt-4o-mini")
```

### Disabling steady

```python
# Temporarily turn off all error handling — exceptions propagate normally.
steady.configure(enabled=False)

# Re-enable later.
steady.configure(enabled=True)
```

You can also do this entirely via the environment:

```bash
export STEADY_ENABLED=false
```

### Inspecting the config

```python
from steady import get_config
print(get_config())   # API key is masked in __repr__
```

Or from the command line (API key always masked):

```bash
python -m steady config
```

### Resetting to defaults

```python
from steady import get_config
get_config().reset()   # re-reads environment variables from scratch
```

---

## 3. Using python-dotenv

steady intentionally does not depend on `python-dotenv`. If you keep secrets
in a `.env` file, load it yourself **before** importing steady (or before
calling `steady.configure`):

```python
# Load .env into os.environ first.
from dotenv import load_dotenv
load_dotenv()

# Now steady can see the keys via os.environ.
from steady import steady
```

Because steady reads `os.environ` lazily on first use, keys loaded by
`python-dotenv` are picked up automatically.

---

## 4. Custom LLM backends

You can supply a **custom callable** in place of the OpenAI/Anthropic SDKs —
useful for local models, stubs, or any other chat endpoint:

```python
def my_llm(prompt: str) -> str:
    # ... call your own model / API ...
    return '{"fixed_code": "...", "explanation": "...", "strategy": "fix_value"}'

steady.configure(llm=my_llm)
```

### Callable contract

| Input  | Type  | Description                                                |
| ------ | ----- | ---------------------------------------------------------- |
| prompt | `str` | The fully assembled prompt (system instructions embedded). |

The callable may return either:

* a plain `str` — the response text, **or**
* a `(response, tokens)` tuple — the response text and tokens consumed.

### Recommended response format

steady asks the model to return a JSON object so the explanation and strategy
are recorded in the Bug Tour Report:

```json
{
  "fixed_code": "def divide(a, b):\n    return a / b\n",
  "explanation": "Added a guard for b == 0.",
  "strategy": "add_guard"
}
```

steady also accepts a raw code response (with or without markdown fences) for
backward compatibility — in that case the explanation defaults to
`"LLM-generated fix (raw code response)."`.

### Example: a stub callable for testing

```python
def stub_llm(prompt: str):
    # Return the JSON shape steady expects.
    fixed = "def divide(a, b):\n    if b == 0:\n        return 0\n    return a / b\n"
    return (
        '{"fixed_code": ' + repr(fixed) + ', '
        '"explanation": "Guard against division by zero.", '
        '"strategy": "add_guard"}',
        42,  # tokens
    )

steady.configure(llm=stub_llm, enabled=True)
```

---

## 5. Provider specifics

### OpenAI

```bash
pip install steady[openai]
export STEADY_PROVIDER=openai
export STEADY_MODEL=gpt-4o-mini
export STEADY_API_KEY=sk-...
```

### Anthropic

```bash
pip install steady[anthropic]
export STEADY_PROVIDER=anthropic
export STEADY_MODEL=claude-3-5-sonnet-20241022
export STEADY_API_KEY=sk-ant-...
```

> The system prompt is sent via the `system` parameter for Anthropic and as a
> `system` message for OpenAI, so both providers see the same repair
> instructions and JSON contract.

---

## 6. Tuning repair behaviour

### `STEADY_MAX_RETRIES`

Controls how many repair attempts steady makes per error before giving up and
re-raising the original exception. Each attempt can itself surface a *new*
error (e.g. removing one line reveals another bug), which counts as a retry.

```python
steady.configure(max_retries=10)   # be very persistent
steady.configure(max_retries=1)    # try once, then give up
```

### When steady gives up

If both tiers fail within `max_retries` attempts, steady:

1. Records an unresolved entry in the Bug Tour Report.
2. Re-raises the **original** exception.

This means steady never silently swallows a bug it could not fix — it always
leaves a trace in the report and lets the exception propagate.
