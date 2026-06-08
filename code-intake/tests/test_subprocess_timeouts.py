"""Subprocess timeout coverage for static_python and tests checkers.

A malformed fixture (or a real bug in ruff/mypy/pytest) must not be able to
hang code-intake indefinitely. Each checker wraps every `subprocess.run` in
a per-call timeout and emits a `{CHECKER}998` finding distinct from `999`
(crashed checker) when the subprocess exceeds it.

These tests use a fixture whose `tests/test_score.py` does `time.sleep(99999)`
at module-import time, so both `pytest --collect-only` (static_python) and
`pytest` (tests checker) hang at collection time and get killed by the
timeout. Constructor `timeout_seconds=2` is used for fast feedback.
"""

from __future__ import annotations

from pathlib import Path

from code_intake.checkers.static_python import StaticPythonChecker
from code_intake.checkers.tests import TestsChecker

FIXTURES = Path(__file__).parent / "fixtures"


def test_static_python_timeout_emits_998_finding() -> None:
    """A package whose pytest --collect-only hangs > timeout produces a
    998 finding rather than wedging the orchestrator.
    """
    checker = StaticPythonChecker(timeout_seconds=2)  # short timeout for test
    result = checker.run(FIXTURES / "timeout_python")
    assert not result.passed
    timeout_findings = [f for f in result.findings if f.code == "PY998"]
    assert len(timeout_findings) >= 1, (
        f"expected at least one PY998 timeout finding; got codes "
        f"{[f.code for f in result.findings]}"
    )
    assert "timed out" in timeout_findings[0].message.lower()
    assert timeout_findings[0].hint is not None
    assert "increase" in timeout_findings[0].hint.lower()


def test_tests_checker_timeout_emits_998_finding() -> None:
    """Tests checker also emits TST998 on subprocess timeout."""
    checker = TestsChecker(timeout_seconds=2)
    result = checker.run(FIXTURES / "timeout_python")
    assert not result.passed
    timeout_findings = [f for f in result.findings if f.code == "TST998"]
    assert len(timeout_findings) >= 1


def test_static_python_default_timeout_is_120s() -> None:
    """Default timeout matches spec §9 F1: 120s."""
    checker = StaticPythonChecker()
    assert checker.timeout_seconds == 120


def test_tests_checker_default_timeout_is_120s() -> None:
    checker = TestsChecker()
    assert checker.timeout_seconds == 120
