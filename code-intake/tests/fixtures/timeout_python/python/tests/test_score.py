"""Test module that hangs on import — exercises static_python timeout path."""

from __future__ import annotations

import time

# Hang at module import time so pytest --collect-only never completes
time.sleep(99999)


def test_placeholder() -> None:
    pass
