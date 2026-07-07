# steady — Documentation

> 稳住，代码能跑。
>
> *Stay steady, the code runs.*

**steady** is an AI-native fault-tolerant Python runtime and the spiritual
successor to [fuckit.py](https://github.com/ajalt/fuckitpy). It wraps your
code in a forgiving runtime that swallows errors, repairs broken functions on
the fly, and keeps your program moving.

---

## Why steady?

Every production codebase has a bug or two that you "just live with". fuckit.py
taught us that sometimes the right move is to **delete the line that blows up
and keep running**. steady takes that philosophy and adds two things on top:

1. **AI-native repair** — when a line can't simply be deleted (it produces a
   needed value, or the bug is a logic error), steady asks an LLM for a minimal
   patch, applies it, and re-executes.
2. **A transparent audit log** — every detour your execution takes is recorded
   in a **Bug Tour Report**, so you always know what steady silently fixed for
   you.

### Two-tier repair strategy

| Tier   | Needs API key? | What it does                                                  |
| ------ | -------------- | ------------------------------------------------------------- |
| AST    | No             | Removes the offending statement from the AST and re-runs.    |
| LLM    | Yes (optional) | Sends source + error + traceback to an LLM and applies the fix. |

AST repair runs **out of the box with zero configuration**. LLM repair is an
opt-in upgrade: configure an API key (or a custom callable) and steady will
escalate to it automatically when AST repair alone is not enough.

---

## Installation

```bash
# Base package — AST repair only, works with no API key.
pip install steady

# With the OpenAI SDK.
pip install steady[openai]

# With the Anthropic SDK.
pip install steady[anthropic]
```

steady has **no hard runtime dependencies** and requires Python 3.9+.

---

## Quick start

### 1. The `@steady` decorator

```python
from steady import steady

@steady
def divide(a, b):
    return a / b

print(divide(10, 0))  # ZeroDivisionError is caught and repaired
```

### 2. The `with steady:` context manager

```python
from steady import steady

with steady:
    x = 1 / 0          # ZeroDivisionError -> line removed
    y = undefined_var  # NameError -> line removed
    print("still running!")  # this line executes
```

### 3. The `steady("module")` import hook

```python
from steady import steady

broken = steady("broken_module")  # would normally raise SyntaxError
broken.do_thing()                 # steady tries to fix on the fly
```

> `from steady import steady` and `import steady; steady.steady` reference the
> **same** singleton instance — use whichever reads better in your code.

---

## Command-line interface

```bash
python -m steady version   # print the installed version
python -m steady config    # print current config (API key masked)
python -m steady report    # print the most recent Bug Tour Report
python -m steady test      # run a quick self-test demonstrating repair
```

---

## Documentation index

| Document                                      | Contents                                            |
| --------------------------------------------- | --------------------------------------------------- |
| [Configuration guide](configuration.md)       | Environment variables, programmatic config, custom LLM backends. |
| [API reference](api.md)                       | Detailed reference for every public class and method. |
| [README](../README.md)                        | Project overview, install, and quick start.         |
| [Changelog](../CHANGELOG.md)                  | Release history.                                   |
| [Contributing](../CONTRIBUTING.md)            | How to set up a dev environment and contribute.      |

---

## Design principles

* **Works with zero configuration.** No API key? No problem — AST repair runs
  out of the box.
* **AI is an enhancement, not a requirement.** Plug in OpenAI, Anthropic, or
  your own callable to upgrade from "delete the line" to "actually fix it".
* **Never silently hide what it did.** Every repair is recorded in the Bug Tour
  Report, with the error type, location, fix strategy, and retry count.
* **No hard dependencies.** The `openai` and `anthropic` SDKs are optional
  extras; steady's core is pure Python.
* **We don't read your `.env` files.** steady reads `os.environ` directly.
  Load your `.env` with `python-dotenv` yourself — it's your secret.

---

## License

[MIT](../LICENSE) — Copyright (c) 2026 steady contributors.
