# Phase 2 Sprint 2 — Pipeline Factory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a hand-authored `model_config.yaml` into a complete, registry-routed scoring pipeline. Build the Python `generate-pipeline` CLI (validate / generate / register), the Jinja2 templates for `standard-batch` and `scalable-batch` tiers, the `pipeline-manifest-payload` shared contract, and the CI flow that POSTs the registration body to the Registry API (preserving the 2.1 approval gate).

**Architecture:** A new `pipeline-factory` uv workspace member depending on `platform-contracts`. The generator validates the YAML against the canonical JSON Schema, renders Jinja2 templates into `pipelines/<name>/<version>/{statemachine.json, registration.json, manifest.json, terraform/main.tf}` (canonicalised JSON sorted-keys; `.tf` passed through `terraform fmt -`), and the manifest carries sentinel placeholder values so it passes envelope validation while being detectable as "unsigned" via `is_signed()`. The `register` subcommand POSTs the registration body to the Registry API with SigV4; 409 is treated as idempotent success, 5xx triggers exponential backoff. Generated artifacts are committed; CI re-runs the generator on PRs as a drift gate (matching the Pydantic drift gate in 2.1).

**Tech Stack:** Python 3.12, uv workspace member, Click (CLI), Jinja2 (templates), PyYAML (config), httpx + boto3 SigV4 (API call), pytest + pytest-httpx + moto for tests, Terraform 1.14.9 (`terraform fmt -` for HCL canonicalisation), GitHub Actions OIDC for CI auth.

**Spec:** `docs/superpowers/specs/2026-05-26-absa-exl-phase-2-sprint-2-pipeline-factory-design.md`

