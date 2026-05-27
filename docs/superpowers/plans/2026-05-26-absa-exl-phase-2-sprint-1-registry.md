# Phase 2 Sprint 1 — Registry & Shared Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Model & Pipeline Registry (DynamoDB + FastAPI-on-Lambda API) and the shared JSON-Schema contracts the rest of Phase 2 writes against.

**Architecture:** A uv workspace introduces the repo's first Python. `platform-contracts` holds canonical JSON Schemas plus Pydantic models generated from them (CI drift-checked). `registry/api` is a FastAPI app (single Lambda via Mangum) over a DynamoDB table, with an approval state machine guarded by CAB + IVU preconditions. A `pipeline-registry` Terraform module provisions the table, Lambda, API Gateway HTTP API (IAM auth), a module-owned KMS CMK, and encrypted log groups. Everything is plan-validate + mocked-AWS only (no creds yet), per Phase 1.

**Tech Stack:** Python 3.12, uv, ruff, mypy, pytest, jsonschema, datamodel-code-generator, Pydantic v2, FastAPI, Mangum, boto3, moto, Terraform (~> AWS 5.100), Terraform native `tftest`, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-05-26-absa-exl-phase-2-sprint-1-registry-design.md`

**Refinement of spec §4 tree:** canonical schemas live as package data at `platform-contracts/src/platform_contracts/schemas/` (not `platform-contracts/schemas/`) so the loader can read them via `importlib.resources` and they ship in the wheel. The pointer READMEs in `registry/schema/` and `pipeline-factory/config-schema/` are unchanged.

**Conventions:**
- All commits use Conventional Commit subjects (CI enforces this). Branch: `phase-2/sprint-1-registry` (already created; the design spec is already committed there).
- Run Python commands from the repo root via `uv run …` unless stated otherwise.
- Run Terraform commands from the directory named in each task.

---

### Task 1: Python tooling baseline + uv workspace

**Files:**
- Create: `pyproject.toml` (workspace root)
- Create: `.python-version`
- Create: `platform-contracts/pyproject.toml`
- Create: `platform-contracts/src/platform_contracts/__init__.py`
- Create: `platform-contracts/tests/test_smoke.py`
- Modify: `.gitignore` (append Python ignores)

- [ ] **Step 1: Write the failing smoke test**

`platform-contracts/tests/test_smoke.py`:
```python
import platform_contracts


def test_package_imports() -> None:
    assert platform_contracts.__name__ == "platform_contracts"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest platform-contracts/tests/test_smoke.py -v`
Expected: FAIL — `uv` errors that no project/workspace is configured, or `ModuleNotFoundError: platform_contracts`.

- [ ] **Step 3: Create the workspace root `pyproject.toml`**

```toml
[tool.uv.workspace]
members = ["platform-contracts", "registry/api"]

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

[tool.ruff]
line-length = 100
target-version = "py312"
# Generated from JSON Schema; excluded so the CI drift check (raw codegen output)
# stays byte-stable and ruff never reformats it.
extend-exclude = ["platform-contracts/src/platform_contracts/models.py"]

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM"]

[tool.mypy]
python_version = "3.12"
strict = true

[[tool.mypy.overrides]]
module = ["moto.*", "mangum.*", "boto3.*", "botocore.*"]
ignore_missing_imports = true

[tool.pytest.ini_options]
addopts = "-q"
testpaths = ["platform-contracts/tests", "registry/api/tests"]
```

- [ ] **Step 4: Create `.python-version`**

```
3.12
```

- [ ] **Step 5: Create the `platform-contracts` member**

`platform-contracts/pyproject.toml`:
```toml
[project]
name = "platform-contracts"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "jsonschema>=4.20",
    "pydantic>=2.7",
    "email-validator>=2",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/platform_contracts"]
```

`platform-contracts/src/platform_contracts/__init__.py`:
```python
"""Canonical cross-subsystem contracts for the ABSA x EXL platform."""
```

- [ ] **Step 6: Append Python ignores to `.gitignore`**

```
# Python
.venv/
__pycache__/
*.pyc
.mypy_cache/
.pytest_cache/
.ruff_cache/
```

- [ ] **Step 7: Sync and run the smoke test**

Run: `uv sync` then `uv run pytest platform-contracts/tests/test_smoke.py -v`
Expected: `uv.lock` is created; test PASSES.

- [ ] **Step 8: Verify lint and types are clean**

Run: `uv run ruff check . && uv run mypy platform-contracts/src`
Expected: both pass with no errors.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml uv.lock .python-version .gitignore platform-contracts/
git commit -m "chore(py): add uv workspace + ruff/mypy/pytest baseline"
```

---

### Task 2: `model-config` JSON Schema + loader

**Files:**
- Create: `platform-contracts/src/platform_contracts/loader.py`
- Create: `platform-contracts/src/platform_contracts/schemas/model-config.schema.json`
- Create: `platform-contracts/tests/test_model_config_schema.py`

- [ ] **Step 1: Write the failing test**

`platform-contracts/tests/test_model_config_schema.py`:
```python
import pytest
from jsonschema import ValidationError

from platform_contracts.loader import load_schema, validate

VALID = {
    "model_name": "credit-risk-pd",
    "version": "1.0.0",
    "execution_tier": "standard",
    "schedule_cadence": "cron(0 6 * * ? *)",
    "input_schema_ref": "s3://absa-exl/in.json",
    "output_schema_ref": "s3://absa-exl/out.json",
    "pir_doc_ref": "s3://absa-exl/pir.json",
    "owner_email": "owner@absa.africa",
    "accountable_executive": "Jane Exec",
    "sla_seconds": 3600,
}


def test_valid_config_passes() -> None:
    validate("model-config", VALID)


def test_unknown_schema_name_raises() -> None:
    with pytest.raises(KeyError):
        load_schema("does-not-exist")


def test_missing_required_field_fails() -> None:
    bad = {k: v for k, v in VALID.items() if k != "execution_tier"}
    with pytest.raises(ValidationError):
        validate("model-config", bad)


def test_bad_tier_enum_fails() -> None:
    with pytest.raises(ValidationError):
        validate("model-config", {**VALID, "execution_tier": "realtime"})


def test_additional_property_fails() -> None:
    with pytest.raises(ValidationError):
        validate("model-config", {**VALID, "surprise": "x"})
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest platform-contracts/tests/test_model_config_schema.py -v`
Expected: FAIL — `ModuleNotFoundError: platform_contracts.loader`.

- [ ] **Step 3: Write the loader**

`platform-contracts/src/platform_contracts/loader.py`:
```python
from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


def _schema_resource(name: str):  # type: ignore[no-untyped-def]
    return files("platform_contracts") / "schemas" / f"{name}.schema.json"


def load_schema(name: str) -> dict[str, Any]:
    resource = _schema_resource(name)
    if not resource.is_file():
        raise KeyError(f"unknown schema: {name!r}")
    return json.loads(resource.read_text(encoding="utf-8"))


def validate(name: str, document: dict[str, Any]) -> None:
    """Validate a document against a named schema. Raises jsonschema.ValidationError."""
    Draft202012Validator(load_schema(name), format_checker=FormatChecker()).validate(document)
```

- [ ] **Step 4: Write the schema**

