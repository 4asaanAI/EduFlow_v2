import sys
import os

# Ensure backend/ is on sys.path so all backend modules are importable
_backend = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from server import app  # noqa: E402
