"""sys.path bump so `from score import score` resolves inside subprocess pytest."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
