# ABSA × EXL Model Hosting & Delivery Operations — Technical Overview

| Field | Value |
| --- | --- |
| Audience | EXL delivery pod (engineers) + delivery / risk leads |
| Status | Phase 1 Foundation complete · Phase 2 Sprint 1 (Registry) complete · Phase 2 Sprint 2 next |
| Last updated | 2026-05-26 |
| Repo | `C:\Vishnu\Claude\absa-exl-platform` |
| Canonical refs | [`docs/architecture.md`](architecture.md), [`docs/adr/`](adr/), [`CLAUDE_CODE_BRIEF.md`](../CLAUDE_CODE_BRIEF.md) |

## How to read this document

This is the single end-to-end explainer for what we are building and why. It is written for two readers:

- **Leads** — read §1–§4 and §8 (the goal, the operating model, the architecture in brief, and the roadmap/status). ~10 minutes.
- **Engineers** — read everything; §5–§7 and §9–§10 carry the technical and "how to work in this repo" detail.

It deliberately **links rather than duplicates**: the authoritative architecture lives in [`docs/architecture.md`](architecture.md), decisions in [`docs/adr/`](adr/), and the per-sprint specs/plans in [`docs/superpowers/`](superpowers/).

---

## 1. The goal

ABSA Group has more models (credit, fraud, collections, propensity) than its current infrastructure can deploy, score, and govern reliably. Refreshing a model takes 8–12 weeks, drift goes undetected, and audit evidence is fragmented — all under rising SARB/POPIA scrutiny.

**We are building a production-grade, audit-ready ML hosting platform on AWS that lets ABSA productionise developer-authored SAS / Python models, score them on a schedule, and reconcile every run against the developer's own evidence — without raw PII ever leaving the ABSA trust boundary.**

Engagement shape:

- **5-month build**, **10-FTE EXL pod** (8 offshore + 2 onsite at ABSA).
- **10 models** in the initial cohort.
- Greenfield AWS — nothing to migrate.
- Delivered as **fixed-price service units** (platform foundation, per-model onboarding, managed run), not time-and-materials. Commercial detail lives in the investment workbook; this document is the technical view.

The hard constraints (these shape every design decision):

1. **Raw PII never leaves the ABSA AWS account.** Only *model-ready* data (already curated, no raw identifiers) crosses to EXL.
2. **Everything is auditable** — cross-account access, key usage, and model approvals are all first-class CloudTrail/evidence events.
3. **No model reaches production without governance** — CAB approval + Independent Validation (IVU) evidence are enforced, not optional.
4. **5 months to first scoring** — no foundation work that can't land a scoring model inside the schedule.

---

## 2. The two-track operating model

The platform is two distinct, registry-linked flows. We build them as separate pipelines.

### Track A — Model Onboarding & Pipeline Factory (one-time per model)

```
ABSA developer (SAS + inference code)
        │
        ▼
EXL Industrialization Team (ONSITE at ABSA) — standardise & package; NO core-logic changes
        │
        ▼
Controlled handoff (signed manifest)
        │
        ▼
EXL Code Intake — static scans · schema · tests · PIR mapping
        │
        ▼
Pipeline Factory — generate a scoring pipeline from a template (schedule, DQ, PIR hooks, I/O)
        │
        ▼
Model & Pipeline Registry (DynamoDB) — version, schedule, owner, SLA, approval status
```

### Track B — Scheduled Scoring Execution (recurring)

```
ABSA SAS scheduler (daily / weekly / monthly)
        │
        ▼
ABSA writes model-ready data to its own S3 bucket (in ABSA's account)
        │
        ▼ S3 cross-account replication (15-min RTC)   ← the key data path; NOT PrivateLink
EXL landing bucket (in the matching EXL env account)
        │
        ▼ EventBridge → Step Functions
DQ (Great Expectations) → load to model zone → registry lookup → scoring engine (tiered)
        │
        ▼
Score output (snapshot + lineage) → PIR reconciliation (variance gate) → secure delivery to ABSA
```

The **Registry is the hinge** between the two tracks: Track A registers a model+pipeline; Track B looks it up to run it on cadence. That is why it is the first thing we built in Phase 2.

---

## 3. Reference architecture

Four zones, one controlled data path, one controlled control path.