**Conventions:**
- Branch: `phase-2/sprint-2-pipeline-factory` (already created; the spec is committed on it).
- All commits use Conventional Commit subjects (CI enforces).
- Templates live as **package data** under `pipeline-factory/src/pipeline_factory/templates/` (refining spec §4's top-level `templates/`) so Jinja's `PackageLoader` finds them and they ship in the wheel.
- Tests live at `pipeline-factory/tests/`; mypy strict applies to `pipeline-factory/src` (mirroring 2.1).
- Run Python commands from the repo root via `uv run …`. Run `terraform` commands from the relevant directory.

---

### Task 1: `pipeline-factory` workspace member

**Files:**
- Modify: `pyproject.toml` (root) — add `pipeline-factory` to `[tool.uv.workspace] members` and `[tool.pytest.ini_options] testpaths`
- Create: `pipeline-factory/pyproject.toml`
- Create: `pipeline-factory/src/pipeline_factory/__init__.py`
- Create: `pipeline-factory/src/pipeline_factory/py.typed`
- Create: `pipeline-factory/src/pipeline_factory/cli.py` (minimal Click group; subcommands added in Tasks 9–10)
- Create: `pipeline-factory/tests/__init__.py`
- Create: `pipeline-factory/tests/test_smoke.py`

- [ ] **Step 1: Write the failing smoke test**

`pipeline-factory/tests/test_smoke.py`:
```python
from click.testing import CliRunner

import pipeline_factory
from pipeline_factory.cli import main


def test_package_imports() -> None:
    assert pipeline_factory.__name__ == "pipeline_factory"


def test_cli_help_runs() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Pipeline Factory" in result.output
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest pipeline-factory/tests/test_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: pipeline_factory` (or uv errors that the member isn't configured).

- [ ] **Step 3: Add the new workspace member to the root `pyproject.toml`**

In the root `pyproject.toml`, change:
```toml
[tool.uv.workspace]
members = ["platform-contracts", "registry/api"]
```
to:
```toml
[tool.uv.workspace]
members = ["platform-contracts", "registry/api", "pipeline-factory"]
```

And change:
```toml
[tool.pytest.ini_options]
addopts = "-q"
testpaths = ["platform-contracts/tests", "registry/api/tests"]
```
to:
```toml
[tool.pytest.ini_options]
addopts = "-q"
testpaths = ["platform-contracts/tests", "registry/api/tests", "pipeline-factory/tests"]
```

- [ ] **Step 4: Create the member `pyproject.toml`**

`pipeline-factory/pyproject.toml`:
```toml
[project]
name = "pipeline-factory"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "platform-contracts",
    "click>=8.1",
    "jinja2>=3.1",
    "pyyaml>=6",
    "httpx>=0.27",
    "boto3>=1.34",
    "botocore>=1.34",
]

[project.scripts]
generate-pipeline = "pipeline_factory.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/pipeline_factory"]

[tool.uv.sources]
platform-contracts = { workspace = true }
```

- [ ] **Step 5: Create the package skeleton**

`pipeline-factory/src/pipeline_factory/__init__.py`:
```python
"""ABSA x EXL Pipeline Factory — turns model_config.yaml into a scoring pipeline."""
```

`pipeline-factory/src/pipeline_factory/py.typed` — empty file (zero bytes).

`pipeline-factory/src/pipeline_factory/cli.py` (minimal — Tasks 9–10 add subcommands):
```python
from __future__ import annotations

import click


@click.group()
def main() -> None:
    """ABSA x EXL Pipeline Factory generator (validate | generate | register)."""


if __name__ == "__main__":  # pragma: no cover
    main()
```

`pipeline-factory/tests/__init__.py` — empty file.

- [ ] **Step 6: Add the dev-only test dependency**

The new tests will use `pytest-httpx` (Task 10) for the registration mock. Add it to the root dev group. In `pyproject.toml`, change:
```toml
[dependency-groups]
dev = [
    "pytest>=8",
    "mypy>=1.10",
    "ruff>=0.6",
    "moto[dynamodb]>=5",
    "datamodel-code-generator>=0.25",
    "httpx>=0.27",
    "types-jsonschema",
]
```
to:
```toml
[dependency-groups]
dev = [
    "pytest>=8",
    "mypy>=1.10",
    "ruff>=0.6",
    "moto[dynamodb]>=5",
    "datamodel-code-generator>=0.25",
    "httpx>=0.27",
    "pytest-httpx>=0.30",
    "types-jsonschema",
    "types-PyYAML",
]
```

- [ ] **Step 7: Sync and run the smoke test**

Run: `uv sync` then `uv run pytest pipeline-factory/tests/test_smoke.py -v`
Expected: `uv.lock` updates; both tests PASS.

- [ ] **Step 8: Verify lint and types are clean**

Run: `uv run ruff check .` and `uv run mypy platform-contracts/src registry/api/src pipeline-factory/src`
Expected: both pass.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml uv.lock pipeline-factory/
git commit -m "chore(py): add pipeline-factory workspace member"
```

---

### Task 2: extend `model-config` schema for code versions

**Files:**
- Modify: `platform-contracts/src/platform_contracts/schemas/model-config.schema.json` — add two optional fields
- Modify: `platform-contracts/src/platform_contracts/models.py` — regenerated by the script (do NOT hand-edit)
- Modify: `platform-contracts/tests/test_model_config_schema.py` — add tests for the new fields

- [ ] **Step 1: Write the failing tests for the new fields**

Append to `platform-contracts/tests/test_model_config_schema.py` (preserve the existing tests; add at the bottom):
```python
def test_with_code_versions_passes() -> None:
    validate("model-config", {**VALID, "sas_code_version": "sas-2026.04.1", "inference_code_version": "py-2026.04.1"})


def test_empty_sas_code_version_fails() -> None:
    with pytest.raises(ValidationError):
        validate("model-config", {**VALID, "sas_code_version": ""})


def test_empty_inference_code_version_fails() -> None:
    with pytest.raises(ValidationError):
        validate("model-config", {**VALID, "inference_code_version": ""})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest platform-contracts/tests/test_model_config_schema.py -v`
Expected: `test_with_code_versions_passes` FAILS (the schema's `additionalProperties: false` rejects the new keys) and the two empty-string tests would also fail because empty strings would currently be accepted as `additionalProperties` (they fail differently — confirms missing schema entries).

- [ ] **Step 3: Add the two optional fields to the schema**

Edit `platform-contracts/src/platform_contracts/schemas/model-config.schema.json`. After the `"registry_lookup_key": { "type": "string" }` line in the `properties` object, add (note the leading comma added to the prior line):
```json
"registry_lookup_key": { "type": "string" },
"sas_code_version": { "type": "string", "minLength": 1 },
"inference_code_version": { "type": "string", "minLength": 1 }
```

The schema's `required` array is **not** modified — these stay optional in the schema (required at register time, enforced by the generator).

- [ ] **Step 4: Regenerate the Pydantic models**

Run: `bash platform-contracts/regenerate-models.sh`
Expected: `platform-contracts/src/platform_contracts/models.py` updates; `ModelConfig` now has `sas_code_version` and `inference_code_version` as `Optional[str]` (or equivalent).

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest platform-contracts -v`
Expected: all platform-contracts tests pass, including the three new ones; full suite count increases by 3.

Run: `uv run mypy platform-contracts/src`
Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add platform-contracts/src/platform_contracts/schemas/model-config.schema.json platform-contracts/src/platform_contracts/models.py platform-contracts/tests/test_model_config_schema.py
git commit -m "feat(contracts): add optional sas/inference_code_version to model-config"
```

---

### Task 3: `pipeline-manifest-payload` shared schema

**Files:**
- Create: `platform-contracts/src/platform_contracts/schemas/pipeline-manifest-payload.schema.json`
- Modify: `platform-contracts/src/platform_contracts/models.py` (regenerated)
- Create: `platform-contracts/tests/test_pipeline_manifest_payload_schema.py`
- Modify: `platform-contracts/tests/test_models_match_schema.py` — add the new schema to CASES

- [ ] **Step 1: Write the failing schema test**

`platform-contracts/tests/test_pipeline_manifest_payload_schema.py`:
```python
import pytest
from jsonschema import ValidationError

from platform_contracts.loader import validate

VALID = {
    "schema_version": 1,
    "generator_version": "0.1.0",
    "model_name": "credit-risk-pd",
    "version": "1.0.0",
    "tier": "standard",
    "generated_at": "2026-05-26T06:00:00+00:00",
    "artifact_hashes": {
        "statemachine_sha256": "a" * 64,
        "terraform_sha256": "b" * 64,
        "model_config_sha256": "c" * 64,
        "registration_sha256": "d" * 64,
    },
}


def test_valid_payload_passes() -> None:
    validate("pipeline-manifest-payload", VALID)


def test_bad_tier_enum_fails() -> None:
    with pytest.raises(ValidationError):
        validate("pipeline-manifest-payload", {**VALID, "tier": "realtime"})


def test_missing_artifact_hash_fails() -> None:
    bad = {**VALID, "artifact_hashes": {"statemachine_sha256": "a" * 64}}
    with pytest.raises(ValidationError):
        validate("pipeline-manifest-payload", bad)


def test_short_hash_fails() -> None:
    bad = {**VALID, "artifact_hashes": {**VALID["artifact_hashes"], "statemachine_sha256": "abc"}}
    with pytest.raises(ValidationError):
        validate("pipeline-manifest-payload", bad)


def test_additional_property_fails() -> None:
    with pytest.raises(ValidationError):
        validate("pipeline-manifest-payload", {**VALID, "surprise": "x"})
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest platform-contracts/tests/test_pipeline_manifest_payload_schema.py -v`
Expected: FAIL with `KeyError: unknown schema: 'pipeline-manifest-payload'`.

- [ ] **Step 3: Write the schema**

`platform-contracts/src/platform_contracts/schemas/pipeline-manifest-payload.schema.json`:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://contracts.absa-exl.internal/pipeline-manifest-payload/v1.json",
  "title": "PipelineManifestPayload",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version", "generator_version", "model_name", "version",
    "tier", "generated_at", "artifact_hashes"
  ],
  "properties": {
    "schema_version": { "type": "integer", "const": 1 },
    "generator_version": { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$" },
    "model_name": { "type": "string", "pattern": "^[a-z][a-z0-9-]{2,63}$" },
    "version": { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$" },
    "tier": { "type": "string", "enum": ["standard", "scalable"] },
    "generated_at": { "type": "string", "format": "date-time" },
    "artifact_hashes": {
      "type": "object",
      "additionalProperties": false,
      "required": ["statemachine_sha256", "terraform_sha256", "model_config_sha256", "registration_sha256"],
      "properties": {
        "statemachine_sha256": { "type": "string", "pattern": "^[0-9a-f]{64}$" },
        "terraform_sha256": { "type": "string", "pattern": "^[0-9a-f]{64}$" },
        "model_config_sha256": { "type": "string", "pattern": "^[0-9a-f]{64}$" },
        "registration_sha256": { "type": "string", "pattern": "^[0-9a-f]{64}$" }
      }
    }
  }
}
```

- [ ] **Step 4: Regenerate the Pydantic models**

Run: `bash platform-contracts/regenerate-models.sh`
Expected: `models.py` updates; `PipelineManifestPayload` class is added.

- [ ] **Step 5: Extend the parity test**

Edit `platform-contracts/tests/test_models_match_schema.py`. Change:
```python
CASES = [
    ("model-config", "ModelConfig"),
    ("registry-record", "RegistryRecord"),
    ("manifest-envelope", "ManifestEnvelope"),
]
```
to:
```python
CASES = [
    ("model-config", "ModelConfig"),
    ("registry-record", "RegistryRecord"),
    ("manifest-envelope", "ManifestEnvelope"),
    ("pipeline-manifest-payload", "PipelineManifestPayload"),
]
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest platform-contracts -v`
Expected: all platform-contracts tests pass; new schema tests included (5 new) and the parity test now runs 4 parametrized cases.

Run: `uv run mypy platform-contracts/src`
Expected: pass.

- [ ] **Step 7: Verify drift gate is byte-stable**

Run: `bash platform-contracts/regenerate-models.sh` then `git diff --exit-code platform-contracts/src/platform_contracts/models.py`
Expected: exit code 0 (no diff after re-running).

- [ ] **Step 8: Commit**

```bash
git add platform-contracts/src/platform_contracts/schemas/pipeline-manifest-payload.schema.json platform-contracts/src/platform_contracts/models.py platform-contracts/tests/test_pipeline_manifest_payload_schema.py platform-contracts/tests/test_models_match_schema.py
git commit -m "feat(contracts): add pipeline-manifest-payload JSON Schema"
```

---

### Task 4: hashing + canonicalisation

**Files:**
- Create: `pipeline-factory/src/pipeline_factory/hashing.py`
- Create: `pipeline-factory/tests/test_hashing.py`

- [ ] **Step 1: Write the failing tests**

`pipeline-factory/tests/test_hashing.py`:
```python
import json

import pytest

from pipeline_factory.hashing import (
    canonical_json,
    sha256_of_bytes,
    sha256_of_json,
    sha256_of_text,
    terraform_fmt,
)


def test_canonical_json_sorts_keys() -> None:
    out = canonical_json({"b": 1, "a": 2})
    assert out == b'{\n  "a": 2,\n  "b": 1\n}\n'


def test_canonical_json_is_deterministic() -> None:
    a = canonical_json({"z": [3, 2, 1], "y": {"q": 1, "p": 2}})
    b = canonical_json({"y": {"p": 2, "q": 1}, "z": [3, 2, 1]})
    assert a == b


def test_sha256_of_json_is_stable() -> None:
    h1 = sha256_of_json({"a": 1, "b": 2})
    h2 = sha256_of_json({"b": 2, "a": 1})
    assert h1 == h2
    assert len(h1) == 64


def test_sha256_of_text_matches_bytes() -> None:
    assert sha256_of_text("hello") == sha256_of_bytes(b"hello")


def test_terraform_fmt_canonicalises() -> None:
    messy = 'variable    "x"   {\n  type=string\n}\n'
    out = terraform_fmt(messy)
    # `terraform fmt -` normalises whitespace and alignment
    assert "variable" in out
    assert "string" in out
    # idempotent on re-application
    assert terraform_fmt(out) == out
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest pipeline-factory/tests/test_hashing.py -v`
Expected: FAIL — `ModuleNotFoundError: pipeline_factory.hashing`.

- [ ] **Step 3: Write the module**

`pipeline-factory/src/pipeline_factory/hashing.py`:
```python
from __future__ import annotations

import hashlib
import json
import subprocess
from typing import Any


def canonical_json(obj: Any) -> bytes:
    """JSON-serialise *obj* deterministically (sorted keys, 2-space indent, UTF-8, trailing newline)."""
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"


def sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_of_text(text: str) -> str:
    return sha256_of_bytes(text.encode("utf-8"))


def sha256_of_json(obj: Any) -> str:
    return sha256_of_bytes(canonical_json(obj))


def terraform_fmt(text: str) -> str:
    """Run ``terraform fmt -`` on *text* and return the formatted output.

    Requires the ``terraform`` binary on PATH.
    """
    completed = subprocess.run(
        ["terraform", "fmt", "-"],
        input=text,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest pipeline-factory/tests/test_hashing.py -v`
Expected: 5 tests PASS.

Run: `uv run mypy pipeline-factory/src`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline-factory/src/pipeline_factory/hashing.py pipeline-factory/tests/test_hashing.py
git commit -m "feat(factory): add canonical-json + sha256 + terraform-fmt helpers"
```

---

### Task 5: manifest builder

**Files:**
- Create: `pipeline-factory/src/pipeline_factory/manifest.py`
- Create: `pipeline-factory/tests/test_manifest.py`

- [ ] **Step 1: Write the failing tests**

`pipeline-factory/tests/test_manifest.py`:
```python
from datetime import UTC, datetime

from platform_contracts.loader import validate

from pipeline_factory.manifest import (
    UNSIGNED_KEY_ARN,
    UNSIGNED_SIGNATURE,
    build_envelope,
    build_payload,
    is_signed,
)


def _hashes() -> dict[str, str]:
    return {
        "statemachine_sha256": "a" * 64,
        "terraform_sha256": "b" * 64,
        "model_config_sha256": "c" * 64,
        "registration_sha256": "d" * 64,
    }


def test_payload_validates_against_schema() -> None:
    payload = build_payload(
        model_name="credit-risk-pd",
        version="1.0.0",
        tier="standard",
        artifact_hashes=_hashes(),
        generated_at="2026-05-26T06:00:00+00:00",
    )
    validate("pipeline-manifest-payload", payload)


def test_envelope_validates_against_schema() -> None:
    payload = build_payload(
        model_name="credit-risk-pd",
        version="1.0.0",
        tier="standard",
        artifact_hashes=_hashes(),
        generated_at="2026-05-26T06:00:00+00:00",
    )
    envelope = build_envelope(payload=payload, subject_ref="pipelines/credit-risk-pd/1.0.0/")
    validate("manifest-envelope", envelope)


def test_unsigned_is_detectable() -> None:
    payload = build_payload(
        model_name="credit-risk-pd",
        version="1.0.0",
        tier="standard",
        artifact_hashes=_hashes(),
        generated_at="2026-05-26T06:00:00+00:00",
    )
    envelope = build_envelope(payload=payload, subject_ref="pipelines/credit-risk-pd/1.0.0/")
    assert envelope["signature"] == UNSIGNED_SIGNATURE
    assert envelope["signing_key_arn"] == UNSIGNED_KEY_ARN
    assert is_signed(envelope) is False


def test_is_signed_true_when_signature_overwritten() -> None:
    payload = build_payload(
        model_name="credit-risk-pd",
        version="1.0.0",
        tier="standard",
        artifact_hashes=_hashes(),
        generated_at="2026-05-26T06:00:00+00:00",
    )
    envelope = build_envelope(payload=payload, subject_ref="pipelines/credit-risk-pd/1.0.0/")
    envelope["signature"] = "REAL_BASE64_SIG_VALUE=="
    assert is_signed(envelope) is True
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest pipeline-factory/tests/test_manifest.py -v`
Expected: FAIL — `ModuleNotFoundError: pipeline_factory.manifest`.

- [ ] **Step 3: Write the module**

`pipeline-factory/src/pipeline_factory/manifest.py`:
```python
from __future__ import annotations

from datetime import UTC, datetime
from importlib.metadata import version as _pkg_version
from typing import Any

from .hashing import canonical_json, sha256_of_bytes

UNSIGNED_SIGNATURE = "UNSIGNED"
UNSIGNED_KEY_ARN = "arn:aws:kms:placeholder:000000000000:key/unsigned"
UNSIGNED_SIGNING_ALGORITHM = "RSASSA_PKCS1_V1_5_SHA_256"
UNSIGNED_PRINCIPAL = "unsigned"


def _generator_version() -> str:
    try:
        return _pkg_version("pipeline-factory")
    except Exception:  # pragma: no cover — fallback for source checkout without install
        return "0.1.0"


def build_payload(
    *,
    model_name: str,
    version: str,
    tier: str,
    artifact_hashes: dict[str, str],
    generated_at: str | None = None,
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
    }


def build_envelope(*, payload: dict[str, Any], subject_ref: str) -> dict[str, Any]:
    """Wrap *payload* in a manifest-envelope. Unsigned by design — 2.3 fills the signature fields."""
    digest = sha256_of_bytes(canonical_json(payload))
    return {
        "digest": digest,
        "digest_algorithm": "SHA-256",
        "signature": UNSIGNED_SIGNATURE,
        "signing_key_arn": UNSIGNED_KEY_ARN,
        "signing_algorithm": UNSIGNED_SIGNING_ALGORITHM,
        "subject_type": "pipeline",
        "subject_ref": subject_ref,
        "signed_at": datetime.now(UTC).isoformat(),
        "signer_principal": UNSIGNED_PRINCIPAL,
        "payload": payload,
    }


def is_signed(envelope: dict[str, Any]) -> bool:
    """Return True iff the envelope's signature has been overwritten with a real value."""
    return envelope.get("signature") != UNSIGNED_SIGNATURE
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest pipeline-factory/tests/test_manifest.py -v`
Expected: 4 PASS.

Run: `uv run mypy pipeline-factory/src`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline-factory/src/pipeline_factory/manifest.py pipeline-factory/tests/test_manifest.py
git commit -m "feat(factory): add manifest payload + envelope builder (sentinel unsigned)"
```

---

### Task 6: renderer + `standard-batch` ASL template

**Files:**
- Create: `pipeline-factory/src/pipeline_factory/renderer.py`
- Create: `pipeline-factory/src/pipeline_factory/templates/__init__.py` (empty — makes Python treat it as a sub-package so `PackageLoader` finds it)
- Create: `pipeline-factory/src/pipeline_factory/templates/statemachines/standard-batch.json.j2`
- Create: `pipeline-factory/tests/test_renderer_standard.py`

- [ ] **Step 1: Write the failing test**

`pipeline-factory/tests/test_renderer_standard.py`:
```python
import json

import pytest

from pipeline_factory.renderer import render_statemachine


@pytest.fixture
def context() -> dict:
    return {
        "model": {
            "name": "credit-risk-pd",
            "version": "1.0.0",
            "schedule_cadence": "cron(0 6 * * ? *)",
            "input_schema_ref": "s3://absa-exl/in.json",
            "output_schema_ref": "s3://absa-exl/out.json",
            "pir_doc_ref": "s3://absa-exl/pir.json",
        }
    }


def test_standard_batch_renders_valid_json(context: dict) -> None:
    out = render_statemachine("standard", context)
    parsed = json.loads(out)
    assert parsed["StartAt"] == "ValidateInput"
    expected_states = {
        "ValidateInput", "DataQuality", "Score", "WriteOutput",
        "PIRVariance", "VarianceDecision", "Notify", "BlockDelivery",
        "NotifyFailure", "Fail",
    }
    assert set(parsed["States"]) == expected_states


def test_standard_batch_score_uses_sagemaker_integration(context: dict) -> None:
    parsed = json.loads(render_statemachine("standard", context))
    assert parsed["States"]["Score"]["Resource"] == "arn:aws:states:::sagemaker:createTransformJob.sync"


def test_standard_batch_is_byte_stable(context: dict) -> None:
    a = render_statemachine("standard", context)
    b = render_statemachine("standard", context)
    assert a == b


def test_realtime_tier_refused(context: dict) -> None:
    with pytest.raises(ValueError, match="realtime"):
        render_statemachine("realtime", context)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest pipeline-factory/tests/test_renderer_standard.py -v`
Expected: FAIL — `ModuleNotFoundError: pipeline_factory.renderer`.

- [ ] **Step 3: Write the renderer**

`pipeline-factory/src/pipeline_factory/renderer.py`:
```python
from __future__ import annotations

import json
from typing import Any

from jinja2 import Environment, PackageLoader, StrictUndefined

from .hashing import canonical_json


def _env() -> Environment:
    return Environment(
        loader=PackageLoader("pipeline_factory", "templates"),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=False,
    )


def render_statemachine(tier: str, context: dict[str, Any]) -> str:
    """Render the tier-specific ASL template and return canonical JSON (sorted keys, trailing newline)."""
    if tier == "realtime":
        raise ValueError("realtime tier template is a placeholder; not implemented (brief §6)")
    if tier not in ("standard", "scalable"):
        raise ValueError(f"unknown tier: {tier!r}")
    template = _env().get_template(f"statemachines/{tier}-batch.json.j2")
    rendered = template.render(**context)
    # Validate it's parseable JSON and re-emit canonically.
    parsed = json.loads(rendered)
    return canonical_json(parsed).decode("utf-8")


def render_pipeline_tf(context: dict[str, Any]) -> str:
    """Render the per-pipeline Terraform stub. Caller is responsible for terraform-fmt."""
    template = _env().get_template("terraform/pipeline.tf.j2")
    return template.render(**context)
```

- [ ] **Step 4: Add the empty templates package init**

`pipeline-factory/src/pipeline_factory/templates/__init__.py` — empty file.

- [ ] **Step 5: Write the `standard-batch` template**

`pipeline-factory/src/pipeline_factory/templates/statemachines/standard-batch.json.j2`:
```jinja
{
  "Comment": "{{ model.name }}@{{ model.version }} — standard-batch tier",
  "StartAt": "ValidateInput",
  "States": {
    "ValidateInput": {
      "Type": "Task",
      "Resource": "${ValidateInputLambdaArn}",
      "Parameters": {
        "modelName": "{{ model.name }}",
        "modelVersion": "{{ model.version }}",
        "inputSchemaRef": "{{ model.input_schema_ref }}"
      },
      "Retry": [
        { "ErrorEquals": ["States.TaskFailed"], "IntervalSeconds": 4, "MaxAttempts": 3, "BackoffRate": 2 }
      ],
      "Catch": [
        { "ErrorEquals": ["States.ALL"], "Next": "NotifyFailure", "ResultPath": "$.error" }
      ],
      "Next": "DataQuality"
    },
    "DataQuality": {
      "Type": "Task",
      "Resource": "${GreatExpectationsRunnerArn}",
      "Parameters": {
        "modelName": "{{ model.name }}",
        "modelVersion": "{{ model.version }}"
      },
      "Catch": [
        { "ErrorEquals": ["States.ALL"], "Next": "NotifyFailure", "ResultPath": "$.error" }
      ],
      "Next": "Score"
    },
    "Score": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sagemaker:createTransformJob.sync",
      "Parameters": {
        "TransformJobName.$": "States.Format('{{ model.name }}-{{ model.version }}-{}', $$.Execution.Name)",
        "ModelName": "{{ model.name }}",
        "TransformInput": {
          "DataSource": { "S3DataSource": { "S3DataType": "S3Prefix", "S3Uri.$": "$.inputUri" } }
        },
        "TransformOutput": { "S3OutputPath.$": "$.outputUri" },
        "TransformResources": { "InstanceType": "ml.m5.xlarge", "InstanceCount": 1 }
      },
      "Catch": [
        { "ErrorEquals": ["States.ALL"], "Next": "NotifyFailure", "ResultPath": "$.error" }
      ],
      "Next": "WriteOutput"
    },
    "WriteOutput": {
      "Type": "Task",
      "Resource": "${WriteOutputLambdaArn}",
      "Parameters": {
        "outputSchemaRef": "{{ model.output_schema_ref }}",
        "outputUri.$": "$.outputUri"
      },
      "Next": "PIRVariance"
    },
    "PIRVariance": {
      "Type": "Task",
      "Resource": "${PirCheckerArn}",
      "Parameters": {
        "modelName": "{{ model.name }}",
        "modelVersion": "{{ model.version }}",
        "pirDocRef": "{{ model.pir_doc_ref }}",
        "scoreUri.$": "$.outputUri"
      },
      "Next": "VarianceDecision"
    },
    "VarianceDecision": {
      "Type": "Choice",
      "Choices": [
        { "Variable": "$.varianceWithinThreshold", "BooleanEquals": true, "Next": "Notify" }
      ],
      "Default": "BlockDelivery"
    },
    "Notify": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "${NotifyTopicArn}",
        "Message.$": "$"
      },
      "End": true
    },
    "BlockDelivery": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "${NotifyTopicArn}",
        "Message": {
          "status": "BLOCKED",
          "reason": "PIR variance exceeded threshold",
          "modelName": "{{ model.name }}",
          "modelVersion": "{{ model.version }}"
        }
      },
      "End": true
    },
    "NotifyFailure": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "${NotifyTopicArn}",
        "Message": {
          "status": "FAILED",
          "modelName": "{{ model.name }}",
          "modelVersion": "{{ model.version }}",
          "error.$": "$.error"
        }
      },
      "Next": "Fail"
    },
    "Fail": {
      "Type": "Fail",
      "Cause": "Pipeline failed; see audit log"
    }
  }
}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest pipeline-factory/tests/test_renderer_standard.py -v`
Expected: 4 PASS.

Run: `uv run mypy pipeline-factory/src`
Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add pipeline-factory/src/pipeline_factory/renderer.py pipeline-factory/src/pipeline_factory/templates/__init__.py pipeline-factory/src/pipeline_factory/templates/statemachines/standard-batch.json.j2 pipeline-factory/tests/test_renderer_standard.py
git commit -m "feat(factory): add Jinja renderer + standard-batch ASL template"
```

---

### Task 7: `scalable-batch` + `realtime` placeholder

**Files:**
- Create: `pipeline-factory/src/pipeline_factory/templates/statemachines/scalable-batch.json.j2`
- Create: `pipeline-factory/src/pipeline_factory/templates/statemachines/realtime.json.j2`
- Create: `pipeline-factory/tests/test_renderer_scalable.py`

- [ ] **Step 1: Write the failing test**

`pipeline-factory/tests/test_renderer_scalable.py`:
```python
import json

import pytest

from pipeline_factory.renderer import render_statemachine


@pytest.fixture
def context() -> dict:
    return {
        "model": {
            "name": "fraud-screen",
            "version": "2.1.0",
            "schedule_cadence": "cron(0 6 ? * 2 *)",
            "input_schema_ref": "s3://absa-exl/in.json",
            "output_schema_ref": "s3://absa-exl/out.json",
            "pir_doc_ref": "s3://absa-exl/pir.json",
        }
    }


def test_scalable_batch_renders_valid_json(context: dict) -> None:
    parsed = json.loads(render_statemachine("scalable", context))
    assert parsed["StartAt"] == "ValidateInput"
    assert "Score" in parsed["States"]
    assert parsed["States"]["Score"]["Resource"] == "arn:aws:states:::eks:runJob.sync"


def test_scalable_batch_states_match_standard(context: dict) -> None:
    parsed = json.loads(render_statemachine("scalable", context))
    expected_states = {
        "ValidateInput", "DataQuality", "Score", "WriteOutput",
        "PIRVariance", "VarianceDecision", "Notify", "BlockDelivery",
        "NotifyFailure", "Fail",
    }
    assert set(parsed["States"]) == expected_states


def test_scalable_batch_is_byte_stable(context: dict) -> None:
    a = render_statemachine("scalable", context)
    b = render_statemachine("scalable", context)
    assert a == b
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest pipeline-factory/tests/test_renderer_scalable.py -v`
Expected: FAIL — `jinja2.exceptions.TemplateNotFound: statemachines/scalable-batch.json.j2`.

- [ ] **Step 3: Write the `scalable-batch` template**

`pipeline-factory/src/pipeline_factory/templates/statemachines/scalable-batch.json.j2`:
```jinja
{
  "Comment": "{{ model.name }}@{{ model.version }} — scalable-batch tier",
  "StartAt": "ValidateInput",
  "States": {
    "ValidateInput": {
      "Type": "Task",
      "Resource": "${ValidateInputLambdaArn}",
      "Parameters": {
        "modelName": "{{ model.name }}",
        "modelVersion": "{{ model.version }}",
        "inputSchemaRef": "{{ model.input_schema_ref }}"
      },
      "Retry": [
        { "ErrorEquals": ["States.TaskFailed"], "IntervalSeconds": 4, "MaxAttempts": 3, "BackoffRate": 2 }
      ],
      "Catch": [
        { "ErrorEquals": ["States.ALL"], "Next": "NotifyFailure", "ResultPath": "$.error" }
      ],
      "Next": "DataQuality"
    },
    "DataQuality": {
      "Type": "Task",
      "Resource": "${GreatExpectationsRunnerArn}",
      "Parameters": {
        "modelName": "{{ model.name }}",
        "modelVersion": "{{ model.version }}"
      },
      "Catch": [
        { "ErrorEquals": ["States.ALL"], "Next": "NotifyFailure", "ResultPath": "$.error" }
      ],
      "Next": "Score"
    },
    "Score": {
      "Type": "Task",
      "Resource": "arn:aws:states:::eks:runJob.sync",
      "Parameters": {
        "ClusterName": "${EksClusterName}",
        "Namespace": "${EksScoringNamespace}",
        "Job": {
          "apiVersion": "batch/v1",
          "kind": "Job",
          "metadata": {
            "name.$": "States.Format('{{ model.name }}-{{ model.version }}-{}', $$.Execution.Name)"
          },
          "spec": {
            "template": {
              "spec": {
                "containers": [
                  {
                    "name": "score",
                    "image": "${ScoringImageUri}",
                    "args": [
                      "--model-name", "{{ model.name }}",
                      "--model-version", "{{ model.version }}",
                      "--input-uri", "$.inputUri",
                      "--output-uri", "$.outputUri"
                    ]
                  }
                ],
                "restartPolicy": "Never"
              }
            },
            "backoffLimit": 2
          }
        }
      },
      "Catch": [
        { "ErrorEquals": ["States.ALL"], "Next": "NotifyFailure", "ResultPath": "$.error" }
      ],
      "Next": "WriteOutput"
    },
    "WriteOutput": {
      "Type": "Task",
      "Resource": "${WriteOutputLambdaArn}",
      "Parameters": {
        "outputSchemaRef": "{{ model.output_schema_ref }}",
        "outputUri.$": "$.outputUri"
      },
      "Next": "PIRVariance"
    },
    "PIRVariance": {
      "Type": "Task",
      "Resource": "${PirCheckerArn}",
      "Parameters": {
        "modelName": "{{ model.name }}",
        "modelVersion": "{{ model.version }}",
        "pirDocRef": "{{ model.pir_doc_ref }}",
        "scoreUri.$": "$.outputUri"
      },
      "Next": "VarianceDecision"
    },
    "VarianceDecision": {
      "Type": "Choice",
      "Choices": [
        { "Variable": "$.varianceWithinThreshold", "BooleanEquals": true, "Next": "Notify" }
      ],
      "Default": "BlockDelivery"
    },
    "Notify": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "${NotifyTopicArn}",
        "Message.$": "$"
      },
      "End": true
    },
    "BlockDelivery": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "${NotifyTopicArn}",
        "Message": {
          "status": "BLOCKED",
          "reason": "PIR variance exceeded threshold",
          "modelName": "{{ model.name }}",
          "modelVersion": "{{ model.version }}"
        }
      },
      "End": true
    },
    "NotifyFailure": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "${NotifyTopicArn}",
        "Message": {
          "status": "FAILED",
          "modelName": "{{ model.name }}",
          "modelVersion": "{{ model.version }}",
          "error.$": "$.error"
        }
      },
      "Next": "Fail"
    },
    "Fail": {
      "Type": "Fail",
      "Cause": "Pipeline failed; see audit log"
    }
  }
}
```

- [ ] **Step 4: Write the `realtime` placeholder**

`pipeline-factory/src/pipeline_factory/templates/statemachines/realtime.json.j2`:
```
{# Placeholder — real-time inference template is deferred (brief §6). The renderer refuses tier=realtime. #}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest pipeline-factory/tests/ -v`
Expected: all `test_renderer_*.py` PASS (3 new); standard-batch unaffected.

Run: `uv run mypy pipeline-factory/src`
Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add pipeline-factory/src/pipeline_factory/templates/statemachines/scalable-batch.json.j2 pipeline-factory/src/pipeline_factory/templates/statemachines/realtime.json.j2 pipeline-factory/tests/test_renderer_scalable.py
git commit -m "feat(factory): add scalable-batch ASL + realtime placeholder"
```

---

### Task 8: per-pipeline Terraform stub template

**Files:**
- Create: `pipeline-factory/src/pipeline_factory/templates/terraform/pipeline.tf.j2`
- Create: `pipeline-factory/tests/test_renderer_terraform.py`

- [ ] **Step 1: Write the failing test**

`pipeline-factory/tests/test_renderer_terraform.py`:
```python
import pytest

from pipeline_factory.hashing import terraform_fmt
from pipeline_factory.renderer import render_pipeline_tf


@pytest.fixture
def standard_context() -> dict:
    return {
        "tier": "standard",
        "model": {
            "name": "credit-risk-pd",
            "version": "1.0.0",
            "schedule_cadence": "cron(0 6 * * ? *)",
        },
    }


@pytest.fixture
def scalable_context() -> dict:
    return {
        "tier": "scalable",
        "model": {
            "name": "fraud-screen",
            "version": "2.1.0",
            "schedule_cadence": "cron(0 6 ? * 2 *)",
        },
    }


def test_standard_tf_renders_and_fmts(standard_context: dict) -> None:
    raw = render_pipeline_tf(standard_context)
    formatted = terraform_fmt(raw)
    assert "aws_sfn_state_machine" in formatted
    assert "aws_cloudwatch_event_rule" in formatted
    assert "aws_cloudwatch_log_group" in formatted
    assert "schedule_expression = \"cron(0 6 * * ? *)\"" in formatted
    # idempotent
    assert terraform_fmt(formatted) == formatted


def test_scalable_tf_includes_eks_variables(scalable_context: dict) -> None:
    formatted = terraform_fmt(render_pipeline_tf(scalable_context))
    assert "eks_cluster_name" in formatted
    assert "eks_scoring_namespace" in formatted
    assert "scoring_image_uri" in formatted


def test_standard_tf_excludes_eks_variables(standard_context: dict) -> None:
    formatted = terraform_fmt(render_pipeline_tf(standard_context))
    assert "eks_cluster_name" not in formatted
    assert "scoring_image_uri" not in formatted
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest pipeline-factory/tests/test_renderer_terraform.py -v`
Expected: FAIL — `TemplateNotFound: terraform/pipeline.tf.j2`.

- [ ] **Step 3: Write the template**

`pipeline-factory/src/pipeline_factory/templates/terraform/pipeline.tf.j2`:
```jinja
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.100" }
  }
}