`platform-contracts/src/platform_contracts/schemas/model-config.schema.json`:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://contracts.absa-exl.internal/model-config/v1.json",
  "title": "ModelConfig",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "model_name", "version", "execution_tier", "schedule_cadence",
    "input_schema_ref", "output_schema_ref", "pir_doc_ref",
    "owner_email", "accountable_executive", "sla_seconds"
  ],
  "properties": {
    "model_name": { "type": "string", "pattern": "^[a-z][a-z0-9-]{2,63}$" },
    "version": { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$" },
    "execution_tier": { "type": "string", "enum": ["standard", "scalable"] },
    "schedule_cadence": { "type": "string", "minLength": 1 },
    "input_schema_ref": { "type": "string", "pattern": "^s3://" },
    "output_schema_ref": { "type": "string", "pattern": "^s3://" },
    "pir_doc_ref": { "type": "string", "pattern": "^s3://" },
    "owner_email": { "type": "string", "format": "email" },
    "accountable_executive": { "type": "string", "minLength": 1 },
    "sla_seconds": { "type": "integer", "exclusiveMinimum": 0 },
    "model_class": { "type": "string", "enum": ["credit", "fraud", "propensity", "other"] },
    "registry_lookup_key": { "type": "string" }
  }
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest platform-contracts/tests/test_model_config_schema.py -v`
Expected: PASS (all 5 tests).

- [ ] **Step 6: Commit**

```bash
git add platform-contracts/src/platform_contracts/loader.py platform-contracts/src/platform_contracts/schemas/model-config.schema.json platform-contracts/tests/test_model_config_schema.py
git commit -m "feat(contracts): add model-config JSON Schema + loader"
```

---

### Task 3: `registry-record` JSON Schema

**Files:**
- Create: `platform-contracts/src/platform_contracts/schemas/registry-record.schema.json`
- Create: `platform-contracts/tests/test_registry_record_schema.py`

- [ ] **Step 1: Write the failing test**

`platform-contracts/tests/test_registry_record_schema.py`:
```python
import pytest
from jsonschema import ValidationError

from platform_contracts.loader import validate

VALID = {
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
    "approval_status": "pending",
    "sla_seconds": 3600,
    "cab_record_id": None,
    "ivu_evidence_ref": None,
    "created_at": "2026-05-26T06:00:00+00:00",
    "updated_at": "2026-05-26T06:00:00+00:00",
    "last_scored_at": None,
    "rev": 0,
}


def test_valid_record_passes() -> None:
    validate("registry-record", VALID)


def test_bad_status_enum_fails() -> None:
    with pytest.raises(ValidationError):
        validate("registry-record", {**VALID, "approval_status": "live"})


def test_missing_rev_fails() -> None:
    bad = {k: v for k, v in VALID.items() if k != "rev"}
    with pytest.raises(ValidationError):
        validate("registry-record", bad)


def test_additional_property_fails() -> None:
    with pytest.raises(ValidationError):
        validate("registry-record", {**VALID, "surprise": "x"})
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest platform-contracts/tests/test_registry_record_schema.py -v`
Expected: FAIL — `KeyError: unknown schema: 'registry-record'`.

- [ ] **Step 3: Write the schema**

`platform-contracts/src/platform_contracts/schemas/registry-record.schema.json`:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://contracts.absa-exl.internal/registry-record/v1.json",
  "title": "RegistryRecord",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "model_name", "version", "sas_code_version", "inference_code_version",
    "schedule_cadence", "execution_tier", "input_schema_ref", "output_schema_ref",
    "pir_doc_ref", "owner_email", "accountable_executive", "approval_status",
    "sla_seconds", "created_at", "updated_at", "rev"
  ],
  "properties": {
    "model_name": { "type": "string", "pattern": "^[a-z][a-z0-9-]{2,63}$" },
    "version": { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$" },
    "sas_code_version": { "type": "string", "minLength": 1 },
    "inference_code_version": { "type": "string", "minLength": 1 },
    "schedule_cadence": { "type": "string", "minLength": 1 },
    "execution_tier": { "type": "string", "enum": ["standard", "scalable"] },
    "input_schema_ref": { "type": "string", "pattern": "^s3://" },
    "output_schema_ref": { "type": "string", "pattern": "^s3://" },
    "pir_doc_ref": { "type": "string", "pattern": "^s3://" },
    "owner_email": { "type": "string", "format": "email" },
    "accountable_executive": { "type": "string", "minLength": 1 },
    "approval_status": { "type": "string", "enum": ["pending", "approved", "retired"] },
    "sla_seconds": { "type": "integer", "exclusiveMinimum": 0 },
    "cab_record_id": { "type": ["string", "null"] },
    "ivu_evidence_ref": { "type": ["string", "null"], "pattern": "^s3://" },
    "created_at": { "type": "string", "format": "date-time" },
    "updated_at": { "type": "string", "format": "date-time" },
    "last_scored_at": { "type": ["string", "null"], "format": "date-time" },
    "rev": { "type": "integer", "minimum": 0 }
  }
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest platform-contracts/tests/test_registry_record_schema.py -v`
Expected: PASS (all 4 tests).

- [ ] **Step 5: Commit**

```bash
git add platform-contracts/src/platform_contracts/schemas/registry-record.schema.json platform-contracts/tests/test_registry_record_schema.py
git commit -m "feat(contracts): add registry-record JSON Schema"
```

---

### Task 4: `manifest-envelope` JSON Schema

**Files:**
- Create: `platform-contracts/src/platform_contracts/schemas/manifest-envelope.schema.json`
- Create: `platform-contracts/tests/test_manifest_envelope_schema.py`

- [ ] **Step 1: Write the failing test**

`platform-contracts/tests/test_manifest_envelope_schema.py`:
```python
import pytest
from jsonschema import ValidationError

from platform_contracts.loader import validate

VALID = {
    "digest": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
    "digest_algorithm": "SHA-256",
    "signature": "QUJDRA==",
    "signing_key_arn": "arn:aws:kms:eu-west-1:111122223333:key/abc",
    "signing_algorithm": "RSASSA_PKCS1_V1_5_SHA_256",
    "subject_type": "pipeline",
    "subject_ref": "s3://exl-platform/pipelines/credit-risk-pd/1.0.0/manifest.json",
    "signed_at": "2026-05-26T06:00:00+00:00",
    "signer_principal": "arn:aws:iam::111122223333:role/ci-signer",
    "payload": {"any": "shape"},
}


def test_valid_envelope_passes() -> None:
    validate("manifest-envelope", VALID)


def test_bad_subject_type_fails() -> None:
    with pytest.raises(ValidationError):
        validate("manifest-envelope", {**VALID, "subject_type": "model"})


def test_missing_signature_fails() -> None:
    bad = {k: v for k, v in VALID.items() if k != "signature"}
    with pytest.raises(ValidationError):
        validate("manifest-envelope", bad)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest platform-contracts/tests/test_manifest_envelope_schema.py -v`
Expected: FAIL — `KeyError: unknown schema: 'manifest-envelope'`.

- [ ] **Step 3: Write the schema**

`platform-contracts/src/platform_contracts/schemas/manifest-envelope.schema.json`:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://contracts.absa-exl.internal/manifest-envelope/v1.json",
  "title": "ManifestEnvelope",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "digest", "digest_algorithm", "signature", "signing_key_arn",
    "signing_algorithm", "subject_type", "subject_ref", "signed_at",
    "signer_principal", "payload"
  ],
  "properties": {
    "digest": { "type": "string", "pattern": "^[0-9a-f]{64}$" },
    "digest_algorithm": { "type": "string", "const": "SHA-256" },
    "signature": { "type": "string", "minLength": 1 },
    "signing_key_arn": { "type": "string", "pattern": "^arn:aws:kms:" },
    "signing_algorithm": {
      "type": "string",
      "enum": ["RSASSA_PKCS1_V1_5_SHA_256", "ECDSA_SHA_384"]
    },
    "subject_type": { "type": "string", "enum": ["package", "pipeline"] },
    "subject_ref": { "type": "string", "minLength": 1 },
    "signed_at": { "type": "string", "format": "date-time" },
    "signer_principal": { "type": "string", "minLength": 1 },
    "payload": { "type": "object" }
  }
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest platform-contracts/tests/test_manifest_envelope_schema.py -v`
Expected: PASS (all 3 tests).

- [ ] **Step 5: Commit**

```bash
git add platform-contracts/src/platform_contracts/schemas/manifest-envelope.schema.json platform-contracts/tests/test_manifest_envelope_schema.py
git commit -m "feat(contracts): add manifest-envelope JSON Schema"
```

---

### Task 5: Generate Pydantic models + drift guard

**Files:**
- Create: `platform-contracts/src/platform_contracts/_base.py`
- Create: `platform-contracts/src/platform_contracts/models.py` (generated)
- Create: `platform-contracts/tests/test_models_match_schema.py`
- Create: `platform-contracts/regenerate-models.sh`

- [ ] **Step 1: Write the failing parity test**

`platform-contracts/tests/test_models_match_schema.py`:
```python
import pytest

from platform_contracts import models
from platform_contracts.loader import load_schema

CASES = [
    ("model-config", "ModelConfig"),
    ("registry-record", "RegistryRecord"),
    ("manifest-envelope", "ManifestEnvelope"),
]


@pytest.mark.parametrize(("schema_name", "model_name"), CASES)
def test_model_covers_all_schema_properties(schema_name: str, model_name: str) -> None:
    schema = load_schema(schema_name)
    model = getattr(models, model_name)
    assert set(schema["properties"]).issubset(set(model.model_fields))
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest platform-contracts/tests/test_models_match_schema.py -v`
Expected: FAIL — `ModuleNotFoundError: platform_contracts.models`.

- [ ] **Step 3: Write the base class (avoids the `model_` protected-namespace warning)**

`platform-contracts/src/platform_contracts/_base.py`:
```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ContractBase(BaseModel):
    """Base for generated contract models.

    `protected_namespaces=()` silences Pydantic's warning about fields that begin
    with `model_` (e.g. `model_name`, `model_class`).
    """

    model_config = ConfigDict(protected_namespaces=())
```

- [ ] **Step 4: Write the regeneration script**

`platform-contracts/regenerate-models.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
uv run datamodel-codegen \
  --input src/platform_contracts/schemas \
  --input-file-type jsonschema \
  --output src/platform_contracts/models.py \
  --output-model-type pydantic_v2.BaseModel \
  --base-class platform_contracts._base.ContractBase \
  --use-standard-collections \
  --use-union-operator \
  --target-python-version 3.12 \
  --disable-timestamp