```
 ABSA TRUST ZONE (1 AWS account)          TRANSIT              EXL ENCLAVE (3 AWS accounts: dev / stg / prod)
┌──────────────────────────────┐                        ┌──────────────────────────────────────────────────┐
│ Core banking / risk marts     │                        │  LANDING + DQ              FACTORY / REGISTRY / RUN │
│ Raw data lake  (PII stays)    │   ── S3 cross-acct ──▶ │  ┌───────────────┐   ┌────────────────────────────┐│
│ Industrialization Team        │      replication       │  │ Landing S3+KMS│ → │ Pipeline Factory           ││
│  (EXL onsite, SAS packaging)  │   (model-ready data,   │  │ Great Exp. DQ │   │ Model & Pipeline Registry  ││
│ Controlled handoff            │    15-min RTC SLA)     │  │ Code Intake   │   │ Scoring Engine (tiered)    ││
│  (signed manifest)            │                        │  └───────────────┘   │ PIR Engine                 ││
│                               │   ◀── PrivateLink ───  │                      │ Secure delivery (SFTP/API) ││
│                               │   (CONTROL PLANE only: │                      └────────────────────────────┘│
│                               │    registry API,       │   Observability · CloudTrail (both accts) · KMS    │
│                               │    score delivery)     │                                                    │
└──────────────────────────────┘                        └──────────────────────────────────────────────────┘
       RAW PII NEVER LEAVES ABSA          only model-ready data + signed code ever cross the boundary
```

Three load-bearing architecture calls:

### 3.1 Data movement = S3 cross-account replication (NOT PrivateLink)

This is the most important correction over the original proposal. Bulk model-ready data crosses ABSA→EXL via **S3 cross-account replication** with Replication Time Control (15-min SLA), KMS-encrypted on both sides with separate per-env CMKs, versioning + object-lock compliance mode. **PrivateLink is reserved for control-plane API calls only** (the Registry API, scoring/status APIs, score delivery) — never bulk data. Rationale: PrivateLink scales API calls, not multi-million-row parquet; and S3 replication metrics + CloudTrail give the audit trail SR 11-7 reviewers expect. See [ADR-0001](adr/0001-data-movement-s3-replication.md).

### 3.2 Account topology = 1 ABSA + 3 EXL, "Pattern Z"

ABSA allocates **one** AWS account; EXL uses **three** (dev/stg/prod, their standard). Pattern Z: the single ABSA account holds three env-suffixed source buckets, each replicating to its matching EXL env account. EXL-side isolation is "free" from separate accounts; ABSA-side env isolation comes from per-env buckets, keys, and replication roles. See [ADR-0004](adr/0004-account-topology-1-absa-3-exl.md).

### 3.3 Execution tiering (stored per model in the registry)

| Tier | Model class | Cadence | Volume | Pattern |
| --- | --- | --- | --- | --- |
| **Standard batch** | Application models | Daily | ~20k rows | SageMaker Batch Transform |
| **Scalable batch** | Scoring models | Weekly / monthly | 2M–6M rows | EKS + Spark / multi-instance SageMaker |

The Pipeline Factory selects the tier from one config field (`execution_tier: standard | scalable`) — we never hand-roll per model.

---

## 4. Key architectural decisions (ADRs)

All decisions are recorded as ADRs (MADR format) in [`docs/adr/`](adr/). Current set:

| ADR | Decision | One-liner |
| --- | --- | --- |
| [0001](adr/0001-data-movement-s3-replication.md) | Data movement via S3 replication | Bulk data crosses via S3 cross-account replication; PrivateLink is control-plane only. |
| [0002](adr/0002-cross-account-iac-dual-module-split.md) | Cross-account IaC dual-module split | `s3-replication` is split into `-source` (deploys into ABSA) and `-destination` (deploys into EXL); each side owns its state. |
| [0003](adr/0003-manifest-signing-kms-asymmetric.md) | Manifest signing via KMS asymmetric | Code-intake + factory manifests are signed by CI with KMS asymmetric CMKs; verifiable online or offline against a published public key. |
| [0004](adr/0004-account-topology-1-absa-3-exl.md) | Account topology (Pattern Z) | One ABSA account (3 env-suffixed source buckets) → three EXL env accounts. |
| [0005](adr/0005-kms-hierarchy-audit-evidence-only.md) | KMS hierarchy = audit-evidence keys only | The central `kms-hierarchy` module owns only audit-grade keys; per-data-class workload keys live in their owning module. |
| [0006](adr/0006-contract-strategy-json-schema-canonical.md) | Contract strategy — JSON Schema canonical | JSON Schema is the hand-authored contract; Pydantic is generated from it with a CI drift gate. Sets the Python tooling baseline. |
| [0007](adr/0007-registry-data-model-and-api.md) | Registry data model & API | DynamoDB single-table `(model_name, version)` + `by_status` GSI; FastAPI on one Lambda via Mangum; IAM auth; CAB+IVU approval gate. |

