"""tests checker: actually invokes pytest against the package's
python/tests/ directory.

Uses the same isolation pattern as static_python (cwd=python_dir +
--override-ini + --confcutdir) so the surrounding workspace's pytest
config and conftest don't leak into the package being checked. The
package must be testable in isolation regardless of where it sits
on disk."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .base import CheckResult, Finding


class TestsChecker:
    name = "tests"

    def run(self, package_path: Path) -> CheckResult:
        tests_dir = package_path / "python" / "tests"
        if not tests_dir.is_dir():
            return CheckResult(checker=self.name, passed=True)

        python_dir = package_path / "python"
        result = subprocess.run(
            [
                "uv",
                "run",
                "pytest",
                "--override-ini=testpaths=",
                "--override-ini=addopts=",
                "--confcutdir=.",
                "tests",
                "-q",
            ],
            cwd=str(python_dir),
            capture_output=True,
            text=True,
        )

        # pytest exit codes:
        #   0 = all tests passed
        #   1 = tests collected but >=1 failed
        #   2 = test collection failed (syntax error, missing import, ...)
        #   5 = no tests collected (we treat as pass — no tests is allowed)
        findings: list[Finding] = []
        if result.returncode == 2:
            findings.append(
                Finding(
                    severity="error",
                    code="TST001",
                    message=f"pytest collection failed:\n{result.stdout}\n{result.stderr}".strip(),
                )
            )
        elif result.returncode == 1:
            findings.append(
                Finding(
                    severity="error",
                    code="TST002",
                    message=f">=1 test failed:\n{result.stdout}".strip(),
                )
            )
        elif result.returncode not in (0, 5):
            findings.append(
                Finding(
                    severity="error",
                    code="TST001",
                    message=f"pytest returned unexpected exit code {result.returncode}:\n"
                    f"{result.stdout}\n{result.stderr}".strip(),
                )
            )

        passed = not any(f.severity == "error" for f in findings)
        return CheckResult(checker=self.name, passed=passed, findings=findings)