```

- [ ] **Step 5: Generate the models**

Run: `bash platform-contracts/regenerate-models.sh`
Expected: `platform-contracts/src/platform_contracts/models.py` is created containing classes `ModelConfig`, `RegistryRecord`, `ManifestEnvelope` (all extending `ContractBase`). Inspect the file to confirm the three class names exist.

- [ ] **Step 6: Run the parity test to verify it passes**

Run: `uv run pytest platform-contracts/tests/test_models_match_schema.py -v`
Expected: PASS (3 parametrized cases).

- [ ] **Step 7: Verify lint/types across the package**

Run: `uv run ruff check platform-contracts && uv run mypy platform-contracts/src`
Expected: pass. The generated `models.py` is excluded from ruff (Task 1 `extend-exclude`) so it stays byte-identical to codegen output for the CI drift check; mypy still type-checks it.

- [ ] **Step 8: Commit**

```bash
git add platform-contracts/src/platform_contracts/_base.py platform-contracts/src/platform_contracts/models.py platform-contracts/regenerate-models.sh platform-contracts/tests/test_models_match_schema.py
git commit -m "feat(contracts): generate Pydantic models from schemas"
```

---

### Task 6: Registry settings + DynamoDB repository

**Files:**
- Create: `registry/api/pyproject.toml`
- Create: `registry/api/src/registry_api/__init__.py`
- Create: `registry/api/src/registry_api/settings.py`
- Create: `registry/api/src/registry_api/repository.py`
- Create: `registry/api/tests/conftest.py`
- Create: `registry/api/tests/test_repository.py`

- [ ] **Step 1: Create the `registry-api` member**

`registry/api/pyproject.toml`:
```toml
[project]
name = "registry-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "platform-contracts",
    "fastapi>=0.110",
    "mangum>=0.17",
    "boto3>=1.34",
    "pydantic[email]>=2.7",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/registry_api"]

[tool.uv.sources]
platform-contracts = { workspace = true }
```

`registry/api/src/registry_api/__init__.py`:
```python
"""ABSA x EXL Model & Pipeline Registry API."""
```

Run: `uv sync`
Expected: `registry-api` resolves; `uv.lock` updates.

- [ ] **Step 2: Write the failing repository test**

`registry/api/tests/conftest.py`:
```python
from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws

TABLE_NAME = "model_pipeline_registry"
REGION = "eu-west-1"


