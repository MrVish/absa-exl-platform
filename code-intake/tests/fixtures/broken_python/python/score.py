"""Synthetic broken fixture — has unused imports that ruff F401 will flag."""

from __future__ import annotations

import os
import sys


def score(data: dict[str, float]) -> dict[str, float]:
    return {"pd_score": 0.5}