variable "env" { type = string }
variable "region" { type = string }
variable "cmk_arn" { type = string }
variable "notify_topic_arn" { type = string }
variable "validate_input_lambda_arn" { type = string }
variable "great_expectations_runner_arn" { type = string }
variable "write_output_lambda_arn" { type = string }
variable "pir_checker_arn" { type = string }
{%- if tier == "scalable" %}
variable "eks_cluster_name" { type = string }
variable "eks_scoring_namespace" { type = string }
variable "scoring_image_uri" { type = string }
{%- endif %}
variable "tags" {
  type = map(string)
  description = "Tags to apply to every resource. Must include cost_center."
  validation {
    condition     = contains(keys(var.tags), "cost_center")
    error_message = "tags must include cost_center."
  }
}

locals {
  name = "${var.env}-{{ model.name }}-{{ model.version | replace('.', '-') }}"

  asl_substitutions = merge(
    {
      ValidateInputLambdaArn     = var.validate_input_lambda_arn
      GreatExpectationsRunnerArn = var.great_expectations_runner_arn
      WriteOutputLambdaArn       = var.write_output_lambda_arn
      PirCheckerArn              = var.pir_checker_arn
      NotifyTopicArn             = var.notify_topic_arn
    },
{%- if tier == "scalable" %}
    {
      EksClusterName      = var.eks_cluster_name
      EksScoringNamespace = var.eks_scoring_namespace
      ScoringImageUri     = var.scoring_image_uri
    }
{%- else %}
    {}
{%- endif %}
  )
}

