# ABSA × EXL Model Hosting & Delivery Operations — Phase 2 Sprint 2: Pipeline Factory

| Field | Value |
| --- | --- |
| Date | 2026-05-26 |
| Engagement | ABSA × EXL Model Hosting & Delivery Operations (5-month build, 10-FTE pod) |
| Phase | 2 — Pipeline Factory + Registry (Months 2-3) |
| Sub-sprint | 2.2 — Pipeline Factory (second of three) |
| Authoring source | `CLAUDE_CODE_BRIEF.md` §6 (Pipeline Factory) and §5 (Execution tiering); ADR-0003 (deferred signing handoff to 2.3); Phase 1 spec decision #5 (dual-mode generator runtime — ADR owed) |
| Predecessor | Phase 2 Sprint 1 — Registry & Shared Contracts (merge `dbac0e5`) |
| Checkpoint gate | Engagement-lead review of the squash-merge PR before sub-sprint 2.3 (Code Intake) begins |
| Status | Design approved; awaiting written-spec review before implementation plan |

## TL;DR

This sub-sprint builds the **Pipeline Factory**: the one-time-per-model machinery that
turns a hand-authored `model_config.yaml` into a complete, registry-routed scoring
pipeline. It delivers a Python CLI (`generate-pipeline`) with three subcommands
(`validate` / `generate` / `register`), two Jinja2 templates (`standard-batch` and
`scalable-batch`) plus a `realtime` placeholder, a new `pipeline-manifest-payload`
JSON Schema in `platform-contracts`, and per-version immutable artifact directories
at `pipelines/<name>/<version>/`. On merge to `main`, a CI step POSTs the generated
registration to the Registry API (SigV4 via GitHub Actions OIDC), so all
governance — validation, the approval state machine, the audit log — flows through
the API built in 2.1. ADR-0008 captures the dual-mode (local dev / CI canonical)
generator runtime owed by ADR-0003. **The manifest is emitted unsigned**; the
asymmetric signing CMK and the CI signing step land in sub-sprint 2.3 (Code Intake)
and fill the envelope's placeholder fields. Consistent with Phase 1 and 2.1, this is
**plan-validate + mocked-AWS only** (no real `terraform apply`, no live API).

## 1. Context

Phase 2 Sprint 1 delivered the keystone: the shared JSON-Schema contracts and the
Model & Pipeline Registry, including an audit-critical approval gate enforced
server-side. With the Registry in place, the Pipeline Factory is the natural next
sub-sprint: it produces the artifact set (Step Functions definition, per-pipeline
Terraform stub, registration body, unsigned manifest) for every model and routes
the registration through the API.

The brief at `CLAUDE_CODE_BRIEF.md` §6 specifies the Factory: a CLI generator
`generate_pipeline.py --config model_config.yaml --out pipelines/<model_name>/`,
Jinja2 templates per model class, schema validation, Step Functions definition
rendering, a Terraform stub registering into the registry, and a manifest with
content hashes for Code Intake to sign. §5 defines the two execution tiers
(standard batch ~20k rows daily; scalable batch 2M–6M rows weekly/monthly). This
sub-sprint implements both tier templates and the full generator surface; it does
**not** implement the `realtime` template (brief §6 explicitly defers it) and does
**not** implement manifest signing (brief §6 says Code Intake signs).

Phase 2 sequencing recap (locked in 2.1):

- **2.1 — Registry & Shared Contracts** ✅ shipped (merge `dbac0e5`).
- **2.2 — Pipeline Factory** — this spec.
- **2.3 — Code Intake + first Track A run** — next; owns SAS/Python validators,
  the KMS asymmetric signing CMK, and the CI signing step that fills the manifest
  envelope this sprint emits unsigned.

## 2. Decisions locked this session

Brainstorming choices answered by the engagement lead, plus the smaller calls made
during design approval.

