"""tests checker: actually invokes pytest against the package's
python/tests/ directory.

Uses the same isolation pattern as static_python (cwd=python_dir +
--override-ini + --confcutdir) so the surrounding workspace's pytest
config and conftest don't leak into the package being checked. The
package must be testable in isolation regardless of where it sits
on disk.

Per-subprocess timeout (F1): the pytest call is wrapped with
`timeout=self.timeout_seconds` via the local `run_with_timeout` helper,
which on Windows kills the *whole* `uv -> pytest -> python` process tree
on timeout (plain `subprocess.run(timeout=...)` only kills the immediate
child, leaving grandchildren holding the stdout/stderr pipes and
wedging the parent). On `TimeoutExpired` we emit a `TST998` finding,
intentionally distinct from `TST999` (crashed checker, emitted by the
orchestrator) so operators can tell "tests timed out" apart from
"tests checker threw an exception"."""

from __future__ import annotations

import subprocess
from pathlib import Path

from ._subprocess_util import run_with_timeout
from .base import CheckResult, Finding

DEFAULT_TIMEOUT_SECONDS = 120


class TestsChecker:
    name = "tests"
    # Tell pytest this isn't a test class — without this, the collector
    # warns when it's imported into a test module and finds the `__init__`.
    __test__ = False

    def __init__(self, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> None:
        self.timeout_seconds = timeout_seconds

    def run(self, package_path: Path) -> CheckResult:
        tests_dir = package_path / "python" / "tests"
        if not tests_dir.is_dir():
            return CheckResult(checker=self.name, passed=True)

        python_dir = package_path / "python"
        findings: list[Finding] = []
        try:
            result = run_with_timeout(
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
                timeout_seconds=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            findings.append(
                Finding(
                    severity="error",
                    code="TST998",
                    message=(
                        f"pytest timed out after {self.timeout_seconds}s "
                        f"on {python_dir}"
                    ),
                    hint=(
                        "Increase --timeout-seconds on TestsChecker, or "
                        "investigate why pytest is hanging (a hung fixture, "
                        "an infinite import side-effect, or a real test/tool "
                        "bug)."
                    ),
                    location=str(python_dir),
                )
            )
            return CheckResult(checker=self.name, passed=False, findings=findings)

        # pytest exit codes:
        #   0 = all tests passed
        #   1 = tests collected but >=1 failed
        #   2 = test collection failed (syntax error, missing import, ...)
        #   5 = no tests collected (we treat as pass — no tests is allowed)
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
