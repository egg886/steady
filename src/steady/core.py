"""Core module for steady — the AI-native fault-tolerant runtime.

This module contains the :class:`Steady` class, which can be used as:

* A **decorator** — ``@steady`` wraps a function so runtime errors are
  caught and repaired automatically.
* A **context manager** — ``with steady:`` suppresses errors inside the
  block and attempts AST-level repair.
* An **import hook** — ``steady("module_name")`` installs a meta-path
  finder that wraps the module's loader.

The repair strategy follows a two-tier priority:

1. **AST repair** (no API key needed) — remove the offending line from the
   AST, recompile, and re-execute.  This is the *fuckit.py* approach.
2. **LLM repair** (needs API key) — send source + error + traceback to an
   AI model, get a fix, apply it, recompile, and re-execute.

If both tiers fail the original exception is re-raised.
"""

from __future__ import annotations

import functools
import sys
import traceback as tb_module
from typing import Any, Callable, Optional, Tuple, Union

from .ast_fixer import (
    ErrorInfo,
    analyze_traceback,
    get_function_source,
    recompile_function,
    try_ast_repair,
)
from .config import Config, get_config
from .hooks import install_import_hook
from .llm import LLMRepairResult, create_llm_client
from .report import BugEntry, BugReport


class Steady:
    """Main steady class.

    Used as a decorator, context manager, or import hook to provide
    AI-native fault tolerance.

    Example::

        import steady

        @steady
        def risky(x):
            return x / 0  # steady will handle this

        with steady:
            data = 1 / 0  # caught and suppressed

        steady("broken_module")  # import with error handling
    """

    def __init__(self) -> None:
        """Initialise steady with default config, an empty bug report, and
        an LLM client.
        """
        self._config: Config = get_config()
        self._report: BugReport = BugReport()
        self._llm = create_llm_client(self._config)
        self._prev_excepthook = sys.excepthook

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def configure(self, **kwargs: Any) -> None:
        """Configure the AI backend.

        Forwards all keyword arguments to :meth:`Config.configure`, then
        re-creates the LLM client so the new settings take effect.

        Example::

            steady.configure(api_key="sk-...", model="gpt-4o")
        """
        self._config.configure(**kwargs)
        self._llm = create_llm_client(self._config)

    # ------------------------------------------------------------------
    # __call__ — decorator / import hook
    # ------------------------------------------------------------------
    def __call__(
        self, func: Optional[Union[str, Callable]] = None
    ) -> Any:
        """Use steady as a decorator or import hook.

        * ``@steady`` or ``@steady()`` — decorate a function.
        * ``steady("module_name")`` — install an import hook and import the
          module with error handling.

        Args:
            func: A callable to decorate, a module name string, or
                ``None`` (returns ``self`` for ``@steady()`` syntax).

        Returns:
            The decorated wrapper, the imported module, or ``self``.
        """
        if func is None:
            # @steady() syntax — return self for later decoration
            return self

        if isinstance(func, str):
            # steady("module_name") — import hook
            install_import_hook(self, func)
            import importlib

            return importlib.import_module(func)

        if callable(func):
            return self._decorate(func)

        raise TypeError(
            f"steady() expected callable or str, got {type(func).__name__}"
        )

    # ------------------------------------------------------------------
    # Context manager protocol
    # ------------------------------------------------------------------
    def __enter__(self) -> "Steady":
        """Enter the ``with steady:`` context.

        Saves the current ``sys.excepthook`` and replaces it with a no-op
        so that unhandled exceptions inside the block don't print a
        traceback to stderr.
        """
        self._prev_excepthook = sys.excepthook
        sys.excepthook = lambda *args: None  # Suppress default handler
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit the ``with steady:`` context.

        Restores the original ``sys.excepthook``.  If an exception
        occurred inside the block, attempts to handle it.  Returns
        ``True`` (suppress) if the exception was handled, ``False``
        (re-raise) otherwise.

        Args:
            exc_type: The exception class, or ``None``.
            exc_val: The exception instance, or ``None``.
            exc_tb: The traceback object, or ``None``.

        Returns:
            ``True`` to suppress the exception, ``False`` to propagate it.
        """
        sys.excepthook = self._prev_excepthook
        if exc_type is not None:
            handled = self._handle_block_exception(exc_type, exc_val, exc_tb)
            return handled
        return False

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------
    def report(self, format: str = "markdown") -> Any:
        """Export the Bug Tour Report.

        Args:
            format: Output format — ``"markdown"``, ``"json"``, or
                ``"dict"``.

        Returns:
            The report as a string (markdown/json) or dict.
        """
        return self._report.export(format)

    @property
    def bug_count(self) -> int:
        """Return the total number of bugs recorded in the report."""
        return self._report.bug_count

    # ------------------------------------------------------------------
    # Internal: decoration
    # ------------------------------------------------------------------
    def _decorate(self, func: Callable) -> Callable:
        """Wrap a function with steady error handling.

        The wrapper tries to call the original function.  On exception,
        if steady is enabled, it delegates to
        :meth:`_handle_function_error` which attempts AST / LLM repair.

        Args:
            func: The function to wrap.

        Returns:
            The wrapped function.
        """

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if not self._config.enabled:
                    raise
                return self._handle_function_error(func, e, args, kwargs)

        wrapper._steady_wrapped = True  # type: ignore[attr-defined]
        return wrapper

    # ------------------------------------------------------------------
    # Internal: core error handler for decorated functions
    # ------------------------------------------------------------------
    def _handle_function_error(
        self,
        func: Callable,
        exc: Exception,
        args: tuple,
        kwargs: dict,
    ) -> Any:
        """Core repair logic for decorated functions.

        Implements the two-tier priority strategy:

        1. **AST repair** — remove the error-causing line, recompile, and
           re-execute.  No API key needed.
        2. **LLM repair** — if AST repair fails and an API key is
           configured, ask the LLM for a fix, apply it, recompile, and
           re-execute.
        3. **Fallback** — if both tiers fail, re-raise the original
           exception.

        Each repair attempt that produces a fix is tried by recompiling
        and re-executing.  If the re-execution itself fails, the new error
        is analysed and the loop continues (up to ``max_retries``).

        Args:
            func: The original (un-wrapped) function.
            exc: The exception that was raised.
            args: Positional arguments passed to the function.
            kwargs: Keyword arguments passed to the function.

        Returns:
            The result of the repaired function call.

        Raises:
            Exception: The original exception if all repair attempts fail.
        """
        max_retries: int = self._config.max_retries
        retry_count: int = 0

        # --- Step 1: Get the original function source ---
        current_source: Optional[str] = get_function_source(func)
        if current_source is None:
            raise exc

        # --- Step 2: Analyse the traceback ---
        current_exc: Exception = exc
        current_error_info: Optional[ErrorInfo] = analyze_traceback(
            type(exc), exc, exc.__traceback__
        )

        # Build a human-readable location string for the report
        original_location = self._build_location_string(
            current_error_info, exc
        )

        # ------------------------------------------------------------------
        # Repair loop
        # ------------------------------------------------------------------
        while retry_count < max_retries:
            retry_count += 1

            # --- Tier 1: AST repair (no API key needed) ---
            fixed_source, ast_strategy = self._attempt_ast_repair(
                current_source, current_error_info, current_exc
            )

            if fixed_source is not None:
                # We have a fix — try recompiling and re-executing
                success, result, new_exc = self._try_recompile_and_execute(
                    fixed_source, func, args, kwargs
                )

                if success:
                    # The fix worked!
                    self._report.add_entry(
                        BugEntry(
                            error_type=type(current_exc).__name__,
                            location=original_location,
                            explanation=str(current_exc),
                            fix_strategy="ast_repair",
                            fix_description=ast_strategy,
                            retry_count=retry_count,
                            resolved=True,
                        )
                    )
                    return result

                # The fix compiled and ran but raised a *new* error.
                # Record the intermediate fix, then loop to fix the new error.
                self._report.add_entry(
                    BugEntry(
                        error_type=type(current_exc).__name__,
                        location=original_location,
                        explanation=str(current_exc),
                        fix_strategy="ast_repair",
                        fix_description=ast_strategy,
                        retry_count=retry_count,
                        resolved=True,
                    )
                )
                current_exc = new_exc  # type: ignore[assignment]
                current_source = fixed_source
                current_error_info = self._refresh_error_info(
                    new_exc, current_source, func.__name__
                )
                continue

            # --- Tier 2: LLM repair (needs API key) ---
            if self._config.api_key or self._config.llm_client is not None:
                llm_result = self._attempt_llm_repair(
                    current_source,
                    current_error_info,
                    current_exc,
                    func,
                    args,
                    kwargs,
                )

                if (
                    llm_result is not None
                    and llm_result.success
                    and llm_result.fixed_code
                ):
                    success, result, new_exc = self._try_recompile_and_execute(
                        llm_result.fixed_code, func, args, kwargs
                    )

                    if success:
                        self._report.add_entry(
                            BugEntry(
                                error_type=type(current_exc).__name__,
                                location=original_location,
                                explanation=llm_result.explanation,
                                fix_strategy="llm_repair",
                                fix_description=(
                                    f"LLM strategy: {llm_result.strategy}"
                                ),
                                retry_count=retry_count,
                                resolved=True,
                            )
                        )
                        self._report.add_tokens(llm_result.tokens_used)
                        return result

                    # LLM fix compiled but raised a new error.
                    # Record the intermediate fix, then loop to fix the new error.
                    self._report.add_entry(
                        BugEntry(
                            error_type=type(current_exc).__name__,
                            location=original_location,
                            explanation=llm_result.explanation,
                            fix_strategy="llm_repair",
                            fix_description=(
                                f"LLM strategy: {llm_result.strategy}"
                            ),
                            retry_count=retry_count,
                            resolved=True,
                        )
                    )
                    current_exc = new_exc  # type: ignore[assignment]
                    current_source = llm_result.fixed_code
                    current_error_info = self._refresh_error_info(
                        new_exc, current_source, func.__name__
                    )
                    self._report.add_tokens(llm_result.tokens_used)
                    continue

            # Neither AST nor LLM could produce a fix for this error.
            break

        # ------------------------------------------------------------------
        # All repair attempts failed — record and re-raise
        # ------------------------------------------------------------------
        self._report.add_entry(
            BugEntry(
                error_type=type(exc).__name__,
                location=original_location,
                explanation=str(exc),
                fix_strategy="failed",
                fix_description=(
                    f"All {retry_count} repair attempt(s) failed"
                ),
                retry_count=retry_count,
                resolved=False,
            )
        )
        raise exc

    # ------------------------------------------------------------------
    # Internal: block exception handler (context manager)
    # ------------------------------------------------------------------
    def _handle_block_exception(
        self, exc_type, exc_val, exc_tb
    ) -> bool:
        """Handle exceptions from ``with steady:`` blocks.

        Simplified version: analyses the traceback, attempts AST repair
        on the enclosing function/module source.  Returns ``True``
        (suppress) if the repair succeeds, ``False`` (re-raise) otherwise.

        Args:
            exc_type: The exception class.
            exc_val: The exception instance.
            exc_tb: The traceback object.

        Returns:
            ``True`` if the exception was handled, ``False`` to re-raise.
        """
        if not self._config.enabled:
            return False

        error_info = analyze_traceback(exc_type, exc_val, exc_tb)

        location = self._build_location_string(error_info, exc_val)

        if error_info is not None and error_info.source:
            fixed_source, strategy = try_ast_repair(
                error_info.source, error_info
            )
            if fixed_source is not None:
                self._report.add_entry(
                    BugEntry(
                        error_type=error_info.error_type,
                        location=location,
                        explanation=str(exc_val),
                        fix_strategy="ast_repair",
                        fix_description=strategy,
                        retry_count=1,
                        resolved=True,
                    )
                )
                return True

        # Could not repair — record and let the exception propagate
        self._report.add_entry(
            BugEntry(
                error_type=(
                    error_info.error_type
                    if error_info
                    else exc_type.__name__ if exc_type else "Unknown"
                ),
                location=location,
                explanation=str(exc_val),
                fix_strategy="failed",
                fix_description="Block exception could not be auto-repaired",
                retry_count=1,
                resolved=False,
            )
        )
        return False

    # ------------------------------------------------------------------
    # Internal: module syntax error handler (called by hooks)
    # ------------------------------------------------------------------
    def _handle_module_syntax_error(self, module, exc: SyntaxError) -> None:
        """Record a syntax error encountered during module import.

        Args:
            module: The module being imported.
            exc: The :class:`SyntaxError` that was raised.
        """
        filename = getattr(exc, "filename", None) or "<unknown>"
        lineno = getattr(exc, "lineno", 0) or 0
        self._report.add_entry(
            BugEntry(
                error_type="SyntaxError",
                location=f"{filename}:{lineno}",
                explanation=getattr(exc, "msg", str(exc)),
                fix_strategy="failed",
                fix_description=(
                    "Syntax error in module import (could not auto-repair)"
                ),
                retry_count=1,
                resolved=False,
            )
        )

    # ==================================================================
    # Private helpers
    # ==================================================================

    @staticmethod
    def _get_tb_lineno(tb) -> int:
        """Walk to the innermost frame and return its line number.

        Args:
            tb: A traceback object (possibly ``None``).

        Returns:
            The innermost line number, or ``0`` if ``tb`` is ``None``.
        """
        if tb is None:
            return 0
        while tb.tb_next is not None:
            tb = tb.tb_next
        return tb.tb_lineno

    @staticmethod
    def _build_location_string(
        error_info: Optional[ErrorInfo], exc: Any
    ) -> str:
        """Build a human-readable location string for a BugEntry.

        Args:
            error_info: Analysed error info (may be ``None``).
            exc: The exception (used as fallback for traceback info).

        Returns:
            A string like ``"file.py:42 in function_name"``.
        """
        if error_info is not None:
            # Use the original traceback's absolute lineno for the report
            tb = getattr(exc, "__traceback__", None)
            abs_lineno = Steady._get_tb_lineno(tb)
            if abs_lineno == 0:
                abs_lineno = error_info.lineno
            return (
                f"{error_info.filename}:{abs_lineno} "
                f"in {error_info.function_name}"
            )
        return "unknown"

    @staticmethod
    def _attempt_ast_repair(
        source: Optional[str],
        error_info: Optional[ErrorInfo],
        exc: Exception,
    ) -> Tuple[Optional[str], str]:
        """Attempt AST repair on the current source.

        A thin wrapper around :func:`try_ast_repair` that handles ``None``
        inputs gracefully.

        Args:
            source: Current source code.
            error_info: Current error info.
            exc: The current exception.

        Returns:
            ``(fixed_source, strategy)`` or ``(None, '')``.
        """
        if not source or error_info is None:
            return None, ""
        return try_ast_repair(source, error_info)

    def _attempt_llm_repair(
        self,
        source: Optional[str],
        error_info: Optional[ErrorInfo],
        exc: Exception,
        func: Callable,
        args: tuple,
        kwargs: dict,
    ) -> Optional[LLMRepairResult]:
        """Attempt LLM repair on the current source.

        Args:
            source: Current source code.
            error_info: Current error info.
            exc: The current exception.
            func: The original function.
            args: Positional arguments.
            kwargs: Keyword arguments.

        Returns:
            An :class:`LLMRepairResult` or ``None``.
        """
        if not source:
            return None

        error_type = (
            error_info.error_type
            if error_info
            else type(exc).__name__
        )
        error_msg = str(exc)
        tb_str = "".join(
            tb_module.format_exception(type(exc), exc, exc.__traceback__)
        )

        return self._llm.repair(
            source=source,
            error_type=error_type,
            error_msg=error_msg,
            traceback_str=tb_str,
            context={
                "function": func.__name__,
                "args": repr(args),
                "kwargs": repr(kwargs),
            },
        )

    @staticmethod
    def _try_recompile_and_execute(
        source: str,
        func: Callable,
        args: tuple,
        kwargs: dict,
    ) -> Tuple[bool, Any, Optional[Exception]]:
        """Recompile *source* and try executing it.

        Args:
            source: The repaired source code.
            func: The original function (for name and globals).
            args: Positional arguments.
            kwargs: Keyword arguments.

        Returns:
            A tuple ``(success, result, new_exception)``.  If *success*
            is ``True``, *result* holds the return value.  If ``False``,
            *new_exception* holds the exception that was raised.
        """
        try:
            new_func = recompile_function(
                source, func.__name__, func.__globals__
            )
            result = new_func(*args, **kwargs)
            return True, result, None
        except Exception as new_exc:
            return False, None, new_exc

    @staticmethod
    def _refresh_error_info(
        exc: Exception,
        current_source: str,
        func_name: str,
    ) -> Optional[ErrorInfo]:
        """Create or refresh :class:`ErrorInfo` after a failed repair.

        When the repaired source is recompiled and re-executed, the new
        exception's traceback points to ``<steady>`` (the virtual filename
        used by :func:`recompile_function`).  :func:`analyze_traceback`
        cannot read that "file", so it returns an :class:`ErrorInfo` with
        an empty ``source`` but a valid ``lineno`` (relative to the
        compiled source).

        This helper fills in the ``source`` and ``source_lines`` fields
        so that the next AST-repair attempt can work correctly.

        Args:
            exc: The new exception from the re-execution.
            current_source: The source that was compiled.
            func_name: The function name for the report.

        Returns:
            A refreshed :class:`ErrorInfo`, or ``None`` if the exception
            has no traceback.
        """
        error_info = analyze_traceback(
            type(exc), exc, exc.__traceback__
        )

        if error_info is not None:
            # Fill in the source so try_ast_repair can use it
            error_info.source = current_source
            error_info.source_lines = current_source.splitlines()
            return error_info

        # analyse_traceback returned None — build a synthetic ErrorInfo
        tb = exc.__traceback__
        lineno = 1
        filename = "<steady>"
        if tb is not None:
            while tb.tb_next is not None:
                tb = tb.tb_next
            lineno = tb.tb_lineno
            filename = tb.tb_frame.f_code.co_filename

        return ErrorInfo(
            filename=filename,
            lineno=lineno,
            function_name=func_name,
            error_type=type(exc).__name__,
            error_msg=str(exc),
            source=current_source,
            source_lines=current_source.splitlines(),
        )
