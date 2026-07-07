# Examples

Real-world scenarios showing steady in action. Each example includes complete,
runnable code and the expected output.

> All examples use `from steady import steady` and run **without an API key**
> unless explicitly noted. AST repair handles everything out of the box.

---

## Table of contents

- [Scenario 1: Bug in a data processing script](#scenario-1-bug-in-a-data-processing-script)
- [Scenario 2: Demo Day code crash](#scenario-2-demo-day-code-crash)
- [Scenario 3: One-off script fault tolerance](#scenario-3-one-off-script-fault-tolerance)
- [Scenario 4: Custom LLM backend](#scenario-4-custom-llm-backend)
- [Scenario 5: Protecting a whole block with `with steady:`](#scenario-5-protecting-a-whole-block-with-with-steady)
- [Scenario 6: Bug Tour Report for post-incident analysis](#scenario-6-bug-tour-report-for-post-incident-analysis)

---

## Scenario 1: Bug in a data processing script

You wrote a data processing function. It works on your test data, but a
leftover debug line causes an `IndexError` on production data. steady removes
the offending line and the function returns the correct result.

### Code

```python
from steady import steady

@steady
def calculate_stats(data):
    """Calculate statistics on a list of numbers."""
    total = sum(data)
    average = total / len(data)
    debug = data[999]  # Bug: IndexError (data is too short in production)
    return f"Total: {total}, Average: {average:.2f}"

# Production data — only 5 elements, not 1000.
result = calculate_stats([10, 20, 30, 40, 50])
print(result)
print(f"\nBugs intercepted: {steady.bug_count}")
```

### Expected output

```
Total: 150, Average: 30.00

Bugs intercepted: 1
```

steady caught the `IndexError` on the `debug = data[999]` line, removed it via
AST repair, and re-executed the function. The `return` statement was
unaffected, so the correct result came back.

---

## Scenario 2: Demo Day code crash

It is five minutes before your demo. The sales report generator has two bugs
— an `IndexError` from a debug line and a `NameError` from a refactoring
leftover. No time to fix them. With steady, the show goes on.

### Code

```python
from steady import steady

@steady
def generate_report(sales_data):
    """Generate a formatted sales report.

    This function has 2 bugs, but steady handles them:
      1. IndexError: accessing sales_data[999] (debug leftover)
      2. NameError: referencing 'undefined_metric' (refactoring leftover)
    """
    total = sum(sales_data)
    average = total / len(sales_data)
    growth = ((sales_data[-1] - sales_data[0]) / sales_data[0]) * 100

    debug_entry = sales_data[999]      # Bug 1: IndexError
    unused_metric = undefined_metric   # Bug 2: NameError

    return (
        f"Sales Report\n"
        f"{'=' * 30}\n"
        f"Total Revenue:  ${total:,}\n"
        f"Average:        ${average:,.2f}\n"
        f"Growth:         {growth:+.1f}%"
    )

sales = [10000, 15000, 22000, 31000, 45000]
print(generate_report(sales))
```

### Expected output

```
Sales Report
==============================
Total Revenue:  $123,000
Average:        $24,600.00
Growth:         +350.0%
```

Both buggy lines were debug leftovers — removing them did not affect the
report. steady recorded both bugs in the Bug Tour Report.

---

## Scenario 3: One-off script fault tolerance

You are writing a one-off script to process a batch of records. Some records
are malformed. Instead of writing `try/except` around every line, you wrap
the whole processing function with `@steady`.

### Code

```python
from steady import steady

records = [
    {"name": "Alice", "score": 95},
    {"name": "Bob"},                    # missing "score" key
    {"score": 88},                       # missing "name" key
    {"name": "Carol", "score": 0},      # score is 0 (division by zero risk)
    {"name": "Dave", "score": 72},
]

@steady
def process_record(record):
    """Process a single record and return a formatted string."""
    percentage = record["score"] / 100 * 100
    grade = "A" if record["score"] >= 90 else "B"
    name = record["name"].upper()
    return f"{name}: {percentage:.0f}% ({grade})"

for record in records:
    result = process_record(record)
    print(result)

print(f"\nTotal bugs intercepted: {steady.bug_count}")
```

### Expected output

```
ALICE: 95% (A)
ALICE: 95% (A)
CAROL: 0% (B)
DAVE: 72% (B)

Total bugs intercepted: 2
```

Records 2 and 3 had missing keys (`KeyError`). steady removed the offending
lines and the function returned the best-effort result from the previous
successful line. The script kept running instead of crashing on the first
malformed record.

---

## Scenario 4: Custom LLM backend

You want AI-powered repairs but don't use OpenAI or Anthropic — maybe you
have a local model or a custom API. steady lets you plug in any callable.

### Code

```python
from steady import steady

# A stub LLM that returns a JSON fix. In production, this would call
# your local model (e.g. via Ollama, vLLM, or a custom HTTP endpoint).
def my_custom_llm(prompt: str):
    """A stub LLM backend for demonstration.

    The real implementation would call your model API here.
    Returns a (response, tokens) tuple.
    """
    # The prompt contains the failing source. For this demo, we
    # hardcode a fix that guards against division by zero.
    fixed_code = (
        "def divide(a, b):\n"
        "    if b == 0:\n"
        "        return 0\n"
        "    return a / b\n"
    )
    response = (
        '{"fixed_code": ' + repr(fixed_code) + ', '
        '"explanation": "Added a guard for b == 0 to return 0.", '
        '"strategy": "add_guard"}'
    )
    return response, 42  # 42 tokens used

# Configure steady to use our custom LLM.
steady.configure(llm=my_custom_llm)

@steady
def divide(a, b):
    return a / b  # ZeroDivisionError when b == 0

print(f"divide(10, 2) = {divide(10, 2)}")   # Normal case
print(f"divide(10, 0) = {divide(10, 0)}")   # LLM repairs this

# The Bug Tour Report shows the LLM repair with token usage.
print(steady.report("json"))
```

### Expected output

```json
divide(10, 2) = 5.0
divide(10, 0) = 0
{
  "report_id": "STEADY-20260707120000",
  "bug_count": 1,
  "resolved": 1,
  "unresolved": 0,
  "success_rate": 100.0,
  "average_retries": 1.0,
  "risk_level": "low",
  "tokens": 42,
  "duration": 0.01,
  "entries": [
    {
      "error_type": "ZeroDivisionError",
      "location": "...:5 in divide",
      "explanation": "Added a guard for b == 0 to return 0.",
      "fix_strategy": "llm_repair",
      "fix_description": "LLM strategy: add_guard",
      "retry_count": 1,
      "resolved": true,
      "timestamp": "2026-07-07T12:00:00.000000"
    }
  ]
}
```

The custom callable received the full prompt (with system instructions
embedded), returned a JSON response, and steady applied the fix. Token usage
was tracked and recorded in the report.

---

## Scenario 5: Protecting a whole block with `with steady:`

Sometimes you don't want to wrap a single function — you want to protect an
entire block of code. The `with steady:` context manager catches and repairs
errors anywhere inside the block.

### Code

```python
from steady import steady

# A block of mixed operations — some will fail.
with steady:
    config = {"host": "localhost", "port": 8080}
    host = config["host"]
    port = config["port"]

    # This line has a typo — 'hosst' instead of 'host'
    debug_host = config["hosst"]  # KeyError -> line removed

    # This line references an undefined variable
    extra = undefined_setting  # NameError -> line removed

    print(f"Connecting to {host}:{port}...")

print("Program continued past the errors!")
print(f"Bugs intercepted: {steady.bug_count}")
```

### Expected output

```
Connecting to localhost:8080...
Program continued past the errors!
Bugs intercepted: 2
```

The `with steady:` block caught both the `KeyError` and the `NameError`,
removed the offending lines, and continued execution. The `print` statement
ran normally because it didn't depend on the removed lines.

---

## Scenario 6: Bug Tour Report for post-incident analysis

After running your code under steady, you want to review exactly what was
fixed. The Bug Tour Report gives you a structured, exportable audit trail.

### Code

```python
from steady import steady

@steady
def fetch_and_parse(data, index):
    """Fetch and parse data — has several bugs."""
    raw = data[index]                    # IndexError if index out of range
    parsed = raw["value"]                # KeyError if "value" missing
    debug = data[999]                    # IndexError: debug leftover
    normalized = parsed / 100
    return normalized

# Run with data that triggers some bugs.
data = [{"value": 85}, {"value": 90}]
print(f"Result 1: {fetch_and_parse(data, 0)}")
print(f"Result 2: {fetch_and_parse(data, 1)}")

# Generate the full report for post-incident analysis.
print("\n" + "=" * 50)
print("POST-INCIDENT ANALYSIS")
print("=" * 50)

# Markdown report for humans.
print(steady.report())

# JSON report for machines (pipelines, dashboards, alerts).
import json
report_dict = steady.report("dict")
print("\nJSON summary:")
print(json.dumps(
    {k: v for k, v in report_dict.items() if k != "entries"},
    indent=2,
))
```

### Expected output

```
Result 1: 0.85
Result 2: 0.9

==================================================
POST-INCIDENT ANALYSIS
==================================================
# Bug Tour Report

## Ticket

| Field | Value |
| --- | --- |
| **Ticket ID** | `STEADY-20260707120000` |
| **Duration** | 0.01s |
| **Scenic spots (bugs)** | 2 |
| **Resolved** | 2 / 2 |
| **Risk rating** | Low |

## Tour Stops

### Stop 1: IndexError
- **Location:** `script.py:5 in fetch_and_parse`
- **What happened:** list index out of range
- **Fix strategy:** `ast_repair`
- **Tour commentary:** Removed error-causing statement at line 4 (IndexError: ...)
- **Retries:** 1
- **Status:** resolved

### Stop 2: IndexError
- **Location:** `script.py:5 in fetch_and_parse`
- **What happened:** list index out of range
- **Fix strategy:** `ast_repair`
- **Tour commentary:** Removed error-causing statement at line 4 (IndexError: ...)
- **Retries:** 1
- **Status:** resolved

## Summary

| Metric | Value |
| --- | --- |
| Total bugs | 2 |
| Resolved | 2 |
| Unresolved | 0 |
| Fix success rate | 100.0% |
| Average retries | 1.00 |
| Risk rating | Low |
| Duration | 0.01s |

**Bugs by error type:**

- `IndexError`: 2

**Bugs by fix strategy:**

- `ast_repair`: 2

JSON summary:
{
  "report_id": "STEADY-20260707120000",
  "bug_count": 2,
  "resolved": 2,
  "unresolved": 0,
  "success_rate": 100.0,
  "average_retries": 1.0,
  "risk_level": "low",
  "tokens": 0,
  "duration": 0.01
}
```

The Markdown report is human-readable with emoji icons and a risk rating.
The JSON report is machine-readable for integration into monitoring
pipelines, CI dashboards, or alerting systems. Both contain the same data:
every bug's error type, location, fix strategy, and resolution status.

---

## Running the example scripts

All examples are available as runnable scripts in the `examples/` directory:

```bash
git clone https://github.com/egg886/steady.git
cd steady
pip install -e .

python examples/basic_usage.py    # decorator, context manager, report
python examples/demo.py           # Scenario 2: Demo Day
python examples/advanced.py       # Scenario 4 + 6: custom LLM, JSON report
python examples/with_dotenv.py    # .env file integration
```

No API key is needed for `basic_usage.py`, `demo.py`, or the AST-repair
portions of `advanced.py`.
