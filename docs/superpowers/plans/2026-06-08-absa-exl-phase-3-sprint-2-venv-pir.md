# Phase 3 Sprint 2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CI hardening + per-package venv orchestration + stricter PIR extraction. See [`docs/superpowers/specs/2026-06-08-absa-exl-phase-3-sprint-2-venv-pir-design.md`](../specs/2026-06-08-absa-exl-phase-3-sprint-2-venv-pir-design.md).

**Tech Stack:** Python 3.12, uv venv, Click, FastAPI, ast (stdlib).

**Branch:** `phase-3/sprint-2-venv-pir`. Current HEAD: `2216eb1` (spec).

---

## Pre-flight verification

```bash
git status                                  # clean
git log --oneline -3                        # 2216eb1 spec on top of 3ac6835 (main, Sprint 1)
uv run pytest 2>&1 | tail -3                # 259 passing (Sprint 1 baseline)
uv run ruff check && uv run mypy            # both clean
```

---

## Phase A — CI Hardening (day 1)

### Task 1: Add `uvicorn[standard]` to `registry/api` deps

**Files:**
- Modify: `registry/api/pyproject.toml`
- Modify: `uv.lock`

- [ ] **Step 1: Add dep**

Edit `registry/api/pyproject.toml`. In the `[project] dependencies = [...]` list, add:

```toml
"uvicorn[standard]>=0.30",
```

(Add it after `boto3>=1.34.131,` to keep alphabetical-ish ordering.)

- [ ] **Step 2: Update lockfile**

```bash
uv lock
```

- [ ] **Step 3: Verify resolution**

```bash
grep -A 1 "^name = .uvicorn" uv.lock | head -10
```

Expected: a `uvicorn` entry with version `>=0.30`.

- [ ] **Step 4: Verify the demo's uvicorn invocation resolves**

```bash
PYTHONPATH=scripts uv run python -c "import shutil; print('uvicorn on PATH:', shutil.which('uvicorn'))"
```

Expected: prints a non-None path.

- [ ] **Step 5: Run registry-api tests for regression**

```bash
uv run pytest registry/api/ -v 2>&1 | tail -3
```

Expected: 26 passing (was 26 baseline).

- [ ] **Step 6: Commit**

```bash
git add registry/api/pyproject.toml uv.lock
git commit -m "T1/A.1: add uvicorn[standard]>=0.30 to registry-api deps

PR #7's first CI run failed at the readyz poll (last_status=None) because
\`uv run uvicorn registry_api.app:create_app\` couldn't resolve the
uvicorn binary - uvicorn was never declared as a registry-api
dependency. Locally it worked via transitive/system install; on the GH
runner's clean uv environment it didn't.

Explicit dep + uv lock regen. The [standard] extra pulls httptools,
uvloop (Linux/macOS only - skipped on Windows), websockets, watchfiles
- same set the demo orchestrator implicitly relied on.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Restructure `localstack-demo.yml` Gate logic

**Files:**
- Modify: `.github/workflows/localstack-demo.yml`

- [ ] **Step 1: Read current workflow**

```bash
cat .github/workflows/localstack-demo.yml
```

Find the "Run demo" step (id: demo), the "Upload" steps, the "Annotate failure exit code" step, and the "Soft-fail on infra issues" step.

- [ ] **Step 2: Apply the gate restructure**

Replace the `Run demo` step's body so it ALWAYS exits 0:

```yaml
- name: Run demo
  id: demo
  run: |
    set +e
    uv run python -m demo run --no-color --no-cleanup --transcript demo-transcript.md
    ec=$?
    echo "exit_code=$ec" >> $GITHUB_OUTPUT
    exit 0
  env:
    PYTHONPATH: scripts
```

Replace the `Upload transcript on success` step's `if:` from `success()` to:

```yaml
if: steps.demo.outputs.exit_code == '0'
```

Replace the `Upload failure bundle` step's `if:` from `failure()` to:

```yaml
if: steps.demo.outputs.exit_code != '0'
```

DELETE the old `Annotate failure exit code` step (the Gate step below replaces it).

DELETE the old `Soft-fail on infra issues` step (no longer needed; the Gate step doesn't fire `exit 1` for codes 2/3).

ADD a new step in place of the deleted ones:

```yaml
- name: Gate on demo exit code
  run: |
    ec="${{ steps.demo.outputs.exit_code }}"
    case "$ec" in
      0) echo "::notice::Demo passed (chain verified end-to-end)." ;;
      1) echo "::error::Chain verification failed (platform regression). See demo-failure-bundle artifact." ; exit 1 ;;
      2) echo "::warning::Demo infrastructure failure (not a platform regression); not blocking merge." ;;
      3) echo "::warning::Demo teardown failed (CI runner discarded); not blocking merge." ;;
      *) echo "::error::Demo failed with unexpected exit code $ec" ; exit 1 ;;
    esac
```

The `Always tear down` step at the end stays unchanged.

- [ ] **Step 3: Verify YAML syntax**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/localstack-demo.yml'))"
```

Expected: no errors.

- [ ] **Step 4: Lint with actionlint**

```bash
actionlint .github/workflows/localstack-demo.yml 2>&1 | tail -5
```

(If actionlint not on PATH, skip — yaml.safe_load above is the minimum gate.)

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/localstack-demo.yml
git commit -m "T2/A.2: restructure localstack-demo gate so soft-fail actually works

