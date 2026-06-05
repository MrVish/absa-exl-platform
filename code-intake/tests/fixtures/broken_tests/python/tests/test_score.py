from score import score


def test_score_passes() -> None:
    assert score({"x": 1}) == {"pd_score": 0.5}


def test_score_intentionally_fails() -> None:
    # This assertion is wrong on purpose — exercises TST002.
    assert score({"x": 1}) == {"pd_score": 999.9}
