"""End-to-end integration tests for steady.

These tests exercise the *complete* steady flow — decoration, AST repair,
re-execution, and Bug Tour Report generation — using realistic, multi-step
scenarios rather than isolated units.  No real API key is required: every
test relies on the AST-only repair path (the ``fuckit.py`` strategy of
removing the offending line and re-running).
"""

from __future__ import annotations

import json
import sys

import pytest

from steady import steady
from steady.core import Steady


# ---------------------------------------------------------------------- #
# Fixtures
# ---------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _isolate_state():
    """Isolate global state before and after each integration test.

    Clears the shared bug report and protects ``sys.excepthook`` from
    leakage caused by the context-manager protocol (which replaces it with
    a no-op for the duration of a ``with steady:`` block).
    """
    steady._report.clear()
    saved_excepthook = sys.excepthook
    yield
    sys.excepthook = saved_excepthook
    steady._report.clear()


@pytest.fixture
def enabled_steady():
    """Ensure steady is enabled, and restore it after the test."""
    steady.configure(enabled=True)
    yield steady
    steady.configure(enabled=True)


# ---------------------------------------------------------------------- #
# Full AST repair flow
# ---------------------------------------------------------------------- #
def test_full_ast_repair_flow(enabled_steady):
    """End-to-end: a buggy function is repaired by AST removal, returns the
    correct value, and the Bug Tour Report reflects the fix."""

    @enabled_steady
    def calculate_average(numbers):
        total = sum(numbers)
        count = len(numbers)
        debug = total / 0  # ZeroDivisionError — stray debug line
        return total / count

    result = calculate_average([1, 2, 3, 4])

    # The debug line was removed, so the real computation succeeds.
    assert result == 2.5  # 10 / 4

    # The report captured the bug.
    assert enabled_steady.bug_count >= 1
    report = enabled_steady.report(format="dict")
    assert report["bug_count"] >= 1
    assert report["resolved"] >= 1
    assert any(
        e["error_type"] == "ZeroDivisionError" for e in report["entries"]
    )

    # The markdown report is human-readable.
    md = enabled_steady.report(format="markdown")
    assert "Bug Tour Report" in md
    assert "ZeroDivisionError" in md


# ---------------------------------------------------------------------- #
# Multiple independent decorated functions
# ---------------------------------------------------------------------- #
def test_multiple_functions_decorated(enabled_steady):
    """Several decorated functions should each handle their own bugs
    independently without interfering with one another."""

    @enabled_steady
    def func_a():
        debug_a = 1 / 0  # ZeroDivisionError
        return "a"

    @enabled_steady
    def func_b():
        debug_b = undefined_name  # NameError
        return "b"

    @enabled_steady
    def func_c():
        return "c"  # no bug at all

    assert func_a() == "a"
    assert func_b() == "b"
    assert func_c() == "c"

    # Only the two buggy functions generated report entries.
    assert enabled_steady.bug_count >= 2
    report = enabled_steady.report(format="dict")
    error_types = {e["error_type"] for e in report["entries"]}
    assert "ZeroDivisionError" in error_types
    assert "NameError" in error_types


# ---------------------------------------------------------------------- #
# Mixed decorator + context manager
# ---------------------------------------------------------------------- #
def test_mixed_decorator_and_context(enabled_steady):
    """Using both the decorator and the context manager together should
    work: the decorator handles function-body bugs while the context
    manager suppresses block-level exceptions."""

    @enabled_steady
    def decorated():
        debug = 1 / 0  # decorator handles this
        return "decorated-ok"

    # Decorator path — the bug is auto-repaired.
    assert decorated() == "decorated-ok"

    # Context-manager path — a bare exception is suppressed.
    with enabled_steady:
        raise ValueError("block-level error")

    # Both paths contributed to the report.
    assert enabled_steady.bug_count >= 2
    report = enabled_steady.report(format="dict")
    types = {e["error_type"] for e in report["entries"]}
    assert "ZeroDivisionError" in types
    assert "ValueError" in types