PR #7's CI run produced 'Demo infra issue (exit 2); not blocking merge'
in the workflow log BUT the check still showed as failed in the
GitHub UI. Root cause: GitHub aggregates job status from all step
statuses. The 'Run demo' step exited 2 -> step failed -> job failed,
and no subsequent 'exit 0' step could undo that.

Fix: 'Run demo' now ALWAYS exits 0, captures the real demo exit code
into \$GITHUB_OUTPUT, and a dedicated 'Gate on demo exit code' step
explicitly fails ONLY for exit code 1 (platform regression). Exit 2
and 3 produce ::warning:: annotations but the job still passes.

The 'Upload transcript on success' / 'Upload failure bundle' if:
conditions now reference steps.demo.outputs.exit_code instead of
GitHub's success() / failure() builtins (which are unreliable when
the demo step doesn't actually fail).

Drops the now-redundant 'Annotate failure exit code' and 'Soft-fail
on infra issues' steps.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Capture sample transcript (post-CI-green)

**Files:**
- Create: `docs/runbooks/sample-transcripts/2026-06-08-demo.md`

**Note:** this task can only run AFTER T1 and T2 are pushed and CI goes green. Order: implement T1+T2, push, wait for CI, then return for T3.

- [ ] **Step 1: Push T1+T2 to remote**

```bash
git push origin phase-3/sprint-2-venv-pir
```

- [ ] **Step 2: Wait for CI to run + go green**

Monitor with:
```bash
gh run list --branch phase-3/sprint-2-venv-pir --workflow localstack-demo --limit 5
```

- [ ] **Step 3: Download the demo-transcript artifact from the latest green run**

```bash
RUN_ID=$(gh run list --branch phase-3/sprint-2-venv-pir --workflow localstack-demo --status success --limit 1 --json databaseId -q '.[0].databaseId')
mkdir -p /tmp/transcript-capture
gh run download "$RUN_ID" --name demo-transcript --dir /tmp/transcript-capture
```

- [ ] **Step 4: Commit the captured transcript**

```bash
mkdir -p docs/runbooks/sample-transcripts
cp /tmp/transcript-capture/demo-transcript.md docs/runbooks/sample-transcripts/2026-06-08-demo.md
git add docs/runbooks/sample-transcripts/2026-06-08-demo.md
git commit -m "T3/A.3: commit sample transcript from first green CI run

docs/runbooks/localstack-demo.md (Sprint 1 T20) references this file
as the canonical 'what success looks like' reference. Sample comes from
the first localstack-demo CI run on this branch after T1+T2 landed.

Note: byte-equality between local and CI runs is NOT asserted - the
transcript embeds timestamps that change per-run. This sample is a
reference, not a regression gate.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

If the CI run fails (exit 2/3), don't capture — investigate, fix, and re-push. T3 is gated on a real green run.

---

## Phase B-1 — Per-package venv orchestration (days 2-6)

### Task 4: Add `VenvCreationError` to errors.py

**Files:**
- Modify: `code-intake/src/code_intake/errors.py`

- [ ] **Step 1: Read current errors module**

```bash
cat code-intake/src/code_intake/errors.py
```

- [ ] **Step 2: Add VenvCreationError class**

Append to `code-intake/src/code_intake/errors.py`:

```python
class VenvCreationError(Exception):
    """Raised by venv.create_ephemeral_venv() when venv setup fails.

    The orchestrator catches this and surfaces it as a Finding so the
    'checkers never propagate exceptions' invariant holds.
    """

    def __init__(self, *, code: str, message: str, hint: str | None = None) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        super().__init__(message)
```

- [ ] **Step 3: Run code-intake tests to ensure no breakage**

```bash
uv run pytest code-intake/ -v 2>&1 | tail -3
```

Expected: 54 passing (Sprint 1 T3 baseline).

- [ ] **Step 4: Commit**

```bash
git add code-intake/src/code_intake/errors.py
git commit -m "T4/B-1.1: add VenvCreationError exception class

Code-intake's venv.create_ephemeral_venv() (T5) raises this when:
  - python/pyproject.toml missing (code=PY004)
  - uv venv fails (code=PY998)
  - uv pip install -e fails (code=PY998)

The orchestrator (T7) catches it and surfaces as a Finding so the
'checkers never propagate exceptions to the caller' invariant holds.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Implement `code_intake/venv.py`

**Files:**
- Create: `code-intake/src/code_intake/venv.py`
- Create: `code-intake/tests/test_venv.py`

- [ ] **Step 1: Write failing tests**

Create `code-intake/tests/test_venv.py`:

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from code_intake.errors import VenvCreationError
from code_intake.venv import VenvContext, create_ephemeral_venv


def test_create_ephemeral_venv_raises_PY004_when_pyproject_missing(tmp_path: Path) -> None:
    pkg = tmp_path / "broken-package"
    (pkg / "python").mkdir(parents=True)
    # NO pyproject.toml
    with pytest.raises(VenvCreationError) as exc_info:
        with create_ephemeral_venv(pkg):
            pass
    assert exc_info.value.code == "PY004"
    assert "pyproject.toml" in exc_info.value.message
    assert exc_info.value.hint is not None


