# Changelog

All notable changes to **steady** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- GitHub Actions CI pipeline testing Python 3.9 through 3.13 (`ruff check`,
  `pytest --cov`).
- Automated release workflow that builds and publishes to PyPI on `v*` tags.
- Community health files: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
  `SECURITY.md`, issue templates, and pull request template.
- `steady config` CLI command that prints the current configuration with the
  API key masked.
- `steady test` CLI command that runs a quick self-test demonstrating AST
  repair end-to-end.
- Richer Bug Tour Report Markdown output: emoji icons, a risk rating
  (`none` / `low` / `medium` / `high` / `critical`), a summary section (fix
  success rate, average retries), and breakdowns by error type and fix
  strategy.
- `BugReport.risk_level`, `BugReport.success_rate`, and
  `BugReport.average_retries` properties.
- Enhanced LLM prompt: a detailed system prompt, a JSON output contract
  (`fixed_code` / `explanation` / `strategy`), richer runtime context
  (function signature, argument values), and verbatim handling of non-English
  (e.g. Chinese) error messages.
- Robust LLM response parsing that accepts JSON (with or without markdown
  fences) and falls back to raw code for backward compatibility.
- Public re-exports of `BugEntry`, `BugReport`, `LLMClient`,
  `LLMRepairResult`, `Config`, and `get_config` from the top-level package.
- `docs/` directory with `index.md`, `api.md`, and `configuration.md`.

### Changed

- `import steady` now exposes `steady.steady` (the singleton instance),
  `steady.Steady`, `steady.__version__`, and the full public API. Both
  `import steady; steady.steady` and `from steady import steady` reference the
  same singleton.

## [0.1.0] - 2026-07-07

### Added

- **`@steady` decorator** — wraps a function so runtime errors are caught and
  repaired automatically. On failure, steady tries a deterministic AST fix
  (remove the offending line) and, if an LLM is configured, an AI-powered patch.
- **`with steady:` context manager** — suppresses and repairs errors inside an
  entire code block.
- **`steady("mod")` import hook** — imports a broken module without it blowing
  up; `SyntaxError` and `ImportError` are caught and recorded.
- **AST repair** (no API key needed) — the fuckit.py approach: parse the
  function source into an AST, remove the error-causing statement, recompile,
  and re-execute. Works out of the box with zero configuration.
- **LLM repair** — when an API key or custom callable is configured, steady
  sends source + error + traceback to the model and applies the returned fix.
  Supports OpenAI, Anthropic, and custom callable backends.
- **Bug Tour Report** — a structured log of every error steady intercepts,
  using a tour-guide metaphor (ticket = report ID, scenic spots = bugs, tour
  commentary = fix description). Exportable as Markdown, JSON, or dict.
- **Configuration system** — read from environment variables
  (`STEADY_API_KEY`, `OPENAI_API_KEY`, `STEADY_MODEL`, `STEADY_PROVIDER`,
  `STEADY_MAX_RETRIES`, `STEADY_ENABLED`) or set programmatically via
  `steady.configure(...)`. No `.env` file dependency.
- **Token accounting** — LLM token usage is tracked and surfaced in the
  Bug Tour Report.
- **CLI** — `python -m steady version` prints the version;
  `python -m steady report` prints the latest Bug Tour Report.
- **99 tests** covering AST repair, configuration, core decorator/context
  manager behaviour, LLM integration, and report export formats — all passing
  without an API key.
- Zero hard runtime dependencies. `openai` and `anthropic` are optional extras.

[Unreleased]: https://github.com/egg886/steady/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/egg886/steady/releases/tag/v0.1.0