# ---------------------------------------------------------------------- #
# Report accumulates across multiple fixes
# ---------------------------------------------------------------------- #
def test_report_after_multiple_fixes(enabled_steady):
    """After several independent fixes, the report should contain every
    recorded bug in submission order."""

    @enabled_steady
    def first():
        bug = 1 / 0  # ZeroDivisionError
        return 1

    @enabled_steady
    def second():
        bug = missing_variable  # NameError
        return 2

    @enabled_steady
    def third():
        bug = [1, 2][99]  # IndexError
        return 3

    first()
    second()
    third()

    assert enabled_steady.bug_count >= 3

    report = enabled_steady.report(format="dict")
    assert report["bug_count"] >= 3
    assert report["resolved"] >= 3

    # Every error type is represented.
    types = {e["error_type"] for e in report["entries"]}
    assert {"ZeroDivisionError", "NameError", "IndexError"} <= types

    # The JSON export is valid and consistent with the dict export.
    json_report = json.loads(enabled_steady.report(format="json"))
    assert json_report["bug_count"] == report["bug_count"]


# ---------------------------------------------------------------------- #
# Real-world data-processing scenario
# ---------------------------------------------------------------------- #
def test_steady_with_real_world_scenarios(enabled_steady):
    """Simulate a real-world data pipeline where a stray debug statement
    crashes the loop. steady removes the offending line and the pipeline
    completes with the correct results."""

    @enabled_steady
    def process_records(records):
        results = []
        for record in records:
            # A debug line accidentally divides by zero.
            debug_ratio = record["value"] / 0
            results.append(record["value"] * 2)
        return results

    data = [
        {"value": 10},
        {"value": 20},
        {"value": 30},
    ]
    result = process_records(data)

    # The debug line was stripped, so each record is doubled correctly.
    assert result == [20, 40, 60]
    assert enabled_steady.bug_count >= 1


# ---------------------------------------------------------------------- #
# Recursive function
# ---------------------------------------------------------------------- #
def test_recursive_function_repair(enabled_steady):
    """A recursive function with a stray bug should be repaired so the
    recursion completes correctly."""

    @enabled_steady
    def factorial(n):
        if n <= 1:
            return 1
        debug = 1 / 0  # ZeroDivisionError on every non-base call
        return n * factorial(n - 1)

    result = factorial(5)

    assert result == 120
    # At least one repair was performed.
    assert enabled_steady.bug_count >= 1


# ---------------------------------------------------------------------- #
# Lambda — not supported
# ---------------------------------------------------------------------- #
def test_lambda_not_supported(enabled_steady):
    """Lambda functions cannot be reliably AST-repaired: ``inspect`` can
    fetch the source line but the recompile/repair path cannot produce a
    valid standalone ``def``. steady therefore re-raises the original
    exception rather than silently masking it."""

    buggy_lambda = enabled_steady(lambda x: x / 0)

    with pytest.raises(ZeroDivisionError):
        buggy_lambda(1)

    # steady still recorded the (failed) repair attempt.
    assert enabled_steady.bug_count >= 1
    report = enabled_steady.report(format="dict")
    assert report["unresolved"] >= 1


# ---------------------------------------------------------------------- #
# Generator function
# ---------------------------------------------------------------------- #
def test_generator_function(enabled_steady):
    """Generator-body bugs fire lazily during iteration, *outside* the
    wrapper's try/except, so steady cannot intercept them. The generator
    is still created and yields values up to the failing line, after
    which the error propagates normally."""

    @enabled_steady
    def count_up():
        yield 1
        yield 2
        bad = 1 / 0  # fires on the third next() call
        yield 3

    g = count_up()  # generator created; wrapper returns it cleanly
    assert next(g) == 1
    assert next(g) == 2
    with pytest.raises(ZeroDivisionError):
        next(g)  # bug triggers during iteration — not caught by steady

    # No bugs were recorded: the error never passed through the wrapper.
    assert enabled_steady.bug_count == 0


def test_generator_function_no_bug(enabled_steady):
    """A decorated generator function without bugs should iterate
    normally and produce a usable generator object."""

    @enabled_steady
    def squares(n):
        for i in range(n):
            yield i * i

    gen = squares(4)
    assert hasattr(gen, "__next__")
    assert list(gen) == [0, 1, 4, 9]
    assert enabled_steady.bug_count == 0


# ---------------------------------------------------------------------- #
# Fresh Steady instance — full flow
# ---------------------------------------------------------------------- #
def test_fresh_instance_full_flow():
    """A freshly-constructed :class:`Steady` instance should support the
    complete decorate -> repair -> report cycle independently."""

    s = Steady()

    @s
    def risky(a, b):
        noise = a / 0  # ZeroDivisionError
        return a + b

    assert risky(2, 3) == 5
    assert s.bug_count == 1

    report = s.report(format="dict")
    assert report["bug_count"] == 1
    assert report["resolved"] == 1
