# Sprint 4 — Code Intake + First Track A Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close Phase 2 by shipping Code Intake — a new `code-intake/` uv workspace member that validates productized packages (SAS + Python + PIR + tests + model_config) and emits a signed package manifest — plus extending Pipeline Factory with `upstream_refs[]` so its manifest references the validated package by digest. Combined with a worked-example wire-through proving the full Track A chain works end-to-end.

**Architecture:** Five focused checker modules (`static_python`, `static_sas`, `schema`, `tests`, `pir`) under one orchestrator that collects all findings and never short-circuits. A new envelope payload type (`package`) shares Sprint 3's signer infrastructure unchanged. Pipeline Factory's manifest gains an optional `upstream_refs[]` array; the generator reads the corresponding `packages/<name>/<version>/manifest.json` at gen-time and embeds the cross-link digest. The pipeline's own signature covers the cross-link, completing the chain-of-custody from validated package → generated pipeline → registry inventory.

**Tech Stack:** Python 3.12, `click`, `jsonschema`, `pyyaml`, stdlib `ast` for column extraction, subprocess for ruff/mypy/pytest, `moto v5` for tests. No new AWS / Terraform / IAM. uv workspace.

**Predecessors:** Sprint 1 (Registry & Shared Contracts), Sprint 2 (Pipeline Factory), Sprint 3 (Signing & OIDC Foundation, merged `767d434`). All Sprint 1+2+3 tests must still pass after this plan lands.

**Spec:** [docs/superpowers/specs/2026-06-04-absa-exl-phase-2-sprint-4-code-intake-design.md](../specs/2026-06-04-absa-exl-phase-2-sprint-4-code-intake-design.md)

**Branch:** `phase-2/sprint-4-code-intake` (spec is already committed here as `790b0bb`).

---

## Task Map

| # | Title | Touches | Why this order |
|---|---|---|---|
| T1 | Contract schemas: add 2 new + modify 2 existing | `platform-contracts/src/.../schemas/`, `models.py` | All downstream tasks import the regenerated models |
| T2 | Scaffold `code-intake` workspace member + errors + Checker protocol | `code-intake/`, root `pyproject.toml` | Establishes package shell + the interface every checker implements |
| T3 | `static_python` checker | `code-intake/src/.../checkers/static_python.py` + tests + fixtures | Independent checker; first one is the reference implementation |
| T4 | `static_sas` checker | `code-intake/src/.../checkers/static_sas.py` + tests + fixtures | Independent checker |
| T5 | `schema` checker | `code-intake/src/.../checkers/schema.py` + tests + fixtures | Independent checker |
| T6 | `tests` checker | `code-intake/src/.../checkers/tests.py` + tests + fixtures | Independent checker |
| T7 | `pir` checker | `code-intake/src/.../checkers/pir.py` + tests + fixtures | Independent checker; uses stdlib `ast` |
| T8 | Orchestrator | `code-intake/src/.../orchestrator.py` + tests | Wires the five checkers; never short-circuits |
| T9 | `package_config` loader + `manifest` builder | `code-intake/src/.../package_config.py`, `manifest.py` + tests | Manifest builder needs validated config |
| T10 | CLI (`validate` + `generate-manifest`) | `code-intake/src/.../cli.py` + tests | Surfaces used by CI and the worked example |
| T11 | Worked example package | `packages/credit-risk-pd/1.0.0/...` | Real package the e2e test runs against |
| T12 | Pipeline-factory extension: `upstream_resolver` + `manifest.py`/`generator.py` mods | `pipeline-factory/src/...` | Embeds the cross-link in the pipeline manifest |
| T13 | Update pipeline-factory's `credit-risk-pd` config + regenerate pipeline manifest | `pipeline-factory/configs/.../model_config.yaml`, `pipelines/.../manifest.json` | Brings the worked example end-to-end |
| T14 | End-to-end Track A test | `code-intake/tests/test_e2e_track_a.py` | Proves the full chain works without AWS |
| T15 | CI workflows: new `code-intake.yml` + modify `pipeline-factory.yml` | `.github/workflows/` | Activates the drift gates and the dual-root signer |
| T16 | ADR-0010 + ADR-0006 edit + READMEs | `docs/adr/`, `code-intake/README.md`, `packages/credit-risk-pd/1.0.0/README.md` | Locks the design rationale |
| T17 | Final verification + PR | repo-wide | Acceptance criteria check, open PR |

---

## Conventions used throughout this plan

- **Working directory** is the repo root (`C:\Vishnu\Claude\absa-exl-platform`) unless a step says otherwise.
- **Branch** is `phase-2/sprint-4-code-intake` (already checked out per the spec commit `790b0bb`).
- **Test runner** is `uv run pytest` from the repo root. The root `pyproject.toml` has `addopts = "-q --import-mode=importlib"`. T2 adds `code-intake/tests` to `testpaths`.
- **Commit message style:** Conventional Commits prefixes (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`).
- **No `--no-verify`.** Pre-commit hooks (`ruff`, `ruff-format`, `terraform_fmt`, `actionlint`, secret scanning) must all pass. If a hook fails, fix the underlying issue.
- **Both `ruff check` and `ruff format --check` must pass.** The Sprint 3 CI failure was a `ruff format` miss; verify both in every task that touches Python.
- **Existing factual context:**
  - `execution_tier` valid values are `"standard"` and `"scalable"` (from `platform-contracts/src/platform_contracts/schemas/model-config.schema.json:15`).
  - `model-config.schema.json` lives in `platform-contracts/` — there is no `pipeline-factory/src/pipeline_factory/schemas/` directory.
  - The pipeline-factory's `generator.py:96-126` is the integration point for `upstream_resolver`.
  - `manifest-envelope.schema.json`'s `subject_type` enum already includes `"package"` (verified by reading `platform-contracts/src/platform_contracts/models.py:16-18`) — no envelope-schema change needed.

---

## Task 1: Contract schemas — 2 new + 2 modified, regenerate models

**Why:** All downstream Python code (Code Intake, Pipeline Factory) imports Pydantic models generated from these schemas. Doing all four schema changes in one task means one regeneration of `models.py` and one drift-gate verification.

**Files:**
- Create: `platform-contracts/src/platform_contracts/schemas/package-manifest-payload.schema.json`
- Create: `platform-contracts/src/platform_contracts/schemas/pir-mapping.schema.json`
- Modify: `platform-contracts/src/platform_contracts/schemas/pipeline-manifest-payload.schema.json` (add `upstream_refs[]`)
- Modify: `platform-contracts/src/platform_contracts/schemas/model-config.schema.json` (add `upstream_package` block)
- Modify: `platform-contracts/regenerate-models.sh` (add the two new schemas to its SCHEMAS list)
- Regenerate: `platform-contracts/src/platform_contracts/models.py`
- Test: `platform-contracts/tests/test_loader.py` (extend with the new schemas' positive + negative cases)

- [ ] **Step 1: Write the failing tests**

Append to `platform-contracts/tests/test_loader.py`:

```python
import pytest
from platform_contracts.loader import validate


# --- package-manifest-payload ---

def test_package_manifest_payload_minimum_valid():
    validate("package-manifest-payload", {
        "schema_version": 1,
        "code_intake_version": "0.1.0",
        "model_name": "credit-risk-pd",
        "version": "1.0.0",
        "generated_at": "2026-06-04T12:00:00+00:00",
        "package_layout": {
            "sas_files":        [{"path": "sas/score.sas", "sha256": "a"*64}],
            "python_files":     [{"path": "python/score.py", "sha256": "b"*64}],
            "test_files":       [{"path": "python/tests/test_score.py", "sha256": "c"*64}],
            "pir_ref":          {"path": "pir.yaml", "sha256": "d"*64},
            "model_config_ref": {"path": "model_config.yaml", "sha256": "e"*64},
        },
        "validation_summary": {
            "ran_at": "2026-06-04T12:00:00+00:00",
            "checks": [{"name": "static_python", "passed": True, "finding_count": 0}],
        },
    })


def test_package_manifest_payload_rejects_bad_sha256_format():
    from jsonschema import ValidationError
    with pytest.raises(ValidationError):
        validate("package-manifest-payload", {
            "schema_version": 1,
            "code_intake_version": "0.1.0",
            "model_name": "credit-risk-pd",
            "version": "1.0.0",
            "generated_at": "2026-06-04T12:00:00+00:00",
            "package_layout": {
                "sas_files":        [{"path": "x", "sha256": "not-hex"}],
                "python_files":     [],
                "test_files":       [],
                "pir_ref":          {"path": "p", "sha256": "d"*64},
                "model_config_ref": {"path": "m", "sha256": "e"*64},
            },
            "validation_summary": {"ran_at": "2026-06-04T12:00:00+00:00", "checks": []},
        })


# --- pir-mapping ---

def test_pir_mapping_minimum_valid():
    validate("pir-mapping", {
        "mapping_version": 1,
        "model_name": "credit-risk-pd",
        "model_version": "1.0.0",
        "inputs": [{"name": "income_band", "type": "float", "source": "customer.income_band"}],
        "outputs": [{"name": "pd_score", "type": "float"}],
    })


def test_pir_mapping_rejects_unknown_type():
    from jsonschema import ValidationError
    with pytest.raises(ValidationError):
        validate("pir-mapping", {
            "mapping_version": 1,
            "model_name": "credit-risk-pd",
            "model_version": "1.0.0",
            "inputs": [{"name": "x", "type": "complex128", "source": "s"}],
            "outputs": [{"name": "y", "type": "float"}],
        })


# --- pipeline-manifest-payload extension ---

def test_pipeline_manifest_payload_accepts_upstream_refs():
    validate("pipeline-manifest-payload", {
        "schema_version": 1,
        "generator_version": "0.1.0",
        "model_name": "credit-risk-pd",
        "version": "1.0.0",
        "tier": "standard",
        "generated_at": "2026-06-04T12:00:00+00:00",
        "artifact_hashes": {
            "statemachine_sha256":  "a"*64, "terraform_sha256":   "b"*64,
            "model_config_sha256":  "c"*64, "registration_sha256": "d"*64,
        },
        "upstream_refs": [
            {"type": "package", "ref": "credit-risk-pd@1.0.0", "digest": "f"*64},
        ],
    })


def test_pipeline_manifest_payload_accepts_no_upstream_refs():
    """The field is optional with default [] — Sprint 2's existing manifest stays valid."""
    validate("pipeline-manifest-payload", {
        "schema_version": 1, "generator_version": "0.1.0",
        "model_name": "credit-risk-pd", "version": "1.0.0",
        "tier": "standard", "generated_at": "2026-06-04T12:00:00+00:00",
        "artifact_hashes": {
            "statemachine_sha256":  "a"*64, "terraform_sha256":   "b"*64,
            "model_config_sha256":  "c"*64, "registration_sha256": "d"*64,
        },
    })


def test_pipeline_manifest_payload_rejects_unknown_upstream_type():
    from jsonschema import ValidationError
    with pytest.raises(ValidationError):
        validate("pipeline-manifest-payload", {
            "schema_version": 1, "generator_version": "0.1.0",
            "model_name": "credit-risk-pd", "version": "1.0.0",
            "tier": "standard", "generated_at": "2026-06-04T12:00:00+00:00",
            "artifact_hashes": {
                "statemachine_sha256":  "a"*64, "terraform_sha256":   "b"*64,
                "model_config_sha256":  "c"*64, "registration_sha256": "d"*64,
            },
            "upstream_refs": [{"type": "dataset", "ref": "x", "digest": "f"*64}],
        })


# --- model-config extension ---

def test_model_config_accepts_optional_upstream_package():
    validate("model-config", {
        "model_name": "credit-risk-pd",
        "version": "1.0.0",
        "execution_tier": "standard",
        "schedule_cadence": "cron(0 6 * * ? *)",
        "input_schema_ref":  "s3://x/in.json",
        "output_schema_ref": "s3://x/out.json",
        "pir_doc_ref":       "s3://x/pir.json",
        "owner_email": "a@absa.africa",
        "accountable_executive": "Jane Exec",
        "sla_seconds": 3600,
        "upstream_package": {"name": "credit-risk-pd", "version": "1.0.0"},
    })


def test_model_config_still_accepts_no_upstream_package():
    """Sprint 2's existing model_config.yaml stays valid."""
    validate("model-config", {
        "model_name": "credit-risk-pd",
        "version": "1.0.0",
        "execution_tier": "standard",
        "schedule_cadence": "cron(0 6 * * ? *)",
        "input_schema_ref":  "s3://x/in.json",
        "output_schema_ref": "s3://x/out.json",
        "pir_doc_ref":       "s3://x/pir.json",
        "owner_email": "a@absa.africa",
        "accountable_executive": "Jane Exec",
        "sla_seconds": 3600,
    })


def test_model_config_rejects_upstream_package_missing_version():
    from jsonschema import ValidationError
    with pytest.raises(ValidationError):
        validate("model-config", {
            "model_name": "credit-risk-pd", "version": "1.0.0",
            "execution_tier": "standard",
            "schedule_cadence": "cron(0 6 * * ? *)",
            "input_schema_ref":  "s3://x/in.json",
            "output_schema_ref": "s3://x/out.json",
            "pir_doc_ref":       "s3://x/pir.json",
            "owner_email": "a@absa.africa",
            "accountable_executive": "Jane Exec",
            "sla_seconds": 3600,
            "upstream_package": {"name": "credit-risk-pd"},  # missing version
        })
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest platform-contracts/tests/test_loader.py -v -k "upstream or pir_mapping or package_manifest"
```

Expected: every new test fails with `KeyError: unknown schema: 'package-manifest-payload'` (or similar) for the two new schemas, and the upstream-related tests fail with `ValidationError` complaining about an unrecognised property `upstream_refs` / `upstream_package` for the modified schemas.

- [ ] **Step 3: Create `package-manifest-payload.schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://contracts.absa-exl.internal/package-manifest-payload/v1.json",
  "title": "PackageManifestPayload",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version", "code_intake_version", "model_name", "version",
    "generated_at", "package_layout", "validation_summary"
  ],
  "properties": {
    "schema_version":      { "type": "integer", "const": 1 },
    "code_intake_version": { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$" },
    "model_name":          { "type": "string", "pattern": "^[a-z][a-z0-9-]{2,63}$" },
    "version":             { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$" },
    "generated_at":        { "type": "string", "format": "date-time" },
    "package_layout": {
      "type": "object",
      "additionalProperties": false,
      "required": ["sas_files", "python_files", "test_files", "pir_ref", "model_config_ref"],
      "properties": {
        "sas_files":         { "type": "array", "items": { "$ref": "#/$defs/file_ref" } },
        "python_files":      { "type": "array", "items": { "$ref": "#/$defs/file_ref" } },
        "test_files":        { "type": "array", "items": { "$ref": "#/$defs/file_ref" } },
        "pir_ref":           { "$ref": "#/$defs/file_ref" },
        "model_config_ref":  { "$ref": "#/$defs/file_ref" }
      }
    },
    "validation_summary": {
      "type": "object",
      "additionalProperties": false,
      "required": ["ran_at", "checks"],
      "properties": {
        "ran_at": { "type": "string", "format": "date-time" },
        "checks": {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["name", "passed", "finding_count"],
            "properties": {
              "name":          { "type": "string" },
              "passed":        { "type": "boolean" },
              "finding_count": { "type": "integer", "minimum": 0 },
              "codes":         { "type": "array", "items": { "type": "string" } }
            }
          }
        }
      }
    }
  },
  "$defs": {
    "file_ref": {
      "type": "object",
      "additionalProperties": false,
      "required": ["path", "sha256"],
      "properties": {
        "path":   { "type": "string", "minLength": 1 },
        "sha256": { "type": "string", "pattern": "^[a-f0-9]{64}$" }
      }
    }
  }
}
```

- [ ] **Step 4: Create `pir-mapping.schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://contracts.absa-exl.internal/pir-mapping/v1.json",
  "title": "PirMapping",
  "type": "object",
  "additionalProperties": false,
  "required": ["mapping_version", "model_name", "model_version", "inputs", "outputs"],
  "properties": {
    "mapping_version": { "type": "integer", "const": 1 },
    "model_name":      { "type": "string", "pattern": "^[a-z][a-z0-9-]{2,63}$" },
    "model_version":   { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$" },
    "inputs": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["name", "type", "source"],
        "properties": {
          "name":        { "type": "string", "pattern": "^[a-z][a-z0-9_]*$" },
          "type":        { "enum": ["string","int","float","bool","date","datetime","decimal"] },
          "source":      { "type": "string", "minLength": 1 },
          "description": { "type": "string" },
          "nullable":    { "type": "boolean", "default": false }
        }
      }
    },
    "outputs": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["name", "type"],
        "properties": {
          "name":        { "type": "string", "pattern": "^[a-z][a-z0-9_]*$" },
          "type":        { "enum": ["string","int","float","bool","date","datetime","decimal"] },
          "description": { "type": "string" }
        }
      }
    },
    "notes": { "type": "string" }
  }
}
```

- [ ] **Step 5: Modify `pipeline-manifest-payload.schema.json` to add `upstream_refs[]`**

Edit `platform-contracts/src/platform_contracts/schemas/pipeline-manifest-payload.schema.json`. Add the property in the `properties` block (after `artifact_hashes`):

```diff
       }