@pytest.fixture
def dynamo_table() -> Iterator[str]:
    with mock_aws():
        resource = boto3.resource("dynamodb", region_name=REGION)
        resource.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "model_name", "KeyType": "HASH"},
                {"AttributeName": "version", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "model_name", "AttributeType": "S"},
                {"AttributeName": "version", "AttributeType": "S"},
                {"AttributeName": "approval_status", "AttributeType": "S"},
                {"AttributeName": "updated_at", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "by_status",
                    "KeySchema": [
                        {"AttributeName": "approval_status", "KeyType": "HASH"},
                        {"AttributeName": "updated_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield TABLE_NAME


def make_record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
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
        "approval_status": "pending",
        "sla_seconds": 3600,
        "cab_record_id": None,
        "ivu_evidence_ref": None,
        "created_at": "2026-05-26T06:00:00+00:00",
        "updated_at": "2026-05-26T06:00:00+00:00",
        "last_scored_at": None,
        "rev": 0,
    }
    record.update(overrides)
    return record
```

`registry/api/tests/test_repository.py`:
```python
import pytest

from registry_api.repository import (
    RecordConflictError,
    RecordNotFoundError,
    RegistryRepository,
)

from .conftest import REGION, make_record


def _repo(table: str) -> RegistryRepository:
    return RegistryRepository(table, REGION)


def test_create_then_get(dynamo_table: str) -> None:
    repo = _repo(dynamo_table)
    repo.create(make_record())
    got = repo.get("credit-risk-pd", "1.0.0")
    assert got["model_name"] == "credit-risk-pd"
    assert got["rev"] == 0


def test_create_duplicate_conflicts(dynamo_table: str) -> None:
    repo = _repo(dynamo_table)
    repo.create(make_record())
    with pytest.raises(RecordConflictError):
        repo.create(make_record())


def test_get_missing_raises(dynamo_table: str) -> None:
    with pytest.raises(RecordNotFoundError):
        _repo(dynamo_table).get("missing", "1.0.0")


def test_update_optimistic_lock(dynamo_table: str) -> None:
    repo = _repo(dynamo_table)
    repo.create(make_record())
    updated = repo.update(
        "credit-risk-pd", "1.0.0", {"sla_seconds": 7200, "updated_at": "2026-05-26T07:00:00+00:00"}, expected_rev=0
    )
    assert updated["rev"] == 1
    assert updated["sla_seconds"] == 7200
    with pytest.raises(RecordConflictError):
        repo.update("credit-risk-pd", "1.0.0", {"sla_seconds": 10}, expected_rev=0)


def test_list_versions_and_by_status(dynamo_table: str) -> None:
    repo = _repo(dynamo_table)
    repo.create(make_record())
    repo.create(make_record(version="1.1.0"))
    assert len(repo.list_versions("credit-risk-pd")) == 2
    assert len(repo.list_by_status("pending")) == 2
    assert repo.list_by_status("approved") == []
```

- [ ] **Step 3: Run it to verify it fails**

Run: `uv run pytest registry/api/tests/test_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: registry_api.repository`.

- [ ] **Step 4: Write the repository**

`registry/api/src/registry_api/repository.py`:
```python
from __future__ import annotations

from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

_CONFLICT = "ConditionalCheckFailedException"


class RecordNotFoundError(Exception):
    """Raised when a (model_name, version) record does not exist."""


class RecordConflictError(Exception):
    """Raised on create-duplicate or optimistic-lock (rev) mismatch."""


class RegistryRepository:
    def __init__(self, table_name: str, region: str) -> None:
        self._table = boto3.resource("dynamodb", region_name=region).Table(table_name)

    def create(self, record: dict[str, Any]) -> dict[str, Any]:
        try:
            self._table.put_item(
                Item=record,
                ConditionExpression="attribute_not_exists(model_name) AND attribute_not_exists(#version)",
                ExpressionAttributeNames={"#version": "version"},
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == _CONFLICT:
                raise RecordConflictError(
                    f"{record['model_name']}@{record['version']} already exists"
                ) from exc
            raise
        return record

    def get(self, model_name: str, version: str) -> dict[str, Any]:
        item = self._table.get_item(Key={"model_name": model_name, "version": version}).get("Item")
        if item is None:
            raise RecordNotFoundError(f"{model_name}@{version} not found")
        return item

    def list_versions(self, model_name: str) -> list[dict[str, Any]]:
        resp = self._table.query(KeyConditionExpression=Key("model_name").eq(model_name))
        return list(resp.get("Items", []))

    def list_by_status(self, status: str) -> list[dict[str, Any]]:
        resp = self._table.query(
            IndexName="by_status",
            KeyConditionExpression=Key("approval_status").eq(status),
        )
        return list(resp.get("Items", []))

    def scan_all(self) -> list[dict[str, Any]]:
        resp = self._table.scan()
        return list(resp.get("Items", []))

    def update(
        self,
        model_name: str,
        version: str,
        changes: dict[str, Any],
        expected_rev: int,
    ) -> dict[str, Any]:
        names: dict[str, str] = {"#rev": "rev"}
        values: dict[str, Any] = {":new_rev": expected_rev + 1, ":exp_rev": expected_rev}
        set_parts = ["#rev = :new_rev"]
        for i, (key, val) in enumerate(changes.items()):
            names[f"#k{i}"] = key
            values[f":v{i}"] = val
            set_parts.append(f"#k{i} = :v{i}")
        try:
            resp = self._table.update_item(
                Key={"model_name": model_name, "version": version},
                UpdateExpression="SET " + ", ".join(set_parts),
                ConditionExpression="attribute_exists(model_name) AND #rev = :exp_rev",
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=values,
                ReturnValues="ALL_NEW",
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == _CONFLICT:
                raise RecordConflictError(
                    f"rev mismatch or missing record for {model_name}@{version}"
                ) from exc
            raise
        return dict(resp["Attributes"])
```

- [ ] **Step 5: Write the settings module**

`registry/api/src/registry_api/settings.py`:
```python
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    table_name: str
    region: str
    log_level: str


@lru_cache
def get_settings() -> Settings:
    return Settings(
        table_name=os.environ["TABLE_NAME"],
        region=os.environ.get("AWS_REGION", "eu-west-1"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest registry/api/tests/test_repository.py -v`
Expected: PASS (5 tests).

- [ ] **Step 7: Commit**

```bash
git add registry/api/pyproject.toml registry/api/src/registry_api/__init__.py registry/api/src/registry_api/settings.py registry/api/src/registry_api/repository.py registry/api/tests/conftest.py registry/api/tests/test_repository.py uv.lock
git commit -m "feat(registry): add settings + DynamoDB repository"
```

---

### Task 7: Approval state machine

**Files:**
- Create: `registry/api/src/registry_api/transitions.py`
- Create: `registry/api/tests/test_transitions.py`

- [ ] **Step 1: Write the failing test**

`registry/api/tests/test_transitions.py`:
```python
import pytest

from registry_api.transitions import (
    ApprovalPreconditionError,
    IllegalTransitionError,
    assert_approval_preconditions,
    assert_transition_allowed,
)


def test_pending_to_approved_allowed() -> None:
    assert_transition_allowed("pending", "approved")


def test_approved_to_retired_allowed() -> None:
    assert_transition_allowed("approved", "retired")


def test_pending_to_retired_illegal() -> None:
    with pytest.raises(IllegalTransitionError):
        assert_transition_allowed("pending", "retired")


def test_approved_to_pending_illegal() -> None:
    with pytest.raises(IllegalTransitionError):
        assert_transition_allowed("approved", "pending")


def test_preconditions_ok_when_cab_and_ivu_present() -> None:
    assert_approval_preconditions({"cab_record_id": "CAB-1", "ivu_evidence_ref": "s3://x/ivu.pdf"})


def test_preconditions_list_missing_fields() -> None:
    with pytest.raises(ApprovalPreconditionError) as exc:
        assert_approval_preconditions({"cab_record_id": None, "ivu_evidence_ref": None})
    assert exc.value.missing == ["cab_record_id", "ivu_evidence_ref"]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest registry/api/tests/test_transitions.py -v`
Expected: FAIL — `ModuleNotFoundError: registry_api.transitions`.

- [ ] **Step 3: Write the module**

`registry/api/src/registry_api/transitions.py`:
```python
from __future__ import annotations

from typing import Any

VALID_STATUSES = ("pending", "approved", "retired")
_ALLOWED_EDGES = {("pending", "approved"), ("approved", "retired")}
_APPROVAL_REQUIRED_FIELDS = ("cab_record_id", "ivu_evidence_ref")


class IllegalTransitionError(Exception):
    """Raised for a transition that is not on the allowed edge set."""


class ApprovalPreconditionError(Exception):
    """Raised when approval is attempted without CAB + IVU evidence."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__("missing approval preconditions: " + ", ".join(missing))


def assert_transition_allowed(current: str, target: str) -> None:
    if (current, target) not in _ALLOWED_EDGES:
        raise IllegalTransitionError(f"cannot transition {current} -> {target}")


def assert_approval_preconditions(record: dict[str, Any]) -> None:
    missing = [field for field in _APPROVAL_REQUIRED_FIELDS if not record.get(field)]
    if missing:
        raise ApprovalPreconditionError(missing)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest registry/api/tests/test_transitions.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add registry/api/src/registry_api/transitions.py registry/api/tests/test_transitions.py
git commit -m "feat(registry): add approval state machine + CAB/IVU guards"
```

---

### Task 8: Audit logging

**Files:**
- Create: `registry/api/src/registry_api/audit.py`
- Create: `registry/api/tests/test_audit.py`

- [ ] **Step 1: Write the failing test**

`registry/api/tests/test_audit.py`:
```python
import json
import logging

from registry_api.audit import emit_audit


def test_emit_audit_writes_json_line(caplog) -> None:  # type: ignore[no-untyped-def]
    with caplog.at_level(logging.INFO, logger="registry.audit"):
        emit_audit(
            principal="arn:aws:iam::111122223333:role/writer",
            action="approve",
            model_name="credit-risk-pd",
            version="1.0.0",
            old_status="pending",
            new_status="approved",
            rev=1,
        )
    record = json.loads(caplog.records[-1].getMessage())
    assert record["action"] == "approve"
    assert record["principal"].endswith("role/writer")
    assert record["old_status"] == "pending"
    assert record["new_status"] == "approved"
    assert record["model"] == "credit-risk-pd@1.0.0"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest registry/api/tests/test_audit.py -v`
Expected: FAIL — `ModuleNotFoundError: registry_api.audit`.

- [ ] **Step 3: Write the module**

`registry/api/src/registry_api/audit.py`:
```python
from __future__ import annotations

import json
import logging

logger = logging.getLogger("registry.audit")


def emit_audit(
    *,
    principal: str,
    action: str,
    model_name: str,
    version: str,
    old_status: str | None = None,
    new_status: str | None = None,
    rev: int | None = None,
) -> None:
    logger.info(
        json.dumps(
            {
                "principal": principal,
                "action": action,
                "model": f"{model_name}@{version}",
                "old_status": old_status,
                "new_status": new_status,
                "rev": rev,
            }
        )
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest registry/api/tests/test_audit.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add registry/api/src/registry_api/audit.py registry/api/tests/test_audit.py
git commit -m "feat(registry): add structured audit logging"
```

---

### Task 9: FastAPI app — create / get / list / patch

**Files:**
- Create: `registry/api/src/registry_api/api_models.py`
- Create: `registry/api/src/registry_api/routes.py`
- Create: `registry/api/src/registry_api/app.py`
- Modify: `registry/api/tests/conftest.py` (add `client` fixture + a create body helper)
- Create: `registry/api/tests/test_api_crud.py`

- [ ] **Step 1: Write the API request models**

`registry/api/src/registry_api/api_models.py`:
```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Tier = Literal["standard", "scalable"]
_S3 = r"^s3://"


class CreateModelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_name: str = Field(pattern=r"^[a-z][a-z0-9-]{2,63}$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    sas_code_version: str = Field(min_length=1)
    inference_code_version: str = Field(min_length=1)
    schedule_cadence: str = Field(min_length=1)
    execution_tier: Tier
    input_schema_ref: str = Field(pattern=_S3)
    output_schema_ref: str = Field(pattern=_S3)
    pir_doc_ref: str = Field(pattern=_S3)
    owner_email: EmailStr
    accountable_executive: str = Field(min_length=1)
    sla_seconds: int = Field(gt=0)
    cab_record_id: str | None = None
    ivu_evidence_ref: str | None = Field(default=None, pattern=_S3)


class UpdateModelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    expected_rev: int = Field(ge=0)
    schedule_cadence: str | None = Field(default=None, min_length=1)
    sla_seconds: int | None = Field(default=None, gt=0)
    last_scored_at: str | None = None
    cab_record_id: str | None = None
    ivu_evidence_ref: str | None = Field(default=None, pattern=_S3)
```

- [ ] **Step 2: Write the app factory + exception handlers**

`registry/api/src/registry_api/app.py`:
```python
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mangum import Mangum

from .repository import RecordConflictError, RecordNotFoundError
from .routes import router
from .transitions import ApprovalPreconditionError, IllegalTransitionError


def _error(status: int, code: str, message: str, detail: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "detail": detail}},
    )


def create_app() -> FastAPI:
    app = FastAPI(title="ABSA x EXL Model & Pipeline Registry", version="1.0.0")
    app.include_router(router)

    @app.exception_handler(RecordNotFoundError)
    def _not_found(_: Request, exc: RecordNotFoundError) -> JSONResponse:
        return _error(404, "not_found", str(exc))

    @app.exception_handler(RecordConflictError)
    def _conflict(_: Request, exc: RecordConflictError) -> JSONResponse:
        return _error(409, "conflict", str(exc))

    @app.exception_handler(IllegalTransitionError)
    def _illegal(_: Request, exc: IllegalTransitionError) -> JSONResponse:
        return _error(409, "illegal_transition", str(exc))

    @app.exception_handler(ApprovalPreconditionError)
    def _precondition(_: Request, exc: ApprovalPreconditionError) -> JSONResponse:
        return _error(422, "approval_preconditions", str(exc), {"missing": exc.missing})

    return app


app = create_app()
handler = Mangum(app)
```

- [ ] **Step 3: Write the routes (create / get / list / patch)**

`registry/api/src/registry_api/routes.py`:
```python
from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status

from platform_contracts.loader import validate as validate_contract

from .api_models import CreateModelRequest, UpdateModelRequest
from .audit import emit_audit
from .repository import RegistryRepository
from .settings import get_settings

router = APIRouter()


@lru_cache
def get_repository() -> RegistryRepository:
    settings = get_settings()
    return RegistryRepository(settings.table_name, settings.region)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _principal(request: Request) -> str:
    event = request.scope.get("aws.event", {})
    try:
        return str(event["requestContext"]["authorizer"]["iam"]["userArn"])
    except (KeyError, TypeError):
        return "local-dev"


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/models", status_code=status.HTTP_201_CREATED)
def create_model(
    body: CreateModelRequest,
    request: Request,
    repo: RegistryRepository = Depends(get_repository),
) -> dict[str, Any]:
    now = _now()
    record = body.model_dump()
    record.update(
        {
            "approval_status": "pending",
            "created_at": now,
            "updated_at": now,
            "last_scored_at": None,
            "rev": 0,
        }
    )
    validate_contract("registry-record", record)
    created = repo.create(record)
    emit_audit(
        principal=_principal(request),
        action="create",
        model_name=created["model_name"],
        version=created["version"],
        new_status="pending",
        rev=0,
    )
    return created


@router.get("/models")
def list_models(
    repo: RegistryRepository = Depends(get_repository),
    status_filter: str | None = Query(default=None, alias="status"),
) -> dict[str, Any]:
    items = repo.list_by_status(status_filter) if status_filter else repo.scan_all()
    return {"items": items, "count": len(items)}


@router.get("/models/{model_name}")
def list_versions(
    model_name: str,
    repo: RegistryRepository = Depends(get_repository),
) -> dict[str, Any]:
    items = repo.list_versions(model_name)
    return {"items": items, "count": len(items)}


@router.get("/models/{model_name}/versions/{version}")
def get_model(
    model_name: str,
    version: str,
    repo: RegistryRepository = Depends(get_repository),
) -> dict[str, Any]:
    return repo.get(model_name, version)


@router.patch("/models/{model_name}/versions/{version}")
def update_model(
    model_name: str,
    version: str,
    body: UpdateModelRequest,
    request: Request,
    repo: RegistryRepository = Depends(get_repository),
) -> dict[str, Any]:
    changes = body.model_dump(exclude={"expected_rev"}, exclude_none=True)
    changes["updated_at"] = _now()
    updated = repo.update(model_name, version, changes, expected_rev=body.expected_rev)
    emit_audit(
        principal=_principal(request),
        action="update",
        model_name=model_name,
        version=version,
        rev=updated["rev"],
    )
    return updated
```

- [ ] **Step 4: Add the `client` fixture and create-body helper to conftest**

First add `from fastapi.testclient import TestClient` to the existing imports at the top of `registry/api/tests/conftest.py` (do **not** re-import `pytest` — it is already imported in Task 6). Then append the helper and fixture below:
```python
def make_create_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
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
    }
    body.update(overrides)
    return body


@pytest.fixture
def client(dynamo_table: str):  # type: ignore[no-untyped-def]
    from registry_api.app import create_app
    from registry_api.repository import RegistryRepository
    from registry_api.routes import get_repository

    app = create_app()
    app.dependency_overrides[get_repository] = lambda: RegistryRepository(dynamo_table, REGION)
    return TestClient(app)
```

- [ ] **Step 5: Write the CRUD route test**

`registry/api/tests/test_api_crud.py`:
```python
from .conftest import make_create_body


def test_create_returns_201_and_pending(client) -> None:  # type: ignore[no-untyped-def]
    resp = client.post("/models", json=make_create_body())
    assert resp.status_code == 201
    body = resp.json()
    assert body["approval_status"] == "pending"
    assert body["rev"] == 0


def test_create_duplicate_returns_409(client) -> None:  # type: ignore[no-untyped-def]
    client.post("/models", json=make_create_body())
    resp = client.post("/models", json=make_create_body())
    assert resp.status_code == 409


def test_create_rejects_unknown_field_422(client) -> None:  # type: ignore[no-untyped-def]
    resp = client.post("/models", json=make_create_body(surprise="x"))
    assert resp.status_code == 422


def test_get_missing_returns_404(client) -> None:  # type: ignore[no-untyped-def]
    resp = client.get("/models/missing/versions/1.0.0")
    assert resp.status_code == 404


def test_list_by_status(client) -> None:  # type: ignore[no-untyped-def]
    client.post("/models", json=make_create_body())
    client.post("/models", json=make_create_body(version="1.1.0"))
    resp = client.get("/models", params={"status": "pending"})
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


def test_patch_updates_and_bumps_rev(client) -> None:  # type: ignore[no-untyped-def]
    client.post("/models", json=make_create_body())
    resp = client.patch(
        "/models/credit-risk-pd/versions/1.0.0",
        json={"expected_rev": 0, "sla_seconds": 7200},
    )
    assert resp.status_code == 200
    assert resp.json()["rev"] == 1
    assert resp.json()["sla_seconds"] == 7200
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest registry/api/tests/test_api_crud.py -v`
Expected: PASS (6 tests).

- [ ] **Step 7: Commit**

```bash
git add registry/api/src/registry_api/api_models.py registry/api/src/registry_api/routes.py registry/api/src/registry_api/app.py registry/api/tests/conftest.py registry/api/tests/test_api_crud.py
git commit -m "feat(registry): add FastAPI app (create/get/list/patch)"
```

---

### Task 10: Approve / retire routes

**Files:**
- Modify: `registry/api/src/registry_api/routes.py` (add `:approve` and `:retire`)
- Create: `registry/api/tests/test_api_transitions.py`

- [ ] **Step 1: Write the failing test**

`registry/api/tests/test_api_transitions.py`:
```python
from .conftest import make_create_body


def _create(client, **o):  # type: ignore[no-untyped-def]
    return client.post("/models", json=make_create_body(**o))


def test_approve_without_cab_ivu_returns_422(client) -> None:  # type: ignore[no-untyped-def]
    _create(client)
    resp = client.post("/models/credit-risk-pd/versions/1.0.0:approve")
    assert resp.status_code == 422
    assert set(resp.json()["error"]["detail"]["missing"]) == {"cab_record_id", "ivu_evidence_ref"}


def test_approve_with_cab_ivu_returns_200(client) -> None:  # type: ignore[no-untyped-def]
    _create(client)
    client.patch(
        "/models/credit-risk-pd/versions/1.0.0",
        json={"expected_rev": 0, "cab_record_id": "CAB-1", "ivu_evidence_ref": "s3://x/ivu.pdf"},
    )
    resp = client.post("/models/credit-risk-pd/versions/1.0.0:approve")
    assert resp.status_code == 200
    assert resp.json()["approval_status"] == "approved"


def test_illegal_pending_to_retire_returns_409(client) -> None:  # type: ignore[no-untyped-def]
    _create(client)
    resp = client.post("/models/credit-risk-pd/versions/1.0.0:retire")
    assert resp.status_code == 409


def test_approve_then_retire(client) -> None:  # type: ignore[no-untyped-def]
    _create(client)
    client.patch(
        "/models/credit-risk-pd/versions/1.0.0",
        json={"expected_rev": 0, "cab_record_id": "CAB-1", "ivu_evidence_ref": "s3://x/ivu.pdf"},
    )
    client.post("/models/credit-risk-pd/versions/1.0.0:approve")
    resp = client.post("/models/credit-risk-pd/versions/1.0.0:retire")
    assert resp.status_code == 200
    assert resp.json()["approval_status"] == "retired"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest registry/api/tests/test_api_transitions.py -v`
Expected: FAIL — 404/405 on the `:approve` path (routes not defined yet).

- [ ] **Step 3: Add the transition routes**

Append to `registry/api/src/registry_api/routes.py` (and extend the imports at the top to include the transition helpers):
```python
from .transitions import assert_approval_preconditions, assert_transition_allowed


def _transition(
    model_name: str,
    version: str,
    target: str,
    request: Request,
    repo: RegistryRepository,
) -> dict[str, Any]:
    current = repo.get(model_name, version)
    assert_transition_allowed(current["approval_status"], target)
    if target == "approved":
        assert_approval_preconditions(current)
    updated = repo.update(
        model_name,
        version,
        {"approval_status": target, "updated_at": _now()},
        expected_rev=int(current["rev"]),
    )
    emit_audit(
        principal=_principal(request),
        action=target,
        model_name=model_name,
        version=version,
        old_status=current["approval_status"],
        new_status=target,
        rev=updated["rev"],
    )
    return updated


@router.post("/models/{model_name}/versions/{version}:approve")
def approve_model(
    model_name: str,
    version: str,
    request: Request,
    repo: RegistryRepository = Depends(get_repository),
) -> dict[str, Any]:
    return _transition(model_name, version, "approved", request, repo)


@router.post("/models/{model_name}/versions/{version}:retire")
def retire_model(
    model_name: str,
    version: str,
    request: Request,
    repo: RegistryRepository = Depends(get_repository),
) -> dict[str, Any]:
    return _transition(model_name, version, "retired", request, repo)
```

> Note: the literal `:approve` / `:retire` action suffix is a valid path segment in Starlette/FastAPI routing. If route matching misbehaves, confirm the path is registered exactly as written (no URL-encoding of the colon).

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest registry/api/tests/test_api_transitions.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Run the full Python suite + lint + types**

Run: `uv run pytest && uv run ruff check . && uv run mypy platform-contracts/src registry/api/src`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add registry/api/src/registry_api/routes.py registry/api/tests/test_api_transitions.py
git commit -m "feat(registry): add approve/retire transition routes"
```

---

### Task 11: `pipeline-registry` Terraform module

**Files:**
- Create: `terraform/modules/pipeline-registry/versions.tf`
- Create: `terraform/modules/pipeline-registry/variables.tf`
- Create: `terraform/modules/pipeline-registry/main.tf`
- Create: `terraform/modules/pipeline-registry/outputs.tf`
- Create: `terraform/modules/pipeline-registry/README.md`
- Create: `terraform/modules/pipeline-registry/tests/pipeline_registry.tftest.hcl`

- [ ] **Step 1: Write `versions.tf`**

```hcl
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws     = { source = "hashicorp/aws", version = "~> 5.100" }
    archive = { source = "hashicorp/archive", version = "~> 2.4" }
  }
}
```

- [ ] **Step 2: Write `variables.tf`**

```hcl
variable "env" {
  type = string
  validation {
    condition     = contains(["dev", "stg", "prod"], var.env)
    error_message = "env must be one of dev, stg, prod."
  }
}

variable "region" {
  type = string
}

variable "table_name" {
  type    = string
  default = "model_pipeline_registry"
}

variable "lambda_source_dir" {
  type        = string
  description = "Path to the registry_api source tree zipped into the deployment artifact."
}

variable "lambda_runtime" {
  type    = string
  default = "python3.12"
}

variable "log_retention_days" {
  type    = number
  default = 365
}

variable "enable_deletion_protection" {
  type    = bool
  default = true
}

variable "tags" {
  type    = map(string)
  default = {}
}
```

- [ ] **Step 3: Write `main.tf`**

```hcl
locals {
  name   = "${var.env}-registry"
  tags   = merge(var.tags, { env = var.env, module = "pipeline-registry", cost_center = "model-hosting" })
}

resource "aws_kms_key" "this" {
  description             = "${local.name} registry data + logs CMK"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  tags                    = local.tags
}

resource "aws_kms_alias" "this" {
  name          = "alias/${local.name}"
  target_key_id = aws_kms_key.this.key_id
}

resource "aws_dynamodb_table" "this" {
  name         = var.table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "model_name"
  range_key    = "version"

  attribute {
    name = "model_name"
    type = "S"
  }
  attribute {
    name = "version"
    type = "S"
  }
  attribute {
    name = "approval_status"
    type = "S"
  }
  attribute {
    name = "updated_at"
    type = "S"
  }

  global_secondary_index {
    name            = "by_status"
    hash_key        = "approval_status"
    range_key       = "updated_at"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.this.arn
  }

  deletion_protection_enabled = var.enable_deletion_protection
  tags                        = local.tags
}

data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = var.lambda_source_dir
  output_path = "${path.module}/.build/${local.name}-lambda.zip"
}

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${local.name}-lambda"
  assume_role_policy = data.aws_iam_policy_document.assume.json
  tags               = local.tags
}

data "aws_iam_policy_document" "lambda" {
  statement {
    sid    = "TableAccess"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem",
      "dynamodb:Query", "dynamodb:Scan",
    ]
    resources = [aws_dynamodb_table.this.arn, "${aws_dynamodb_table.this.arn}/index/*"]
  }
  statement {
    sid       = "KmsData"
    effect    = "Allow"
    actions   = ["kms:Decrypt", "kms:GenerateDataKey"]
    resources = [aws_kms_key.this.arn]
  }
  statement {
    sid       = "Logs"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.lambda.arn}:*"]
  }
}

resource "aws_iam_role_policy" "lambda" {
  name   = "${local.name}-lambda"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda.json
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.name}"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.this.arn
  tags              = local.tags
}

resource "aws_lambda_function" "this" {
  function_name    = local.name
  role             = aws_iam_role.lambda.arn
  runtime          = var.lambda_runtime
  handler          = "registry_api.app.handler"
  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256
  timeout          = 15
  memory_size      = 256

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.this.name
      LOG_LEVEL  = "INFO"
    }
  }

  depends_on = [aws_cloudwatch_log_group.lambda]
  tags       = local.tags
}

resource "aws_apigatewayv2_api" "this" {
  name          = local.name
  protocol_type = "HTTP"
  tags          = local.tags
}

resource "aws_apigatewayv2_integration" "this" {
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.this.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "default" {
  api_id             = aws_apigatewayv2_api.this.id
  route_key          = "$default"
  target             = "integrations/${aws_apigatewayv2_integration.this.id}"
  authorization_type = "AWS_IAM"
}

resource "aws_cloudwatch_log_group" "apigw" {
  name              = "/aws/apigw/${local.name}"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.this.arn
  tags              = local.tags
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.this.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.apigw.arn
    format          = "$context.requestId $context.identity.caller $context.httpMethod $context.path $context.status"
  }
  tags = local.tags
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowApiGwInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}

# Caller policies for read/write IAM separation (attach to ABSA/EXL caller roles).
data "aws_iam_policy_document" "reader" {
  statement {
    effect    = "Allow"
    actions   = ["execute-api:Invoke"]
    resources = ["${aws_apigatewayv2_api.this.execution_arn}/*/GET/*"]
  }
}

resource "aws_iam_policy" "reader" {
  name   = "${local.name}-reader"
  policy = data.aws_iam_policy_document.reader.json
  tags   = local.tags
}

data "aws_iam_policy_document" "writer" {
  statement {
    effect  = "Allow"
    actions = ["execute-api:Invoke"]
    resources = [
      "${aws_apigatewayv2_api.this.execution_arn}/*/POST/*",
      "${aws_apigatewayv2_api.this.execution_arn}/*/PATCH/*",
    ]
  }
}

resource "aws_iam_policy" "writer" {
  name   = "${local.name}-writer"
  policy = data.aws_iam_policy_document.writer.json
  tags   = local.tags
}
```

- [ ] **Step 4: Write `outputs.tf`**

```hcl
output "table_name" { value = aws_dynamodb_table.this.name }
output "table_arn" { value = aws_dynamodb_table.this.arn }
output "kms_key_arn" { value = aws_kms_key.this.arn }
output "lambda_function_arn" { value = aws_lambda_function.this.arn }
output "api_id" { value = aws_apigatewayv2_api.this.id }
output "api_endpoint" { value = aws_apigatewayv2_api.this.api_endpoint }
output "audit_log_group_name" { value = aws_cloudwatch_log_group.lambda.name }
output "reader_policy_arn" { value = aws_iam_policy.reader.arn }
output "writer_policy_arn" { value = aws_iam_policy.writer.arn }
```

- [ ] **Step 5: Write the module `README.md`**

```markdown
# pipeline-registry

Phase 2 sprint 1. Provisions the Model & Pipeline Registry: a DynamoDB table
`model_pipeline_registry` (composite key `model_name` + `version`, `by_status` GSI,
PITR, module-owned KMS SSE, deletion protection) fronted by a single-Lambda FastAPI
app (`registry_api.app.handler`) behind an API Gateway HTTP API with `AWS_IAM` auth.

The CMK is module-owned per ADR-0005 (workload data-class keys live in their owning
module; `kms-hierarchy` owns audit-evidence keys only).

Plan-validate only in sprint 1; real dependency packaging and `apply` land when AWS
credentials are available.
```

- [ ] **Step 6: Write the `tftest`**

`terraform/modules/pipeline-registry/tests/pipeline_registry.tftest.hcl`:
```hcl
mock_provider "aws" {}

variables {
  env               = "dev"
  region            = "eu-west-1"
  lambda_source_dir = "../../../../registry/api/src"
}

run "defaults_validate" {
  command = plan

  assert {
    condition     = aws_dynamodb_table.this.billing_mode == "PAY_PER_REQUEST"
    error_message = "table must be on-demand"
  }
  assert {
    condition     = aws_dynamodb_table.this.hash_key == "model_name" && aws_dynamodb_table.this.range_key == "version"
    error_message = "composite key must be (model_name, version)"
  }
  assert {
    condition     = one(aws_dynamodb_table.this.point_in_time_recovery[*].enabled) == true
    error_message = "PITR must be enabled"
  }
  assert {
    condition     = length([for gsi in aws_dynamodb_table.this.global_secondary_index : gsi if gsi.name == "by_status"]) == 1
    error_message = "by_status GSI must exist"
  }
  assert {
    condition     = aws_dynamodb_table.this.deletion_protection_enabled == true
    error_message = "deletion protection default must be true"
  }
  assert {
    condition     = aws_lambda_function.this.runtime == "python3.12"
    error_message = "lambda runtime must be python3.12"
  }
  assert {
    condition     = aws_lambda_function.this.environment[0].variables["TABLE_NAME"] == "model_pipeline_registry"
    error_message = "TABLE_NAME env var must be set"
  }
  assert {
    condition     = aws_apigatewayv2_route.default.authorization_type == "AWS_IAM"
    error_message = "route auth must be AWS_IAM"
  }
  assert {
    condition     = one(aws_dynamodb_table.this.server_side_encryption[*].enabled) == true
    error_message = "table SSE must be enabled (module-owned CMK)"
  }
}

run "deletion_protection_override" {
  command = plan
  variables {
    enable_deletion_protection = false
  }
  assert {
    condition     = aws_dynamodb_table.this.deletion_protection_enabled == false
    error_message = "deletion protection override must be honoured"
  }
}
```

- [ ] **Step 7: Format, init, validate, and test the module**

Run from `terraform/modules/pipeline-registry`:
```bash
terraform fmt -recursive
terraform init -backend=false
terraform validate
terraform test
```
Expected: `fmt` makes no further changes; `validate` succeeds; `terraform test` reports 2 passed runs. If `terraform test` cannot resolve the `archive` provider under `mock_provider`, add `mock_provider "archive" {}` alongside the aws mock and re-run.

- [ ] **Step 8: Commit**

```bash
git add terraform/modules/pipeline-registry/
git commit -m "feat(tf): add pipeline-registry module (dynamodb + lambda + http api)"
```

---

### Task 12: Per-env registry stacks

**Files:**
- Create: `terraform/envs/dev/registry/{main.tf,variables.tf,locals.tf,terraform.tfvars}`
- Create: `terraform/envs/stg/registry/{main.tf,variables.tf,locals.tf,terraform.tfvars}`
- Create: `terraform/envs/prod/registry/{main.tf,variables.tf,locals.tf,terraform.tfvars}`

- [ ] **Step 1: Write the dev stack**

`terraform/envs/dev/registry/main.tf`:
```hcl
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.100" }
  }
}

provider "aws" {
  region = var.region
}

module "registry" {
  source                     = "../../../modules/pipeline-registry"
  env                        = local.env
  region                     = var.region
  lambda_source_dir          = "${path.module}/../../../../registry/api/src"
  log_retention_days         = 30
  enable_deletion_protection = false
  tags                       = local.tags
}
```

`terraform/envs/dev/registry/variables.tf`:
```hcl
variable "region" {
  type    = string
  default = "eu-west-1"
}
```

`terraform/envs/dev/registry/locals.tf`:
```hcl
locals {
  env = "dev"
  tags = {
    project = "absa-exl-model-hosting"
    env     = local.env
  }
}
```

`terraform/envs/dev/registry/terraform.tfvars`:
```hcl
region = "eu-west-1"
```

- [ ] **Step 2: Write the stg stack**

Repeat the four dev files into `terraform/envs/stg/registry/` with these changes: in `locals.tf` set `env = "stg"`; in `main.tf` set `log_retention_days = 90` and `enable_deletion_protection = true`.

`terraform/envs/stg/registry/main.tf`:
```hcl
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.100" }
  }
}

provider "aws" {
  region = var.region
}

module "registry" {
  source                     = "../../../modules/pipeline-registry"
  env                        = local.env
  region                     = var.region
  lambda_source_dir          = "${path.module}/../../../../registry/api/src"
  log_retention_days         = 90
  enable_deletion_protection = true
  tags                       = local.tags
}
```

`terraform/envs/stg/registry/variables.tf`:
```hcl
variable "region" {
  type    = string
  default = "eu-west-1"
}
```

`terraform/envs/stg/registry/locals.tf`:
```hcl
locals {
  env = "stg"
  tags = {
    project = "absa-exl-model-hosting"
    env     = local.env
  }
}
```

`terraform/envs/stg/registry/terraform.tfvars`:
```hcl
region = "eu-west-1"
```

- [ ] **Step 3: Write the prod stack**

`terraform/envs/prod/registry/main.tf`:
```hcl
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.100" }
  }
}

provider "aws" {
  region = var.region
}

module "registry" {
  source                     = "../../../modules/pipeline-registry"
  env                        = local.env
  region                     = var.region
  lambda_source_dir          = "${path.module}/../../../../registry/api/src"
  log_retention_days         = 365
  enable_deletion_protection = true
  tags                       = local.tags
}
```

`terraform/envs/prod/registry/variables.tf`:
```hcl
variable "region" {
  type    = string
  default = "eu-west-1"
}
```

`terraform/envs/prod/registry/locals.tf`:
```hcl
locals {
  env = "prod"
  tags = {
    project = "absa-exl-model-hosting"
    env     = local.env
  }
}
```

`terraform/envs/prod/registry/terraform.tfvars`:
```hcl
region = "eu-west-1"
```

- [ ] **Step 4: Validate all three stacks**

Run for each of `terraform/envs/{dev,stg,prod}/registry`:
```bash
terraform fmt -recursive
terraform init -backend=false
terraform validate
```
Expected: each `validate` succeeds. (No `apply`; no backend.)

- [ ] **Step 5: Commit**

```bash
git add terraform/envs/dev/registry/ terraform/envs/stg/registry/ terraform/envs/prod/registry/
git commit -m "feat(tf): add per-env registry stacks (dev/stg/prod)"
```

---

### Task 13: CI — Python validate + Terraform matrix update

**Files:**
- Create: `.github/workflows/python-validate.yml`
- Modify: `.github/workflows/terraform-validate.yml` (add `phase-2/**` triggers + the new module and env stacks to the matrices)

> **Spec/reality note:** spec §4 and §10 listed these under `ci/pipelines/` (the brief's layout), but Phase 1's real workflows live in `.github/workflows/` — the only path GitHub Actions executes. This plan targets reality.

- [ ] **Step 1: Open the existing Terraform workflow**

Run: `cat .github/workflows/terraform-validate.yml`
Expected: confirm the `validate-modules` matrix `module:` list, the `validate-stacks` matrix `stack:` list, and the `on.pull_request.branches` / `on.push.branches` lists before editing them in Step 3.

- [ ] **Step 2: Write the Python CI workflow**

`.github/workflows/python-validate.yml`:
```yaml
name: python-validate

on:
  pull_request:
    paths:
      - "platform-contracts/**"
      - "registry/**"
      - "pyproject.toml"
      - "uv.lock"
      - ".python-version"
      - ".github/workflows/python-validate.yml"

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true
      - name: Sync
        run: uv sync --frozen
      - name: Lint
        run: uv run ruff check .
      - name: Format check
        run: uv run ruff format --check .
      - name: Types
        run: uv run mypy platform-contracts/src registry/api/src
      - name: Tests
        run: uv run pytest
      - name: Contract model drift check
        run: |
          bash platform-contracts/regenerate-models.sh
          git diff --exit-code platform-contracts/src/platform_contracts/models.py
```

- [ ] **Step 3: Wire the new Terraform targets + phase-2 triggers**

Make three edits to `.github/workflows/terraform-validate.yml`:

(a) Add `phase-2/**` to both branch filters. There are two `branches:` blocks (one under `pull_request`, one under `push`); change each:
```yaml
    branches:
      - main
      - "phase-1/**"
```
to:
```yaml
    branches:
      - main
      - "phase-1/**"
      - "phase-2/**"
```

(b) Add the module to the `validate-modules` matrix:
```yaml
        module:
          - landing-zone
          - s3-replication-source
          - s3-replication-destination
          - kms-hierarchy
          - iam-federation
          - pipeline-registry
```

(c) Add the three stacks to the `validate-stacks` matrix (after the existing `prod/destination` entry):
```yaml
          - terraform/envs/prod/destination
          - terraform/envs/dev/registry
          - terraform/envs/stg/registry
          - terraform/envs/prod/registry
          - terraform/account-bootstrap/exl-dev
```

The `validate-modules` job's `terraform test` step already injects dummy AWS creds + `AWS_REGION`; the `pipeline-registry` module test uses `mock_provider` so those are ignored but harmless.

- [ ] **Step 4: Validate the workflow YAML locally**

Run: `uv run --with pyyaml python -c "import yaml; yaml.safe_load(open('.github/workflows/python-validate.yml')); yaml.safe_load(open('.github/workflows/terraform-validate.yml')); print('yaml ok')"`
Expected: prints `yaml ok` (`uv run --with pyyaml` pulls PyYAML ephemerally — no project dep added). Then run `uv run ruff format --check .` and fix with `uv run ruff format .` if it reports changes, so the new CI format-check step will pass.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/python-validate.yml .github/workflows/terraform-validate.yml
git commit -m "ci: add python-validate workflow + register registry tf targets"
```

---

### Task 14: ADRs, compliance rows, CODEOWNERS, pointers, READMEs

**Files:**
- Create: `docs/adr/0006-contract-strategy-json-schema-canonical.md`
- Create: `docs/adr/0007-registry-data-model-and-api.md`
- Modify: `docs/compliance/control-matrix.md` (append Phase 2 registry rows)
- Modify: `CODEOWNERS` (add `platform-contracts/**`, `registry/**`)
- Create: `registry/schema/README.md` (pointer)
- Create: `pipeline-factory/config-schema/README.md` (pointer)
- Modify: `registry/README.md` (describe the API)

- [ ] **Step 1: Write ADR-0006**

`docs/adr/0006-contract-strategy-json-schema-canonical.md`:
```markdown
# ADR-0006: Contract strategy — JSON Schema canonical, Pydantic generated

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-05-26 |
| Deciders | Engagement lead, EXL Platform Engineering |

## Context

Phase 2 introduces shared contracts (model-config, registry-record,
manifest-envelope) consumed by the Registry, the Pipeline Factory, and Code Intake —
two of which are not Python. The contract must be language-neutral, versioned, and
citable in the audit pack, while the Registry API needs typed Python models. This is
also the repo's first Python, so the tooling baseline is decided here.

## Decision

JSON Schema (Draft 2020-12) is the hand-authored canonical contract, stored in the
shared `platform-contracts` package. Pydantic v2 models are generated from the
schemas with `datamodel-code-generator` and committed; CI regenerates and fails on
any diff, enforcing the "Pydantic equals JSON Schema" invariant.

Python tooling baseline (platform-wide): uv (with committed `uv.lock`) for
environment and dependencies, ruff for lint + format, mypy (strict) for types,
pytest for tests.

## Consequences

### Positive
- Language-neutral contract auditors and non-Python subsystems can consume.
- No hand-sync drift between schema and models — CI proves equivalence.
- Reproducible builds via the lockfile.

### Negative
- A code-generation step in the toolchain; contributors must run
  `regenerate-models.sh` after editing a schema.
- Generated `models.py` is committed (a generated artifact in source control), which
  is the deliberate trade for the CI drift gate.

## Alternatives considered
1. Pydantic canonical, JSON Schema generated. Rejected: the audit contract would be
   a generated file living in Python code.
2. Two hand-maintained definitions. Rejected: they drift.
```

- [ ] **Step 2: Write ADR-0007**

`docs/adr/0007-registry-data-model-and-api.md`:
```markdown
# ADR-0007: Registry data model & API

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-05-26 |
| Deciders | Engagement lead, EXL Platform Engineering |

## Context

The Model & Pipeline Registry is the Phase 2 system of record. The brief (§7)
fixes a DynamoDB table keyed by (model_name, version), fronted by a FastAPI API on
Lambda + API Gateway, with IAM-authed writes and CloudTrail audit. Open choices were
the API packaging, the access patterns / indexes, the approval workflow, and the
encryption key ownership.

## Decision

- Single DynamoDB table `model_pipeline_registry`, composite key
  `model_name` (PK) + `version` (SK); on-demand billing; PITR on; one GSI
  `by_status` (`approval_status` + `updated_at`) for approval/ops listing; full
  listing via scan (acceptable at 10-model scale).
- FastAPI runs as one Lambda via Mangum behind an API Gateway HTTP API with
  `AWS_IAM` (SigV4) authorization. Lambda Web Adapter is the documented migration
  path if scale/real-time needs arrive.
- Approval state machine `pending -> approved -> retired`, strictly ordered;
  `:approve` requires `cab_record_id` and `ivu_evidence_ref` (brief §9); status
  changes only via `:approve`/`:retire`, never via `PATCH`.
- The table SSE CMK and the API/Lambda log-group CMK are module-owned, per ADR-0005
  (workload data-class keys live in their owning module).
- Optimistic concurrency via a `rev` counter with DynamoDB condition expressions.

## Consequences

### Positive
- Matches the brief; minimal infra; strong local/`moto` test story.
- Audit-critical approval gate is enforced server-side and cannot be bypassed.

### Negative
- One IAM role spans all routes (read/write separation is by caller-role policy +
  CloudTrail), accepted at this scale.
- Scan-based full listing would need a rethink well beyond 10 models.

## Alternatives considered
1. Per-route Lambdas. Rejected: contradicts the brief's "FastAPI"; heavy infra.
2. Lambda Web Adapter container now. Rejected: needs ECR + build pipeline for no
   present benefit; retained as the future migration path.
```

- [ ] **Step 3: Add the Phase 2 controls section**

In `docs/compliance/control-matrix.md`, insert this section immediately **before** the `## Out-of-matrix items (deferred)` heading, matching the existing 4-column format (Control | Implementation | Evidence artifact | Owner):
```markdown
## Phase 2 controls (sprint 1 — Registry)

| Control | Implementation | Evidence artifact | Owner |
| --- | --- | --- | --- |
| **SARB GOI 3 — model risk governance** | Registry approval gate: `approval_status` cannot reach `approved` without `cab_record_id` + `ivu_evidence_ref` | `registry/api/src/registry_api/transitions.py`, `docs/adr/0007-registry-data-model-and-api.md` | ABSA Model Risk |
| **SR 11-7 III.4 — model implementation evidence** | Structured audit log (principal / action / old→new / rev) per mutation + CloudTrail on API GW, Lambda, DynamoDB | `registry/api/src/registry_api/audit.py`, `terraform/modules/pipeline-registry/main.tf` | EXL Platform Engineering |
| **ISO 27001 A.10.1 — cryptographic controls** | Module-owned CMK (rotation enabled) for DynamoDB SSE + log groups | `terraform/modules/pipeline-registry/main.tf` (aws_kms_key.this) | EXL Platform Engineering |
| **ISO 27001 A.9 / SOC 2 CC6.1 — logical access** | API Gateway `AWS_IAM` (SigV4) auth; reader/writer caller policies scope `execute-api:Invoke` by HTTP method | `terraform/modules/pipeline-registry/main.tf` (route auth + reader/writer policies) | EXL Platform Engineering |
| **SOC 2 CC6.1 — recoverability of evidence** | DynamoDB PITR on the registry table | `terraform/modules/pipeline-registry/main.tf` (point_in_time_recovery) | EXL Platform Engineering |
| **ABSA GMRMG — model inventory + ownership** | Authoritative registry record with owner, accountable executive, SLA per model version | `platform-contracts/src/platform_contracts/schemas/registry-record.schema.json` | ABSA Model Risk |
```

Then, in the `## Out-of-matrix items (deferred)` list, delete the now-satisfied bullet (this sprint implements it):
`- **SARB GOI 3 — model risk governance**: Phase 2 (Registry approval gate + CAB record linkage).`

- [ ] **Step 4: Update CODEOWNERS**

Append to `CODEOWNERS`, matching the existing no-leading-slash, column-aligned style:
```
platform-contracts/                @platform-leads
registry/                          @platform-leads
```

- [ ] **Step 5: Write the pointer READMEs**

`registry/schema/README.md`:
```markdown
# registry/schema

Canonical schemas live in the shared package:
`platform-contracts/src/platform_contracts/schemas/` (see ADR-0006). This directory
is intentionally a pointer to keep one source of truth for the audited contract.
```

`pipeline-factory/config-schema/README.md`:
```markdown
# pipeline-factory/config-schema

The model-config JSON Schema is canonical in the shared package:
`platform-contracts/src/platform_contracts/schemas/model-config.schema.json`
(see ADR-0006). This directory is a pointer.
```

- [ ] **Step 6: Update `registry/README.md` and the root `README.md`**

Replace the contents of `registry/README.md` with:
```markdown
# registry

Phase 2 sprint 1 — Model & Pipeline Registry. The system of record for every model
version and its generated pipeline.

- `api/` — FastAPI app (single Lambda via Mangum) over DynamoDB; routes for
  create / get / list / patch and `:approve` / `:retire` transitions with a
  CAB+IVU-guarded approval gate (ADR-0007).
- `schema/` — pointer to the canonical schemas in `platform-contracts` (ADR-0006).

Terraform for the table + API lives in `terraform/modules/pipeline-registry/` and is
instantiated per env in `terraform/envs/{env}/registry/`.

Local dev: `uv run uvicorn registry_api.app:app --reload` (set `TABLE_NAME`).
Tests: `uv run pytest registry/api/tests`.
```

Then update the root `README.md`:

- Replace the `## Status` section with:
```markdown
## Status

Phase 1 foundation complete (kickoff + sprint 2). Phase 2 sprint 1 (Registry & shared contracts) in progress. See [`docs/superpowers/plans/2026-05-26-absa-exl-phase-2-sprint-1-registry.md`](docs/superpowers/plans/2026-05-26-absa-exl-phase-2-sprint-1-registry.md).
```

- In the repository-layout block, add a line for the new shared package (directly above the `registry/` line):
```
platform-contracts/          Shared JSON-Schema contracts + generated Pydantic models (Phase 2)
```

- [ ] **Step 7: Final full verification**

Run from repo root:
```bash
uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy platform-contracts/src registry/api/src
```
Then run `terraform fmt -check -recursive terraform/` from the repo root.
Expected: all green; `fmt -check` reports nothing to change.

- [ ] **Step 8: Commit**

```bash
git add docs/adr/0006-contract-strategy-json-schema-canonical.md docs/adr/0007-registry-data-model-and-api.md docs/compliance/control-matrix.md CODEOWNERS registry/schema/README.md pipeline-factory/config-schema/README.md registry/README.md README.md
git commit -m "docs(phase-2): add registry ADRs, compliance rows, pointers"
```

---

## Final Checklist (run before opening the PR)

- [ ] `uv run pytest` — all Python tests pass
- [ ] `uv run ruff check . && uv run ruff format --check .` — clean
- [ ] `uv run mypy platform-contracts/src registry/api/src` — clean
- [ ] `terraform fmt -check -recursive terraform/` — clean
- [ ] `terraform validate` passes in `terraform/modules/pipeline-registry` and all three `terraform/envs/*/registry`
- [ ] `terraform test` passes in `terraform/modules/pipeline-registry`
- [ ] `tflint --recursive` passes for the new module + stacks (CI runs it non-soft-fail)
- [ ] Every spec §14 deliverable has a corresponding committed file
- [ ] Open one squash-merge PR `phase-2/sprint-1-registry` -> `main` for engagement-lead review at the checkpoint gate
