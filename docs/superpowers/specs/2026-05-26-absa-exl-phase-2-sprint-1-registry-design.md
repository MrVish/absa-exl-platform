# ABSA × EXL Model Hosting & Delivery Operations — Phase 2 Sprint 1: Registry & Shared Contracts

| Field | Value |
| --- | --- |
| Date | 2026-05-26 |
| Engagement | ABSA × EXL Model Hosting & Delivery Operations (5-month build, 10-FTE pod) |
| Phase | 2 — Pipeline Factory + Registry (Months 2-3) |
| Sub-sprint | 2.1 — Registry & Shared Contracts (first of three) |
| Authoring source | `CLAUDE_CODE_BRIEF.md` §6 (Pipeline Factory), §7 (Registry), §9 (Constraints), §11 (Phase plan) |
| Predecessor | Phase 1 Foundation (kickoff + sprint 2) — landing zone, S3 replication, KMS hierarchy, IAM federation, CI |
| Checkpoint gate | Engagement-lead review of the squash-merge PR before sub-sprint 2.2 (Pipeline Factory) begins |
| Status | Design approved; awaiting written-spec review before implementation plan |

## TL;DR

Phase 2 bundles three subsystems (Registry, Pipeline Factory, Code Intake) plus a
first end-to-end Track A run. That is too much for one spec, so Phase 2 is
decomposed into three sub-sprints built in order, mirroring how Phase 1 split into
kickoff + sprint 2. **This spec covers sub-sprint 2.1 only: the Registry and the
shared contracts** that the other two subsystems will write against — the keystone
of Phase 2.

The sub-sprint delivers: three canonical JSON-Schema contracts (model-config,
registry-record, manifest-envelope) with Pydantic models generated from them and a
CI drift check; the `pipeline-registry` Terraform module (a DynamoDB table fronted
by a single-Lambda FastAPI app behind an API Gateway HTTP API with IAM/SigV4 auth);
per-env registry stacks; the repo's first Python tooling baseline (uv + ruff + mypy
+ pytest); a Python CI workflow; ADR-0006 and ADR-0007; and Phase 2 rows in the
compliance matrix. Consistent with Phase 1, everything is **plan-validate +
mocked-AWS only** — no `terraform apply`, no live API — until AWS credentials land.

## 1. Context

Phase 1 delivered the foundation: workload landing zone, the S3 cross-account
replication module pair, KMS hierarchy (audit-evidence keys), IAM federation, and a
plan-validate CI pipeline — all documented in `docs/architecture.md` and ADRs
0001–0005. The engagement lead has cleared the `CLAUDE_CODE_BRIEF.md` §12 step-7
checkpoint and authorised Phase 2.

`CLAUDE_CODE_BRIEF.md` §11 scopes Phase 2 as "Pipeline Factory templates + generator
· Registry API · Code Intake validation · sign-and-handoff flow · first end-to-end
Track A run for one test model (Months 2-3)". That is three subsystems and an
integration milestone. Per the brainstorming discipline (flag multi-subsystem work
before refining details), Phase 2 is decomposed:

- **Sub-sprint 2.1 — Registry & Shared Contracts** (this spec). The system of
  record and the schemas the other subsystems consume. Built first because Pipeline
  Factory writes pipeline records into it and Code Intake flips `approval_status`,
  so both depend on its contracts.
- **Sub-sprint 2.2 — Pipeline Factory.** Jinja2 templates (`standard-batch`,
  `scalable-batch`) + the `generate_pipeline.py` CLI that validates a model config,
  renders a Step Functions definition, writes a Terraform stub registering the
  pipeline, and emits a (signable) manifest. Owns the dual-mode generator-runtime
  ADR that ADR-0003 deferred.
- **Sub-sprint 2.3 — Code Intake + first Track A run.** SAS/Python validators, the
  KMS-asymmetric manifest signer, the GitHub Actions sign-and-handoff flow, and one
  test model wired end-to-end through Code Intake → Factory → Registry.

This sub-sprint also introduces the **first Python in the repository** (Phase 1 was
entirely Terraform), so it establishes the platform-wide Python tooling convention.