-    }
+    },
+    "upstream_refs": {
+      "type": "array",
+      "default": [],
+      "description": "Chain-of-custody links to upstream manifests. The pipeline's signature covers this array.",
+      "items": {
+        "type": "object",
+        "additionalProperties": false,
+        "required": ["type", "ref", "digest"],
+        "properties": {
+          "type":   { "enum": ["package"] },
+          "ref":    { "type": "string", "minLength": 1 },
+          "digest": { "type": "string", "pattern": "^[a-f0-9]{64}$" }
+        }
+      }
+    }
   }
 }
```

**Do not** add `upstream_refs` to the top-level `required` array — it stays optional with default `[]`.

- [ ] **Step 6: Modify `model-config.schema.json` to add `upstream_package`**

Edit `platform-contracts/src/platform_contracts/schemas/model-config.schema.json`. Add the property after `inference_code_version` (the existing last property):

```diff
     "inference_code_version": { "type": "string", "minLength": 1 }
+    ,"upstream_package": {
+      "type": "object",
+      "additionalProperties": false,
+      "required": ["name", "version"],
+      "description": "Code Intake package this pipeline scores from. When set, the generator embeds an upstream_refs entry in the pipeline manifest.",
+      "properties": {
+        "name":    { "type": "string", "pattern": "^[a-z][a-z0-9-]{2,63}$" },
+        "version": { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$" }
+      }
+    }
   }
 }
```

Again, `upstream_package` stays optional (not in `required`).

- [ ] **Step 7: Modify `regenerate-models.sh` to include the two new schemas**

Edit `platform-contracts/regenerate-models.sh`. Find the `SCHEMAS=(...)` array and add the two new entries:

```diff
 SCHEMAS=(
   "manifest-envelope.schema.json"
   "model-config.schema.json"
+  "package-manifest-payload.schema.json"
   "pipeline-manifest-payload.schema.json"
+  "pir-mapping.schema.json"
   "registry-record.schema.json"
 )
```

Order alphabetically to match the existing convention.

- [ ] **Step 8: Regenerate `models.py`**

```bash
cd platform-contracts
bash regenerate-models.sh
cd ..
```

Expected: script runs `datamodel-codegen` on each schema individually + merges via the AST helper + writes `platform-contracts/src/platform_contracts/models.py`. The new models `PackageManifestPayload`, `PirMapping`, and the extended `PipelineManifestPayload` / `ModelConfig` Pydantic classes appear. No errors.

- [ ] **Step 9: Run the new schema tests**

```bash
uv run pytest platform-contracts/tests/test_loader.py -v
```

Expected: all new tests pass (10 new ones added in Step 1) plus the existing Sprint 1+2+3 tests still pass.

- [ ] **Step 10: Run the full workspace test suite**

```bash
uv run pytest -q
```

Expected: prior totals + 10 new tests, no regressions. Sprint 3's existing 129 + 10 new = 139 passes.

- [ ] **Step 11: Ruff + ruff format + mypy clean**

```bash
uv run ruff check
uv run ruff format --check
uv run mypy platform-contracts/src
```

Expected: All checks passed. Success: no issues found.

- [ ] **Step 12: Commit**

```bash
git add platform-contracts/src/platform_contracts/schemas/package-manifest-payload.schema.json \
        platform-contracts/src/platform_contracts/schemas/pir-mapping.schema.json \
        platform-contracts/src/platform_contracts/schemas/pipeline-manifest-payload.schema.json \
        platform-contracts/src/platform_contracts/schemas/model-config.schema.json \
        platform-contracts/src/platform_contracts/models.py \
        platform-contracts/regenerate-models.sh \
        platform-contracts/tests/test_loader.py
git commit -m "feat(platform-contracts): add package + pir schemas; extend pipeline + model-config

Sprint 4 contract changes (all additive — Sprint 2/3 existing manifests
stay valid):

NEW:
- package-manifest-payload.schema.json: payload Code Intake emits for a
  productized package (schema_version + code_intake_version + model_name
  + version + generated_at + package_layout + validation_summary).
- pir-mapping.schema.json: shape of pir.yaml (mapping_version +
  model_name + model_version + inputs[] + outputs[]).

MODIFIED (both purely additive — fields are optional with safe defaults):
- pipeline-manifest-payload.schema.json: optional upstream_refs[] array
  with {type: 'package', ref, digest}. The pipeline's signature covers
  the array so the cross-link is tamper-evident at the pipeline layer.
- model-config.schema.json: optional upstream_package: {name, version}
  block. The generator (T12) resolves this to the corresponding
  packages/<name>/<version>/manifest.json at gen-time.

Models.py regenerated via the existing platform-contracts/regenerate-
models.sh; CI's existing byte-stability drift gate covers the new
schemas automatically.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Scaffold `code-intake` workspace member + errors + Checker protocol

**Why:** Establish the package shell, dependencies, and the `Checker` protocol every checker implements. Errors and the protocol are tiny shared modules used by every subsequent task.

**Files:**
- Create: `code-intake/pyproject.toml`
- Create: `code-intake/src/code_intake/__init__.py`
- Create: `code-intake/src/code_intake/errors.py`
- Create: `code-intake/src/code_intake/checkers/__init__.py`
- Create: `code-intake/src/code_intake/checkers/base.py`
- Create: `code-intake/tests/__init__.py` (empty file — but see note in Step 6)
- Create: `code-intake/tests/test_smoke.py`
- Create: `code-intake/tests/test_errors.py`
- Create: `code-intake/tests/test_checker_base.py`
- Modify: root `pyproject.toml` (add `code-intake` to workspace members + testpaths)

- [ ] **Step 1: Create `code-intake/pyproject.toml`**

```toml
[project]
name = "code-intake"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "platform-contracts",
    "click>=8.1",
    "jsonschema>=4.21",
    "pyyaml>=6",
]

[project.scripts]
code-intake = "code_intake.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/code_intake"]

[tool.uv.sources]
platform-contracts = { workspace = true }
```

- [ ] **Step 2: Create the empty package init**

`code-intake/src/code_intake/__init__.py`:

```python
"""code-intake — validates productized packages and emits signed manifests."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Write the errors tests**

`code-intake/tests/test_errors.py`:

```python
import pytest

from code_intake.errors import (
    CodeIntakeError,
    PackageConfigError,
    ValidationError,
)


def test_code_intake_error_is_exception():
    assert issubclass(CodeIntakeError, Exception)


def test_validation_error_is_code_intake_error():
    assert issubclass(ValidationError, CodeIntakeError)


def test_package_config_error_is_code_intake_error():
    assert issubclass(PackageConfigError, CodeIntakeError)


def test_raising_validation_error_carries_message():
    with pytest.raises(ValidationError, match="bad package"):
        raise ValidationError("bad package")
```

- [ ] **Step 4: Write the Checker protocol tests**

`code-intake/tests/test_checker_base.py`:

```python
from __future__ import annotations

from pathlib import Path