data "aws_iam_policy_document" "sfn_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "sfn" {
  name               = "${local.name}-sfn"
  assume_role_policy = data.aws_iam_policy_document.sfn_assume.json
  tags               = var.tags
}

data "aws_iam_policy_document" "schedule_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "schedule" {
  name               = "${local.name}-schedule"
  assume_role_policy = data.aws_iam_policy_document.schedule_assume.json
  tags               = var.tags
}

resource "aws_cloudwatch_log_group" "sfn" {
  name              = "/aws/sfn/${local.name}"
  retention_in_days = 365
  kms_key_id        = var.cmk_arn
  tags              = var.tags
}

resource "aws_sfn_state_machine" "this" {
  name     = local.name
  role_arn = aws_iam_role.sfn.arn
  type     = "STANDARD"
  definition = templatefile("${path.module}/../statemachine.json", local.asl_substitutions)

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.sfn.arn}:*"
    include_execution_data = false
    level                  = "ERROR"
  }

  tags = var.tags
}

resource "aws_cloudwatch_event_rule" "schedule" {
  name                = "${local.name}-schedule"
  schedule_expression = "{{ model.schedule_cadence }}"
  tags                = var.tags
}

resource "aws_cloudwatch_event_target" "this" {
  rule     = aws_cloudwatch_event_rule.schedule.name
  arn      = aws_sfn_state_machine.this.arn
  role_arn = aws_iam_role.schedule.arn
}

