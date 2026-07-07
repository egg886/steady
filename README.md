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

---

## Table of contents

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

```bash
export STEADY_API_KEY="sk-..."
# or, reuse an existing OpenAI key:
export OPENAI_API_KEY="sk-..."
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
AI layer and a reporting layer on top.

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
