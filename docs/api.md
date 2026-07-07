# API reference

This is the complete reference for steady's public API. All symbols below are
re-exported from the top-level `steady` package unless noted otherwise.

```python
import steady

steady.steady          # the singleton Steady instance
steady.Steady          # the Steady class
steady.Config          # the Config class
steady.get_config      # get the process-wide Config singleton
steady.BugEntry        # a single bug record
steady.BugReport       # the report collector
steady.LLMClient       # the LLM repair client
steady.LLMRepairResult # the result of an LLM repair attempt
steady.__version__     # the installed version string
```

---

## `steady` (singleton instance)

```python
from steady import steady
```

A process-wide singleton instance of [`Steady`](#steady-class). It is the
primary entry point and is shared across the whole process, so configuration
and the Bug Tour Report are consistent everywhere.

Use it as:

* a **decorator** — `@steady`
* a **context manager** — `with steady:`
* an **import hook** — `steady("module_name")`

---

## `Steady` class

```python
from steady import Steady

s = Steady()
```

The main fault-tolerance class. You normally use the singleton `steady`
instance, but you can construct independent instances (e.g. for tests or
isolated reports).

### `Steady.__init__()`

Create a fresh instance with default config, an empty Bug Tour Report, and an
LLM client. Reads the process-wide config singleton.

### `Steady.__call__(func=None)`

Use steady as a decorator or import hook.

* `@steady` or `@steady()` — decorate a function.
* `steady("module_name")` — install an import hook and import the module with
  error handling.
* `steady()` (no args) — returns `self`, for the `@steady()` syntax.

| Parameter | Type                          | Description                                     |
| --------- | ----------------------------- | ----------------------------------------------- |
| `func`    | `Callable \| str \| None`     | Callable to decorate, module name, or `None`.   |

**Returns:**
- When decorating a function: the wrapped callable.
- When passed a module name string: the imported `ModuleType` (with
  steady's import hook active).
- When called with no arguments: `self` (the `Steady` instance).

**Raises:**
- `ImportError` — if the module name cannot be found (after steady
  attempts repair on syntax/import errors).
- The original exception is re-raised if steady cannot repair a
  decorated function within `max_retries` attempts.

### `Steady.__enter__()` / `Steady.__exit__(...)`

Context-manager protocol for `with steady:`. On exit, if an exception
occurred inside the block, steady attempts AST repair and returns `True`
(suppress) if the repair succeeds, `False` (re-raise) otherwise.

### `Steady.configure(**kwargs)`

Configure the AI backend. Forwards all keyword arguments to
[`Config.configure`](#configconfigure) and re-creates the LLM client.

```python
steady.configure(api_key="sk-...", model="gpt-4o", max_retries=5)
```

### `Steady.report(format="markdown")`

Export the Bug Tour Report.

| Parameter | Type                                  | Default      | Description                       |
| --------- | ------------------------------------- | ------------ | --------------------------------- |
| `format`  | `"markdown" \| "json" \| "dict"`      | `"markdown"` | Output format.                    |

**Returns:**
- `"markdown"`: a Markdown-formatted string with emoji icons, ticket
  table, per-stop details, and a summary section.
- `"json"`: a JSON string (same structure as `"dict"`).
- `"dict"`: a Python `dict` with keys `report_id`, `bug_count`,
  `resolved`, `unresolved`, `success_rate`, `average_retries`,
  `risk_level`, `tokens`, `duration`, and `entries`.

**Raises:** Nothing — safe to call at any time.

**Example:**

```python
print(steady.report())           # Markdown to stdout
print(steady.report("json"))     # JSON string
data = steady.report("dict")     # Python dict for pipelines
```

### `Steady.bug_count`

Read-only property. The total number of bugs recorded in the report.

---

## `Config` class

```python
from steady import Config, get_config
```

Stores all runtime configuration. A single instance is shared process-wide
(see `get_config`). Reads from environment variables on construction; all
mutations are thread-safe.

### Environment variables

| Variable             | Default        | Description                                            |
| -------------------- | -------------- | ------------------------------------------------------ |
| `STEADY_API_KEY`     | *(none)*       | Primary API key. Falls back to `OPENAI_API_KEY`.       |
| `OPENAI_API_KEY`     | *(none)*       | Fallback API key when `STEADY_API_KEY` is unset.       |
| `STEADY_MODEL`       | `gpt-4o-mini`  | Model identifier sent to the provider.                |
| `STEADY_PROVIDER`    | `openai`       | `openai` or `anthropic`.                              |
| `STEADY_MAX_RETRIES` | `3`            | Maximum repair attempts per error.                     |
| `STEADY_ENABLED`     | `true`         | Master switch (`false`/`0` disables steady).            |
| `STEADY_LOG_LEVEL`   | `WARNING`      | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |

### `Config.configure(*, api_key=None, model=None, llm=None, provider=None, max_retries=None, enabled=None, log_level=None)`

Programmatically update configuration. Only provided (non-`None`) keyword
arguments are applied; existing values are preserved otherwise.

| Parameter    | Type             | Description                                                  |
| ------------ | ---------------- | ------------------------------------------------------------ |
| `api_key`    | `str \| None`    | Override the LLM API key.                                    |
| `model`      | `str \| None`    | Override the model identifier (e.g. `"gpt-4o"`).             |
| `llm`        | `Callable \| None` | A custom callable used instead of the SDKs.                 |
| `provider`   | `str \| None`    | `"openai"` or `"anthropic"`.                                 |
| `max_retries`| `int \| None`    | Maximum repair attempts per error.                           |
| `enabled`    | `bool \| None`   | Master switch. `False` disables steady entirely.            |
| `log_level`  | `str \| None`    | Logging level: `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`, `"CRITICAL"`. |

**Returns:** `None`.

**Example:**

```python
steady.configure(
    api_key="sk-...",
    model="gpt-4o",
    max_retries=5,
    log_level="INFO",
)
```

### `Config.reset()`

Reset to defaults and re-read environment variables. Clears any custom LLM
callable.

### Read-only properties

| Property    | Type        | Description                                          |
| ----------- | ----------- | ---------------------------------------------------- |
| `api_key`   | `str \| None` | The configured API key, or `None`.                |
| `model`     | `str`       | The model identifier.                                |
| `max_retries` | `int`     | Maximum repair attempts per error.                   |
| `enabled`   | `bool`      | Whether steady's error handling is active.           |
| `llm_client`| `Callable \| None` | A custom LLM callable, or `None`.             |
| `provider`  | `str`       | `"openai"` or `"anthropic"`.                        |
| `log_level` | `str`       | Logging level name (e.g. `"WARNING"`, `"INFO"`).    |

### `get_config()`

```python
from steady import get_config
config = get_config()
```

Return the process-wide `Config` singleton, created lazily on first access.

---

## `BugEntry`

```python
from steady import BugEntry
```

A single bug entry in the Bug Tour Report (one "scenic spot"). It is a
dataclass with the following fields:

| Field             | Type   | Description                                                        |
| ----------------- | ------ | ------------------------------------------------------------------ |
| `error_type`      | `str`  | Exception class name, e.g. `"ZeroDivisionError"`.                  |
| `location`        | `str`  | Where the bug occurred, e.g. `"file.py:42 in fn"`.                  |
| `explanation`     | `str`  | Human-readable description of what went wrong.                      |
| `fix_strategy`    | `str`  | `"ast_repair"`, `"llm_repair"`, or `"failed"`.                     |
| `fix_description` | `str`  | Human-readable description of the applied fix.                      |
| `retry_count`     | `int`  | How many retries were needed.                                       |
| `resolved`        | `bool` | Whether the fix succeeded.                                          |
| `timestamp`       | `str`  | ISO timestamp of when the entry was recorded (auto-set).            |

---

## `BugReport`

```python
from steady import BugReport
report = BugReport()
```

Collects and exports bug entries as a Bug Tour Report.

### `BugReport.add_entry(entry)`

Append a `BugEntry` to the report.

### `BugReport.add_tokens(count)`

Add `count` LLM tokens to the running total.

### `BugReport.export(format="markdown")`

Export the full report. Markdown includes emoji icons, a risk rating, a
ticket table, per-stop details, and a summary section (success rate, average
retries, breakdowns by error type and strategy).

| Parameter | Type                                  | Default      | Description       |
| --------- | ------------------------------------- | ------------ | ----------------- |
| `format`  | `"markdown" \| "json" \| "dict"`      | `"markdown"` | Output format.    |

### `BugReport.summary()`

Return a dict with `report_id`, `bug_count`, `resolved`, `unresolved`,
`success_rate`, `average_retries`, `risk_level`, `tokens`, `duration`, and
`entries`.

### `BugReport.clear()`

Clear all entries, reset tokens, and generate a new ticket ID.

### Properties

| Property           | Type             | Description                                                  |
| ------------------ | ---------------- | ------------------------------------------------------------ |
| `entries`          | `list[BugEntry]` | The recorded entries.                                        |
| `bug_count`        | `int`            | Total number of bugs.                                        |
| `duration_seconds` | `float`          | Seconds elapsed since the report started.                   |
| `risk_level`       | `str`            | `"none"`, `"low"`, `"medium"`, `"high"`, or `"critical"`.    |
| `success_rate`     | `float`          | Percentage of resolved bugs (`0.0`–`100.0`).                 |
| `average_retries`  | `float`          | Mean retries across entries.                                 |

#### Risk rating heuristic

* `0` bugs → `none`
* `1–2` bugs → `low`
* `3–5` bugs → `medium`
* `6–10` bugs → `high`
* `> 10` bugs → `critical`

Any **unresolved** bug of a severe type (`TypeError`, `ValueError`, `KeyError`,
`AttributeError`, `RuntimeError`, `RecursionError`, `OverflowError`,
`MemoryError`, `SystemError`) bumps the level by one tier (capped at
`critical`).

---

## `LLMClient`

```python
from steady import LLMClient
client = LLMClient()
```

Client for AI-powered code repair. Delegates to OpenAI, Anthropic, or a custom
callable based on config. If no API key or custom callable is configured,
`repair` returns `None`.

### `LLMClient.repair(*, source, error_type, error_msg, traceback_str, context=None)`

Send code + error to the LLM and get back a fix.

| Parameter       | Type             | Description                                              |
| --------------- | ---------------- | -------------------------------------------------------- |
| `source`        | `str`            | The failing function source.                            |
| `error_type`    | `str`            | The exception class name.                                |
| `error_msg`     | `str`            | The exception message (any language, incl. Chinese).     |
| `traceback_str` | `str`            | Formatted traceback string.                              |
| `context`       | `dict \| None`   | Extra context (function name, signature, args, kwargs). |

**Returns:** an `LLMRepairResult` if successful, `None` otherwise.

The prompt asks the model to return a JSON object:

```json
{
  "fixed_code": "...",
  "explanation": "...",
  "strategy": "..."
}
```

Plain-code responses are still accepted for backward compatibility.

### `create_llm_client(config=None)`

Factory function that creates an `LLMClient`.

---

## `LLMRepairResult`

```python
from steady import LLMRepairResult
```

Result of an LLM repair attempt. Dataclass fields:

| Field          | Type   | Description                                                      |
| -------------- | ------ | ---------------------------------------------------------------- |
| `fixed_code`   | `str`  | The repaired source code.                                        |
| `explanation`  | `str`  | Human-readable explanation of the fix.                            |
| `strategy`     | `str`  | Repair strategy tag (`remove_line`, `fix_value`, etc.).          |
| `success`      | `bool` | Whether the LLM produced a valid fix.                            |
| `tokens_used`  | `int`  | Tokens consumed by the call (default `0`).                        |

---

## Logging

steady integrates with Python's standard `logging` module. The logger is
named `"steady"` and its level is controlled by the
[`STEADY_LOG_LEVEL`](#environment-variables) environment variable or the
[`log_level`](#configconfigure) parameter of `Config.configure()`.

| Log level | What steady logs                                          |
| --------- | --------------------------------------------------------- |
| `DEBUG`   | Detailed repair info (function source, error analysis).  |
| `INFO`    | Bug caught, repair attempted, repair succeeded/failed.    |
| `WARNING` | A repair could not be completed — re-raising exception.  |
| `ERROR`   *(default)* | *(same as WARNING)*                            |
| `CRITICAL` | *(same as WARNING)*                                      |

By default (`WARNING`), steady is silent in the happy path — no log output
unless a repair fails. Set `STEADY_LOG_LEVEL=INFO` to see every repair in
real time:

```bash
export STEADY_LOG_LEVEL=INFO
python your_script.py
```

Or programmatically:

```python
from steady import steady

steady.configure(log_level="INFO")
```

steady ensures its logger has at least one `StreamHandler` so messages are
visible even when the application has not called `logging.basicConfig()`.
The log format is:

```
2026-07-07 12:00:00,000 [steady] INFO: Bug caught in 'divide': ...
```

You can also access the logger directly for advanced integration:

```python
import logging

steady_logger = logging.getLogger("steady")
steady_logger.setLevel(logging.DEBUG)
```

---

## CLI

```bash
python -m steady version   # print the installed version
python -m steady config    # print current config (API key masked)
python -m steady report    # print the most recent Bug Tour Report
python -m steady test      # run a quick self-test demonstrating repair
```

See the [configuration guide](configuration.md) for how to configure the AI
backend.
