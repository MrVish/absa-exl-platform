"""Synthetic broken fixture — has unused imports that ruff F401 will flag.

Also references ``data["tenure_months"]`` so the orchestrator's
two-failures test can use this script alongside ``broken_pir/pir.yaml``
(which omits ``tenure_months``) to assert that static_python AND pir
findings BOTH surface.
"""

from __future__ import annotations

import os
import sys


def score(data: dict[str, float]) -> dict[str, float]:
    return {"pd_score": data["tenure_months"] * 0.5}
