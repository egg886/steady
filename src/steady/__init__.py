"""steady - AI-native fault-tolerant Python runtime.

steady is the spiritual successor to `fuckit.py <https://github.com/ajalt/fuckitpy>`_.
It wraps your code in a forgiving runtime that swallows errors, repairs
broken functions on the fly, and keeps your program moving.

Two-tier repair strategy:

1. **AST repair** (no API key needed) - remove the offending line from the
   AST, recompile, and re-execute.  This is the *fuckit.py* approach.
2. **LLM repair** (optional, needs API key) - send source + error +
   traceback to an AI model, get a minimal patch, apply it, and re-execute.

Usage
-----
The primary, ergonomic entry point is the module-level :data:`steady`
instance, usable as a decorator, context manager, or import hook::

    import steady

    @steady.steady
    def risky(x):
        return x / 0

    with steady.steady:
        data = 1 / 0

    steady.steady("broken_module")

The same instance is also importable directly for brevity::

    from steady import steady

    @steady
    def risky(x):
        return x / 0

Both forms reference the *same* singleton :class:`Steady` instance, so the
Bug Tour Report and configuration are shared across the whole process.
"""

from __future__ import annotations

from ._version import __version__
from .config import Config, get_config
from .core import Steady
from .llm import LLMClient, LLMRepairResult
from .report import BugEntry, BugReport

#: Process-wide singleton :class:`Steady` instance.
#:
#: Use it as ``@steady`` (decorator), ``with steady:`` (context manager),
#: or ``steady("module")`` (import hook). Both ``import steady; steady.steady``
#: and ``from steady import steady`` expose this same object.
steady: Steady = Steady()

__all__ = [
    "BugEntry",
    "BugReport",
    "Config",
    "LLMClient",
    "LLMRepairResult",
    "Steady",
    "__version__",
    "get_config",
    "steady",
]
