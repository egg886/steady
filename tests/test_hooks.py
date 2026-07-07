"""Tests for the import hook module (``steady.hooks``).

These tests exercise the ``steady("module_name")`` syntax and the underlying
``install_import_hook`` / ``uninstall_import_hook`` helpers, including the
``SteadyMetaFinder`` and ``SteadyLoader`` classes.

Import-hook tests are inherently global-state heavy (they mutate
``sys.meta_path`` and the module-level ``_registered_hooks`` dict), so an
autouse fixture snapshots and restores that state around every test.
"""

from __future__ import annotations

import importlib
import sys

import pytest

from steady import Steady, steady
from steady.hooks import (
    SteadyLoader,
    SteadyMetaFinder,
    _registered_hooks,
    install_import_hook,
    uninstall_import_hook,
)


# ---------------------------------------------------------------------- #
# Fixtures
# ---------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _restore_hook_state():
    """Snapshot and restore ``sys.meta_path`` and ``_registered_hooks``.

    Import hooks mutate two pieces of global state:

    * ``sys.meta_path`` — the list of meta path finders consulted by the
      import system.
    * ``steady.hooks._registered_hooks`` — the dict mapping module names to
      their installed :class:`SteadyMetaFinder`.

    Without restoring these, a single failing test could leak finders into
    ``sys.meta_path`` and break every subsequent import in the test session.
    """
    saved_meta_path = list(sys.meta_path)
    saved_hooks = dict(_registered_hooks)
    saved_excepthook = sys.excepthook
    yield
    sys.meta_path[:] = saved_meta_path
    _registered_hooks.clear()
    _registered_hooks.update(saved_hooks)
    sys.excepthook = saved_excepthook


@pytest.fixture
def tmp_module_dir(tmp_path, monkeypatch):
    """Create a temporary directory and prepend it to ``sys.path``.

    Test modules written here become importable, and are automatically
    removed from ``sys.path`` (and ``sys.modules``) when the test ends.
    """
    monkeypatch.syspath_prepend(str(tmp_path))
    yield tmp_path


def _purge_modules(*names: str) -> None:
    """Remove the given top-level modules (and their submodules) from
    ``sys.modules`` so that a fresh import re-runs the loader.
    """
    for name in names:
        for mod in list(sys.modules):
            if mod == name or mod.startswith(name + "."):
                del sys.modules[mod]


# ---------------------------------------------------------------------- #
# install / uninstall
# ---------------------------------------------------------------------- #
def test_install_and_uninstall_hook():
    """install_import_hook should register a finder and insert it into
    ``sys.meta_path``; uninstall should remove both."""
    s = Steady()
    module_name = "steady_hook_install_target"

    assert module_name not in _registered_hooks

    install_import_hook(s, module_name)

    # The hook is tracked in the registry ...
    assert module_name in _registered_hooks
    finder = _registered_hooks[module_name]
    assert isinstance(finder, SteadyMetaFinder)
    assert finder._module_name == module_name
    assert finder._steady is s

    # ... and present at the front of sys.meta_path.
    assert finder in sys.meta_path

    uninstall_import_hook(module_name)

    assert module_name not in _registered_hooks
    assert finder not in sys.meta_path


def test_uninstall_nonexistent():
    """Uninstalling a hook that was never installed should be a silent no-op."""
    # No exception should be raised.
    uninstall_import_hook("definitely_not_a_registered_module_12345")

    # The registry is unchanged.
    assert "definitely_not_a_registered_module_12345" not in _registered_hooks


def test_registered_hooks_tracking():
    """``_registered_hooks`` should track every installed hook and de-dupe
    repeated installations of the same module name."""
    s = Steady()

    # Initially neither module is registered.
    assert "steady_hook_track_a" not in _registered_hooks
    assert "steady_hook_track_b" not in _registered_hooks

    install_import_hook(s, "steady_hook_track_a")
    assert "steady_hook_track_a" in _registered_hooks
    finder_a = _registered_hooks["steady_hook_track_a"]

    # Re-installing the same module is a no-op: the original finder is kept
    # and no duplicate entry is inserted into sys.meta_path.
    install_import_hook(s, "steady_hook_track_a")
    assert _registered_hooks["steady_hook_track_a"] is finder_a
    assert sys.meta_path.count(finder_a) == 1

    # A second, distinct module gets its own finder.
    install_import_hook(s, "steady_hook_track_b")
    assert "steady_hook_track_b" in _registered_hooks
    finder_b = _registered_hooks["steady_hook_track_b"]
    assert finder_b is not finder_a

    # Removing one does not affect the other.
    uninstall_import_hook("steady_hook_track_a")
    assert "steady_hook_track_a" not in _registered_hooks
    assert "steady_hook_track_b" in _registered_hooks
    assert finder_b in sys.meta_path


