from __future__ import annotations

from pathlib import Path

from code_intake.checkers.static_python import StaticPythonChecker

FIXTURES = Path(__file__).parent / "fixtures"


def test_valid_python_passes():
    result = StaticPythonChecker().run(FIXTURES / "valid_package")
    assert result.passed, f"unexpected findings: {result.findings}"
    assert result.checker == "static_python"


def test_broken_python_returns_ruff_finding():
    result = StaticPythonChecker().run(FIXTURES / "broken_python")
    assert not result.passed
    codes = {f.code for f in result.findings}
    assert "PY001" in codes  # ruff


def test_no_python_dir_returns_passed_with_zero_findings():
    """Packages without a python/ dir are valid (pure-SAS packages, future
    use case). The checker is a no-op rather than an error."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        result = StaticPythonChecker().run(Path(td))
        assert result.passed
        assert result.findings == []


def test_empty_python_dir_returns_passed_with_zero_findings():
    """Packages with an empty python/ dir are valid (developer in-progress,
    moved-away files). Without this guard, mypy emits 'no .py files in
    directory' and the operator sees a confusing PY002."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "python").mkdir()
        result = StaticPythonChecker().run(Path(td))
        assert result.passed, f"unexpected findings: {result.findings}"
        assert result.findings == []
