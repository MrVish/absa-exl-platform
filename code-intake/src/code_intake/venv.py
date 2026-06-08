"""Ephemeral per-package venv creation for Code Intake checkers.

Each `code-intake validate <package>` invocation creates a fresh venv
in a tmpdir, installs the package's deps from python/pyproject.toml,
yields a VenvContext that static_python + tests checkers use to invoke
ruff/mypy/pytest INSIDE the venv, then tears down on context exit.

Design rationale (spec section 3): ephemeral over cached because
cache invalidation is the source of most pain in similar tools; the
~25-40s cold cost per package is acceptable for CI gate use.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from code_intake.errors import VenvCreationError


@dataclass(frozen=True)
class VenvContext:
    """Handles for invoking checkers inside the venv."""

    venv_dir: Path  # the venv root
    python_path: Path  # the venv's python binary
    env_vars: dict[str, str]  # env to pass to subprocess.run for venv activation


@contextlib.contextmanager
def create_ephemeral_venv(package_path: Path, *, timeout_s: int = 180) -> Iterator[VenvContext]:
    """Create a fresh venv, install deps from python/pyproject.toml,
    yield VenvContext, tear down on exit (even on exception).
    """
    pyproject = package_path / "python" / "pyproject.toml"
    if not pyproject.exists():
        raise VenvCreationError(
            code="PY004",
            message=f"package missing python/pyproject.toml at {pyproject}",
            hint=(
                "Each package's python/ must declare its dependencies via "
                "pyproject.toml [project] dependencies. See "
                "packages/credit-risk-pd/1.0.0/python/pyproject.toml as the "
                "canonical example."
            ),
        )

    tmpdir = Path(tempfile.mkdtemp(prefix="code-intake-venv-"))
    try:
        # 1. Create venv via uv
        result = subprocess.run(
            ["uv", "venv", str(tmpdir)],
            capture_output=True,
            timeout=timeout_s,
        )
        if result.returncode != 0:
            raise VenvCreationError(
                code="PY998",
                message=f"uv venv failed: {result.stderr.decode('utf-8', errors='replace')}",
            )

        # 2. Install the package in editable mode with test extras.
        # We use the `<dir>[extra]` syntax (rather than `--extra test`)
        # because uv requires the latter to point at a pyproject.toml on
        # the *requirement* side, not the install target.
        install_target = f"{package_path / 'python'}[test]"
        result = subprocess.run(
            ["uv", "pip", "install", "-e", install_target],
            capture_output=True,
            timeout=timeout_s,
            env={**os.environ, "VIRTUAL_ENV": str(tmpdir)},
        )
        if result.returncode != 0:
            raise VenvCreationError(
                code="PY998",
                message=(
                    f"uv pip install -e failed: {result.stderr.decode('utf-8', errors='replace')}"
                ),
                hint=(
                    "Check that python/pyproject.toml has valid syntax and "
                    "that all declared deps are resolvable. Run "
                    f"`uv pip install -e {install_target}` "
                    f"locally to reproduce."
                ),
            )

        python_path = (
            tmpdir
            / ("Scripts" if sys.platform == "win32" else "bin")
            / ("python.exe" if sys.platform == "win32" else "python")
        )

        env_vars: dict[str, str] = {
            **os.environ,
            "VIRTUAL_ENV": str(tmpdir),
            "PATH": str(python_path.parent) + os.pathsep + os.environ.get("PATH", ""),
        }
        env_vars.pop("PYTHONHOME", None)

        yield VenvContext(venv_dir=tmpdir, python_path=python_path, env_vars=env_vars)
    finally:

        def _onexc(func: Any, path: str, exc: BaseException) -> None:
            # On Windows, read-only files (e.g. .pyc files) can block rmtree.
            # Flip the write bit and retry.
            os.chmod(path, stat.S_IWRITE)
            func(path)

        # Python 3.12+ uses onexc (single exception arg); older onerror is
        # deprecated. We're locked to 3.12.
        shutil.rmtree(tmpdir, onexc=_onexc)