| # | Topic | Choice | Rationale | Captured by |
| - | --- | --- | --- | --- |
| 1 | Registration mechanism | Generator POSTs the Registry API in CI (SigV4 via GitHub Actions OIDC) | All governance (validation, approval state machine, audit log) flows through the API built in 2.1; no Terraform plumbing for the registration itself; direct DB writes would bypass the gate | ADR-0007 (existing) + this spec §10 |
| 2 | Artifact layout | Per-version immutable directories: `pipelines/<name>/<version>/` | Strongest audit trail (every change visible in git); old versions preserved for reproducibility; clean diffs | This spec §4 |
| 3 | Generator runtime | Dual-mode — local dev (no creds, no API call) and CI canonical (drift-checked, POSTs API on merge) | Allows fast engineer iteration while making CI the single source of governance | ADR-0008 (new) |
| 4 | Template scope | `standard-batch` and `scalable-batch` only; `realtime` is a placeholder file (config schema enum already rejects it) | Brief §6 explicitly defers realtime; the schema's `execution_tier` enum is `["standard", "scalable"]` | This spec §6 |
| 5 | Manifest signing | Factory emits *unsigned* envelope (signature/key-arn/algorithm placeholders); 2.3 provisions the CMK + the CI signing step that fills them | Matches brief §6 ("emits a manifest with content hashes for Code Intake to sign"); keeps the asymmetric-CMK provisioning with the first signer | This spec §9; ADR-0003 |
| 6 | Generator packaging | New uv workspace member `pipeline-factory/` depending on `platform-contracts`; CLI entry point `generate-pipeline` | Matches `registry/api/` precedent; reuses the shared loader and generated models | This spec §4, §7 |
| 7 | `model-config` schema additions | Add **optional** `sas_code_version` and `inference_code_version` strings to `model-config.schema.json`; the generator's `register` subcommand requires them present | The API's registry-record contract requires both; without them, registration would be impossible until 2.3. Additive and backwards-compatible; 2.3's Code Intake will later verify the declared values match the packaged code | This spec §5; regenerated `models.py` |
| 8 | Idempotency on registration | `409 Conflict` from the API is treated as success (record already exists) | Re-runs of the CI register job should not fail; the API's create-conflict path is the natural idempotency signal | This spec §10 |

## 3. Scope

### 3.1 In scope (sub-sprint 2.2)

- New uv workspace member `pipeline-factory/` with the generator package, three
  Jinja2 template trees, CLI, tests.
- Three CLI subcommands: `validate`, `generate`, `register` (the last
  needs SigV4 creds; the first two do not).
- Per-version artifact directories under `pipelines/<name>/<version>/`:
  `statemachine.json`, `registration.json`, `manifest.json` (unsigned envelope),
  and `terraform/` (the per-pipeline TF stub).
- New shared contract `pipeline-manifest-payload.schema.json` in
  `platform-contracts`, with the matching generated Pydantic model and the CI
  drift gate it inherits.
