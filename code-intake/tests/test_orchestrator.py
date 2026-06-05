from __future__ import annotations

from pathlib import Path

from code_intake.checkers.base import CheckResult
from code_intake.orchestrator import validate

FIXTURES = Path(__file__).parent / "fixtures"


def test_valid_package_all_checkers_pass():
    results = validate(FIXTURES / "valid_package")
    assert len(results) == 5
    assert {r.checker for r in results} == {"static_python", "static_sas", "schema", "tests", "pir"}
    assert all(r.passed for r in results), [
        (r.checker, r.findings) for r in results if not r.passed
    ]


def test_broken_package_surfaces_multiple_findings():
    """A package broken in two ways (broken_python AND broken_pir) must
    surface BOTH findings — the orchestrator never short-circuits."""
    import shutil
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        # Copy broken_python's python/ + valid_package's sas/ + valid's model_config
        # + broken_pir's pir.yaml so the package is broken in two ways.
        shutil.copytree(FIXTURES / "broken_python" / "python", td_path / "python")
        shutil.copytree(FIXTURES / "valid_package" / "sas", td_path / "sas")
        shutil.copy(FIXTURES / "valid_package" / "model_config.yaml", td_path / "model_config.yaml")
        shutil.copy(FIXTURES / "broken_pir" / "pir.yaml", td_path / "pir.yaml")
        # Add a test that passes so the tests checker doesn't fail
        (td_path / "python" / "tests").mkdir(exist_ok=True)
        (td_path / "python" / "tests" / "test_dummy.py").write_text(
            "def test_pass() -> None:\n    assert True\n"
        )

        results = validate(td_path)
        failed = {r.checker for r in results if not r.passed}
        # Both python lint AND pir unmapped column must be detected:
        assert "static_python" in failed
        assert "pir" in failed


def test_crashed_checker_becomes_finding(monkeypatch):
    """A buggy checker that raises Exception must NOT propagate; the
    orchestrator wraps it in a single error-severity finding ending in 999."""
    from code_intake.checkers import static_sas

    class BoomChecker:
        name = "static_sas"

        def run(self, package_path: Path) -> CheckResult:
            raise RuntimeError("intentional boom")

    monkeypatch.setattr(static_sas, "StaticSasChecker", BoomChecker)

    results = validate(FIXTURES / "valid_package")
    sas_result = next(r for r in results if r.checker == "static_sas")
    assert not sas_result.passed
    codes = {f.code for f in sas_result.findings}
    assert any(c.endswith("999") for c in codes), f"got codes: {codes}"


def test_results_have_duration_recorded():
    results = validate(FIXTURES / "valid_package")
    for r in results:
        assert r.duration_seconds >= 0.0
