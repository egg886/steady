"""Tests for the steady core module.

These tests do NOT require an API key — they only exercise the AST repair
path, which is the fuckit.py-style "remove the error line and rerun" approach.
"""

from __future__ import annotations

import sys

import pytest

from steady import steady
from steady.core import Steady


# ---------------------------------------------------------------------- #
# Fixtures
# ---------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _isolate_state():
    """Isolate global state before and after each test.

    Clears the global steady report and protects ``sys.excepthook`` from
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
# Basic decorator tests
# ---------------------------------------------------------------------- #
def test_decorator_basic(enabled_steady):
    """A normal function should pass through unchanged."""

    @enabled_steady
    def add(a, b):
        return a + b

    assert add(2, 3) == 5


def test_decorator_zero_division(enabled_steady):
    """ZeroDivisionError should be handled by removing the offending line."""

    @enabled_steady
    def divide():
        bad = 1 / 0
        return 42

    assert divide() == 42


def test_decorator_name_error(enabled_steady):
    """NameError (e.g. typo) should be handled."""

    @enabled_steady
    def name_err():
        result = undefined_variable
        return 99

    assert name_err() == 99


def test_decorator_value_error(enabled_steady):
    """ValueError should be handled."""

    @enabled_steady
    def val_err():
        data = [1, 2, 3]
        bad = data[100]
        return len(data)

    assert val_err() == 3


def test_decorator_index_error(enabled_steady):
    """IndexError should be handled."""

    @enabled_steady
    def idx_err():
        data = [1, 2]
        extra = data[99]
        return sum(data)

    assert idx_err() == 3


def test_decorator_attribute_error(enabled_steady):
    """AttributeError should be handled."""

    @enabled_steady
    def attr_err():
        x = 5
        bad = x.nonexistent_method()
        return x * 2

    assert attr_err() == 10


# ---------------------------------------------------------------------- #
# Multiple bugs
# ---------------------------------------------------------------------- #
def test_multiple_bugs(enabled_steady):
    """Multiple bugs in one function should be fixed sequentially."""

    @enabled_steady
    def multi():
        total = sum([1, 2, 3])
        debug_1 = [1, 2, 3][99]  # IndexError
        debug_2 = undefined_var  # NameError
        return total

    result = multi()
    assert result == 6
    assert enabled_steady.bug_count >= 2


# ---------------------------------------------------------------------- #
# Context manager
# ---------------------------------------------------------------------- #
def test_context_manager_suppresses(enabled_steady):
    """``with steady:`` should suppress exceptions."""

    with enabled_steady:
        raise ValueError("oops")

    # If we reach here, the exception was suppressed
    assert True


def test_context_manager_no_error(enabled_steady):
    """``with steady:`` with no error should work normally."""

    with enabled_steady:
        result = 1 + 1

    assert result == 2


# ---------------------------------------------------------------------- #
# Report
# ---------------------------------------------------------------------- #
def test_report_generation(enabled_steady):
    """After fixing a bug, the report should be non-empty."""

    @enabled_steady
    def buggy():
        bad = 1 / 0
        return "ok"

    buggy()
    report = enabled_steady.report()
    assert isinstance(report, str)
    assert len(report) > 0
    assert "Bug Tour Report" in report


def test_report_json_format(enabled_steady):
    """JSON report format should work."""

    @enabled_steady
    def buggy():
        bad = 1 / 0
        return "ok"

    buggy()
    report = enabled_steady.report(format="json")
    assert isinstance(report, str)
    import json

    data = json.loads(report)
    assert data["bug_count"] >= 1


def test_report_dict_format(enabled_steady):
    """Dict report format should return a dict."""

    @enabled_steady
    def buggy():
        bad = 1 / 0
        return "ok"

    buggy()
    report = enabled_steady.report(format="dict")
    assert isinstance(report, dict)
    assert report["bug_count"] >= 1


def test_empty_report(enabled_steady):
    """Report with no bugs should indicate that."""

    report = enabled_steady.report()
    assert isinstance(report, str)
    assert "No bugs" in report or "uneventful" in report


# ---------------------------------------------------------------------- #
# Disabled
# ---------------------------------------------------------------------- #
def test_disabled_re_raises(enabled_steady):
    """When disabled, steady should let exceptions propagate."""

    steady.configure(enabled=False)

    @enabled_steady
    def crash():
        return 1 / 0

    with pytest.raises(ZeroDivisionError):
        crash()


def test_re_enable_after_disable(enabled_steady):
    """Re-enabling steady should restore error handling."""

    steady.configure(enabled=False)
    steady.configure(enabled=True)

    @enabled_steady
    def crash():
        bad = 1 / 0
        return 42

    assert crash() == 42


# ---------------------------------------------------------------------- #
# Fresh Steady instance
# ---------------------------------------------------------------------- #
def test_fresh_instance():
    """A fresh Steady instance should work independently."""
    s = Steady()

    @s
    def buggy():
        bad = 1 / 0
        return 77

    assert buggy() == 77
    assert s.bug_count == 1


# ---------------------------------------------------------------------- #
# __call__ with string (import hook)
# ---------------------------------------------------------------------- #
def test_call_with_none_returns_self(enabled_steady):
    """``steady()`` with no args should return self (for ``@steady()`` syntax)."""
    assert enabled_steady() is enabled_steady


# ---------------------------------------------------------------------- #
# Metadata & signature preservation
# ---------------------------------------------------------------------- #
def test_decorator_preserves_metadata(enabled_steady):
    """``@steady`` should preserve the wrapped function's __name__ and __doc__."""

    @enabled_steady
    def my_func():
        """This is my docstring."""
        return 42

    assert my_func.__name__ == "my_func"
    assert my_func.__doc__ == "This is my docstring."


