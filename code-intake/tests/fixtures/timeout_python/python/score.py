"""Fixture that hangs forever — used to trigger subprocess timeout in tests."""

from __future__ import annotations

import time


def score(data: dict) -> float:
    time.sleep(99999)  # noqa: hang forever
    return 0.0
