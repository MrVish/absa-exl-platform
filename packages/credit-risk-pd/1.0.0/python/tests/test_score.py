from __future__ import annotations

from score import score


def test_score_high() -> None:
    out = score({"income_band": 2.0, "tenure_months": 24, "delinquencies": 1.0})
    assert isinstance(out["pd_score"], float)
    assert out["pd_score"] > 0.7
    assert out["risk_band"] == "HIGH"


def test_score_medium() -> None:
    out = score({"income_band": 0.5, "tenure_months": 12, "delinquencies": 0.5})
    pd_score = out["pd_score"]
    assert isinstance(pd_score, float)
    assert 0.4 < pd_score <= 0.7
    assert out["risk_band"] == "MEDIUM"


def test_score_low() -> None:
    out = score({"income_band": 0.1, "tenure_months": 6, "delinquencies": 0.0})
    assert isinstance(out["pd_score"], float)
    assert out["pd_score"] < 0.4
    assert out["risk_band"] == "LOW"
