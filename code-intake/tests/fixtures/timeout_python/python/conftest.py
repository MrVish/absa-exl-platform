# Required to keep static_python's pytest --collect-only from short-circuiting.
# Also adds python/ to sys.path so the in-subprocess pytest can resolve
# `from score import score` if collection ever reaches that import — but
# tests/test_score.py hangs at module import via a top-level time.sleep()
# so collection never actually completes (that's the point of this fixture).

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
