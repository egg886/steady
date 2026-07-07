# Security Policy

## Supported versions

steady is in early development (pre-1.0). Security fixes are applied only to
the latest release and the `main` branch.

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

## Reporting a vulnerability

We take security bugs seriously and appreciate your efforts to responsibly
disclose them.

**Please do not open a public GitHub issue for security vulnerabilities.**

Instead, please report vulnerabilities privately:

1. Email **[egg886@users.noreply.github.com](mailto:egg886@users.noreply.github.com)**.
2. Include a description of the vulnerability and the potential impact.
3. Provide steps to reproduce, or a proof-of-concept if possible.
4. Suggest a fix if you have one in mind.

### What to expect

- We will acknowledge receipt of your report within **72 hours**.
- We will investigate and confirm the vulnerability within **7 days**.
- We will work on a fix and coordinate a disclosure timeline with you.
- We will credit you in the release notes (unless you prefer to remain
  anonymous).

Please give us reasonable time to address the issue before any public
disclosure. We aim to release a fix within **30 days** of confirmation, though
complex issues may take longer — we will keep you informed of progress.

## Security considerations

steady is a fault-tolerance runtime that **executes dynamically generated code**.
Be aware of the following:

- **AST repair** recompiles and executes modified source code in-process. This
  is by design — steady's job is to keep code running — but it means that any
  code steady repairs will execute with the same privileges as your
  application.
- **LLM repair** sends your source code, error messages, and tracebacks to a
  third-party API (OpenAI, Anthropic, or a custom endpoint). If your code
  contains sensitive data (secrets, personal information), configure a custom
  callable that redacts or avoids sending such data.
- steady **never** reads `.env` files. API keys are read from `os.environ`
  directly. Ensure your environment is configured securely.
- When steady is **disabled** (`STEADY_ENABLED=false` or `steady.configure(enabled=False)`),
  it behaves as a transparent pass-through — no repair, no code execution, no
  data is sent to any API.

## Scope

The following are **in scope** for this policy:

- Vulnerabilities in steady's core runtime, AST repair, LLM integration,
  import hooks, and CLI.
- Issues that could lead to information disclosure, code injection, or
  privilege escalation through steady's repair mechanisms.

The following are **out of scope**:

- Vulnerabilities in third-party dependencies (OpenAI SDK, Anthropic SDK) —
  report these to the respective maintainers.
- Bugs in user code that steady is wrapping — steady is designed to keep
  buggy code running, not to fix security flaws in that code.
- Theoretical issues without a concrete reproduction.

## Attribution

This security policy is adapted from the
[GitHub Security Policy guidelines](https://docs.github.com/en/code-security/getting-started/adding-a-security-policy-to-your-repository).
