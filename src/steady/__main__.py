"""Command-line entry point for steady.

Usage
-----
Print the version::

    python -m steady version

Print the most recent Bug Tour Report::

    python -m steady report

The CLI is intentionally minimal. Programmatic usage (``import steady``,
``@steady``, ``with steady:``) is the primary interface; the CLI only exposes
inspection utilities.
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

__all__ = ["main"]


def _get_version() -> str:
    """Return the installed steady version.

    Importing ``steady._version`` directly avoids importing the full
    ``steady`` package (and its optional heavy dependencies) just to print
    a version string.
    """
    try:
        from ._version import __version__  # type: ignore[attr-defined]
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
        import steady  # type: ignore[import-not-found]
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


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser for the ``steady`` CLI."""
    parser = argparse.ArgumentParser(
        prog="steady",
        description=(
            "steady - AI-native fault-tolerant Python runtime. "
            "稳住，代码能跑。"
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
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
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

    # Should be unreachable thanks to argparse choices.
    parser.error(f"Unknown command: {command!r}")  # pragma: no cover
    return 2  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main())
