# ABSA × EXL Phase 2 Sprint 4 — Code Intake + First Track A Run (Design)

**Status:** Accepted (design phase)
**Date:** 2026-06-04
**Branch:** `phase-2/sprint-4-code-intake`
**Predecessors:** Sprint 1 (Registry & Shared Contracts), Sprint 2 (Pipeline Factory), Sprint 3 (Signing & OIDC Foundation, merged `767d434`).
**Successor:** Phase 3 (real AWS account onboarding, real SAS validation depth, per-package venvs).

---

## 1 · Goal

Close out Phase 2 by shipping the third stage of the audit chain — Code Intake — and proving the whole chain works end-to-end with a worked example. Concretely:

- A new `code-intake/` uv workspace member that validates a productized package (SAS + Python code, schema, tests, PIR mapping) and emits a signed package manifest.
- A `payload.upstream_refs[]` extension to the pipeline manifest schema so Pipeline Factory's manifest references the Code Intake-validated package by digest. The pipeline's signature now covers the cross-link, completing the chain-of-custody from validated package → generated pipeline → registry inventory.
- A worked-example package `packages/credit-risk-pd/1.0.0/` (the same model that's threaded through Sprints 2 and 3) with synthetic SAS + Python + PIR + tests + model_config. Code Intake validates it; Pipeline Factory's existing `credit-risk-pd@1.0.0` pipeline gets the `upstream_package` block added and regenerates its manifest with the cross-link.
- A single end-to-end integration test exercising the full Track A chain (Code Intake → Pipeline Factory → signer → mock registrar) inside one moto context.

Out of Sprint 4, Phase 2 is complete: the platform validates packages, generates pipelines, signs both, and registers them — all without real AWS, all under deterministic drift gates, all with audit-grade chain-of-custody.

---

## 2 · Decomposition context

Sprint 3's spec called the remaining Phase 2 work "Code Intake + first end-to-end Track A run." The brainstorming session at the start of Sprint 4 considered splitting it into two sub-sprints (Code Intake alone, then the end-to-end run) but decided against it: the first-end-to-end run is the natural acceptance test for Code Intake, and one PR closing out Phase 2 makes for cleaner storytelling. The combined sprint is ~13–17 tasks, comparable to Sprints 2 and 3 in size.

---

## 3 · Scope and non-goals

### 3.1 In scope

1. **New `code-intake/` uv workspace member.** Five checker modules + an orchestrator + a Click CLI:
   - `checkers/static_python.py` — subprocess `ruff check`, `mypy --strict`, `pytest --collect-only` against the package's `python/` directory.
   - `checkers/static_sas.py` — structural checks: every `.sas` file exists, is non-empty, has balanced `PROC <X>; ... RUN;` blocks (simple text-based state machine; not a real SAS parser).
   - `checkers/schema.py` — validates the package's `model_config.yaml` against `package-manifest-payload.schema.json`; cross-checks artefact references against on-disk SHA-256 hashes.
   - `checkers/tests.py` — actually invokes `pytest` against `python/tests/`.
   - `checkers/pir.py` — validates `pir.yaml` against `pir-mapping.schema.json`; uses Python's stdlib `ast` to extract column references from `score.py` and asserts every referenced column is in `pir.inputs[]`.
   - `orchestrator.py` — runs all five checkers, collects every `CheckResult`, never short-circuits. A checker that raises becomes a single error-severity finding (`<CHECKER>999`), not a stack trace.

2. **Two new JSON Schema contracts in `platform-contracts`:**
   - `package-manifest-payload.schema.json` — the Code Intake payload type. Required fields: `schema_version`, `code_intake_version`, `model_name`, `version`, `generated_at`, `package_layout` (per-artefact SHA-256s), `validation_summary` (per-checker pass/fail + finding codes).
   - `pir-mapping.schema.json` — describes `pir.yaml`. Required fields: `mapping_version`, `model_name`, `model_version`, `inputs[]` (name/type/source/description/nullable), `outputs[]` (name/type/description).

3. **Additive extension to `pipeline-manifest-payload.schema.json`:** new optional `upstream_refs[]` field defaulting to `[]`. Each entry is `{type: "package", ref: "<name>@<version>", digest: "<hex sha256>"}`. The pipeline's own signature covers this array (envelope signature is over the entire payload), so tampering with the cross-link is detected at the pipeline layer. Verifiers reconstruct the full chain by fetching the upstream manifest from S3 and matching hex digests.

4. **Pipeline-factory extension** (additive):
   - `pipeline-factory.manifest.build_payload` gains an optional `upstream_refs` parameter, defaulting to `[]`.
   - New `pipeline_factory/upstream_resolver.py` — pure function reading `packages/<name>/<version>/manifest.json` and returning the `upstream_refs[]` entry. Raises `GeneratorError` if the package manifest is missing or lacks a `digest`.
   - `pipeline_factory.generator` calls the resolver when the loaded model config has an `upstream_package: {name, version}` block.
   - The pipeline-factory `model-config.schema.json` gains the optional `upstream_package` block.

5. **Worked example `packages/credit-risk-pd/1.0.0/`:** synthetic SAS scoring stub + Python `score(data)` function + 2-3 pytest unit tests + PIR YAML mapping the three Python-referenced columns (`income_band`, `tenure_months`, `delinquencies`) + a package-level `model_config.yaml` + README. Sufficient to make every checker exercise a real code path.

6. **CI workflows:**
   - New `.github/workflows/code-intake.yml` — `validate-and-generate-package` job that runs `code-intake validate --strict` + `code-intake generate-manifest` on every `packages/*/*/` directory, then asserts `git diff --exit-code packages/`. Validate-only — no signing or registration.
   - Existing `.github/workflows/pipeline-factory.yml` — minimal additive changes: add `packages/**` to trigger paths (so changing a package retriggers the pipeline-factory drift gate via the cross-link), and change the `sign` step to loop `manifest-signer sign-all` over both `packages` and `pipelines` roots.

7. **End-to-end integration test** `code-intake/tests/test_e2e_track_a.py` exercising the full Track A chain in one moto context: validate package → generate package manifest → sign → upload to mocked S3 → run `generate-pipeline generate` with cross-link → sign pipeline manifest → verify both signatures online and offline → assert the pipeline's `upstream_refs[0].digest` matches the package manifest's `digest`.

8. **ADR-0010 — Productized Package Contract** (new) and a minor edit to ADR-0006 listing the two new schemas.

### 3.2 Out of scope (explicitly deferred)

- **Real SAS linting / SAS runtime execution** → Phase 3. Needs ABSA's SAS environment + Docker container infrastructure. Sprint 4 ships structural-only checks; ADR-0010 documents the deferral.
- **Production Input Register tied to ABSA's real PIR system** → Phase 3. Sprint 4 ships a JSON Schema describing what a PIR file looks like + a sample YAML; the actual PIR feed integration is a Phase 3 deliverable.
- **Per-package virtualenvs** → Phase 3. Sprint 4 assumes the package's Python toolchain is compatible with the workspace's (works for synthetic packages with no extra deps; the worked example complies). Phase 3 packages with isolated runtime deps will need `uv venv` per package or a container-based isolation step.
- **Parallel checker execution** → Phase 3 performance work. Sprint 4 runs checkers sequentially; for the 5 checkers × seconds-per-package this is acceptable.
- **A graphical UI for Code Intake findings** → never. CI logs + the JSON output mode are sufficient.
- **New IAM role / Terraform module for Code Intake** → not needed. Sprint 4 reuses the Sprint-3 `pipeline-factory-signer` role (whose `s3:PutObject` is already scoped to the entire signed-manifests bucket, covering both `packages/...` and `pipelines/...` prefixes). No new TF in Sprint 4 at all.
- **Live `terraform apply`** → Phase 4 alongside ABSA account handover.

### 3.3 Platform-boundary statement

All Code Intake compute runs in EXL CI (GitHub Actions runners), same as Sprints 2-3. The validators read git-tracked package source, run subprocess linters/tests, and emit a signed envelope in S3. ABSA's role on Code Intake is read-only audit — they can fetch any package manifest from S3 and verify offline against the published public key, exactly the same way they audit pipeline manifests.

The brief's Pattern Z account topology remains unchanged: Code Intake adds zero new accounts, zero new IAM roles, zero new buckets.

---

## 4 · Architecture

### 4.1 Chain of custody

```
EXL Industrialization Team produces a package
        |
        v
   packages/<name>/<version>/
        ├── model_config.yaml     (package contract — files, tests, PIR ref)
        ├── sas/...               (SAS scoring code)
        ├── python/               (Python scoring + tests)
        ├── pir.yaml              (PIR mapping)
        └── (no manifest.json yet)
        |
        v
+----------------+
| code-intake    |  `code-intake validate --package <path>`
| validators     |   - static_python  (ruff + mypy + pytest --collect-only)
| run            |   - static_sas     (structural: PROC/RUN balance, non-empty)
+----------------+   - schema         (model_config.yaml + artefact-hash match)
                     - tests          (pytest python/tests/)
                     - pir            (pir.yaml + Python column cross-check)
                     |
                     v  (all checkers pass; collect-all-findings)
+----------------+
| code-intake    |  `code-intake generate-manifest --package <path>`
| renders        |   emits packages/<name>/<version>/manifest.json with
| unsigned       |   payload.type = "package", artefact_hashes, pir_ref,
| manifest       |   signature = "UNSIGNED" (sentinel)
+----------------+
        |
        v  (on push to main; Sprint-3 sign-all walks packages/* too)
+----------------+
| manifest-signer|  kms:Sign + s3:PutObject to
| signs package  |  s3://exl-platform-signed-manifests/packages/<name>/<version>/manifest.json
+----------------+
        |
        v
   pipeline-factory/configs/<name>/<version>/model_config.yaml
        + upstream_package: {name, version}     (NEW Sprint-4 field)
        |
        v
+----------------+
| pipeline-      |  `generate-pipeline generate --config <pipeline_config>`
| factory        |   reads packages/<name>/<version>/manifest.json
| generates with |   embeds upstream_refs[]: [{type, ref, digest}]
| cross-link     |   the pipeline signature covers the cross-link
+----------------+
        |
        v  (Sprint 3's sign job continues unchanged for pipelines/)
+----------------+
| manifest-signer|  kms:Sign the pipeline manifest
| signs pipeline |  uploads to s3://.../pipelines/<name>/<version>/manifest.json
+----------------+
        |
        v  (Sprint 3's register job continues unchanged)
+----------------+
| registrar      |  POST/PATCH /pipelines → registry inventory record
+----------------+
```

### 4.2 Key design properties

- **Cryptographic chain.** Registry record → pipeline manifest digest → `upstream_refs[0].digest` → package manifest. Each link's signature covers the next link's identifier; tampering anywhere breaks signature verification at the next hop. Auditors traverse the chain by fetching signed manifests from S3 and matching hex digests against published public keys.
- **Drift-gate symmetry.** Each subsystem regenerates its `manifest.json` and asserts `git diff --exit-code`. Re-publishing a package bumps its manifest's `digest`, which forces `pipelines/<name>/<version>/manifest.json` to regenerate with the new digest in `upstream_refs[0]`, which makes the pipeline-factory drift gate fail until the pipeline manifest is also regenerated. Forgetting to update either side surfaces in PR review, not in production.
- **No new IAM principals.** The Sprint-3 `pipeline-factory-signer` role has `s3:PutObject` on the entire `signed_manifests_bucket`. Adding `packages/...` writes needs no policy change; the new prefix flows under the same audit role.
- **Verifier compatibility.** Sprint 3's `manifest-signer verify_online` and `verify_offline` work unchanged on package manifests — the envelope shape is identical (only `payload.type` and field set differ). Sprint 4 needs zero verifier-code changes.

---

## 5 · Repository layout

### 5.1 Net-new and modified files

```
code-intake/                                          (new uv workspace member)
├── pyproject.toml                                    (entry point: code-intake)
├── README.md
├── src/code_intake/
│   ├── __init__.py
│   ├── errors.py                # CodeIntakeError, ValidationError, PackageConfigError
│   ├── checkers/
│   │   ├── __init__.py
│   │   ├── base.py              # Checker protocol + Finding + CheckResult dataclasses
│   │   ├── static_python.py     # ruff + mypy + pytest --collect-only
│   │   ├── static_sas.py        # structural PROC/RUN balance scanner
│   │   ├── schema.py            # model_config + artifact-hash cross-check
│   │   ├── tests.py             # real pytest invocation
│   │   └── pir.py               # pir.yaml + Python AST column cross-check
│   ├── orchestrator.py          # runs all checkers, aggregates CheckResults
│   ├── package_config.py        # loader + Pydantic for packages' model_config.yaml
│   ├── manifest.py              # build_package_payload + build_envelope
│   └── cli.py                   # Click: validate / generate-manifest
└── tests/
    ├── conftest.py
    ├── fixtures/
    │   ├── valid_package/
    │   ├── broken_python/       # ruff lint error
    │   ├── broken_sas/          # PROC/RUN imbalance
    │   ├── broken_schema/       # missing required field
    │   ├── broken_tests/        # failing pytest
    │   └── broken_pir/          # column referenced by Python not in PIR
    ├── test_checker_static_python.py
    ├── test_checker_static_sas.py
    ├── test_checker_schema.py
    ├── test_checker_tests.py
    ├── test_checker_pir.py
    ├── test_orchestrator.py
    ├── test_manifest.py
    ├── test_package_config.py
    ├── test_cli.py
    └── test_e2e_track_a.py      # the integration test

platform-contracts/src/platform_contracts/schemas/
├── package-manifest-payload.schema.json             (NEW)
├── pir-mapping.schema.json                          (NEW)
└── pipeline-manifest-payload.schema.json            (MODIFY — add optional upstream_refs[])

platform-contracts/src/platform_contracts/
└── models.py                                         (REGENERATE via Sprint-1 codegen + AST merger)

pipeline-factory/src/pipeline_factory/
├── manifest.py                                       (MODIFY — build_payload accepts upstream_refs)
├── generator.py                                      (MODIFY — resolves upstream_package -> upstream_refs)
└── upstream_resolver.py                              (NEW — thin reader for package manifest)

pipeline-factory/src/pipeline_factory/schemas/model-config.schema.json
                                                      (MODIFY — add optional upstream_package block)

pipeline-factory/configs/credit-risk-pd/1.0.0/
└── model_config.yaml                                 (MODIFY — add upstream_package: {name, version})

packages/credit-risk-pd/1.0.0/                       (NEW worked example)
├── model_config.yaml                                 (package contract)
├── sas/score.sas                                     (synthetic SAS scoring stub)
├── python/
│   ├── score.py                                      (~25 lines)
│   └── tests/
│       └── test_score.py                             (~30 lines, 2-3 tests)
├── pir.yaml                                          (3 inputs, 2 outputs)
├── manifest.json                                     (generated; UNSIGNED in git)
└── README.md

pipelines/credit-risk-pd/1.0.0/                      (REGENERATE — adds upstream_refs[])
└── manifest.json                                     (other files unchanged)

.github/workflows/code-intake.yml                    (NEW)
.github/workflows/pipeline-factory.yml               (MODIFY — paths + sign step over both roots)

docs/adr/0010-productized-package-contract.md         (NEW)
docs/adr/0006-contract-strategy-json-schema-canonical.md  (minor edit — list two new schemas)

pyproject.toml (root)                                # add "code-intake" to workspace members + testpaths
```

### 5.2 Workspace-toolchain compatibility (Sprint-4 limit)

Code Intake's `static_python` and `tests` checkers invoke `ruff` / `mypy` / `pytest` via subprocess against `packages/<name>/<version>/python/`. For Sprint 4, the package's Python is assumed to be runnable under the workspace's existing toolchain (Python 3.12, no extra deps). The synthetic worked example complies. Phase 3 packages with `numpy` / `pandas` / `sklearn` version pins will need per-package venvs — ADR-0010 records this as the known limit Sprint 4 ships under.

---

## 6 · `code-intake` package internals

### 6.1 Checker protocol

```python
# code_intake/checkers/base.py
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Finding:
    """A single issue detected by a checker."""
    severity: str          # "error" | "warning"
    code: str              # e.g. "PY001", "SAS003", "PIR002"
    message: str
    file: str | None = None
    line: int | None = None


@dataclass(frozen=True)
class CheckResult:
    """One checker's output. `passed` is True iff there are no error-severity findings."""
    checker: str
    passed: bool
    findings: list[Finding] = field(default_factory=list)
    duration_seconds: float = 0.0


class Checker(Protocol):
    name: str
    def run(self, package_path: Path) -> CheckResult: ...
```

### 6.2 The five checkers

| Checker | What it runs | Failure codes |
|---|---|---|
| `static_python` | `ruff check` + `mypy --strict` + `pytest --collect-only` via subprocess in `packages/<name>/<version>/python/` | `PY001` ruff finding · `PY002` mypy finding · `PY003` pytest discovery failure |
| `static_sas` | Reads every `.sas` file; simple state machine matching `PROC <X>;` open against `RUN;` close. Asserts files exist + non-empty + balanced. | `SAS001` missing file · `SAS002` empty file · `SAS003` unbalanced PROC/RUN |
| `schema` | Loads `model_config.yaml`, validates against `package-manifest-payload.schema.json`; for every artefact reference, computes SHA-256 of the on-disk file and asserts match. | `SCH001` schema validation · `SCH002` missing artefact file · `SCH003` artefact hash mismatch |
| `tests` | Subprocesses `pytest packages/<name>/<version>/python/tests/`. | `TST001` collection failed · `TST002` ≥1 test failed |
| `pir` | Loads `pir.yaml`, validates against `pir-mapping.schema.json`; parses Python source under `python/` via stdlib `ast` for `data["col"]` and `data.col` patterns; asserts every referenced column is in `pir.inputs[]`. | `PIR001` schema validation · `PIR002` column not mapped · `PIR003` mapping_version mismatch |

The `pir` checker's column-reference parser is intentionally crude: it handles `data["col_name"]` (subscript) and `data.col_name` (attribute access) on identifiers named `data` inside any function. This catches the synthetic-package case; real Phase-3 parsers can opt into stricter logic via a future PIR config flag.

### 6.3 Orchestrator

```python
# code_intake/orchestrator.py
def validate(package_path: Path, *, strict: bool = False) -> list[CheckResult]:
    """Run every checker; never short-circuit.

    `strict` flips warning-severity findings into errors. Default False.
    Returns the list of all CheckResults in execution order.
    """
    checkers: list[Checker] = [
        StaticPythonChecker(),
        StaticSasChecker(),
        SchemaChecker(),
        TestsChecker(),
        PirChecker(),
    ]
    results = []
    for c in checkers:
        start = time.monotonic()
        try:
            result = c.run(package_path)
        except Exception as e:
            # A checker crashed (not just found issues). Convert to a single
            # error-severity Finding so the orchestrator never bails.
            result = CheckResult(
                checker=c.name, passed=False,
                findings=[Finding("error", f"{c.name.upper()}999",
                                  f"checker crashed: {e!r}")],
            )
        result = replace(result, duration_seconds=time.monotonic() - start)
        results.append(result)
    return results
```

Three properties: collect-all-findings (CI shows every issue per run), never-crash-on-checker-bug (a buggy checker becomes a single finding, not a stack trace), per-checker timing in CI logs.

### 6.4 CLI

```
code-intake validate --package <path> [--strict] [--json]
    Runs all five checkers; prints a table summary by default, or a single
    JSON object if --json. Exit 0 if all checkers passed, 1 otherwise.

code-intake generate-manifest --package <path>
    Runs validate first; if validation fails, exits 1 without writing the
    manifest. If validation passes, builds an UNSIGNED package envelope
    (Sprint 3's signer fills the sentinels in CI) and writes it to
    packages/<name>/<version>/manifest.json. Exit 0/1.
```

Both commands are read-from-disk-only. No AWS calls. The signer in Sprint 3 owns the AWS path.

### 6.5 Error hierarchy

```python
class CodeIntakeError(Exception):                    ...
class ValidationError(CodeIntakeError):              ...    # validate() found error-severity findings
class PackageConfigError(CodeIntakeError):           ...    # model_config.yaml doesn't parse / match schema
```

No `KeyMismatchError`-equivalent — Code Intake has no idempotency contract beyond determinism. Re-running `validate` on the same package gives the same result; re-running `generate-manifest` overwrites the in-git manifest (and the drift gate catches the difference if anything changed).

### 6.6 Dependencies

- `boto3` — not needed by Code Intake itself (no AWS calls); the manifest-signer owns the AWS path.
- `click` — CLI.
- `jsonschema` — validates `model_config.yaml` and `pir.yaml` against their schemas.
- `pyyaml` — reads `model_config.yaml` and `pir.yaml`.
- `platform-contracts` — workspace dep; provides the schemas + Pydantic models + `canonical_json`.
- Test-time: `pytest`, `pytest-timeout` (already in workspace dev deps).

---

## 7 · Contract schemas

### 7.1 `package-manifest-payload.schema.json` (new)

Required fields: `schema_version` (const 1), `code_intake_version`, `model_name` (kebab-case), `version` (semver), `generated_at` (ISO-8601), `package_layout`, `validation_summary`.

`package_layout` lists every shipped artefact's path + SHA-256: `sas_files[]`, `python_files[]`, `test_files[]`, `pir_ref` (single `file_ref`), `model_config_ref` (single `file_ref`).

`validation_summary` records what Code Intake found: `ran_at` (ISO-8601) + `checks[]` (per-checker `{name, passed, finding_count, codes[]}`).

The whole payload is what Sprint-3's signer signs over. The hex digest of `canonical_json(payload)` is what `upstream_refs[i].digest` in the downstream pipeline manifest matches.

### 7.2 `pir-mapping.schema.json` (new)

Required fields: `mapping_version` (const 1, the schema version not the model version), `model_name`, `model_version`, `inputs[]`, `outputs[]`. Optional `notes`.

Each input: `{name, type, source, description?, nullable?}`. Each output: `{name, type, description?}`. `type` is one of `string|int|float|bool|date|datetime|decimal`. `source` is a string (ABSA's real PIR system reference; Phase 3 will tighten the schema once the actual PIR shape is available).

### 7.3 `pipeline-manifest-payload.schema.json` (additive modification)

Add optional `upstream_refs[]` field defaulting to `[]`:

```json
"upstream_refs": {
  "type": "array",
  "default": [],
  "items": {
    "type": "object",
    "required": ["type", "ref", "digest"],
    "properties": {
      "type":   { "enum": ["package"] },
      "ref":    { "type": "string" },
      "digest": { "type": "string", "pattern": "^[a-f0-9]{64}$" }
    },
    "additionalProperties": false
  }
}
```

Sprint 2's existing `pipelines/credit-risk-pd/1.0.0/manifest.json` stays a valid shape (the field is optional with an empty default). Re-running `generate` with the Sprint-4 `upstream_package` block populates the array; the regeneration is what bumps the in-git manifest's content and trips the drift gate.

**No `signature` field in `upstream_refs[]`.** The integrity story is the pipeline's own signature covering the array. To prove a cross-link is genuine, a verifier (1) fetches `s3://signed-manifests/packages/<ref>/manifest.json`, (2) hashes its canonical payload, (3) confirms the hex digest matches `upstream_refs[i].digest`, (4) verifies the upstream manifest's own signature against the published public key. Offline-verifiable end-to-end.

### 7.4 Codegen regeneration

`platform-contracts/regenerate-models.sh` (from Sprint 1) re-runs `datamodel-code-generator` over all schemas + the AST merger merges into `models.py`. The CI byte-stability check on `models.py` (already in place from Sprint 1) catches accidental regeneration drift.

---

## 8 · Pipeline-factory extension

### 8.1 `model-config.schema.json` (additive modification)

Add optional `upstream_package` block:

```json
"upstream_package": {
  "type": "object",
  "required": ["name", "version"],
  "properties": {
    "name":    { "type": "string", "pattern": "^[a-z][a-z0-9-]*$" },
    "version": { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$" }
  },
  "additionalProperties": false
}
```

### 8.2 New `pipeline_factory/upstream_resolver.py`

```python
def resolve_upstream_refs(
    *,
    upstream_package: dict[str, str] | None,
    packages_root: Path,
) -> list[dict[str, Any]]:
    """Resolve the model_config's `upstream_package` block to an upstream_refs entry.

    Returns [] if `upstream_package` is None.
    Raises GeneratorError if the package manifest is missing or has no `digest`.
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

    envelope = json.loads(manifest_path.read_text())
    digest = envelope.get("digest")
    if not digest:
        raise GeneratorError(
            f"upstream package manifest at {manifest_path} is missing the "
            f"`digest` field; cannot embed cross-link."
        )

    return [{
        "type":   "package",
        "ref":    f"{name}@{version}",
        "digest": digest,
    }]
```

Pure function. No AWS calls, no signature verification (the in-git digest is trusted because the drift gate enforces consistency). Test with `tmp_path` fixtures only.

### 8.3 `manifest.py` modification

```python
def build_payload(
    *,
    model_name: str,
    version: str,
    tier: str,
    artifact_hashes: dict[str, str],
    generated_at: str | None = None,
    upstream_refs: list[dict[str, Any]] | None = None,    # NEW
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generator_version": _generator_version(),
        "model_name": model_name,
        "version": version,
        "tier": tier,
        "generated_at": generated_at or datetime.now(UTC).isoformat(),
        "artifact_hashes": artifact_hashes,
        "upstream_refs": upstream_refs or [],          # NEW
    }
```

### 8.4 `generator.py` modification

Insert the resolver call between config-loading and payload-building:

```python
config = load_model_config(config_path)
upstream_refs = resolve_upstream_refs(
    upstream_package=config.get("upstream_package"),
    packages_root=Path("packages"),
)
...
payload = build_payload(
    model_name=config["model_name"],
    version=config["version"],
    tier=config["tier"],
    artifact_hashes=artifact_hashes,
    upstream_refs=upstream_refs,
)
```

Drift gate symmetry: the existing `git diff --exit-code` step catches any cross-link mismatch — bumping the package without regenerating the pipeline manifest fails the gate.

---

## 9 · CI integration

### 9.1 New `.github/workflows/code-intake.yml`

```yaml
name: code-intake

on:
  pull_request:
    paths:
      - "code-intake/**"
      - "packages/**"
      - "platform-contracts/**"
      - "pyproject.toml"
      - "uv.lock"
      - ".github/workflows/code-intake.yml"
  push:
    branches: [main, "phase-2/**"]
    paths: <same>

permissions:
  contents: read

jobs:
  validate-and-generate-package:
    name: validate + generate-manifest (drift gate)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with: { enable-cache: true }
      - run: uv sync --frozen
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

### 9.2 `.github/workflows/pipeline-factory.yml` modifications

Two tiny additive changes:

- **Path triggers** (both `pull_request.paths` and `push.paths`): add `packages/**`. Reason: changing a package bumps its manifest's `digest`, which forces pipeline manifest regeneration via `upstream_refs[].digest`. The pipeline-factory drift gate must run on package changes too.

- **`sign` step:** loop the existing `manifest-signer sign-all` over both roots, packages first:

```diff
       - name: Sign all unsigned manifests
         if: env.SIGNER_ROLE_ARN != ''
         run: |
           set -euo pipefail
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

Ordering: `packages` before `pipelines` gives auditors a cleaner timeline in S3 object-creation order (a pipeline's upstream reference, when fetched, always points at a package that's already in S3). The signature math doesn't depend on the order — both manifests' digests are computed at gen-time, not at sign-time — but the operational story is cleaner this way.

No new IAM, no new bucket, no new role. The Sprint-3 signer's permission `s3:PutObject` on `${signed_manifests_bucket}/*` covers both prefixes.

---

## 10 · Worked example

### 10.1 Package content (`packages/credit-risk-pd/1.0.0/`)

Synthetic but real enough to exercise every checker:

- `model_config.yaml` (~30 lines): names every shipped file, declares no extra deps, sets `code_intake_version` (the producer of this manifest).
- `sas/score.sas` (~15 lines): one `DATA scored;` step + one `PROC PRINT data=scored;` block, each with a matching `RUN;`. The `static_sas` checker sees balanced PROC/RUN.
- `python/score.py` (~25 lines): `score(data) -> dict` mirroring the SAS logic. Reads `data["income_band"]`, `data["tenure_months"]`, `data["delinquencies"]`. The `pir` checker's AST scanner extracts these three column names.
- `python/tests/test_score.py` (~30 lines): 2-3 pytest functions asserting band classification under different inputs (HIGH, MEDIUM, LOW paths).
- `pir.yaml` (~25 lines): `mapping_version: 1`, `model_name: credit-risk-pd`, `model_version: 1.0.0`, `inputs: [{name: income_band, ...}, {name: tenure_months, ...}, {name: delinquencies, ...}]`, `outputs: [{name: pd_score, ...}, {name: risk_band, ...}]`. Every column the Python references is mapped.
- `manifest.json`: generated by `code-intake generate-manifest`. UNSIGNED in git; signed copy lives at `s3://exl-platform-signed-manifests/packages/credit-risk-pd/1.0.0/manifest.json` post-CI.
- `README.md`: brief description of what the package contains and how to regenerate the manifest.

### 10.2 Pipeline config update

`pipeline-factory/configs/credit-risk-pd/1.0.0/model_config.yaml` gains a tiny block:

```yaml
upstream_package:
  name: credit-risk-pd
  version: 1.0.0
```

Re-running `generate-pipeline generate --force` regenerates `pipelines/credit-risk-pd/1.0.0/manifest.json` with the new `payload.upstream_refs[]` populated. The committed manifest changes — the drift gate in `pipeline-factory.yml` catches this and the PR shows the diff.

---

## 11 · Testing strategy

### 11.1 Per-checker unit tests

| File | Asserts |
|---|---|
| `test_checker_static_python.py` | `valid_package/` passes. `broken_python/` (has `import os\nos` with no usage) → returns `PY001` (ruff F401-style finding). |
| `test_checker_static_sas.py` | `valid_package/sas/score.sas` balanced → passes. `broken_sas/sas/score.sas` with orphan `PROC FREQ;` → `SAS003`. Empty file → `SAS002`. Missing file → `SAS001`. |
| `test_checker_schema.py` | Valid config passes. `broken_schema/` removes a required field → `SCH001`. A fixture where the manifest claims an artefact hash that doesn't match the on-disk file → `SCH003`. Missing artefact file → `SCH002`. |
| `test_checker_tests.py` | `valid_package/python/tests/test_score.py` (2 tests) passes. `broken_tests/python/tests/test_score.py` has one `assert False` → `TST002` with the failing test name in the finding message. |
| `test_checker_pir.py` | Valid PIR passes. `broken_pir/pir.yaml` is missing `tenure_months` (referenced by `score.py`) → `PIR002` with the column name in the message. Invalid PIR schema (missing `mapping_version`) → `PIR001`. |

### 11.2 Orchestrator + manifest tests

- `test_orchestrator.py`: all five checkers run on `valid_package/` → 5 passing CheckResults. A package broken in two ways (Python lint + PIR mapping) → both findings surface. A monkey-patched checker that raises → orchestrator returns a synthetic finding with code `*999` and never propagates the exception.
- `test_manifest.py`: `build_package_payload` produces a payload that passes `package-manifest-payload.schema.json`. Envelope wraps it with `signature == "UNSIGNED"`. Idempotency on re-render — `generated_at` preserved when an existing manifest is read (Sprint 2's pattern).
- `test_package_config.py`: loader accepts valid config, rejects schema-invalid configs with a clear error message.

### 11.3 CLI tests

`test_cli.py` covers: `validate` exits 0 on valid, 1 on broken; `validate --json` outputs a single JSON object; `generate-manifest` runs validate first and refuses to write the manifest if validation fails; `--strict` flag flips warnings into errors.

### 11.4 End-to-end test (`test_e2e_track_a.py`)

The strongest test signal Sprint 4 ships. In one moto context:

1. Run `code-intake validate` on the worked-example package → asserts all five checkers pass.
2. Run `code-intake generate-manifest` → asserts `packages/credit-risk-pd/1.0.0/manifest.json` is written with `signature == "UNSIGNED"` and a valid `digest`.
3. Sign the package manifest via Sprint-3's `manifest-signer.signer.sign_envelope` → upload to mocked S3.
4. Run `pipeline_factory.generator.generate` on the pipeline config (with `upstream_package` set) → asserts the regenerated pipeline manifest has `payload.upstream_refs[0].digest` equal to the package manifest's `digest`.
5. Sign the pipeline manifest → upload to mocked S3.
6. Verify both manifests via `verify_online` and `verify_offline` (using the moto-generated public key) → asserts every signature is valid.
7. Build a mock `CreateModelRequest` from the pipeline's `registration.json` → asserts the body would POST cleanly (no actual HTTP call; the registrar's structure is what's verified).

Asserts the chain-of-custody is consistent at every link.

### 11.5 Pipeline-factory regression test

`pipeline-factory/tests/test_upstream_resolver.py` covers the new module:
- `upstream_package=None` → `[]`.
- Valid package → correct `{type, ref, digest}`.
- Missing package manifest → `GeneratorError` with a clear message.
- Manifest missing `digest` → `GeneratorError`.

Plus a small extension to the existing `test_manifest.py` confirming `build_payload` accepts and embeds `upstream_refs`.

### 11.6 Other gates (no new infra)

- **Codegen drift:** Sprint 1's existing models.py byte-stability check covers the two new schemas automatically.
- **`actionlint`:** runs on the new `code-intake.yml` via the existing pre-commit hook.
- **Drift gate on `packages/`:** new `code-intake.yml` does `git diff --exit-code packages/` after regeneration.
- **No new Terraform.** Sprint 4 ships zero TF changes; `terraform-validate.yml` matrix unchanged.

---

## 12 · ADRs

### 12.1 ADR-0010 — Productized Package Contract (new)

Outline:

- **Context.** Brief §2.1 step 3 commits to a "signed, manifested" handoff between EXL's Industrialization Team and Pipeline Factory. Sprint 4 implements it.
- **Decisions.** Git-tracked `packages/<name>/<version>/` layout with five artefact groups (`sas/`, `python/`, `pir.yaml`, `model_config.yaml`, `manifest.json`). Two new schemas in `platform-contracts`. Five checkers (real Python depth via ruff/mypy/pytest; structural SAS only). Chain-of-custody via `upstream_refs[]` on pipeline manifests, digest-only (no signature embedded — verifier fetches from S3 to confirm). One Sprint-3 IAM role signs both packages and pipelines. Workspace-toolchain-compatible Python required.
- **Consequences (pros).** Audit chain extends one link up (registry → pipeline → package); each link is signature-covered and drift-gated. Collect-all-findings dev ergonomics. No new IAM / bucket / TF.
- **Consequences (cons accepted).** SAS validation is structural-only — real SAS linting deferred to Phase 3 (needs ABSA's SAS runtime). The package's Python must be workspace-toolchain-compatible — real Phase-3 packages with isolated deps will need per-package venvs or containers; framework supports a per-checker config flag we'll add in Phase 3.
- **Alternatives considered.**
  - *Monolithic single checker* — rejected: hard to extend, hard to test, no per-checker timing.
  - *Embedding upstream signature in pipeline manifest* — rejected: complicates two-pass CI signing; digest+offline-verify is sufficient.
  - *Per-package venvs in Sprint 4* — deferred: needs `uv venv` orchestration per package; current workspace-toolchain approach works for synthetic Phase-2 packages.
  - *Real SAS linting* — deferred: Docker + SAS license/runtime concerns; structural is the right Phase-2 depth.
  - *Decoupled chain (no `upstream_refs[]`)* — rejected: weakens the audit story; the registry record can't prove which validated package a pipeline descended from.

### 12.2 ADR-0006 minor edit

ADR-0006 (Contract Strategy — JSON Schema canonical) lists the contracts that `platform-contracts` ships. Add two lines for `package-manifest-payload.schema.json` and `pir-mapping.schema.json`. No semantic change to the original decision.

---

## 13 · Open questions and deferred items

Carried into Phase 3 or later; not blockers for Sprint 4:

| Item | Why deferred | Owner |
|---|---|---|
| Real SAS linting / SAS runtime execution | Needs ABSA's SAS environment + Docker container | Phase 3 |
| Per-package Python venvs (isolated runtime deps) | Sprint 4's workspace-toolchain assumption holds for synthetic packages only | Phase 3 |
| PIR mapping fed from ABSA's real PIR system | Phase-3 integration; Sprint 4 ships the schema + sample YAML | ABSA / Phase 3 |
| Parallel checker execution | Performance optimisation; not needed at Sprint-4 scale | Phase 3 |
| `upstream_refs[]` to types other than `"package"` (e.g. dataset, feature-set) | Schema is extensible (enum on `type`); no Sprint-4 use case | Phase 3 / Phase 4 |
| Code Intake against multiple packages in parallel | Single-shot CLI in Sprint 4; multi-package orchestration deferred | Phase 3 |
| `code-intake validate` against a package fetched directly from a git submodule or tarball | Sprint 4 only validates packages in the repo's `packages/` tree | Phase 3 |

---

## 14 · Acceptance criteria

Sprint 4 is done when:

1. All Code Intake unit tests + the end-to-end Track A test pass — `uv run pytest code-intake/tests` is green.
2. The full workspace test suite passes — `uv run pytest` is green (Sprint 1 + 2 + 3 tests still pass after the additive changes).
3. `code-intake validate` on the worked-example package exits 0; on each `broken_*` fixture exits 1 with the expected finding codes.
4. `code-intake generate-manifest` produces a `manifest.json` that passes `package-manifest-payload.schema.json` validation.
5. `pipeline-factory.generator` resolves `upstream_package: {name: credit-risk-pd, version: 1.0.0}` to the correct `upstream_refs[]` entry. The regenerated `pipelines/credit-risk-pd/1.0.0/manifest.json` is byte-stable across repeated invocations (drift gate passes).
6. The end-to-end test asserts the full chain (Code Intake → Factory → signer → mock registrar) is consistent at every link.
7. `actionlint` passes on the new `code-intake.yml` and the modified `pipeline-factory.yml`.
8. ADR-0010 is committed; ADR-0006 has the minor edit.
9. READMEs exist for `code-intake/` and `packages/credit-risk-pd/1.0.0/`.
10. The final review pass (subagent-driven code reviewer at the end of execution) finds no blocking issues.
11. A PR is opened against `main`; CI is green (the drift gate, code-intake, pipeline-factory, terraform-validate, python-validate, actionlint all run and pass; sign + register jobs skip cleanly in dev).

---

## 15 · Implementation handoff

After this spec is reviewed and approved, the writing-plans skill produces a tasked implementation plan covering:

- Three contract changes (`package-manifest-payload.schema.json`, `pir-mapping.schema.json`, `pipeline-manifest-payload.schema.json` modification) — done first so subsequent tasks import generated models.
- The `code-intake` Python package built bottom-up: errors → base/Checker protocol → each of the five checkers (one task each) → orchestrator → manifest builder → CLI → end-to-end test.
- Pipeline-factory extension: `model-config.schema.json` modification + `upstream_resolver.py` + `manifest.py`/`generator.py` modifications.
- Worked example artefacts (`packages/credit-risk-pd/1.0.0/` content + the pipeline config update + regenerated pipeline manifest).
- CI workflows (new `code-intake.yml`, additive edits to `pipeline-factory.yml`).
- Documentation: ADR-0010 → ADR-0006 minor edit → READMEs → top-level CHANGELOG entry if one exists.
- Final verification pass.

Execution then proceeds via the subagent-driven-development pattern established in Sprints 1, 2, and 3: a fresh implementer subagent per task, followed by a spec-compliance reviewer and a code-quality reviewer, with the controller dispatching one task at a time.