## 2. Decisions locked this session

Brainstorming questions answered by the engagement lead, plus the §11-style
"smaller calls" resolved at design approval. Recorded so the design lineage is
reconstructable without replaying the conversation.

| # | Topic | Choice | Rationale | Captured by |
| - | --- | --- | --- | --- |
| 1 | Phase 2 structure | Decompose into 3 sub-sprints; Registry first | Registry is the keystone both other subsystems write into; smallest review surface per sprint; mirrors Phase 1's kickoff+sprint-2 cadence | This spec §1 |
| 2 | Contract source of truth | JSON Schema canonical; Pydantic generated from it + CI drift check | Language-neutral, versioned, citable as the ABSA↔EXL interface in the audit pack; matches the brief's "JSON Schema for model config" wording | ADR-0006 |
| 3 | Python tooling baseline | uv + ruff + mypy + pytest | Reproducible `uv.lock` builds auditors/CI like; ruff = lint+format; mypy = types; pytest = tests. Platform-wide convention for all later Python | ADR-0006 (tooling note) / this spec §4 |
| 4 | Registry API packaging | FastAPI monolith on a single Lambda via Mangum, behind an API Gateway HTTP API with AWS_IAM auth | Matches the brief literally; smallest deploy artifact; excellent local/`moto` test story; Lambda Web Adapter documented as the future scale/real-time migration path | ADR-0007 |
| 5 | Contract file location | Single shared `platform-contracts/` package; `pipeline-factory/config-schema/` and `registry/schema/` become pointer READMEs | Model-config is consumed by both Registry and Factory; one shared home avoids cross-subsystem-dir import coupling; correct shape for a "shared contracts" sprint | This spec §4, §5 |
| 6 | manifest-envelope schema timing | Define now | ADR-0003 already fixed the envelope's fields; defining it in the contracts sprint lets 2.2/2.3 build against a frozen contract. Payload bodies stay deferred to their producers | This spec §5.3 |
| 7 | Registry GSIs | `by_status` only | Approval/ops listing is the one access pattern beyond the composite key; full listing via scan is fine at 10-model scale; add `by_owner` later only if a route needs it | This spec §6 |
| 8 | DynamoDB SSE key ownership | `pipeline-registry` module owns its own per-env CMK (table SSE + its log groups) | ADR-0005 scopes `kms-hierarchy` to audit-evidence keys only and keeps per-data-class workload keys in their owning module (the s3-replication precedent). The registry table is a workload data class | This spec §6, §8; aligns ADR-0005 |

## 3. Scope

### 3.1 In scope (sub-sprint 2.1)

- Three canonical JSON-Schema contracts + generated Pydantic models + drift check.
- `terraform/modules/pipeline-registry/` — DynamoDB + Lambda + API Gateway HTTP API
  + IAM + module-owned KMS CMK + KMS-encrypted log groups, with `tftest` coverage.
- `terraform/envs/{dev,stg,prod}/registry/` — per-env stacks instantiating the module.
- `registry/api/` — the FastAPI application (Mangum handler + repository layer).
- The repo's Python tooling baseline (uv workspace root, ruff, mypy, pytest config).
- `ci/pipelines/python-validate.yml` + extension of `terraform-validate.yml`'s matrix.
- ADR-0006 (contract strategy) and ADR-0007 (registry data model & API).
- Phase 2 registry rows in `docs/compliance/control-matrix.md`.
- README updates: `registry/`, `pipeline-factory/config-schema/` pointer, root.

### 3.2 Out of scope (deferred)

| Item | Where it lands |
| --- | --- |
| Pipeline Factory templates + `generate_pipeline.py` | Sub-sprint 2.2 |
| Dual-mode generator-runtime ADR | Sub-sprint 2.2 |
| Code Intake validators + KMS signer + sign-and-handoff | Sub-sprint 2.3 |
| Payload bodies of signed manifests (package / pipeline) | 2.2 / 2.3 (their producers) |
| Track B data sidecar `manifest.json` body | Phase 3 (scoring) |
| First end-to-end Track A run | Sub-sprint 2.3 |
| Real `terraform apply` / live API Gateway / integration tests | When AWS credentials land (Phase 1 precedent) |
| Client SDK for the Registry API | Not planned; SigV4 + OpenAPI is the contract |
| Provisioning the KMS asymmetric signing CMK | Sub-sprint 2.3 (Code Intake is the first signer) |