def test_decorator_with_arguments(enabled_steady):
    """A decorated function with positional args should receive them after repair."""

    @enabled_steady
    def add_and_bug(a, b):
        bad = 1 / 0
        return a + b

    assert add_and_bug(3, 4) == 7


def test_decorator_with_kwargs(enabled_steady):
    """A decorated function with keyword args should receive them after repair."""

    @enabled_steady
    def greet(name, greeting="Hello"):
        bad = undefined_var
        return f"{greeting}, {name}"

    assert greet("World") == "Hello, World"
    assert greet("World", greeting="Hi") == "Hi, World"


def test_decorated_function_attribute(enabled_steady):
    """The wrapper should expose a ``_steady_wrapped`` marker attribute."""

    @enabled_steady
    def f():
        return 1

    assert hasattr(f, "_steady_wrapped")
    assert f._steady_wrapped is True


# ---------------------------------------------------------------------- #
# Exhausted-repair / re-raise
# ---------------------------------------------------------------------- #
def test_decorator_returns_none_on_all_fail(enabled_steady):
    """When all repair attempts are exhausted, the original exception is re-raised.

    The function contains more bugs than the configured ``max_retries`` (3),
    so after removing the first few offending lines steady runs out of
    retries and re-raises the original ``NameError``.
    """

    @enabled_steady
    def f():
        a = undefined_one
        b = undefined_two
        c = undefined_three
        d = undefined_four
        return 42

    with pytest.raises(NameError):
        f()


# ---------------------------------------------------------------------- #
# Context manager — advanced
# ---------------------------------------------------------------------- #
def test_context_manager_nested(enabled_steady):
    """Nested ``with steady:`` blocks should each suppress their exceptions."""

    with enabled_steady:
        with enabled_steady:
            raise ValueError("inner")
        raise ValueError("outer")


def test_context_manager_with_exception_in_function(enabled_steady):
    """An exception raised inside a function called within the block is suppressed."""

    def buggy():
        bad = 1 / 0
        return 42

    with enabled_steady:
        buggy()

    # If we reach here the exception was suppressed.
    assert True


# ---------------------------------------------------------------------- #
# Report — multiple calls / empty
# ---------------------------------------------------------------------- #
def test_report_after_multiple_calls(enabled_steady):
    """After several buggy calls, the report should contain every recorded bug."""

    @enabled_steady
    def f1():
        bad = 1 / 0
        return 1

    @enabled_steady
    def f2():
        bad = undefined_var
        return 2

    f1()
    f2()

    assert enabled_steady.bug_count >= 2
    report = enabled_steady.report(format="dict")
    assert report["bug_count"] >= 2
    assert len(report["entries"]) >= 2


def test_steady_disabled_then_works(enabled_steady):
    """When disabled, steady should run normal functions without any repair logic."""

    enabled_steady.configure(enabled=False)

    @enabled_steady
    def normal():
        return 123

    assert normal() == 123


def test_zero_bugs_report(enabled_steady):
    """A report with zero bugs should be valid in every supported format."""

    assert enabled_steady.bug_count == 0

    md = enabled_steady.report(format="markdown")
    assert isinstance(md, str)
    assert "No bugs" in md or "uneventful" in md

    js = enabled_steady.report(format="json")
    import json

    data = json.loads(js)
    assert data["bug_count"] == 0

    d = enabled_steady.report(format="dict")
    assert d["bug_count"] == 0
    assert d["entries"] == []