(One more ADR — the dual-mode generator runtime — is owed in Sprint 2.2 when the Pipeline Factory lands.)

---

## 5. Security, privacy & compliance

Compliance is not a bolt-on; every Terraform module and service maps to specific controls in [`docs/compliance/control-matrix.md`](compliance/control-matrix.md).

Posture highlights:

- **PII boundary** — raw PII stays in ABSA; only model-ready data crosses (POPIA data sovereignty).
- **Encryption** — KMS everywhere, separate per-env CMKs, rotation on; object-lock compliance mode on hand-off and landing buckets for audit-grade immutability.
- **Access** — IAM federation via ABSA SSO; permissions boundaries enforce env-scoped, tag-based access on EXL workload roles; break-glass requires MFA.
- **Audit** — CloudTrail in both accounts logs every cross-account object op, KMS Sign/Decrypt, and AssumeRole; the Registry adds a structured per-mutation audit log.
- **Governance gate** — a model cannot be marked `approved` in the Registry without a CAB record and an IVU evidence reference (enforced server-side; see §9.2).

Regulator mapping the platform is built against: **POPIA · SARB GOI 3/5 · SR 11-7 · ISO 27001 · SOC 2 Type II · ABSA GMRMG.**

---

## 6. The build — phases & current status

Four phases over five months:

| Phase | Months | Scope | Status |
| --- | --- | --- | --- |
| **1 — Foundation** | 1 | Landing zone, KMS hierarchy, IAM federation, S3 replication, CI/CD | ✅ **Complete** (kickoff + sprint 2) |
| **2 — Pipeline Factory + Registry** | 2–3 | Templates, generator CLI, Code Intake, Registry API, signed handoff | 🟡 **In progress** — Sprint 1 (Registry) done |
| **3 — Scoring Engine** | 3–4 | Standard + scalable tiers, EventBridge orchestration, delivery adapters | ⬜ Not started |
| **4 — PIR + Hardening** | 4–5 | Variance gates, DR runbooks, SR 11-7 evidence pack, audit hub | ⬜ Not started |

**Phase 2 is decomposed into three sub-sprints** (it bundled too much for one spec):

- **2.1 — Registry & Shared Contracts** ✅ — the system of record + the schemas the other two write into. *(the keystone — done first)*
- **2.2 — Pipeline Factory** ⬜ — Jinja templates + `generate_pipeline.py` (validate config → render Step Functions → register into the registry → emit a signable manifest).
- **2.3 — Code Intake + first Track A run** ⬜ — SAS/Python validators + KMS signer + GitHub Actions sign-and-handoff, then one test model wired end-to-end.

> **Important posture:** everything to date is **plan-validate + mocked-AWS only** — no real `terraform apply`, no live AWS — because account credentials aren't provisioned yet. Terraform is validated via `terraform test` (plan-only, mock providers); Python is tested against `moto` (in-memory AWS). Real `apply` and integration tests begin once AWS accounts/credentials land.

---

## 7. Deep dive — what's built so far

### 7.1 Phase 1 — Foundation (Terraform)

Five Terraform modules, each with a `terraform test` plan-validate suite, plus env and account-bootstrap stacks:

- `landing-zone` — 3-tier VPC, TGW attachment, flow logs, GuardDuty/Security Hub, permissions boundary.
- `s3-replication-source` (deploys into ABSA) / `s3-replication-destination` (deploys into EXL) — the replication pair (ADR-0002), KMS, object-lock, RTC, replication-lag alarms.
- `kms-hierarchy` — audit-evidence CMKs (CloudTrail bucket, flow-logs/CW Logs) (ADR-0005).
- `iam-federation` — ABSA SSO federation, RBAC, break-glass.
- `terraform/envs/{dev,stg,prod}/{source,destination}` + `terraform/account-bootstrap/exl-{env}` (CloudTrail, GuardDuty, Security Hub, CIS metric filters/alarms).

