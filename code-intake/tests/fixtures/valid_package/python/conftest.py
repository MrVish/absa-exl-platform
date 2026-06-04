"""Adds the package's python/ directory to sys.path so tests under
python/tests/ can `from score import score` without packaging.

This mirrors the convention real packages will follow before they're
installed as wheels — during static checks the code is still on disk.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
