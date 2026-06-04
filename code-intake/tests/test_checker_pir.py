from __future__ import annotations

from pathlib import Path

from code_intake.checkers.pir import PirChecker, _extract_column_references

FIXTURES = Path(__file__).parent / "fixtures"


def test_valid_pir_passes():
    result = PirChecker().run(FIXTURES / "valid_package")
    assert result.passed, f"unexpected findings: {result.findings}"
    assert result.checker == "pir"


def test_broken_pir_unmapped_column_returns_pir002():
    result = PirChecker().run(FIXTURES / "broken_pir")
    assert not result.passed
    codes = {f.code for f in result.findings}
    assert "PIR002" in codes


def test_extract_columns_subscript():
    cols = _extract_column_references('def f(data):\n    return data["a"] + data["b"]\n')
    assert cols == {"a", "b"}


def test_extract_columns_attribute():
    cols = _extract_column_references("def f(data):\n    return data.x + data.y\n")
    assert cols == {"x", "y"}


def test_extract_columns_mixed():
    cols = _extract_column_references('def f(data):\n    return data["a"] + data.b\n')
    assert cols == {"a", "b"}


def test_extract_columns_ignores_non_data_subscripts():
    """data["x"] is extracted; other["x"] is not."""
    cols = _extract_column_references('def f(data, other):\n    return data["a"] + other["b"]\n')
    assert cols == {"a"}
