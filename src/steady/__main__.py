"""Command-line entry point for steady.

Usage
-----
Print the version::

    python -m steady version

Print the most recent Bug Tour Report::

    python -m steady report

Print the current configuration (API key masked)::

    python -m steady config

Run a quick self-test that demonstrates AST repair in action::

    python -m steady test

The CLI is intentionally minimal. Programmatic usage (``import steady``,
``@steady``, ``with steady:``) is the primary interface; the CLI only exposes
inspection utilities and a smoke test.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

__all__ = ["main"]


def _get_version() -> str:
    """Return the installed steady version.

    Importing ``steady._version`` directly avoids importing the full
    ``steady`` package (and its optional heavy dependencies) just to print
    a version string.

    Returns:
        The version string, or ``"0.0.0+unknown"`` if it cannot be read.
    """
    try:
        from ._version import __version__
        return __version__
    except Exception:  # pragma: no cover - defensive
        return "0.0.0+unknown"


def _print_report() -> int:
    """Print the most recent Bug Tour Report.

    Returns a process exit code. ``0`` on success, ``1`` if the steady
    runtime (which depends on core/ast_fixer/report/hooks modules) cannot be
    imported - for example because optional modules are not yet installed.
    """
    try:
        import steady
    except Exception as exc:  # pragma: no cover - depends on install state
        print(
            "steady: unable to import the steady runtime.\n"
            f"  reason: {exc}\n"
            "  Make sure all steady modules are installed "
            "(pip install -e .).",
            file=sys.stderr,
        )
        return 1

    instance = getattr(steady, "steady", None)
    if instance is None:  # pragma: no cover - defensive
        print("steady: no global 'steady' instance available.", file=sys.stderr)
        return 1

    report = instance.report()
    if not report:
        print("No bugs recorded yet. The tour hasn't started - keep coding!")
        return 0

    print(report)
    return 0


def _mask_api_key(key: str | None) -> str:
    """Mask an API key for safe display.

    Shows the first 3 and last 4 characters, masking the middle. Short or
    unset keys are reported as ``<not set>``.

    Args:
        key: The API key to mask, or ``None``.

    Returns:
        A masked representation safe to print.
    """
    if not key:
        return "<not set>"
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:3]}...{key[-4:]}"


def _print_config() -> int:
    """Print the current steady configuration with the API key masked.

    Returns:
        Process exit code (``0`` on success, ``1`` if the runtime cannot be
        imported).
    """
    try:
        import steady
    except Exception as exc:  # pragma: no cover - depends on install state
        print(
            "steady: unable to import the steady runtime.\n"
            f"  reason: {exc}\n"
            "  Make sure all steady modules are installed "
            "(pip install -e .).",
            file=sys.stderr,
        )
        return 1

    instance = getattr(steady, "steady", None)
    if instance is None:  # pragma: no cover - defensive
        print("steady: no global 'steady' instance available.", file=sys.stderr)
        return 1

    config = instance._config
    has_custom_llm = config.llm_client is not None

    print("steady configuration")
    print("-" * 40)
    print(f"  enabled      : {config.enabled}")
    print(f"  provider     : {config.provider}")
    print(f"  model        : {config.model}")
    print(f"  api_key      : {_mask_api_key(config.api_key)}")
    print(f"  max_retries  : {config.max_retries}")
    print(f"  custom llm   : {'yes (callable)' if has_custom_llm else 'no'}")
    print(f"  bug_count    : {instance.bug_count}")
    print("-" * 40)
    print(
        "Tip: set STEADY_API_KEY / STEADY_PROVIDER / STEADY_MODEL env vars,"
        "\n     or call steady.configure(api_key=..., model=...)."
    )
    return 0


def _run_selftest() -> int:
    """Run a quick self-test demonstrating AST repair.

    Defines a deliberately buggy function decorated with ``@steady``, calls
    it, and verifies that steady silently repaired the bug. Prints the
    result and the resulting Bug Tour Report so the user can see the runtime
    working end-to-end without an API key.

    Returns:
        ``0`` if the self-test passes, ``1`` otherwise.
    """
    try:
        import steady
    except Exception as exc:  # pragma: no cover - depends on install state
        print(
            "steady: unable to import the steady runtime.\n"
            f"  reason: {exc}\n"
            "  Make sure all steady modules are installed "
            "(pip install -e .).",
            file=sys.stderr,
        )
        return 1

    instance = getattr(steady, "steady", None)
    if instance is None:  # pragma: no cover - defensive
        print("steady: no global 'steady' instance available.", file=sys.stderr)
        return 1

    # Use a fresh isolated Steady instance so we never pollute the global
    # report the user may already be building.
    test_steady = steady.Steady()

    print("steady self-test")
    print("=" * 50)
    print("Defining a buggy function decorated with @steady...\n")

    @test_steady
    def buggy_function() -> int:
        """A deliberately broken function.

        The first line raises ZeroDivisionError; steady removes it and the
        function returns 42.
        """
        bad = 1 / 0  # noqa: F841
        return 42

    print("Calling buggy_function()...")
    try:
        result = buggy_function()
    except Exception as exc:  # pragma: no cover - defensive
        print(f"\nFAIL: steady did not handle the error: {exc!r}")
        return 1

    if result != 42:
        print(f"\nFAIL: expected 42, got {result!r}")
        return 1

    print(f"  -> returned {result!r} (expected 42)")
    print(f"  -> bug_count: {test_steady.bug_count} (expected >= 1)")

    if test_steady.bug_count < 1:
        print("\nFAIL: steady did not record the bug in the report.")
        return 1

    print("\nPASS: steady repaired the bug and kept the program running.")
    print("\n--- Bug Tour Report ---")
    print(test_steady.report())
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser for the ``steady`` CLI.

    Returns:
        A configured :class:`argparse.ArgumentParser`.
    """
    parser = argparse.ArgumentParser(
        prog="steady",
        description=(
            "steady - AI-native fault-tolerant Python runtime. "
            "稳住，代码能跑。"  # noqa: RUF001
        ),
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    sub.add_parser(
        "version",
        help="Print the installed steady version and exit.",
    )
    sub.add_parser(
        "report",
        help="Print the most recent Bug Tour Report.",
    )
    sub.add_parser(
        "config",
        help="Print the current steady configuration (API key masked).",
    )
    sub.add_parser(
        "test",
        help="Run a quick self-test demonstrating AST repair.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the ``steady`` console script and ``python -m steady``.

    Parameters
    ----------
    argv:
        Optional argument list (defaults to ``sys.argv[1:]``).

    Returns
    -------
    int
        Process exit code.
    """
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    command = args.command

    if command is None:
        # No subcommand: print help and version banner.
        parser.print_help()
        return 0

    if command == "version":
        print(f"steady {_get_version()}")
        return 0

    if command == "report":
        return _print_report()

    if command == "config":
        return _print_config()

    if command == "test":
        return _run_selftest()

    # Should be unreachable thanks to argparse choices.
    parser.error(f"Unknown command: {command!r}")  # pragma: no cover
    return 2  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main())
