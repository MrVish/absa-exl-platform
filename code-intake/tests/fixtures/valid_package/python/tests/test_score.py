from __future__ import annotations

from score import score


def test_score_returns_dict() -> None:
    out = score({"income_band": 1.0, "tenure_months": 12, "delinquencies": 0.0})
    assert "pd_score" in out
    assert "risk_band" in out
