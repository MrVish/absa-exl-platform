from __future__ import annotations

import tempfile
from pathlib import Path

from code_intake.checkers.static_sas import StaticSasChecker

FIXTURES = Path(__file__).parent / "fixtures"


def test_valid_sas_passes():
    result = StaticSasChecker().run(FIXTURES / "valid_package")
    assert result.passed, f"unexpected findings: {result.findings}"
    assert result.checker == "static_sas"


def test_broken_sas_unbalanced_proc_run():
    result = StaticSasChecker().run(FIXTURES / "broken_sas")
    assert not result.passed
    codes = {f.code for f in result.findings}
    assert "SAS003" in codes  # PROC without matching RUN


def test_empty_sas_file_returns_sas002():
    with tempfile.TemporaryDirectory() as td:
        sas_dir = Path(td) / "sas"
        sas_dir.mkdir()
        (sas_dir / "empty.sas").write_text("")
        result = StaticSasChecker().run(Path(td))
        assert not result.passed
        codes = {f.code for f in result.findings}
        assert "SAS002" in codes


def test_no_sas_dir_returns_passed():
    """Packages without a sas/ dir are valid (pure-Python packages)."""
    with tempfile.TemporaryDirectory() as td:
        result = StaticSasChecker().run(Path(td))
        assert result.passed
        assert result.findings == []
