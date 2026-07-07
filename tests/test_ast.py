"""Tests for the AST repair module."""

from __future__ import annotations

import pytest

from steady.ast_fixer import (
    ErrorInfo,
    analyze_traceback,
    get_function_source,
    recompile_function,
    remove_error_line,
    try_ast_repair,
)


# ---------------------------------------------------------------------- #
# remove_error_line
# ---------------------------------------------------------------------- #
def test_remove_simple_statement():
    """Removing a simple statement should leave the rest intact."""
    source = "def f():\n    x = 1 / 0\n    return 42\n"
    result = remove_error_line(source, 2)
    assert result is not None
    assert "1 / 0" not in result
    assert "return 42" in result


def test_remove_leaves_pass_for_empty_body():
    """Removing the only statement in a body should insert pass."""
    source = "def f():\n    x = 1 / 0\n"
    result = remove_error_line(source, 2)
    assert result is not None
    assert "pass" in result


def test_remove_from_if_body():
    """Removing a statement inside an if block should work."""
    source = "def f():\n    if True:\n        x = 1 / 0\n    return 42\n"
    result = remove_error_line(source, 3)
    assert result is not None
    assert "1 / 0" not in result
    assert "return 42" in result


def test_remove_from_for_body():
    """Removing a statement inside a for loop should work."""
    source = "def f():\n    for i in range(3):\n        bad = 1 / 0\n    return 42\n"
    result = remove_error_line(source, 3)
    assert result is not None
    assert "1 / 0" not in result
    assert "return 42" in result


def test_remove_nonexistent_line():
    """Removing a line that doesn't exist should return None."""
    source = "def f():\n    return 42\n"
    result = remove_error_line(source, 99)
    assert result is None


def test_remove_invalid_syntax():
    """Invalid Python source should return None."""
    result = remove_error_line("def f(:\n    pass\n", 1)
    assert result is None


# ---------------------------------------------------------------------- #
# analyze_traceback
# ---------------------------------------------------------------------- #
def test_analyze_traceback_basic():
    """analyze_traceback should extract error info from a real exception."""

    def sample():
        x = 1 / 0

    try:
        sample()
    except ZeroDivisionError as e:
        info = analyze_traceback(type(e), e, e.__traceback__)

    assert info is not None
    assert info.error_type == "ZeroDivisionError"
    assert info.lineno > 0
    assert "division by zero" in info.error_msg
    assert info.function_name == "sample"


def test_analyze_traceback_none():
    """analyze_traceback with None tb should return None."""
    info = analyze_traceback(ValueError, ValueError("x"), None)
    assert info is None


def test_analyze_traceback_preserves_source():
    """analyze_traceback should include source code lines."""

    def sample():
        total = sum([1, 2, 3])
        bad = total / 0
        return total

    try:
        sample()
    except ZeroDivisionError as e:
        info = analyze_traceback(type(e), e, e.__traceback__)

    assert info is not None
    assert len(info.source_lines) > 0
    assert "def sample" in info.source


# ---------------------------------------------------------------------- #
# recompile_function
# ---------------------------------------------------------------------- #
def test_recompile_basic():
    """Recompiled function should be callable and return correct result."""
    source = "def f():\n    return 42\n"
    func = recompile_function(source, "f")
    assert func() == 42


def test_recompile_with_args():
    """Recompiled function should accept arguments."""
    source = "def f(a, b):\n    return a + b\n"
    func = recompile_function(source, "f")
    assert func(2, 3) == 5


def test_recompile_with_globals():
    """Recompiled function should access provided globals."""
    source = "def f():\n    return VALUE\n"
    func = recompile_function(source, "f", {"VALUE": 99})
    assert func() == 99


def test_recompile_missing_function():
    """Should raise NameError if the function name is not in the source."""
    with pytest.raises(NameError):
        recompile_function("x = 1\n", "nonexistent")


# ---------------------------------------------------------------------- #
# get_function_source
# ---------------------------------------------------------------------- #
def test_get_function_source_basic():
    """get_function_source should return the function's source."""

    def sample():
        return 42

    source = get_function_source(sample)
    assert source is not None
    assert "def sample" in source
    assert "return 42" in source


def test_get_function_source_strips_decorator():
    """get_function_source should strip decorators."""

    def decorator(func):
        return func

    @decorator
    def sample():
        return 42

    source = get_function_source(sample)
    assert source is not None
    # Source should start from 'def', not from the decorator
    assert source.lstrip().startswith("def")


