"""Make ``scripts/demo`` importable as ``demo`` for the test suite.

``scripts/demo`` is intentionally NOT a uv workspace member (see spec §10.4),
so we patch ``sys.path`` at test-collection time. ``Path(__file__).parent``
points at ``scripts/demo/tests``; three ``.parent`` hops reach ``scripts/``,
which makes ``from demo.transcript import Transcript`` resolve to
``scripts/demo/transcript.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).parent.parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
