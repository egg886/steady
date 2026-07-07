# Contributing to steady

First off, thank you for taking the time to contribute to **steady**!

steady is an AI-native fault-tolerant Python runtime — the spiritual successor
to [fuckit.py](https://github.com/ajalt/fuckitpy). Every contribution, big or
small, helps make Python code a little more resilient. 稳住，代码能跑。

This document covers everything you need to get started.

---

## Table of contents

- [Code of conduct](#code-of-conduct)
- [Development environment setup](#development-environment-setup)
- [Project structure](#project-structure)
- [Code style](#code-style)
- [Testing](#testing)
- [Type checking](#type-checking)
- [Git workflow](#git-workflow)
- [Branching strategy](#branching-strategy)
- [Commit messages and signing](#commit-messages-and-signing)
- [Submitting a pull request](#submitting-a-pull-request)
- [Reporting bugs](#reporting-bugs)
- [Releases](#releases)

---

## Code of conduct

Participation in this project is governed by the [Contributor Covenant Code of
Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this
code. Please report unacceptable behaviour to
[egg886@users.noreply.github.com](mailto:egg886@users.noreply.github.com).

---

## Development environment setup

steady targets **Python 3.9+** and has no hard runtime dependencies. The
development toolchain (pytest, ruff, mypy, openai, anthropic) is installed via
the `dev` extra.

```bash
# 1. Fork the repo on GitHub, then clone your fork.
git clone https://github.com/<your-username>/steady.git
cd steady

# 2. (Optional) Create and activate a virtual environment.
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# 3. Install steady in editable mode with dev dependencies.
pip install -e ".[dev]"
```

You can verify the installation:

```bash
python -m steady version     # prints the installed version
python -m steady test        # runs a quick AST-repair self-test
ruff --version
pytest --version
```

---

## Project structure

```
steady/
├── src/steady/          # Package source code
│   ├── __init__.py      # Public API + global `steady` singleton instance
│   ├── __main__.py      # CLI entry point (python -m steady)
│   ├── _version.py      # Version string
│   ├── core.py          # Steady class (decorator, context manager, import hook)
│   ├── ast_fixer.py     # AST-based error removal (no API key needed)
│   ├── llm.py           # LLM-powered repair (OpenAI / Anthropic / custom)
│   ├── config.py        # Configuration management (env vars + programmatic)
│   ├── hooks.py         # Import hook for steady("module")
│   ├── report.py        # Bug Tour Report (markdown / json / dict)
│   └── py.typed         # PEP 561 marker
├── tests/               # Test suite (99 tests, no API key needed)
├── examples/            # Usage examples
├── docs/                # Documentation
├── pyproject.toml       # Build config, ruff/mypy/pytest/coverage settings
└── conftest.py          # Adds src/ to sys.path for test runs
```

---

## Code style

We use [ruff](https://docs.astral.sh/ruff/) for both linting and formatting.
The configuration lives in `pyproject.toml` under `[tool.ruff]`.

- **Line length:** 100 characters
- **Target version:** Python 3.9
- **Import sorting:** isort rules (`I`) are enabled

Check your code before committing:

```bash
ruff check src/ tests/
```

Many issues can be auto-fixed:

```bash
ruff check --fix src/ tests/
```

### Type annotations

All source files use `from __future__ import annotations`, so modern PEP 604
union syntax (`X | None` instead of `Optional[X]`) is preferred throughout.

---

## Testing

All tests live in `tests/`. They do **not** require an API key — they exercise
the AST repair path (the fuckit.py-style "remove the offending line and rerun"
approach) and the LLM integration with injected custom callables.

Run the full suite with coverage:

```bash
pytest tests/ --cov=steady --cov-report=term-missing
```

### Writing tests

- Follow the existing structure: group related tests with `# ----` comment
  separators and use descriptive function names starting with `test_`.
- Each test should be independent and deterministic.
- Use the `_isolate_state` fixture pattern (see `tests/test_core.py`) to clear
  the global steady report between tests.
- steady's tests intentionally contain "buggy" code (undefined names, unused
  variables). These patterns are expected — they are what steady is designed to
  handle. The ruff configuration already ignores `F841` and `F821` in `tests/`.

---

## Type checking

steady is fully typed (PEP 561 `py.typed` marker). We use
[mypy](https://mypy-lang.org/) in strict mode:

```bash
mypy src/steady
```

All new public functions and methods should have type annotations and
docstrings.

---

## Git workflow

### Forking and branching

1. **Fork** the repository on GitHub.
2. **Clone** your fork locally (see [Development environment setup](#development-environment-setup)).
3. **Add an upstream remote** to keep your fork in sync:

   ```bash
   git remote add upstream https://github.com/egg886/steady.git
   git fetch upstream
   ```

4. **Create a feature branch** from the latest `main`:

   ```bash
   git checkout main
   git pull upstream main
   git checkout -b feature/your-feature-name
   ```

### Branching strategy

| Branch pattern    | Purpose                                    |
| ----------------- | ------------------------------------------ |
| `main`            | Stable, release-ready code. Always green. |
| `feature/*`       | New features                               |
| `fix/*`           | Bug fixes                                  |
| `docs/*`          | Documentation-only changes                 |
| `chore/*`         | Tooling, dependencies, CI changes          |

---

## Commit messages and signing

### Commit message format

Use clear, descriptive commit messages in the imperative mood. We loosely
follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add retry budget configuration
fix: handle multiline statement removal in AST repair
docs: expand LLM prompt documentation
test: cover JSON response parsing in llm client
```

Keep the subject line under 72 characters. Reference issues with `Closes #123`
or `Refs #123` in the body when applicable.

### Commit signing (DCO — optional)

We encourage but do not strictly require commit signing. If you can, sign
your commits with `git commit -S` or configure GPG/SSH signing globally.

As a lightweight alternative, we support the
[Developer Certificate of Origin (DCO)](https://developercertificate.org/).
By submitting a contribution, you certify that you have the right to submit
it under the project's MIT license. To indicate this, add a `Signed-off-by`
line to your commit:

```bash
git commit -s -m "feat: add retry budget configuration"
```

This is optional. Either signing or `Signed-off-by` is appreciated but not
mandatory.

---

## Submitting a pull request

1. **Rebase** your branch onto the latest `main`:

   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run all checks locally:**

   ```bash
   ruff check src/ tests/
   mypy src/steady
   pytest tests/ --cov=steady
   ```

3. **Push** to your fork:

   ```bash
   git push origin feature/your-feature-name
   ```

4. **Open a pull request** against the `egg886/steady:main` branch. Fill in the
   [PR template](.github/PULL_REQUEST_TEMPLATE.md).

5. **Respond to review feedback** by pushing additional commits (do not squash
   until the PR is approved).

### PR expectations

- All CI checks (ruff, pytest across Python 3.9–3.13) must pass.
- New public API should be documented with docstrings.
- New features should include tests.
- Update `CHANGELOG.md` under the `[Unreleased]` section if applicable.

---

## Reporting bugs

Use the [Bug Report template](.github/ISSUE_TEMPLATE/bug_report.md) to file an
issue. Include:

- A minimal reproduction snippet.
- The full traceback or unexpected output.
- Your Python version and steady version (`python -m steady version`).
- The Bug Tour Report (`python -m steady report`) if steady was involved.

---

## Releases

steady follows [Semantic Versioning](https://semver.org/). The release process:

1. A maintainer updates `CHANGELOG.md` and `src/steady/_version.py`.
2. A Git tag `vX.Y.Z` is pushed.
3. The [release workflow](.github/workflows/release.yml) builds the
   distributions and publishes them to PyPI automatically.

---

Questions? Feel free to
[open a discussion](https://github.com/egg886/steady/discussions) or an issue.
Happy hacking!
