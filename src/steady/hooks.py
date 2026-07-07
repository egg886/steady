"""Import hooks for steady.

Enables the ``steady("module_name")`` syntax: wraps module imports so that
syntax errors and import errors are caught and handled.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys
import types
from collections.abc import Sequence
from typing import Any


class SteadyLoader(importlib.abc.Loader):
    """Loader that wraps module execution with steady error handling.

    Delegates module creation to the original loader, but wraps execution
    so that ``SyntaxError`` and ``ImportError`` can be caught and retried.
    """

    def __init__(
        self,
        steady_instance: Any,
        original_loader: importlib.abc.Loader,
        spec: importlib.machinery.ModuleSpec,
    ) -> None:
        self._steady = steady_instance
        self._original_loader = original_loader
        self._spec = spec

    def create_module(
        self, spec: importlib.machinery.ModuleSpec
    ) -> types.ModuleType | None:
        """Delegate module creation to the original loader."""
        if hasattr(self._original_loader, "create_module"):
            return self._original_loader.create_module(spec)
        return None  # Use default module creation

    def exec_module(self, module: types.ModuleType) -> None:
        """Execute the module with error handling.

        On ``SyntaxError``, attempts to read and fix the source file, then
        re-executes.  On ``ImportError``, the import is allowed to propagate
        after recording the error.
        """
        try:
            if hasattr(self._original_loader, "exec_module"):
                self._original_loader.exec_module(module)
        except SyntaxError as e:
            # Try to fix the syntax error
            if self._steady._config.enabled:
                self._steady._handle_module_syntax_error(module, e)
            else:
                raise


class SteadyMetaFinder(importlib.abc.MetaPathFinder):
    """Meta path finder for the ``steady("module_name")`` syntax.

    Intercepts imports of a specific module name and wraps the loader with
    :class:`SteadyLoader`.
    """

    def __init__(self, steady_instance: Any, module_name: str) -> None:
        self._steady = steady_instance
        self._module_name = module_name

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target: types.ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        """Find the module spec and wrap its loader."""
        if fullname != self._module_name:
            return None

        # Temporarily remove ourselves to avoid infinite recursion
        sys.meta_path.remove(self)
        try:
            spec = importlib.util.find_spec(fullname)
        except (ModuleNotFoundError, ValueError):
            return None
        finally:
            sys.meta_path.insert(0, self)

        if spec is None:
            return None

        # Wrap the original loader
        if spec.loader is not None:
            spec.loader = SteadyLoader(
                self._steady, spec.loader, spec
            )

        return spec


_registered_hooks: dict[str, SteadyMetaFinder] = {}


def install_import_hook(steady_instance: Any, module_name: str) -> None:
    """Install an import hook for the given module name.

    After installation, ``importlib.import_module(module_name)`` will be
    wrapped with steady error handling.

    Args:
        steady_instance: The :class:`Steady` instance to use for error handling.
        module_name: The fully-qualified module name to intercept.
    """
    if module_name in _registered_hooks:
        return  # Already installed

    finder = SteadyMetaFinder(steady_instance, module_name)
    _registered_hooks[module_name] = finder
    sys.meta_path.insert(0, finder)


def uninstall_import_hook(module_name: str) -> None:
    """Remove the import hook for the given module name.

    Args:
        module_name: The module name whose hook should be removed.
    """
    finder = _registered_hooks.pop(module_name, None)
    if finder is not None and finder in sys.meta_path:
        sys.meta_path.remove(finder)