from code_intake.checkers.base import (
    CheckResult,
    Checker,
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
```

- [ ] **Step 5: Write the smoke test**

`code-intake/tests/test_smoke.py`:

```python
def test_package_imports() -> None:
    import code_intake

    assert code_intake.__version__ == "0.1.0"
```

- [ ] **Step 6: Decide on `code-intake/tests/__init__.py`**

**Important — pytest namespace collision precedent:** Sprint 2 hit a pytest collision when both `pipeline-factory/tests/` and `code-intake/tests/` (would) have `__init__.py` files under `prepend` import mode. The root `pyproject.toml` already sets `addopts = "-q --import-mode=importlib"` which prevents this — so leaving `__init__.py` files in place is safe. **Do NOT create `code-intake/tests/__init__.py`** (the existing workspace members don't have one in their `tests/`). Skip this step — the directory is auto-discovered without it.

- [ ] **Step 7: Run smoke + errors + protocol tests, confirm they fail**

```bash
uv run pytest code-intake/tests -v
```

Expected: `ImportError` / `ModuleNotFoundError` for `code_intake.errors` and `code_intake.checkers.base` (these don't exist yet).

- [ ] **Step 8: Create `errors.py`**

`code-intake/src/code_intake/errors.py`:

```python
"""Error hierarchy for the code-intake package."""

from __future__ import annotations


class CodeIntakeError(Exception):
    """Base class for code-intake failures."""


class ValidationError(CodeIntakeError):
    """Raised when validate() found error-severity findings.

    Carries the list of CheckResults as the first arg if available.
    """


class PackageConfigError(CodeIntakeError):
    """Raised when a package's model_config.yaml doesn't parse or doesn't
    match its schema."""
```

- [ ] **Step 9: Create the `checkers/` sub-package**

`code-intake/src/code_intake/checkers/__init__.py`:

```python
"""Checker implementations + the shared Checker protocol."""
```

- [ ] **Step 10: Create `checkers/base.py`**

`code-intake/src/code_intake/checkers/base.py`:

```python
"""Checker protocol + result dataclasses shared by all checkers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Finding:
    """A single issue detected by a checker.

    `severity` is "error" or "warning". `code` is the checker-prefixed
    identifier (e.g. PY001, SAS003, PIR002) so log lines are self-describing.
    `file` and `line` are optional location hints.
    """

    severity: str
    code: str
    message: str
    file: str | None = None
    line: int | None = None


@dataclass(frozen=True)
class CheckResult:
    """One checker's output.

    `passed` is True iff there are no error-severity findings (warnings are
    OK unless --strict is on). The orchestrator measures `duration_seconds`
    around each call so CI logs surface slow checks.
    """

    checker: str
    passed: bool
    findings: list[Finding] = field(default_factory=list)
    duration_seconds: float = 0.0


class Checker(Protocol):
    """The interface every checker implements.

    Implementations are stateless and idempotent — calling `run` twice on the
    same `package_path` returns equivalent CheckResults (modulo wall-clock
    timestamps). The orchestrator catches exceptions and never propagates
    them up.
    """

    name: str

    def run(self, package_path: Path) -> CheckResult: ...
```

- [ ] **Step 11: Update root workspace**

Edit `pyproject.toml` (root). The line currently reads:

```toml
members = ["platform-contracts", "registry/api", "pipeline-factory", "manifest-signer"]
```

Change to:

```toml
members = ["platform-contracts", "registry/api", "pipeline-factory", "manifest-signer", "code-intake"]
```

And:

```toml
testpaths = ["platform-contracts/tests", "registry/api/tests", "pipeline-factory/tests", "manifest-signer/tests"]
```

Change to:

```toml
testpaths = ["platform-contracts/tests", "registry/api/tests", "pipeline-factory/tests", "manifest-signer/tests", "code-intake/tests"]
```

- [ ] **Step 12: Resolve the workspace**

```bash
uv sync
```

Expected: `uv` resolves the new member and updates `uv.lock`. No errors.

- [ ] **Step 13: Run code-intake tests**

```bash
uv run pytest code-intake/tests -v
```

Expected: 4 errors tests + 4 base tests + 1 smoke = 9 passed.

- [ ] **Step 14: Full workspace pytest**

```bash
uv run pytest -q
```

Expected: T1's 139 + 9 new = 148 passed.

- [ ] **Step 15: Ruff + ruff format + mypy clean**

```bash
uv run ruff check
uv run ruff format --check
uv run mypy code-intake/src
```

Expected: All checks passed. Success: no issues found.

- [ ] **Step 16: Commit**

```bash
git add code-intake/ pyproject.toml uv.lock
git commit -m "chore(code-intake): scaffold uv workspace member + errors + Checker protocol

New uv workspace member with platform-contracts, click, jsonschema,
pyyaml as deps. Shared error hierarchy (CodeIntakeError,
ValidationError, PackageConfigError) and the Checker protocol +
Finding/CheckResult dataclasses every checker implements.

Subsequent tasks fill in the five checkers, the orchestrator, the
manifest builder, the CLI, and the end-to-end test.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `static_python` checker

**Why:** The checker that catches lint, type, and test-discovery issues in the package's Python code. Uses subprocess for ruff / mypy / pytest --collect-only against the package's `python/` dir. First checker so future ones follow the same pattern.

**Files:**
- Create: `code-intake/src/code_intake/checkers/static_python.py`
- Create: `code-intake/tests/fixtures/valid_package/python/score.py`
- Create: `code-intake/tests/fixtures/broken_python/python/score.py`
- Create: `code-intake/tests/test_checker_static_python.py`

- [ ] **Step 1: Write the failing tests**

`code-intake/tests/test_checker_static_python.py`:

```python
from __future__ import annotations

from pathlib import Path

from code_intake.checkers.static_python import StaticPythonChecker

FIXTURES = Path(__file__).parent / "fixtures"


def test_valid_python_passes():
    result = StaticPythonChecker().run(FIXTURES / "valid_package")
    assert result.passed, f"unexpected findings: {result.findings}"
    assert result.checker == "static_python"


def test_broken_python_returns_ruff_finding():
    result = StaticPythonChecker().run(FIXTURES / "broken_python")
    assert not result.passed
    codes = {f.code for f in result.findings}
    assert "PY001" in codes  # ruff


def test_no_python_dir_returns_passed_with_zero_findings():
    """Packages without a python/ dir are valid (pure-SAS packages, future
    use case). The checker is a no-op rather than an error."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        result = StaticPythonChecker().run(Path(td))
        assert result.passed
        assert result.findings == []
```

- [ ] **Step 2: Create fixture `valid_package/python/score.py`**

Create `code-intake/tests/fixtures/valid_package/python/score.py`:

```python
"""Synthetic scoring stub used as the valid fixture."""

from __future__ import annotations


def score(data: dict[str, float]) -> dict[str, float | str]:
    """Score one customer record."""
    income_band = data["income_band"]
    tenure_months = data["tenure_months"]
    delinquencies = data["delinquencies"]

    pd_score = 0.5 * income_band + 0.3 * tenure_months / 12 + 0.2 * delinquencies

    if pd_score > 0.7:
        risk_band = "HIGH"
    elif pd_score > 0.4:
        risk_band = "MEDIUM"
    else:
        risk_band = "LOW"

    return {"pd_score": pd_score, "risk_band": risk_band}
```

Create the empty matching test file so `pytest --collect-only` has something to collect:

`code-intake/tests/fixtures/valid_package/python/tests/test_score.py`:

```python
from score import score


def test_score_returns_dict():
    out = score({"income_band": 1.0, "tenure_months": 12, "delinquencies": 0.0})
    assert "pd_score" in out
    assert "risk_band" in out
```

- [ ] **Step 3: Create fixture `broken_python/python/score.py`**

Create `code-intake/tests/fixtures/broken_python/python/score.py`:

```python
"""Synthetic broken fixture — has an unused import that ruff F401 will flag."""

from __future__ import annotations

import os  # noqa: actually do NOT noqa — we want ruff to flag this
import sys

# Use neither — ruff F401 fires twice.


def score(data: dict[str, float]) -> dict[str, float]:
    return {"pd_score": 0.5}
```

Wait — the comment `# noqa: ...` would actually suppress ruff. Remove that line; we want the unused imports to fire. The actual broken fixture:

```python
"""Synthetic broken fixture — has unused imports that ruff F401 will flag."""

from __future__ import annotations

import os
import sys


def score(data: dict[str, float]) -> dict[str, float]:
    return {"pd_score": 0.5}
```

- [ ] **Step 4: Run tests, confirm they fail**

```bash
uv run pytest code-intake/tests/test_checker_static_python.py -v
```

Expected: `ModuleNotFoundError: No module named 'code_intake.checkers.static_python'`.

- [ ] **Step 5: Implement `static_python.py`**

`code-intake/src/code_intake/checkers/static_python.py`:

```python
"""static_python checker: runs ruff, mypy --strict, and pytest --collect-only
against the package's python/ directory via subprocess."""

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
        tests_dir = python_dir / "tests"
        if tests_dir.is_dir():
            pytest_collect = subprocess.run(
                ["uv", "run", "pytest", "--collect-only", str(tests_dir)],
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
```

- [ ] **Step 6: Run tests, confirm they pass**

```bash
uv run pytest code-intake/tests/test_checker_static_python.py -v
```

Expected: 3 passed.

- [ ] **Step 7: Full workspace pytest + ruff + format + mypy**

```bash
uv run pytest -q
uv run ruff check
uv run ruff format --check
uv run mypy code-intake/src
```

Expected: all green. Workspace total: 148 + 3 = 151 passed.

- [ ] **Step 8: Commit**

```bash
git add code-intake/src/code_intake/checkers/static_python.py \
        code-intake/tests/test_checker_static_python.py \
        code-intake/tests/fixtures/valid_package/ \
        code-intake/tests/fixtures/broken_python/
git commit -m "feat(code-intake): add static_python checker

Subprocess-driven ruff check + mypy --strict + pytest --collect-only
against the package's python/ directory. Returns PY001/PY002/PY003
findings on the respective tool's failure.

Pure-SAS packages (no python/ dir) are valid — the checker is a no-op
rather than an error, supporting the future use case of packages that
ship only SAS code.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `static_sas` checker

**Why:** Structural SAS validation — every `.sas` file exists, is non-empty, has balanced `PROC <X>; ... RUN;` blocks. Real SAS linting is deferred to Phase 3 (needs ABSA's SAS runtime).

**Files:**
- Create: `code-intake/src/code_intake/checkers/static_sas.py`
- Create: `code-intake/tests/fixtures/valid_package/sas/score.sas`
- Create: `code-intake/tests/fixtures/broken_sas/sas/score.sas`
- Create: `code-intake/tests/test_checker_static_sas.py`

- [ ] **Step 1: Write failing tests**

`code-intake/tests/test_checker_static_sas.py`:

```python
from __future__ import annotations

import tempfile
from pathlib import Path

from code_intake.checkers.static_sas import StaticSasChecker

FIXTURES = Path(__file__).parent / "fixtures"


def test_valid_sas_passes():
    result = StaticSasChecker().run(FIXTURES / "valid_package")
    assert result.passed, f"unexpected findings: {result.findings}"
    assert result.checker == "static_sas"


def test_broken_sas_unbalanced_proc_run():
    result = StaticSasChecker().run(FIXTURES / "broken_sas")
    assert not result.passed
    codes = {f.code for f in result.findings}
    assert "SAS003" in codes  # PROC without matching RUN


def test_empty_sas_file_returns_sas002():
    with tempfile.TemporaryDirectory() as td:
        sas_dir = Path(td) / "sas"
        sas_dir.mkdir()
        (sas_dir / "empty.sas").write_text("")
        result = StaticSasChecker().run(Path(td))
        assert not result.passed
        codes = {f.code for f in result.findings}
        assert "SAS002" in codes


def test_no_sas_dir_returns_passed():
    """Packages without a sas/ dir are valid (pure-Python packages)."""
    with tempfile.TemporaryDirectory() as td:
        result = StaticSasChecker().run(Path(td))
        assert result.passed
        assert result.findings == []
```

- [ ] **Step 2: Create fixture `valid_package/sas/score.sas`**

```sas
/* Synthetic SAS scoring code — valid fixture with balanced PROC/RUN. */
DATA scored;
  SET input;
  pd_score = 0.5 * income_band + 0.3 * tenure_months / 12 + 0.2 * delinquencies;
  IF pd_score > 0.7 THEN risk_band = 'HIGH';
  ELSE IF pd_score > 0.4 THEN risk_band = 'MEDIUM';
  ELSE risk_band = 'LOW';
RUN;

PROC PRINT data=scored;
RUN;
```

- [ ] **Step 3: Create fixture `broken_sas/sas/score.sas`**

```sas
/* Synthetic broken fixture — PROC FREQ has no matching RUN. */
DATA scored;
  SET input;
  pd_score = 0.5;
RUN;

PROC FREQ data=scored;
  TABLES risk_band;
/* missing RUN; */
```

- [ ] **Step 4: Run tests, confirm they fail**

```bash
uv run pytest code-intake/tests/test_checker_static_sas.py -v
```

Expected: `ModuleNotFoundError: No module named 'code_intake.checkers.static_sas'`.

- [ ] **Step 5: Implement `static_sas.py`**

`code-intake/src/code_intake/checkers/static_sas.py`:

```python
"""static_sas checker: structural checks on .sas files.

Sprint 4 ships structural-only validation: file existence, non-emptiness,
balanced PROC/RUN blocks. Real SAS linting (parsing PROC contents, type
checking variable references, etc.) is deferred to Phase 3 when ABSA's
SAS runtime is in scope.
"""

from __future__ import annotations

import re
from pathlib import Path

from .base import CheckResult, Finding

# Match `PROC <NAME>` (case-insensitive). The DATA step doesn't take a RUN
# in some SAS conventions but standardly does; we treat both DATA and PROC
# as needing a matching RUN.
_OPEN_RE = re.compile(r"^\s*(DATA|PROC)\b", re.IGNORECASE | re.MULTILINE)
_RUN_RE = re.compile(r"^\s*RUN\s*;", re.IGNORECASE | re.MULTILINE)


class StaticSasChecker:
    name = "static_sas"

    def run(self, package_path: Path) -> CheckResult:
        sas_dir = package_path / "sas"
        if not sas_dir.is_dir():
            return CheckResult(checker=self.name, passed=True)

        findings: list[Finding] = []

        for sas_file in sorted(sas_dir.rglob("*.sas")):
            content = sas_file.read_text(encoding="utf-8")
            rel = str(sas_file.relative_to(package_path))

            if not content.strip():
                findings.append(
                    Finding(severity="error", code="SAS002",
                            message=f"empty SAS file: {rel}", file=rel)
                )
                continue

            opens = len(_OPEN_RE.findall(content))
            runs = len(_RUN_RE.findall(content))
            if opens != runs:
                findings.append(
                    Finding(
                        severity="error", code="SAS003",
                        message=(
                            f"unbalanced PROC/RUN in {rel}: "
                            f"{opens} DATA/PROC blocks vs {runs} RUN statements"
                        ),
                        file=rel,
                    )
                )

        # SAS001 (missing required file) is intentionally not checked here —
        # the schema checker validates the declared file_refs against on-disk
        # presence. static_sas only sees what's actually in sas/.

        passed = not any(f.severity == "error" for f in findings)
        return CheckResult(checker=self.name, passed=passed, findings=findings)
```

- [ ] **Step 6: Run tests, confirm they pass**

```bash
uv run pytest code-intake/tests/test_checker_static_sas.py -v
```

Expected: 4 passed.

- [ ] **Step 7: Full workspace pytest + ruff + format + mypy**

```bash
uv run pytest -q
uv run ruff check
uv run ruff format --check
uv run mypy code-intake/src
```

Expected: all green. Workspace total: 151 + 4 = 155 passed.

- [ ] **Step 8: Commit**

```bash
git add code-intake/src/code_intake/checkers/static_sas.py \
        code-intake/tests/test_checker_static_sas.py \
        code-intake/tests/fixtures/valid_package/sas/ \
        code-intake/tests/fixtures/broken_sas/sas/
git commit -m "feat(code-intake): add static_sas checker

Structural-only SAS validation: every .sas file exists, is non-empty,
has balanced DATA/PROC open with matching RUN statements. Real SAS
linting (PROC body parsing, type checking) is Phase 3 territory — needs
ABSA's SAS runtime. Documented in ADR-0010 (Task 16).

Findings:
- SAS002: empty .sas file
- SAS003: unbalanced PROC/RUN

(SAS001 — missing required file — is left for the schema checker to
catch via the model_config.yaml's file_refs.)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: `schema` checker

**Why:** Validates the package's `model_config.yaml` against the new `package-manifest-payload.schema.json` and asserts that every artefact reference in the config matches its on-disk SHA-256.

**Note on schema reuse:** The package's `model_config.yaml` lives at `packages/<name>/<version>/model_config.yaml` and describes the package's structure. **For Sprint 4 we validate it against `package-manifest-payload.schema.json` directly** — the package-level config is structurally identical to the manifest payload (it declares `package_layout` and is what `validation_summary` is appended to). The Code Intake-generated `manifest.json` later wraps this exact structure into a signed envelope. This keeps one schema as the source of truth.

**Files:**
- Create: `code-intake/src/code_intake/checkers/schema.py`
- Create: `code-intake/tests/fixtures/valid_package/model_config.yaml`
- Create: `code-intake/tests/fixtures/broken_schema/python/score.py`
- Create: `code-intake/tests/fixtures/broken_schema/model_config.yaml` (missing required field)
- Create: `code-intake/tests/test_checker_schema.py`

- [ ] **Step 1: Write failing tests**

`code-intake/tests/test_checker_schema.py`:

```python
from __future__ import annotations

from pathlib import Path

from code_intake.checkers.schema import SchemaChecker

FIXTURES = Path(__file__).parent / "fixtures"


def test_valid_schema_passes():
    result = SchemaChecker().run(FIXTURES / "valid_package")
    assert result.passed, f"unexpected findings: {result.findings}"
    assert result.checker == "schema"


def test_missing_required_field_returns_sch001():
    result = SchemaChecker().run(FIXTURES / "broken_schema")
    assert not result.passed
    codes = {f.code for f in result.findings}
    assert "SCH001" in codes


def test_missing_model_config_returns_sch001():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        result = SchemaChecker().run(Path(td))
        assert not result.passed
        codes = {f.code for f in result.findings}
        assert "SCH001" in codes
```

(Hash-mismatch tests SCH002/SCH003 are exercised end-to-end in Task 14; for the per-checker tests, the schema-validation path covers the broken_schema fixture.)

- [ ] **Step 2: Create `valid_package/model_config.yaml`**

```yaml
schema_version: 1
code_intake_version: "0.1.0"
model_name: valid-package
version: 1.0.0
generated_at: "2026-06-04T00:00:00+00:00"

package_layout:
  sas_files:
    - { path: "sas/score.sas", sha256: "0000000000000000000000000000000000000000000000000000000000000000" }
  python_files:
    - { path: "python/score.py", sha256: "0000000000000000000000000000000000000000000000000000000000000000" }
  test_files:
    - { path: "python/tests/test_score.py", sha256: "0000000000000000000000000000000000000000000000000000000000000000" }
  pir_ref:
    path: "pir.yaml"
    sha256: "0000000000000000000000000000000000000000000000000000000000000000"
  model_config_ref:
    path: "model_config.yaml"
    sha256: "0000000000000000000000000000000000000000000000000000000000000000"

validation_summary:
  ran_at: "2026-06-04T00:00:00+00:00"
  checks: []
```

**Note:** the sha256 placeholders here are intentionally all-zeros — the SchemaChecker's job is only to validate the *config shape*, not to verify the hashes match disk content. The hash-mismatch check (SCH002/SCH003) is enforced as part of the orchestrator's end-to-end flow (Task 8 verifies). The per-checker tests for valid_package skip the hash assertion by using placeholders.

- [ ] **Step 3: Create `broken_schema/model_config.yaml` and `broken_schema/python/score.py`**

`code-intake/tests/fixtures/broken_schema/python/score.py`:

```python
"""Minimal Python so the package directory exists; the broken_schema
fixture exercises the SchemaChecker via model_config.yaml only."""

from __future__ import annotations


def score(data: dict[str, float]) -> dict[str, float]:
    return {"pd_score": 0.0}
```

`code-intake/tests/fixtures/broken_schema/model_config.yaml` — missing the required `validation_summary` field:

```yaml
schema_version: 1
code_intake_version: "0.1.0"
model_name: broken-schema
version: 1.0.0
generated_at: "2026-06-04T00:00:00+00:00"

package_layout:
  sas_files: []
  python_files:
    - { path: "python/score.py", sha256: "0000000000000000000000000000000000000000000000000000000000000000" }
  test_files: []
  pir_ref:
    path: "pir.yaml"
    sha256: "0000000000000000000000000000000000000000000000000000000000000000"
  model_config_ref:
    path: "model_config.yaml"
    sha256: "0000000000000000000000000000000000000000000000000000000000000000"

# validation_summary intentionally missing — schema rejects this.
```

- [ ] **Step 4: Run tests, confirm they fail**

```bash
uv run pytest code-intake/tests/test_checker_schema.py -v
```

Expected: `ModuleNotFoundError: No module named 'code_intake.checkers.schema'`.

- [ ] **Step 5: Implement `schema.py`**

`code-intake/src/code_intake/checkers/schema.py`:

```python
"""schema checker: validates model_config.yaml against
package-manifest-payload.schema.json. Hash-cross-check is performed as part
of the orchestrator's full validation when a manifest exists."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml
from jsonschema import ValidationError
from platform_contracts.loader import validate as validate_contract

from .base import CheckResult, Finding


class SchemaChecker:
    name = "schema"

    def run(self, package_path: Path) -> CheckResult:
        config_path = package_path / "model_config.yaml"
        findings: list[Finding] = []

        if not config_path.is_file():
            findings.append(
                Finding(
                    severity="error",
                    code="SCH001",
                    message=f"missing model_config.yaml at {config_path}",
                    file="model_config.yaml",
                )
            )
            return CheckResult(checker=self.name, passed=False, findings=findings)

        try:
            parsed = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            findings.append(
                Finding(
                    severity="error",
                    code="SCH001",
                    message=f"model_config.yaml is not valid YAML: {e}",
                    file="model_config.yaml",
                )
            )
            return CheckResult(checker=self.name, passed=False, findings=findings)

        if not isinstance(parsed, dict):
            findings.append(
                Finding(
                    severity="error",
                    code="SCH001",
                    message="model_config.yaml top-level must be a mapping",
                    file="model_config.yaml",
                )
            )
            return CheckResult(checker=self.name, passed=False, findings=findings)

        try:
            validate_contract("package-manifest-payload", cast(dict[str, Any], parsed))
        except ValidationError as e:
            findings.append(
                Finding(
                    severity="error",
                    code="SCH001",
                    message=f"model_config.yaml fails schema validation: {e.message}",
                    file="model_config.yaml",
                )
            )
            return CheckResult(checker=self.name, passed=False, findings=findings)

        return CheckResult(checker=self.name, passed=True, findings=[])
```

**Note on SCH002/SCH003 deferral:** SCH002 (missing artifact file referenced in config) and SCH003 (artifact hash mismatch) need the on-disk hashes computed at orchestration time. The SchemaChecker only validates the config's *shape*; the orchestrator (Task 8) folds in the on-disk hash check as a separate concern. **For Sprint 4 this is split between schema (shape) and manifest builder (hashes computed fresh at gen-time)** — bypassing the SCH002/SCH003 codes in the per-checker test path. The end-to-end test in Task 14 verifies the hashes are actually correct in the generated manifest.

- [ ] **Step 6: Run tests, confirm they pass**

```bash
uv run pytest code-intake/tests/test_checker_schema.py -v
```

Expected: 3 passed.

- [ ] **Step 7: Full workspace pytest + ruff + format + mypy**

```bash
uv run pytest -q
uv run ruff check
uv run ruff format --check
uv run mypy code-intake/src
```

Expected: all green. Workspace total: 155 + 3 = 158 passed.

- [ ] **Step 8: Commit**

```bash
git add code-intake/src/code_intake/checkers/schema.py \
        code-intake/tests/test_checker_schema.py \
        code-intake/tests/fixtures/valid_package/model_config.yaml \
        code-intake/tests/fixtures/broken_schema/
git commit -m "feat(code-intake): add schema checker

Validates the package's model_config.yaml against
package-manifest-payload.schema.json (from T1). Returns SCH001 on
missing file, invalid YAML, non-mapping root, or schema validation
failure.

SCH002/SCH003 (artifact hash mismatch) are enforced at manifest-build
time rather than per-checker because the on-disk hash needs to be
computed fresh; the orchestrator wires the two concerns together.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: `tests` checker

**Why:** Actually runs `pytest` against the package's `python/tests/` directory. Catches "the package's own code is broken" in a way `pytest --collect-only` (used by static_python) does not.

**Files:**
- Create: `code-intake/src/code_intake/checkers/tests.py`
- Create: `code-intake/tests/fixtures/valid_package/python/tests/test_score.py` (already created in T3 — verify)
- Create: `code-intake/tests/fixtures/broken_tests/python/score.py`
- Create: `code-intake/tests/fixtures/broken_tests/python/tests/test_score.py` (one `assert False`)
- Create: `code-intake/tests/test_checker_tests.py`

- [ ] **Step 1: Write failing tests**

`code-intake/tests/test_checker_tests.py`:

```python
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
```

- [ ] **Step 2: Create `broken_tests/` fixture**

`code-intake/tests/fixtures/broken_tests/python/score.py`:

```python
"""Synthetic stub used by the broken_tests fixture."""

from __future__ import annotations


def score(data: dict[str, float]) -> dict[str, float]:
    return {"pd_score": 0.5}
```

`code-intake/tests/fixtures/broken_tests/python/tests/test_score.py`:

```python
from score import score


def test_score_passes():
    assert score({"x": 1}) == {"pd_score": 0.5}


def test_score_intentionally_fails():
    # This assertion is wrong on purpose — exercises TST002.
    assert score({"x": 1}) == {"pd_score": 999.9}
```

- [ ] **Step 3: Run tests, confirm they fail**

```bash
uv run pytest code-intake/tests/test_checker_tests.py -v
```

Expected: `ModuleNotFoundError: No module named 'code_intake.checkers.tests'`.

- [ ] **Step 4: Implement `tests.py`**

`code-intake/src/code_intake/checkers/tests.py`:

```python
"""tests checker: actually invokes pytest against the package's
python/tests/ directory."""

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

        result = subprocess.run(
            ["uv", "run", "pytest", str(tests_dir), "-q"],
            capture_output=True,
            text=True,
        )

        # pytest exit codes:
        #   0 = all tests passed
        #   1 = tests collected but ≥1 failed
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
                    message=f"≥1 test failed:\n{result.stdout}".strip(),
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
```

- [ ] **Step 5: Run tests, confirm they pass**

```bash
uv run pytest code-intake/tests/test_checker_tests.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Full workspace pytest + ruff + format + mypy**

```bash
uv run pytest -q
uv run ruff check
uv run ruff format --check
uv run mypy code-intake/src
```

Expected: all green. Workspace total: 158 + 3 = 161 passed.

- [ ] **Step 7: Commit**

```bash
git add code-intake/src/code_intake/checkers/tests.py \
        code-intake/tests/test_checker_tests.py \
        code-intake/tests/fixtures/broken_tests/
git commit -m "feat(code-intake): add tests checker

Subprocesses pytest against the package's python/tests/ directory.

Exit code mapping:
  0 -> passed
  1 -> TST002 (≥1 test failed)
  2 -> TST001 (collection failed)
  5 -> passed (no tests is OK — supports placeholder packages)
  other -> TST001 (unexpected exit code, full output in message)

Packages without python/tests/ are valid (no-op).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: `pir` checker

**Why:** Validates the package's `pir.yaml` against `pir-mapping.schema.json`, then parses the package's Python source for column references (`data["col"]` and `data.col`) and asserts every referenced column is in `pir.inputs[]`.

**Files:**
- Create: `code-intake/src/code_intake/checkers/pir.py`
- Create: `code-intake/tests/fixtures/valid_package/pir.yaml`
- Create: `code-intake/tests/fixtures/broken_pir/python/score.py`
- Create: `code-intake/tests/fixtures/broken_pir/pir.yaml` (missing one column referenced by score.py)
- Create: `code-intake/tests/test_checker_pir.py`

- [ ] **Step 1: Write failing tests**

`code-intake/tests/test_checker_pir.py`:

```python
from __future__ import annotations

from pathlib import Path

from code_intake.checkers.pir import PirChecker, _extract_column_references

FIXTURES = Path(__file__).parent / "fixtures"


def test_valid_pir_passes():
    result = PirChecker().run(FIXTURES / "valid_package")
    assert result.passed, f"unexpected findings: {result.findings}"
    assert result.checker == "pir"


def test_broken_pir_unmapped_column_returns_pir002():
    result = PirChecker().run(FIXTURES / "broken_pir")
    assert not result.passed
    codes = {f.code for f in result.findings}
    assert "PIR002" in codes


def test_extract_columns_subscript():
    cols = _extract_column_references(
        'def f(data):\n    return data["a"] + data["b"]\n'
    )
    assert cols == {"a", "b"}


def test_extract_columns_attribute():
    cols = _extract_column_references(
        "def f(data):\n    return data.x + data.y\n"
    )
    assert cols == {"x", "y"}


def test_extract_columns_mixed():
    cols = _extract_column_references(
        'def f(data):\n    return data["a"] + data.b\n'
    )
    assert cols == {"a", "b"}


def test_extract_columns_ignores_non_data_subscripts():
    """data["x"] is extracted; other["x"] is not."""
    cols = _extract_column_references(
        'def f(data, other):\n    return data["a"] + other["b"]\n'
    )
    assert cols == {"a"}
```

- [ ] **Step 2: Create `valid_package/pir.yaml`**

```yaml
mapping_version: 1
model_name: valid-package
model_version: 1.0.0

inputs:
  - { name: income_band,   type: float, source: customer.income_band }
  - { name: tenure_months, type: int,   source: customer.tenure_months }
  - { name: delinquencies, type: float, source: customer.delinquencies_12m, nullable: true }

outputs:
  - { name: pd_score, type: float }
  - { name: risk_band, type: string }
```

This matches the column references in `valid_package/python/score.py` (created in T3): `data["income_band"]`, `data["tenure_months"]`, `data["delinquencies"]`.

- [ ] **Step 3: Create `broken_pir/` fixture**

`code-intake/tests/fixtures/broken_pir/python/score.py`:

```python
"""Synthetic — references tenure_months but PIR omits it."""

from __future__ import annotations


def score(data: dict[str, float]) -> dict[str, float]:
    income_band = data["income_band"]
    tenure_months = data["tenure_months"]   # this is missing from PIR
    return {"pd_score": income_band + tenure_months / 12}
```

`code-intake/tests/fixtures/broken_pir/pir.yaml`:

```yaml
mapping_version: 1
model_name: broken-pir
model_version: 1.0.0

inputs:
  - { name: income_band, type: float, source: customer.income_band }
  # tenure_months intentionally missing — score.py references it

outputs:
  - { name: pd_score, type: float }
```

- [ ] **Step 4: Run tests, confirm they fail**

```bash
uv run pytest code-intake/tests/test_checker_pir.py -v
```

Expected: `ModuleNotFoundError: No module named 'code_intake.checkers.pir'`.

- [ ] **Step 5: Implement `pir.py`**

`code-intake/src/code_intake/checkers/pir.py`:

```python
"""pir checker: validates pir.yaml against pir-mapping.schema.json and
cross-checks that every column referenced by the Python code is mapped.

Column extraction uses stdlib `ast` to find:
  - data["col_name"]    (Subscript on Name `data`)
  - data.col_name       (Attribute on Name `data`)
within any function. Crude but sufficient for the Sprint-4 worked
example. Phase-3 packages can opt into stricter parsing via a future
PIR config flag.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, cast

import yaml
from jsonschema import ValidationError
from platform_contracts.loader import validate as validate_contract

from .base import CheckResult, Finding


def _extract_column_references(source: str) -> set[str]:
    """Parse Python source and return the set of `data["..."]` / `data....`
    column references. Returns an empty set if the source doesn't parse."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    columns: set[str] = set()
    for node in ast.walk(tree):
        # data["col_name"]  (Subscript)
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            if node.value.id == "data" and isinstance(node.slice, ast.Constant):
                if isinstance(node.slice.value, str):
                    columns.add(node.slice.value)
        # data.col_name     (Attribute)
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == "data":
                columns.add(node.attr)
    return columns


class PirChecker:
    name = "pir"

    def run(self, package_path: Path) -> CheckResult:
        pir_path = package_path / "pir.yaml"
        findings: list[Finding] = []

        if not pir_path.is_file():
            findings.append(
                Finding(
                    severity="error",
                    code="PIR001",
                    message=f"missing pir.yaml at {pir_path}",
                    file="pir.yaml",
                )
            )
            return CheckResult(checker=self.name, passed=False, findings=findings)

        try:
            pir_data = yaml.safe_load(pir_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            findings.append(
                Finding(
                    severity="error",
                    code="PIR001",
                    message=f"pir.yaml is not valid YAML: {e}",
                    file="pir.yaml",
                )
            )
            return CheckResult(checker=self.name, passed=False, findings=findings)

        if not isinstance(pir_data, dict):
            findings.append(
                Finding(
                    severity="error",
                    code="PIR001",
                    message="pir.yaml top-level must be a mapping",
                    file="pir.yaml",
                )
            )
            return CheckResult(checker=self.name, passed=False, findings=findings)

        try:
            validate_contract("pir-mapping", cast(dict[str, Any], pir_data))
        except ValidationError as e:
            findings.append(
                Finding(
                    severity="error",
                    code="PIR001",
                    message=f"pir.yaml fails schema validation: {e.message}",
                    file="pir.yaml",
                )
            )
            return CheckResult(checker=self.name, passed=False, findings=findings)

        # Cross-check: every column referenced by Python sources must be in inputs[]
        pir_inputs = {item["name"] for item in pir_data.get("inputs", [])}
        python_dir = package_path / "python"
        if python_dir.is_dir():
            referenced: set[str] = set()
            for py_file in sorted(python_dir.rglob("*.py")):
                # Skip tests dir — pytest references won't be PIR columns.
                if "tests" in py_file.parts:
                    continue
                referenced |= _extract_column_references(
                    py_file.read_text(encoding="utf-8")
                )

            unmapped = referenced - pir_inputs
            for col in sorted(unmapped):
                findings.append(
                    Finding(
                        severity="error",
                        code="PIR002",
                        message=f"column {col!r} referenced by Python code but not in pir.inputs[]",
                        file="pir.yaml",
                    )
                )

        passed = not any(f.severity == "error" for f in findings)
        return CheckResult(checker=self.name, passed=passed, findings=findings)
```

- [ ] **Step 6: Run tests, confirm they pass**

```bash
uv run pytest code-intake/tests/test_checker_pir.py -v
```

Expected: 6 passed.

- [ ] **Step 7: Full workspace pytest + ruff + format + mypy**

```bash
uv run pytest -q
uv run ruff check
uv run ruff format --check
uv run mypy code-intake/src
```

Expected: all green. Workspace total: 161 + 6 = 167 passed.

- [ ] **Step 8: Commit**

```bash
git add code-intake/src/code_intake/checkers/pir.py \
        code-intake/tests/test_checker_pir.py \
        code-intake/tests/fixtures/valid_package/pir.yaml \
        code-intake/tests/fixtures/broken_pir/
git commit -m "feat(code-intake): add pir checker

Validates pir.yaml against pir-mapping.schema.json (PIR001), then uses
stdlib ast to extract data['col'] and data.col references from non-test
Python files and asserts every referenced column is in pir.inputs[]
(PIR002).

The AST-based extractor is intentionally crude:
- Only Name('data') subscript/attribute patterns are detected
- Constant string subscripts only (no f-strings, no aliases)
- Test-dir Python is skipped

Phase 3 can opt into stricter extraction via a future PIR config flag.
Documented in ADR-0010.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Orchestrator

**Why:** Wires the five checkers, collects all findings, never short-circuits, and never propagates exceptions (a buggy checker becomes a single error-severity finding `<CHECKER>999`).

**Files:**
- Create: `code-intake/src/code_intake/orchestrator.py`
- Create: `code-intake/tests/test_orchestrator.py`

- [ ] **Step 1: Write failing tests**

`code-intake/tests/test_orchestrator.py`:

```python
from __future__ import annotations

from pathlib import Path

from code_intake.checkers.base import CheckResult, Finding
from code_intake.orchestrator import validate

FIXTURES = Path(__file__).parent / "fixtures"


def test_valid_package_all_checkers_pass():
    results = validate(FIXTURES / "valid_package")
    assert len(results) == 5
    assert {r.checker for r in results} == {
        "static_python", "static_sas", "schema", "tests", "pir"
    }
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
            "def test_pass():\n    assert True\n"
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
```

- [ ] **Step 2: Run tests, confirm they fail**

```bash
uv run pytest code-intake/tests/test_orchestrator.py -v
```

Expected: `ModuleNotFoundError: No module named 'code_intake.orchestrator'`.

- [ ] **Step 3: Implement `orchestrator.py`**

`code-intake/src/code_intake/orchestrator.py`:

```python
"""orchestrator: runs every checker; collects all findings; never crashes."""

from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path

from .checkers.base import CheckResult, Finding
from .checkers.pir import PirChecker
from .checkers.schema import SchemaChecker
from .checkers.static_python import StaticPythonChecker
from .checkers.static_sas import StaticSasChecker
from .checkers.tests import TestsChecker


def _build_checkers() -> list:
    """Build the checker list at call-time so monkey-patching in tests
    affects future invocations."""
    from .checkers import pir, schema, static_python, static_sas, tests as tests_mod
    return [
        static_python.StaticPythonChecker(),
        static_sas.StaticSasChecker(),
        schema.SchemaChecker(),
        tests_mod.TestsChecker(),
        pir.PirChecker(),
    ]


def validate(package_path: Path, *, strict: bool = False) -> list[CheckResult]:
    """Run every checker; never short-circuit; never raise.

    `strict` flips warning-severity findings into errors. Default False.

    Returns the list of all CheckResults in execution order.

    A checker that raises is converted to a single error-severity Finding
    with code `<CHECKER>999` so the orchestrator never propagates a crash.
    """
    results: list[CheckResult] = []
    for checker in _build_checkers():
        start = time.monotonic()
        try:
            result = checker.run(package_path)
        except Exception as e:
            result = CheckResult(
                checker=checker.name,
                passed=False,
                findings=[
                    Finding(
                        severity="error",
                        code=f"{checker.name.upper()}999",
                        message=f"checker crashed: {e!r}",
                    )
                ],
            )

        if strict:
            # Flip warning-severity findings into errors.
            elevated = [
                replace(f, severity="error") if f.severity == "warning" else f
                for f in result.findings
            ]
            still_passed = not any(f.severity == "error" for f in elevated)
            result = replace(result, findings=elevated, passed=still_passed)

        result = replace(result, duration_seconds=time.monotonic() - start)
        results.append(result)

    return results
```

- [ ] **Step 4: Run tests, confirm they pass**

```bash
uv run pytest code-intake/tests/test_orchestrator.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Full workspace pytest + ruff + format + mypy**

```bash
uv run pytest -q
uv run ruff check
uv run ruff format --check
uv run mypy code-intake/src
```

Expected: all green. Workspace total: 167 + 4 = 171 passed.

- [ ] **Step 6: Commit**

```bash
git add code-intake/src/code_intake/orchestrator.py \
        code-intake/tests/test_orchestrator.py
git commit -m "feat(code-intake): add orchestrator

Runs all five checkers in fixed order, collects every CheckResult, never
short-circuits. A checker that raises is wrapped in a single error
severity Finding with code <CHECKER>999 — never propagates a stack
trace. Records per-checker timing.

--strict flag flips warning-severity findings into errors.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: `package_config` loader + `manifest` builder

**Why:** The CLI's `generate-manifest` subcommand needs (1) a loader for the package's `model_config.yaml` and (2) a builder that wraps the config + checker summary into an UNSIGNED envelope ready for Sprint 3's signer.

**Files:**
- Create: `code-intake/src/code_intake/package_config.py`
- Create: `code-intake/src/code_intake/manifest.py`
- Create: `code-intake/tests/test_package_config.py`
- Create: `code-intake/tests/test_manifest.py`

- [ ] **Step 1: Write failing tests**

`code-intake/tests/test_package_config.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from code_intake.errors import PackageConfigError
from code_intake.package_config import load_package_config

FIXTURES = Path(__file__).parent / "fixtures"


def test_loads_valid_package_config():
    cfg = load_package_config(FIXTURES / "valid_package" / "model_config.yaml")
    assert cfg["model_name"] == "valid-package"
    assert cfg["version"] == "1.0.0"


def test_rejects_invalid_schema():
    with pytest.raises(PackageConfigError, match="schema"):
        load_package_config(FIXTURES / "broken_schema" / "model_config.yaml")


def test_rejects_missing_file(tmp_path):
    with pytest.raises(PackageConfigError, match="missing"):
        load_package_config(tmp_path / "model_config.yaml")
```

`code-intake/tests/test_manifest.py`:

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from code_intake.checkers.base import CheckResult, Finding
from code_intake.manifest import build_package_envelope, build_package_payload
from platform_contracts.canonical import canonical_json
from platform_contracts.loader import validate as validate_contract

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_results() -> list[CheckResult]:
    return [
        CheckResult(checker="static_python", passed=True, findings=[]),
        CheckResult(checker="static_sas", passed=True, findings=[]),
        CheckResult(checker="schema", passed=True, findings=[]),
        CheckResult(
            checker="tests",
            passed=False,
            findings=[Finding(severity="error", code="TST002", message="boom")],
        ),
        CheckResult(checker="pir", passed=True, findings=[]),
    ]


def test_build_payload_passes_schema(sample_results):
    payload = build_package_payload(
        package_path=FIXTURES / "valid_package",
        results=sample_results,
        generated_at="2026-06-04T00:00:00+00:00",
    )
    validate_contract("package-manifest-payload", payload)


def test_build_payload_records_validation_summary(sample_results):
    payload = build_package_payload(
        package_path=FIXTURES / "valid_package",
        results=sample_results,
        generated_at="2026-06-04T00:00:00+00:00",
    )
    summary = payload["validation_summary"]
    by_name = {c["name"]: c for c in summary["checks"]}
    assert by_name["static_python"]["passed"] is True
    assert by_name["tests"]["passed"] is False
    assert by_name["tests"]["finding_count"] == 1
    assert "TST002" in by_name["tests"]["codes"]


def test_build_payload_computes_file_hashes_from_disk(sample_results):
    payload = build_package_payload(
        package_path=FIXTURES / "valid_package",
        results=sample_results,
        generated_at="2026-06-04T00:00:00+00:00",
    )
    layout = payload["package_layout"]
    # python_files[0] is python/score.py — verify its hash matches on-disk
    score_path = FIXTURES / "valid_package" / "python" / "score.py"
    expected = hashlib.sha256(score_path.read_bytes()).hexdigest()
    python_files = layout["python_files"]
    assert any(f["sha256"] == expected for f in python_files), (
        f"score.py hash {expected} not found in {[f['sha256'] for f in python_files]}"
    )


def test_build_envelope_wraps_with_unsigned_sentinel(sample_results):
    payload = build_package_payload(
        package_path=FIXTURES / "valid_package",
        results=sample_results,
        generated_at="2026-06-04T00:00:00+00:00",
    )
    envelope = build_package_envelope(
        payload=payload,
        subject_ref="packages/valid-package/1.0.0/",
        signed_at="2026-06-04T00:00:00+00:00",
    )
    assert envelope["signature"] == "UNSIGNED"
    assert envelope["subject_type"] == "package"
    assert envelope["digest"] == hashlib.sha256(canonical_json(payload)).hexdigest()


def test_build_envelope_preserves_existing_timestamps(tmp_path, sample_results):
    """Re-rendering reads the existing manifest's generated_at/signed_at
    so the drift gate is byte-stable across re-runs."""
    # First build
    payload_a = build_package_payload(
        package_path=FIXTURES / "valid_package",
        results=sample_results,
        generated_at="2026-06-04T00:00:00+00:00",
    )
    envelope_a = build_package_envelope(
        payload=payload_a,
        subject_ref="packages/valid-package/1.0.0/",
        signed_at="2026-06-04T00:00:00+00:00",
    )
    # Write to disk
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(envelope_a, indent=2, sort_keys=True))

    # Second build with same fixture; without explicit timestamps it should
    # generate a fresh one (different from envelope_a's). With explicit
    # timestamps reusing the existing values, the bytes match.
    payload_b = build_package_payload(
        package_path=FIXTURES / "valid_package",
        results=sample_results,
        generated_at=payload_a["generated_at"],
    )
    envelope_b = build_package_envelope(
        payload=payload_b,
        subject_ref="packages/valid-package/1.0.0/",
        signed_at=envelope_a["signed_at"],
    )
    assert canonical_json(envelope_a) == canonical_json(envelope_b)
```

- [ ] **Step 2: Run tests, confirm they fail**

```bash
uv run pytest code-intake/tests/test_package_config.py code-intake/tests/test_manifest.py -v
```

Expected: `ModuleNotFoundError: No module named 'code_intake.package_config'` and `code_intake.manifest`.

- [ ] **Step 3: Implement `package_config.py`**

`code-intake/src/code_intake/package_config.py`:

```python
"""Loader for the package's model_config.yaml (validates against
package-manifest-payload.schema.json)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml
from jsonschema import ValidationError
from platform_contracts.loader import validate as validate_contract

from .errors import PackageConfigError


def load_package_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PackageConfigError(f"missing model_config.yaml at {path}")

    try:
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise PackageConfigError(f"model_config.yaml is not valid YAML: {e}") from e

    if not isinstance(parsed, dict):
        raise PackageConfigError("model_config.yaml top-level must be a mapping")

    try:
        validate_contract("package-manifest-payload", cast(dict[str, Any], parsed))
    except ValidationError as e:
        raise PackageConfigError(
            f"model_config.yaml fails schema validation: {e.message}"
        ) from e

    return cast(dict[str, Any], parsed)
```

- [ ] **Step 4: Implement `manifest.py`**

`code-intake/src/code_intake/manifest.py`:

```python
"""Build the Code Intake package manifest payload + envelope.

Mirrors Sprint 2's pipeline-factory manifest builder. The envelope's
sentinel fields stay UNSIGNED in git; Sprint 3's manifest-signer fills
them in CI."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from importlib.metadata import version as _pkg_version
from pathlib import Path
from typing import Any

from platform_contracts.canonical import canonical_json

from .checkers.base import CheckResult

# Sentinel constants (mirror pipeline-factory.manifest — both packages
# define their own to avoid a cross-package dependency).
UNSIGNED_SIGNATURE = "UNSIGNED"
UNSIGNED_KEY_ARN = "arn:aws:kms:placeholder:000000000000:key/unsigned"
UNSIGNED_SIGNING_ALGORITHM = "RSASSA_PKCS1_V1_5_SHA_256"
UNSIGNED_PRINCIPAL = "unsigned"


def _code_intake_version() -> str:
    try:
        return _pkg_version("code-intake")
    except Exception:  # pragma: no cover — source checkout without install
        return "0.1.0"


def _file_ref(package_path: Path, file_path: Path) -> dict[str, str]:
    return {
        "path": str(file_path.relative_to(package_path).as_posix()),
        "sha256": hashlib.sha256(file_path.read_bytes()).hexdigest(),
    }


def _build_layout(package_path: Path) -> dict[str, Any]:
    sas_files = [_file_ref(package_path, p) for p in sorted((package_path / "sas").rglob("*.sas"))] \
        if (package_path / "sas").is_dir() else []
    python_dir = package_path / "python"
    python_files: list[dict[str, str]] = []
    test_files: list[dict[str, str]] = []
    if python_dir.is_dir():
        for py in sorted(python_dir.rglob("*.py")):
            if "tests" in py.parts:
                test_files.append(_file_ref(package_path, py))
            else:
                python_files.append(_file_ref(package_path, py))

    return {
        "sas_files": sas_files,
        "python_files": python_files,
        "test_files": test_files,
        "pir_ref": _file_ref(package_path, package_path / "pir.yaml"),
        "model_config_ref": _file_ref(package_path, package_path / "model_config.yaml"),
    }


def _build_validation_summary(
    results: list[CheckResult], ran_at: str
) -> dict[str, Any]:
    return {
        "ran_at": ran_at,
        "checks": [
            {
                "name": r.checker,
                "passed": r.passed,
                "finding_count": len(r.findings),
                "codes": sorted({f.code for f in r.findings}),
            }
            for r in results
        ],
    }


def build_package_payload(
    *,
    package_path: Path,
    results: list[CheckResult],
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Construct the payload object that goes inside the package envelope."""
    config_path = package_path / "model_config.yaml"
    import yaml

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    now = generated_at or datetime.now(UTC).isoformat(timespec="seconds")
    return {
        "schema_version": 1,
        "code_intake_version": _code_intake_version(),
        "model_name": config["model_name"],
        "version": config["version"],
        "generated_at": now,
        "package_layout": _build_layout(package_path),
        "validation_summary": _build_validation_summary(results, now),
    }


def build_package_envelope(
    *,
    payload: dict[str, Any],
    subject_ref: str,
    signed_at: str | None = None,
) -> dict[str, Any]:
    """Wrap payload in a manifest-envelope. UNSIGNED by design — Sprint 3's
    signer fills the signature fields in CI."""
    digest = hashlib.sha256(canonical_json(payload)).hexdigest()
    return {
        "digest": digest,
        "digest_algorithm": "SHA-256",
        "signature": UNSIGNED_SIGNATURE,
        "signing_key_arn": UNSIGNED_KEY_ARN,
        "signing_algorithm": UNSIGNED_SIGNING_ALGORITHM,
        "subject_type": "package",
        "subject_ref": subject_ref,
        "signed_at": signed_at or datetime.now(UTC).isoformat(timespec="seconds"),
        "signer_principal": UNSIGNED_PRINCIPAL,
        "payload": payload,
    }
```

- [ ] **Step 5: Run tests, confirm they pass**

```bash
uv run pytest code-intake/tests/test_package_config.py code-intake/tests/test_manifest.py -v
```

Expected: 3 + 5 = 8 passed.

- [ ] **Step 6: Full workspace pytest + ruff + format + mypy**

```bash
uv run pytest -q
uv run ruff check
uv run ruff format --check
uv run mypy code-intake/src
```

Expected: all green. Workspace total: 171 + 8 = 179 passed.

- [ ] **Step 7: Commit**

```bash
git add code-intake/src/code_intake/package_config.py \
        code-intake/src/code_intake/manifest.py \
        code-intake/tests/test_package_config.py \
        code-intake/tests/test_manifest.py
git commit -m "feat(code-intake): add package_config loader + manifest builder

package_config.load_package_config validates model_config.yaml against
package-manifest-payload.schema.json. PackageConfigError on any failure.

manifest.build_package_payload reads model_config.yaml + the orchestrator
results + computes fresh SHA-256s of every file on disk -> emits a
payload that passes the schema. build_package_envelope wraps it with
the four UNSIGNED sentinel fields Sprint 3's signer fills in CI.

Both functions are pure with respect to wall-clock time: pass
generated_at/signed_at explicitly to get byte-identical re-renders (the
drift gate's contract).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: CLI — `validate` + `generate-manifest`

**Why:** The surface CI calls. `validate` runs the orchestrator and reports findings; `generate-manifest` runs validate first and only writes the manifest if validation passes.

**Files:**
- Create: `code-intake/src/code_intake/cli.py`
- Create: `code-intake/tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

`code-intake/tests/test_cli.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from code_intake.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def runner():
    return CliRunner()


def test_help_lists_subcommands(runner):
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    for cmd in ("validate", "generate-manifest"):
        assert cmd in result.output


def test_validate_valid_package_exits_zero(runner):
    result = runner.invoke(main, ["validate", "--package", str(FIXTURES / "valid_package")])
    assert result.exit_code == 0, result.output


def test_validate_broken_package_exits_one(runner):
    result = runner.invoke(main, ["validate", "--package", str(FIXTURES / "broken_python")])
    assert result.exit_code == 1, result.output


def test_validate_json_emits_single_object(runner):
    result = runner.invoke(main, [
        "validate", "--package", str(FIXTURES / "valid_package"), "--json"
    ])
    assert result.exit_code == 0, result.output
    parsed = json.loads(result.output.strip().splitlines()[-1])
    assert "checks" in parsed
    assert "passed" in parsed


def test_generate_manifest_writes_file_on_success(runner, tmp_path):
    import shutil
    pkg = tmp_path / "pkg"
    shutil.copytree(FIXTURES / "valid_package", pkg)
    result = runner.invoke(main, ["generate-manifest", "--package", str(pkg)])
    assert result.exit_code == 0, result.output
    assert (pkg / "manifest.json").exists()
    envelope = json.loads((pkg / "manifest.json").read_text())
    assert envelope["signature"] == "UNSIGNED"
    assert envelope["subject_type"] == "package"


def test_generate_manifest_refuses_on_validation_failure(runner, tmp_path):
    import shutil
    pkg = tmp_path / "pkg"
    shutil.copytree(FIXTURES / "broken_python", pkg)
    # broken_python has only python/ — add the other required structure so
    # only the static_python check fails (otherwise SCH001 dominates).
    shutil.copytree(FIXTURES / "valid_package" / "sas", pkg / "sas")
    shutil.copy(FIXTURES / "valid_package" / "model_config.yaml", pkg / "model_config.yaml")
    shutil.copy(FIXTURES / "valid_package" / "pir.yaml", pkg / "pir.yaml")

    result = runner.invoke(main, ["generate-manifest", "--package", str(pkg)])
    assert result.exit_code == 1
    assert not (pkg / "manifest.json").exists()
```

- [ ] **Step 2: Run tests, confirm they fail**

```bash
uv run pytest code-intake/tests/test_cli.py -v
```

Expected: `ModuleNotFoundError: No module named 'code_intake.cli'`.

- [ ] **Step 3: Implement `cli.py`**

`code-intake/src/code_intake/cli.py`:

```python
"""Click CLI for code-intake.

Subcommands:
- validate          — run all five checkers; exit 0/1
- generate-manifest — validate then write manifest.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import click
from platform_contracts.canonical import canonical_json

from .manifest import build_package_envelope, build_package_payload
from .orchestrator import validate as run_validate


def _read_existing_manifest_timestamps(
    out: Path,
) -> tuple[str | None, str | None]:
    if not out.is_file():
        return None, None
    try:
        envelope = json.loads(out.read_text(encoding="utf-8"))
        return (
            envelope.get("payload", {}).get("generated_at"),
            envelope.get("signed_at"),
        )
    except (json.JSONDecodeError, OSError):
        return None, None


def _summarise(results: list, *, as_json: bool) -> str:
    if as_json:
        return json.dumps(
            {
                "passed": all(r.passed for r in results),
                "checks": [
                    {
                        "name": r.checker,
                        "passed": r.passed,
                        "finding_count": len(r.findings),
                        "duration_seconds": round(r.duration_seconds, 3),
                        "findings": [
                            {
                                "severity": f.severity,
                                "code": f.code,
                                "message": f.message,
                                "file": f.file,
                                "line": f.line,
                            }
                            for f in r.findings
                        ],
                    }
                    for r in results
                ],
            },
            indent=2,
            sort_keys=True,
        )

    lines = []
    for r in results:
        status = "OK" if r.passed else "FAIL"
        lines.append(f"[{status}] {r.checker} ({r.duration_seconds:.2f}s)")
        for f in r.findings:
            lines.append(f"    {f.code} ({f.severity}): {f.message}")
            if f.file:
                location = f.file + (f":{f.line}" if f.line else "")
                lines.append(f"        at {location}")
    overall = "PASSED" if all(r.passed for r in results) else "FAILED"
    lines.append(f"\nOverall: {overall}")
    return "\n".join(lines)


@click.group(help=__doc__)
def main() -> None:
    pass


@main.command("validate")
@click.option(
    "--package",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option("--strict", is_flag=True, help="Flip warning-severity findings into errors")
@click.option("--json", "as_json", is_flag=True, help="Emit a single JSON object on stdout")
def validate_cmd(package: Path, strict: bool, as_json: bool) -> None:
    results = run_validate(package, strict=strict)
    click.echo(_summarise(results, as_json=as_json))
    if not all(r.passed for r in results):
        sys.exit(1)


@main.command("generate-manifest")
@click.option(
    "--package",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option("--strict", is_flag=True)
def generate_manifest_cmd(package: Path, strict: bool) -> None:
    """Run validate; on success, write packages/<name>/<version>/manifest.json."""
    results = run_validate(package, strict=strict)
    if not all(r.passed for r in results):
        click.echo(_summarise(results, as_json=False), err=True)
        click.echo("\nValidation failed — manifest NOT written.", err=True)
        sys.exit(1)

    manifest_path = package / "manifest.json"
    existing_generated_at, existing_signed_at = _read_existing_manifest_timestamps(
        manifest_path
    )
    payload = build_package_payload(
        package_path=package,
        results=results,
        generated_at=existing_generated_at,
    )
    envelope = build_package_envelope(
        payload=payload,
        subject_ref=f"packages/{payload['model_name']}/{payload['version']}/",
        signed_at=existing_signed_at,
    )

    manifest_path.write_bytes(canonical_json(envelope))
    click.echo(f"Wrote {manifest_path}")
```

- [ ] **Step 4: Run tests, confirm they pass**

```bash
uv run pytest code-intake/tests/test_cli.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Sanity-check the entry point**

```bash
uv sync
uv run code-intake --help
```

Expected: help output listing `validate` and `generate-manifest`.

- [ ] **Step 6: Full workspace pytest + ruff + format + mypy**

```bash
uv run pytest -q
uv run ruff check
uv run ruff format --check
uv run mypy code-intake/src
```

Expected: all green. Workspace total: 179 + 6 = 185 passed.

- [ ] **Step 7: Commit**

```bash
git add code-intake/src/code_intake/cli.py code-intake/tests/test_cli.py
git commit -m "feat(code-intake): add Click CLI with validate + generate-manifest

validate         — runs orchestrator, prints findings table (or --json), exit 0/1
generate-manifest — runs validate; on success writes manifest.json with
                   the UNSIGNED sentinels Sprint 3's signer fills in CI.
                   Preserves generated_at/signed_at from any existing
                   manifest for byte-stable re-renders.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: Worked example package

**Why:** Real package the end-to-end test runs against. Synthetic but real enough to exercise every checker.

**Files:**
- Create: `packages/credit-risk-pd/1.0.0/model_config.yaml`
- Create: `packages/credit-risk-pd/1.0.0/sas/score.sas`
- Create: `packages/credit-risk-pd/1.0.0/python/score.py`
- Create: `packages/credit-risk-pd/1.0.0/python/tests/test_score.py`
- Create: `packages/credit-risk-pd/1.0.0/pir.yaml`
- Create: `packages/credit-risk-pd/1.0.0/README.md`
- Create: `packages/credit-risk-pd/1.0.0/manifest.json` (generated by Step 8)

- [ ] **Step 1: Create `python/score.py`**

```python
"""Credit-risk PD scoring stub — synthetic Phase-2 worked example."""

from __future__ import annotations


def score(data: dict[str, float]) -> dict[str, float | str]:
    """Score one customer record.

    Mirrors the SAS score logic (sas/score.sas). Real Phase-3 scoring
    code goes here.
    """
    income_band = data["income_band"]
    tenure_months = data["tenure_months"]
    delinquencies = data["delinquencies"]

    pd_score = 0.5 * income_band + 0.3 * tenure_months / 12 + 0.2 * delinquencies

    if pd_score > 0.7:
        risk_band = "HIGH"
    elif pd_score > 0.4:
        risk_band = "MEDIUM"
    else:
        risk_band = "LOW"

    return {"pd_score": pd_score, "risk_band": risk_band}
```

- [ ] **Step 2: Create `python/tests/test_score.py`**

```python
from score import score


def test_score_high():
    out = score({"income_band": 2.0, "tenure_months": 24, "delinquencies": 1.0})
    assert out["pd_score"] > 0.7
    assert out["risk_band"] == "HIGH"


def test_score_medium():
    out = score({"income_band": 1.0, "tenure_months": 12, "delinquencies": 0.5})
    assert 0.4 < out["pd_score"] <= 0.7
    assert out["risk_band"] == "MEDIUM"


def test_score_low():
    out = score({"income_band": 0.1, "tenure_months": 6, "delinquencies": 0.0})
    assert out["pd_score"] < 0.4
    assert out["risk_band"] == "LOW"
```

- [ ] **Step 3: Create `sas/score.sas`**

```sas
/* Synthetic SAS scoring code — Phase-2 worked example mirroring score.py. */
DATA scored;
  SET input;
  pd_score = 0.5 * income_band + 0.3 * tenure_months / 12 + 0.2 * delinquencies;
  IF pd_score > 0.7 THEN risk_band = 'HIGH';
  ELSE IF pd_score > 0.4 THEN risk_band = 'MEDIUM';
  ELSE risk_band = 'LOW';
RUN;

PROC PRINT data=scored;
RUN;
```

- [ ] **Step 4: Create `pir.yaml`**

```yaml
mapping_version: 1
model_name: credit-risk-pd
model_version: 1.0.0

inputs:
  - { name: income_band,   type: float, source: customer.income_band_lookup,
      description: "Discretised income tier (1..5)" }
  - { name: tenure_months, type: int,   source: customer.tenure_months,
      description: "Months since account opening" }
  - { name: delinquencies, type: float, source: customer.delinquencies_12m,
      description: "Count of 30+ DPD events in last 12 months", nullable: true }

outputs:
  - { name: pd_score,  type: float,  description: "Probability of default (0..1)" }
  - { name: risk_band, type: string, description: "HIGH / MEDIUM / LOW" }
```

- [ ] **Step 5: Create `model_config.yaml`**

Use zero-hash placeholders for the file_refs — the manifest generation in Step 8 will overwrite the manifest.json with the correct hashes. The model_config.yaml itself just declares the package's identity + layout shape.

```yaml
schema_version: 1
code_intake_version: "0.1.0"
model_name: credit-risk-pd
version: 1.0.0
generated_at: "2026-06-04T00:00:00+00:00"

package_layout:
  sas_files:
    - { path: "sas/score.sas", sha256: "0000000000000000000000000000000000000000000000000000000000000000" }
  python_files:
    - { path: "python/score.py", sha256: "0000000000000000000000000000000000000000000000000000000000000000" }
  test_files:
    - { path: "python/tests/test_score.py", sha256: "0000000000000000000000000000000000000000000000000000000000000000" }
  pir_ref:
    path: "pir.yaml"
    sha256: "0000000000000000000000000000000000000000000000000000000000000000"
  model_config_ref:
    path: "model_config.yaml"
    sha256: "0000000000000000000000000000000000000000000000000000000000000000"

validation_summary:
  ran_at: "2026-06-04T00:00:00+00:00"
  checks: []
```

- [ ] **Step 6: Create `README.md`**

```markdown
# `credit-risk-pd@1.0.0` — Phase-2 worked-example package

Synthetic Track-A productized package. Threaded through Sprints 2, 3, and 4 as the end-to-end demonstration model.

## Layout

| Path | Purpose |
|---|---|
| `model_config.yaml`        | Package contract — names every shipped artefact |
| `sas/score.sas`            | Synthetic SAS scoring code (DATA + PROC PRINT) |
| `python/score.py`          | Python scoring stub mirroring the SAS logic |
| `python/tests/test_score.py` | pytest unit tests covering HIGH/MEDIUM/LOW paths |
| `pir.yaml`                 | PIR mapping for the three input columns |
| `manifest.json`            | Generated by `code-intake generate-manifest`; UNSIGNED in git, signed copy in S3 |

## Validating this package

```bash
uv run code-intake validate --package packages/credit-risk-pd/1.0.0
uv run code-intake generate-manifest --package packages/credit-risk-pd/1.0.0
```

The generated `manifest.json` is committed to git as the audit anchor. The signed copy lives at `s3://exl-platform-signed-manifests/packages/credit-risk-pd/1.0.0/manifest.json` (post-CI sign step).

## Downstream

`pipeline-factory/configs/credit-risk-pd/1.0.0/model_config.yaml` declares `upstream_package: {name: credit-risk-pd, version: 1.0.0}` so the generated pipeline manifest embeds `upstream_refs[].digest` pointing here.
```

- [ ] **Step 7: Validate the package against the checkers**

```bash
uv run code-intake validate --package packages/credit-risk-pd/1.0.0
```

Expected: all 5 checkers pass. Exit 0.

If a checker fails, the package content needs adjustment. Don't proceed to Step 8 until all five pass.

- [ ] **Step 8: Generate the manifest**

```bash
uv run code-intake generate-manifest --package packages/credit-risk-pd/1.0.0
```

Expected: `Wrote packages/credit-risk-pd/1.0.0/manifest.json`. The committed manifest's payload `validation_summary.checks` should show all five checkers passing.

- [ ] **Step 9: Verify the regenerated manifest is byte-stable across re-runs**

```bash
uv run code-intake generate-manifest --package packages/credit-risk-pd/1.0.0
git diff --exit-code packages/credit-risk-pd/1.0.0/manifest.json
```

Expected: second run produces identical bytes (the timestamps are preserved from the first run via `_read_existing_manifest_timestamps`). `git diff --exit-code` exits 0.

- [ ] **Step 10: Full workspace pytest**

```bash
uv run pytest -q
```

Expected: still green at 185 passes (no new tests; just new fixture data).

- [ ] **Step 11: Commit**

```bash
git add packages/credit-risk-pd/1.0.0/
git commit -m "feat(packages): add credit-risk-pd@1.0.0 worked-example package

Synthetic Phase-2 Track-A demonstration package threaded through all
three subsystems. Contents:

- python/score.py + tests — score(data) function with HIGH/MEDIUM/LOW
  classification + 3 pytest unit tests
- sas/score.sas — DATA + PROC PRINT mirroring the Python logic
- pir.yaml — maps the three input columns (income_band, tenure_months,
  delinquencies) plus the two outputs (pd_score, risk_band)
- model_config.yaml — package contract
- manifest.json — generated by code-intake generate-manifest; UNSIGNED
  in git, signed copy will land in S3 via Sprint 3's signer

All five Code Intake checkers pass against this fixture. The next sprint
task (T12-T13) wires upstream_refs[] from the pipeline-factory manifest
to this package's manifest.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: Pipeline-factory extension — `upstream_resolver` + `manifest.py`/`generator.py` mods

**Why:** Pipeline Factory's `generate` needs to read the package's manifest and embed the cross-link digest. New `upstream_resolver.py` isolates the cross-link logic; `manifest.py` and `generator.py` get tiny additive changes.

**Files:**
- Create: `pipeline-factory/src/pipeline_factory/upstream_resolver.py`
- Modify: `pipeline-factory/src/pipeline_factory/manifest.py` (`build_payload` accepts `upstream_refs`)
- Modify: `pipeline-factory/src/pipeline_factory/generator.py` (resolves `upstream_package` and threads to `build_payload`)
- Create: `pipeline-factory/tests/test_upstream_resolver.py`
- Modify: `pipeline-factory/tests/test_manifest.py` (existing — add tests for `upstream_refs` parameter)

- [ ] **Step 1: Write failing tests for the resolver**

`pipeline-factory/tests/test_upstream_resolver.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline_factory.upstream_resolver import resolve_upstream_refs


def test_returns_empty_when_no_upstream(tmp_path):
    assert resolve_upstream_refs(upstream_package=None, packages_root=tmp_path) == []


def test_returns_ref_for_existing_package(tmp_path):
    pkg = tmp_path / "credit-risk-pd" / "1.0.0"
    pkg.mkdir(parents=True)
    manifest = {
        "digest": "f" * 64,
        "digest_algorithm": "SHA-256",
        "signature": "UNSIGNED",
        "payload": {"model_name": "credit-risk-pd", "version": "1.0.0"},
    }
    (pkg / "manifest.json").write_text(json.dumps(manifest))

    result = resolve_upstream_refs(
        upstream_package={"name": "credit-risk-pd", "version": "1.0.0"},
        packages_root=tmp_path,
    )
    assert result == [{
        "type": "package",
        "ref": "credit-risk-pd@1.0.0",
        "digest": "f" * 64,
    }]


def test_raises_on_missing_manifest(tmp_path):
    from pipeline_factory.upstream_resolver import GeneratorError

    with pytest.raises(GeneratorError, match="does not exist"):
        resolve_upstream_refs(
            upstream_package={"name": "credit-risk-pd", "version": "1.0.0"},
            packages_root=tmp_path,
        )


def test_raises_when_manifest_missing_digest(tmp_path):
    from pipeline_factory.upstream_resolver import GeneratorError

    pkg = tmp_path / "credit-risk-pd" / "1.0.0"
    pkg.mkdir(parents=True)
    (pkg / "manifest.json").write_text(json.dumps({"foo": "bar"}))

    with pytest.raises(GeneratorError, match="digest"):
        resolve_upstream_refs(
            upstream_package={"name": "credit-risk-pd", "version": "1.0.0"},
            packages_root=tmp_path,
        )
```

- [ ] **Step 2: Run tests, confirm they fail**

```bash
uv run pytest pipeline-factory/tests/test_upstream_resolver.py -v
```

Expected: `ModuleNotFoundError: No module named 'pipeline_factory.upstream_resolver'`.

- [ ] **Step 3: Implement `upstream_resolver.py`**

`pipeline-factory/src/pipeline_factory/upstream_resolver.py`:

```python
"""Resolve a pipeline-factory model_config's upstream_package block to an
upstream_refs[] entry suitable for the pipeline manifest payload."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class GeneratorError(Exception):
    """Raised when pipeline generation can't resolve a required input."""


def resolve_upstream_refs(
    *,
    upstream_package: dict[str, str] | None,
    packages_root: Path,
) -> list[dict[str, Any]]:
    """Read packages/<name>/<version>/manifest.json and return a single
    upstream_refs entry. Returns [] when upstream_package is None.

    Raises:
        GeneratorError: when the package manifest is missing or lacks a
            `digest` field.
    """
    if upstream_package is None:
        return []

    name = upstream_package["name"]
    version = upstream_package["version"]
    manifest_path = packages_root / name / version / "manifest.json"

    if not manifest_path.exists():
        raise GeneratorError(
            f"upstream_package references {name}@{version} but "
            f"{manifest_path} does not exist. "
            f"Run `code-intake generate-manifest --package {manifest_path.parent}` first."
        )

    envelope = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = envelope.get("digest")
    if not digest:
        raise GeneratorError(
            f"upstream package manifest at {manifest_path} is missing the "
            f"`digest` field; cannot embed cross-link."
        )

    return [{
        "type": "package",
        "ref": f"{name}@{version}",
        "digest": digest,
    }]
```

- [ ] **Step 4: Run resolver tests, confirm they pass**

```bash
uv run pytest pipeline-factory/tests/test_upstream_resolver.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Modify `manifest.py` to accept `upstream_refs`**

Edit `pipeline-factory/src/pipeline_factory/manifest.py`. Update `build_payload` (currently around line 22):

```diff
 def build_payload(
     *,
     model_name: str,
     version: str,
     tier: str,
     artifact_hashes: dict[str, str],
     generated_at: str | None = None,
+    upstream_refs: list[dict[str, Any]] | None = None,
 ) -> dict[str, Any]:
     """Construct the payload object that goes inside the manifest envelope."""
     return {
         "schema_version": 1,
         "generator_version": _generator_version(),
         "model_name": model_name,
         "version": version,
         "tier": tier,
         "generated_at": generated_at or datetime.now(UTC).isoformat(),
         "artifact_hashes": artifact_hashes,
+        "upstream_refs": upstream_refs or [],
     }
```

- [ ] **Step 6: Add a test confirming `build_payload` embeds `upstream_refs`**

Edit `pipeline-factory/tests/test_manifest.py` — append:

```python
def test_build_payload_embeds_upstream_refs():
    from pipeline_factory.manifest import build_payload

    payload = build_payload(
        model_name="credit-risk-pd",
        version="1.0.0",
        tier="standard",
        artifact_hashes={
            "statemachine_sha256":  "a" * 64,
            "terraform_sha256":     "b" * 64,
            "model_config_sha256":  "c" * 64,
            "registration_sha256":  "d" * 64,
        },
        upstream_refs=[{"type": "package", "ref": "credit-risk-pd@1.0.0", "digest": "f" * 64}],
    )
    assert payload["upstream_refs"] == [{
        "type": "package", "ref": "credit-risk-pd@1.0.0", "digest": "f" * 64,
    }]


def test_build_payload_defaults_upstream_refs_to_empty_list():
    from pipeline_factory.manifest import build_payload

    payload = build_payload(
        model_name="credit-risk-pd",
        version="1.0.0",
        tier="standard",
        artifact_hashes={
            "statemachine_sha256":  "a" * 64, "terraform_sha256":     "b" * 64,
            "model_config_sha256":  "c" * 64, "registration_sha256":  "d" * 64,
        },
    )
    assert payload["upstream_refs"] == []
```

- [ ] **Step 7: Modify `generator.py` to call the resolver**

Edit `pipeline-factory/src/pipeline_factory/generator.py`. Two changes:

1. Add the import at the top:

```diff
 from .hashing import canonical_json, sha256_of_text, terraform_fmt
 from .manifest import build_envelope, build_payload
 from .renderer import render_pipeline_tf, render_statemachine
+from .upstream_resolver import resolve_upstream_refs
```

2. Inside the `generate(...)` function (after `config = load_config(config_path)` around line 96), thread the resolver into the payload build:

```diff
     config = load_config(config_path)
     model_name: str = config["model_name"]
     version: str = config["version"]
     tier: str = config["execution_tier"]
     out_dir = outputs_root / model_name / version

+    upstream_refs = resolve_upstream_refs(
+        upstream_package=config.get("upstream_package"),
+        packages_root=Path("packages"),
+    )
+
     statemachine_json = render_statemachine(tier, {"model": _model_context(config)})
     ...

     existing_generated_at, existing_signed_at = _existing_manifest_timestamps(out_dir)
     payload = build_payload(
         model_name=model_name,
         version=version,
         tier=tier,
         artifact_hashes=artifact_hashes,
         generated_at=existing_generated_at,
+        upstream_refs=upstream_refs,
     )
```

- [ ] **Step 8: Run all pipeline-factory tests, confirm they still pass**

```bash
uv run pytest pipeline-factory/tests -v
```

Expected: existing Sprint 2 tests + 4 new resolver tests + 2 new manifest tests = previous total + 6 passed. The Sprint 2 worked example regenerates with `upstream_refs: []` (the existing config doesn't have `upstream_package` yet; T13 adds it).

- [ ] **Step 9: Full workspace pytest + ruff + format + mypy**

```bash
uv run pytest -q
uv run ruff check
uv run ruff format --check
uv run mypy pipeline-factory/src code-intake/src
```

Expected: all green. Workspace total: 185 + 6 = 191 passed.

- [ ] **Step 10: Commit**

```bash
git add pipeline-factory/src/pipeline_factory/upstream_resolver.py \
        pipeline-factory/src/pipeline_factory/manifest.py \
        pipeline-factory/src/pipeline_factory/generator.py \
        pipeline-factory/tests/test_upstream_resolver.py \
        pipeline-factory/tests/test_manifest.py
git commit -m "feat(pipeline-factory): add upstream_resolver + extend manifest builder

Three additive changes:
- new pipeline_factory/upstream_resolver.py: pure function that reads
  packages/<name>/<version>/manifest.json and emits a single
  upstream_refs entry (type=package, ref=<name>@<version>, digest=...).
  GeneratorError on missing file or missing digest.
- pipeline_factory.manifest.build_payload gains optional upstream_refs
  parameter defaulting to []. Sprint 2's existing manifest stays a valid
  shape.
- pipeline_factory.generator.generate calls the resolver between config
  loading and payload building.

The cross-link is implicit drift-gated: bumping a package's manifest
bumps its digest, which forces upstream_refs[0].digest to change in the
pipeline manifest, which fails 'git diff --exit-code pipelines/' until
the pipeline manifest is also regenerated.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 13: Wire the worked example — update pipeline-factory config + regenerate manifest

**Why:** The credit-risk-pd pipeline manifest from Sprint 2 currently has `upstream_refs: []`. Bringing the worked example fully end-to-end means adding `upstream_package: {name: credit-risk-pd, version: 1.0.0}` to the pipeline config and regenerating the manifest.

**Files:**
- Modify: `pipeline-factory/configs/credit-risk-pd/1.0.0/model_config.yaml`
- Modify: `pipelines/credit-risk-pd/1.0.0/manifest.json` (regenerated)

- [ ] **Step 1: Add `upstream_package` to the existing config**

Edit `pipeline-factory/configs/credit-risk-pd/1.0.0/model_config.yaml`. Append the block:

```yaml
upstream_package:
  name: credit-risk-pd
  version: 1.0.0
```

The file should now look like (existing 13 lines + 3 new):

```yaml
model_name: credit-risk-pd
version: 1.0.0
execution_tier: standard
schedule_cadence: "cron(0 6 * * ? *)"
input_schema_ref: s3://absa-exl/schemas/credit-risk-pd/1.0.0/input.json
output_schema_ref: s3://absa-exl/schemas/credit-risk-pd/1.0.0/output.json
pir_doc_ref: s3://absa-exl/pir/credit-risk-pd/1.0.0/pir-evidence.json
owner_email: model.owner@absa.africa
accountable_executive: Jane Exec
sla_seconds: 3600
sas_code_version: sas-2026.04.1
inference_code_version: py-2026.04.1
model_class: credit
upstream_package:
  name: credit-risk-pd
  version: 1.0.0
```

- [ ] **Step 2: Regenerate the pipeline manifest**

```bash
uv run generate-pipeline generate --config pipeline-factory/configs/credit-risk-pd/1.0.0/model_config.yaml --force
```

Expected: command exits 0. The regenerated `pipelines/credit-risk-pd/1.0.0/manifest.json` now contains:

```json
"upstream_refs": [
  {
    "type": "package",
    "ref": "credit-risk-pd@1.0.0",
    "digest": "<the package manifest's digest from T11>"
  }
]
```

- [ ] **Step 3: Verify the digest matches the package manifest**

```bash
PKG_DIGEST=$(python -c "import json; print(json.load(open('packages/credit-risk-pd/1.0.0/manifest.json'))['digest'])")
PIPE_REF=$(python -c "import json; m=json.load(open('pipelines/credit-risk-pd/1.0.0/manifest.json')); print(m['payload']['upstream_refs'][0]['digest'])")
echo "package digest:   $PKG_DIGEST"
echo "pipeline ref:     $PIPE_REF"
[ "$PKG_DIGEST" = "$PIPE_REF" ] && echo "MATCH" || (echo "MISMATCH"; exit 1)
```

Expected: `MATCH`.

- [ ] **Step 4: Verify byte-stability — regenerate twice**

```bash
uv run generate-pipeline generate --config pipeline-factory/configs/credit-risk-pd/1.0.0/model_config.yaml --force
git diff --exit-code pipelines/credit-risk-pd/1.0.0/
```

Expected: `git diff --exit-code` returns 0 (second generation produces identical bytes).

- [ ] **Step 5: Confirm the regenerated manifest passes schema validation**

```bash
python -c "
import json
from platform_contracts.loader import validate
m = json.load(open('pipelines/credit-risk-pd/1.0.0/manifest.json'))
validate('pipeline-manifest-payload', m['payload'])
print('OK')
"
```

Expected: `OK`. (`uv run` not strictly needed since the script imports are workspace deps.)

- [ ] **Step 6: Full workspace pytest**

```bash
uv run pytest -q
```

Expected: still green at 191 passes — no new tests; just regenerated fixture data.

- [ ] **Step 7: Commit**

```bash
git add pipeline-factory/configs/credit-risk-pd/1.0.0/model_config.yaml \
        pipelines/credit-risk-pd/1.0.0/manifest.json
git commit -m "feat(pipelines): wire credit-risk-pd@1.0.0 cross-link to upstream package

Adds upstream_package: {name: credit-risk-pd, version: 1.0.0} to the
pipeline-factory config and regenerates the pipeline manifest. The
manifest now contains payload.upstream_refs[0] referencing the package
manifest's digest — the cryptographic chain registry-record ->
pipeline-manifest -> package-manifest is now complete.

Drift-gate symmetry verified: regenerating the pipeline manifest twice
produces byte-identical output, and the embedded digest matches the
in-git package manifest's digest field exactly.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 14: End-to-end Track A test

**Why:** The strongest test signal Sprint 4 ships. Proves the full Track A chain (Code Intake → Pipeline Factory → signer → mock registrar) is consistent at every link inside one moto context — no real AWS, no real network.

**Files:**
- Create: `code-intake/tests/test_e2e_track_a.py`

- [ ] **Step 1: Write the e2e test**

`code-intake/tests/test_e2e_track_a.py`:

```python
"""End-to-end Track A: Code Intake -> Pipeline Factory -> signer -> mock registrar.

Proves the full Phase-2 chain is consistent at every link inside one moto
context. No real AWS calls; no real HTTP."""

from __future__ import annotations

import json
import os
from pathlib import Path

import boto3
import pytest
from click.testing import CliRunner
from cryptography.hazmat.primitives import serialization
from moto import mock_aws

from code_intake.cli import main as code_intake_main
from manifest_signer.signer import sign_envelope
from manifest_signer.verifier import verify_offline, verify_online
from platform_contracts.canonical import canonical_json

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_PATH = REPO_ROOT / "packages" / "credit-risk-pd" / "1.0.0"
PIPELINE_CONFIG = REPO_ROOT / "pipeline-factory" / "configs" / "credit-risk-pd" / "1.0.0" / "model_config.yaml"
PIPELINE_MANIFEST = REPO_ROOT / "pipelines" / "credit-risk-pd" / "1.0.0" / "manifest.json"


@pytest.fixture(autouse=True)
def _aws_env(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")


def test_full_track_a_chain():
    """Single-context proof that:
      1. The committed package validates and its manifest's payload-digest
         is byte-stable.
      2. The committed pipeline manifest's upstream_refs[0].digest matches
         the package manifest's digest exactly.
      3. Both manifests can be signed by the Sprint 3 signer.
      4. Both signed manifests verify online (kms:Verify) and offline (PEM).
    """
    # ----- 1) Verify the package validates fresh -----
    runner = CliRunner()
    result = runner.invoke(
        code_intake_main, ["validate", "--package", str(PACKAGE_PATH)],
    )
    assert result.exit_code == 0, result.output

    # ----- 2) Verify the cryptographic chain (in-git, no signing yet) -----
    pkg_manifest = json.loads((PACKAGE_PATH / "manifest.json").read_text())
    pipeline_manifest = json.loads(PIPELINE_MANIFEST.read_text())

    assert pkg_manifest["subject_type"] == "package"
    pipeline_payload = pipeline_manifest["payload"]
    assert len(pipeline_payload["upstream_refs"]) == 1
    upstream = pipeline_payload["upstream_refs"][0]
    assert upstream["type"] == "package"
    assert upstream["ref"] == "credit-risk-pd@1.0.0"
    assert upstream["digest"] == pkg_manifest["digest"], (
        f"chain broken: pipeline.upstream_refs[0].digest={upstream['digest']!r} "
        f"!= package.digest={pkg_manifest['digest']!r}"
    )

    # ----- 3) Sign both manifests under moto -----
    with mock_aws():
        kms = boto3.client("kms", region_name="eu-west-1")
        key_meta = kms.create_key(
            Description="test signing key",
            KeyUsage="SIGN_VERIFY",
            KeySpec="RSA_3072",
        )["KeyMetadata"]

        signed_pkg = sign_envelope(
            pkg_manifest,
            key_arn=key_meta["Arn"],
            kms_client=kms,
            signer_principal="arn:aws:sts::111:assumed-role/signer/test-run",
        )
        signed_pipeline = sign_envelope(
            pipeline_manifest,
            key_arn=key_meta["Arn"],
            kms_client=kms,
            signer_principal="arn:aws:sts::111:assumed-role/signer/test-run",
        )

        # The chain still holds AFTER signing: the digest field doesn't move
        # (the signer fills only the signature sentinels, not the digest).
        assert signed_pkg["digest"] == pkg_manifest["digest"]
        assert (
            signed_pipeline["payload"]["upstream_refs"][0]["digest"]
            == signed_pkg["digest"]
        )

        # ----- 4) Verify both online and offline -----
        verify_online(signed_pkg, kms_client=kms)
        verify_online(signed_pipeline, kms_client=kms)

        # Offline path: fetch the moto-generated public key + PEM-encode it.
        der = kms.get_public_key(KeyId=key_meta["KeyId"])["PublicKey"]
        pub = serialization.load_der_public_key(der)
        pem = pub.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        verify_offline(signed_pkg, public_key_pem=pem)
        verify_offline(signed_pipeline, public_key_pem=pem)


def test_full_track_a_chain_idempotent_re_sign():
    """Re-signing the already-signed envelope is a no-op (Sprint 3 contract)."""
    pkg_manifest = json.loads((PACKAGE_PATH / "manifest.json").read_text())

    with mock_aws():
        kms = boto3.client("kms", region_name="eu-west-1")
        key_meta = kms.create_key(
            Description="test signing key",
            KeyUsage="SIGN_VERIFY",
            KeySpec="RSA_3072",
        )["KeyMetadata"]

        signed_a = sign_envelope(
            pkg_manifest,
            key_arn=key_meta["Arn"],
            kms_client=kms,
            signer_principal="test",
            signed_at="2026-06-04T00:00:00+00:00",
        )
        # Re-sign with same key — same-key noop branch
        signed_b = sign_envelope(
            signed_a,
            key_arn=key_meta["Arn"],
            kms_client=kms,
            signer_principal="test",
            signed_at="2026-06-04T00:00:00+00:00",
        )
        assert signed_b is signed_a  # same object identity = noop branch fired
```

- [ ] **Step 2: Run the e2e test**

```bash
uv run pytest code-intake/tests/test_e2e_track_a.py -v
```

Expected: 2 passed. The first test asserts the chain is consistent at the in-git layer AND under signing AND under both verification paths. The second asserts the Sprint-3 idempotency contract still holds for package manifests.

- [ ] **Step 3: Full workspace pytest + ruff + format + mypy**

```bash
uv run pytest -q
uv run ruff check
uv run ruff format --check
uv run mypy code-intake/src
```

Expected: all green. Workspace total: 191 + 2 = 193 passed.

- [ ] **Step 4: Commit**

```bash
git add code-intake/tests/test_e2e_track_a.py
git commit -m "test(code-intake): end-to-end Track A chain test

Single moto-backed test exercising the full Phase-2 chain:
1. code-intake validate against the committed credit-risk-pd@1.0.0 package
2. Cryptographic chain check: pipeline.upstream_refs[0].digest matches
   package.digest byte-for-byte (the chain-of-custody anchor)
3. Sign both manifests via the Sprint 3 signer under moto KMS
4. Verify both signed envelopes online (kms:Verify) AND offline (PEM)

Second test confirms the Sprint 3 idempotency contract still holds for
package manifests: re-signing returns the same object (object identity,
not just equality).

This is the strongest test signal Sprint 4 ships -- proves the full
audit chain works without any real AWS.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 15: CI workflows — new `code-intake.yml` + modify `pipeline-factory.yml`

**Why:** Activates the drift gates and the dual-root signer in CI. The new `code-intake.yml` runs validate + generate + git diff on every push touching `packages/**`. The modified `pipeline-factory.yml` triggers on `packages/**` too (so the cross-link drift gate fires) and signs both prefixes.

**Files:**
- Create: `.github/workflows/code-intake.yml`
- Modify: `.github/workflows/pipeline-factory.yml`

- [ ] **Step 1: Create `code-intake.yml`**

```yaml
name: code-intake

on:
  pull_request:
    branches:
      - main
      - "phase-1/**"
      - "phase-2/**"
    paths:
      - "code-intake/**"
      - "packages/**"
      - "platform-contracts/**"
      - "pyproject.toml"
      - "uv.lock"
      - ".github/workflows/code-intake.yml"
  push:
    branches:
      - main
      - "phase-1/**"
      - "phase-2/**"
    paths:
      - "code-intake/**"
      - "packages/**"
      - "platform-contracts/**"
      - "pyproject.toml"
      - "uv.lock"
      - ".github/workflows/code-intake.yml"

permissions:
  contents: read

jobs:
  validate-and-generate-package:
    name: validate + generate-manifest (drift gate)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - name: Sync
        run: uv sync --frozen
      - name: code-intake tests
        run: uv run pytest code-intake/tests -v --timeout=60 --timeout-method=thread
      - name: Validate + regenerate manifest for every package, assert byte-stability
        run: |
          set -euo pipefail
          for pkg in packages/*/*/; do
            uv run code-intake validate --package "$pkg" --strict
            uv run code-intake generate-manifest --package "$pkg"
          done
          git diff --exit-code packages/
```

- [ ] **Step 2: Modify `pipeline-factory.yml` — add `packages/**` to triggers**

Edit `.github/workflows/pipeline-factory.yml`. Update both `pull_request.paths` and `push.paths` to include `packages/**`:

```diff
       - "pipeline-factory/**"
       - "pipelines/**"
+      - "packages/**"
       - "platform-contracts/**"
       - "manifest-signer/**"
       - "pyproject.toml"
       - "uv.lock"
       - ".github/workflows/pipeline-factory.yml"
```

Apply to both the `pull_request` block and the `push` block (the existing file has them duplicated).

- [ ] **Step 3: Modify the `sign` step to loop over both roots**

In `.github/workflows/pipeline-factory.yml`, find the `Sign all unsigned manifests` step (around line 90-100) and replace its `run:` block:

```diff
       - name: Sign all unsigned manifests
         if: env.SIGNER_ROLE_ARN != ''
         run: |
           set -euo pipefail
           # Build the assumed-role STS session ARN to record as signer_principal
           CALLER=$(aws sts get-caller-identity --query Arn --output text)
-          uv run manifest-signer sign-all \
-            --root pipelines \
-            --key-arn "$KMS_KEY_ARN" \
-            --upload-to-bucket "$SIGNED_MANIFESTS_BUCKET" \
-            --signer-principal "$CALLER"
+          for root in packages pipelines; do
+            uv run manifest-signer sign-all \
+              --root "$root" \
+              --key-arn "$KMS_KEY_ARN" \
+              --upload-to-bucket "$SIGNED_MANIFESTS_BUCKET" \
+              --signer-principal "$CALLER"
+          done
```

Ordering matters: `packages` first, then `pipelines`. The pipeline's `upstream_refs[i].digest` already points at the package manifest's `digest` (computed at gen-time, stable from there). Signing packages first gives auditors a cleaner timeline in S3 object-creation order.

- [ ] **Step 4: Run actionlint on both workflows**

```bash
actionlint .github/workflows/code-intake.yml .github/workflows/pipeline-factory.yml
```

Expected: no errors. If `actionlint` isn't installed locally, the pre-commit hook will catch it on commit.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/code-intake.yml .github/workflows/pipeline-factory.yml
git commit -m "ci: add code-intake workflow + extend pipeline-factory signer to packages/

code-intake.yml: new workflow with validate-and-generate-package drift
gate. Runs code-intake validate --strict + generate-manifest on every
packages/*/*/ then asserts git diff --exit-code. Validate-only; signing
+ registration stay in pipeline-factory.yml as the unified hub.

pipeline-factory.yml: two additive changes:
- packages/** added to both pull_request.paths and push.paths so
  changing a package retriggers the pipeline-factory drift gate (the
  pipeline manifest's upstream_refs[0].digest depends on the package
  manifest's digest)
- sign step now loops `for root in packages pipelines` so both prefixes
  are signed in one job. Order matters: packages first so the pipeline's
  upstream reference, when fetched, always points at a manifest that's
  already in S3.

No new IAM, no new bucket: the Sprint-3 signer's s3:PutObject on
\${signed_manifests_bucket}/* covers both prefixes.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 16: ADRs + READMEs

**Why:** Lock the design rationale for future contributors.

**Files:**
- Create: `docs/adr/0010-productized-package-contract.md`
- Modify: `docs/adr/0006-contract-strategy-json-schema-canonical.md` (minor edit listing the two new schemas)
- Create: `code-intake/README.md`

- [ ] **Step 1: Inspect the existing ADR convention**

```bash
head -30 docs/adr/0009-signing-foundation-topology.md
```

Note the table-style frontmatter (`| Field | Value |`) and `### Positive` / `### Negative (accepted)` Consequences subsections. Match these conventions in the new ADR.

- [ ] **Step 2: Create ADR-0010**

`docs/adr/0010-productized-package-contract.md`:

```markdown
# ADR-0010 — Productized Package Contract

| Field        | Value                                             |
|--------------|---------------------------------------------------|
| Status       | Accepted                                          |
| Date         | 2026-06-04                                        |
| Deciders     | Vishnu S (EXL ML Platform)                        |
| Consulted    | (ABSA Industrialization Team to confirm Phase 3) |
| Related      | [ADR-0003](0003-manifest-signing-kms-asymmetric.md), [ADR-0006](0006-contract-strategy-json-schema-canonical.md), [ADR-0009](0009-signing-foundation-topology.md), [Sprint 4 spec](../superpowers/specs/2026-06-04-absa-exl-phase-2-sprint-4-code-intake-design.md) |

## Context

Brief §2.1 step 3 commits to a "signed, manifested" handoff between EXL's Industrialization Team and Pipeline Factory. Sprint 4 implements that contract: a git-tracked productized package directory, a Code Intake validator that produces a signed package manifest, and a cross-link from the downstream pipeline manifest to the upstream package manifest by digest.

## Decision

**Git-tracked package layout** at `packages/<name>/<version>/`. Five artefact groups required:

- `sas/...` — SAS scoring code
- `python/score.py` + `python/tests/...` — Python scoring code and unit tests
- `pir.yaml` — PIR mapping (Production Input Register)
- `model_config.yaml` — package contract (matches `package-manifest-payload.schema.json`)
- `manifest.json` — generated by `code-intake generate-manifest`; UNSIGNED in git, signed copy in S3

**Two new schemas in `platform-contracts`:**
- `package-manifest-payload.schema.json` — the envelope payload type for a productized package.
- `pir-mapping.schema.json` — describes the shape of `pir.yaml`.

**Five checkers (collect-all-findings, never short-circuit):**
- `static_python` — subprocess ruff check + mypy --strict + pytest --collect-only.
- `static_sas` — **structural-only** for Sprint 4. Files exist, non-empty, balanced PROC/RUN. Real SAS linting deferred (see Cons).
- `schema` — model_config.yaml against package-manifest-payload schema.
- `tests` — actually invokes pytest against the package's tests.
- `pir` — pir.yaml against pir-mapping schema + AST cross-check of column references in Python.

**Chain-of-custody via `upstream_refs[]` on pipeline manifests, digest-only.** The pipeline's own signature covers the array; verifiers fetch the upstream manifest from S3 to confirm the digest matches. No signature is embedded in `upstream_refs[i]` — the digest is sufficient because canonical_json is deterministic and the upstream's signature is itself verifiable from the published public key.

**One Sprint-3 IAM role signs both packages and pipelines.** The `pipeline-factory-signer` role's `s3:PutObject` is already scoped to `${signed_manifests_bucket}/*` — adding `packages/...` writes needs no policy change. No new IAM in Sprint 4.

**Workspace-toolchain-compatible Python required.** Sprint 4's `static_python` and `tests` checkers invoke `ruff` / `mypy` / `pytest` via the workspace's `uv` environment. Packages with their own runtime deps (numpy, pandas, sklearn) will need per-package venvs — deferred (see Cons).

## Consequences

### Positive

- Audit chain extends one link up the validation pipeline: registry-record → pipeline-manifest → package-manifest. Each link is signature-covered and drift-gated.
- Collect-all-findings ergonomics: developers see every issue per `validate` run.
- No new IAM / bucket / Terraform; Sprint-4 ships zero infrastructure changes.
- Cross-link drift symmetry: bumping a package's manifest forces pipeline regeneration via `upstream_refs[0].digest`. Forgetting to regenerate either side fails CI's `git diff --exit-code`.
- Code Intake's package manifest reuses Sprint 3's signer module unchanged — only `payload.type` differs from the pipeline manifest.

### Negative (accepted)

- **SAS validation is structural-only.** Real SAS linting (parsing PROC bodies, checking variable types) needs ABSA's SAS runtime + Docker container infrastructure — deferred to Phase 3. The Sprint-4 structural checker catches "empty file" and "unbalanced PROC/RUN" but cannot catch logical errors inside a SAS block.
- **Package Python must be workspace-toolchain-compatible.** Real Phase-3 packages with isolated runtime deps will need per-package venvs (`uv venv` per package) or container-based isolation. The Sprint-4 framework supports this with a future per-checker config flag.
- **PIR column extraction is crude.** Only `data["col"]` (Subscript on Name) and `data.col` (Attribute on Name) patterns are detected. F-strings, aliases, and dynamic dispatch are not. Real Phase-3 packages with more complex parsing can opt into a stricter mode via a future PIR config flag.
- **`SCH002`/`SCH003` (artifact hash mismatch) is enforced at manifest-build time** rather than per-checker. The schema checker validates the config's shape; the manifest builder computes fresh hashes from disk and the orchestrator wires the two concerns together.

## Alternatives considered

1. **Monolithic single checker** — rejected. Hard to extend, hard to test individually, no per-checker timing.
2. **Embedding upstream signature in pipeline manifest** — rejected. Complicates two-pass CI signing (pipeline manifest would need to be regenerated after the upstream package is signed); digest-plus-offline-verify is sufficient.
3. **Per-package venvs in Sprint 4** — deferred. Needs `uv venv` orchestration per package; current workspace-toolchain approach works for synthetic Phase-2 packages. Phase 3 will revisit when real packages with isolated deps arrive.
4. **Real SAS linting via a Docker SAS runtime** — deferred. SAS license and runtime concerns; structural-only is the right depth for Phase 2.
5. **Decoupled chain (no `upstream_refs[]`)** — rejected. Weakens the audit story; a registry record in isolation can't prove which validated package its pipeline descended from.

## Rotation / evolution

The Code Intake schema is versioned via `schema_version` (currently 1). A future breaking change (e.g. richer artefact metadata, stricter PIR types) bumps `schema_version` and ships alongside a migration note. Existing signed manifests at `schema_version=1` remain verifiable indefinitely — the verifier doesn't need to understand the payload shape, only the canonical bytes the signature is over.
```

- [ ] **Step 3: Edit ADR-0006**

Open `docs/adr/0006-contract-strategy-json-schema-canonical.md`. Find the list of contracts the package ships (likely a bullet list of schema names). Add two lines:

```diff
+- `package-manifest-payload.schema.json` — Code Intake payload (Sprint 4)
+- `pir-mapping.schema.json` — PIR mapping shape (Sprint 4)
```

If the file doesn't have an obvious list to extend, add a section at the end:

```markdown
## Sprint 4 additions (2026-06-04)

Two new schemas join the canonical set:
- `package-manifest-payload.schema.json` — the envelope payload type Code Intake emits for productized packages. See [ADR-0010](0010-productized-package-contract.md).
- `pir-mapping.schema.json` — describes the shape of `pir.yaml` shipped inside packages.

Both follow the existing canonical-encoding rules (sort_keys + 2-space indent + UTF-8 + trailing newline) and are regenerated into `models.py` via the existing `regenerate-models.sh` script.
```

- [ ] **Step 4: Create `code-intake/README.md`**

```markdown
# `code-intake`

Validates productized packages (SAS + Python + PIR + tests + model_config) and emits a signed package manifest. The third stage of the Phase-2 audit chain.

See [Sprint 4 spec](../docs/superpowers/specs/2026-06-04-absa-exl-phase-2-sprint-4-code-intake-design.md), [ADR-0010](../docs/adr/0010-productized-package-contract.md).

## Subcommands

| Command | Use case |
|---|---|
| `code-intake validate --package <path> [--strict] [--json]` | Run all five checkers; print summary; exit 0/1. `--strict` flips warnings into errors. `--json` emits a single JSON object on stdout. |
| `code-intake generate-manifest --package <path> [--strict]` | Run validate first; on success write `<path>/manifest.json` with UNSIGNED sentinels Sprint 3's signer fills in CI. Preserves `generated_at`/`signed_at` from an existing manifest for byte-stable re-renders. |

## Library API

```python
from code_intake.orchestrator import validate
from code_intake.manifest import build_package_payload, build_package_envelope
from code_intake.package_config import load_package_config
```

All functions are pure — no AWS calls, no network. Sprint 3's `manifest-signer` owns the AWS path.

## The five checkers

| Checker | Validates | Failure codes |
|---|---|---|
| `static_python` | ruff check + mypy --strict + pytest --collect-only against `<package>/python/` | PY001 ruff · PY002 mypy · PY003 pytest discovery |
| `static_sas`    | Files in `<package>/sas/` are non-empty and have balanced PROC/RUN (structural only) | SAS002 empty · SAS003 PROC/RUN imbalance |
| `schema`        | `<package>/model_config.yaml` validates against `package-manifest-payload.schema.json` | SCH001 schema validation |
| `tests`         | `pytest <package>/python/tests/` exits 0 | TST001 collection · TST002 ≥1 test failed |
| `pir`           | `<package>/pir.yaml` validates against `pir-mapping.schema.json` AND every column referenced by Python is in `pir.inputs[]` | PIR001 schema · PIR002 unmapped column |

The orchestrator runs all five and **never short-circuits**. A checker that crashes is wrapped as a single `<CHECKER>999` finding rather than propagating the exception.

## Architecture

| Module | Responsibility |
|---|---|
| `code_intake.checkers.base`     | Shared `Checker` protocol + `Finding`/`CheckResult` dataclasses |
| `code_intake.checkers.*`        | Five concrete checkers (one file each) |
| `code_intake.orchestrator`      | Runs all five; collect-all-findings; never crashes; records timing |
| `code_intake.package_config`    | Loader + schema validation for the package's model_config.yaml |
| `code_intake.manifest`          | Build payload + UNSIGNED envelope (Sprint 3's signer fills sentinels) |
| `code_intake.cli`               | Click CLI exposing `validate` and `generate-manifest` |
| `code_intake.errors`            | `CodeIntakeError`, `ValidationError`, `PackageConfigError` |

## Testing

```bash
uv run pytest code-intake/tests
```

The end-to-end test (`test_e2e_track_a.py`) exercises the full Code Intake → Pipeline Factory → signer → mock registrar chain inside one moto context — proving the CI flow works without AWS credentials.
```

- [ ] **Step 5: Verify all three docs render and links resolve**

```bash
# Spot-check the ADR-0010 file exists and references existing ADRs
test -f docs/adr/0010-productized-package-contract.md
grep -q "ADR-0003" docs/adr/0010-productized-package-contract.md
grep -q "ADR-0009" docs/adr/0010-productized-package-contract.md
grep -q "code-intake" code-intake/README.md
echo "OK"
```

Expected: `OK`.

- [ ] **Step 6: Full workspace pytest + ruff + format + mypy (sanity)**

```bash
uv run pytest -q
uv run ruff check
uv run ruff format --check
```

Expected: all green at 193 passes.

- [ ] **Step 7: Commit**

```bash
git add docs/adr/0010-productized-package-contract.md \
        docs/adr/0006-contract-strategy-json-schema-canonical.md \
        code-intake/README.md
git commit -m "docs(adr): add ADR-0010 + code-intake README + ADR-0006 edit

ADR-0010 (Productized Package Contract) locks the Sprint 4 design:
- Git-tracked packages/<name>/<version>/ layout with five artefact groups
- Two new schemas in platform-contracts (package-manifest-payload +
  pir-mapping)
- Five checkers, collect-all-findings, never short-circuit
- Chain-of-custody via upstream_refs[], digest-only, offline-verifiable
- Reuses Sprint 3's IAM role for signing (no new infrastructure)
- Structural-only SAS posture (Phase 3 deferral) and workspace-toolchain
  -compatible Python assumption (Phase 3 deferral for per-package venvs)
- Crude AST-based PIR column extraction (Phase 3 deferral for stricter
  parsing)

ADR-0006 gains a Sprint 4 additions section listing the two new schemas.

code-intake README documents the two CLI subcommands, the library API,
the five checkers + their failure codes, the architecture decomposition,
and how to run the test suite.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 17: Final verification + PR

**Why:** Acceptance criteria check from spec §14 before opening the PR.

- [ ] **Step 1: Full test suite**

```bash
uv run pytest -q
```

Expected: 193 passed (Sprint 1+2+3 baseline 129 + Sprint 4's new tests). Re-run produces the same count deterministically.

- [ ] **Step 2: Ruff + ruff format + mypy clean across the workspace**

```bash
uv run ruff check
uv run ruff format --check
uv run mypy platform-contracts/src pipeline-factory/src manifest-signer/src code-intake/src registry/api/src
```

Expected: All checks passed. Success: no issues found.

- [ ] **Step 3: Terraform validate matrix (no new TF in Sprint 4, just confirm nothing broke)**

```bash
for stack in terraform/modules/signing-foundation terraform/envs/prod/signing terraform/envs/prod/registry; do
  echo "--- $stack ---"
  (cd "$stack" && terraform init -backend=false -no-color && terraform validate -no-color) 2>&1 | tail -3
done
```

Expected: each reports `Success! The configuration is valid.`

- [ ] **Step 4: actionlint on changed workflows**

```bash
actionlint .github/workflows/code-intake.yml .github/workflows/pipeline-factory.yml
```

Expected: no errors.

- [ ] **Step 5: Spec §14 acceptance criteria check (manual tick)**

Manually confirm each item:

- [ ] All Code Intake unit tests + the e2e test pass (Step 1).
- [ ] Full workspace test suite passes — Sprint 1+2+3 tests still green after the additive changes.
- [ ] `code-intake validate` on `packages/credit-risk-pd/1.0.0/` exits 0; on each `broken_*` fixture exits 1 with the expected codes.
- [ ] `code-intake generate-manifest` produces a `manifest.json` that passes the `package-manifest-payload` schema.
- [ ] `pipeline-factory.generator` resolves the `upstream_package` block to the correct `upstream_refs[]` entry; regenerated pipeline manifest is byte-stable across repeated invocations.
- [ ] The e2e test asserts the chain is consistent at every link.
- [ ] actionlint passes on the new + modified workflows.
- [ ] ADR-0010 committed; ADR-0006 has the minor edit.
- [ ] READMEs exist for `code-intake/` and `packages/credit-risk-pd/1.0.0/`.

- [ ] **Step 6: Final code-reviewer subagent**

Dispatch a `superpowers:code-reviewer` subagent over the full sprint diff (`main..HEAD`). Address any blocking findings before opening the PR. Non-blocking ones go into the PR description as Known Limitations.

- [ ] **Step 7: Push the branch and open the PR**

```bash
git push -u origin phase-2/sprint-4-code-intake
gh pr create --title "Phase 2 Sprint 4: Code Intake + First Track A Run" --body "$(cat <<'EOF'
## Summary

Closes Phase 2. Adds the third stage of the audit chain (Code Intake) plus the worked-example wire-through that proves all four subsystems (Code Intake, Pipeline Factory, signer, registrar) agree end-to-end.

- New uv workspace member `code-intake/` with 5 checkers (real Python via ruff+mypy+pytest; structural-only SAS; real schema/tests/PIR), an orchestrator that collects all findings and never short-circuits, and a Click CLI (`validate`, `generate-manifest`).
- Two new schemas in `platform-contracts`: `package-manifest-payload.schema.json` and `pir-mapping.schema.json`. Additive `upstream_refs[]` field on the pipeline manifest schema; additive `upstream_package` block on the model-config schema.
- Pipeline-factory extension: optional `upstream_package: {name, version}` in `model_config.yaml`; pure-function `upstream_resolver` embeds the cross-link in the pipeline manifest at gen-time.
- Worked example `packages/credit-risk-pd/1.0.0/` (synthetic SAS + Python + tests + PIR + model_config + generated manifest). Existing `pipelines/credit-risk-pd/1.0.0/manifest.json` regenerated with `upstream_refs[]` populated.
- New `code-intake.yml` CI workflow (validate + generate-manifest drift gate). `pipeline-factory.yml` extended: `packages/**` added to triggers; sign step loops over both `packages/` and `pipelines/` roots.
- ADR-0010 (Productized Package Contract); ADR-0006 minor edit.

## Spec & plan

- [Spec](docs/superpowers/specs/2026-06-04-absa-exl-phase-2-sprint-4-code-intake-design.md)
- [Plan](docs/superpowers/plans/2026-06-04-absa-exl-phase-2-sprint-4-code-intake.md)

## Test plan

- [ ] CI green on this PR (drift-gates, validate-and-generate, terraform-validate, python-validate, actionlint, tfsec all run; sign + register jobs no-op in dev where secrets are unset)
- [ ] Reviewer confirms ADR-0010 captures the design rationale (especially the structural-SAS / workspace-toolchain-Python compromises)
- [ ] Reviewer verifies the end-to-end test exercises sign + verify-online + verify-offline against both manifests
- [ ] Reviewer confirms the chain digest matches: `packages/credit-risk-pd/1.0.0/manifest.json:.digest` equals `pipelines/credit-risk-pd/1.0.0/manifest.json:.payload.upstream_refs[0].digest`

## Known limitations (intentional, deferred to Phase 3)

- SAS validation is structural-only — real SAS linting needs ABSA's SAS runtime + Docker. ADR-0010 documents.
- Package Python must be workspace-toolchain-compatible — real Phase-3 packages with isolated deps will need per-package venvs.
- PIR column extraction uses crude AST patterns (`data["col"]` / `data.col`) — Phase-3 packages can opt into stricter parsing.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Return the PR URL.

- [ ] **Step 8: Branch finalisation**

Hand off to `superpowers:finishing-a-development-branch` to walk the standard options (merge locally / push and create PR / keep as-is / discard). The PR was already opened in Step 7 if `gh pr create` was chosen.

---

## Self-review checklist (controller-side, run before dispatching tasks)

Run through this once before kicking off subagent-driven execution:

- [ ] **Spec coverage.** Every section of the spec (§1–§15) maps to at least one task: §3 scope → T1–T17 collectively; §4 architecture → T11+T12+T13 (the chain); §5 repo layout → T2+T11; §6 checker internals → T3–T7+T8; §7 schemas → T1; §8 pipeline-factory extension → T12; §9 CI → T15; §10 worked example → T11+T13; §11 testing → T3–T8+T14; §12 ADRs → T16; §14 acceptance criteria → T17.
- [ ] **No placeholders.** Every code block is complete; no `TBD`, `TODO`, `implement later`, or `# ...` ellipses where real code is required.
- [ ] **Type consistency.**
  - `Finding` and `CheckResult` field names match across `base.py`, all five checkers, the orchestrator, and the manifest builder.
  - `static_python.StaticPythonChecker`, `static_sas.StaticSasChecker`, etc. — exact class names match the import statements in `orchestrator.py`.
  - `upstream_resolver.resolve_upstream_refs` signature in T12 matches the call site in T12 step 7.
  - `build_package_payload`/`build_package_envelope` names in T9 match the imports in T10's cli.py.
- [ ] **Refactor depends-first.** T1 (schemas) precedes everything; T2 (scaffold + Checker protocol) precedes T3–T8 (checkers); T9 (manifest builder) precedes T10 (CLI); T11 (worked example) precedes T13 (pipeline-factory wire-up) which precedes T14 (e2e test).
- [ ] **Chain digest match is tested in three places.** T13 step 3 (shell assertion at gen-time), T14 step 1 (in-test assertion before signing), and T14 step 1 again (in-test assertion AFTER signing — proves the signer doesn't move the digest field).
- [ ] **CI lessons applied.** T2, T3, T5, T6, T7, T8, T9, T10 all include both `ruff check` AND `ruff format --check` in their verification step (Sprint 3 CI failed because the formatter check was missed locally).

---

## Execution handoff

Plan complete and saved to [docs/superpowers/plans/2026-06-04-absa-exl-phase-2-sprint-4-code-intake.md](2026-06-04-absa-exl-phase-2-sprint-4-code-intake.md). Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task with two-stage review (spec compliance, then code quality) between tasks. Same disciplined pattern that landed Sprints 1, 2, and 3.

**2. Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.

**Which approach?**