output "state_machine_arn" { value = aws_sfn_state_machine.this.arn }
output "state_machine_name" { value = aws_sfn_state_machine.this.name }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest pipeline-factory/tests/test_renderer_terraform.py -v`
Expected: 3 PASS.

Run: `uv run mypy pipeline-factory/src`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline-factory/src/pipeline_factory/templates/terraform/pipeline.tf.j2 pipeline-factory/tests/test_renderer_terraform.py
git commit -m "feat(factory): add per-pipeline Terraform stub template"
```

---

### Task 9: generator orchestration + `validate` / `generate` CLI

**Files:**
- Create: `pipeline-factory/src/pipeline_factory/generator.py`
- Modify: `pipeline-factory/src/pipeline_factory/cli.py` — add `validate` and `generate` subcommands
- Create: `pipeline-factory/tests/test_generator.py`
- Create: `pipeline-factory/tests/test_cli_generate.py`
- Create: `pipeline-factory/tests/conftest.py`

- [ ] **Step 1: Write the failing tests**

`pipeline-factory/tests/conftest.py`:
```python
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def sample_config(tmp_path: Path) -> Path:
    config = tmp_path / "model_config.yaml"
    config.write_text(
        """
model_name: credit-risk-pd
version: 1.0.0
execution_tier: standard
schedule_cadence: "cron(0 6 * * ? *)"
input_schema_ref: s3://absa-exl/in.json
output_schema_ref: s3://absa-exl/out.json
pir_doc_ref: s3://absa-exl/pir.json
owner_email: owner@absa.africa
accountable_executive: Jane Exec
sla_seconds: 3600
sas_code_version: sas-2026.04.1
inference_code_version: py-2026.04.1
""".strip(),
        encoding="utf-8",
    )
    return config
```

`pipeline-factory/tests/test_generator.py`:
```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline_factory.generator import PipelineDriftError, generate, load_config


def test_load_config_validates(sample_config: Path) -> None:
    config = load_config(sample_config)
    assert config["model_name"] == "credit-risk-pd"


def test_load_config_rejects_bad_tier(sample_config: Path, tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(sample_config.read_text().replace("standard", "realtime"), encoding="utf-8")
    with pytest.raises(Exception):  # jsonschema.ValidationError; broad to avoid coupling
        load_config(bad)


def test_generate_writes_four_artifacts(sample_config: Path, tmp_path: Path) -> None:
    out_dir = generate(sample_config, outputs_root=tmp_path / "pipelines")
    assert out_dir == tmp_path / "pipelines" / "credit-risk-pd" / "1.0.0"
    assert (out_dir / "statemachine.json").exists()
    assert (out_dir / "registration.json").exists()
    assert (out_dir / "manifest.json").exists()
    assert (out_dir / "terraform" / "main.tf").exists()


def test_generated_registration_matches_create_request_shape(sample_config: Path, tmp_path: Path) -> None:
    out_dir = generate(sample_config, outputs_root=tmp_path / "pipelines")
    body = json.loads((out_dir / "registration.json").read_text())
    assert body["model_name"] == "credit-risk-pd"
    assert body["sas_code_version"] == "sas-2026.04.1"
    assert body["inference_code_version"] == "py-2026.04.1"
    # server-managed fields must NOT be present (API sets them)
    for forbidden in ("approval_status", "created_at", "updated_at", "rev", "last_scored_at"):
        assert forbidden not in body


def test_generated_manifest_is_unsigned(sample_config: Path, tmp_path: Path) -> None:
    out_dir = generate(sample_config, outputs_root=tmp_path / "pipelines")
    envelope = json.loads((out_dir / "manifest.json").read_text())
    assert envelope["signature"] == "UNSIGNED"
    assert envelope["subject_type"] == "pipeline"
    assert envelope["subject_ref"] == f"pipelines/credit-risk-pd/1.0.0/"


def test_regenerate_without_force_raises_on_drift(sample_config: Path, tmp_path: Path) -> None:
    out_dir = generate(sample_config, outputs_root=tmp_path / "pipelines")
    # Mutate one of the outputs to simulate drift
    (out_dir / "statemachine.json").write_text("{}", encoding="utf-8")
    with pytest.raises(PipelineDriftError):
        generate(sample_config, outputs_root=tmp_path / "pipelines")


def test_regenerate_with_force_overwrites(sample_config: Path, tmp_path: Path) -> None:
    out_dir = generate(sample_config, outputs_root=tmp_path / "pipelines")
    (out_dir / "statemachine.json").write_text("{}", encoding="utf-8")
    generate(sample_config, outputs_root=tmp_path / "pipelines", force=True)
    # rendered content restored
    content = (out_dir / "statemachine.json").read_text()
    assert "StartAt" in content
```

`pipeline-factory/tests/test_cli_generate.py`:
```python
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from pipeline_factory.cli import main


def test_validate_subcommand_ok(sample_config: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["validate", "--config", str(sample_config)])
    assert result.exit_code == 0
    assert "OK" in result.output


def test_generate_subcommand_writes_outputs(sample_config: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["generate", "--config", str(sample_config), "--outputs-root", str(tmp_path / "pipelines")],
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "pipelines" / "credit-risk-pd" / "1.0.0" / "statemachine.json").exists()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest pipeline-factory/tests/test_generator.py pipeline-factory/tests/test_cli_generate.py -v`
Expected: FAIL — `ModuleNotFoundError: pipeline_factory.generator`.

- [ ] **Step 3: Write the generator**

`pipeline-factory/src/pipeline_factory/generator.py`:
```python
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from platform_contracts.loader import validate as validate_contract

from .hashing import canonical_json, sha256_of_text, terraform_fmt
from .manifest import build_envelope, build_payload
from .renderer import render_pipeline_tf, render_statemachine

OUTPUTS_ROOT = Path("pipelines")


class PipelineDriftError(Exception):
    """Raised when re-generating would change a file that already exists, without --force."""


def load_config(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(text)
    if not isinstance(parsed, dict):
        raise ValueError(f"{path} did not parse as a YAML mapping")
    validate_contract("model-config", parsed)
    return parsed


def _model_context(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": config["model_name"],
        "version": config["version"],
        "schedule_cadence": config["schedule_cadence"],
        "input_schema_ref": config["input_schema_ref"],
        "output_schema_ref": config["output_schema_ref"],
        "pir_doc_ref": config["pir_doc_ref"],
    }


def _build_registration(config: dict[str, Any]) -> dict[str, Any]:
    # registration body mirrors the API's CreateModelRequest exactly; the API sets
    # server-managed fields (approval_status, created_at, updated_at, rev, last_scored_at).
    return {
        "model_name": config["model_name"],
        "version": config["version"],
        "sas_code_version": config.get("sas_code_version"),
        "inference_code_version": config.get("inference_code_version"),
        "schedule_cadence": config["schedule_cadence"],
        "execution_tier": config["execution_tier"],
        "input_schema_ref": config["input_schema_ref"],
        "output_schema_ref": config["output_schema_ref"],
        "pir_doc_ref": config["pir_doc_ref"],
        "owner_email": config["owner_email"],
        "accountable_executive": config["accountable_executive"],
        "sla_seconds": config["sla_seconds"],
        "cab_record_id": config.get("cab_record_id"),
        "ivu_evidence_ref": config.get("ivu_evidence_ref"),
    }


def _write_or_check(path: Path, content: str, *, force: bool) -> None:
    if path.exists() and not force:
        existing = path.read_text(encoding="utf-8")
        if existing != content:
            raise PipelineDriftError(
                f"drift detected in {path}: existing content differs from re-rendered output. "
                f"Re-run with --force to overwrite, or investigate the divergence."
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def generate(
    config_path: Path,
    *,
    force: bool = False,
    outputs_root: Path = OUTPUTS_ROOT,
) -> Path:
    """Validate the config and render the four artifacts under outputs_root/<name>/<version>/."""
    config = load_config(config_path)
    model_name = config["model_name"]
    version = config["version"]
    tier = config["execution_tier"]
    out_dir = outputs_root / model_name / version

    statemachine_json = render_statemachine(tier, {"model": _model_context(config)})
    pipeline_tf_raw = render_pipeline_tf({"tier": tier, "model": _model_context(config)})
    pipeline_tf = terraform_fmt(pipeline_tf_raw)
    registration = _build_registration(config)
    registration_json = canonical_json(registration).decode("utf-8")

    artifact_hashes = {
        "statemachine_sha256": sha256_of_text(statemachine_json),
        "terraform_sha256": sha256_of_text(pipeline_tf),
        "model_config_sha256": sha256_of_text(config_path.read_text(encoding="utf-8")),
        "registration_sha256": sha256_of_text(registration_json),
    }
    payload = build_payload(
        model_name=model_name,
        version=version,
        tier=tier,
        artifact_hashes=artifact_hashes,
    )
    envelope = build_envelope(payload=payload, subject_ref=f"pipelines/{model_name}/{version}/")
    manifest_json = canonical_json(envelope).decode("utf-8")

    files: dict[Path, str] = {
        out_dir / "statemachine.json": statemachine_json,
        out_dir / "registration.json": registration_json,
        out_dir / "manifest.json": manifest_json,
        out_dir / "terraform" / "main.tf": pipeline_tf,
    }
    for path, content in files.items():
        _write_or_check(path, content, force=force)
    return out_dir
```

- [ ] **Step 4: Add the `validate` and `generate` subcommands to the CLI**

