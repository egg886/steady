"""AST-based error removal module for steady.

This is the core of the fuckit.py-style error handling: when a line causes
an error, we remove that line from the AST and recompile. No AI needed.

Key design:
    - ``analyze_traceback`` returns ``ErrorInfo`` with ``lineno`` relative to
      the function source (1-based, line 1 = the ``def`` line).
    - ``get_function_source`` returns the function source starting from
      ``def`` (decorators stripped, dedented) so linenos match.
    - ``try_ast_repair`` uses ``error_info.lineno`` to find and remove the
      offending statement via AST manipulation.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
import types
from dataclasses import dataclass, field
from typing import Any, Callable, cast


@dataclass
class ErrorInfo:
    """Structured information extracted from a traceback.

    ``lineno`` is relative to ``source`` (1-based).  When ``source`` is the
    function body starting from the ``def`` line, ``lineno == 1`` means the
    ``def`` line itself.
    """

    filename: str
    lineno: int
    function_name: str
    error_type: str  # e.g. "ZeroDivisionError"
    error_msg: str  # e.g. "division by zero"
    source: str  # Full source of the function/module
    source_lines: list[str] = field(default_factory=list)
    end_lineno: int | None = None


def analyze_traceback(
    exc_type: type[BaseException] | None,
    exc_value: BaseException | None,
    exc_tb: types.TracebackType | None,
) -> ErrorInfo | None:
    """Extract structured error info from a traceback object.

    Walks to the innermost frame, reads the source file, and identifies the
    enclosing function.  The returned ``lineno`` is **relative to the
    function source** (1-based, starting from the ``def`` line) so that it
    can be used directly with :func:`try_ast_repair`.

    Args:
        exc_type: The exception class.
        exc_value: The exception instance.
        exc_tb: The traceback object.

    Returns:
        An :class:`ErrorInfo` instance, or ``None`` if ``exc_tb`` is ``None``.
    """
    if exc_tb is None:
        return None

    # Walk to the innermost frame
    tb = exc_tb
    while tb.tb_next is not None:
        tb = tb.tb_next

    frame = tb.tb_frame
    abs_lineno = tb.tb_lineno
    filename = frame.f_code.co_filename
    function_name = frame.f_code.co_name

    error_type = exc_type.__name__ if exc_type is not None else "Unknown"
    error_msg = str(exc_value) if exc_value is not None else ""

    # Try to read the source file
    try:
        with open(filename, encoding="utf-8") as f:
            file_source = f.read()
    except (OSError, UnicodeDecodeError):
        # Can't read the file (e.g. <string>, <steady>, or <stdin>)
        return ErrorInfo(
            filename=filename,
            lineno=abs_lineno,
            function_name=function_name,
            error_type=error_type,
            error_msg=error_msg,
            source="",
            source_lines=[],
        )

    file_lines = file_source.splitlines(keepends=False)

    # Parse the file to find the enclosing function
    try:
        tree = ast.parse(file_source, filename=filename)
    except SyntaxError:
        # Can't parse the file — return with absolute lineno and full source
        return ErrorInfo(
            filename=filename,
            lineno=abs_lineno,
            function_name=function_name,
            error_type=error_type,
            error_msg=error_msg,
            source=file_source,
            source_lines=file_lines,
        )

    # Collect all candidate functions that contain the error line
    candidates: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = node.lineno
            if start is None:
                continue
            end = (
                node.end_lineno
                if node.end_lineno is not None
                else start
            )
            if start <= abs_lineno <= end:
                candidates.append(node)

    if candidates:
        # Pick the innermost function (largest start lineno)
        func_node = max(candidates, key=lambda n: n.lineno)
        start_line = func_node.lineno
        end_line = (
            func_node.end_lineno
            if func_node.end_lineno is not None
            else start_line
        )
        func_lines = file_lines[start_line - 1 : end_line]
        func_source = textwrap.dedent("\n".join(func_lines))
        relative_lineno = abs_lineno - start_line + 1

        return ErrorInfo(
            filename=filename,
            lineno=relative_lineno,
            function_name=func_node.name,
            error_type=error_type,
            error_msg=error_msg,
            source=func_source,
            source_lines=func_source.splitlines(keepends=False),
            end_lineno=func_node.end_lineno,
        )

    # Module-level code — use absolute lineno
    return ErrorInfo(
        filename=filename,
        lineno=abs_lineno,
        function_name=function_name,
        error_type=error_type,
        error_msg=error_msg,
        source=file_source,
        source_lines=file_lines,
    )


def get_function_source(func: Callable[..., Any]) -> str | None:
    """Get the source code of a function via :mod:`inspect`.

    Returns the function source starting from the ``def`` line (decorators
    are stripped) and dedented so that linenos are 1-based relative to
    ``def``.  This keeps linenos consistent with :func:`analyze_traceback`.

    Args:
        func: The function to inspect.

    Returns:
        The dedented source string, or ``None`` if it cannot be retrieved.
    """
    try:
        source = inspect.getsource(func)
    except (OSError, TypeError):
        return None

    source = textwrap.dedent(source)

    # Strip decorators so the source starts from 'def'
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    if tree.body and isinstance(
        tree.body[0], (ast.FunctionDef, ast.AsyncFunctionDef)
    ):
        func_node = tree.body[0]
        if func_node.decorator_list:
            lines = source.splitlines(keepends=True)
            # func_node.lineno is 1-based, pointing to the 'def' line
            start_idx = func_node.lineno - 1
            source = "".join(lines[start_idx:])
            source = textwrap.dedent(source)

    return source


class _StatementRemover(ast.NodeTransformer):
    """AST transformer that removes the statement at a specific line number.

    If removing a statement would leave a body empty, a ``pass`` statement
    is inserted to keep the code valid.
    """

    _BODY_FIELDS = frozenset({"body", "orelse", "finalbody"})

    # Compound statement types — their *body* is visited, but the statement
    # itself is never removed even when the error line falls inside its span.
    _COMPOUND_TYPES = (
        ast.If,
        ast.For,
        ast.While,
        ast.With,
        ast.AsyncFor,
        ast.AsyncWith,
        ast.Try,
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.ClassDef,
    )

    def __init__(self, target_lineno: int) -> None:
        self.target_lineno = target_lineno
        self.removed = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _should_remove(self, node: ast.AST) -> bool:
        """Return ``True`` if *node* should be removed."""
        if not hasattr(node, "lineno"):
            return False

        # Exact line match — always remove (even compound statements that
        # *start* on the error line).
        if node.lineno == self.target_lineno:
            return True

        # Range match for multi-line simple statements.
        end = getattr(node, "end_lineno", None)
        if end is not None and node.lineno <= self.target_lineno <= end:
            # Only remove simple statements; compound statements are
            # visited so their inner bodies can be checked.
            if not isinstance(node, self._COMPOUND_TYPES):
                return True

        return False

    def _process_list(self, items: list[ast.stmt]) -> list[ast.stmt]:
        """Process a list of AST nodes, removing the target if found."""
        new_list: list[ast.stmt] = []
        for item in items:
            if isinstance(item, ast.stmt) and not self.removed:
                if self._should_remove(item):
                    self.removed = True
                    continue  # drop this statement
            new_list.append(self.visit(item))
        return new_list

    # ------------------------------------------------------------------
    # NodeTransformer override
    # ------------------------------------------------------------------
    def generic_visit(self, node: ast.AST) -> ast.AST:
        for attr_name, old_value in ast.iter_fields(node):
            if isinstance(old_value, list):
                new_list = self._process_list(old_value)
                # Insert 'pass' if a body-like field becomes empty.
                if attr_name in self._BODY_FIELDS and not new_list:
                    new_list = [ast.Pass()]
                setattr(node, attr_name, new_list)
            elif isinstance(old_value, ast.AST):
                setattr(node, attr_name, self.visit(old_value))
        return node


def remove_error_line(source: str, lineno: int) -> str | None:
    """Remove the statement at the given line number using AST manipulation.

    Parses *source* into an AST, finds the statement at *lineno*, removes it,
    and unparses back to source.  If removing a statement would leave a body
    empty, a ``pass`` is inserted.

    Args:
        source: Python source code (typically a single function).
        lineno: 1-based line number within *source*.

    Returns:
        The fixed source string, or ``None`` if the line cannot be safely
        removed.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    remover = _StatementRemover(lineno)
    new_tree = remover.visit(tree)

    if not remover.removed:
        return None

    # Ensure the module body is not empty
    if not new_tree.body:
        new_tree.body = [ast.Pass()]

    try:
        return ast.unparse(new_tree)
    except Exception:
        return None