## 4. Repo layout

New and changed paths. "WRITTEN" = authored this sub-sprint; "pointer" = a short
README redirecting to the canonical location.

```
absa-exl-platform/
├── pyproject.toml                      # WRITTEN — uv workspace root; shared ruff/mypy/pytest config
├── uv.lock                             # WRITTEN — committed lockfile
├── platform-contracts/                 # WRITTEN — shared contracts package (uv workspace member)
│   ├── pyproject.toml
│   ├── schemas/
│   │   ├── model-config.schema.json        # canonical, Draft 2020-12
│   │   ├── registry-record.schema.json     # canonical, Draft 2020-12
│   │   └── manifest-envelope.schema.json   # canonical, Draft 2020-12 (payload body deferred)
│   ├── src/platform_contracts/
│   │   ├── __init__.py
│   │   ├── models.py                       # GENERATED from schemas via datamodel-code-generator
│   │   ├── loader.py                        # load + jsonschema-validate a doc against a named schema
│   │   └── examples/                        # valid + invalid fixtures used by contract tests
│   └── tests/
├── registry/
│   ├── api/                            # WRITTEN — FastAPI app
│   │   ├── pyproject.toml               # workspace member; depends on platform-contracts
│   │   ├── src/registry_api/
│   │   │   ├── app.py                   # FastAPI app + Mangum handler
│   │   │   ├── routes.py                # route handlers
│   │   │   ├── repository.py            # DynamoDB repository (boto3)
│   │   │   ├── transitions.py           # approval state machine + guards
│   │   │   ├── audit.py                 # structured audit-log emitter
│   │   │   └── settings.py              # env config (TABLE_NAME, LOG_LEVEL, ...)
│   │   └── tests/                       # pytest + moto
│   └── schema/                          # pointer README -> platform-contracts/schemas
├── pipeline-factory/
│   └── config-schema/                   # pointer README -> platform-contracts/schemas
├── terraform/
│   ├── modules/
│   │   └── pipeline-registry/           # WRITTEN — full module + tests + README
│   │       ├── main.tf  variables.tf  outputs.tf  versions.tf  README.md
│   │       └── tests/pipeline_registry.tftest.hcl
│   └── envs/{dev,stg,prod}/
│       └── registry/                    # WRITTEN — {main.tf, variables.tf, locals.tf, terraform.tfvars}
├── ci/pipelines/
│   ├── python-validate.yml              # WRITTEN — uv sync · ruff · mypy · pytest · drift check
│   └── terraform-validate.yml           # CHANGED — matrix gains pipeline-registry + envs/*/registry
└── docs/
    ├── adr/0006-contract-strategy-json-schema-canonical.md   # WRITTEN
    ├── adr/0007-registry-data-model-and-api.md               # WRITTEN
    └── compliance/control-matrix.md                          # CHANGED — Phase 2 registry rows
```

