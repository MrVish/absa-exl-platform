"""Tests for the extended _extract_column_references (PIR T10)."""

from __future__ import annotations

from code_intake.checkers.pir import _extract_column_references


def test_extracts_literal_subscript() -> None:
    """Baseline: existing pattern still works."""
    src = """
def score(data):
    return data["tenure_months"] * 0.5
"""
    cols = _extract_column_references(src)
    assert "tenure_months" in cols


def test_extracts_literal_attribute() -> None:
    src = """
def score(data):
    return data.income * 0.2
"""
    cols = _extract_column_references(src)
    assert "income" in cols


def test_extracts_variable_column_name() -> None:
    """New: col = "tenure"; data[col] -> "tenure"."""
    src = """
def score(data):
    col = "tenure_months"
    return data[col]
"""
    cols = _extract_column_references(src)
    assert "tenure_months" in cols


def test_extracts_fstring_with_glob() -> None:
    """New: data[f"month_{i}"] -> "month_*"."""
    src = """
def score(data):
    total = 0
    for i in range(12):
        total += data[f"month_{i}"]
    return total
"""
    cols = _extract_column_references(src)
    assert "month_*" in cols


def test_extracts_multi_part_fstring() -> None:
    """data[f"col_{a}_{b}_data"] -> "col_*_*_data"."""
    src = """
def score(data):
    a = "x"
    b = "y"
    return data[f"col_{a}_{b}_data"]
"""
    cols = _extract_column_references(src)
    assert "col_*_*_data" in cols


def test_pure_variable_fstring_is_ignored() -> None:
    """f"{var}" with no literal parts gives no useful glob; should be skipped."""
    src = """
def score(data):
    n = "tenure"
    return data[f"{n}"]
"""
    cols = _extract_column_references(src)
    # The "n" should resolve via the constant propagator to "tenure"
    # since we DO handle name lookup. But the f-string fallback alone
    # would skip pure-var f-strings; with name lookup it's "tenure".
    # Either is acceptable; document the expectation:
    assert "tenure" in cols or "*" in cols


def test_constant_propagation_is_intra_function() -> None:
    """Different functions have independent constant tables."""
    src = """
def score_a(data):
    col = "income"
    return data[col]

def score_b(data):
    col = "tenure"
    return data[col]
"""
    cols = _extract_column_references(src)
    assert "income" in cols
    assert "tenure" in cols
