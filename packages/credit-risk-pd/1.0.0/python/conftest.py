"""sys.path bump so `from score import score` resolves under subprocess pytest.

Mirrors the convention real packages will follow before they're installed as wheels.
The static_python and tests checkers run pytest from inside python/ with
--confcutdir=. so this conftest is found and applied to their subprocess.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