### 7.2 Phase 2 Sprint 1 — Registry & Shared Contracts (the new work)

This sub-sprint introduced the **first Python in the repo** and the **system of record**. Three pieces:

**(a) `platform-contracts/` — the shared contracts package.** JSON Schema (Draft 2020-12) is the canonical, hand-authored contract (ADR-0006). Three schemas: `model-config` (the Factory's per-model input), `registry-record` (the DynamoDB item), `manifest-envelope` (the signing envelope). Pydantic v2 models are **generated** from the schemas and committed; CI regenerates and fails on any diff, so "Pydantic ≡ JSON Schema" is enforced, not hoped for.

**(b) `registry/api/` — the Model & Pipeline Registry API.** A FastAPI app running as a single Lambda via Mangum, behind an API Gateway HTTP API with `AWS_IAM` (SigV4) auth (ADR-0007). It fronts a DynamoDB table:

```
POST /models                                  create a model+version (status → pending)
GET  /models?status=                          list (by-status GSI) / all
GET  /models/{name}                           list versions of a model
GET  /models/{name}/versions/{ver}            fetch one
PATCH /models/{name}/versions/{ver}           update mutable fields (optimistic-locked by rev)
POST /models/{name}/versions/{ver}:approve    pending → approved   (GATED — see §9.2)
POST /models/{name}/versions/{ver}:retire     approved → retired
```

Internals: a thin DynamoDB repository (optimistic concurrency via a `rev` counter + condition expressions), an approval **state machine**, structured audit logging, and a uniform error envelope. Backed by `moto` tests.

**(c) `terraform/modules/pipeline-registry/` + 3 env stacks.** The infra for the above: DynamoDB (composite key `(model_name, version)`, `by_status` GSI, PITR, module-owned KMS CMK with a CloudWatch-Logs key policy, deletion protection) + the Lambda + API Gateway HTTP API + encrypted log groups + reader/writer caller IAM policies. Validated with a `tftest` suite.

How the pieces wire (and will wire) together:

```
model-config.json ──(2.2 Pipeline Factory: validate + render)──▶ Step Functions def + signed manifest
        │                                                                  │
        └──────────────────────── registry record ───────────────────────┘
                                       │
                                       ▼
                         Registry API  (POST /models, :approve)
                                       │
                       Track B scoring looks up the registry by (model_name, version)
```

### 7.3 The audit-critical approval gate

Brief §9 requires CAB approval and IVU evidence before a model goes live. We enforce it in code, server-side:

- The only way to change `approval_status` is the `:approve` / `:retire` actions — **never** via `PATCH` (so the gate can't be bypassed by a field update).
- `:approve` is rejected (HTTP 422) unless the record has **both** `cab_record_id` and `ivu_evidence_ref`.
- Transitions are restricted to `pending → approved → retired` (any other edge → HTTP 409).
- Every mutation writes a structured audit line (principal, action, old→new status, rev) — the SR 11-7 evidence trail.

---

## 8. Roadmap & open items

**Immediate next:** Sub-sprint **2.2 — Pipeline Factory**, then **2.3 — Code Intake + first end-to-end Track A run**. Then Phase 3 (Scoring Engine) and Phase 4 (PIR + hardening).

**Deferred to the "apply" sprint** (when AWS credentials land): real `terraform apply`, a state backend (S3 + DynamoDB lock), integration tests against ephemeral accounts/LocalStack, and per-module apply-time hardening (reserved concurrency, X-Ray tracing, API-Gateway throttling).

**Open items for the engagement lead / ABSA** (none block engineering today):

- Confirm the canonical schema-registry `$id` domain (currently a placeholder).
- Replace placeholder ABSA Identity Center SAML provider ARN; confirm MFA claim in assertions (break-glass dependency).
- Provide SNS subscriber addresses for `${env}-security-alerts` and the replication-lag alarms.
- ABSA Compliance sign-off on prod retention years (default 7).
- Terraform vs OpenTofu confirmation (bank procurement).
- AFT timeline for the three EXL accounts (gates Phase 2 `apply`).

---

## 9. Engineering conventions — how to work in this repo

This is the "you just joined the pod" section.

### 9.1 Repo layout

```
docs/                         architecture.md, ADRs, compliance matrix, specs/plans (this doc lives here)
platform-contracts/           shared JSON-Schema contracts + generated Pydantic models (Python, uv workspace member)
registry/                     Model & Pipeline Registry — api/ (FastAPI) + schema/ (pointer)
pipeline-factory/             Pipeline generator CLI (Phase 2.2)
code-intake/                  Validators + manifest signer (Phase 2.3)
scoring-engine/  pir-engine/  Phases 3 / 4
terraform/
├── modules/                  reusable modules (landing-zone, s3-replication-*, kms-hierarchy, iam-federation, pipeline-registry)
├── envs/{dev,stg,prod}/      per-env stacks calling the modules
└── account-bootstrap/        account-singleton resources (CloudTrail, GuardDuty, ...)
.github/workflows/            CI (terraform-validate, python-validate)
```

### 9.2 Terraform conventions

- Modules expose `versions.tf / variables.tf / main.tf / outputs.tf / README.md` + `tests/<name>.tftest.hcl`.
- Tests are **plan-validate with `mock_provider "aws"`** — no creds, no apply.
- Per-data-class workload keys are **module-owned** (ADR-0005); `kms-hierarchy` is only for audit-evidence keys.
- `terraform fmt -check -recursive` and `tflint` are enforced in CI (tflint requires variable/output descriptions and env-prefixed resource names).

### 9.3 Python conventions (set in Sprint 2.1)

- **uv** workspace (committed `uv.lock`) · **ruff** (lint + format) · **mypy --strict** · **pytest** (with `moto` for AWS).
- **JSON Schema is canonical**; never hand-edit the generated `platform-contracts/src/platform_contracts/models.py` — run `platform-contracts/regenerate-models.sh` and let CI's drift gate verify it.
- Common commands: `uv sync` · `uv run pytest` · `uv run ruff check .` · `uv run mypy platform-contracts/src registry/api/src`.

### 9.4 How we deliver work (the workflow)

We use a disciplined **brainstorm → spec → plan → execute → review** loop (the artifacts live in [`docs/superpowers/`](superpowers/)):

1. **Brainstorm** the sub-sprint, lock decisions, write a **design spec** (`specs/`).
2. Write a bite-sized, test-first **implementation plan** (`plans/`).
3. **Execute** task-by-task (TDD: failing test → minimal code → green → commit), with **two-stage review** (spec compliance, then code quality) after each task.
4. A **final whole-branch review**, then merge.

Conventional Commit subjects are enforced by CI. Branch per sub-sprint; squash/merge at the checkpoint gate.

---

## 10. Glossary

| Term | Meaning |
| --- | --- |
| **Track A / Track B** | Onboarding+Factory (one-time per model) / Scheduled scoring (recurring). |
| **PIR** | Post-Implementation Review — reconciling a scoring run against the developer's reference output. |
| **IVU** | Independent Validation Unit — independent model challenge/validation evidence (SR 11-7). |
| **CAB** | Change Advisory Board — risk/IT/business production sign-off. |
| **Industrialization Team** | EXL staff **onsite at ABSA** who package developer code for production (no logic changes). |
| **Pattern Z** | Account topology: 1 ABSA account (3 env source buckets) → 3 EXL env accounts. |
| **RTC** | S3 Replication Time Control — the 15-minute replication SLA. |
| **Model-ready data** | Curated data with no raw identifiers — the only data allowed to cross to EXL. |
| **plan-validate** | Terraform validated via `terraform test` (plan only, mock providers) — no real `apply` yet. |
| **GMRMG** | ABSA Group Model Risk Management Guidance. |

---

## 11. References

- Architecture (authoritative): [`docs/architecture.md`](architecture.md)
- Decisions: [`docs/adr/`](adr/) (ADR-0001 … 0007)
- Compliance control matrix: [`docs/compliance/control-matrix.md`](compliance/control-matrix.md)
- Sprint specs & plans: [`docs/superpowers/specs/`](superpowers/specs/), [`docs/superpowers/plans/`](superpowers/plans/)
- Engagement brief: [`CLAUDE_CODE_BRIEF.md`](../CLAUDE_CODE_BRIEF.md)
- Proposal deck: `ABSA_EXL_Model_Hosting_Proposal_v3.0.pptx`