def recompile_function(
    source: str,
    func_name: str,
    globals_dict: dict[str, Any] | None = None,
) -> Callable[..., Any]:
    """Recompile a function from source code and return the new callable.

    Uses :func:`compile` + :func:`exec` to create a fresh function object.
    The new function shares ``globals_dict`` so it can access the same module
    -level names as the original.

    Args:
        source: Python source defining the function.
        func_name: Name of the function to extract after compilation.
        globals_dict: The globals dict to use (typically
            ``func.__globals__``).  If ``None``, an empty dict is used.

    Returns:
        The recompiled callable.

    Raises:
        NameError: If *func_name* is not found after compilation.
    """
    if globals_dict is None:
        globals_dict = {}

    code = compile(source, "<steady>", "exec")
    exec(code, globals_dict)

    if func_name in globals_dict:
        result = globals_dict[func_name]
        if callable(result):
            return cast(Callable[..., Any], result)
        raise NameError(
            f"'{func_name}' is not callable after recompilation"
        )

    raise NameError(
        f"Function '{func_name}' not found after recompilation"
    )


def try_ast_repair(
    source: str, error_info: ErrorInfo | None
) -> tuple[str | None, str]:
    """Try to fix the source using AST manipulation.

    Attempts to remove the error-causing statement identified by
    ``error_info.lineno``.  This is the fuckit.py approach — no AI needed.

    Args:
        source: The source code to repair (typically from
            :func:`get_function_source`).
        error_info: Structured error information with ``lineno``.

    Returns:
        A tuple ``(fixed_source, strategy_description)``.  If the repair
        fails, returns ``(None, '')``.
    """
    if not source or error_info is None:
        return None, ""

    lineno = error_info.lineno
    fixed_source = remove_error_line(source, lineno)

    if fixed_source is not None:
        strategy = (
            f"Removed error-causing statement at line {lineno} "
            f"({error_info.error_type}: {error_info.error_msg})"
        )
        return fixed_source, strategy

    return None, ""
