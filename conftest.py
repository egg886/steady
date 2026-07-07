"""Pytest configuration — adds src/ to sys.path so `import steady` works."""
import os
import sys

# Insert src/ at the front of sys.path so tests can import steady
# without installing the package.
_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
