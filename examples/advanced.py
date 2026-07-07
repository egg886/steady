"""steady advanced usage examples.

Run:  python examples/advanced.py

This script demonstrates steady's advanced features:
  1. Custom LLM backend configuration (no OpenAI/Anthropic SDK needed)
  2. Configuring max_retries
  3. Generating a JSON-format Bug Tour Report
  4. Disabling and re-enabling steady at runtime
  5. Repairing a function that takes parameters
"""

from __future__ import annotations

import json

from steady import steady

# ---------------------------------------------------------------------- #
# 1. Custom LLM backend
# ---------------------------------------------------------------------- #
# steady can use any callable as its LLM backend — no OpenAI or Anthropic
# SDK required. This is useful for local models, test stubs, or custom APIs.
#
# The callable receives the full prompt string and returns either a plain
# str or a (response, tokens) tuple. steady asks for a JSON response:
#   {"fixed_code": "...", "explanation": "...", "strategy": "..."}
#
# The LLM is used as a FALLBACK: steady first tries AST repair (remove the
# offending line). If AST repair cannot produce a fix, steady escalates to
# the LLM for a smarter patch.

def stub_llm(prompt: str):
    """A stub LLM that returns a JSON fix.

    In production, replace this with a call to your local model (e.g. via
    Ollama, vLLM, LM Studio, or a custom HTTP endpoint).
    """
    fixed_code = (
        "def safe_divide(a, b):\n"
        "    if b == 0:\n"
        "        return 0\n"
        "    return a / b\n"
    )
    response = (
        '{"fixed_code": ' + repr(fixed_code) + ', '
        '"explanation": "Added a guard to return 0 when b is zero.", '
        '"strategy": "add_guard"}'
    )
    return response, 42  # (response_text, tokens_used)


# Configure steady: plug in the custom LLM, bump max_retries, and enable
# INFO-level logging so you can see repairs in real time.
steady.configure(
    llm=stub_llm,
    max_retries=5,
    log_level="INFO",
)


# ---------------------------------------------------------------------- #
# 2. Function with parameters (AST-repaired)
# ---------------------------------------------------------------------- #
@steady
def safe_divide(a, b):
    """Divide a by b.

    When b is 0, ZeroDivisionError is raised. steady's AST repair removes
    the offending line and the function returns None. If AST repair could
    not fix it (e.g. the source cannot be read), steady would escalate to
    the custom LLM configured above.
    """
    return a / b


# ---------------------------------------------------------------------- #
# 3. Function with multiple debug-leftover bugs (AST-repaired)
# ---------------------------------------------------------------------- #
@steady
def analyze_data(data):
    """Analyze a list of numbers.

    Contains debug leftovers that cause IndexError and NameError, but
    steady removes them via AST repair (no LLM needed).
    """
    total = sum(data)
    average = total / len(data)
    debug = data[999]          # Bug: IndexError (debug leftover)
    leftover = undefined_var  # Bug: NameError (refactoring leftover)
    return {"total": total, "average": round(average, 2)}


def main():
    print()
    print("=" * 55)
    print("  steady Advanced Examples")
    print("=" * 55)
    print()

    # --- Section 1: Custom LLM configuration ---
    print("-" * 55)
    print("1. Custom LLM backend configured")
    print("-" * 55)
    print("   steady is configured with a custom callable as its LLM.")
    print("   AST repair runs first (zero-config, no network).")
    print("   The LLM is a fallback for when AST repair cannot fix it.")
    print()

    # --- Section 2: Function with parameters ---
    print("-" * 55)
    print("2. Repairing a function with parameters")
    print("-" * 55)

    print(f"   safe_divide(10, 2) = {safe_divide(10, 2)}")
    print(f"   safe_divide(10, 0) = {safe_divide(10, 0)}  (AST repaired)")
    print()

    # --- Section 3: Multiple bugs ---
    print("-" * 55)
    print("3. AST repair (multiple debug-leftover bugs)")
    print("-" * 55)

    result = analyze_data([10, 20, 30, 40, 50])
    print(f"   analyze_data result: {result}")
    print()

    # --- Section 4: JSON-format Bug Tour Report ---
    print("-" * 55)
    print("4. JSON-format Bug Tour Report")
    print("-" * 55)

    json_report = steady.report("json")
    report_data = json.loads(json_report)
    # Print the summary without the full entries list for brevity.
    summary = {k: v for k, v in report_data.items() if k != "entries"}
    print(f"   {json.dumps(summary, indent=2)}")
    print(f"   Total entries: {len(report_data['entries'])}")
    print()

    # --- Section 5: Disabling and re-enabling steady ---
    print("-" * 55)
    print("5. Disabling and re-enabling steady at runtime")
    print("-" * 55)

    # Use a FRESH function that has not been repaired yet, so the decorator
    # wrapper is still in place. Once steady repairs a function, the repaired
    # version replaces it in the module globals — so we need a new function
    # to demonstrate the disable/enable behavior.
    @steady
    def risky_divide(a, b):
        return a / b

    # Disable steady — exceptions propagate normally.
    steady.configure(enabled=False)
    print("   steady disabled. Calling risky_divide(10, 0)...")
    try:
        risky_divide(10, 0)
    except ZeroDivisionError:
        print("   -> ZeroDivisionError raised (steady was disabled)")
    print()

    # Re-enable steady — errors are caught and repaired again.
    steady.configure(enabled=True)
    print("   steady re-enabled. Calling risky_divide(10, 0)...")
    result = risky_divide(10, 0)
    print(f"   -> Result: {result} (steady repaired it)")
    print()

    # --- Section 6: Final summary ---
    print("=" * 55)
    print("  Final Bug Tour Report Summary")
    print("=" * 55)
    summary = steady.report("dict")
    print(f"  Bug count:     {summary['bug_count']}")
    print(f"  Resolved:      {summary['resolved']}")
    print(f"  Unresolved:    {summary['unresolved']}")
    print(f"  Success rate:  {summary['success_rate']}%")
    print(f"  Risk level:    {summary['risk_level']}")
    print(f"  LLM tokens:    {summary['tokens']}")
    print("=" * 55)


if __name__ == "__main__":
    main()
