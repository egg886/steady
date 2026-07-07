"""Tests for the steady core module.

These tests do NOT require an API key — they only exercise the AST repair
path, which is the fuckit.py-style "remove the error line and rerun" approach.
"""

from __future__ import annotations

import pytest

from steady import steady
from steady.core import Steady


# ---------------------------------------------------------------------- #
# Fixtures
# ---------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _isolate_state():
    """Clear the global steady report before and after each test."""
    steady._report.clear()
    yield
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
