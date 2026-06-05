"""Credit-risk PD scoring stub — synthetic Phase-2 worked example."""

from __future__ import annotations


def score(data: dict[str, float]) -> dict[str, float | str]:
    """Score one customer record.

    Mirrors the SAS score logic (sas/score.sas). Real Phase-3 scoring
    code goes here.
    """
    income_band = data["income_band"]
    tenure_months = data["tenure_months"]
    delinquencies = data["delinquencies"]

    pd_score = 0.5 * income_band + 0.3 * tenure_months / 12 + 0.2 * delinquencies

    if pd_score > 0.7:
        risk_band = "HIGH"
    elif pd_score > 0.4:
        risk_band = "MEDIUM"
    else:
        risk_band = "LOW"

    return {"pd_score": pd_score, "risk_band": risk_band}