- Two-field additive update to `model-config.schema.json`
  (`sas_code_version`, `inference_code_version`, both optional in the schema; the
  generator's `register` requires them).
- New CI workflow `.github/workflows/pipeline-factory.yml` (PR drift gate +
  on-merge register job, OIDC-authenticated and feature-gated on a secret so it
  is a no-op until AWS credentials land).
- Extension of `terraform-validate.yml` to validate at least one generated
  per-pipeline `terraform/` directory as a proof point.
- ADR-0008 (dual-mode generator runtime) and the Phase 2 Sprint 2 compliance rows.
- One worked-example fixture configuration and golden artifacts under
  `pipeline-factory/tests/fixtures/`.

### 3.2 Out of scope (deferred)

| Item | Where it lands |
| --- | --- |
| `realtime` Jinja2 template body | A future sub-sprint when real-time inference is in scope. Today: placeholder README only |
| Manifest signing (KMS asymmetric CMK, CI signing step) | Sub-sprint 2.3 (Code Intake — first signer) |
| Actual deployment of the per-pipeline Terraform (env-stack wiring, real `apply`) | Phase 3 (Scoring Engine) wires the per-pipeline stub into env stacks |
| The scoring / PIR Lambda + SageMaker / EKS resources the ASL references | Phase 3 / Phase 4; the ASL parameterizes them as `${…}` |
| Provisioning the `pipeline-factory-registrar` IAM role + the GitHub Actions OIDC provider in AWS | Sub-sprint 2.3 (alongside the signing role) — same OIDC IdP, two trusted roles |
| Real `terraform apply` / live API Gateway / integration test against a real Registry | When AWS credentials land |
| SAS / Python static validators | Sub-sprint 2.3 (Code Intake) |
| Synthetic data generator for dev/stg source buckets | Later (Phase 3 dependency) |

## 4. Repo layout

New and changed paths. "WRITTEN" = authored this sub-sprint; "GENERATED" = produced
by the generator and committed.

```
absa-exl-platform/
├── pyproject.toml                                      # CHANGED — add `pipeline-factory` to uv workspace members + pytest testpaths
├── pipeline-factory/
│   ├── pyproject.toml                                  # WRITTEN — workspace member; deps on platform-contracts, jinja2, httpx, boto3, pyyaml, click
│   ├── src/pipeline_factory/
│   │   ├── __init__.py
│   │   ├── cli.py                                      # WRITTEN — `generate-pipeline` Click CLI (validate | generate | register)
│   │   ├── generator.py                                # WRITTEN — orchestrates validate → render → write
│   │   ├── renderer.py                                 # WRITTEN — Jinja2 env, template lookup, canonical-JSON serialisation
│   │   ├── registration.py                             # WRITTEN — SigV4 POST to Registry API; 409-idempotent; 5xx exponential backoff
│   │   ├── manifest.py                                 # WRITTEN — builds the unsigned manifest envelope + payload
│   │   ├── hashing.py                                  # WRITTEN — canonical sha256 (sorted-keys JSON; deterministic for drift gate)
│   │   └── py.typed
│   ├── templates/
│   │   ├── statemachines/
│   │   │   ├── standard-batch.json.j2                  # WRITTEN — daily ~20k rows; SageMaker Batch Transform tier
│   │   │   ├── scalable-batch.json.j2                  # WRITTEN — 2M–6M rows; EKS/Fargate or multi-instance SageMaker tier
│   │   │   └── realtime.json.j2                        # WRITTEN — placeholder only (single comment line; generator refuses tier=realtime)
│   │   └── terraform/
│   │       └── pipeline.tf.j2                          # WRITTEN — aws_sfn_state_machine + EventBridge schedule + IAM role; shared by both tiers
│   ├── configs/
│   │   └── credit-risk-pd/1.0.0/model_config.yaml      # WRITTEN — the worked-example fixture (golden test seed)
│   ├── tests/
│   │   ├── test_validate.py                            # schema-validation tests
│   │   ├── test_generator.py                           # golden-file render tests for both tiers
│   │   ├── test_manifest.py                            # payload + envelope shape, hashing stability
│   │   ├── test_registration.py                        # httpx-mocked POST (201 success, 409 idempotent, 5xx retry)
│   │   ├── test_cli.py                                 # CLI integration via Click runner
│   │   └── fixtures/
│   │       └── expected/credit-risk-pd/1.0.0/          # checked-in expected outputs (4 files mirroring pipelines/)
│   └── README.md                                       # WRITTEN — how to onboard a model (local dev + CI flow)
├── pipelines/                                          # NEW top-level — generated, committed
│   └── credit-risk-pd/1.0.0/                           # GENERATED for the fixture; demonstrates the contract
│       ├── statemachine.json
│       ├── registration.json
│       ├── manifest.json
│       └── terraform/{main.tf, variables.tf, versions.tf}
├── platform-contracts/src/platform_contracts/schemas/
│   ├── model-config.schema.json                        # CHANGED — add optional `sas_code_version`, `inference_code_version`
│   └── pipeline-manifest-payload.schema.json           # WRITTEN — new shared contract
├── platform-contracts/src/platform_contracts/models.py # REGENERATED (drift gate)
├── platform-contracts/tests/
│   └── test_pipeline_manifest_payload_schema.py        # WRITTEN — schema validity + valid/invalid fixtures
├── .github/workflows/
│   ├── pipeline-factory.yml                            # WRITTEN — PR drift check + on-merge register (gated on secrets)
│   └── terraform-validate.yml                          # CHANGED — add `pipelines/credit-risk-pd/1.0.0/terraform` to the stacks matrix
├── docs/adr/0008-generator-runtime-dual-mode.md        # WRITTEN
└── docs/compliance/control-matrix.md                   # CHANGED — Phase 2 Sprint 2 rows
```

## 5. Inputs — `model_config.yaml`

The model-config schema is already canonical in
`platform-contracts/src/platform_contracts/schemas/model-config.schema.json` from
2.1. This sub-sprint makes one **additive, backwards-compatible** change to enable
registration:

- Add `sas_code_version` (string, `minLength: 1`) — **optional in the schema**.
- Add `inference_code_version` (string, `minLength: 1`) — **optional in the schema**.

The schema's `additionalProperties: false` invariant is preserved by listing the
new fields in `properties`. Existing tests stay green because they don't reference
the new fields, and the JSON-Schema-canonical drift gate regenerates `models.py`
to add them. The generator's **`register` subcommand requires both** at runtime —
schema-optional + register-required matches the lifecycle: a developer can iterate
locally without code versions; CI must have them before posting.

A `model_config.yaml` is committed by the onboarding PR at
`pipeline-factory/configs/<model_name>/<version>/model_config.yaml`. It is treated
as immutable per `(name, version)` (a new version is a new directory).

## 6. Templates (Jinja2)

### 6.1 Conventions

- Jinja2 strict mode: `undefined=StrictUndefined`, autoescape off for JSON/HCL
  templates (we control the inputs), `trim_blocks=True`, `lstrip_blocks=True`.
- All rendered outputs are passed through a **canonicaliser** before writing:
  JSON outputs are re-serialised with `sort_keys=True, indent=2`, HCL outputs are
  passed through `terraform fmt` (a subprocess call) on write so generated `.tf`
  is fmt-canonical. This is what makes the CI drift gate reliable.

### 6.2 `standard-batch.json.j2` (daily ~20k-row tier)

A Step Functions Standard Workflow ASL with the following named states (real ARNs
are template parameters — Phase 3/4 fills them in):

```
ValidateInput          (Task, ${ValidateInputLambdaArn})
   ↓
DataQuality            (Task, ${GreatExpectationsRunnerArn})
   ↓  (Catch DQFail → NotifyFailure → Fail)
Score                  (Task, arn:aws:states:::sagemaker:createTransformJob.sync;
                        parameters from {{ model.name }}, {{ model.version }},
                        ${InputBucket}, ${OutputBucket}, tier-specific instance type)
   ↓
WriteOutput            (Task, ${WriteOutputLambdaArn})
   ↓
PIRVariance            (Task, ${PirCheckerArn})
   ↓  (Choice: VarianceWithinThreshold? yes → Notify, no → BlockDelivery)
Notify | BlockDelivery (Tasks publishing to ${NotifyTopicArn})
   ↓
End
```

Catch / Retry blocks are defined for transient AWS errors (`States.TaskFailed`,
`States.Timeout`) with bounded backoff. The `Comment` field carries
`{{ model.name }}@{{ model.version }}` so it appears in execution logs.

### 6.3 `scalable-batch.json.j2` (2M–6M rows weekly/monthly)

Same overall shape as standard-batch. Two differences:

- `Score` is `arn:aws:states:::eks:runJob.sync` (or a SageMaker multi-instance
  Batch Transform — picked at template level; this spec uses EKS-on-Fargate to
  match brief §5's "EKS + Spark / SageMaker with multi-instance"). The job
  manifest is parameterised by the Spark resource sizing from a per-tier defaults
  block.
- A `WaitForDataAvailability` Wait state guards the start, since this tier
  triggers weekly / monthly off the EventBridge schedule rather than on each
  data arrival.

### 6.4 `realtime.json.j2` (placeholder only)

A single-line file containing
`// Placeholder — real-time inference template is deferred (brief §6).`
The generator refuses `execution_tier=realtime` outright — the canonical
`model-config.schema.json` enum is `["standard", "scalable"]` from 2.1, so the
validate step rejects it before the renderer is reached. The placeholder exists
purely so the `templates/statemachines/` directory documents the full set.

### 6.5 `pipeline.tf.j2` (per-pipeline Terraform stub, shared by both tiers)

Renders, in `pipelines/<name>/<version>/terraform/`:

- `versions.tf` — pins `aws ~> 5.100`.
- `variables.tf` — `cmk_arn`, `input_bucket_arn`, `output_bucket_arn`,
  `notify_topic_arn`, env tags, plus the Phase-3 ARN inputs that the ASL parameters
  refer to.
- `main.tf` — `aws_sfn_state_machine.this` (definition reads `../statemachine.json`
  via `file()`), `aws_cloudwatch_event_rule.schedule` (cron from
  `schedule_cadence`), `aws_cloudwatch_event_target.this`, an `aws_iam_role` for
  the state machine, and a `aws_cloudwatch_log_group` for SFN execution logs (KMS
  via `var.cmk_arn`).

This stub is **plan-validate only** in this sub-sprint. Phase 3 wires per-pipeline
stubs into env stacks and applies them.

## 7. Generator CLI

A single binary, three subcommands. Built on Click for argument parsing.

| Command | Args | What it does | Creds? |
| --- | --- | --- | --- |
| `generate-pipeline validate` | `--config <path>` | Loads YAML, validates against the canonical `model-config` JSON Schema via `platform_contracts.loader.validate`. Exits 0 on pass | no |
| `generate-pipeline generate` | `--config <path>` | `validate` → render templates → write to `pipelines/<model_name>/<version>/`. **Idempotent**: if the output dir exists, re-renders, diffs against existing files, fails if drift is detected (matching the CI drift gate behaviour). `--force` overwrites without diff. Writes `statemachine.json`, `registration.json`, `manifest.json`, `terraform/*.tf` | no |
| `generate-pipeline register` | `--pipeline <name>@<version>` (resolves the dir) or `--config <path>`; `--dry-run` | Reads `pipelines/<name>/<version>/registration.json` and POSTs to the Registry API endpoint (env var `REGISTRY_API_ENDPOINT`). SigV4-signs via boto3 + `aws-requests-auth`. `--dry-run` logs what would be posted without calling the API | yes (unless `--dry-run`) |

CLI errors map to non-zero exit codes with structured stderr (JSON line) so CI can
parse failures.

## 8. Generated artifact structure

For one model+version, the generator writes exactly four artifacts:

```
pipelines/<model_name>/<version>/
├── statemachine.json     # The rendered Step Functions ASL. Read by the per-pipeline TF stub via file().
├── registration.json     # The body the registrar POSTs to the Registry API.
│                          # Matches `CreateModelRequest` from 2.1 exactly.
├── manifest.json         # The UNSIGNED manifest envelope (see §9). 2.3 fills the signature fields.
└── terraform/
    ├── versions.tf, variables.tf, main.tf
```

The directory is immutable per `(name, version)`. A new version produces a new
sibling directory. Cleanup of old versions is a Phase 4 concern (object-lock
retention applies to the data, not the artifacts; git history holds the artifacts).

### 8.1 `registration.json` body

Exactly the `CreateModelRequest` shape from 2.1:

```json
{
  "model_name": "credit-risk-pd",
  "version": "1.0.0",
  "sas_code_version": "<from model_config>",
  "inference_code_version": "<from model_config>",
  "schedule_cadence": "<from model_config>",
  "execution_tier": "standard",
  "input_schema_ref": "<from model_config>",
  "output_schema_ref": "<from model_config>",
  "pir_doc_ref": "<from model_config>",
  "owner_email": "<from model_config>",
  "accountable_executive": "<from model_config>",
  "sla_seconds": 3600,
  "cab_record_id": null,
  "ivu_evidence_ref": null
}
```

The API sets server-managed fields (`approval_status=pending`, `created_at`,
`updated_at`, `last_scored_at=null`, `rev=0`) on receipt.

## 9. Manifest payload schema (new shared contract)

A new schema `platform-contracts/src/platform_contracts/schemas/pipeline-manifest-payload.schema.json`
(Draft 2020-12, `$id` `.../pipeline-manifest-payload/v1.json`, title
`PipelineManifestPayload`, `additionalProperties: false`).

| Field | Type / constraint | Required | Notes |
| --- | --- | --- | --- |
| `schema_version` | const `1` | yes | for future evolution |
| `generator_version` | string, semver | yes | pinned from the `pipeline-factory` package version |
| `model_name` | string, model-config pattern | yes | must match the registration body |
| `version` | string, semver | yes | must match the registration body |
| `tier` | enum `standard` \| `scalable` | yes | from model-config |
| `generated_at` | string, `date-time` | yes | ISO-8601 UTC |
| `artifact_hashes` | object | yes | required keys: `statemachine_sha256`, `terraform_sha256`, `model_config_sha256`, `registration_sha256` |

The payload is wrapped in the existing `manifest-envelope` (2.1):

- `subject_type = "pipeline"`
- `subject_ref = "pipelines/<name>/<version>/"`
- `digest = sha256(canonical_json(payload))`
- `digest_algorithm = "SHA-256"`
- **`signature = "UNSIGNED"`** (the sentinel constant `UNSIGNED_SIGNATURE` in
  `pipeline_factory.manifest`), **`signing_key_arn = "arn:aws:kms:placeholder:000000000000:key/unsigned"`**
  (`UNSIGNED_KEY_ARN`), **`signing_algorithm = "RSASSA_PKCS1_V1_5_SHA_256"`** (an
  envelope-valid enum value, deliberately picked). The sentinel values satisfy
  the envelope's strict validation (`signature` minLength 1; `signing_key_arn`
  pattern `^arn:aws:kms:`), so the unsigned manifest passes envelope-schema
  validation cleanly. 2.3's signing step overwrites these three fields with real
  values.

To make "unsigned" detectable without relying on schema validation, the generator
exposes `pipeline_factory.manifest.is_signed(envelope) -> bool` — returns `False`
when `signature == UNSIGNED_SIGNATURE`. A unit test asserts an unsigned envelope
both passes the JSON-Schema validator and is detected as unsigned by `is_signed`.

Alternative considered: write `signature = ""` and accept that the envelope
schema would fail. Rejected — it forces a "skip envelope validation for our own
outputs" carve-out everywhere we touch the manifest.

`artifact_hashes` are computed over the **canonicalised** form of each file (sorted
JSON for JSON outputs, `terraform fmt`'d HCL for `.tf`). This is what makes the
drift gate stable.

## 10. Registration flow

On push to `main`, CI runs `generate-pipeline register --all` (or per-pipeline)
under an IAM role assumed via the GitHub Actions OIDC provider.

1. Discover candidates: every `pipelines/<name>/<version>/registration.json`
   present in the merged commit. The registrar attempts to register all of them;
   already-registered records resolve via the `409`-idempotent path (step 3),
   so there is no separate pre-check.
2. POST `${REGISTRY_API_ENDPOINT}/models` with the body. The request is signed
   with SigV4 against the API Gateway's region using boto3 credentials from the
   OIDC role.
3. **Response handling**
   - `201 Created` → log + audit (`registration_succeeded`); proceed to next.
   - `409 Conflict` → treat as idempotent success; log
     (`registration_already_exists`).
   - `4xx` other → fail the CI step loudly with the API error body.
   - `5xx` → exponential backoff (1s, 4s, 16s) with up to 3 attempts; if all
     fail, fail the CI step.
4. After all registrations succeed, emit a summary JSON line to stdout
   (`{ "registered": [...], "skipped": [...] }`).

The IAM role `pipeline-factory-registrar` (defined but not deployed this sprint)
trusts the GitHub Actions OIDC provider for this repository's `main` branch only
(`token.actions.githubusercontent.com` with subject filter
`repo:absa-group/absa-exl-platform:ref:refs/heads/main`). Its inline policy is the
**writer-policy ARN exported by `pipeline-registry`** (i.e., `execute-api:Invoke`
scoped to POST/PATCH routes on the Registry API).

Until AWS credentials land, the register job in CI is gated on
`secrets.AWS_OIDC_REGISTRAR_ROLE_ARN`; if absent, the step is skipped with a clear
log line.

## 11. Per-pipeline Terraform stub

The stub at `pipelines/<name>/<version>/terraform/` is a thin module instance, not
a full module. It declares only the resources unique to *this* pipeline: the SFN
state machine, the EventBridge rule, the IAM role, and the SFN log group.
**Inputs** (variables) it expects from a calling env stack (Phase 3 wires these):

- `cmk_arn` — the KMS CMK for SFN log encryption
- `input_bucket_arn`, `output_bucket_arn`
- `notify_topic_arn`
- The Phase-3 placeholder ARNs (`scoring_lambda_arn`, `pir_checker_arn`,
  `write_output_lambda_arn`, `dq_runner_arn`)
- `tags`

The stub is `terraform validate`d in CI (proves the rendered HCL is valid) but
never `apply`ed in this sprint. Phase 3 supplies the actual ARNs and wires the
stub into env stacks at `terraform/envs/{env}/scoring/`.

## 12. ADR-0008 — Generator runtime dual-mode

The ADR Phase 1 owed (decision #5). Records:

- **Local dev mode** — the engineer runs `uv run generate-pipeline generate` (and
  optionally `register --dry-run`) on their workstation. No AWS creds; no
  side-effects beyond local files. Used to iterate on `model_config.yaml` and
  watch the generator's outputs change.
- **CI canonical mode** — GitHub Actions runs `generate` on every PR (drift gate:
  re-render, diff against committed; fail on drift). On push to `main`, GHA
  additionally runs `register` against the live Registry API using the
  OIDC-assumed role. **Only CI may POST to the API in this design.**
- Same binary, same code path; mode is a function of the subcommand and the
  presence of OIDC creds.
- Future: in 2.3 the same dual-mode applies to signing — local can sign
  speculatively against a non-prod CMK (or skip), but CI is the only signer
  whose output is treated as canonical (per ADR-0003).

MADR 3.0 format, identical structure to ADR-0006/0007.

## 13. CI strategy

### 13.1 New workflow `pipeline-factory.yml`

Trigger:
- `pull_request` with paths `pipeline-factory/**`, `pipelines/**`,
  `platform-contracts/**`, `pyproject.toml`, `uv.lock`,
  `.github/workflows/pipeline-factory.yml`.
- `push` to `main` with the same paths.

Jobs:
1. `validate-and-generate` (PR + push): `uv sync --frozen`, `uv run pytest
   pipeline-factory/tests`, `uv run generate-pipeline generate --config <each
   model_config> --force` then `git diff --exit-code pipelines/` — the drift
   gate.
2. `register` (push to `main` only): runs after `validate-and-generate`. Uses
   `aws-actions/configure-aws-credentials@v4` with `role-to-assume:
   ${{ secrets.AWS_OIDC_REGISTRAR_ROLE_ARN }}`. Gated on the presence of that
   secret using the standard env-var indirection workaround (GitHub Actions does
   not allow direct `secrets.*` references in job-level `if:`): a pre-step
   exposes the secret as `env.ROLE_ARN`, and the register step runs
   `if: env.ROLE_ARN != ''`. Until the secret is set, the register step is a
   documented no-op. The step calls `uv run generate-pipeline register --all`
   with `REGISTRY_API_ENDPOINT` from a second secret.

### 13.2 Extension to `terraform-validate.yml`

Add `pipelines/credit-risk-pd/1.0.0/terraform` to the `validate-stacks` matrix.
This proves a generated per-pipeline stub is valid HCL. Future per-version dirs
land automatically when added to the matrix (or — better — when a small script
discovers them; pragmatically, manual matrix entry for the fixture is enough
for this sprint).

### 13.3 Triggers + branch protection

The existing `terraform-validate.yml` matrices already include `phase-2/**`
triggers from 2.1. `pipeline-factory.yml` follows the same convention (`main`
plus the active phase branches). Branch protection on `main` is unchanged;
CODEOWNERS gains `pipeline-factory/` and `pipelines/` → `@platform-leads`.

## 14. Testing strategy

- **Python unit (pytest + httpx mock)** —
  - `validate`: schema rejects malformed configs (missing required field, bad
    tier enum, bad s3:// pattern, additional property).
  - `generate`: renders the fixture config and produces byte-identical outputs to
    the checked-in `tests/fixtures/expected/credit-risk-pd/1.0.0/`. Tests both
    tiers via a second fixture.
  - `manifest`: payload validates against the new schema; envelope's placeholder
    fields are explicit constants; digest is stable across runs.
  - `register`: 201 path succeeds; 409 maps to idempotent success; 5xx triggers
    backoff (`pytest-httpx` queues a 502 then 201 and asserts the second attempt
    succeeds); `--dry-run` does not call the network.
  - `cli`: Click runner test for each subcommand and key flag (`--force`,
    `--dry-run`).
- **Contract tests** — every fixture in `platform-contracts/.../examples/`-equivalent
  validates (we continue to use inline fixtures as in 2.1; carrying over the
  decision); new schema's `examples/` lives inline in the test file.
- **Terraform** — `terraform validate` against the generated stub in CI
  (matrix extension). No apply.
- **Drift gate** — the CI `validate-and-generate` job is the executable drift
  contract (re-render + `git diff --exit-code`). Mirrors the Pydantic drift gate.

## 15. ADRs to author

| ID | Title | Summary |
| - | --- | --- |
| 0008 | Generator runtime — dual-mode (local + CI) | Same binary; local dev is no-creds/no-API; CI is canonical with drift checks and the only API caller. Records the deferred decision from ADR-0003 and Phase 1 spec decision #5. |

(No other ADRs in this sub-sprint. ADR-0003 already covers signing.)

## 16. Compliance mapping (Phase 2 Sprint 2 rows)

Append to `docs/compliance/control-matrix.md` (4-column format, before the
deferred list):

| Control | Implementation | Evidence artifact | Owner |
| --- | --- | --- | --- |
| **SR 11-7 III.1 — model documentation** | Per-version immutable artifact directories committed in git (model_config, statemachine, registration, manifest, terraform) | `pipelines/<name>/<version>/`, `pipeline-factory/configs/<name>/<version>/model_config.yaml` | EXL Platform Engineering |
| **SR 11-7 III.4 — implementation evidence** | API-routed registration preserves the audit log + approval gate from 2.1; CI is the only POST path | `.github/workflows/pipeline-factory.yml` (`register` job), `pipeline_factory/registration.py` | EXL Platform Engineering |
| **SARB GOI 3 — model risk governance** | Generator can only create `pending` records; CAB + IVU still required to flip to `approved` (gate is in the API) | `registry/api/src/registry_api/transitions.py`, `pipeline_factory/registration.py` | ABSA Model Risk |
| **ISO 27001 A.14.2 — secure development** | Drift gate + golden-file tests ensure generated artifacts are reproducible bit-for-bit; CI is the canonical signer (per ADR-0008) | `.github/workflows/pipeline-factory.yml`, `pipeline-factory/tests/fixtures/expected/` | EXL Platform Engineering |

## 17. Open items for the engagement lead

Not blocking this sub-sprint; worth confirming before or shortly after the
checkpoint.

1. **GitHub Actions OIDC provider in AWS** — needs to be provisioned per EXL
   account (one-time, per env). 2.3 will define the Terraform; confirm ABSA has
   no objections to a `token.actions.githubusercontent.com` OIDC IdP in the EXL
   accounts.
2. **Onboarding workflow** — model_config files are committed by the developer's
   PR. Alternative (deferred): a `workflow_dispatch` "Onboard model" job that
   takes the inputs and opens a PR. Confirm the PR-first flow is acceptable for
   the Industrialization Team.
3. **Schedule semantics** — `model_config.yaml.schedule_cadence` accepts
   EventBridge cron (`cron(0 6 * * ? *)`). Confirm ABSA's existing SAS schedules
   translate cleanly; if not, the Factory may need a small translator.
4. **CI secrets `AWS_OIDC_REGISTRAR_ROLE_ARN` and `REGISTRY_API_ENDPOINT`** — set
   per environment when AWS credentials and the Registry deployment land. Until
   then, the `register` job is a documented no-op.

## 18. Deliverables manifest

- [ ] `pipeline-factory/pyproject.toml` (new workspace member) + uv.lock update
- [ ] `pipeline-factory/src/pipeline_factory/{cli,generator,renderer,registration,manifest,hashing}.py` + `py.typed`
- [ ] `pipeline-factory/templates/statemachines/{standard-batch,scalable-batch,realtime}.json.j2`
- [ ] `pipeline-factory/templates/terraform/pipeline.tf.j2`
- [ ] `pipeline-factory/configs/credit-risk-pd/1.0.0/model_config.yaml`
- [ ] `pipeline-factory/tests/{test_validate,test_generator,test_manifest,test_registration,test_cli}.py` + `fixtures/expected/...`
- [ ] `pipelines/credit-risk-pd/1.0.0/{statemachine.json, registration.json, manifest.json, terraform/*.tf}` (generated, committed)
- [ ] `platform-contracts/src/platform_contracts/schemas/pipeline-manifest-payload.schema.json`
- [ ] `platform-contracts/src/platform_contracts/schemas/model-config.schema.json` (additive change)
- [ ] `platform-contracts/src/platform_contracts/models.py` (regenerated; drift gate verifies)
- [ ] `platform-contracts/tests/test_pipeline_manifest_payload_schema.py`
- [ ] `.github/workflows/pipeline-factory.yml`
- [ ] `.github/workflows/terraform-validate.yml` (matrix extension)
- [ ] `docs/adr/0008-generator-runtime-dual-mode.md`
- [ ] `docs/compliance/control-matrix.md` (Phase 2 Sprint 2 rows)
- [ ] `pipeline-factory/README.md` + `CODEOWNERS` update + root `pyproject.toml` update

## 19. Branch / commit strategy

Branch `phase-2/sprint-2-pipeline-factory` off `main` (already created). Logical
commits for reviewer ergonomics:

1. Workspace tooling: new `pipeline-factory` member; root `pyproject.toml` workspace + testpaths update.
2. Contracts: `model-config` schema extension + new `pipeline-manifest-payload.schema.json` + regenerated `models.py` + new payload schema test.
3. Templates: `statemachines/{standard-batch,scalable-batch,realtime}.json.j2` + `terraform/pipeline.tf.j2`.
4. Generator core: `renderer`, `generator`, `manifest`, `hashing`, `cli` (validate + generate subcommands), unit tests.
5. Registration: `registration.py` (SigV4 POST, retry/idempotency) + tests.
6. Fixture + golden outputs: `configs/credit-risk-pd/1.0.0/model_config.yaml` + checked-in `pipelines/credit-risk-pd/1.0.0/*` + `fixtures/expected/*`.
7. CI: `pipeline-factory.yml` + `terraform-validate.yml` matrix update.
8. ADR-0008 + compliance rows + CODEOWNERS + READMEs.

One squash-merge PR for engagement-lead review at the checkpoint gate before
sub-sprint 2.3 (Code Intake) begins.