Replace `pipeline-factory/src/pipeline_factory/cli.py` with:
```python
from __future__ import annotations

from pathlib import Path

import click
import yaml

from platform_contracts.loader import validate as validate_contract

from .generator import OUTPUTS_ROOT, generate


@click.group()
def main() -> None:
    """ABSA x EXL Pipeline Factory generator (validate | generate | register)."""


@main.command("validate")
@click.option("--config", "config", required=True, type=click.Path(exists=True, path_type=Path))
def cmd_validate(config: Path) -> None:
    """Validate a model_config.yaml against the canonical schema."""
    parsed = yaml.safe_load(config.read_text(encoding="utf-8"))
    validate_contract("model-config", parsed)
    click.echo(f"OK: {config}")


@main.command("generate")
@click.option("--config", "config", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--force", is_flag=True, default=False, help="Overwrite existing outputs without drift check")
@click.option(
    "--outputs-root",
    "outputs_root",
    type=click.Path(path_type=Path),
    default=OUTPUTS_ROOT,
    show_default=True,
)
def cmd_generate(config: Path, force: bool, outputs_root: Path) -> None:
    """Render the four pipeline artifacts into <outputs_root>/<name>/<version>/."""
    out_dir = generate(config, force=force, outputs_root=outputs_root)
    click.echo(f"generated: {out_dir}")


if __name__ == "__main__":  # pragma: no cover
    main()
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest pipeline-factory/tests/test_generator.py pipeline-factory/tests/test_cli_generate.py -v`
Expected: PASS.

Run: `uv run mypy pipeline-factory/src`
Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add pipeline-factory/src/pipeline_factory/generator.py pipeline-factory/src/pipeline_factory/cli.py pipeline-factory/tests/conftest.py pipeline-factory/tests/test_generator.py pipeline-factory/tests/test_cli_generate.py
git commit -m "feat(factory): add generator + validate/generate CLI subcommands"
```

---

### Task 10: registration (SigV4 POST) + `register` CLI

**Files:**
- Create: `pipeline-factory/src/pipeline_factory/registration.py`
- Modify: `pipeline-factory/src/pipeline_factory/cli.py` — add `register` subcommand
- Create: `pipeline-factory/tests/test_registration.py`
- Create: `pipeline-factory/tests/test_cli_register.py`

- [ ] **Step 1: Write the failing tests**

`pipeline-factory/tests/test_registration.py`:
```python
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from pipeline_factory.registration import RegistrationError, register


