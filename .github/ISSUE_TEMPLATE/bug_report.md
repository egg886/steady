---
name: Bug report
about: Report a bug so steady can keep your code running
title: "[Bug]: "
labels: bug, triage
assignees: ""
---

## Description

A clear and concise description of what the bug is.

## Steps to reproduce

Steps to reproduce the behavior:

1. ...
2. ...
3. ...

Minimal code example that triggers the bug:

```python
from steady import steady

# Replace with the smallest snippet that reproduces the issue.
@steady
def example():
    ...
```

## Expected behavior

What you expected to happen.

## Actual behavior

What actually happened, including any error messages, tracebacks, or unexpected
output.

```text
# Paste the full traceback or output here
```

## Environment

- **Python version:** <!-- e.g. 3.12.3 -->
- **steady version:** <!-- run `python -m steady version` or `pip show steady` -->
- **OS:** <!-- e.g. macOS 14.4, Ubuntu 22.04, Windows 11 -->
- **LLM provider configured (optional):** <!-- openai / anthropic / custom callable / none -->
- **steady configuration (optional):**

  ```python
  steady.configure(...)
  ```

## Additional context

Add any other context about the problem here. If applicable, attach the Bug
Tour Report (`python -m steady report`).
