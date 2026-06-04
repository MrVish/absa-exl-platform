from __future__ import annotations

import tempfile
from pathlib import Path

from code_intake.checkers.tests import TestsChecker

FIXTURES = Path(__file__).parent / "fixtures"


def test_valid_package_tests_pass():
    result = TestsChecker().run(FIXTURES / "valid_package")
    assert result.passed, f"unexpected findings: {result.findings}"
    assert result.checker == "tests"


def test_failing_test_returns_tst002():
    result = TestsChecker().run(FIXTURES / "broken_tests")
    assert not result.passed
    codes = {f.code for f in result.findings}
    assert "TST002" in codes


def test_no_python_tests_dir_passes():
    with tempfile.TemporaryDirectory() as td:
        result = TestsChecker().run(Path(td))
        assert result.passed
        assert result.findings == []
