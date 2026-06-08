# Phase 3 Sprint 2 — CI Hardening + Per-Package Venv + Stricter PIR

**Status:** Design approved · 2026-06-08
**Owner:** EXL platform team
**Sprint window:** ~8-10 engineer-days
**Branch:** `phase-3/sprint-2-venv-pir`

---

## 1. Goal

Close two classes of work that follow naturally from Phase 3 Sprint 1:

1. **CI hardening** — fix the two bugs that surfaced when `localstack-demo.yml` ran for the first time on PR #7 (missing `uvicorn` dep, broken soft-fail logic), then capture the first green sample transcript as the canonical "what success looks like" reference.

2. **ADR-0010 deferrals** — replace Code Intake's workspace-toolchain Python with proper per-package venv orchestration, and extend the PIR column extractor to handle f-strings + simple variable column names.

Both workstreams ship as one PR. The CI hardening lands in the first three commits so subsequent venv + PIR work is actually gated by the demo.

## 2. Locked scope decisions

Locked during brainstorming:

| Area | Choice |
|---|---|
| Sprint theme | A + B (CI hardening + ADR-0010 deferrals) |
| Venv isolation | Ephemeral `uv venv` per `code-intake validate` invocation; no caching |
| PIR pattern coverage | F-strings + variable column names via intra-function constant propagation; skip dict aliases, method chains, runtime instrumentation |
| Deps shape | Each package declares deps in `python/pyproject.toml`; `uv pip install -e python/` materializes the env |
| Worked example | `credit-risk-pd@1.0.0/python/pyproject.toml` added; chain digest re-anchors (Sprint 4's `3b1134c4...` rotates) |
| Venv placement | tmpdir per validate (Approach A from brainstorming); no on-disk pollution, no cache invalidation logic |

## 3. Architecture summary

Three workstreams, one PR:

```
A. CI hardening (commits 1-3, day 1)
  ├─ A.1  uvicorn[standard]>=0.30 added to registry/api deps + uv lock
  ├─ A.2  localstack-demo.yml restructured: demo step always exits 0,
  │        dedicated Gate step explicitly fails only on exit code 1
  └─ A.3  docs/runbooks/sample-transcripts/2026-06-08-demo.md committed
          from the first green CI run on this PR

B-1. Per-package venv orchestration (commits 4-9, days 2-6)
  ├─ code-intake/src/code_intake/venv.py (new module)
  │      - create_ephemeral_venv(package_path) -> contextmgr
  │      - yields VenvContext(python_path, venv_dir, env_vars)
  ├─ checkers/static_python.py: invoke ruff/mypy/pytest INSIDE venv
  ├─ checkers/tests.py: same
  ├─ PY004: package missing python/pyproject.toml (hard fail)
  ├─ Migrate worked example: credit-risk-pd@1.0.0/python/pyproject.toml
  └─ Regenerate package + pipeline manifests (chain digest rotates)

B-2. Stricter PIR column extraction (commits 10-12, days 7-9)
  ├─ checkers/pir.py extended with _ConstantPropagator class
  ├─ F-string pattern: data[f"col_{n}"] → glob "col_*"
  ├─ Variable pattern: col = "tenure"; data[col] → "tenure"
  └─ Tests cover both patterns + the existing literal pattern

Day 10: Final verification + PR open
```

## 4. CI hardening details

### 4.1 `uvicorn[standard]` dependency

Add to `registry/api/pyproject.toml` `[project] dependencies`:

```toml
"uvicorn[standard]>=0.30",
```

Run `uv lock` to update `uv.lock`. The `[standard]` extra pulls `httptools`, `uvloop` (Linux/macOS only — skipped on Windows), `websockets`, `watchfiles`, etc. — same set the demo orchestrator implicitly relied on.

### 4.2 Workflow gate restructure

`.github/workflows/localstack-demo.yml` `Run demo` step changes from `exit $ec` to `exit 0` so GitHub doesn't aggregate the step failure into the job status. A new `Gate on demo exit code` step replaces the old `Annotate failure exit code` + `Soft-fail on infra issues` pair:

```yaml
- name: Run demo
  id: demo
  run: |
    set +e
    uv run python -m demo run --no-color --no-cleanup --transcript demo-transcript.md
    ec=$?
    echo "exit_code=$ec" >> $GITHUB_OUTPUT
    exit 0

- name: Upload transcript on success
  if: steps.demo.outputs.exit_code == '0'
  uses: actions/upload-artifact@v4
  with:
    name: demo-transcript
    path: demo-transcript.md
    retention-days: 14

- name: Upload failure bundle
  if: steps.demo.outputs.exit_code != '0'
  uses: actions/upload-artifact@v4
  with:
    name: demo-failure-bundle
    path: |
      demo-transcript.md
      infra/localstack/terraform/terraform.tfstate
      infra/localstack/.uvicorn.log
    retention-days: 30
    if-no-files-found: warn

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

Drops the obsolete `Annotate failure exit code` + `Soft-fail on infra issues` steps.

### 4.3 Sample transcript capture

After A.1 + A.2 land and CI goes green, download the `demo-transcript` artifact from the run and commit it as `docs/runbooks/sample-transcripts/2026-06-08-demo.md`. The runbook already references this filename convention.

## 5. Per-package venv orchestration

### 5.1 New module `code-intake/src/code_intake/venv.py`

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
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from code_intake.errors import VenvCreationError


@dataclass(frozen=True)
class VenvContext:
    """Handles the env vars + paths a checker needs to run inside the venv."""

    venv_dir: Path           # the venv root (contains bin/, lib/, etc.)
    python_path: Path        # the venv's python binary
    env_vars: dict[str, str] # env to pass to subprocess.run for venv activation


@contextlib.contextmanager
def create_ephemeral_venv(package_path: Path, *, timeout_s: int = 180) -> Iterator[VenvContext]:
    """Create a fresh venv, install deps from python/pyproject.toml, yield VenvContext.

    Raises PY004 (via raise VenvCreationError) if python/pyproject.toml is missing.
    Raises VenvCreationError on venv creation or pip install failure.
    Tears down the tmpdir on exit (even on exception).
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
        # 1. Create venv via uv (fast, well-tested)
        result = subprocess.run(
            ["uv", "venv", str(tmpdir)],
            capture_output=True,
            timeout=timeout_s,
        )
        if result.returncode != 0:
            raise VenvCreationError(
                code="PY998",  # reuses the timeout finding code for "venv setup failed"
                message=f"uv venv failed: {result.stderr.decode('utf-8', errors='replace')}",
            )

        # 2. Install the package in editable mode (pulls its declared deps)
        result = subprocess.run(
            ["uv", "pip", "install", "-e", str(package_path / "python")],
            capture_output=True,
            timeout=timeout_s,
            env={**os.environ, "VIRTUAL_ENV": str(tmpdir)},
        )
        if result.returncode != 0:
            raise VenvCreationError(
                code="PY998",
                message=f"uv pip install -e failed: {result.stderr.decode('utf-8', errors='replace')}",
                hint=(
                    "Check that python/pyproject.toml has valid syntax and "
                    "that all declared deps are resolvable. Run "
                    f"`uv pip install -e {package_path / 'python'}` locally to reproduce."
                ),
            )

        python_path = tmpdir / ("Scripts" if sys.platform == "win32" else "bin") / (
            "python.exe" if sys.platform == "win32" else "python"
        )

        # 3. Compose env vars for checker subprocesses
        env_vars = {
            **os.environ,
            "VIRTUAL_ENV": str(tmpdir),
            # Prepend venv bin/ to PATH so `ruff`, `mypy`, `pytest` resolve correctly
            "PATH": str(python_path.parent) + os.pathsep + os.environ.get("PATH", ""),
        }
        # On Windows, also drop PYTHONHOME if set (uv venv handles this)
        env_vars.pop("PYTHONHOME", None)

        yield VenvContext(venv_dir=tmpdir, python_path=python_path, env_vars=env_vars)
    finally:
        # Tear down: shutil.rmtree handles read-only files (Windows venv quirk)
        def _onerror(func, path, exc_info):  # noqa: ANN001
            import stat
            os.chmod(path, stat.S_IWRITE)
            func(path)
        shutil.rmtree(tmpdir, onerror=_onerror)
```

### 5.2 Checker integration

`static_python.py` and `tests.py` change their subprocess invocations to:
1. Accept the `VenvContext` (or `env: dict[str, str]`) from the orchestrator
2. Pass `env=venv_ctx.env_vars` to every `subprocess.run`
3. The `cwd=python_dir` arg stays — checkers still run from the package's python/ dir

The orchestrator (`code_intake.orchestrator.validate()`) wraps checker invocations in the `create_ephemeral_venv` context:

```python
def validate(package_path: Path, *, strict: bool = False) -> list[CheckResult]:
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
        # Surface the failure as a Finding so the orchestrator's "never propagate
        # exceptions" invariant holds.
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

### 5.3 Migration policy

Hard fail on missing `python/pyproject.toml`. The only existing package is `credit-risk-pd@1.0.0`, which we migrate in this sprint. No backward-compat path; future packages declare deps from day one.

## 6. Stricter PIR column extraction

### 6.1 New patterns

Today's `_extract_column_references` walks `ast.Subscript` and `ast.Attribute` nodes for literal `data["col"]` / `data.col`. The extension adds two more:

**Pattern 1 — f-string column names:**

```python
def score(data):
    for i in range(12):
        x = data[f"month_{i}"]  # extracts as "month_*"
```

The extractor records `month_*` (a glob); the PIR validation matches against any column whose name matches the glob.

**Pattern 2 — variable column names via intra-function constant propagation:**

```python
def score(data):
    col_name = "tenure_months"
    x = data[col_name]   # extracts as "tenure_months"
```

The extractor maintains a per-function symbol table of `name: Constant` assignments, then resolves `data[name]` against that table when `name` is a string literal target.

### 6.2 What's NOT supported

Explicitly out of scope (per brainstorming choice):

- Dict aliases: `cols = data; cols["x"]`
- Method calls: `data.get("x", default)`
- Cross-function flow: `col = get_col(); data[col]`
- Runtime instrumentation / proxy classes
- Multi-assignment: `a = b = "tenure"; data[a]`

Future sprints can add these if real-world packages demand them. For now, the conservative 80% catches the common case without false positives.

### 6.3 Implementation sketch

```python
class _ConstantPropagator(ast.NodeVisitor):
    """Tracks `name = "literal"` and `name = f"prefix_{var}"` assignments
    within a single function. Resolves data[name] references against the table.
    """

    def __init__(self) -> None:
        self.const_table: dict[str, str] = {}  # name -> resolved column ref (may include glob)
        self.column_refs: set[str] = set()

    def visit_Assign(self, node: ast.Assign) -> None:
        # Track `name = "literal"` and `name = f"prefix_{...}"`
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target_name = node.targets[0].id
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                self.const_table[target_name] = node.value.value
            elif isinstance(node.value, ast.JoinedStr):
                # f-string: resolve fixed parts, substitute "*" for variable parts
                resolved = _resolve_fstring_to_glob(node.value)
                if resolved is not None:
                    self.const_table[target_name] = resolved
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        # Look for data[...] patterns
        if isinstance(node.value, ast.Name) and node.value.id == "data":
            key = self._resolve_subscript_key(node.slice)
            if key is not None:
                self.column_refs.add(key)
        self.generic_visit(node)

    def _resolve_subscript_key(self, slice_node: ast.expr) -> str | None:
        # Literal: data["col"]
        if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
            return slice_node.value
        # Variable: data[col_name] -> look up in const table
        if isinstance(slice_node, ast.Name):
            return self.const_table.get(slice_node.id)
        # Inline f-string: data[f"col_{n}"]
        if isinstance(slice_node, ast.JoinedStr):
            return _resolve_fstring_to_glob(slice_node)
        return None


def _resolve_fstring_to_glob(node: ast.JoinedStr) -> str | None:
    """Convert an f-string to a glob pattern:
       f"month_{i}" -> "month_*"
       f"col_{prefix}_{suffix}_data" -> "col_*_*_data"
       f"{var}_only" -> "*_only"
    Returns None if the f-string has no string parts at all (pure variable).
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
        return None  # pure variable f-string isn't a useful column hint
    return "".join(parts)
```

### 6.4 Matching against PIR mapping

The PIR mapping declares column names like `tenure_months`, `month_1`, `month_2`, etc. The extractor's output (`{"tenure_months", "month_*"}`) needs to match against PIR's declared set:

- Exact match: `tenure_months` ∈ PIR cols → satisfied
- Glob match: `month_*` matches all PIR cols starting with `month_` → all satisfied

A column referenced in code but not declared in PIR raises `PIR001`. A glob that matches zero PIR cols raises a new `PIR002` (potentially-dangling glob warning, severity=warning not error — globs that miss are suspicious but not fatal).

## 7. Worked example migration

### 7.1 New file `packages/credit-risk-pd/1.0.0/python/pyproject.toml`

```toml
[project]
name = "credit-risk-pd-score"
version = "1.0.0"
description = "Scoring code for credit-risk-pd@1.0.0. Sole consumer: ABSA EXL Pipeline Factory."
requires-python = ">=3.12"
dependencies = []   # the worked example uses only stdlib

[project.optional-dependencies]
test = [
    "pytest>=8.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["."]
```

No external runtime deps (the worked example is intentionally minimal — single function reading dict keys). Pytest is in test extras so `uv pip install -e python/ --extra test` pulls it.

### 7.2 Chain digest re-anchor

Adding `python/pyproject.toml` to credit-risk-pd@1.0.0 changes the package's payload:

1. The `model_config_sha256` field in payload (or a new `python_deps_sha256` field, see below) changes.
2. Therefore `sha256(canonical_json(payload))` changes.
3. Therefore the package envelope's `digest` field changes.
4. Therefore the pipeline's `upstream_refs[0].digest` (set by `upstream_resolver` during pipeline generation) must update.

**Implementation:** during this sprint, after the worked example migration commits, regenerate both manifests:

```bash
uv run code-intake generate-manifest packages/credit-risk-pd/1.0.0/
uv run generate-pipeline generate credit-risk-pd 1.0.0 --force
```

Sprint 4's anchor `3b1134c4775a2b58ea8a57888a33e12ec697ea86fe6f905020427dcefabcbdf6` rotates to a new digest. The new digest is recorded in the spec's section 9 (References) and in the runbook.

### 7.3 Open question: where in payload does python-deps fingerprint live?

Two options:
- (a) Folded into `model_config_sha256`: the existing field hashes the whole package config; just add python/pyproject.toml to the hashed set.
- (b) New explicit field `python_deps_sha256` in `artifact_hashes`: clearer audit trail; requires platform-contracts schema bump.

**Choice: (a) for this sprint.** The package's `model_config_sha256` already covers "the package's static config files"; pyproject.toml is one of them. Option (b) would require a schema migration which is overhead for this sprint. If we later want explicit fingerprinting, ADR-0010 can be amended.

## 8. New finding codes + error handling

| Code | Severity | Meaning |
|---|---|---|
| `PY004` | error | package missing `python/pyproject.toml` |
| `PY998` (existing, reused) | error | venv creation or pip install failed |
| `PIR002` (new) | warning | glob pattern matches zero columns in PIR mapping |

`VenvCreationError` (new exception class in `code_intake.errors`) carries `code`, `message`, `hint`. The orchestrator catches it and surfaces as a `Finding` so the "checkers never propagate exceptions" invariant holds.

## 9. Implementation order

12 commits in 3 phases:

```
Phase A — CI hardening (day 1)
  T1.  Add uvicorn[standard] to registry/api deps + uv lock          [0.5d]
  T2.  Restructure localstack-demo.yml: gate logic via output, drop
       broken soft-fail step                                          [0.5d]
  T3.  After first green CI run, capture + commit
       docs/runbooks/sample-transcripts/2026-06-08-demo.md            [0.25d]

Phase B-1 — Per-package venv (days 2-6)
  T4.  code-intake/src/code_intake/errors.py: add VenvCreationError   [0.25d]
  T5.  code-intake/src/code_intake/venv.py + tests (mocked uv venv)   [1d]
  T6.  Refactor static_python.py + tests.py to accept env_vars kwarg  [0.5d]
  T7.  Orchestrator wraps venv checkers in create_ephemeral_venv ctx  [0.5d]
  T8.  Worked example: add credit-risk-pd@1.0.0/python/pyproject.toml [0.25d]
  T9.  Regenerate package + pipeline manifests; commit new digest     [0.5d]

Phase B-2 — Stricter PIR extraction (days 7-9)
  T10. _ConstantPropagator class + _resolve_fstring_to_glob helper    [1d]
  T11. PIR mapping match logic: glob support + new PIR002 finding     [0.5d]
  T12. Worked example exercises both new patterns (optional fixture)  [0.5d]

Phase C — Final (day 10)
  T13. Final verification: full workspace tests + lint + mypy +
       terraform validate + actionlint + chain digest assertion       [0.5d]
  T14. Open PR                                                         [0.25d]
```

**Total: ~7-8 engineer days serial, ~5 days with parallel subagents on independent tasks.**

## 10. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| `uv venv` fails on Windows during tests (per-package venv has Windows quirks) | Medium | T5 mocks `subprocess.run` so unit tests don't actually create venvs; integration coverage comes from the demo CI run on Linux |
| Worked example migration breaks the demo (e.g., pyproject.toml syntax bug) | Low | Demo runs on PR; any regression caught before merge |
| f-string glob matches spuriously against unrelated PIR cols | Medium | `PIR002` warning (not error) when glob matches zero cols; future sprint can tighten if false positives surface |
| Venv setup cost causes demo CI to exceed 8-minute timeout | Low | Demo only validates one package (worked example); ~30s venv setup << 8 min |
| Chain digest re-anchor surfaces a hidden bug in upstream_resolver | Low | Sprint 4's logic is well-tested; T9 will rerun + verify both manifests' digests match end-to-end |

## 11. Acceptance criteria

For the sprint to ship:

1. `make demo` returns exit 0 locally.
2. `localstack-demo.yml` CI workflow runs green on the PR (exit code 0).
3. The Gate step correctly classifies exit codes 1 vs 2 vs 3 (verified by an intentional break-then-fix during the sprint, or accepted as covered by T2's logic review).
4. `uv run pytest` workspace-wide: no new failures (Phase 3 Sprint 1 baseline: 259 passing).
5. `uv run ruff check && uv run ruff format --check && uv run mypy` all clean.
6. `terraform validate` clean on all 3 stacks.
7. `actionlint .github/workflows/localstack-demo.yml` clean.
8. `code-intake validate packages/credit-risk-pd/1.0.0` runs inside an ephemeral venv (verifiable by deleting `pytest` from workspace deps and confirming validate still works because the venv has its own).
9. PIR extractor catches both new patterns (f-string + variable column name) in a fixture; existing literal pattern still works.
10. Chain digest re-anchored: both committed manifests' digests match end-to-end; new digest recorded in this spec section.
11. Sample transcript committed at `docs/runbooks/sample-transcripts/2026-06-08-demo.md`.
12. PR text includes the new chain digest, summary of the 3 CI fixes, and a brief description of the 2 ADR-0010 deferrals closed.

## 12. References

- ADR-0010 (Productized package contract) — section "Deferred items": [`docs/adr/0010-productized-package-contract.md`](../../adr/0010-productized-package-contract.md)
- ADR-0009 (Signing) — for the chain-of-custody re-anchor context
- Phase 3 Sprint 1 spec: [`docs/superpowers/specs/2026-06-05-absa-exl-phase-3-sprint-1-localstack-demo-design.md`](2026-06-05-absa-exl-phase-3-sprint-1-localstack-demo-design.md)
- Phase 3 Sprint 1 PR #7 (now merged as `3ac6835`): https://github.com/MrVish/absa-exl-platform/pull/7
- uv venv documentation: https://docs.astral.sh/uv/pip/environments/
