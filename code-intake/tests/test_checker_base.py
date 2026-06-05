from __future__ import annotations

from pathlib import Path

from code_intake.checkers.base import (
    Checker,
    CheckResult,
    Finding,
)


def test_finding_is_frozen():
    f = Finding(severity="error", code="X001", message="boom")
    try:
        f.severity = "warning"  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("Finding should be frozen")


def test_check_result_default_findings_empty():
    r = CheckResult(checker="x", passed=True)
    assert r.findings == []
    assert r.duration_seconds == 0.0


def test_check_result_with_findings():
    r = CheckResult(
        checker="x",
        passed=False,
        findings=[Finding(severity="error", code="X001", message="boom")],
    )
    assert r.passed is False
    assert len(r.findings) == 1


def test_checker_protocol_is_satisfied_by_stub():
    class StubChecker:
        name = "stub"

        def run(self, package_path: Path) -> CheckResult:
            return CheckResult(checker="stub", passed=True)

    c: Checker = StubChecker()  # static type assertion that the protocol matches
    result = c.run(Path("/nonexistent"))
    assert result.passed is True
