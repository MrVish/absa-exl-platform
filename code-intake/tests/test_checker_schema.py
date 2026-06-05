from __future__ import annotations

from pathlib import Path

from code_intake.checkers.schema import SchemaChecker

FIXTURES = Path(__file__).parent / "fixtures"


def test_valid_schema_passes():
    result = SchemaChecker().run(FIXTURES / "valid_package")
    assert result.passed, f"unexpected findings: {result.findings}"
    assert result.checker == "schema"


def test_missing_required_field_returns_sch001():
    result = SchemaChecker().run(FIXTURES / "broken_schema")
    assert not result.passed
    codes = {f.code for f in result.findings}
    assert "SCH001" in codes


def test_missing_model_config_returns_sch001():
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        result = SchemaChecker().run(Path(td))
        assert not result.passed
        codes = {f.code for f in result.findings}
        assert "SCH001" in codes
