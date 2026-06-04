"""Synthetic — references tenure_months but PIR omits it."""

from __future__ import annotations


def score(data: dict[str, float]) -> dict[str, float]:
    income_band = data["income_band"]
    tenure_months = data["tenure_months"]  # this is missing from PIR
    return {"pd_score": income_band + tenure_months / 12}