**Deviation from the brief, accepted at approval (decision #5):** the brief's §3
layout placed schemas in `pipeline-factory/config-schema/` and `registry/schema/`.
Because the model-config schema is consumed by both the Registry (to derive a record
on intake) and the Pipeline Factory (as its input), splitting it across subsystem
directories would create cross-dir import coupling. A single `platform-contracts/`
package is the canonical home; the brief's two directories become pointer READMEs so
discoverability is preserved.

## 5. Shared contracts

### 5.1 Strategy (per ADR-0006)

JSON Schema (Draft 2020-12) is canonical and hand-authored. Pydantic v2 models are
**generated** from the schemas with `datamodel-code-generator` and committed to
`platform_contracts/models.py`. CI regenerates and `diff`s against the committed
file, **failing on any drift** — the "Pydantic ≡ JSON Schema" invariant is enforced
by the pipeline, not by convention. Each schema declares a versioned `$id`
(e.g. `https://contracts.absa-exl.internal/model-config/v1.json`); breaking changes
bump the version segment and ship a new file rather than mutating the old one.

### 5.2 `model-config.schema.json`

The per-model onboarding input (brief §6). Fields:

| Field | Type / constraint | Required | Notes |
| --- | --- | --- | --- |
| `model_name` | string, `^[a-z][a-z0-9-]{2,63}$` | yes | lowercase-kebab; forms the registry PK |
| `version` | string, semver | yes | forms the registry SK |
| `execution_tier` | enum `standard` \| `scalable` | yes | drives Factory template selection (brief §5) |
| `schedule_cadence` | string, cron expression | yes | daily / weekly / monthly |
| `input_schema_ref` | string, `s3://` URI | yes | |
| `output_schema_ref` | string, `s3://` URI | yes | |
| `pir_doc_ref` | string, `s3://` URI | yes | developer-evidence reference (Track B PIR) |
| `owner_email` | string, email | yes | |
| `accountable_executive` | string | yes | |
| `sla_seconds` | integer, > 0 | yes | |
| `model_class` | enum `credit` \| `fraud` \| `propensity` \| `other` | no | cohort/type grouping; optional |
| `registry_lookup_key` | string | no | defaults to `{model_name}/{version}` if omitted |

`additionalProperties: false` to reject typos.

### 5.3 `registry-record.schema.json`

The DynamoDB item shape (brief §7), with two additions justified below:

All brief §7 attributes: `model_name`, `version`, `sas_code_version`,
`inference_code_version`, `schedule_cadence`, `execution_tier`, `input_schema_ref`,
`output_schema_ref`, `pir_doc_ref`, `owner_email`, `accountable_executive`,
`approval_status` (`pending` | `approved` | `retired`), `sla_seconds`,
`cab_record_id`, `created_at`, `updated_at`, `last_scored_at`. Plus:

- `ivu_evidence_ref` (string, `s3://` URI, optional until approval) — required by
  brief §9 ("IVU evidence pack must be attached to the registry record before first
  production run"); enforced as an approval precondition (§7.3).
- `rev` (integer ≥ 0) — optimistic-concurrency counter incremented on every write,
  used in DynamoDB `ConditionExpression`s; also the record-format discriminator.

Timestamps are ISO-8601 UTC strings. `additionalProperties: false`.

### 5.4 `manifest-envelope.schema.json`

The signing envelope ADR-0003 fixed; the **payload body is deliberately open**
(`payload: { "type": "object" }`) and refined by its producer in 2.2 / 2.3.

| Field | Type | Notes |
| --- | --- | --- |
| `digest` | string, hex | SHA-256 of the canonicalised payload |
| `digest_algorithm` | const `SHA-256` | |
| `signature` | string, base64 | `kms:Sign` output |
| `signing_key_arn` | string | KMS asymmetric CMK ARN |
| `signing_algorithm` | enum | `RSASSA_PKCS1_V1_5_SHA_256` (default) \| `ECDSA_SHA_384` |
| `subject_type` | enum `package` \| `pipeline` | Code Intake vs Pipeline Factory |
| `subject_ref` | string | logical id / `s3://` URI of the signed artifact |
| `signed_at` | string, ISO-8601 | |
| `signer_principal` | string | CI OIDC role / IAM principal |
| `payload` | object | producer-specific; body schema deferred |

## 6. DynamoDB table design

Table `model_pipeline_registry`:

- **Keys:** `model_name` (PK, S) + `version` (SK, S) — composite, per brief §7.
- **Billing:** `PAY_PER_REQUEST` (on-demand) — low, spiky volume; no capacity tuning.
- **PITR:** enabled — audit/recovery.
- **SSE:** customer-managed KMS CMK **owned by this module** (rotation enabled),
  per ADR-0005's per-data-class-key convention (decision #8).
- **Deletion protection:** enabled in prod; off in dev/stg via env tfvars.
- **GSI `by_status`:** PK `approval_status` (S) + SK `updated_at` (S) — powers
  `GET /models?status=` and ops/CAB listings. Projection `ALL`.
- Item shape enforced at the app layer (the generated Pydantic mirror); DynamoDB
  only declares the key + GSI-key attributes.
- **Writes** use `ConditionExpression`: create asserts `attribute_not_exists(model_name)`;
  updates assert the expected `rev` (optimistic locking) and increment it.

## 7. Registry API

### 7.1 Surface

API Gateway **HTTP API** (apigatewayv2), `$default` route → Lambda proxy
(payload format v2.0), Mangum adapts the proxy event to the FastAPI ASGI app.

| Method & path | Purpose | Success | Notable failures |
| --- | --- | --- | --- |
| `POST /models` | Create a model+version record (status→`pending`) | 201 | 409 if `(name,version)` exists; 400 invalid body |
| `GET /models` | List; optional `?status=` (GSI), cursor pagination | 200 | 400 bad query |
| `GET /models/{name}` | List versions of a model (query PK) | 200 | 404 unknown model |
| `GET /models/{name}/versions/{ver}` | Fetch one record | 200 | 404 |
| `PATCH /models/{name}/versions/{ver}` | Update mutable fields (`schedule_cadence`, `sla_seconds`, `last_scored_at`, `cab_record_id`, `ivu_evidence_ref`); client passes the expected `rev` | 200 | 404; 409 on `rev` mismatch |
| `POST /models/{name}/versions/{ver}:approve` | `pending`→`approved` | 200 | 409 illegal transition; 422 missing CAB/IVU |
| `POST /models/{name}/versions/{ver}:retire` | `approved`→`retired` | 200 | 409 illegal transition |
| `GET /healthz` | Liveness | 200 | — |

**Mutability rules.** Immutable after create: `model_name`, `version`, `created_at`,
`sas_code_version`, `inference_code_version` (a new code version is a new record, not
a mutation). `approval_status` changes **only** via the `:approve` / `:retire`
actions — never via `PATCH` — so the state machine in §7.3 cannot be bypassed.
OpenAPI is served by FastAPI at `/openapi.json` and is the published interface.

### 7.2 Auth & audit

- **Auth:** route `authorization_type = AWS_IAM`; callers sign requests with SigV4.
  No application-layer auth. Read-only vs read-write separation is enforced by IAM
  policy on distinct caller roles (defined in the env stack, documented in the
  module README).
- **Audit:** CloudTrail automatically logs API Gateway, Lambda, and DynamoDB
  activity in the EXL account. In addition, every mutation emits a **structured
  audit log line** (JSON: `principal` from `requestContext`, `action`, `model_name`,
  `version`, `old_status`→`new_status`, `rev`, `timestamp`) to a KMS-encrypted
  CloudWatch Log group. This is the SR 11-7 model-implementation evidence trail.

### 7.3 Approval state machine (audit-critical)

States `pending → approved → retired`, strictly ordered; no skips, no reopening.
Implemented in `transitions.py` as a small table of allowed `(from, to)` edges with
per-edge guards:

- `:approve` (`pending`→`approved`) is **rejected unless** both `cab_record_id` and
  `ivu_evidence_ref` are present on the record — directly enforcing brief §9 (CAB
  approval recorded + IVU evidence attached before first production run). Missing
  either → `422` listing the missing fields.
- `:retire` (`approved`→`retired`) has no precondition beyond the current state.
- Any other transition (e.g. `pending`→`retired`, `approved`→`pending`) → `409`.

### 7.4 Error handling

Uniform JSON error envelope `{ "error": { "code", "message", "detail" } }`. Pydantic
validation failures map to `400`; DynamoDB `ConditionalCheckFailedException` maps to
`409` (create-conflict or `rev` mismatch); unknown keys map to `404`; approval
precondition failures map to `422`. No stack traces in responses; full detail goes
to the audit/error log.

## 8. Terraform module `pipeline-registry`

### 8.1 Contract

Inputs (selected): `env` (validated `dev`|`stg`|`prod`), `region`,
`table_name` (default `model_pipeline_registry`), `lambda_source_dir`
(path zipped via `archive_file`), `lambda_runtime` (default `python3.12`),
`log_retention_days` (env-tiered), `enable_deletion_protection` (default true),
`tags` (module ensures `env`, `module`, `cost_center`).

Outputs: `table_name`, `table_arn`, `api_endpoint`, `api_id`,
`lambda_function_arn`, `kms_key_arn`, `reader_policy_arn`, `writer_policy_arn`,
`audit_log_group_name`.

Resources owned:

- `aws_kms_key` + alias — module-owned CMK, rotation enabled, used for table SSE and
  the CW Log groups (decision #8 / ADR-0005 convention).
- `aws_dynamodb_table` — per §6.
- `aws_lambda_function` — the API; artifact from `data.archive_file` over
  `var.lambda_source_dir` so `terraform plan`/`tftest` work without a build step.
  Real dependency packaging (vendored deps via `uv pip install --target`, or a
  Lambda layer) is wired when `apply` is enabled and is out of scope here.
- `aws_iam_role` (+ policies) for the Lambda: scoped DynamoDB CRUD on the table and
  its GSI, `kms:Decrypt`/`GenerateDataKey` on the module CMK, CloudWatch Logs.
- `aws_apigatewayv2_api` (+ `$default` route, AWS_IAM authorization, Lambda proxy
  integration, stage with access logging) and `aws_lambda_permission`.
- `aws_cloudwatch_log_group` ×2 (Lambda, API access logs), KMS-encrypted.
- Managed IAM policies `reader_policy_arn` / `writer_policy_arn` for caller roles.

### 8.2 Env wiring

`terraform/envs/{env}/registry/` instantiates the module against the matching EXL
account, separate from the Phase 1 `source/` and `destination/` stacks so the
registry's lifecycle and blast radius are independent. State backend stays the
Phase 1 placeholder (no backend until accounts land).

### 8.3 Tests (`tests/pipeline_registry.tftest.hcl`, plan-validate)

Assert: composite key `(model_name, version)`; on-demand billing; PITR enabled; SSE
uses the module CMK; `by_status` GSI present; deletion protection follows the var;
Lambda runtime `python3.12` with `TABLE_NAME` set; API route `authorization_type =
AWS_IAM`; both log groups KMS-encrypted. Negative tests cover var overrides
(retention, deletion protection) and a clear failure when a required var is omitted.

## 9. Testing strategy

- **Python unit (pytest + `moto`):** `repository.py` CRUD against mocked DynamoDB
  (create-conflict, `rev` optimistic-lock, GSI query, pagination); routes via
  FastAPI `TestClient`; `transitions.py` guard tests (approve blocked without
  CAB/IVU; illegal transitions → 409); validation rejects malformed config.
- **Contract tests:** every fixture in `examples/` validates (valid pass, invalid
  fail) against its schema; each schema is itself a valid Draft 2020-12 document;
  Pydantic round-trips a valid doc; the JSON-Schema↔Pydantic drift check.
- **Terraform (`tftest`):** plan-validate per §8.3. No apply, no live AWS.
- **Coverage rule (carried from Phase 1):** every Python module has tests; every
  module variable with a default gets a positive and a negative test.

## 10. CI strategy

New `ci/pipelines/python-validate.yml`, PR-triggered on `platform-contracts/**`,
`registry/**`, `pyproject.toml`, `uv.lock`:

1. `actions/checkout`
2. `astral-sh/setup-uv` + `uv sync --frozen`
3. `uv run ruff check` and `uv run ruff format --check`
4. `uv run mypy`
5. `uv run pytest` (moto-backed)
6. schema-drift check — regenerate models, fail on `git diff`
7. validate every `examples/` fixture against its schema

`terraform-validate.yml` matrix gains the `pipeline-registry` module and the three
`envs/*/registry` stacks; step list (fmt/validate/test/tflint/tfsec/checkov)
unchanged. `gitleaks` continues to run once for the repo. `main` branch protection
(CODEOWNERS, linear history, conventional commits) is unchanged; CODEOWNERS gains
`@platform-leads` on `platform-contracts/**` and `registry/**`.

## 11. ADRs to author

| ID | Title | Summary |
| - | --- | --- |
| 0006 | Contract strategy — JSON Schema canonical | JSON Schema is the hand-authored, versioned, audit-citable contract; Pydantic models are generated from it and drift-checked in CI. Records the Python tooling baseline (uv/ruff/mypy/pytest) as the platform convention. |
| 0007 | Registry data model & API | DynamoDB single table `(model_name, version)` + `by_status` GSI; FastAPI on a single Lambda via Mangum behind an API Gateway HTTP API with AWS_IAM auth; approval state machine `pending→approved→retired` with CAB+IVU guards; module-owned CMK per ADR-0005. |

MADR 3.0 format (status / context / decision / consequences / alternatives), as in
Phase 1.

## 12. Compliance mapping (control-matrix Phase 2 rows)

| Component | Control(s) | How |
| --- | --- | --- |
| Registry record (inventory) | SARB GOI 3/5; ABSA GMRMG | Authoritative model inventory with owner + accountable executive + SLA |
| `approval_status` + `cab_record_id` + IVU guard | SR 11-7; ABSA GMRMG | CAB approval and IVU evidence enforced before `approved` (brief §9) |
| Structured audit log + CloudTrail | SR 11-7 III.4 | Immutable principal/action/state-change trail per mutation |
| DynamoDB SSE (module CMK) + PITR | ISO 27001 A.10.1; SOC 2 CC6.1 | Customer-managed key with rotation; point-in-time recovery |
| API Gateway AWS_IAM auth | ISO 27001 A.9; SOC 2 CC6 | SigV4; reader/writer IAM separation |

## 13. Open items for the engagement lead

Not blocking this sub-sprint; worth a conversation before or shortly after the
checkpoint.

1. **Contract `$id` domain.** `contracts.absa-exl.internal` is a placeholder. If
   ABSA has a canonical internal schema-registry domain, we should adopt it before
   2.2/2.3 reference these `$id`s.
2. **Registry API caller identities.** Reader vs writer IAM roles need real
   principals — which ABSA/EXL services and humans call the API, and from where
   (PrivateLink per ADR-0001). Needed before live deploy, not before code.
3. **`last_scored_at` writer.** This field is written by Track B scoring (Phase 3).
   In 2.1 it is read-only on the record and only set via `PATCH` for test fixtures.
4. **Retention of the audit log group.** Defaulting to env-tiered (long in prod). If
   ABSA MRMG mandates a specific model-evidence retention, set it now (CW Logs
   retention is cheap to change, unlike object-lock).

## 14. Deliverables manifest

- [ ] `pyproject.toml` (uv workspace root) + `uv.lock` + shared ruff/mypy/pytest config
- [ ] `platform-contracts/` — 3 schemas, generated `models.py`, loader, examples, tests
- [ ] `registry/api/` — FastAPI app (app/routes/repository/transitions/audit/settings) + tests
- [ ] `registry/schema/` + `pipeline-factory/config-schema/` — pointer READMEs
- [ ] `terraform/modules/pipeline-registry/` — full module + `tftest` + README
- [ ] `terraform/envs/{dev,stg,prod}/registry/` — env stacks
- [ ] `ci/pipelines/python-validate.yml` + `terraform-validate.yml` matrix update
- [ ] `docs/adr/0006-contract-strategy-json-schema-canonical.md`
- [ ] `docs/adr/0007-registry-data-model-and-api.md`
- [ ] `docs/compliance/control-matrix.md` — Phase 2 registry rows
- [ ] `CODEOWNERS` — add `platform-contracts/**`, `registry/**`
- [ ] README updates (`registry/`, root)

## 15. Branch / commit strategy

Branch `phase-2/sprint-1-registry` off `main`. Logical commits for reviewer
ergonomics: (1) Python tooling baseline + uv workspace; (2) shared contracts +
generation + drift check; (3) `pipeline-registry` Terraform module + tests;
(4) registry FastAPI app + tests; (5) env stacks; (6) CI + ADRs + compliance rows.
One squash-merge PR for engagement-lead review at the checkpoint gate before
sub-sprint 2.2 (Pipeline Factory) begins.