# ---------------------------------------------------------------------- #
# max_retries exhausted
# ---------------------------------------------------------------------- #
def test_max_retries_exceeded(enabled_steady):
    """When repair attempts exceed ``max_retries``, the original exception
    should be re-raised and the report should record an unresolved entry.

    With ``max_retries=1`` and two sequential bugs, steady can only remove
    the first offending line before running out of retries; the second
    ``NameError`` propagates as the original exception.
    """
    enabled_steady.configure(max_retries=1)
    try:

        @enabled_steady
        def f():
            a = undefined_one  # removed on retry 1
            b = undefined_two  # still fails -> re-raise
            return 42

        with pytest.raises(NameError):
            f()

        report = enabled_steady.report(format="dict")
        assert report["unresolved"] >= 1
    finally:
        # Restore the default so subsequent tests are unaffected.
        enabled_steady.configure(max_retries=3)


# ---------------------------------------------------------------------- #
# Generator function
# ---------------------------------------------------------------------- #
def test_decorator_with_generator(enabled_steady):
    """A decorated generator function should return a usable generator
    object that iterates normally when there is no bug in the body."""

    @enabled_steady
    def squares(n):
        for i in range(n):
            yield i * i

    gen = squares(3)
    assert hasattr(gen, "__next__")
    assert list(gen) == [0, 1, 4]
    assert enabled_steady.bug_count == 0


def test_decorator_with_generator_bug_during_iteration(enabled_steady):
    """Bugs that fire lazily during iteration are outside the wrapper's
    try/except, so steady cannot intercept them; they propagate normally."""

    @enabled_steady
    def gen():
        yield 1
        bad = 1 / 0  # fires on the second next() call
        yield 2

    g = gen()
    assert next(g) == 1
    with pytest.raises(ZeroDivisionError):
        next(g)
    # steady never saw the error — it occurred during iteration.
    assert enabled_steady.bug_count == 0


# ---------------------------------------------------------------------- #
# Class & static methods
# ---------------------------------------------------------------------- #
def test_decorator_class_method(enabled_steady):
    """A decorated instance method should be repaired when its body raises."""

    class Calculator:
        @enabled_steady
        def divide(self, a, b):
            debug = 1 / 0  # stray debug line
            return a / b

    calc = Calculator()
    assert calc.divide(10, 2) == 5
    assert enabled_steady.bug_count >= 1


def test_decorator_static_method(enabled_steady):
    """A decorated static method should be repaired when its body raises."""

    class Utility:
        @staticmethod
        @enabled_steady
        def parse(text):
            debug = undefined_var  # stray debug line
            return int(text)

    assert Utility.parse("42") == 42
    assert enabled_steady.bug_count >= 1


# ---------------------------------------------------------------------- #
# Concurrency / thread safety
# ---------------------------------------------------------------------- #
def test_concurrent_calls(enabled_steady):
    """Concurrent calls to a decorated function should be thread-safe:
    every call returns the correct result and the shared bug report is
    not corrupted."""

    import threading

    @enabled_steady
    def compute(x):
        debug = 1 / 0  # removed on repair
        return x * 2

    results: list = []
    errors: list = []

    def worker():
        try:
            results.append(compute(21))
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert len(results) == 8
    assert all(r == 42 for r in results)
    assert enabled_steady.bug_count >= 8


# ---------------------------------------------------------------------- #
# Nested decorated functions
# ---------------------------------------------------------------------- #
def test_nested_decorated_functions(enabled_steady):
    """A decorated function defined inside another decorated function
    should be repaired independently; both bugs are recorded.

    The inner decorator uses the module-level ``steady`` singleton rather
    than the ``enabled_steady`` fixture: when steady recompiles the outer
    function's source, the inner ``@`` decorator is preserved in the
    recompiled code and resolved against the module globals (where
    ``enabled_steady`` is a pytest fixture and thus not directly callable,
    but ``steady`` is a real :class:`Steady` instance).
    """

    @enabled_steady
    def outer():
        @steady
        def inner():
            debug = 1 / 0  # ZeroDivisionError
            return "inner"

        noise = undefined_var  # NameError
        return inner()

    assert outer() == "inner"
    assert enabled_steady.bug_count >= 2

    report = enabled_steady.report(format="dict")
    types = {e["error_type"] for e in report["entries"]}
    assert "ZeroDivisionError" in types
    assert "NameError" in types
