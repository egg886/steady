# Changelog

All notable changes to **steady** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Logging support** — steady now integrates with Python's standard
  `logging` module (logger name: `"steady"`). Control the level via the
  new `STEADY_LOG_LEVEL` environment variable (default: `WARNING`) or the
  `log_level` parameter in `steady.configure(...)`. At `INFO` level, steady
  logs every bug caught, repair attempted, and repair outcome in real time.
  A `StreamHandler` is auto-configured so messages are visible without
  `logging.basicConfig()`.
- `STEADY_LOG_LEVEL` environment variable for controlling log verbosity.
- `log_level` parameter in `Config.configure()` and corresponding
  `Config.log_level` read-only property.
- `docs/examples.md` — a complete examples document with six real-world
  scenarios (data processing bug, Demo Day crash, one-off script tolerance,
  custom LLM backend, `with steady:` block protection, and Bug Tour Report
  for post-incident analysis), each with full code and expected output.
- `examples/advanced.py` — advanced usage demo: custom LLM backend,
  `max_retries` configuration, JSON report generation, runtime
  enable/disable, and function repair with parameters.
- `examples/with_dotenv.py` — `.env` file integration example using
  `python-dotenv`, with explanation of why steady does not read `.env` files
  itself.
- GitHub Actions CI pipeline testing Python 3.9 through 3.13 (`ruff check`,
  `pytest --cov`).
- Automated release workflow that builds and publishes to PyPI on `v*` tags.
- Community health files: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
  `SECURITY.md`, issue templates, and pull request template.
- `steady config` CLI command that prints the current configuration with the
  API key masked. Now also displays the `log_level` setting.
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
- `docs/` directory with `index.md`, `api.md`, `configuration.md`, and
  `examples.md`.

### Changed

- **Enhanced test coverage** — test suite expanded to 128 tests covering AST
  repair, configuration (including `log_level`), core decorator/context
  manager behaviour, import hooks, LLM integration, and report export
  formats — all passing without an API key.
- `import steady` now exposes `steady.steady` (the singleton instance),
  `steady.Steady`, `steady.__version__`, and the full public API. Both
  `import steady; steady.steady` and `from steady import steady` reference the
  same singleton.
- `Steady.configure()` now re-applies the log level after re-creating the LLM
  client, so logging configuration stays in sync.
- README.md significantly expanded with "How It Works" (ASCII flow diagram of
  the two-tier repair strategy), "Why steady?" (try/except pain comparison),
  and "Performance" (AST repair near-zero overhead) sections.
- `docs/api.md` updated with `log_level` parameter/property, return value
  details, exception documentation, and a dedicated "Logging" section.
- `docs/configuration.md` updated with `STEADY_LOG_LEVEL` and a "Logging"
  section (section 7).
- `pyproject.toml` ruff configuration updated to include `examples/` in
  `src` and add per-file-ignores for example files (intentional bugs and
  Chinese catchphrase characters).

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
