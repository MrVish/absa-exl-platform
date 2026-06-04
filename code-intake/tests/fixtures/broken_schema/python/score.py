"""Minimal Python so the package directory exists; the broken_schema
fixture exercises the SchemaChecker via model_config.yaml only."""

from __future__ import annotations


def score(data: dict[str, float]) -> dict[str, float]:
    return {"pd_score": 0.0}