def _write_registration(tmp_path: Path, **overrides: object) -> Path:
    body = {
        "model_name": "credit-risk-pd",
        "version": "1.0.0",
        "sas_code_version": "sas-2026.04.1",
        "inference_code_version": "py-2026.04.1",
        "schedule_cadence": "cron(0 6 * * ? *)",
        "execution_tier": "standard",
        "input_schema_ref": "s3://absa-exl/in.json",
        "output_schema_ref": "s3://absa-exl/out.json",
        "pir_doc_ref": "s3://absa-exl/pir.json",
        "owner_email": "owner@absa.africa",
        "accountable_executive": "Jane Exec",
        "sla_seconds": 3600,
        "cab_record_id": None,
        "ivu_evidence_ref": None,
    }
    body.update(overrides)
    path = tmp_path / "registration.json"
    path.write_text(json.dumps(body, sort_keys=True, indent=2), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _aws_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
    monkeypatch.setenv("REGISTRY_API_ENDPOINT", "https://api.example.test")


def test_register_dry_run_does_not_call_network(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
    reg = _write_registration(tmp_path)
    result = register(reg, dry_run=True)
    assert result["status"] == "dry_run"
    assert result["would_post"]["model_name"] == "credit-risk-pd"
    # nothing should have hit the network
    assert httpx_mock.get_requests() == []


def test_register_201_succeeds(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url="https://api.example.test/models",
        status_code=201,
        json={"model_name": "credit-risk-pd", "version": "1.0.0", "approval_status": "pending", "rev": 0},
    )
    reg = _write_registration(tmp_path)
    result = register(reg)
    assert result["status"] == "created"
    assert result["body"]["approval_status"] == "pending"


def test_register_409_treated_as_idempotent(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url="https://api.example.test/models",
        status_code=409,
        json={"error": {"code": "conflict", "message": "exists"}},
    )
    reg = _write_registration(tmp_path)
    result = register(reg)
    assert result["status"] == "already_exists"


def test_register_5xx_retries_then_succeeds(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(method="POST", url="https://api.example.test/models", status_code=502)
    httpx_mock.add_response(
        method="POST",
        url="https://api.example.test/models",
        status_code=201,
        json={"approval_status": "pending"},
    )
    reg = _write_registration(tmp_path)
    result = register(reg, backoff_initial=0.0)  # disable sleep in tests
    assert result["status"] == "created"
    assert len(httpx_mock.get_requests()) == 2


def test_register_missing_code_version_raises(tmp_path: Path) -> None:
    reg = _write_registration(tmp_path, sas_code_version=None)
    with pytest.raises(RegistrationError, match="sas_code_version"):
        register(reg, dry_run=True)


def test_register_4xx_other_raises(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url="https://api.example.test/models",
        status_code=422,
        json={"error": {"code": "validation_error"}},
    )
    reg = _write_registration(tmp_path)
    with pytest.raises(RegistrationError, match="422"):
        register(reg)
```

`pipeline-factory/tests/test_cli_register.py`:
```python
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from pytest_httpx import HTTPXMock

from pipeline_factory.cli import main


@pytest.fixture(autouse=True)
def _aws_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")


def _write_registration(out_dir: Path) -> None:
    body = {
        "model_name": "credit-risk-pd",
        "version": "1.0.0",
        "sas_code_version": "sas-2026.04.1",
        "inference_code_version": "py-2026.04.1",
        "schedule_cadence": "cron(0 6 * * ? *)",
        "execution_tier": "standard",
        "input_schema_ref": "s3://absa-exl/in.json",
        "output_schema_ref": "s3://absa-exl/out.json",
        "pir_doc_ref": "s3://absa-exl/pir.json",
        "owner_email": "owner@absa.africa",
        "accountable_executive": "Jane Exec",
        "sla_seconds": 3600,
        "cab_record_id": None,
        "ivu_evidence_ref": None,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "registration.json").write_text(json.dumps(body, sort_keys=True, indent=2), encoding="utf-8")


def test_cli_register_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_registration(tmp_path / "pipelines" / "credit-risk-pd" / "1.0.0")
    runner = CliRunner()
    result = runner.invoke(main, ["register", "--pipeline", "credit-risk-pd@1.0.0", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "dry_run" in result.output


def test_cli_register_posts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, httpx_mock: HTTPXMock) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("REGISTRY_API_ENDPOINT", "https://api.example.test")
    _write_registration(tmp_path / "pipelines" / "credit-risk-pd" / "1.0.0")
    httpx_mock.add_response(method="POST", url="https://api.example.test/models", status_code=201, json={"approval_status": "pending"})
    runner = CliRunner()
    result = runner.invoke(main, ["register", "--pipeline", "credit-risk-pd@1.0.0"])
    assert result.exit_code == 0, result.output
    assert "created" in result.output
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest pipeline-factory/tests/test_registration.py pipeline-factory/tests/test_cli_register.py -v`
Expected: FAIL — `ModuleNotFoundError: pipeline_factory.registration`.

- [ ] **Step 3: Write the registration module**

`pipeline-factory/src/pipeline_factory/registration.py`:
```python
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import boto3
import httpx
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest


class RegistrationError(Exception):
    """Raised when registration cannot be completed."""


def _sign_headers(*, method: str, url: str, body: str, region: str) -> dict[str, str]:
    session = boto3.Session()
    credentials = session.get_credentials()
    if credentials is None:
        raise RegistrationError("no AWS credentials available for SigV4 signing")
    request = AWSRequest(method=method, url=url, data=body, headers={"Content-Type": "application/json"})
    SigV4Auth(credentials, "execute-api", region).add_auth(request)
    return dict(request.headers)


def register(
    registration_path: Path,
    *,
    endpoint: str | None = None,
    region: str | None = None,
    dry_run: bool = False,
    max_attempts: int = 3,
    backoff_initial: float = 1.0,
) -> dict[str, Any]:
    """Read the registration body and POST it to the Registry API.

    Returns a small status dict. Raises RegistrationError on terminal failures.
    """
    body_text = registration_path.read_text(encoding="utf-8")
    body = json.loads(body_text)

    for required in ("sas_code_version", "inference_code_version"):
        if not body.get(required):
            raise RegistrationError(
                f"{required} is required for registration; populate it in model_config.yaml "
                f"(it is optional in the schema but required at register time)"
            )

    if dry_run:
        return {"status": "dry_run", "would_post": body}

    endpoint = endpoint or os.environ.get("REGISTRY_API_ENDPOINT")
    if not endpoint:
        raise RegistrationError("REGISTRY_API_ENDPOINT not set")
    region = region or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION", "eu-west-1")
    url = f"{endpoint.rstrip('/')}/models"

    backoff = backoff_initial
    last_status: int | None = None
    last_body: str = ""
    for attempt in range(1, max_attempts + 1):
        headers = _sign_headers(method="POST", url=url, body=body_text, region=region)
        with httpx.Client(timeout=30) as client:
            resp = client.post(url, content=body_text, headers=headers)
        last_status, last_body = resp.status_code, resp.text
        if resp.status_code == 201:
            return {"status": "created", "body": resp.json()}
        if resp.status_code == 409:
            return {"status": "already_exists", "body": _try_json(resp)}
        if 500 <= resp.status_code < 600 and attempt < max_attempts:
            time.sleep(backoff)
            backoff *= 4
            continue
        # non-retryable 4xx or final 5xx
        raise RegistrationError(f"registration failed: HTTP {resp.status_code} {resp.text}")
    raise RegistrationError(
        f"registration failed after {max_attempts} attempts (last HTTP {last_status}: {last_body})"
    )


def _try_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return resp.text
```

- [ ] **Step 4: Replace `cli.py` with the final version (adds the `register` subcommand)**

Overwrite `pipeline-factory/src/pipeline_factory/cli.py` with this complete file:
```python
from __future__ import annotations

from pathlib import Path

import click
import yaml

from platform_contracts.loader import validate as validate_contract

from . import registration as _registration
from .generator import OUTPUTS_ROOT, generate


@click.group()
def main() -> None:
    """ABSA x EXL Pipeline Factory generator (validate | generate | register)."""


@main.command("validate")
@click.option("--config", "config", required=True, type=click.Path(exists=True, path_type=Path))
def cmd_validate(config: Path) -> None:
    """Validate a model_config.yaml against the canonical schema."""
    parsed = yaml.safe_load(config.read_text(encoding="utf-8"))
    validate_contract("model-config", parsed)
    click.echo(f"OK: {config}")


@main.command("generate")
@click.option("--config", "config", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--force", is_flag=True, default=False, help="Overwrite existing outputs without drift check")
@click.option(
    "--outputs-root",
    "outputs_root",
    type=click.Path(path_type=Path),
    default=OUTPUTS_ROOT,
    show_default=True,
)
def cmd_generate(config: Path, force: bool, outputs_root: Path) -> None:
    """Render the four pipeline artifacts into <outputs_root>/<name>/<version>/."""
    out_dir = generate(config, force=force, outputs_root=outputs_root)
    click.echo(f"generated: {out_dir}")


@main.command("register")
@click.option(
    "--pipeline",
    "pipeline",
    default=None,
    help="<name>@<version> — resolves pipelines/<name>/<version>/registration.json",
)
@click.option(
    "--registration",
    "registration_path",
    default=None,
    type=click.Path(exists=True, path_type=Path),
)
@click.option("--endpoint", default=None, help="Registry API endpoint (default: env REGISTRY_API_ENDPOINT)")
@click.option("--region", default=None, help="AWS region (default: env AWS_REGION)")
@click.option("--dry-run", is_flag=True, default=False)
def cmd_register(
    pipeline: str | None,
    registration_path: Path | None,
    endpoint: str | None,
    region: str | None,
    dry_run: bool,
) -> None:
    """POST the registration body to the Registry API (SigV4)."""
    if pipeline and registration_path:
        raise click.UsageError("specify either --pipeline or --registration, not both")
    if not pipeline and not registration_path:
        raise click.UsageError("specify --pipeline or --registration")
    if pipeline:
        name, _, ver = pipeline.partition("@")
        if not ver:
            raise click.UsageError("--pipeline must be <name>@<version>")
        registration_path = Path("pipelines") / name / ver / "registration.json"
        if not registration_path.exists():
            raise click.UsageError(f"not found: {registration_path}")
    result = _registration.register(
        registration_path, endpoint=endpoint, region=region, dry_run=dry_run
    )
    click.echo(result)


if __name__ == "__main__":  # pragma: no cover
    main()
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest pipeline-factory/tests/test_registration.py pipeline-factory/tests/test_cli_register.py -v`
Expected: PASS.

Run the full suite to confirm nothing else broke:
Run: `uv run pytest -q`
Expected: full suite passes.

Run: `uv run mypy platform-contracts/src registry/api/src pipeline-factory/src`
Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add pipeline-factory/src/pipeline_factory/registration.py pipeline-factory/src/pipeline_factory/cli.py pipeline-factory/tests/test_registration.py pipeline-factory/tests/test_cli_register.py
git commit -m "feat(factory): add SigV4 registration + register CLI subcommand"
```

---

### Task 11: worked-example fixture + golden artifacts + drift-stability test

**Files:**
- Create: `pipeline-factory/configs/credit-risk-pd/1.0.0/model_config.yaml`
- Create (via the generator): `pipelines/credit-risk-pd/1.0.0/{statemachine.json, registration.json, manifest.json, terraform/main.tf}`
- Create: `pipeline-factory/tests/test_golden_fixture.py`

- [ ] **Step 1: Create the fixture config**

`pipeline-factory/configs/credit-risk-pd/1.0.0/model_config.yaml`:
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
```

- [ ] **Step 2: Generate the artifacts and commit them as golden**

Run from the repo root:
```bash
uv run generate-pipeline generate --config pipeline-factory/configs/credit-risk-pd/1.0.0/model_config.yaml
```
Expected: `pipelines/credit-risk-pd/1.0.0/{statemachine.json, registration.json, manifest.json, terraform/main.tf}` are created.

Inspect them briefly:
```bash
ls -la pipelines/credit-risk-pd/1.0.0/
```
Expected: four entries (3 files + `terraform/`).

- [ ] **Step 3: Write the byte-stability (drift) test**

`pipeline-factory/tests/test_golden_fixture.py`:
```python
from __future__ import annotations

from pathlib import Path

from pipeline_factory.generator import generate

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_CONFIG = REPO_ROOT / "pipeline-factory" / "configs" / "credit-risk-pd" / "1.0.0" / "model_config.yaml"
EXPECTED_DIR = REPO_ROOT / "pipelines" / "credit-risk-pd" / "1.0.0"


def test_fixture_regenerate_is_byte_stable(tmp_path: Path) -> None:
    out_root = tmp_path / "pipelines"
    out_dir = generate(FIXTURE_CONFIG, outputs_root=out_root)
    for rel in ("statemachine.json", "registration.json", "manifest.json", "terraform/main.tf"):
        regenerated = (out_dir / rel).read_text(encoding="utf-8")
        expected = (EXPECTED_DIR / rel).read_text(encoding="utf-8")
        assert regenerated == expected, (
            f"drift in {rel}: re-generating from the committed config produced different output. "
            f"Re-run `uv run generate-pipeline generate --config pipeline-factory/configs/credit-risk-pd/1.0.0/model_config.yaml --force` "
            f"and commit, or investigate the divergence."
        )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest pipeline-factory/tests/test_golden_fixture.py -v`
Expected: PASS.

Run the full suite again:
Run: `uv run pytest -q`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add pipeline-factory/configs/credit-risk-pd/1.0.0/model_config.yaml pipelines/credit-risk-pd/1.0.0/ pipeline-factory/tests/test_golden_fixture.py
git commit -m "feat(factory): add credit-risk-pd worked-example fixture + golden artifacts"
```

---

### Task 12: CI — `pipeline-factory.yml` + terraform-validate matrix

**Files:**
- Create: `.github/workflows/pipeline-factory.yml`
- Modify: `.github/workflows/terraform-validate.yml` — add the generated TF stub to the matrix

- [ ] **Step 1: Write the new workflow**

`.github/workflows/pipeline-factory.yml`:
```yaml
name: pipeline-factory

on:
  pull_request:
    branches:
      - main
      - "phase-1/**"
      - "phase-2/**"
    paths:
      - "pipeline-factory/**"
      - "pipelines/**"
      - "platform-contracts/**"
      - "pyproject.toml"
      - "uv.lock"
      - ".github/workflows/pipeline-factory.yml"
  push:
    branches:
      - main
      - "phase-1/**"
      - "phase-2/**"
    paths:
      - "pipeline-factory/**"
      - "pipelines/**"
      - "platform-contracts/**"
      - "pyproject.toml"
      - "uv.lock"
      - ".github/workflows/pipeline-factory.yml"

permissions:
  contents: read
  id-token: write
  pull-requests: write

jobs:
  validate-and-generate:
    name: validate + generate (drift gate)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.9.5
      - name: Sync
        run: uv sync --frozen
      - name: Pipeline-factory tests
        run: uv run pytest pipeline-factory/tests -q
      - name: Regenerate every fixture and assert byte-stability
        run: |
          set -euo pipefail
          for config in pipeline-factory/configs/*/*/model_config.yaml; do
            uv run generate-pipeline generate --config "$config" --force
          done
          git diff --exit-code pipelines/

  register:
    name: register (POST to Registry API)
    needs: validate-and-generate
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    env:
      ROLE_ARN: ${{ secrets.AWS_OIDC_REGISTRAR_ROLE_ARN }}
      REGISTRY_API_ENDPOINT: ${{ secrets.REGISTRY_API_ENDPOINT }}
    steps:
      - name: Skip if not configured
        if: env.ROLE_ARN == ''
        run: echo "AWS_OIDC_REGISTRAR_ROLE_ARN not set — register step is a no-op until creds land."
      - uses: actions/checkout@v4
        if: env.ROLE_ARN != ''
      - uses: astral-sh/setup-uv@v5
        if: env.ROLE_ARN != ''
        with:
          enable-cache: true
      - name: Sync
        if: env.ROLE_ARN != ''
        run: uv sync --frozen
      - uses: aws-actions/configure-aws-credentials@v4
        if: env.ROLE_ARN != ''
        with:
          role-to-assume: ${{ env.ROLE_ARN }}
          aws-region: eu-west-1
      - name: Register every committed pipeline
        if: env.ROLE_ARN != ''
        run: |
          set -euo pipefail
          for reg in pipelines/*/*/registration.json; do
            pipeline=$(echo "$reg" | sed -E 's|pipelines/([^/]+)/([^/]+)/registration.json|\1@\2|')
            echo "Registering $pipeline"
            uv run generate-pipeline register --pipeline "$pipeline"
          done
```

- [ ] **Step 2: Add the generated TF stub to the terraform-validate matrix**

Edit `.github/workflows/terraform-validate.yml`. Locate the `validate-stacks` matrix's `stack:` list (the one that already contains entries like `terraform/envs/dev/source`). After the last `terraform/envs/prod/registry` entry, add:
```yaml
          - pipelines/credit-risk-pd/1.0.0/terraform
```

- [ ] **Step 3: Validate workflow YAML locally**

Run:
```bash
uv run --with pyyaml python -c "import yaml; yaml.safe_load(open('.github/workflows/pipeline-factory.yml')); yaml.safe_load(open('.github/workflows/terraform-validate.yml')); print('yaml ok')"
```
Expected: prints `yaml ok`.

- [ ] **Step 4: Validate the generated stub locally**

Run from the repo root:
```bash
terraform -chdir=pipelines/credit-risk-pd/1.0.0/terraform init -backend=false
terraform -chdir=pipelines/credit-risk-pd/1.0.0/terraform validate
```
Expected: `Success! The configuration is valid.`

Also ensure the repo-wide fmt check stays clean:
```bash
terraform fmt -check -recursive terraform/ pipelines/
```
Expected: exit 0.

- [ ] **Step 5: Confirm ruff/format stay clean after the YAML changes**

Run: `uv run ruff format --check .`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/pipeline-factory.yml .github/workflows/terraform-validate.yml
git commit -m "ci: add pipeline-factory workflow + register generated TF stub in matrix"
```

---

### Task 13: ADR-0008, compliance rows, CODEOWNERS, READMEs, final verification

**Files:**
- Create: `docs/adr/0008-generator-runtime-dual-mode.md`
- Modify: `docs/compliance/control-matrix.md` (append Phase 2 Sprint 2 rows)
- Modify: `CODEOWNERS` (add `pipeline-factory/`, `pipelines/`)
- Create: `pipeline-factory/README.md`
- Modify: root `README.md` (Status section + add `pipeline-factory/` and `pipelines/` to the layout block)

- [ ] **Step 1: Write ADR-0008**

`docs/adr/0008-generator-runtime-dual-mode.md`:
```markdown
# ADR-0008: Generator runtime — dual-mode (local dev + CI canonical)

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-05-26 |
| Deciders | Engagement lead, EXL Platform Engineering |

## Context

The Pipeline Factory generator turns a `model_config.yaml` into committed artifacts
and routes a registration to the Registry API. Two question hung over the runtime:
where does it run, and who has the authority to POST?

ADR-0003 (manifest signing) already said "CI is the only signer". ADR-0006 set the
Python tooling baseline. The remaining gap, owed since Phase 1 (decision #5 in the
foundation spec), was the formal record of the generator runtime mode.

## Decision

The generator runs in two modes from the same binary (`generate-pipeline`):

- **Local dev mode** — an engineer runs `uv run generate-pipeline validate` and
  `... generate` on their workstation. No AWS credentials are required. The
  generator does not POST to the Registry API in this mode (the `register`
  subcommand is allowed but `--dry-run` is the expectation; running it with real
  creds is a per-engineer choice, not the canonical path).
- **CI canonical mode** — GitHub Actions runs `generate` on every PR (a drift
  gate: re-render, `git diff --exit-code pipelines/`, fail on drift). On push
  to `main`, GitHub Actions additionally runs `register` for every committed
  pipeline using an IAM role assumed via the GitHub Actions OIDC provider
  (`pipeline-factory-registrar`, writer-policy from the `pipeline-registry`
  module). **Only CI may POST to the Registry API in this design.**

Mode is a function of the subcommand and the presence of OIDC creds; there is no
mode flag.

## Consequences

### Positive
- Single source of governance for what is registered (the API), guarded by IAM.
- Engineers iterate fast locally without burning CI cycles.
- The drift gate makes generator changes safe — any divergence between the
  committed artifacts and a fresh render fails the PR.

### Negative
- Until the OIDC IdP and the registrar role are provisioned (deferred to 2.3),
  the `register` job is a documented no-op (gated on the secret). Models cannot
  actually be registered against a live API yet — which is consistent with the
  rest of the platform's plan-validate posture.

## Alternatives considered
1. CLI-only on developer workstations, no CI involvement. Rejected — no single
   audit trail; developers could POST inconsistent versions.
2. Lambda-hosted generator triggered by an EventBridge rule. Rejected —
   debugging Jinja rendering inside a Lambda is painful; CI gives clean logs
   and PR-diff review for free.
3. Sign + register inline in the generator. Rejected — couples signing infra to
   generator infra. ADR-0003 already separates signing (Code Intake / 2.3) from
   manifest emission (Pipeline Factory / this sprint).
```

- [ ] **Step 2: Append the compliance rows**

In `docs/compliance/control-matrix.md`, find the `## Phase 2 controls (sprint 1 — Registry)` section. After that table and before the `## Out-of-matrix items (deferred)` heading, insert:
```markdown
## Phase 2 controls (sprint 2 — Pipeline Factory)

| Control | Implementation | Evidence artifact | Owner |
| --- | --- | --- | --- |
| **SR 11-7 III.1 — model documentation** | Per-version immutable artifact directories committed in git (model_config + state machine + registration + manifest + terraform) | `pipelines/<name>/<version>/`, `pipeline-factory/configs/<name>/<version>/model_config.yaml` | EXL Platform Engineering |
| **SR 11-7 III.4 — model implementation evidence** | API-routed registration preserves the audit log + approval gate from 2.1; CI is the only POST path (per ADR-0008) | `.github/workflows/pipeline-factory.yml` (`register` job), `pipeline-factory/src/pipeline_factory/registration.py` | EXL Platform Engineering |
| **SARB GOI 3 — model risk governance** | The generator can only create `pending` records; CAB + IVU still required to flip to `approved` (gate is server-side in the Registry API) | `registry/api/src/registry_api/transitions.py`, `pipeline-factory/src/pipeline_factory/registration.py` | ABSA Model Risk |
| **ISO 27001 A.14.2 — secure development** | Drift gate (CI re-render + `git diff --exit-code`) + golden-file tests ensure generated artifacts are reproducible bit-for-bit | `.github/workflows/pipeline-factory.yml`, `pipeline-factory/tests/test_golden_fixture.py` | EXL Platform Engineering |
```

- [ ] **Step 3: Update CODEOWNERS**

Append to `CODEOWNERS`, matching the existing no-leading-slash, column-aligned style:
```
pipeline-factory/                  @platform-leads
pipelines/                         @platform-leads
```

- [ ] **Step 4: Write the pipeline-factory README**

`pipeline-factory/README.md`:
```markdown
# pipeline-factory

Phase 2 Sprint 2. Turns a `model_config.yaml` into a complete, registry-routed
scoring pipeline. Built as a uv workspace member.

## What it produces

For every `pipeline-factory/configs/<name>/<version>/model_config.yaml`, the
generator writes four artifacts under `pipelines/<name>/<version>/`:

- `statemachine.json` — the rendered Step Functions ASL (parameterized; Phase 3
  fills in the real Lambda/SageMaker/EKS ARNs).
- `registration.json` — the body the registrar POSTs to the Registry API.
- `manifest.json` — the manifest envelope. Emitted **unsigned** (sentinel
  placeholders); sub-sprint 2.3 signs it with the KMS asymmetric CMK.
- `terraform/main.tf` — the per-pipeline Terraform stub (`aws_sfn_state_machine`
  + EventBridge schedule + IAM + KMS-encrypted log group). Plan-validate only
  in this sprint; Phase 3 wires it into env stacks.

## Onboarding a model

1. Add `pipeline-factory/configs/<name>/<version>/model_config.yaml` (validates
   against the canonical `model-config` JSON Schema from 2.1).
2. Run locally: `uv run generate-pipeline generate --config <path>`.
3. Commit both the config and the generated `pipelines/<name>/<version>/` dir.
4. Open the PR. CI re-renders and diffs (the drift gate) to confirm
   reproducibility.
5. On merge to `main`, CI runs `register` (when AWS credentials are available)
   and the new model lands in the Registry as `approval_status=pending`.
6. CAB + IVU evidence + `:approve` then flips it to `approved` (per ADR-0007).

## CLI

- `generate-pipeline validate --config <path>` — schema check, no side effects.
- `generate-pipeline generate --config <path>` — render the artifacts;
  `--force` overwrites without the drift check.
- `generate-pipeline register --pipeline <name>@<version>` — POST registration
  to the Registry API (SigV4); `--dry-run` logs what would be posted.

## Runtime modes (ADR-0008)

- **Local dev** — no creds, no API calls.
- **CI canonical** — drift gate on PR; `register` on merge to `main`. Only CI
  POSTs to the API.

See [`docs/adr/0008-generator-runtime-dual-mode.md`](../docs/adr/0008-generator-runtime-dual-mode.md).
```

- [ ] **Step 5: Update the root README**

In `README.md`, replace the `## Status` section. Current:
```markdown
## Status

Phase 1 foundation complete (kickoff + sprint 2). Phase 2 sprint 1 (Registry & shared contracts) in progress. See [`docs/superpowers/plans/2026-05-26-absa-exl-phase-2-sprint-1-registry.md`](docs/superpowers/plans/2026-05-26-absa-exl-phase-2-sprint-1-registry.md).
```
Replace with:
```markdown
## Status

Phase 1 foundation complete. Phase 2 Sprint 1 (Registry & shared contracts) complete. **Phase 2 Sprint 2 (Pipeline Factory) in progress.** See [`docs/superpowers/plans/2026-05-26-absa-exl-phase-2-sprint-2-pipeline-factory.md`](docs/superpowers/plans/2026-05-26-absa-exl-phase-2-sprint-2-pipeline-factory.md).
```

In the same file, in the `## Repository layout` code block, add lines for the new top-level dirs. Find the existing `platform-contracts/          Shared JSON-Schema contracts + generated Pydantic models (Phase 2)` line and add immediately below it:
```
pipeline-factory/            Pipeline generator: validate / generate / register CLI (Phase 2)
pipelines/                   Per-version generated pipeline artifacts (Phase 2)
```

- [ ] **Step 6: Final full verification**

Run from repo root, in this order, each must succeed:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy platform-contracts/src registry/api/src pipeline-factory/src
terraform fmt -check -recursive terraform/ pipelines/
terraform -chdir=pipelines/credit-risk-pd/1.0.0/terraform init -backend=false
terraform -chdir=pipelines/credit-risk-pd/1.0.0/terraform validate
terraform -chdir=terraform/modules/pipeline-registry init -backend=false && terraform -chdir=terraform/modules/pipeline-registry test
bash platform-contracts/regenerate-models.sh && git diff --exit-code platform-contracts/src/platform_contracts/models.py
uv run generate-pipeline generate --config pipeline-factory/configs/credit-risk-pd/1.0.0/model_config.yaml --force && git diff --exit-code pipelines/
```

Expected: every command succeeds with exit 0 and no diff output.

- [ ] **Step 7: Commit**

```bash
git add docs/adr/0008-generator-runtime-dual-mode.md docs/compliance/control-matrix.md CODEOWNERS pipeline-factory/README.md README.md
git commit -m "docs(phase-2): add ADR-0008 + sprint-2 compliance rows + READMEs"
```

---

## Final Checklist (run before opening the PR)

- [ ] `uv run pytest` — full suite passes (39 + the new pipeline-factory tests)
- [ ] `uv run ruff check . && uv run ruff format --check .` — clean
- [ ] `uv run mypy platform-contracts/src registry/api/src pipeline-factory/src` — clean
- [ ] `terraform fmt -check -recursive terraform/ pipelines/` — clean
- [ ] `terraform -chdir=pipelines/credit-risk-pd/1.0.0/terraform validate` — Success
- [ ] `terraform -chdir=terraform/modules/pipeline-registry test` — passes
- [ ] Drift gates green: `bash platform-contracts/regenerate-models.sh` + `git diff --exit-code` on `models.py`; `uv run generate-pipeline generate --config <fixture> --force` + `git diff --exit-code` on `pipelines/`
- [ ] `tflint --recursive` passes (CI runs it non-soft-fail)
- [ ] Every spec §18 deliverable has a committed file
- [ ] One squash-merge PR `phase-2/sprint-2-pipeline-factory` → `main` for engagement-lead review at the checkpoint gate before sub-sprint 2.3 (Code Intake)
