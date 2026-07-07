"""steady — AI-native fault-tolerant runtime. 稳住，代码能跑."""

from .core import Steady
from .config import get_config
from ._version import __version__

steady = Steady()

__all__ = ["steady", "Steady", "get_config", "__version__"]
