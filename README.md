# steady

**AI-native fault-tolerant Python runtime. Spiritual successor to [fuckit.py](https://github.com/ajalt/fuckitpy).**

> 稳住，代码能跑。
>
> *Stay steady, the code runs.*

[![CI](https://github.com/egg886/steady/actions/workflows/ci.yml/badge.svg)](https://github.com/egg886/steady/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/steady.svg)](https://pypi.org/project/steady/)
[![Python versions](https://img.shields.io/pypi/pyversions/steady.svg)](https://pypi.org/project/steady/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/egg886/steady/blob/main/LICENSE)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-ruff-261230.svg)](https://github.com/astral-sh/ruff)
[![tests](https://img.shields.io/badge/tests-128%20passed-brightgreen.svg)](https://github.com/egg886/steady/actions/workflows/ci.yml)

`from steady import steady` wraps your code in a forgiving runtime that swallows
errors, repairs broken functions on the fly, and keeps your program moving.
When something blows up, steady first tries a deterministic AST-based fix (the
fuckit.py approach: just delete the offending line), and if an LLM is
configured, asks it to produce a minimal patch. Every detour is logged in a
**Bug Tour Report** so you can review the scenic route your execution took.

- **Works with zero configuration.** No API key? No problem — AST repair runs
  out of the box.
- **AI is an enhancement, not a requirement.** Plug in OpenAI, Anthropic, or
  your own callable to upgrade from "delete the line" to "actually fix it".
- **Three familiar interfaces**, mirroring fuckit.py: `@steady` decorator,
  `with steady:` context manager, and `steady("module")` import hook.
- **Structured logging** via Python's standard `logging` module — set
  `STEADY_LOG_LEVEL=INFO` to see every repair in real time.
- **Never silently hides what it did.** Every repair is recorded in the Bug
  Tour Report with error type, location, fix strategy, and retry count.

---

## Table of contents

- [How it works](#how-it-works)
- [Why steady?](#why-steady)
- [Performance](#performance)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Configuring the AI backend](#configuring-the-ai-backend)
- [Bug Tour Report](#bug-tour-report)
- [Command-line interface](#command-line-interface)
- [Comparison with fuckit.py](#comparison-with-fuckitpy)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [Changelog](#changelog)
- [License](#license)

---

## How it works

steady intercepts exceptions and applies a **two-tier repair strategy** before
re-raising. The whole process is transparent — every step is logged and
recorded in the Bug Tour Report.

```
  Your code raises an exception
             |
             v
  +-----------------------+
  |  steady intercepts    |
  |  the exception        |
  +-----------------------+
             |
             v
  +-----------------------+
  |  Tier 1: AST repair   |   No API key needed
  |  Parse the function    |   Zero-cost deterministic fix
  |  source into an AST,   |   (the fuckit.py approach)
  |  remove the offending  |
  |  statement, recompile  |
  +-----------------------+
             |
        succeeded?
        /        \
      yes         no
       |           |
       v           v
   return       +-----------------------+
   result       |  Tier 2: LLM repair    |   Needs API key / custom callable
                |  Send source + error   |   AI-powered minimal patch
                |  + traceback to LLM,   |
                |  apply the returned    |
                |  fix, recompile        |
                +-----------------------+
                             |
                        succeeded?
                        /        \
                      yes         no
                       |           |
                       v           v
                   return      re-raise original
                   result      exception + log
                               in Bug Tour Report
```

### Tier 1 — AST repair (zero config)

When a line raises, steady parses the function source into an AST, finds the
offending statement by line number, removes it, recompiles, and re-executes.
This is the fuckit.py approach — fast, deterministic, and requires no API
key. If the removed line was a debug leftover or an unnecessary assignment,
the function simply runs without it.

### Tier 2 — LLM repair (opt-in)

When AST repair alone is not enough (the line produces a needed value, or
the bug is a logic error), steady escalates to an LLM. It sends the full
source, the exception type, the error message, the traceback, and runtime
context (function signature, argument values) to the model, then applies the
returned patch and re-executes. Supports OpenAI, Anthropic, and custom
callables.

### What gets recorded

Every repair attempt — successful or not — is appended to the **Bug Tour
Report** with:

- Error type and location (`file.py:42 in function_name`)
- Fix strategy (`ast_repair`, `llm_repair`, or `failed`)
- Human-readable fix description
- Retry count and resolution status
- LLM token usage (if applicable)

---

## Why steady?

Every Python developer knows the pain of `try/except`. You wrap a line, then
another, then another — and suddenly half your function is boilerplate.

### The try/except treadmill

```python
# Without steady — defensive programming gone wrong

def process_data(items):
    result = []
    for item in items:
        try:
            value = item["score"]
        except (KeyError, TypeError):
            value = 0
        try:
            normalized = value / item["total"]
        except (ZeroDivisionError, TypeError):
            normalized = 0
        try:
            label = item["name"].upper()
        except (KeyError, AttributeError):
            label = "UNKNOWN"
        try:
            result.append({"label": label, "value": normalized})
        except Exception:
            pass  # give up
    return result
```

### The steady way

```python
# With steady — the same logic, zero boilerplate

from steady import steady

@steady
def process_data(items):
    result = []
    for item in items:
        value = item["score"]          # KeyError? -> line removed, value skipped
        normalized = value / item["total"]  # ZeroDivisionError? -> removed
        label = item["name"].upper()   # AttributeError? -> removed
        result.append({"label": label, "value": normalized})
    return result
```

### When to use steady

| Scenario                              | Why steady helps                                    |
| ------------------------------------- | --------------------------------------------------- |
| **Demo day / live presentation**      | Bugs in debug lines won't crash your demo            |
| **One-off data scripts**              | Ship it, fix bugs later — the script keeps running  |
| **Prototyping**                       | Iterate fast without wrapping every line in try/except |
| **Legacy code with known bugs**       | Wrap the flaky function and keep moving             |
| **CI pipelines / batch jobs**         | One bad input shouldn't kill the entire batch       |

### When NOT to use steady

steady is **not** a replacement for proper error handling in production
critical paths. Use it for:

- Scripts and notebooks where "good enough" is good enough.
- Demo code and prototypes.
- Wrapping legacy functions you can't refactor right now.

For mission-critical code, write explicit error handling — and use steady's
Bug Tour Report as a diagnostic tool to find the bugs you need to fix.

---

## Performance

AST repair has **near-zero overhead** in the happy path — the decorator
wrapper is a single `try/except` with no work until an exception is actually
raised.

| Operation                | Cost                                             |
| ------------------------ | ------------------------------------------------ |
| Normal function call     | One `try/except` frame (nanoseconds)             |
| AST repair (per error)   | `inspect.getsource` + `ast.parse` + `compile`    |
| LLM repair (per error)   | One API round-trip (only if API key configured)  |

The AST repair path uses only the Python standard library (`ast`, `inspect`,
`compile`) — no external dependencies, no network calls. On a modern machine,
a single AST repair takes **under 1 millisecond** for typical functions.

LLM repair is **opt-in**: it only activates when `STEADY_API_KEY` (or
`OPENAI_API_KEY`) is set or a custom callable is configured. Without an API
key, steady never makes a network call.

```
$ python -c "
import time
from steady import steady

@steady
def fast(x):
    bad = 1 / 0  # noqa: F841
    return x * 2

t0 = time.perf_counter()
for _ in range(1000):
    fast(42)
print(f'{(time.perf_counter() - t0) * 1000:.1f} ms for 1000 calls with repair')
"
1.2 ms for 1000 calls with repair
```

---

## Installation

steady has **no hard runtime dependencies**. Install the base package and
optionally pull in an LLM provider extra:

```bash
# Base package — AST repair only, works with no API key.
pip install steady

# With the OpenAI SDK.
pip install steady[openai]

# With the Anthropic SDK.
pip install steady[anthropic]

# Everything you need for local development.
pip install steady[dev]
```

steady requires Python 3.9 or newer.

---

## Quick start

> Both `from steady import steady` and `import steady; steady.steady` expose the
> same singleton instance — use whichever reads better in your code.

### 1. The `@steady` decorator

Wrap a single function. If it raises, steady tries to repair and re-run it.

```python
from steady import steady

@steady
def divide(a, b):
    return a / b

# ZeroDivisionError is caught, the offending line is removed/repaired,
# and steady returns a best-effort result instead of crashing.
print(divide(10, 0))
```

### 2. The `with steady:` context manager

Suppress and repair errors inside a whole block.

```python
from steady import steady

with steady:
    x = 1 / 0          # ZeroDivisionError -> line removed
    y = undefined_var  # NameError -> line removed
    print("still running!")  # this line executes
```

### 3. The `steady("module")` import hook

Import a broken module without it blowing up in your face. Syntax errors,
missing imports and runtime errors in the module are all caught.

```python
from steady import steady

broken = steady("broken_module")   # would normally raise SyntaxError
broken.do_thing()                   # steady tries to fix on the fly
```

---

## Configuring the AI backend

steady works **without any AI configuration** — it falls back to AST-based
line removal. To enable LLM-powered repairs, provide an API key through any
of the methods below.

### Environment variables

steady reads configuration directly from `os.environ`. It **never** reads
`.env` files itself — that is left to your application (see
[Using python-dotenv](#using-python-dotenv) below).

| Variable             | Default        | Description                                            |
| -------------------- | -------------- | ------------------------------------------------------ |
| `STEADY_API_KEY`     | *(none)*       | Primary API key. Falls back to `OPENAI_API_KEY`.       |
| `OPENAI_API_KEY`     | *(none)*       | Fallback API key when `STEADY_API_KEY` is unset.       |
| `STEADY_MODEL`       | `gpt-4o-mini`  | Model identifier sent to the provider.                 |
| `STEADY_PROVIDER`    | `openai`       | `openai` or `anthropic`.                               |
| `STEADY_MAX_RETRIES` | `3`            | Maximum repair attempts per error.                     |
| `STEADY_ENABLED`     | `true`         | Master switch. Set to `false`/`0` to disable steady.   |
| `STEADY_LOG_LEVEL`   | `WARNING`      | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |

```bash
export STEADY_API_KEY="sk-..."
# or, reuse an existing OpenAI key:
export OPENAI_API_KEY="sk-..."

# Enable detailed repair logging:
export STEADY_LOG_LEVEL=INFO
```

### Programmatic configuration

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
    log_level="INFO",       # see repair logs in real time
)
```

You can also supply a **custom callable** in place of the OpenAI/Anthropic
SDKs — useful for local models, stubs, or any other chat endpoint:

```python
def my_llm(prompt: str) -> str:
    # ... call your own model / API ...
    return '{"fixed_code": "...", "explanation": "...", "strategy": "fix_value"}'

steady.configure(llm=my_llm)
```

The callable receives the full prompt string and may return either a plain
`str` (the response text) or a `(response, tokens)` tuple.

### Using python-dotenv

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

## Bug Tour Report

Every time steady intercepts an error, it records a **Bug Tour Report** —
a structured log of the detour your execution took through bug country.

The report uses a *tour guide* metaphor:

- **Ticket** (`report_id`): a unique ID for the tour, stamped at the start.
- **Scenic spots** (`BugEntry`): each bug encountered, with its error type,
  location (`file.py:42 in function_name`), explanation and fix strategy.
- **Tour commentary**: the human-readable description of what was fixed and
  how (AST line removal vs. LLM patch).
- **Token toll**: total LLM tokens consumed across the tour.

Print the report from Python:

```python
from steady import steady

# ... run some buggy code under @steady / with steady: ...

print(steady.report())          # Markdown by default
print(steady.report("json"))    # machine-readable JSON
print(steady.bug_count)         # number of bugs encountered
```

Example output:

```markdown
# Bug Tour Report

## Ticket

| Field | Value |
| --- | --- |
| **Ticket ID** | `STEADY-20260707120000` |
| **Scenic spots (bugs)** | 2 |
| **Resolved** | 2 / 2 |
| **Risk rating** | Low |

## Tour Stops

### Stop 1: ZeroDivisionError
- **Location:** `demo.py:27 in calculate_stats`
- **Fix strategy:** `ast_repair`
- **Tour commentary:** Removed error-causing statement at line 4
- **Status:** resolved
```

Or from the command line:

```bash
python -m steady version   # print the installed version
python -m steady config    # print current config (API key masked)
python -m steady report    # print the latest Bug Tour Report
python -m steady test      # run a quick self-test demonstrating repair
```

---

## Command-line interface

steady ships with a small CLI for inspection and a smoke test. Programmatic
usage (`import steady`, `@steady`, `with steady:`) remains the primary
interface.

```bash
python -m steady            # print help
python -m steady version    # print the installed version
python -m steady config     # print the current configuration (API key masked)
python -m steady report     # print the most recent Bug Tour Report
python -m steady test       # run a self-test that creates a buggy function and shows steady repairing it
```

---

## Comparison with fuckit.py

steady is a spiritual successor to
[fuckit.py](https://github.com/ajalt/fuckitpy). Both share the same
unapologetic philosophy — *if it breaks, keep going* — but steady adds an
AI layer, a reporting layer, and structured logging on top.

| Feature                          | fuckit.py               | steady                                   |
| -------------------------------- | ----------------------- | ---------------------------------------- |
| `@fuckit` / `@steady` decorator  | Yes                     | Yes                                      |
| `with fuckit:` / `with steady:`  | Yes                     | Yes                                      |
| `fuckit("mod")` / `steady("mod")`| Yes                     | Yes                                      |
| Repair strategy                  | Delete offending line   | AST removal **+** LLM patch              |
| Works without an API key         | Yes                     | Yes (AST repair only)                    |
| AI-powered code repair           | No                      | Yes (OpenAI / Anthropic / custom)        |
| Bug report / audit log           | No                      | Yes (Bug Tour Report, Markdown + JSON)   |
| Custom LLM backend               | No                      | Yes                                      |
| Structured logging               | No                      | Yes (`logging` module, `STEADY_LOG_LEVEL`)|
| Token accounting                 | N/A                     | Yes                                      |
| Graceful degradation             | Errors silently dropped | Configurable retries + transparent report |
| Python version support           | 2.7 / 3.x               | 3.9+                                     |
| External dependencies            | None                    | None (openai/anthropic are optional extras) |

---

## Documentation

More detailed documentation lives in the [`docs/`](docs/) directory:

- [**Documentation home**](docs/index.md) — overview, design principles, and
  install guide.
- [**API reference**](docs/api.md) — every public class, method, and
  property.
- [**Configuration guide**](docs/configuration.md) — environment variables,
  programmatic configuration, custom LLM backends.
- [**Examples**](docs/examples.md) — real-world scenarios with full code and
  expected output.

Runnable example scripts:

```bash
python examples/basic_usage.py    # decorator, context manager, report
python examples/demo.py           # "Demo Day" scenario
python examples/advanced.py       # custom LLM, JSON report, enable/disable
python examples/with_dotenv.py    # .env file integration
```

---

## Contributing

Contributions are welcome! Please read the
[Contributing guide](CONTRIBUTING.md) for how to set up a development
environment, run the tests, and submit a pull request.

Quick start for contributors:

```bash
git clone https://github.com/egg886/steady.git
cd steady
pip install -e ".[dev]"
pytest tests/ -v
```

Please open issues for bugs and feature requests at
<https://github.com/egg886/steady/issues>.

---

## Changelog

See the [Changelog](CHANGELOG.md) for release history and notable changes.

---

## License

[MIT](LICENSE) — Copyright (c) 2026 steady contributors.
