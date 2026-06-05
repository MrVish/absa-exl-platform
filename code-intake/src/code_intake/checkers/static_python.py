"""static_python checker: runs ruff, mypy --strict, and pytest --collect-only
against the package's python/ directory via subprocess.

Workspace-toolchain assumption (per ADR-0010 §"Negative (accepted)"): ruff
and mypy are invoked with the caller's cwd inherited, so they resolve the
WORKSPACE's `pyproject.toml` configuration (line length, lint rule set,
mypy strictness). This is intentional for Sprint 4 — packages are
workspace-toolchain-compatible. Phase 3 packages with isolated runtime
deps will switch to per-package cwd or per-package venvs.

The pytest subprocess uses `cwd=python_dir` + `--confcutdir=.` so it
doesn't walk up to the workspace's conftest/testpaths. The package must be
discoverable in isolation regardless of where it sits on disk.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .base import CheckResult, Finding


class StaticPythonChecker:
    name = "static_python"

    def run(self, package_path: Path) -> CheckResult:
        python_dir = package_path / "python"
        if not python_dir.is_dir():
            # Pure-SAS packages are valid — no Python to check.
            return CheckResult(checker=self.name, passed=True)

        if not any(python_dir.rglob("*.py")):
            # Empty python/ — treat like missing python/, no-op pass.
            # mypy would otherwise emit "There are no .py[i] files in
            # directory" which the operator sees as a confusing PY002.
            return CheckResult(checker=self.name, passed=True)

        findings: list[Finding] = []

        # ruff check
        ruff = subprocess.run(
            ["uv", "run", "ruff", "check", str(python_dir)],
            capture_output=True,
            text=True,
        )
        if ruff.returncode != 0:
            findings.append(
                Finding(
                    severity="error",
                    code="PY001",
                    message=f"ruff check failed:\n{ruff.stdout}\n{ruff.stderr}".strip(),
                )
            )

        # mypy --strict
        mypy = subprocess.run(
            ["uv", "run", "mypy", "--strict", str(python_dir)],
            capture_output=True,
            text=True,
        )
        if mypy.returncode != 0:
            findings.append(
                Finding(
                    severity="error",
                    code="PY002",
                    message=f"mypy --strict failed:\n{mypy.stdout}\n{mypy.stderr}".strip(),
                )
            )

        # pytest --collect-only
        # We invoke pytest with cwd=python_dir, override-ini, and confcutdir
        # so the surrounding workspace's pyproject.toml (testpaths/addopts)
        # and conftest.py files (collect_ignore_glob) don't leak into the
        # package being checked. A real intake target must be checkable in
        # isolation regardless of where it sits on disk.
        tests_dir = python_dir / "tests"
        if tests_dir.is_dir():
            pytest_collect = subprocess.run(
                [
                    "uv",
                    "run",
                    "pytest",
                    "--collect-only",
                    "--override-ini=testpaths=",
                    "--override-ini=addopts=",
                    "--confcutdir=.",
                    "tests",
                ],
                cwd=str(python_dir),
                capture_output=True,
                text=True,
            )
            if pytest_collect.returncode != 0:
                findings.append(
                    Finding(
                        severity="error",
                        code="PY003",
                        message=f"pytest --collect-only failed:\n"
                        f"{pytest_collect.stdout}\n{pytest_collect.stderr}".strip(),
                    )
                )

        passed = not any(f.severity == "error" for f in findings)
        return CheckResult(checker=self.name, passed=passed, findings=findings)