def test_create_ephemeral_venv_succeeds_and_yields_context(tmp_path: Path) -> None:
    pkg = tmp_path / "good-package"
    (pkg / "python").mkdir(parents=True)
    (pkg / "python" / "pyproject.toml").write_text('[project]\nname = "test"\nversion = "0.1"\n')

    with patch("code_intake.venv.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
        with create_ephemeral_venv(pkg) as ctx:
            assert isinstance(ctx, VenvContext)
            assert ctx.venv_dir.exists()
            assert "VIRTUAL_ENV" in ctx.env_vars
            assert ctx.env_vars["VIRTUAL_ENV"] == str(ctx.venv_dir)
            assert "PATH" in ctx.env_vars
            # PATH includes the venv's bin dir
            assert str(ctx.python_path.parent) in ctx.env_vars["PATH"]


def test_create_ephemeral_venv_tears_down_on_exception(tmp_path: Path) -> None:
    pkg = tmp_path / "good-package"
    (pkg / "python").mkdir(parents=True)
    (pkg / "python" / "pyproject.toml").write_text('[project]\nname = "test"\nversion = "0.1"\n')

    captured_venv_dir: Path | None = None
    with patch("code_intake.venv.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        with pytest.raises(RuntimeError, match="body"):
            with create_ephemeral_venv(pkg) as ctx:
                captured_venv_dir = ctx.venv_dir
                raise RuntimeError("body raised")
    assert captured_venv_dir is not None
    # After context exit, the tmpdir is gone
    assert not captured_venv_dir.exists()


def test_create_ephemeral_venv_raises_PY998_on_uv_venv_failure(tmp_path: Path) -> None:
    pkg = tmp_path / "good-package"
    (pkg / "python").mkdir(parents=True)
    (pkg / "python" / "pyproject.toml").write_text('[project]\nname = "test"\nversion = "0.1"\n')

    with patch("code_intake.venv.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1, stdout=b"", stderr=b"uv venv failed: permission denied"
        )
        with pytest.raises(VenvCreationError) as exc_info:
            with create_ephemeral_venv(pkg):
                pass
        assert exc_info.value.code == "PY998"
        assert "uv venv" in exc_info.value.message.lower() or "permission denied" in exc_info.value.message


def test_create_ephemeral_venv_raises_PY998_on_pip_install_failure(tmp_path: Path) -> None:
    pkg = tmp_path / "good-package"
    (pkg / "python").mkdir(parents=True)
    (pkg / "python" / "pyproject.toml").write_text('[project]\nname = "test"\nversion = "0.1"\n')

    call_count = [0]

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        call_count[0] += 1
        if call_count[0] == 1:
            # First call: uv venv succeeds
            return MagicMock(returncode=0, stdout=b"", stderr=b"")
        # Second call: uv pip install fails
        return MagicMock(returncode=1, stdout=b"", stderr=b"resolution-impossible")

    with patch("code_intake.venv.subprocess.run", side_effect=fake_run):
        with pytest.raises(VenvCreationError) as exc_info:
            with create_ephemeral_venv(pkg):
                pass
        assert exc_info.value.code == "PY998"
        assert "install" in exc_info.value.message.lower() or "resolution-impossible" in exc_info.value.message
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest code-intake/tests/test_venv.py -v
```

Expected: FAIL — `code_intake.venv` doesn't exist.

- [ ] **Step 3: Implement venv.py**

Create `code-intake/src/code_intake/venv.py`:

```python
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

from code_intake.errors import VenvCreationError


@dataclass(frozen=True)
class VenvContext:
    """Handles for invoking checkers inside the venv."""

    venv_dir: Path           # the venv root
    python_path: Path        # the venv's python binary
    env_vars: dict[str, str] # env to pass to subprocess.run for venv activation


@contextlib.contextmanager
def create_ephemeral_venv(
    package_path: Path, *, timeout_s: int = 180
) -> Iterator[VenvContext]:
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

        # 2. Install the package in editable mode
        result = subprocess.run(
            ["uv", "pip", "install", "-e", str(package_path / "python"), "--extra", "test"],
            capture_output=True,
            timeout=timeout_s,
            env={**os.environ, "VIRTUAL_ENV": str(tmpdir)},
        )
        if result.returncode != 0:
            raise VenvCreationError(
                code="PY998",
                message=(
                    f"uv pip install -e failed: "
                    f"{result.stderr.decode('utf-8', errors='replace')}"
                ),
                hint=(
                    "Check that python/pyproject.toml has valid syntax and "
                    "that all declared deps are resolvable. Run "
                    f"`uv pip install -e {package_path / 'python'} --extra test` "
                    f"locally to reproduce."
                ),
            )

        python_path = tmpdir / ("Scripts" if sys.platform == "win32" else "bin") / (
            "python.exe" if sys.platform == "win32" else "python"
        )

        env_vars = {
            **os.environ,
            "VIRTUAL_ENV": str(tmpdir),
            "PATH": str(python_path.parent) + os.pathsep + os.environ.get("PATH", ""),
        }
        env_vars.pop("PYTHONHOME", None)

        yield VenvContext(
            venv_dir=tmpdir, python_path=python_path, env_vars=env_vars
        )
    finally:
        def _onerror(func, path, exc_info):  # noqa: ANN001, ANN202, ARG001
            os.chmod(path, stat.S_IWRITE)
            func(path)
        shutil.rmtree(tmpdir, onerror=_onerror)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest code-intake/tests/test_venv.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Lint + type-check**

```bash
uv run ruff check code-intake/src/code_intake/venv.py
uv run mypy code-intake/src/code_intake/venv.py
```

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add code-intake/src/code_intake/venv.py code-intake/tests/test_venv.py
git commit -m "T5/B-1.2: code-intake venv module with create_ephemeral_venv

Per-package venv orchestration per spec section 5.1.

create_ephemeral_venv(package_path) context manager:
  1. Raises VenvCreationError(PY004) if python/pyproject.toml is missing
  2. Creates tmpdir venv via 'uv venv'
  3. Installs the package in editable mode + test extras via
     'uv pip install -e python/ --extra test'
  4. Yields VenvContext(venv_dir, python_path, env_vars)
  5. Tears down tmpdir on exit (including read-only files via
     shutil.rmtree onerror handler for Windows quirks)

VenvContext.env_vars composes VIRTUAL_ENV + PATH-prefix with venv's
bin dir so subsequent subprocess.run invocations resolve ruff/mypy/
pytest from the venv rather than the workspace toolchain.

PY998 (existing 'subprocess failed' code) is reused for both uv venv
and uv pip install failures.

5/5 tests pass; mypy + ruff clean.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Refactor `static_python.py` + `tests.py` to accept `env_vars`

**Files:**
- Modify: `code-intake/src/code_intake/checkers/static_python.py`
- Modify: `code-intake/src/code_intake/checkers/tests.py`
- Modify: `code-intake/tests/test_subprocess_timeouts.py` (constructor signature)

- [ ] **Step 1: Modify StaticPythonChecker to accept env_vars**

In `static_python.py`, update the `__init__` to accept `env_vars: dict[str, str] | None = None`:

```python
class StaticPythonChecker:
    name = "static_python"

    def __init__(
        self,
        *,
        timeout_seconds: int = 120,
        env_vars: dict[str, str] | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.env_vars = env_vars  # None means use os.environ
```

Then every `subprocess.run(...)` call (or `run_with_timeout(...)` from `_subprocess_util`) gets `env=self.env_vars`:

```python
proc = run_with_timeout(
    args,
    timeout_seconds=self.timeout_seconds,
    cwd=python_dir,
    env=self.env_vars,
)
```

(`run_with_timeout` already accepts `env` kwarg per Sprint 1 T3.)

- [ ] **Step 2: Same change in TestsChecker**

In `tests.py`, add `env_vars` to `__init__`, pass to subprocess calls.

- [ ] **Step 3: Update test_subprocess_timeouts to provide env_vars=None explicitly**

In `code-intake/tests/test_subprocess_timeouts.py`, the existing tests construct `StaticPythonChecker(timeout_seconds=2)` and `TestsChecker(timeout_seconds=2)` — these calls still work because `env_vars` defaults to None. No test change needed unless ruff/mypy complains about positional args.

Verify by running:

```bash
uv run pytest code-intake/tests/test_subprocess_timeouts.py -v
```

Expected: 4 passing (same as before).

- [ ] **Step 4: Lint + type-check**

```bash
uv run ruff check code-intake/src/code_intake/checkers/
uv run mypy code-intake/src/code_intake/checkers/
```

- [ ] **Step 5: Commit**

```bash
git add code-intake/src/code_intake/checkers/static_python.py \
        code-intake/src/code_intake/checkers/tests.py
git commit -m "T6/B-1.3: checkers accept env_vars kwarg for venv invocation

Static_python and tests checkers gain an optional env_vars: dict[str, str]
| None constructor kwarg. When set, every subprocess.run/run_with_timeout
call uses this env instead of os.environ.

The orchestrator (T7) wraps these checkers in create_ephemeral_venv()
and passes VenvContext.env_vars so ruff/mypy/pytest resolve from the
venv's bin/ dir, not the workspace's.

env_vars=None (default) means 'use os.environ' - preserves backward
compat for any direct callers + makes the existing tests pass without
modification.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Orchestrator wraps venv checkers in `create_ephemeral_venv`

**Files:**
- Modify: `code-intake/src/code_intake/orchestrator.py`
- Modify: `code-intake/tests/test_orchestrator.py` (if a relevant test exists)

- [ ] **Step 1: Read existing orchestrator**

```bash
cat code-intake/src/code_intake/orchestrator.py
```

- [ ] **Step 2: Refactor `validate()` to wrap venv checkers**

```python
def validate(package_path: Path, *, strict: bool = False) -> list[CheckResult]:
    """Run all checkers against the package.

    Venv-dependent checkers (static_python, tests) run inside an
    ephemeral venv created from python/pyproject.toml. Other checkers
    run in the workspace context.
    """
    from code_intake.checkers import pir, schema, static_python, static_sas, tests
    from code_intake.errors import VenvCreationError
    from code_intake.venv import create_ephemeral_venv

    results: list[CheckResult] = []

    # Non-venv checkers run first (cheap, no setup)
    results.append(static_sas.StaticSasChecker().run(package_path))
    results.append(schema.SchemaChecker().run(package_path))
    results.append(pir.PirChecker().run(package_path))

    # Venv-dependent checkers run inside an ephemeral venv
    try:
        with create_ephemeral_venv(package_path) as venv_ctx:
            results.append(
                static_python.StaticPythonChecker(env_vars=venv_ctx.env_vars).run(package_path)
            )
            results.append(
                tests.TestsChecker(env_vars=venv_ctx.env_vars).run(package_path)
            )
    except VenvCreationError as e:
        # Surface as a Finding rather than propagating - checkers
        # contract says exceptions are converted to findings.
        results.append(CheckResult(
            checker_name="venv",
            passed=False,
            findings=[Finding(
                code=e.code,
                severity="error",
                message=e.message,
                hint=e.hint,
                location=str(package_path / "python"),
            )],
        ))

    return results
```

(Adjust imports and existing structure to match the actual file. The key change: wrap static_python + tests in the venv context, catch VenvCreationError, emit a Finding.)

- [ ] **Step 3: Verify orchestrator tests still pass**

```bash
uv run pytest code-intake/tests/ -v 2>&1 | tail -5
```

Note: the orchestrator tests may use fixtures that have `python/score.py` but NOT `python/pyproject.toml`. Those tests will start hitting PY004. Two options:
(a) Add `python/pyproject.toml` to each fixture (test/fixtures/valid_package, broken_python, timeout_python, etc.)
(b) Make `python/` directory existence the trigger — packages with no `python/` skip the venv entirely

Choose (a) — explicit pyproject.toml per fixture is more honest. Each fixture's pyproject.toml can be minimal:

```toml
[project]
name = "fixture-package"
version = "0.1"
dependencies = []

[project.optional-dependencies]
test = ["pytest"]
```

(Pytest is in test extras so the venv has it for the tests checker.)

Update each existing fixture under `code-intake/tests/fixtures/*/python/` to add a `pyproject.toml`. There are likely 4-5 fixtures.

- [ ] **Step 4: Run full code-intake tests**

```bash
uv run pytest code-intake/ -v 2>&1 | tail -5
```

Expected: all green (54 prior + 5 new from T5 = 59 passing, assuming no new tests in T6/T7).

- [ ] **Step 5: Commit**

```bash
git add code-intake/src/code_intake/orchestrator.py \
        code-intake/tests/fixtures/
git commit -m "T7/B-1.4: orchestrator wraps venv checkers in create_ephemeral_venv

validate() now runs static_python + tests INSIDE an ephemeral venv
created from the package's python/pyproject.toml. Non-venv checkers
(static_sas, schema, pir) still run in the workspace toolchain - they
only need the static files, not the runtime imports.

VenvCreationError from venv module is caught here and surfaced as a
'venv' checker Finding (code PY004 or PY998), preserving the contract
that orchestrator never propagates exceptions to the caller.

Test fixtures under code-intake/tests/fixtures/ gain minimal
python/pyproject.toml files so they exercise the venv path properly.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Add `python/pyproject.toml` to worked example

**Files:**
- Create: `packages/credit-risk-pd/1.0.0/python/pyproject.toml`

- [ ] **Step 1: Create the file**

```toml
[project]
name = "credit-risk-pd-score"
version = "1.0.0"
description = "Scoring code for credit-risk-pd@1.0.0. Sole consumer: ABSA EXL Pipeline Factory."
requires-python = ">=3.12"
dependencies = []

[project.optional-dependencies]
test = ["pytest>=8.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["."]
```

- [ ] **Step 2: Run validate on the worked example to verify it now works through the venv path**

```bash
uv run code-intake validate packages/credit-risk-pd/1.0.0 --strict
```

Expected: exit 0, all checkers green. The venv creation will take ~25s.

- [ ] **Step 3: Commit**

```bash
git add packages/credit-risk-pd/1.0.0/python/pyproject.toml
git commit -m "T8/B-1.5: worked example python/pyproject.toml

credit-risk-pd@1.0.0 declares its Python deps (none - it's stdlib-only)
+ test extras (pytest). Code Intake's new per-package venv (T5) reads
this to materialize an isolated environment for static_python + tests
checkers.

No runtime deps; pytest in [project.optional-dependencies.test].
Hatchling backend matches the other workspace members.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Regenerate package + pipeline manifests (chain re-anchor)

**Files:**
- Modify: `packages/credit-risk-pd/1.0.0/manifest.json`
- Modify: `pipelines/credit-risk-pd/1.0.0/manifest.json`

- [ ] **Step 1: Regenerate package manifest**

```bash
uv run code-intake generate-manifest packages/credit-risk-pd/1.0.0
```

The new manifest's `digest` field will be different from Sprint 4's `3b1134c4...` because the package now contains `python/pyproject.toml`.

- [ ] **Step 2: Capture the new digest**

```bash
NEW_DIGEST=$(python -c "import json; print(json.load(open('packages/credit-risk-pd/1.0.0/manifest.json'))['digest'])")
echo "New chain anchor: $NEW_DIGEST"
```

- [ ] **Step 3: Regenerate pipeline manifest (`upstream_refs[0].digest` will pick up the new digest)**

```bash
uv run generate-pipeline generate credit-risk-pd 1.0.0 --force
```

- [ ] **Step 4: Verify the chain is re-anchored**

```bash
python -c "
import json
pkg = json.load(open('packages/credit-risk-pd/1.0.0/manifest.json'))
pipe = json.load(open('pipelines/credit-risk-pd/1.0.0/manifest.json'))
print('package digest         :', pkg['digest'])
print('pipeline upstream_refs :', pipe['payload']['upstream_refs'][0]['digest'])
print('match                  :', pkg['digest'] == pipe['payload']['upstream_refs'][0]['digest'])
"
```

Expected: both digests match (and both != the old `3b1134c4...`).

- [ ] **Step 5: Update the spec to record the new digest**

Edit `docs/superpowers/specs/2026-06-08-absa-exl-phase-3-sprint-2-venv-pir-design.md` section 11 acceptance criterion #10 — replace `<new_digest>` placeholder with the actual value from step 2.

- [ ] **Step 6: Commit**

```bash
git add packages/credit-risk-pd/1.0.0/manifest.json \
        pipelines/credit-risk-pd/1.0.0/manifest.json \
        docs/superpowers/specs/2026-06-08-absa-exl-phase-3-sprint-2-venv-pir-design.md
git commit -m "T9/B-1.6: regenerate manifests; chain re-anchors to new digest

Sprint 4's anchor 3b1134c4775a2b58ea8a57888a33e12ec697ea86fe6f905020427dcefabcbdf6
rotates because credit-risk-pd@1.0.0/python/pyproject.toml (T8) is a
new file inside the package's hashed payload, changing
model_config_sha256 -> changing payload digest -> changing envelope
digest -> changing pipeline upstream_refs[0].digest.

Both manifests regenerated:
  - packages/credit-risk-pd/1.0.0/manifest.json
  - pipelines/credit-risk-pd/1.0.0/manifest.json

Chain integrity verified: package.digest == pipeline.upstream_refs[0]
.digest. New digest recorded in the spec.

This is the second chain re-anchor in the platform's history
(first: Sprint 4 initial anchor when chain-of-custody was introduced).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase B-2 — Stricter PIR column extraction (days 7-9)

### Task 10: `_ConstantPropagator` class + `_resolve_fstring_to_glob`

**Files:**
- Modify: `code-intake/src/code_intake/checkers/pir.py`
- Create: `code-intake/tests/test_pir_extraction.py` (or extend existing test_pir.py)

- [ ] **Step 1: Write failing tests**

Create `code-intake/tests/test_pir_extraction.py`:

```python
"""Tests for the extended _extract_column_references (PIR T10)."""

from __future__ import annotations

from code_intake.checkers.pir import _extract_column_references


def test_extracts_literal_subscript() -> None:
    """Baseline: existing pattern still works."""
    src = '''
def score(data):
    return data["tenure_months"] * 0.5
'''
    cols = _extract_column_references(src)
    assert "tenure_months" in cols


def test_extracts_literal_attribute() -> None:
    src = '''
def score(data):
    return data.income * 0.2
'''
    cols = _extract_column_references(src)
    assert "income" in cols


def test_extracts_variable_column_name() -> None:
    """New: col = "tenure"; data[col] -> "tenure"."""
    src = '''
def score(data):
    col = "tenure_months"
    return data[col]
'''
    cols = _extract_column_references(src)
    assert "tenure_months" in cols


def test_extracts_fstring_with_glob() -> None:
    """New: data[f"month_{i}"] -> "month_*"."""
    src = '''
def score(data):
    total = 0
    for i in range(12):
        total += data[f"month_{i}"]
    return total
'''
    cols = _extract_column_references(src)
    assert "month_*" in cols


def test_extracts_multi_part_fstring() -> None:
    """data[f"col_{a}_{b}_data"] -> "col_*_*_data"."""
    src = '''
def score(data):
    a = "x"
    b = "y"
    return data[f"col_{a}_{b}_data"]
'''
    cols = _extract_column_references(src)
    assert "col_*_*_data" in cols


def test_pure_variable_fstring_is_ignored() -> None:
    """f"{var}" with no literal parts gives no useful glob; should be skipped."""
    src = '''
def score(data):
    n = "tenure"
    return data[f"{n}"]
'''
    cols = _extract_column_references(src)
    # The "n" should resolve via the constant propagator to "tenure"
    # since we DO handle name lookup. But the f-string fallback alone
    # would skip pure-var f-strings; with name lookup it's "tenure".
    # Either is acceptable; document the expectation:
    assert "tenure" in cols or "*" in cols


def test_constant_propagation_is_intra_function() -> None:
    """Different functions have independent constant tables."""
    src = '''
def score_a(data):
    col = "income"
    return data[col]

def score_b(data):
    col = "tenure"
    return data[col]
'''
    cols = _extract_column_references(src)
    assert "income" in cols
    assert "tenure" in cols
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest code-intake/tests/test_pir_extraction.py -v
```

Expected: most fail (only the literal tests pass with current code).

- [ ] **Step 3: Extend `_extract_column_references` with the propagator**

In `code-intake/src/code_intake/checkers/pir.py`, add the `_ConstantPropagator` class and helper:

```python
import ast


def _resolve_fstring_to_glob(node: ast.JoinedStr) -> str | None:
    """Convert an f-string to a glob pattern.

    f"month_{i}"           -> "month_*"
    f"col_{a}_{b}_data"    -> "col_*_*_data"
    f"{var}_only"          -> "*_only"
    f"{var}"               -> None (pure variable; skip)
    """
    parts: list[str] = []
    has_literal = False
    for piece in node.values:
        if isinstance(piece, ast.Constant) and isinstance(piece.value, str):
            parts.append(piece.value)
            has_literal = True
        else:
            parts.append("*")
    if not has_literal:
        return None
    return "".join(parts)


class _ConstantPropagator(ast.NodeVisitor):
    """Walks a single FunctionDef, tracks `name = "literal"` and
    `name = f"prefix_{var}"` assignments, resolves data[...] subscripts
    against the table.
    """

    def __init__(self) -> None:
        self.const_table: dict[str, str] = {}
        self.column_refs: set[str] = set()

    def visit_Assign(self, node: ast.Assign) -> None:
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target_name = node.targets[0].id
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                self.const_table[target_name] = node.value.value
            elif isinstance(node.value, ast.JoinedStr):
                resolved = _resolve_fstring_to_glob(node.value)
                if resolved is not None:
                    self.const_table[target_name] = resolved
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if isinstance(node.value, ast.Name) and node.value.id == "data":
            key = self._resolve_subscript_key(node.slice)
            if key is not None:
                self.column_refs.add(key)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # data.col_name (literal attribute access)
        if isinstance(node.value, ast.Name) and node.value.id == "data":
            self.column_refs.add(node.attr)
        self.generic_visit(node)

    def _resolve_subscript_key(self, slice_node: ast.expr) -> str | None:
        if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
            return slice_node.value
        if isinstance(slice_node, ast.Name):
            return self.const_table.get(slice_node.id)
        if isinstance(slice_node, ast.JoinedStr):
            return _resolve_fstring_to_glob(slice_node)
        return None
```

Then rewrite `_extract_column_references` to use the propagator per-function:

```python
def _extract_column_references(source: str) -> set[str]:
    """Extract column-name references from Python source.

    Walks each function definition with a fresh _ConstantPropagator
    (constant tables are intra-function only).
    """
    refs: set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return refs

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            propagator = _ConstantPropagator()
            propagator.visit(node)
            refs.update(propagator.column_refs)
    return refs
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest code-intake/tests/test_pir_extraction.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Ensure existing pir tests still pass**

```bash
uv run pytest code-intake/tests/ -v 2>&1 | tail -5
```

Expected: no regressions on the existing 5 + 4 + 4 = ~13 code-intake tests + the new ones.

- [ ] **Step 6: Commit**

```bash
git add code-intake/src/code_intake/checkers/pir.py \
        code-intake/tests/test_pir_extraction.py
git commit -m "T10/B-2.1: stricter PIR extraction via intra-function const propagation

Extends _extract_column_references with two new patterns per spec
section 6.1:

  Pattern 1 (f-string column names):
    data[f\"month_{i}\"]  -> glob 'month_*'

  Pattern 2 (variable column names via simple constant propagation):
    col = \"tenure\"
    data[col]            -> 'tenure'

Implementation:
  _ConstantPropagator(ast.NodeVisitor) - walks one FunctionDef,
    tracks 'name = \"literal\"' and 'name = f\"prefix_{var}\"'
    assignments, resolves data[name] against the table.

  _resolve_fstring_to_glob(JoinedStr) -> str | None - composes
    glob string by replacing FormattedValue parts with '*', keeping
    Constant string parts verbatim. Pure-variable f-strings (no
    literal parts) return None.

Out of scope (spec section 6.2): dict aliases, .get() method calls,
cross-function flow, runtime instrumentation. Conservative 80%
catches common patterns without false positives.

7 new tests + existing pir tests green.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: Glob matching + `PIR002` finding

**Files:**
- Modify: `code-intake/src/code_intake/checkers/pir.py` (the matching logic, not the extraction)
- Modify: existing pir tests if needed

- [ ] **Step 1: Read current matching logic**

Find the function in `pir.py` that compares extracted column references against PIR-declared columns.

- [ ] **Step 2: Add glob matching**

When a reference contains `*`, match it as a glob (using `fnmatch.fnmatchcase`) against the PIR-declared columns. If it matches zero declared columns, emit `PIR002` (warning, not error).

```python
import fnmatch

def _check_column_references_against_pir(
    refs: set[str], pir_columns: set[str]
) -> list[Finding]:
    findings: list[Finding] = []
    for ref in refs:
        if "*" in ref:
            # Glob pattern; match against pir_columns
            matched = [c for c in pir_columns if fnmatch.fnmatchcase(c, ref)]
            if not matched:
                findings.append(Finding(
                    code="PIR002",
                    severity="warning",
                    message=(
                        f"code references column-glob {ref!r} but no PIR "
                        f"mapping column matches it"
                    ),
                    hint=(
                        "Glob patterns come from f-string column accesses like "
                        "data[f\"col_{i}\"]. If the glob matches no PIR columns, "
                        "either the code is unreachable or PIR is incomplete."
                    ),
                ))
        else:
            # Literal reference
            if ref not in pir_columns:
                findings.append(Finding(
                    code="PIR001",
                    severity="error",
                    message=(
                        f"code references column {ref!r} not declared in PIR mapping"
                    ),
                ))
    return findings
```

(Adjust to fit the existing pir.py structure — the function may already exist with a different name.)

- [ ] **Step 3: Add PIR002 test**

In `test_pir_extraction.py` (or pir checker tests), add:

```python
from code_intake.checkers.pir import PirChecker  # or whatever the class is
# ... fixture-based test that exercises a package with f-string col access
# referencing a glob that matches no PIR cols -> expects PIR002 warning
```

(Adapt to the existing testing pattern in code-intake/tests/.)

- [ ] **Step 4: Run tests**

```bash
uv run pytest code-intake/tests/ -v 2>&1 | tail -5
```

- [ ] **Step 5: Commit**

```bash
git add code-intake/src/code_intake/checkers/pir.py code-intake/tests/
git commit -m "T11/B-2.2: glob matching + PIR002 dangling-glob warning

Column references containing '*' are now matched via fnmatch.fnmatchcase
against PIR-declared columns. A glob that matches zero declared cols
emits PIR002 (severity=warning, not error) - suspicious but not fatal.

PIR001 (existing, error severity) still fires for non-glob references
that aren't in the PIR mapping.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 12: (Optional) Worked example exercises new patterns

**Files:**
- Modify: `packages/credit-risk-pd/1.0.0/python/score.py` (optional — add a small loop)
- Modify: `packages/credit-risk-pd/1.0.0/pir.yaml` (add corresponding cols)

If `score.py` currently uses only literal patterns, optionally extend it to also use a variable column name OR an f-string, to exercise the new path in the demo's worked example. This validates the chain through real production behavior.

If adding new columns to PIR, regenerate manifests (chain re-anchors AGAIN — this is fine, the digest will rotate one more time).

**This task is optional.** If the worked example already covers the new patterns naturally, skip. Otherwise, decide whether to make the change here or defer to a future sprint that's specifically about expanding the worked example.

For autonomy, defer to a future sprint — the test coverage in T10 + T11 is sufficient. Skip this task.

---

## Phase C — Final (day 10)

### Task 13: Final verification

- [ ] **Step 1: Full workspace pytest**

```bash
uv run pytest 2>&1 | tail -3
```

Expected: ~270+ passing (259 from Sprint 1 + 5 from T5 + 7 from T10 + smaller test changes).

- [ ] **Step 2: ruff + format + mypy**

```bash
uv run ruff check
uv run ruff format --check
uv run mypy
```

Expected: all clean.

- [ ] **Step 3: terraform validate**

```bash
terraform -chdir=infra/localstack/terraform validate
terraform -chdir=terraform/modules/signing-foundation validate
terraform -chdir=terraform/modules/pipeline-registry validate
```

Expected: all "Success!"

- [ ] **Step 4: actionlint**

```bash
actionlint .github/workflows/localstack-demo.yml
```

Expected: clean (if actionlint not installed, run `yaml.safe_load` python check as fallback).

- [ ] **Step 5: Run `code-intake validate` on the worked example**

```bash
uv run code-intake validate packages/credit-risk-pd/1.0.0 --strict
```

Expected: exit 0. The venv creation will take ~25-40s.

- [ ] **Step 6: Verify the chain digest matches end-to-end**

```bash
python -c "
import json, hashlib
from platform_contracts.canonical import canonical_json
pkg = json.loads(open('packages/credit-risk-pd/1.0.0/manifest.json').read())
pipe = json.loads(open('pipelines/credit-risk-pd/1.0.0/manifest.json').read())
pkg_recomp = hashlib.sha256(canonical_json(pkg['payload'])).hexdigest()
pipe_upstream = pipe['payload']['upstream_refs'][0]['digest']
print('package payload digest (recomputed) :', pkg_recomp)
print('pipeline upstream_refs[0].digest    :', pipe_upstream)
print('chain holds                         :', pkg_recomp == pipe_upstream)
"
```

Expected: match.

---

### Task 14: Open PR

- [ ] **Step 1: Confirm clean tree**

```bash
git status
```

Expected: clean (only the pre-existing untracked files from prior sprints).

- [ ] **Step 2: Review commit list**

```bash
git log --oneline main..HEAD
```

Expected: ~12 commits (1 spec + 11 implementation).

- [ ] **Step 3: Push (the spec was pushed earlier; this push adds the implementation)**

```bash
git push origin phase-3/sprint-2-venv-pir
```

- [ ] **Step 4: Open PR**

```bash
gh pr create --title "Phase 3 Sprint 2: CI Hardening + Per-Package Venv + Stricter PIR" --body "$(cat <<'EOF'
## Summary

- **A. CI hardening:** add `uvicorn[standard]` to registry-api deps (caused PR #7 exit-2 demo crash); restructure `localstack-demo.yml` Gate logic so soft-fail actually converts step-failure → job-success; capture first green sample transcript.
- **B-1. Per-package venv orchestration (ADR-0010 Negative §2):** each package declares Python deps in `python/pyproject.toml`; Code Intake creates an ephemeral `uv venv` per `validate` invocation; checkers run inside the venv.
- **B-2. Stricter PIR column extraction (ADR-0010 Negative §3):** f-string column names (`data[f"col_{n}"]` → glob `col_*`) and variable column names (`col = "tenure"; data[col]` → `"tenure"`) via intra-function constant propagation.

## Chain digest re-anchor

Sprint 4's anchor `3b1134c4...` rotates to a new digest because credit-risk-pd@1.0.0/python/pyproject.toml is a new file in the package's hashed payload. New digest: `<NEW_DIGEST_HERE>`.

## Verification

- [x] `uv run pytest` — all green
- [x] `uv run ruff check && uv run mypy` clean
- [x] `terraform validate` clean
- [x] `code-intake validate packages/credit-risk-pd/1.0.0 --strict` exit 0 (with venv setup ~25-40s)
- [x] Chain digest holds end-to-end
- [ ] `localstack-demo` CI workflow green on the PR (the Gate restructure is its own meta-test)

## Test plan

- [ ] Confirm the Gate step correctly handles exit codes 1, 2, 3 (intentional break-then-fix during sprint OR verified by manual T2 review)
- [ ] Confirm `code-intake validate` runs INSIDE the venv by temporarily removing pytest from workspace deps and re-running

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review

After writing the plan, run inline:

**Spec coverage:**
- Spec §4 (CI hardening) → T1, T2, T3 ✓
- Spec §5 (per-package venv) → T4, T5, T6, T7 ✓
- Spec §6 (stricter PIR) → T10, T11 ✓
- Spec §7 (worked example migration + chain re-anchor) → T8, T9 ✓
- Spec §8 (finding codes) → T5 (PY004, PY998), T11 (PIR002) ✓
- Spec §11 (acceptance criteria) → T13 (final verification covers all 12 criteria) ✓

**Placeholder scan:**
- T9 step 5: `<NEW_DIGEST_HERE>` is a deliberate placeholder, filled in at run time
- T14 PR body: `<NEW_DIGEST_HERE>` is the same placeholder, filled in from T9 step 2

Both are run-time fills, not stale TODOs.

**Type consistency:**
- `VenvContext` fields: `venv_dir: Path`, `python_path: Path`, `env_vars: dict[str, str]` — consistent T5 → T7
- `VenvCreationError(*, code, message, hint)` constructor — consistent T4 → T5
- Finding fields used: `code`, `severity`, `message`, `hint`, `location` — match Sprint 1 T3's extended Finding dataclass

No issues found.