# ---------------------------------------------------------------------- #
# try_ast_repair
# ---------------------------------------------------------------------- #
def test_try_ast_repair_success():
    """try_ast_repair should remove the error line and return a strategy."""
    source = "def f():\n    bad = 1 / 0\n    return 42\n"
    error_info = ErrorInfo(
        filename="test.py",
        lineno=2,
        function_name="f",
        error_type="ZeroDivisionError",
        error_msg="division by zero",
        source=source,
        source_lines=source.splitlines(),
    )
    fixed, strategy = try_ast_repair(source, error_info)
    assert fixed is not None
    assert "1 / 0" not in fixed
    assert "return 42" in fixed
    assert "Removed" in strategy


def test_try_ast_repair_empty_source():
    """try_ast_repair with empty source should return (None, '')."""
    error_info = ErrorInfo(
        filename="test.py",
        lineno=1,
        function_name="f",
        error_type="Error",
        error_msg="msg",
        source="",
        source_lines=[],
    )
    fixed, strategy = try_ast_repair("", error_info)
    assert fixed is None
    assert strategy == ""


def test_try_ast_repair_none_error_info():
    """try_ast_repair with None error_info should return (None, '')."""
    fixed, strategy = try_ast_repair("x = 1\n", None)
    assert fixed is None
    assert strategy == ""


# ---------------------------------------------------------------------- #
# remove_error_line — more complex scenarios
# ---------------------------------------------------------------------- #
def test_remove_from_try_except():
    """Removing an error line inside a try block should work."""
    source = "def f():\n    try:\n        x = 1 / 0\n    except:\n        pass\n    return 42\n"
    result = remove_error_line(source, 3)
    assert result is not None
    assert "1 / 0" not in result
    assert "return 42" in result


def test_remove_from_nested_if():
    """Removing a statement inside a nested if block should work."""
    source = "def f():\n    if True:\n        if True:\n            x = 1 / 0\n    return 42\n"
    result = remove_error_line(source, 4)
    assert result is not None
    assert "1 / 0" not in result
    assert "return 42" in result


def test_remove_multiline_statement():
    """Removing a multi-line statement should remove all of its lines."""
    source = (
        "def f():\n"
        "    x = {\n"
        "        'a': 1,\n"
        "        'b': 2,\n"
        "    }\n"
        "    return 42\n"
    )
    # The dict assignment spans lines 2-5; target a line in the middle.
    result = remove_error_line(source, 3)
    assert result is not None
    assert "return 42" in result
    # The whole multi-line assignment should be gone.
    assert "'b': 2" not in result
    assert "'a': 1" not in result


def test_remove_first_line():
    """Removing the first line of a function body should work."""
    source = "def f():\n    bad = 1 / 0\n    good = 2\n    return 42\n"
    result = remove_error_line(source, 2)
    assert result is not None
    assert "1 / 0" not in result
    assert "good = 2" in result
    assert "return 42" in result


def test_remove_last_line():
    """Removing the last line (a return statement) should work."""
    source = "def f():\n    x = 1\n    return 42\n"
    result = remove_error_line(source, 3)
    assert result is not None
    assert "return 42" not in result
    assert "x = 1" in result


# ---------------------------------------------------------------------- #
# recompile_function — closures & defaults
# ---------------------------------------------------------------------- #
_CLOSURE_VALUE = 777


def test_recompile_preserves_closure():
    """A recompiled function should access names from the provided globals,
    simulating closure / module-level variable access."""
    import sys

    module_globals = sys.modules[__name__].__dict__
    source = "def f():\n    return _CLOSURE_VALUE\n"
    func = recompile_function(source, "f", module_globals)
    assert func() == 777


def test_recompile_with_default_args():
    """A recompiled function should preserve default argument values."""
    source = "def f(a, b=10):\n    return a + b\n"
    func = recompile_function(source, "f")
    assert func(5) == 15
    assert func(5, 20) == 25


# ---------------------------------------------------------------------- #
# try_ast_repair — real traceback integration
# ---------------------------------------------------------------------- #
def test_try_ast_repair_with_real_traceback():
    """try_ast_repair should fix a function using error info from a real traceback."""

    def sample():
        bad = 1 / 0
        return 42

    try:
        sample()
    except ZeroDivisionError as e:
        info = analyze_traceback(type(e), e, e.__traceback__)

    assert info is not None
    fixed, strategy = try_ast_repair(info.source, info)
    assert fixed is not None
    assert "1 / 0" not in fixed
    assert "return 42" in fixed
    assert "Removed" in strategy

    # The fixed source should recompile and run correctly.
    func = recompile_function(fixed, "sample")
    assert func() == 42