# ---------------------------------------------------------------------- #
# Hook behaviour with real modules
# ---------------------------------------------------------------------- #
def test_hook_with_valid_module(tmp_module_dir):
    """Importing a syntactically-valid module through an installed hook
    should load it normally, with its loader wrapped in
    :class:`SteadyLoader`."""
    mod_path = tmp_module_dir / "steady_hook_valid_mod.py"
    mod_path.write_text(
        "VALUE = 42\n"
        "\n"
        "def get_value():\n"
        "    return VALUE\n"
    )
    try:
        s = Steady()
        install_import_hook(s, "steady_hook_valid_mod")

        mod = importlib.import_module("steady_hook_valid_mod")

        # The module body executed correctly.
        assert mod.VALUE == 42
        assert mod.get_value() == 42

        # The hook wrapped the original loader.
        assert isinstance(mod.__spec__.loader, SteadyLoader)

        # No errors were recorded for a clean module.
        assert s.bug_count == 0
    finally:
        _purge_modules("steady_hook_valid_mod")


def test_hook_not_affecting_other_modules(tmp_module_dir):
    """A hook installed for module A must not wrap the loader of an
    unrelated module B imported during the same session."""
    (tmp_module_dir / "steady_hook_target_mod.py").write_text("X = 1\n")
    (tmp_module_dir / "steady_hook_other_mod.py").write_text("Y = 2\n")
    try:
        s = Steady()
        install_import_hook(s, "steady_hook_target_mod")

        other = importlib.import_module("steady_hook_other_mod")
        target = importlib.import_module("steady_hook_target_mod")

        # The targeted module is wrapped ...
        assert isinstance(target.__spec__.loader, SteadyLoader)

        # ... but the unrelated module is *not*.
        assert not isinstance(other.__spec__.loader, SteadyLoader)
        assert other.Y == 2
        assert target.X == 1
    finally:
        _purge_modules("steady_hook_target_mod", "steady_hook_other_mod")


def test_hook_with_syntax_error_records_bug(tmp_module_dir):
    """A module containing a ``SyntaxError`` should still be importable
    when steady is enabled: the error is swallowed and recorded as an
    unresolved entry in the bug report."""
    steady._report.clear()
    steady.configure(enabled=True)
    mod_path = tmp_module_dir / "steady_hook_syntax_mod.py"
    # Intentionally invalid syntax (unclosed parenthesis in def).
    mod_path.write_text("def broken(:\n    pass\n")
    try:
        # steady("name") installs the hook *and* imports the module.
        mod = steady("steady_hook_syntax_mod")

        # The module object exists even though its body could not execute.
        assert mod is not None

        # The syntax error was recorded.
        assert steady.bug_count >= 1
        report = steady.report(format="dict")
        assert any(
            e["error_type"] == "SyntaxError" for e in report["entries"]
        )
        assert report["unresolved"] >= 1
    finally:
        _purge_modules("steady_hook_syntax_mod")
        steady._report.clear()


def test_hook_disabled_re_raises_syntax_error(tmp_module_dir):
    """When steady is disabled, a ``SyntaxError`` during import must
    propagate instead of being swallowed."""
    steady._report.clear()
    steady.configure(enabled=False)
    mod_path = tmp_module_dir / "steady_hook_disabled_syntax_mod.py"
    mod_path.write_text("def broken(:\n    pass\n")
    try:
        with pytest.raises(SyntaxError):
            steady("steady_hook_disabled_syntax_mod")
        # Nothing was recorded because steady was disabled.
        assert steady.bug_count == 0
    finally:
        _purge_modules("steady_hook_disabled_syntax_mod")
        steady.configure(enabled=True)
        steady._report.clear()
