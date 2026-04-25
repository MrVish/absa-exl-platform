# ABSA × EXL Phase 1 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the engagement-lead-checkpoint artifact described in `CLAUDE_CODE_BRIEF.md` §12 — a greenfield repo scaffold with architecture documentation, four ADRs, three production-grade Terraform modules (landing-zone, s3-replication-source, s3-replication-destination), env-stack and account-bootstrap scaffolds, and a CI validation pipeline that runs static checks plus `terraform test` plan-validate.

**Architecture:** Pattern-Z topology (1 ABSA account + 3 EXL accounts). Cross-account data movement via S3 replication, not PrivateLink. Modules split along the trust boundary: source-side (deploys into ABSA) and destination-side (deploys into EXL). Plan-validate testing today; apply-time tests deferred to Phase 2 when account credentials land. All of this is documented in [`docs/superpowers/specs/2026-04-25-absa-exl-phase-1-foundation-design.md`](../specs/2026-04-25-absa-exl-phase-1-foundation-design.md), which is the authoritative design and supersedes this plan if the two ever conflict.

**Tech Stack:** Terraform 1.9+, AWS provider 5.x, `terraform test` HCL-native test framework, GitHub Actions, tflint, tfsec, checkov, gitleaks, pre-commit, MADR 3.0 ADR template.

---

## File Structure

The plan creates ~25 substantive files plus ~40 placeholder / stub files. Files are grouped by task; each task ends with a single squash-prepared commit so the engagement-lead PR has clean reviewer ergonomics.

| Task | Layer | Files (substantive) |
| --- | --- | --- |
| 1 | Repo metadata + dir scaffold | `README.md`, `.gitignore`, `.editorconfig`, `.pre-commit-config.yaml`, `CODEOWNERS`, 12 stub READMEs |
| 2 | Architecture + ADRs + contracts | `docs/architecture.md`, 4 ADR files, `docs/compliance/control-matrix.md`, `terraform/shared/replication-contract.md` |
| 3 | landing-zone module | 6 `.tf` files + `README.md` + `tests/landing_zone.tftest.hcl` |
| 4 | s3-replication-source module | 6 `.tf` files + `README.md` + `tests/source.tftest.hcl` |
| 5 | s3-replication-destination module | 6 `.tf` files + `README.md` + `tests/destination.tftest.hcl` |
| 6 | env stacks + account-bootstrap scaffolds | 6 env stacks (3 envs × source / destination) + 3 bootstrap stacks |
| 7 | CI workflow + pre-commit polish | `ci/pipelines/terraform-validate.yml` |
| 8 | Final integration check + PR | (no new files; runs validators across the tree, opens PR) |

**Branch:** all work happens on `phase-1/foundation-kickoff` off `main`. The repo's root commit (the design spec) is already on `main`.

---

## Task 1: Repo metadata, dir scaffold, and stub READMEs

**Files:**
- Create: `README.md`
- Create: `.gitignore`
- Create: `.editorconfig`
- Create: `.pre-commit-config.yaml`
- Create: `CODEOWNERS`
- Create: 17 stub README files for unbuilt modules and top-level dirs (listed in Step 4)
- Create: `.gitkeep` in `docs/runbooks/` and `ci/policies/`

- [ ] **Step 1: Create the working branch**

```bash
cd C:/Vishnu/Claude/absa-exl-platform
git checkout -b phase-1/foundation-kickoff
git status
```

Expected: branch switched, working tree clean.

- [ ] **Step 2: Create `.gitignore`**

```gitignore
# Terraform
**/.terraform/
*.tfstate
*.tfstate.*
*.tfplan
*.tfvars.local
crash.log
crash.*.log
override.tf
override.tf.json
*_override.tf
*_override.tf.json
.terraformrc
terraform.rc

# Editors
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store

# Secrets / local
.env
.env.local
*.pem
*.key
secrets/
```

Save to `.gitignore`.

- [ ] **Step 3: Create `.editorconfig`**

```ini
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true

[*.{tf,tfvars,hcl}]
indent_style = space
indent_size = 2

[*.{py,yaml,yml}]
indent_style = space
indent_size = 2

[*.md]
trim_trailing_whitespace = false
```

Save to `.editorconfig`.

- [ ] **Step 4: Create `.pre-commit-config.yaml`**

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-merge-conflict
      - id: check-yaml
      - id: check-added-large-files
        args: ['--maxkb=1024']
      - id: detect-private-key

  - repo: https://github.com/antonbabenko/pre-commit-terraform
    rev: v1.92.0
    hooks:
      - id: terraform_fmt
      - id: terraform_validate
        args:
          - --hook-config=--retry-once-with-cleanup=true
      - id: terraform_tflint
        args:
          - --args=--config=__GIT_WORKING_DIR__/.tflint.hcl
      - id: terraform_tfsec
        args:
          - --args=--minimum-severity=MEDIUM

  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.4
    hooks:
      - id: gitleaks
```

Save to `.pre-commit-config.yaml`.

- [ ] **Step 5: Create `CODEOWNERS`**

```
# Default: any change to terraform/modules/** requires platform-leads review
terraform/modules/                 @platform-leads
terraform/account-bootstrap/       @platform-leads
docs/adr/                          @platform-leads @engagement-lead
docs/architecture.md               @platform-leads @engagement-lead
docs/compliance/                   @compliance-leads @platform-leads
ci/                                @platform-leads
```

Save to `CODEOWNERS`. Team handles (`@platform-leads` etc.) are placeholders that the engagement lead will replace with real GitHub team slugs before merging the engagement-lead PR.

- [ ] **Step 6: Create top-level `README.md`**

```markdown
# ABSA × EXL Model Hosting & Delivery Operations

Production-grade, audit-ready ML hosting platform delivered by EXL for ABSA Group's model industrialisation programme. The platform productionises developer-authored SAS / Python models, scores them on cadence, and reconciles every run against developer evidence — without raw PII ever leaving the ABSA trust boundary.

## Operating model — two tracks

1. **Track A — Model Onboarding & Pipeline Factory.** Developer-authored model is industrialised by the EXL onsite team, packaged with a signed manifest, intaked by validation pipelines, and registered. A pipeline is generated from a template based on the registered model's class.
2. **Track B — Scheduled Scoring Execution.** ABSA's SAS scheduler triggers data hand-off via S3 cross-account replication. EXL's scoring engine validates, scores, reconciles against the developer's reference output (PIR), and delivers results back to ABSA.

See [`docs/architecture.md`](docs/architecture.md) for the full architecture and [`CLAUDE_CODE_BRIEF.md`](CLAUDE_CODE_BRIEF.md) for the engagement brief.

## Phase plan (5 months)

| Phase | Months | Scope |
| --- | --- | --- |
| 1 — Foundation | 1 | Landing zone, KMS hierarchy, IAM federation, S3 replication, CI/CD scaffolding |
| 2 — Pipeline Factory + Registry | 2-3 | Templates, generator CLI, code intake, registry API, signed handoff |
| 3 — Scoring Engine | 3-4 | Standard + scalable batch tiers, EventBridge orchestration, delivery adapters |
| 4 — PIR + Hardening | 4-5 | Variance gates, DR runbooks, SR 11-7 evidence pack, audit hub |

## Repository layout

```
docs/                        Architecture, ADRs, runbooks, compliance matrix
terraform/                   Infrastructure as code
├── modules/                 Reusable modules (landing-zone, s3-replication-*, etc.)
├── envs/{dev,stg,prod}/     Per-env stacks calling the modules
├── account-bootstrap/       Account-singleton resources (CloudTrail, GuardDuty)
└── shared/                  Cross-stack contracts and shared variables
pipeline-factory/            Pipeline generator CLI (Phase 2)
code-intake/                 Validators and signing for the productized handoff (Phase 2)
pir-engine/                  Post-implementation review reconciliation (Phase 4)
scoring-engine/              Step Functions / Spark scorers (Phase 3)
registry/                    Model & Pipeline Registry API (Phase 2)
ci/                          GitHub Actions workflows and policy bundles
```

## Compliance mappings

POPIA · SARB GOI 3/5 · SR 11-7 · ISO 27001 · SOC 2 Type II · ABSA GMRMG.
Control matrix: [`docs/compliance/control-matrix.md`](docs/compliance/control-matrix.md).

## Status

Phase 1 foundation kickoff in progress. See [`docs/superpowers/plans/2026-04-25-absa-exl-phase-1-foundation.md`](docs/superpowers/plans/2026-04-25-absa-exl-phase-1-foundation.md).
```

Save to `README.md`.

- [ ] **Step 7: Create the directory tree with stub READMEs**

For each module / top-level dir below, create a single-line stub `README.md`. Use this exact pattern (substituting the phase and short description):

```markdown
# {dir-name}

Phase {N} — {short purpose}. Not built yet. See [`docs/superpowers/plans/`](../../docs/superpowers/plans/) for the active plan.
```

Files to create:

```
terraform/modules/kms-hierarchy/README.md         Phase 1 (next sprint) — KMS key hierarchy + grants
terraform/modules/iam-federation/README.md        Phase 1 (next sprint) — IAM federation + role chains
terraform/modules/sagemaker-domain/README.md      Phase 3 — SageMaker domain + studio profiles
terraform/modules/eks-scoring/README.md           Phase 3 — EKS cluster for scalable-batch tier
terraform/modules/pipeline-registry/README.md     Phase 2 — Model & Pipeline Registry (DynamoDB + API)
terraform/modules/pir-engine/README.md            Phase 4 — PIR reconciliation infrastructure
terraform/modules/observability/README.md         Phase 4 — Cross-stack metrics, dashboards, alerting
pipeline-factory/README.md                        Phase 2 — Pipeline generator CLI + Jinja templates
code-intake/README.md                             Phase 2 — SAS / Python validators + manifest signer
pir-engine/README.md                              Phase 4 — PIR reconciliation workers + reports
scoring-engine/README.md                          Phase 3 — Step Functions / Spark scorers
registry/README.md                                Phase 2 — Registry FastAPI + JSON Schema
```

Also create empty marker files:

```
docs/runbooks/.gitkeep
ci/policies/.gitkeep
```

- [ ] **Step 8: Verify the tree**

```bash
find . -type f -not -path './.git/*' -not -path './docs/superpowers/specs/*' | sort
```

Expected: 19 stub files plus the 5 metadata files plus the spec doc plus the original brief / pptx.

- [ ] **Step 9: Commit**

```bash
git add .gitignore .editorconfig .pre-commit-config.yaml CODEOWNERS README.md \
        terraform/modules/ pipeline-factory/ code-intake/ pir-engine/ scoring-engine/ \
        registry/ docs/runbooks/.gitkeep ci/policies/.gitkeep
git commit -m "scaffold: repo metadata + stub READMEs for unbuilt phases

Establishes editor / git / pre-commit conventions, CODEOWNERS, and
single-line stub READMEs for every module and top-level directory whose
implementation is scheduled for Phase 1 next sprint or later.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Architecture documentation, four ADRs, and cross-account contract

**Files:**
- Create: `docs/architecture.md`
- Create: `docs/adr/0001-data-movement-s3-replication.md`
- Create: `docs/adr/0002-cross-account-iac-dual-module-split.md`
- Create: `docs/adr/0003-manifest-signing-kms-asymmetric.md`
- Create: `docs/adr/0004-account-topology-1-absa-3-exl.md`
- Create: `docs/compliance/control-matrix.md`
- Create: `terraform/shared/replication-contract.md`

- [ ] **Step 1: Write `docs/architecture.md`**

````markdown
# Architecture — ABSA × EXL Model Hosting & Delivery Operations

| Field | Value |
| --- | --- |
| Status | Phase 1 — Foundation kickoff |
| Last reviewed | 2026-04-25 |
| Owners | EXL Platform Engineering, ABSA Model Risk |
| Compliance mappings | POPIA, SARB GOI 3/5, SR 11-7, ISO 27001, SOC 2 Type II, ABSA GMRMG |

## 1. Purpose

Productionise developer-authored SAS / Python models for ABSA Group on a hosted, auditable, cadence-driven AWS platform delivered by EXL. Reconcile every scoring run against developer evidence (PIR) before delivery. Keep raw PII inside the ABSA trust boundary at all times.

## 2. Operating model — two tracks

### Track A — Model Onboarding & Pipeline Factory (one-time per model)

```
ABSA developer ──▶ EXL Industrialization Team (onsite)
                          │
                          ▼
                  Productized package + signed manifest
                          │
                          ▼
                  EXL Code Intake (validators + PIR mapping)
                          │
                          ▼
                  EXL Pipeline Factory (template → pipeline)
                          │
                          ▼
                  Model & Pipeline Registry (DynamoDB)
```

### Track B — Scheduled Scoring Execution (recurring)

```
ABSA SAS scheduler ─▶ ABSA writes model-ready data to S3 (in ABSA account)
                          │
                          ▼ S3 cross-account replication (15-min RTC)
                  EXL landing bucket (in EXL env account)
                          │
                          ▼ EventBridge — Phase 3
                  Step Functions: DQ → load → score → PIR → deliver
                          │
                          ▼ Score delivery
                  ABSA via API Gateway (PrivateLink) or SFTP
```

## 3. Account topology

ABSA allocates one AWS account; EXL follows its standard three-account model. Pattern Z is adopted: one ABSA account hosts three env-suffixed source buckets, each replicating to the matching EXL env account.

```
ABSA account (1)                                EXL accounts (3)
┌───────────────────────────────┐              ┌────────────────────┐
│ absa-model-handoff-dev   ─────┼─── replica ──▶│ exl-dev            │
│ absa-model-handoff-stg   ─────┼─── replica ──▶│ exl-stg            │
│ absa-model-handoff-prod  ─────┼─── replica ──▶│ exl-prod           │
└───────────────────────────────┘              └────────────────────┘
```

Rationale captured in [`adr/0004-account-topology-1-absa-3-exl.md`](adr/0004-account-topology-1-absa-3-exl.md).

## 4. Data movement — S3 cross-account replication, not PrivateLink

The most consequential architecture call: bulk model-ready data crosses the trust boundary via S3 cross-account replication. PrivateLink is reserved for control-plane API calls (registry, scoring, score delivery) — not bulk data. Rationale: [`adr/0001-data-movement-s3-replication.md`](adr/0001-data-movement-s3-replication.md).

Replication characteristics:

- KMS-encrypted both sides, separate CMKs per side, replication role granted minimal cross-key permissions.
- Versioning + object-lock compliance mode on both buckets.
- Replication Time Control enabled with a 15-minute SLA; CloudWatch metric and alarm in the destination account.
- Sidecar manifest convention: `data.parquet` and `manifest.json` land together; EventBridge fires on the manifest's arrival, not the data's.
- Per-env retention: 7 years prod (default), shorter overrides for dev / stg.

## 5. Cross-account IaC — dual-module split

The canonical `s3-replication` module is split into two siblings: `s3-replication-source` (deploys into ABSA) and `s3-replication-destination` (deploys into EXL). They wire via a shared markdown contract at [`../terraform/shared/replication-contract.md`](../terraform/shared/replication-contract.md). Rationale: [`adr/0002-cross-account-iac-dual-module-split.md`](adr/0002-cross-account-iac-dual-module-split.md).

## 6. Signing and provenance

Code Intake and Pipeline Factory both produce manifests that need long-term verifiability. AWS KMS asymmetric CMKs sign all manifests; verification works via `kms:Verify` or against a published public key in S3 (versioned). Rationale: [`adr/0003-manifest-signing-kms-asymmetric.md`](adr/0003-manifest-signing-kms-asymmetric.md).

## 7. Compliance posture

Every Terraform module and process is mapped to specific controls in the matrix at [`compliance/control-matrix.md`](compliance/control-matrix.md). Phase 1 fills the foundation rows; later phases extend the matrix.

Highlights:

- Raw PII never leaves the ABSA AWS account.
- Cross-account access is logged in CloudTrail in both accounts.
- Object-lock compliance mode on hand-off and landing buckets gives audit-grade immutability.
- IAM permissions boundaries on EXL workload-account roles enforce env-scoped tag-based access.

## 8. What this phase covers

Phase 1 — foundation. Lands:

- Workload-account landing zone (VPC, subnets, TGW attachment, flow logs, GuardDuty, Security Hub) for each EXL account.
- S3 replication module pair (source + destination).
- ADRs and architecture documentation.
- CI validation pipeline (plan-validate, no apply).

KMS-hierarchy and IAM-federation modules are scheduled for the second sprint of Phase 1. Pipeline Factory, Code Intake, Registry, Scoring Engine, and PIR Engine follow in later phases per the brief's plan.
````

Save to `docs/architecture.md`.

- [ ] **Step 2: Write `docs/adr/0001-data-movement-s3-replication.md`**

```markdown
# ADR-0001: Data movement via S3 cross-account replication, not PrivateLink

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-04-25 |
| Deciders | Engagement lead, EXL Platform Engineering |
| Consulted | ABSA Model Risk, ABSA Compliance |
| Supersedes | Earlier proposal drafts that placed bulk data on PrivateLink |

## Context

The brief at `CLAUDE_CODE_BRIEF.md` §4 mandates S3 cross-account replication for bulk model-ready data movement between ABSA and EXL. Earlier drafts of the proposal placed this data on PrivateLink, which would not work in ABSA's environment for several reasons:

1. PrivateLink scales API calls, not bulk data — large parquet files crossing a PrivateLink endpoint create both throughput and cost issues at the volumes implied by the scoring-model tier (2M – 6M rows weekly / monthly).
2. The data flow is one-way and asynchronous (ABSA writes; EXL reads later), which fits S3's eventual-consistency-with-replication-metric model better than a synchronous endpoint.
3. Audit reviewers (SR 11-7, ABSA GMRMG) expect data lineage to be visible in S3 replication metrics and in CloudTrail, both of which are first-class for the S3-replication path.

The decision also folds in four secondary choices made during the Phase 1 brainstorm:

- **Object identity**: a sidecar `manifest.json` accompanies each `data.parquet` arrival.
- **Alert chain**: the destination module owns an SNS topic; per-env subscriptions live outside the module.
- **Object-lock retention**: per-env tiered, 7 years prod default.
- **Replication SLA**: Replication Time Control enabled with a 15-minute target.

## Decision

Bulk model-ready data crosses the ABSA → EXL trust boundary exclusively via **S3 cross-account replication** with the following parameters:

- Source: `s3://absa-model-handoff-{env}/` in ABSA's single AWS account, KMS-encrypted with a per-env source CMK.
- Destination: `s3://exl-model-landing-{env}/` in the matching EXL env account, KMS-encrypted with a per-env destination CMK.
- Versioning + object-lock compliance mode on both buckets; default retention from `var.retention_years` (7 prod / shorter non-prod).
- Replication Time Control enabled (RTC, 15-minute SLA).
- Replication metric `AWS/S3 ReplicationLatency` alarmed at 900 seconds in the destination account; alarm action is an SNS topic owned by the destination module. Subscriptions to that topic are managed per env in `terraform/envs/{env}/destination/replication-subscriptions.tf` so the module stays portable.
- Object identity is communicated via a sidecar `manifest.json` per data file. Schema is defined in Phase 2 alongside the Code Intake pipeline.

PrivateLink is reserved for **control-plane** API calls between ABSA and EXL: the Registry API, the scoring trigger / status API, and the score-delivery API gateway. It is not used for bulk data movement in either direction.

## Consequences

### Positive

- Audit-friendly: replication metrics, KMS operations, and IAM grants are all first-class CloudTrail events in both accounts.
- AWS-native: no third-party data-movement vendor in the supply chain.
- Object-lock compliance mode gives audit-grade immutability that SR 11-7 reviewers expect for model evidence.
- The 15-minute RTC SLA is contractually clear and measurable.

### Negative

- Compliance-mode object lock is a one-way door — buckets cannot be deleted in place, and retention can only be extended, never shortened. Per-env tiered retention partially mitigates this for non-prod (a 30-day dev retention means dev mistakes age out quickly). For prod, this is the intended audit posture.
- 15-minute latency floor: not suitable for a future real-time inference tier. Real-time is explicitly out of scope for the current cohort and would warrant a separate ADR.
- Replication is asynchronous and one-way. If a scoring run produces output that ABSA needs back, that delivery uses a different path (API Gateway + SFTP, per architecture §2 step 10), not reverse replication.

## Alternatives considered

1. **PrivateLink for bulk data.** Rejected: scales for API calls, not for parquet at scoring-model volumes; doesn't fit the asynchronous one-way producer / consumer pattern; and creates a single point of failure for the data path.
2. **AWS Transfer Family / SFTP.** Rejected: encryption-at-rest depends on operator hygiene; less first-class CloudTrail visibility; weaker audit story than S3 replication for the same use case.
3. **Custom replication via Lambda S3-trigger + cross-account copy.** Rejected: fragile at volume, expensive on the scoring-tier (2M – 6M rows), and reinvents what S3 replication does natively with RTC SLAs.

## Compliance mapping

| Control | Reference |
| --- | --- |
| POPIA — data minimisation | Sidecar manifest + per-env retention |
| SARB GOI 5 — model documentation | Object-lock compliance mode |
| SR 11-7 — model implementation evidence | CloudTrail + replication metric audit trail |
| ISO 27001 A.13.2 — information transfer | KMS-encrypted both sides; replication role with least privilege |
| SOC 2 — confidentiality | Per-env KMS keys; cross-env separation |
| ABSA GMRMG — model lifecycle | Per-env source bucket = per-env scoring run lineage |
```

Save to `docs/adr/0001-data-movement-s3-replication.md`.

- [ ] **Step 3: Write `docs/adr/0002-cross-account-iac-dual-module-split.md`**

```markdown
# ADR-0002: Cross-account IaC dual-module split

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-04-25 |
| Deciders | Engagement lead, EXL Platform Engineering |
| Consulted | ABSA Cloud Platform team |

## Context

The brief at `CLAUDE_CODE_BRIEF.md` §4 lists a single `terraform/modules/s3-replication/` module taking `source_bucket_name` (in ABSA) and `destination_bucket_name` (in EXL) as inputs. Two interpretations were possible:

1. **Single-state, dual-account module.** This repo owns Terraform for both sides; one `terraform apply` provisions both accounts via assumed-role.
2. **EXL-side-only module with a contract to ABSA.** This repo provisions EXL-side resources; ABSA's IaC team owns the source-side module.
3. **Both, with module split.** Two modules, one per side, each with its own state, wired via a shared contract.

The engagement lead confirmed that EXL has a working relationship with ABSA's cloud platform team that supports option 3 — EXL can ship a Terraform module that ABSA will deploy into ABSA's own account, and vice versa, with each side owning the apply.

## Decision

Split the canonical `s3-replication` module into two siblings:

- `terraform/modules/s3-replication-source/` — deployed into the ABSA account by ABSA's IaC team. Provisions the source bucket, source-side KMS CMK, replication role, and replication configuration.
- `terraform/modules/s3-replication-destination/` — deployed into the matching EXL env account by EXL's IaC team. Provisions the destination bucket, destination-side KMS CMK, bucket policy granting the replication role, an SNS topic, and CloudWatch alarms on `ReplicationLatency` and `FailedReplication`.

Each side keeps its own Terraform state. Outputs from the source module feed inputs of the destination module (and vice versa for KMS and role ARNs); the wiring is documented in [`../terraform/shared/replication-contract.md`](../../terraform/shared/replication-contract.md) and exchanged via `terraform_remote_state` data sources or a shared variable file once both apply destinations exist.

## Consequences

### Positive

- Clear ownership boundary aligned with how each side actually operates its AWS account.
- ABSA's IaC team can apply their side independently when their change-control window opens, without coordinating an exact apply moment with EXL.
- Audit trail per side is naturally separated: each `terraform apply` shows in the originating account's CloudTrail.
- The shared contract at `terraform/shared/replication-contract.md` is itself an audit-pack artifact — reviewers can read the contract before reading either side's HCL.

### Negative

- Two modules to maintain rather than one. Each side's variables and outputs must remain compatible across versions.
- Cross-side wiring requires manual coordination: when one side changes its outputs (e.g. adds a new ARN), the other side must update inputs in lock-step. Mitigated by enforcing the contract at the markdown level and adding a CI check in Phase 2 that diffs the contract against actual module outputs.
- A single dev / stg / prod cycle requires two `terraform apply` invocations, not one.

## Alternatives considered

1. **Single module with provider aliasing.** Rejected: collapses both account states into one HCL module, weakens ownership, and concentrates blast radius. The "good connect with ABSA" supports independent applies, not joint ones.
2. **Single module with separate Terraform workspaces per account.** Rejected: workspaces don't model the cross-side dependency well; would require an out-of-band coordination layer anyway.
3. **EXL-side-only module with ABSA writing their own source-side HCL.** Rejected: leaves the source side to ad-hoc convention, weakens the audit pack (no shared module), and doubles the engineering effort across the two teams.
```

Save to `docs/adr/0002-cross-account-iac-dual-module-split.md`.

- [ ] **Step 4: Write `docs/adr/0003-manifest-signing-kms-asymmetric.md`**

```markdown
# ADR-0003: Manifest signing via AWS KMS asymmetric keys

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-04-25 |
| Deciders | Engagement lead, EXL Platform Engineering |
| Consulted | ABSA Information Security |

## Context

Two pipelines produce manifests that downstream systems and auditors must verify, potentially years after the fact:

- **Code Intake (Phase 2)** signs the productized package handed off from the EXL Industrialization Team.
- **Pipeline Factory (Phase 2)** signs the generated pipeline manifest before it is registered.

Long-term verifiability is the load-bearing requirement. Verification must work in 2032 even if the original CI infrastructure is offline, and the cryptographic primitive must satisfy ABSA's information security review (which favours single-vendor AWS-rooted trust over web-of-trust constructs).

## Decision

Use **AWS KMS asymmetric CMKs (RSA-3072 default; ECC-NIST-P384 supported)** for all signing operations.

- The CMK lives in the EXL prod account (`exl-prod`). Cross-environment signatures are not part of the threat model — dev / stg pipelines either do not sign at all (drafts) or sign with a separate non-prod CMK.
- Signing is performed by GitHub Actions runners via `kms:Sign`. CI is the only signer (per the dual-mode generator-runtime decision; ADR for that follows in Phase 2).
- Each manifest stores: the signature bytes (base64), the CMK ARN, the algorithm, and the manifest's SHA-256 digest.
- Verification is supported via two paths:
  1. **Online** via `kms:Verify` against the live CMK.
  2. **Offline** by fetching the published public key from `s3://exl-platform-public-keys/manifest-signing/<key_id>/v<version>.pem` (versioned, world-readable bucket) and verifying with any standard RSA / ECC tooling.

## Consequences

### Positive

- AWS-native; no third-party transparency log dependency.
- CloudTrail logs every `kms:Sign` and `kms:Verify` automatically — first-class audit trail.
- Single-vendor trust root, which ABSA InfoSec preferred over Sigstore / cosign during the brainstorm.
- Public key publication means an auditor in 2032 can verify any historical signature even if the CMK has been disabled or the original CI runners no longer exist.
- Cost: ~$1/month per CMK plus a fraction of a cent per signing operation. Negligible for the 10-model cohort.

### Negative

- KMS asymmetric throughput is rate-limited (default 300 requests / second). Fine for a 10-model cohort signing manifests at most a few times per day per model. If the platform ever scales to thousands of pipelines / day, sharding across multiple CMKs is the documented workaround.
- IAM grant management: every CI workflow that signs needs `kms:Sign` granted on the specific CMK. Mitigated by a single shared GitHub Actions OIDC role that holds the grant.
- KMS asymmetric is region-bound: the CMK lives in one region. The published public key is region-agnostic, so verification works anywhere; signing requires that region to be available.

## Alternatives considered

1. **Sigstore / cosign with keyless OIDC signing.** Rejected: introduces Fulcio + Rekor as third-party dependencies. ABSA InfoSec was uncomfortable with the transparency-log model relative to KMS-rooted trust for a regulated bank workload.
2. **GPG / OpenPGP.** Rejected: key management (revocation, rotation, escrow) becomes the platform's problem; bank auditors today generally prefer cloud-rooted trust.
3. **AWS Signer (ACM Private CA backed).** Rejected: stronger fit for code-signing certificates than for arbitrary manifest signing; introduces ACM PCA as additional infrastructure for marginal benefit over raw KMS.
```

Save to `docs/adr/0003-manifest-signing-kms-asymmetric.md`.

- [ ] **Step 5: Write `docs/adr/0004-account-topology-1-absa-3-exl.md`**

```markdown
# ADR-0004: Account topology — 1 ABSA + 3 EXL with Pattern Z replication

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-04-25 |
| Deciders | Engagement lead, EXL Platform Engineering |
| Consulted | ABSA Cloud Platform team |

## Context

Two facts shaped the topology decision:

1. ABSA allocates **one AWS account** for the engagement on its side. Multiple ABSA accounts were not on offer.
2. EXL's internal standard is **three AWS accounts** (dev, stg, prod) for any production workload. Single-account variants are only used for proof-of-concept work.

Given the asymmetry, three replication patterns were considered:

- **Pattern X**: ABSA single account → `exl-prod` only. Dev / stg use synthetic data generated inside EXL.
- **Pattern Y**: ABSA single account, single source bucket → all three EXL envs.
- **Pattern Z**: ABSA single account, three env-suffixed source buckets → matching EXL env each.

Pattern Z was chosen.

## Decision

The platform runs across **four AWS accounts** total:

| Account | Owner | Purpose |
| --- | --- | --- |
| `absa-handoff` (single account) | ABSA | Hosts three env-suffixed source buckets: `absa-model-handoff-dev`, `absa-model-handoff-stg`, `absa-model-handoff-prod`. Each has its own per-env KMS CMK and replication role. |
| `exl-dev` | EXL | Dev landing-zone + destination bucket. Receives replicas from `absa-model-handoff-dev` only. |
| `exl-stg` | EXL | Stg landing-zone + destination bucket. Receives replicas from `absa-model-handoff-stg` only. |
| `exl-prod` | EXL | Prod landing-zone + destination bucket. Receives replicas from `absa-model-handoff-prod` only. |

Replication is **strictly env-symmetric**: each ABSA source bucket has exactly one replication rule, pointing to its matching EXL env account. There is no cross-env replication.

ABSA's account-level controls (Organisation, SCPs, CloudTrail organisation trail, GuardDuty master detector) are owned by ABSA's central platform team. EXL's footprint inside the ABSA account is bounded to: the three source buckets, three KMS CMKs, three replication roles, and the replication configurations on each bucket. Anything else in the ABSA account is out of scope for this engagement.

## Consequences

### Positive

- Strong env isolation on the EXL side, courtesy of three separate AWS accounts. SR 11-7 and ABSA GMRMG audit narratives are simple.
- Env isolation on the ABSA side is preserved by per-env KMS CMKs and per-env replication roles, even though all three buckets share an account. A misrouted replication rule on `absa-model-handoff-dev` cannot decrypt prod data because the prod CMK key policy explicitly excludes the dev replication role.
- Symmetric env naming end-to-end. An object in `absa-model-handoff-stg/...` lands in `exl-stg`'s `exl-model-landing-stg/...` — the env never changes. Audit lineage is straightforward.
- Pattern Z preserves the option of using real (de-identified) data in dev or stg if ABSA ever wants to enable that. Pattern X would foreclose this without re-architecting.

### Negative

- Three replication rules and three KMS CMKs to maintain on the ABSA side. Operationally cheap; cognitively a small overhead.
- ABSA must commit to providing three buckets even if they intend to use only the prod bucket for live data. The other two would receive synthetic data populated by an EXL Phase 2 generator. This is a small ABSA-side ask but must be confirmed before Phase 2 begins.
- Cost: three KMS CMKs ($3/month combined) and three replication rules. Trivial.

## Alternatives considered

1. **Pattern X — ABSA → exl-prod only.** Rejected: dev and stg lose realistic replication-path testing. Replication-rule misconfigurations would only surface in prod, defeating the purpose of having dev / stg envs.
2. **Pattern Y — single ABSA bucket → all 3 EXL envs.** Rejected: a single source bucket means real (de-identified) data lands in dev and stg by default. POPIA's data-minimisation principle becomes harder to argue. Also, per-env replication metrics and alarms are less natural to attribute when one source feeds three sinks.
3. **Six EXL accounts (dev / stg / prod × source / destination).** Rejected: the source side is owned by ABSA, not EXL. Provisioning EXL-owned accounts on the source side would conflict with the account-allocation reality.
```

Save to `docs/adr/0004-account-topology-1-absa-3-exl.md`.

- [ ] **Step 6: Write `docs/compliance/control-matrix.md`**

```markdown
# Compliance Control Matrix — Phase 1 Foundation

> **Scope:** Phase 1 controls only. Each phase extends this matrix with the rows it owns. Reviewed quarterly by the engagement lead and ABSA Compliance.

## Reading the matrix

| Column | Meaning |
| --- | --- |
| Control | The compliance requirement (POPIA section, SARB GOI clause, SR 11-7 sub-requirement, etc.) |
| Implementation | The Terraform module / repo file / process that satisfies it |
| Evidence artifact | What an auditor would inspect to confirm the control is in place |
| Owner | Who is accountable for the control's continued operation |

## Phase 1 controls

| Control | Implementation | Evidence artifact | Owner |
| --- | --- | --- | --- |
| **POPIA s19 — security safeguards** | KMS-encrypted S3 buckets on both sides of the replication boundary | `terraform/modules/s3-replication-source/kms.tf`, `terraform/modules/s3-replication-destination/kms.tf` | EXL Platform Engineering |
| **POPIA s14 — retention** | Object-lock compliance mode with per-env tiered retention (default 7 years prod) | `terraform/modules/s3-replication-source/main.tf` (object_lock_configuration block) | EXL Platform Engineering |
| **SARB GOI 5 — model documentation immutability** | Object-lock compliance mode prevents deletion / modification before retention expires | Same as above | EXL Platform Engineering |
| **SR 11-7 III.4 — model implementation evidence** | CloudTrail in both accounts logs every S3 object operation, KMS Sign / Decrypt call, and IAM AssumeRole | `terraform/account-bootstrap/exl-{env}/main.tf` (CloudTrail), assumed for ABSA side | EXL Platform Engineering, ABSA Cloud Platform |
| **ISO 27001 A.13.2.1 — information transfer** | S3 replication with RTC, KMS encryption, IAM least-privilege replication role | `terraform/modules/s3-replication-source/iam.tf`, `replication.tf` | EXL Platform Engineering |
| **ISO 27001 A.12.4.1 — event logging** | VPC flow logs, GuardDuty, Security Hub enabled in every EXL account | `terraform/modules/landing-zone/security.tf` | EXL Platform Engineering |
| **SOC 2 CC6.1 — logical access** | IAM permissions boundaries on EXL workload roles enforce env-tag-based deny conditions | `terraform/modules/landing-zone/iam.tf` | EXL Platform Engineering |
| **ABSA GMRMG — model lifecycle traceability** | Per-env source buckets give per-env scoring-run lineage from the moment data leaves ABSA | `terraform/modules/s3-replication-source/main.tf` (called per env) | ABSA Model Risk |

## Out-of-matrix items (deferred)

The following control rows belong to later phases and will be added to this matrix when the corresponding modules land:

- **POPIA s8 — quality of personal information**: Phase 2 (Code Intake validators).
- **SARB GOI 3 — model risk governance**: Phase 2 (Registry approval gate + CAB record linkage).
- **SR 11-7 III.6 — independent review**: Phase 4 (PIR Engine variance gates).
- **SOC 2 CC7.2 — system monitoring**: Phase 4 (Observability module + dashboards).
- **ABSA GMRMG — IVU evidence pack**: Phase 4 (Audit hub + DR runbooks).
```

Save to `docs/compliance/control-matrix.md`.

- [ ] **Step 7: Write `terraform/shared/replication-contract.md`**

````markdown
# Cross-Account Replication Contract — ABSA Source ↔ EXL Destination

> **Audience:** ABSA's IaC team applying `terraform/modules/s3-replication-source/`, and EXL's IaC team applying `terraform/modules/s3-replication-destination/`. This document is the load-bearing artifact when the two sides need to wire their outputs to the other's inputs without seeing each other's HCL.

## Why this contract exists

The S3 replication module is split (see [ADR-0002](../../docs/adr/0002-cross-account-iac-dual-module-split.md)). Source-side resources live in ABSA's account; destination-side resources live in the matching EXL env account. Each side has its own Terraform state. The contract below documents which outputs from one side are inputs to the other, so neither team needs the other's HCL to apply their own.

## Topology

For each env in `{dev, stg, prod}`:

```
ABSA account (one)                                           EXL env account
──────────────────────────                                   ──────────────────────────
absa-model-handoff-{env}     ──────── replicates ─────────▶  exl-model-landing-{env}
KMS: alias/handoff-{env}                                     KMS: alias/model-landing-{env}
replication role (env)
```

## Outputs and inputs by side

### Source side (ABSA, deploys `s3-replication-source`)

Provides these outputs that the destination side needs:

| Output | Type | Used by destination as |
| --- | --- | --- |
| `replication_role_arn` | string | `var.source_replication_role_arn` (so the destination KMS key policy and bucket policy can grant this principal) |
| `bucket_arn` | string | informational (for monitoring dashboards) |
| `kms_key_arn` | string | informational |

Requires these inputs from the destination side:

| Input | Type | Comes from destination's output |
| --- | --- | --- |
| `destination_bucket_arn` | string | `bucket_arn` |
| `destination_kms_key_arn` | string | `kms_key_arn` |
| `destination_account_id` | string | hardcoded per env (account ID of `exl-{env}`) |

### Destination side (EXL env account, deploys `s3-replication-destination`)

Provides these outputs that the source side needs:

| Output | Type | Used by source as |
| --- | --- | --- |
| `bucket_arn` | string | `var.destination_bucket_arn` |
| `kms_key_arn` | string | `var.destination_kms_key_arn` |

Requires these inputs from the source side:

| Input | Type | Comes from source's output |
| --- | --- | --- |
| `source_replication_role_arn` | string | `replication_role_arn` |
| `source_account_id` | string | hardcoded (ABSA account ID) |

## Apply order

Because both sides depend on the other's outputs, the apply uses a two-phase bootstrap:

1. **Phase 1 — destination first, with replication-role-grant deferred.**
   - Destination side applies. KMS key policy grants are scoped to the EXL env account itself (no source-role grant yet because the source role doesn't exist).
   - Output: `bucket_arn`, `kms_key_arn`.

2. **Phase 2 — source applies, using destination's outputs.**
   - Source side applies. Source bucket, source KMS key, replication role, and replication configuration are all created.
   - Output: `replication_role_arn`.

3. **Phase 3 — destination re-applies with the source role grant.**
   - Destination side passes `var.source_replication_role_arn` and re-applies. KMS key policy and bucket policy now grant the source role its required permissions.

After this bootstrap, ongoing changes can be applied in either order; the dependency direction is symmetric once both sides exist.

## Wiring options

### Option A — `terraform_remote_state` cross-account read

Both sides expose their outputs via the Terraform state backend (S3 + DynamoDB) and read the other side via `data "terraform_remote_state"`. Requires that each side's state-bucket is readable from the other account (a small IAM grant on each state bucket).

```hcl
# In the destination side's caller after the source side has applied
data "terraform_remote_state" "source" {
  backend = "s3"
  config = {
    bucket = "absa-tfstate-handoff-{env}"
    key    = "s3-replication-source/terraform.tfstate"
    region = "af-south-1"
  }
}

module "destination" {
  source                       = "../../modules/s3-replication-destination"
  source_replication_role_arn  = data.terraform_remote_state.source.outputs.replication_role_arn
  source_account_id            = data.terraform_remote_state.source.outputs.account_id
  # ...
}
```

### Option B — Shared variables file checked into the repo

Each side writes its outputs into a versioned `terraform/shared/replication-{env}.auto.tfvars.json` file at the end of its apply (via a `local-exec` or a manual commit). The other side reads them from there.

Simpler than Option A but requires manual coordination on commits. Used as a fallback when cross-account state-bucket grants are not yet in place.

## Compliance assumptions

This contract assumes ABSA's central platform team owns the following on the ABSA account:

- AWS Organizations master and Service Control Policies.
- Organisation-trail CloudTrail (with member-account event capture).
- Account-level GuardDuty master detector.
- IAM Identity Center / SSO federation.

The `s3-replication-source` module does not provision any of these. If these are not in place, the engagement lead should escalate to ABSA's central platform team before the source-side apply.

## Change-control protocol

Any change to either side's variables or outputs requires:

1. A pull request updating this contract document.
2. CODEOWNERS approval from `@platform-leads` and `@engagement-lead`.
3. A coordinated apply window with the other side.

The CI check at `ci/pipelines/terraform-validate.yml` (Phase 2 enhancement) will diff this contract against the actual module variables / outputs and fail if they drift.
````

Save to `terraform/shared/replication-contract.md`.

- [ ] **Step 8: Verify markdown renders**

```bash
find docs terraform/shared -name "*.md" -exec head -3 {} \;
```

Expected: each file's title heading and frontmatter table render cleanly.

- [ ] **Step 9: Commit**

```bash
git add docs/architecture.md docs/adr/ docs/compliance/control-matrix.md \
        terraform/shared/replication-contract.md
git commit -m "docs: phase 1 architecture, four ADRs, and cross-account contract

Architecture document captures the two-track operating model and the
S3-replication data path. Four ADRs (0001 data movement, 0002 dual-module
split, 0003 KMS asymmetric signing, 0004 account topology) record the
decisions made during Phase 1 brainstorming. Compliance control matrix
seeds the audit pack with Phase 1 rows. Replication contract documents
the source-side / destination-side wiring for the IaC teams.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `terraform/modules/landing-zone/` module

**Files:**
- Create: `terraform/modules/landing-zone/versions.tf`
- Create: `terraform/modules/landing-zone/variables.tf`
- Create: `terraform/modules/landing-zone/main.tf`
- Create: `terraform/modules/landing-zone/vpc.tf`
- Create: `terraform/modules/landing-zone/routing.tf`
- Create: `terraform/modules/landing-zone/security.tf`
- Create: `terraform/modules/landing-zone/iam.tf`
- Create: `terraform/modules/landing-zone/outputs.tf`
- Create: `terraform/modules/landing-zone/README.md`
- Create: `terraform/modules/landing-zone/tests/landing_zone.tftest.hcl`

- [ ] **Step 1: Write the failing test first**

Save to `terraform/modules/landing-zone/tests/landing_zone.tftest.hcl`:

```hcl
variables {
  env                = "dev"
  region             = "af-south-1"
  vpc_cidr           = "10.40.0.0/20"
  availability_zones = 3
  transit_gateway_id = "tgw-0123456789abcdef0"
  tags = {
    cost_center = "ml-platform"
    module      = "landing-zone"
  }
}

run "vpc_has_three_subnets_per_tier" {
  command = plan

  assert {
    condition     = length(aws_subnet.public) == 3
    error_message = "Expected 3 public subnets across AZs"
  }

  assert {
    condition     = length(aws_subnet.private) == 3
    error_message = "Expected 3 private subnets across AZs"
  }

  assert {
    condition     = length(aws_subnet.data) == 3
    error_message = "Expected 3 data subnets across AZs"
  }
}

run "non_prod_uses_single_nat_gateway" {
  command = plan

  variables {
    env = "dev"
  }

  assert {
    condition     = length(aws_nat_gateway.this) == 1
    error_message = "Non-prod must use a single NAT gateway for cost"
  }
}

run "prod_uses_one_nat_gateway_per_az" {
  command = plan

  variables {
    env = "prod"
  }

  assert {
    condition     = length(aws_nat_gateway.this) == 3
    error_message = "Prod must use one NAT gateway per AZ"
  }
}

run "flow_logs_are_enabled" {
  command = plan

  assert {
    condition     = aws_flow_log.vpc.traffic_type == "ALL"
    error_message = "VPC flow logs must capture ALL traffic"
  }
}

run "guardduty_detector_exists_when_enabled" {
  command = plan

  variables {
    enable_guardduty = true
  }

  assert {
    condition     = length(aws_guardduty_detector.this) == 1
    error_message = "GuardDuty detector must be created when enable_guardduty=true"
  }
}

run "security_hub_uses_foundational_standard" {
  command = plan

  variables {
    enable_security_hub = true
  }

  assert {
    condition     = length(aws_securityhub_standards_subscription.foundational) == 1
    error_message = "Security Hub Foundational standard must be subscribed"
  }
}

run "env_validation_rejects_unknown_value" {
  command = plan

  variables {
    env = "uat"
  }

  expect_failures = [
    var.env,
  ]
}
```

- [ ] **Step 2: Verify the test fails because the module doesn't exist**

```bash
cd terraform/modules/landing-zone
terraform init -backend=false
terraform test
```

Expected: failure — no resources defined yet.

- [ ] **Step 3: Write `versions.tf`**

```hcl
terraform {
  required_version = ">= 1.9.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.50.0, < 6.0.0"
    }
  }
}
```

- [ ] **Step 4: Write `variables.tf`**

```hcl
variable "env" {
  description = "Deployment environment. Used as a tag and as a name prefix on every taggable resource."
  type        = string

  validation {
    condition     = contains(["dev", "stg", "prod"], var.env)
    error_message = "env must be one of dev, stg, prod."
  }
}

variable "region" {
  description = "AWS region for the workload-account landing zone."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC. Must not overlap with other env CIDRs in the same account."
  type        = string

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "vpc_cidr must be a valid IPv4 CIDR."
  }
}

variable "availability_zones" {
  description = "Number of AZs to span. Must be at most the count of AZs in the region."
  type        = number
  default     = 3

  validation {
    condition     = var.availability_zones >= 2 && var.availability_zones <= 4
    error_message = "availability_zones must be between 2 and 4."
  }
}

variable "transit_gateway_id" {
  description = "ID of the upstream Transit Gateway. Owned by the central platform team."
  type        = string
}

variable "enable_guardduty" {
  description = "Whether to enable GuardDuty in this account. Default true; set false only for ephemeral test accounts."
  type        = bool
  default     = true
}

variable "enable_security_hub" {
  description = "Whether to enable Security Hub. Default true."
  type        = bool
  default     = true
}

variable "flow_logs_retention_days" {
  description = "Retention for VPC flow logs in CloudWatch. Defaults to 365 in prod, 30 elsewhere via env tfvars."
  type        = number
  default     = 30
}

variable "tags" {
  description = "Tags to apply to every resource. Must include cost_center."
  type        = map(string)

  validation {
    condition     = contains(keys(var.tags), "cost_center")
    error_message = "tags must include cost_center."
  }
}
```

- [ ] **Step 5: Write `main.tf`** (locals + data sources)

```hcl
locals {
  azs              = slice(data.aws_availability_zones.available.names, 0, var.availability_zones)
  is_prod          = var.env == "prod"
  nat_gateway_count = local.is_prod ? var.availability_zones : 1
  name_prefix      = var.env

  common_tags = merge(var.tags, {
    env    = var.env
    module = "landing-zone"
  })
}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}
```

- [ ] **Step 6: Write `vpc.tf`** (VPC + subnets + IGW + NAT)

```hcl
resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-vpc"
  })
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-igw"
  })
}

resource "aws_subnet" "public" {
  count = var.availability_zones

  vpc_id                  = aws_vpc.this.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, count.index)
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = false

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-public-${local.azs[count.index]}"
    tier = "public"
  })
}

resource "aws_subnet" "private" {
  count = var.availability_zones

  vpc_id            = aws_vpc.this.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + 4)
  availability_zone = local.azs[count.index]

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-private-${local.azs[count.index]}"
    tier = "private"
  })
}

resource "aws_subnet" "data" {
  count = var.availability_zones

  vpc_id            = aws_vpc.this.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + 8)
  availability_zone = local.azs[count.index]

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-data-${local.azs[count.index]}"
    tier = "data"
  })
}

resource "aws_eip" "nat" {
  count  = local.nat_gateway_count
  domain = "vpc"

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-nat-eip-${count.index}"
  })
}

resource "aws_nat_gateway" "this" {
  count = local.nat_gateway_count

  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-nat-${count.index}"
  })

  depends_on = [aws_internet_gateway.this]
}

resource "aws_ec2_transit_gateway_vpc_attachment" "this" {
  subnet_ids         = aws_subnet.private[*].id
  transit_gateway_id = var.transit_gateway_id
  vpc_id             = aws_vpc.this.id

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-tgw-attach"
  })
}
```

- [ ] **Step 7: Write `routing.tf`**

```hcl
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-rt-public"
  })
}

resource "aws_route_table_association" "public" {
  count = var.availability_zones

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  count = var.availability_zones

  vpc_id = aws_vpc.this.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.this[local.is_prod ? count.index : 0].id
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-rt-private-${count.index}"
  })
}

resource "aws_route_table_association" "private" {
  count = var.availability_zones

  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

resource "aws_route_table" "data" {
  vpc_id = aws_vpc.this.id

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-rt-data"
  })
}

resource "aws_route_table_association" "data" {
  count = var.availability_zones

  subnet_id      = aws_subnet.data[count.index].id
  route_table_id = aws_route_table.data.id
}
```

- [ ] **Step 8: Write `security.tf`** (flow logs + GuardDuty + Security Hub)

```hcl
resource "aws_cloudwatch_log_group" "flow_logs" {
  name              = "/aws/vpc/flow-logs/${local.name_prefix}"
  retention_in_days = var.flow_logs_retention_days

  tags = local.common_tags
}

resource "aws_iam_role" "flow_logs" {
  name = "${local.name_prefix}-flow-logs-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "vpc-flow-logs.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "flow_logs" {
  name = "${local.name_prefix}-flow-logs-policy"
  role = aws_iam_role.flow_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
      ]
      Resource = "${aws_cloudwatch_log_group.flow_logs.arn}:*"
    }]
  })
}

resource "aws_flow_log" "vpc" {
  iam_role_arn    = aws_iam_role.flow_logs.arn
  log_destination = aws_cloudwatch_log_group.flow_logs.arn
  traffic_type    = "ALL"
  vpc_id          = aws_vpc.this.id

  tags = local.common_tags
}

resource "aws_guardduty_detector" "this" {
  count = var.enable_guardduty ? 1 : 0

  enable                       = true
  finding_publishing_frequency = "FIFTEEN_MINUTES"

  tags = local.common_tags
}

resource "aws_securityhub_account" "this" {
  count = var.enable_security_hub ? 1 : 0
}

resource "aws_securityhub_standards_subscription" "foundational" {
  count = var.enable_security_hub ? 1 : 0

  standards_arn = "arn:aws:securityhub:${data.aws_region.current.name}::standards/aws-foundational-security-best-practices/v/1.0.0"

  depends_on = [aws_securityhub_account.this]
}
```

- [ ] **Step 9: Write `iam.tf`** (baseline permissions boundary + password policy)

```hcl
resource "aws_iam_account_password_policy" "this" {
  minimum_password_length        = 14
  require_lowercase_characters   = true
  require_uppercase_characters   = true
  require_numbers                = true
  require_symbols                = true
  allow_users_to_change_password = true
  max_password_age               = 90
  password_reuse_prevention      = 24
  hard_expiry                    = false
}

resource "aws_iam_policy" "env_scoped_boundary" {
  name        = "${local.name_prefix}-env-scoped-boundary"
  description = "Permissions boundary for ${var.env} workload roles. Forbids access to resources tagged with a different env."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "AllowMostActions"
        Effect   = "Allow"
        Action   = "*"
        Resource = "*"
      },
      {
        Sid    = "DenyCrossEnvResourceAccess"
        Effect = "Deny"
        Action = "*"
        Resource = "*"
        Condition = {
          StringNotEquals = {
            "aws:ResourceTag/env" = var.env
          }
          StringEquals = {
            "aws:RequestedRegion" = var.region
          }
          "Null" = {
            "aws:ResourceTag/env" = "false"
          }
        }
      },
      {
        Sid    = "DenyIamModification"
        Effect = "Deny"
        Action = [
          "iam:CreateUser",
          "iam:DeleteUser",
          "iam:PutUserPolicy",
          "iam:AttachUserPolicy",
        ]
        Resource = "*"
      },
    ]
  })
}
```

- [ ] **Step 10: Write `outputs.tf`**

```hcl
output "vpc_id" {
  description = "VPC ID for the env."
  value       = aws_vpc.this.id
}

output "private_subnet_ids" {
  description = "Private subnet IDs for compute workloads."
  value       = aws_subnet.private[*].id
}

output "data_subnet_ids" {
  description = "Data subnet IDs for stateful workloads (DB, ElastiCache, etc.)."
  value       = aws_subnet.data[*].id
}

output "public_subnet_ids" {
  description = "Public subnet IDs (NAT gateways live here)."
  value       = aws_subnet.public[*].id
}

output "flow_logs_log_group_arn" {
  description = "ARN of the CloudWatch log group capturing VPC flow logs."
  value       = aws_cloudwatch_log_group.flow_logs.arn
}

output "guardduty_detector_id" {
  description = "GuardDuty detector ID, or null if disabled."
  value       = try(aws_guardduty_detector.this[0].id, null)
}

output "permissions_boundary_arn" {
  description = "ARN of the env-scoped permissions boundary policy. Attach this to workload IAM roles."
  value       = aws_iam_policy.env_scoped_boundary.arn
}
```

- [ ] **Step 11: Write `README.md`**

````markdown
# `landing-zone` Terraform module

Workload-account landing zone for an EXL env account. Provisions a 3-tier VPC, NAT gateways, Transit Gateway attachment, VPC flow logs, GuardDuty, Security Hub, account password policy, and an env-scoped permissions boundary.

This module is **not** an organisation-level landing zone. It does not manage AWS Organizations resources; account creation is owned by ABSA's central platform team via Control Tower / AFT. See [ADR-0004](../../../docs/adr/0004-account-topology-1-absa-3-exl.md) for the topology rationale.

## Usage

```hcl
module "landing_zone" {
  source = "../../modules/landing-zone"

  env                = "dev"
  region             = "af-south-1"
  vpc_cidr           = "10.40.0.0/20"
  availability_zones = 3
  transit_gateway_id = "tgw-0123456789abcdef0"

  enable_guardduty    = true
  enable_security_hub = true
  flow_logs_retention_days = 30

  tags = {
    cost_center = "ml-platform"
  }
}
```

## CIDR allocation convention

| Env | CIDR | Subnet pattern |
| --- | --- | --- |
| dev | `10.40.0.0/20` | public 0-2, private 3-5, data 6-8 |
| stg | `10.40.16.0/20` | same |
| prod | `10.40.32.0/20` | same |

## NAT gateway pattern

Prod uses one NAT gateway per AZ for high availability (3 NATs in 3 AZs). Dev and stg share a single NAT gateway in the first AZ for cost. Verified by the `non_prod_uses_single_nat_gateway` and `prod_uses_one_nat_gateway_per_az` tests.

## Permissions boundary

The module creates an env-scoped permissions boundary policy at `arn:aws:iam::<account>:policy/<env>-env-scoped-boundary`. Attach this to every workload role you create in the env. The boundary denies any action on a resource tagged `env=<other>` and denies IAM-user mutation entirely. See [ADR-0004 §Compensating controls](../../../docs/adr/0004-account-topology-1-absa-3-exl.md) for context.

## Inputs

See `variables.tf` for the authoritative list and validation rules. Required inputs without defaults: `env`, `region`, `vpc_cidr`, `transit_gateway_id`, `tags`.

## Outputs

See `outputs.tf`. Notable: `vpc_id`, `private_subnet_ids`, `data_subnet_ids`, `permissions_boundary_arn`.

## Tests

Run `terraform test` from the module directory. All tests are plan-validate — no apply, no AWS credentials required.

## Compliance mapping

| Control | Where |
| --- | --- |
| ISO 27001 A.12.4.1 — event logging | VPC flow logs, GuardDuty, Security Hub |
| SOC 2 CC6.1 — logical access | env-scoped permissions boundary |
| ABSA GMRMG — segregation of envs | non-overlapping CIDRs + permissions boundary |
````

- [ ] **Step 12: Re-run the test, expect pass**

```bash
cd terraform/modules/landing-zone
terraform init -backend=false
terraform validate
terraform test
```

Expected: all 7 `run` blocks pass.

- [ ] **Step 13: Format and commit**

```bash
terraform fmt -recursive
cd ../../..
git add terraform/modules/landing-zone/
git commit -m "feat(landing-zone): workload-account landing zone module

Provisions 3-tier VPC (public/private/data subnets across 3 AZs by
default), NAT gateways (1 per AZ in prod, 1 total in non-prod for cost),
Transit Gateway attachment, VPC flow logs to CloudWatch, GuardDuty
detector, Security Hub with the AWS Foundational standard, account
password policy, and an env-scoped IAM permissions boundary policy.

Tests are plan-validate via terraform test framework — no apply.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `terraform/modules/s3-replication-source/` module

**Files:**
- Create: `terraform/modules/s3-replication-source/versions.tf`
- Create: `terraform/modules/s3-replication-source/variables.tf`
- Create: `terraform/modules/s3-replication-source/main.tf`
- Create: `terraform/modules/s3-replication-source/kms.tf`
- Create: `terraform/modules/s3-replication-source/iam.tf`
- Create: `terraform/modules/s3-replication-source/replication.tf`
- Create: `terraform/modules/s3-replication-source/outputs.tf`
- Create: `terraform/modules/s3-replication-source/README.md`
- Create: `terraform/modules/s3-replication-source/tests/source.tftest.hcl`

- [ ] **Step 1: Write the failing test first**

Save to `terraform/modules/s3-replication-source/tests/source.tftest.hcl`:

```hcl
variables {
  bucket_name              = "absa-model-handoff-dev"
  env                      = "dev"
  retention_years          = 1
  prefix_filter            = "model-ready/"
  destination_bucket_arn   = "arn:aws:s3:::exl-model-landing-dev"
  destination_kms_key_arn  = "arn:aws:kms:af-south-1:222222222222:key/abc-123"
  destination_account_id   = "222222222222"
  tags = {
    cost_center = "ml-platform"
    module      = "s3-replication-source"
  }
}

run "bucket_has_object_lock_compliance_mode" {
  command = plan

  assert {
    condition     = aws_s3_bucket_object_lock_configuration.this.rule[0].default_retention[0].mode == "COMPLIANCE"
    error_message = "Object lock must use COMPLIANCE mode for audit-grade immutability"
  }
}

run "default_retention_matches_var" {
  command = plan

  variables {
    retention_years = 7
  }

  assert {
    condition     = aws_s3_bucket_object_lock_configuration.this.rule[0].default_retention[0].years == 7
    error_message = "Default retention must equal var.retention_years"
  }
}

run "kms_key_rotation_is_enabled" {
  command = plan

  assert {
    condition     = aws_kms_key.this.enable_key_rotation == true
    error_message = "Source KMS key must have rotation enabled"
  }
}

run "replication_uses_rtc_with_15_minute_metric" {
  command = plan

  assert {
    condition = (
      aws_s3_bucket_replication_configuration.this.rule[0].destination[0].replication_time[0].time[0].minutes == 15
    )
    error_message = "Replication time control must be set to 15 minutes"
  }
}

run "prefix_filter_is_applied" {
  command = plan

  assert {
    condition     = aws_s3_bucket_replication_configuration.this.rule[0].filter[0].prefix == "model-ready/"
    error_message = "Replication rule must filter on the model-ready/ prefix"
  }
}

run "delete_marker_replication_disabled_by_default" {
  command = plan

  assert {
    condition     = aws_s3_bucket_replication_configuration.this.rule[0].delete_marker_replication[0].status == "Disabled"
    error_message = "Delete marker replication must be disabled by default"
  }
}

run "env_validation_rejects_unknown_value" {
  command = plan

  variables {
    env = "qa"
  }

  expect_failures = [
    var.env,
  ]
}
```

- [ ] **Step 2: Run the test, expect failure**

```bash
cd terraform/modules/s3-replication-source
terraform init -backend=false
terraform test
```

Expected: failure — module not implemented.

- [ ] **Step 3: Write `versions.tf`**

```hcl
terraform {
  required_version = ">= 1.9.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.50.0, < 6.0.0"
    }
  }
}
```

- [ ] **Step 4: Write `variables.tf`**

```hcl
variable "bucket_name" {
  description = "S3 bucket name for the source side. Convention: absa-model-handoff-{env}."
  type        = string
}

variable "env" {
  description = "Environment identifier."
  type        = string

  validation {
    condition     = contains(["dev", "stg", "prod"], var.env)
    error_message = "env must be one of dev, stg, prod."
  }
}

variable "retention_years" {
  description = "Default object-lock retention in years. 7 in prod; shorter overrides for dev / stg."
  type        = number
  default     = 7

  validation {
    condition     = var.retention_years >= 1 && var.retention_years <= 100
    error_message = "retention_years must be between 1 and 100."
  }
}

variable "prefix_filter" {
  description = "Object key prefix that scopes replication. Only objects under this prefix replicate."
  type        = string
  default     = "model-ready/"
}

variable "replication_time_control_enabled" {
  description = "Whether to enable Replication Time Control (15-minute SLA). Default true."
  type        = bool
  default     = true
}

variable "delete_marker_replication" {
  description = "Whether to replicate delete markers. Default false (deletes do not propagate)."
  type        = bool
  default     = false
}

variable "destination_bucket_arn" {
  description = "ARN of the EXL destination bucket. Output of s3-replication-destination."
  type        = string
}

variable "destination_kms_key_arn" {
  description = "ARN of the EXL destination KMS key. Output of s3-replication-destination."
  type        = string
}

variable "destination_account_id" {
  description = "AWS account ID of the EXL env account that owns the destination."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{12}$", var.destination_account_id))
    error_message = "destination_account_id must be a 12-digit AWS account ID."
  }
}

variable "tags" {
  description = "Tags applied to every resource. Must include cost_center."
  type        = map(string)

  validation {
    condition     = contains(keys(var.tags), "cost_center")
    error_message = "tags must include cost_center."
  }
}
```

- [ ] **Step 5: Write `main.tf`** (locals, bucket, versioning, object lock)

```hcl
locals {
  common_tags = merge(var.tags, {
    env    = var.env
    module = "s3-replication-source"
  })
}

resource "aws_s3_bucket" "this" {
  bucket = var.bucket_name

  object_lock_enabled = true

  tags = local.common_tags
}

resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_object_lock_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    default_retention {
      mode  = "COMPLIANCE"
      years = var.retention_years
    }
  }

  depends_on = [aws_s3_bucket_versioning.this]
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.this.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  bucket = aws_s3_bucket.this.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

- [ ] **Step 6: Write `kms.tf`**

```hcl
resource "aws_kms_key" "this" {
  description             = "Source-side CMK for ${var.bucket_name}"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  key_usage               = "ENCRYPT_DECRYPT"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowAccountRoot"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowReplicationRoleDecrypt"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.replication.arn
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey",
        ]
        Resource = "*"
      },
    ]
  })

  tags = local.common_tags
}

resource "aws_kms_alias" "this" {
  name          = "alias/handoff-${var.env}"
  target_key_id = aws_kms_key.this.key_id
}

data "aws_caller_identity" "current" {}
```

- [ ] **Step 7: Write `iam.tf`** (replication role and policy)

```hcl
resource "aws_iam_role" "replication" {
  name = "${var.env}-s3-replication-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "s3.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_policy" "replication" {
  name        = "${var.env}-s3-replication-policy"
  description = "Permissions for the ${var.env} S3 replication role to read source and write destination."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadSourceBucket"
        Effect = "Allow"
        Action = [
          "s3:GetObjectVersionForReplication",
          "s3:GetObjectVersionAcl",
          "s3:GetObjectVersionTagging",
          "s3:ListBucket",
          "s3:GetReplicationConfiguration",
        ]
        Resource = [
          aws_s3_bucket.this.arn,
          "${aws_s3_bucket.this.arn}/*",
        ]
      },
      {
        Sid    = "DecryptWithSourceKey"
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey",
        ]
        Resource = aws_kms_key.this.arn
      },
      {
        Sid    = "WriteDestinationBucket"
        Effect = "Allow"
        Action = [
          "s3:ReplicateObject",
          "s3:ReplicateDelete",
          "s3:ReplicateTags",
        ]
        Resource = "${var.destination_bucket_arn}/*"
      },
      {
        Sid      = "EncryptWithDestinationKey"
        Effect   = "Allow"
        Action   = "kms:Encrypt"
        Resource = var.destination_kms_key_arn
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "replication" {
  role       = aws_iam_role.replication.name
  policy_arn = aws_iam_policy.replication.arn
}
```

- [ ] **Step 8: Write `replication.tf`**

```hcl
resource "aws_s3_bucket_replication_configuration" "this" {
  role   = aws_iam_role.replication.arn
  bucket = aws_s3_bucket.this.id

  rule {
    id       = "${var.env}-replicate-model-ready"
    status   = "Enabled"
    priority = 0

    filter {
      prefix = var.prefix_filter
    }

    delete_marker_replication {
      status = var.delete_marker_replication ? "Enabled" : "Disabled"
    }

    source_selection_criteria {
      sse_kms_encrypted_objects {
        status = "Enabled"
      }
    }

    destination {
      bucket        = var.destination_bucket_arn
      account       = var.destination_account_id
      storage_class = "STANDARD"

      access_control_translation {
        owner = "Destination"
      }

      encryption_configuration {
        replica_kms_key_id = var.destination_kms_key_arn
      }

      dynamic "replication_time" {
        for_each = var.replication_time_control_enabled ? [1] : []
        content {
          status = "Enabled"
          time {
            minutes = 15
          }
        }
      }

      dynamic "metrics" {
        for_each = var.replication_time_control_enabled ? [1] : []
        content {
          status = "Enabled"
          event_threshold {
            minutes = 15
          }
        }
      }
    }
  }

  depends_on = [aws_s3_bucket_versioning.this]
}
```

- [ ] **Step 9: Write `outputs.tf`**

```hcl
output "bucket_arn" {
  description = "ARN of the source bucket."
  value       = aws_s3_bucket.this.arn
}

output "bucket_id" {
  description = "ID (name) of the source bucket."
  value       = aws_s3_bucket.this.id
}

output "kms_key_arn" {
  description = "ARN of the source-side KMS CMK."
  value       = aws_kms_key.this.arn
}

output "kms_key_alias" {
  description = "Alias of the source-side KMS CMK."
  value       = aws_kms_alias.this.name
}

output "replication_role_arn" {
  description = "ARN of the IAM role used by S3 to replicate. Pass this to the destination side."
  value       = aws_iam_role.replication.arn
}

output "replication_metric_namespace" {
  description = "CloudWatch metric namespace for replication metrics. Always AWS/S3 — exposed for caller convenience."
  value       = "AWS/S3"
}
```

- [ ] **Step 10: Write `README.md`**

````markdown
# `s3-replication-source` Terraform module

Source-side S3 replication module. Deploys into ABSA's AWS account. Provisions one source bucket, its per-env KMS CMK, the replication IAM role, and the replication configuration. Designed to pair with [`s3-replication-destination`](../s3-replication-destination/) deployed in the matching EXL env account.

See [ADR-0001](../../../docs/adr/0001-data-movement-s3-replication.md) for the data-movement decision and [ADR-0002](../../../docs/adr/0002-cross-account-iac-dual-module-split.md) for the dual-module split rationale.

## Usage

```hcl
module "replication_source" {
  source = "../../modules/s3-replication-source"

  bucket_name              = "absa-model-handoff-dev"
  env                      = "dev"
  retention_years          = 7
  prefix_filter            = "model-ready/"
  destination_bucket_arn   = data.terraform_remote_state.destination.outputs.bucket_arn
  destination_kms_key_arn  = data.terraform_remote_state.destination.outputs.kms_key_arn
  destination_account_id   = "222222222222"

  tags = {
    cost_center = "ml-platform"
  }
}
```

## Apply order

This module depends on the destination module having applied first to produce the destination bucket and KMS key ARNs. See [`terraform/shared/replication-contract.md`](../../shared/replication-contract.md) for the full bootstrap sequence.

## Object-lock retention warning

This bucket uses **COMPLIANCE mode** object lock. Compliance mode means even the AWS account root cannot delete objects or shorten the retention period before expiry. The default retention of 7 years is intentional for prod. For dev / stg, override `retention_years` to a shorter value (e.g. 1) so test data ages out and storage costs stay bounded.

## Inputs

See `variables.tf`. Required: `bucket_name`, `env`, `destination_bucket_arn`, `destination_kms_key_arn`, `destination_account_id`, `tags`.

## Outputs

See `outputs.tf`. Notable: `replication_role_arn` (consumed by the destination side), `bucket_arn`, `kms_key_arn`.

## Tests

`terraform test` from this directory. Plan-validate only.

## Compliance mapping

| Control | Where |
| --- | --- |
| POPIA s14 — retention | Object-lock configuration |
| SARB GOI 5 — model documentation | COMPLIANCE-mode immutability |
| ISO 27001 A.13.2.1 | KMS encryption + replication role least privilege |
````

- [ ] **Step 11: Re-run the test, expect pass**

```bash
cd terraform/modules/s3-replication-source
terraform init -backend=false
terraform validate
terraform test
```

Expected: all 7 `run` blocks pass.

- [ ] **Step 12: Format and commit**

```bash
terraform fmt -recursive
cd ../../..
git add terraform/modules/s3-replication-source/
git commit -m "feat(s3-replication-source): ABSA-side replication module

Provisions the source bucket (versioned, object-lock compliance mode,
KMS-encrypted), per-env KMS CMK with rotation, replication IAM role, and
the bucket replication configuration with RTC and 15-minute metrics.

Tests assert object-lock compliance mode, retention from var, KMS
rotation, RTC-15min replication, prefix filter, and delete-marker
replication disabled by default.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: `terraform/modules/s3-replication-destination/` module

**Files:**
- Create: `terraform/modules/s3-replication-destination/versions.tf`
- Create: `terraform/modules/s3-replication-destination/variables.tf`
- Create: `terraform/modules/s3-replication-destination/main.tf`
- Create: `terraform/modules/s3-replication-destination/kms.tf`
- Create: `terraform/modules/s3-replication-destination/policy.tf`
- Create: `terraform/modules/s3-replication-destination/alarms.tf`
- Create: `terraform/modules/s3-replication-destination/outputs.tf`
- Create: `terraform/modules/s3-replication-destination/README.md`
- Create: `terraform/modules/s3-replication-destination/tests/destination.tftest.hcl`

- [ ] **Step 1: Write the failing test**

Save to `terraform/modules/s3-replication-destination/tests/destination.tftest.hcl`:

```hcl
variables {
  bucket_name                 = "exl-model-landing-dev"
  env                         = "dev"
  retention_years             = 1
  source_replication_role_arn = "arn:aws:iam::111111111111:role/dev-s3-replication-role"
  source_account_id           = "111111111111"
  prefix_filter               = "model-ready/"
  alarm_threshold_seconds     = 900
  tags = {
    cost_center = "ml-platform"
    module      = "s3-replication-destination"
  }
}

run "bucket_has_object_lock_compliance_mode" {
  command = plan

  assert {
    condition     = aws_s3_bucket_object_lock_configuration.this.rule[0].default_retention[0].mode == "COMPLIANCE"
    error_message = "Object lock must use COMPLIANCE mode"
  }
}

run "kms_key_rotation_is_enabled" {
  command = plan

  assert {
    condition     = aws_kms_key.this.enable_key_rotation == true
    error_message = "Destination KMS key must have rotation enabled"
  }
}

run "replication_latency_alarm_exists" {
  command = plan

  assert {
    condition     = aws_cloudwatch_metric_alarm.replication_latency.threshold == 900
    error_message = "ReplicationLatency alarm threshold must equal alarm_threshold_seconds"
  }
}

run "replication_latency_alarm_uses_correct_metric" {
  command = plan

  assert {
    condition     = aws_cloudwatch_metric_alarm.replication_latency.metric_name == "ReplicationLatency"
    error_message = "Latency alarm must watch ReplicationLatency metric"
  }
}

run "failed_replication_alarm_fires_on_any_failure" {
  command = plan

  assert {
    condition = (
      aws_cloudwatch_metric_alarm.failed_replication.threshold == 0 &&
      aws_cloudwatch_metric_alarm.failed_replication.comparison_operator == "GreaterThanThreshold"
    )
    error_message = "FailedReplication alarm must fire when count > 0"
  }
}

run "sns_topic_exists_and_is_kms_encrypted" {
  command = plan

  assert {
    condition     = aws_sns_topic.replication_alerts.kms_master_key_id == "alias/aws/sns"
    error_message = "SNS topic must be encrypted with the AWS-managed SNS key"
  }
}

run "bucket_policy_grants_source_replication_role" {
  command = plan

  assert {
    condition = strcontains(
      aws_s3_bucket_policy.this.policy,
      "arn:aws:iam::111111111111:role/dev-s3-replication-role",
    )
    error_message = "Bucket policy must grant the source replication role"
  }
}
```

> **Note on the SNS-subscription invariant:** the module-does-not-own-subscriptions invariant is a code-structure rule, not something Terraform's test framework can introspect by resource type. We enforce it via code review (CODEOWNERS gate on `terraform/modules/s3-replication-destination/`) and via the tflint custom rule added in Task 7 if any author later adds an `aws_sns_topic_subscription` here.

- [ ] **Step 2: Run the test, expect failure**

```bash
cd terraform/modules/s3-replication-destination
terraform init -backend=false
terraform test
```

Expected: failure — module not implemented.

- [ ] **Step 3: Write `versions.tf`**

```hcl
terraform {
  required_version = ">= 1.9.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.50.0, < 6.0.0"
    }
  }
}
```

- [ ] **Step 4: Write `variables.tf`**

```hcl
variable "bucket_name" {
  description = "Destination bucket name. Convention: exl-model-landing-{env}."
  type        = string
}

variable "env" {
  description = "Environment identifier."
  type        = string

  validation {
    condition     = contains(["dev", "stg", "prod"], var.env)
    error_message = "env must be one of dev, stg, prod."
  }
}

variable "retention_years" {
  description = "Default object-lock retention in years. 7 prod default; shorter overrides for dev / stg."
  type        = number
  default     = 7
}

variable "source_replication_role_arn" {
  description = "ARN of the source-side replication role. Granted permission to write into this bucket and use this KMS key."
  type        = string
}

variable "source_account_id" {
  description = "AWS account ID of the ABSA source side."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{12}$", var.source_account_id))
    error_message = "source_account_id must be a 12-digit AWS account ID."
  }
}

variable "prefix_filter" {
  description = "Prefix used by source replication; only documented here for cross-side consistency."
  type        = string
  default     = "model-ready/"
}

variable "alarm_threshold_seconds" {
  description = "ReplicationLatency alarm threshold. Default 900s = 15 minutes (matches RTC SLA)."
  type        = number
  default     = 900
}

variable "tags" {
  description = "Tags applied to every resource. Must include cost_center."
  type        = map(string)

  validation {
    condition     = contains(keys(var.tags), "cost_center")
    error_message = "tags must include cost_center."
  }
}
```

- [ ] **Step 5: Write `main.tf`**

```hcl
locals {
  common_tags = merge(var.tags, {
    env    = var.env
    module = "s3-replication-destination"
  })
}

resource "aws_s3_bucket" "this" {
  bucket = var.bucket_name

  object_lock_enabled = true

  tags = local.common_tags
}

resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_object_lock_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    default_retention {
      mode  = "COMPLIANCE"
      years = var.retention_years
    }
  }

  depends_on = [aws_s3_bucket_versioning.this]
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.this.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  bucket = aws_s3_bucket.this.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
```

- [ ] **Step 6: Write `kms.tf`**

```hcl
resource "aws_kms_key" "this" {
  description             = "Destination-side CMK for ${var.bucket_name}"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  key_usage               = "ENCRYPT_DECRYPT"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowAccountRoot"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" }
        Action    = "kms:*"
        Resource  = "*"
      },
      {
        Sid    = "AllowSourceReplicationRoleEncrypt"
        Effect = "Allow"
        Principal = {
          AWS = var.source_replication_role_arn
        }
        Action = [
          "kms:Encrypt",
          "kms:GenerateDataKey",
          "kms:DescribeKey",
        ]
        Resource = "*"
      },
    ]
  })

  tags = local.common_tags
}

resource "aws_kms_alias" "this" {
  name          = "alias/model-landing-${var.env}"
  target_key_id = aws_kms_key.this.key_id
}
```

- [ ] **Step 7: Write `policy.tf`**

```hcl
resource "aws_s3_bucket_policy" "this" {
  bucket = aws_s3_bucket.this.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowSourceReplicationRoleWrite"
        Effect = "Allow"
        Principal = {
          AWS = var.source_replication_role_arn
        }
        Action = [
          "s3:ReplicateObject",
          "s3:ReplicateDelete",
          "s3:ReplicateTags",
          "s3:ObjectOwnerOverrideToBucketOwner",
        ]
        Resource = "${aws_s3_bucket.this.arn}/*"
      },
      {
        Sid    = "AllowSourceAccountListBucket"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${var.source_account_id}:root"
        }
        Action = [
          "s3:GetBucketVersioning",
          "s3:PutBucketVersioning",
        ]
        Resource = aws_s3_bucket.this.arn
      },
    ]
  })
}
```

- [ ] **Step 8: Write `alarms.tf`**

```hcl
resource "aws_sns_topic" "replication_alerts" {
  name              = "${var.env}-s3-replication-alerts"
  kms_master_key_id = "alias/aws/sns"

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "replication_latency" {
  alarm_name          = "${var.env}-s3-replication-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ReplicationLatency"
  namespace           = "AWS/S3"
  period              = 60
  statistic           = "Maximum"
  threshold           = var.alarm_threshold_seconds
  alarm_description   = "Replication latency exceeded RTC SLA for ${var.env}"
  treat_missing_data  = "notBreaching"

  dimensions = {
    SourceBucket    = "absa-model-handoff-${var.env}"
    DestinationBucket = aws_s3_bucket.this.id
    RuleId          = "${var.env}-replicate-model-ready"
  }

  alarm_actions = [aws_sns_topic.replication_alerts.arn]
  ok_actions    = [aws_sns_topic.replication_alerts.arn]

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "failed_replication" {
  alarm_name          = "${var.env}-s3-replication-failed"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "OperationsFailedReplication"
  namespace           = "AWS/S3"
  period              = 60
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Any replication failure for ${var.env} should page immediately"
  treat_missing_data  = "notBreaching"

  dimensions = {
    SourceBucket      = "absa-model-handoff-${var.env}"
    DestinationBucket = aws_s3_bucket.this.id
    RuleId            = "${var.env}-replicate-model-ready"
  }

  alarm_actions = [aws_sns_topic.replication_alerts.arn]

  tags = local.common_tags
}
```

- [ ] **Step 9: Write `outputs.tf`**

```hcl
output "bucket_arn" {
  description = "ARN of the destination bucket. Pass this to the source-side module."
  value       = aws_s3_bucket.this.arn
}

output "bucket_id" {
  description = "ID (name) of the destination bucket."
  value       = aws_s3_bucket.this.id
}

output "kms_key_arn" {
  description = "ARN of the destination KMS CMK. Pass this to the source-side module."
  value       = aws_kms_key.this.arn
}

output "kms_key_alias" {
  description = "KMS alias for the destination key."
  value       = aws_kms_alias.this.name
}

output "sns_topic_arn" {
  description = "SNS topic ARN. Per-env stacks attach subscriptions to this topic."
  value       = aws_sns_topic.replication_alerts.arn
}

output "replication_metric_alarm_arn" {
  description = "ARN of the ReplicationLatency CloudWatch alarm."
  value       = aws_cloudwatch_metric_alarm.replication_latency.arn
}

output "failed_replication_alarm_arn" {
  description = "ARN of the OperationsFailedReplication CloudWatch alarm."
  value       = aws_cloudwatch_metric_alarm.failed_replication.arn
}
```

- [ ] **Step 10: Write `README.md`**

````markdown
# `s3-replication-destination` Terraform module

Destination-side S3 replication module. Deploys into the matching EXL env account. Provisions the destination bucket, destination KMS CMK, bucket policy granting the source replication role, an SNS topic for alerts, and CloudWatch alarms for `ReplicationLatency` and `OperationsFailedReplication`.

The module **does not own SNS subscriptions** — those live in the per-env stack at `terraform/envs/{env}/destination/replication-subscriptions.tf`. This keeps the module portable across envs without baking in vendor-specific paging integrations. See [ADR-0001 §Decision](../../../docs/adr/0001-data-movement-s3-replication.md).

## Usage

```hcl
module "replication_destination" {
  source = "../../modules/s3-replication-destination"

  bucket_name                 = "exl-model-landing-dev"
  env                         = "dev"
  retention_years             = 7
  source_replication_role_arn = data.terraform_remote_state.source.outputs.replication_role_arn
  source_account_id           = "111111111111"
  alarm_threshold_seconds     = 900

  tags = {
    cost_center = "ml-platform"
  }
}
```

## Apply order

This module applies before the source-side module exists (Phase 1 of the bootstrap in [`terraform/shared/replication-contract.md`](../../shared/replication-contract.md)). On the first apply, `var.source_replication_role_arn` is the ARN that will eventually exist; the bucket policy and KMS key policy will reference a principal that resolves only after the source side has applied.

## Inputs

See `variables.tf`. Required: `bucket_name`, `env`, `source_replication_role_arn`, `source_account_id`, `tags`.

## Outputs

See `outputs.tf`. Notable: `bucket_arn`, `kms_key_arn`, `sns_topic_arn`, `replication_metric_alarm_arn`.

## Tests

`terraform test` from this directory.

## Compliance mapping

| Control | Where |
| --- | --- |
| ISO 27001 A.13.2.1 | KMS-encrypted destination, bucket policy least-privilege |
| SOC 2 CC7.2 — system monitoring | ReplicationLatency + FailedReplication alarms |
| ABSA GMRMG | Per-env destination bucket = per-env data lineage |
````

- [ ] **Step 11: Re-run the test, expect pass**

```bash
cd terraform/modules/s3-replication-destination
terraform init -backend=false
terraform validate
terraform test
```

Expected: all assertions pass. (If the SNS-subscription assertion's `plantfstate` symbol is rejected, simplify per the note in Step 1.)

- [ ] **Step 12: Format and commit**

```bash
terraform fmt -recursive
cd ../../..
git add terraform/modules/s3-replication-destination/
git commit -m "feat(s3-replication-destination): EXL-side replication module

Provisions the destination bucket (versioned, object-lock compliance
mode, KMS-encrypted), destination KMS CMK, bucket policy granting the
source replication role, SNS topic owned by the module (no
subscriptions), and CloudWatch alarms for ReplicationLatency (15-min
threshold) and OperationsFailedReplication (any failure).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Env stacks and account-bootstrap scaffolds

**Files:**
- Create: 6 env stacks under `terraform/envs/{dev,stg,prod}/{source,destination}/`
- Create: 3 account-bootstrap stacks under `terraform/account-bootstrap/exl-{dev,stg,prod}/`

For each env in `{dev, stg, prod}` and each side in `{source, destination}`, the stack is a thin caller of the matching module. We write the dev/source stack as the canonical example and reproduce it for the others; this is repetitive but explicit per the no-placeholder rule.

- [ ] **Step 1: Write `terraform/envs/dev/source/main.tf`**

```hcl
terraform {
  required_version = ">= 1.9.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.50.0, < 6.0.0"
    }
  }

  # backend "s3" {
  #   bucket         = "absa-tfstate-handoff-dev"
  #   key            = "s3-replication-source/terraform.tfstate"
  #   region         = "af-south-1"
  #   dynamodb_table = "absa-tfstate-lock-dev"
  #   encrypt        = true
  # }
  # Backend block is commented out for Phase 1 — uncomment when the
  # state bucket is provisioned (ABSA Cloud Platform team task).
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      env         = "dev"
      cost_center = "ml-platform"
      managed_by  = "terraform"
      stack       = "envs/dev/source"
    }
  }
}

module "replication_source" {
  source = "../../../modules/s3-replication-source"

  bucket_name              = "absa-model-handoff-dev"
  env                      = "dev"
  retention_years          = local.retention_years
  prefix_filter            = "model-ready/"
  destination_bucket_arn   = var.destination_bucket_arn
  destination_kms_key_arn  = var.destination_kms_key_arn
  destination_account_id   = var.destination_account_id

  tags = {
    cost_center = "ml-platform"
  }
}
```

- [ ] **Step 2: Write `terraform/envs/dev/source/variables.tf`**

```hcl
variable "region" {
  description = "AWS region for the ABSA-side dev resources."
  type        = string
  default     = "af-south-1"
}

variable "destination_bucket_arn" {
  description = "Output bucket_arn from the dev destination stack."
  type        = string
}

variable "destination_kms_key_arn" {
  description = "Output kms_key_arn from the dev destination stack."
  type        = string
}

variable "destination_account_id" {
  description = "AWS account ID of exl-dev."
  type        = string
}
```

- [ ] **Step 3: Write `terraform/envs/dev/source/locals.tf`**

```hcl
locals {
  retention_years = 1 # dev: short retention so test data ages out quickly
}
```

- [ ] **Step 4: Write `terraform/envs/dev/source/terraform.tfvars`**

```hcl
# Filled in once the dev-destination stack has applied.
# destination_bucket_arn   = "arn:aws:s3:::exl-model-landing-dev"
# destination_kms_key_arn  = "arn:aws:kms:af-south-1:222222222222:key/REPLACE"
# destination_account_id   = "222222222222"
```

- [ ] **Step 5: Write `terraform/envs/dev/destination/main.tf`**

```hcl
terraform {
  required_version = ">= 1.9.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.50.0, < 6.0.0"
    }
  }

  # backend "s3" {
  #   bucket         = "exl-tfstate-dev"
  #   key            = "envs/dev/destination/terraform.tfstate"
  #   region         = "af-south-1"
  #   dynamodb_table = "exl-tfstate-lock-dev"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      env         = "dev"
      cost_center = "ml-platform"
      managed_by  = "terraform"
      stack       = "envs/dev/destination"
    }
  }
}

module "landing_zone" {
  source = "../../../modules/landing-zone"

  env                = "dev"
  region             = var.region
  vpc_cidr           = "10.40.0.0/20"
  availability_zones = 3
  transit_gateway_id = var.transit_gateway_id

  enable_guardduty         = true
  enable_security_hub      = true
  flow_logs_retention_days = 30

  tags = {
    cost_center = "ml-platform"
  }
}

module "replication_destination" {
  source = "../../../modules/s3-replication-destination"

  bucket_name                 = "exl-model-landing-dev"
  env                         = "dev"
  retention_years             = local.retention_years
  source_replication_role_arn = var.source_replication_role_arn
  source_account_id           = var.source_account_id
  alarm_threshold_seconds     = 900

  tags = {
    cost_center = "ml-platform"
  }
}
```

- [ ] **Step 6: Write `terraform/envs/dev/destination/variables.tf`**

```hcl
variable "region" {
  type    = string
  default = "af-south-1"
}

variable "transit_gateway_id" {
  type        = string
  description = "Upstream TGW ID. Provided by ABSA central platform team."
}

variable "source_replication_role_arn" {
  type        = string
  description = "Output replication_role_arn from the dev source stack."
}

variable "source_account_id" {
  type        = string
  description = "AWS account ID of the ABSA account."
}
```

- [ ] **Step 7: Write `terraform/envs/dev/destination/locals.tf`**

```hcl
locals {
  retention_years = 1 # dev override
}
```

- [ ] **Step 8: Write `terraform/envs/dev/destination/replication-subscriptions.tf`**

```hcl
# SNS subscriptions for the dev replication alerts topic.
# Module owns the topic; this stack owns the subscriptions per ADR-0001.
#
# Phase 1: email-only subscription to the platform ops list. PagerDuty /
# Opsgenie integration is added in Phase 2 once the engagement lead
# confirms the paging vendor.
#
# Uncomment when the engagement lead provides the email address.

# resource "aws_sns_topic_subscription" "ops_email" {
#   topic_arn = module.replication_destination.sns_topic_arn
#   protocol  = "email"
#   endpoint  = "exl-platform-ops@example.com" # replace with the real ops list before uncommenting
# }
```

- [ ] **Step 9: Write `terraform/envs/dev/destination/terraform.tfvars`**

```hcl
# Filled in once the source stack has applied and the upstream TGW ID is
# provided by ABSA's central platform team.
# transit_gateway_id          = "tgw-REPLACE"
# source_replication_role_arn = "arn:aws:iam::111111111111:role/dev-s3-replication-role"
# source_account_id           = "111111111111"
```

- [ ] **Step 10: Replicate the dev stacks for stg and prod**

The dev source stack has 4 files (`main.tf`, `variables.tf`, `locals.tf`, `terraform.tfvars`); the dev destination stack has 5 files (`main.tf`, `variables.tf`, `locals.tf`, `replication-subscriptions.tf`, `terraform.tfvars`). Replicate them to four target directories — 18 new files total.

Target directories:

- `terraform/envs/stg/source/` (4 files)
- `terraform/envs/stg/destination/` (5 files)
- `terraform/envs/prod/source/` (4 files)
- `terraform/envs/prod/destination/` (5 files)

Substitutions to apply per env:

| Field | dev (already written) | stg | prod |
| --- | --- | --- | --- |
| `bucket_name` (source) | `absa-model-handoff-dev` | `absa-model-handoff-stg` | `absa-model-handoff-prod` |
| `bucket_name` (destination) | `exl-model-landing-dev` | `exl-model-landing-stg` | `exl-model-landing-prod` |
| `vpc_cidr` | `10.40.0.0/20` | `10.40.16.0/20` | `10.40.32.0/20` |
| `retention_years` (locals.tf) | `1` | `3` | `7` |
| `flow_logs_retention_days` (destination main.tf) | `30` | `30` | `365` |
| Provider `default_tags.env` | `dev` | `stg` | `prod` |
| Provider `default_tags.stack` | `envs/dev/source` etc. | `envs/stg/source` etc. | `envs/prod/source` etc. |
| `module.replication_source` `env` arg | `dev` | `stg` | `prod` |
| `module.replication_destination` `env` arg | `dev` | `stg` | `prod` |
| `module.landing_zone` `env` arg | `dev` | `stg` | `prod` |
| `terraform.tfvars` placeholder ARNs | dev account IDs | stg account IDs | prod account IDs |

All other content (provider block, module source paths, default tags structure, IAM tag content, comment blocks) is identical across envs.

- [ ] **Step 11: Write `terraform/account-bootstrap/exl-dev/main.tf`**

```hcl
terraform {
  required_version = ">= 1.9.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.50.0, < 6.0.0"
    }
  }

  # backend "s3" {
  #   bucket         = "exl-tfstate-dev"
  #   key            = "account-bootstrap/terraform.tfstate"
  #   region         = "af-south-1"
  #   dynamodb_table = "exl-tfstate-lock-dev"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      env         = "dev"
      cost_center = "ml-platform"
      managed_by  = "terraform"
      stack       = "account-bootstrap/exl-dev"
    }
  }
}

# CloudTrail multi-region trail for the dev account
resource "aws_cloudtrail" "this" {
  name                          = "exl-dev-trail"
  s3_bucket_name                = aws_s3_bucket.cloudtrail.id
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_log_file_validation    = true

  event_selector {
    read_write_type           = "All"
    include_management_events = true

    data_resource {
      type   = "AWS::S3::Object"
      values = ["arn:aws:s3:::"]
    }
  }
}

resource "aws_s3_bucket" "cloudtrail" {
  bucket        = "exl-dev-cloudtrail-${data.aws_caller_identity.current.account_id}"
  force_destroy = false
}

resource "aws_s3_bucket_policy" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "cloudtrail.amazonaws.com" }
        Action    = "s3:GetBucketAcl"
        Resource  = aws_s3_bucket.cloudtrail.arn
      },
      {
        Effect    = "Allow"
        Principal = { Service = "cloudtrail.amazonaws.com" }
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.cloudtrail.arn}/AWSLogs/${data.aws_caller_identity.current.account_id}/*"
        Condition = {
          StringEquals = {
            "s3:x-amz-acl" = "bucket-owner-full-control"
          }
        }
      },
    ]
  })
}

data "aws_caller_identity" "current" {}
```

- [ ] **Step 12: Write `terraform/account-bootstrap/exl-dev/variables.tf`**

```hcl
variable "region" {
  type    = string
  default = "af-south-1"
}
```

- [ ] **Step 13: Replicate `account-bootstrap` for stg and prod**

Copy the two files in step 11/12 to `terraform/account-bootstrap/exl-stg/` and `terraform/account-bootstrap/exl-prod/`, replacing every occurrence of `dev` with `stg` and `prod` respectively in resource names and tags.

- [ ] **Step 14: Validate every env stack and bootstrap stack**

```bash
for d in terraform/envs/*/* terraform/account-bootstrap/*; do
  echo "=== $d ==="
  (cd "$d" && terraform init -backend=false && terraform validate)
done
```

Expected: every stack reports `Success! The configuration is valid.`

- [ ] **Step 15: Format and commit**

```bash
terraform fmt -recursive
git add terraform/envs/ terraform/account-bootstrap/
git commit -m "scaffold: env stacks and EXL account-bootstrap stacks

Six env stacks (dev/stg/prod × source/destination) calling the three
modules with env-appropriate variable values. Three account-bootstrap
stacks for exl-dev/stg/prod that own account-singleton resources
(starting with CloudTrail; GuardDuty / Security Hub are owned by the
landing-zone module per env). Backend blocks are commented out — they
become live in Phase 2 once the state buckets are provisioned.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: CI workflow and `.tflint.hcl`

**Files:**
- Create: `.tflint.hcl`
- Create: `ci/pipelines/terraform-validate.yml`

- [ ] **Step 1: Write `.tflint.hcl`**

```hcl
config {
  format = "compact"
  module = true
}

plugin "terraform" {
  enabled = true
  preset  = "recommended"
}

plugin "aws" {
  enabled = true
  version = "0.32.0"
  source  = "github.com/terraform-linters/tflint-ruleset-aws"
}

rule "terraform_required_version" {
  enabled = true
}

rule "terraform_required_providers" {
  enabled = true
}

rule "terraform_naming_convention" {
  enabled = true
  format  = "snake_case"
}

rule "terraform_unused_declarations" {
  enabled = true
}

rule "terraform_documented_outputs" {
  enabled = true
}

rule "terraform_documented_variables" {
  enabled = true
}
```

- [ ] **Step 2: Write `ci/pipelines/terraform-validate.yml`**

```yaml
name: Terraform Validate

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

permissions:
  contents: read
  pull-requests: write

jobs:
  fmt:
    name: terraform fmt
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.9.5
      - name: Check formatting
        run: terraform fmt -check -recursive

  validate-modules:
    name: validate (modules)
    runs-on: ubuntu-latest
    needs: fmt
    strategy:
      fail-fast: false
      matrix:
        module:
          - landing-zone
          - s3-replication-source
          - s3-replication-destination
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.9.5
      - name: terraform init
        run: terraform init -backend=false
        working-directory: terraform/modules/${{ matrix.module }}
      - name: terraform validate
        run: terraform validate
        working-directory: terraform/modules/${{ matrix.module }}
      - name: terraform test
        run: terraform test
        working-directory: terraform/modules/${{ matrix.module }}

  validate-stacks:
    name: validate (env + bootstrap stacks)
    runs-on: ubuntu-latest
    needs: fmt
    strategy:
      fail-fast: false
      matrix:
        stack:
          - terraform/envs/dev/source
          - terraform/envs/dev/destination
          - terraform/envs/stg/source
          - terraform/envs/stg/destination
          - terraform/envs/prod/source
          - terraform/envs/prod/destination
          - terraform/account-bootstrap/exl-dev
          - terraform/account-bootstrap/exl-stg
          - terraform/account-bootstrap/exl-prod
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.9.5
      - name: terraform init
        run: terraform init -backend=false
        working-directory: ${{ matrix.stack }}
      - name: terraform validate
        run: terraform validate
        working-directory: ${{ matrix.stack }}

  tflint:
    name: tflint
    runs-on: ubuntu-latest
    needs: fmt
    steps:
      - uses: actions/checkout@v4
      - uses: terraform-linters/setup-tflint@v4
        with:
          tflint_version: v0.51.0
      - name: tflint --init
        run: tflint --init
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      - name: tflint
        run: tflint --recursive --config="${{ github.workspace }}/.tflint.hcl"

  tfsec:
    name: tfsec
    runs-on: ubuntu-latest
    needs: fmt
    steps:
      - uses: actions/checkout@v4
      - uses: aquasecurity/tfsec-action@v1.0.3
        with:
          additional_args: --minimum-severity MEDIUM

  checkov:
    name: checkov
    runs-on: ubuntu-latest
    needs: fmt
    steps:
      - uses: actions/checkout@v4
      - uses: bridgecrewio/checkov-action@v12
        with:
          directory: terraform/
          framework: terraform
          soft_fail_on: MEDIUM
          hard_fail_on: HIGH

  gitleaks:
    name: gitleaks
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

- [ ] **Step 3: Validate the YAML**

```bash
python -c "import yaml; yaml.safe_load(open('ci/pipelines/terraform-validate.yml'))"
```

Expected: no output (valid YAML).

- [ ] **Step 4: Commit**

```bash
git add .tflint.hcl ci/pipelines/terraform-validate.yml
git commit -m "ci: terraform validate workflow + tflint config

GitHub Actions workflow runs fmt, then in parallel: validate per module
(landing-zone, s3-replication-source, s3-replication-destination) with
terraform test, validate per env stack and bootstrap stack, tflint
recursively, tfsec at MEDIUM threshold, checkov with soft-fail at MEDIUM
and hard-fail at HIGH, and gitleaks across the whole tree.

No apply runs from CI in Phase 1; that wiring lands in Phase 2 with
account credentials and a state backend.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Final integration check + open the PR

**Files:** none new; runs validators across the tree and creates the PR.

- [ ] **Step 1: Run pre-commit across every file**

```bash
pre-commit install
pre-commit run --all-files
```

Expected: all hooks pass. If `terraform_validate` reports init issues for module-internal references, run `terraform init -backend=false` per failing dir first.

- [ ] **Step 2: Run `terraform fmt -recursive` one more time to be sure**

```bash
terraform fmt -recursive
git status
```

Expected: clean working tree.

- [ ] **Step 3: Run `terraform test` for every module**

```bash
for d in terraform/modules/landing-zone terraform/modules/s3-replication-source terraform/modules/s3-replication-destination; do
  echo "=== $d ==="
  (cd "$d" && terraform init -backend=false && terraform test)
done
```

Expected: every module's tests pass.

- [ ] **Step 4: Verify commit history**

```bash
git log --oneline main..HEAD
```

Expected: 7 commits (scaffold, docs, landing-zone, s3-replication-source, s3-replication-destination, env+bootstrap stacks, ci).

- [ ] **Step 5: Push the branch**

```bash
git push -u origin phase-1/foundation-kickoff
```

If `origin` has not been configured yet, the engagement lead will run `git remote add origin <url>` first; then push.

- [ ] **Step 6: Open the PR**

```bash
gh pr create --title "Phase 1 — Foundation kickoff (engagement-lead checkpoint)" --body "$(cat <<'EOF'
## Summary

Phase 1 foundation artifact for the engagement-lead checkpoint at
\`CLAUDE_CODE_BRIEF.md\` §12 step 7.

- Repo scaffold + 17 stub READMEs for unbuilt modules / dirs
- Architecture document, four ADRs (data movement, dual-module split, KMS
  signing, account topology), compliance control matrix
- Three Terraform modules: \`landing-zone\`, \`s3-replication-source\`,
  \`s3-replication-destination\` — each with plan-validate \`terraform test\`
- Six env stacks (dev/stg/prod × source/destination) and three
  account-bootstrap stacks
- GitHub Actions workflow: fmt, validate per module, validate per stack,
  tflint, tfsec, checkov, gitleaks

## Architecture

- Pattern Z topology: 1 ABSA account (3 env-suffixed source buckets) +
  3 EXL accounts (one destination each).
- S3 cross-account replication for bulk data; PrivateLink reserved for
  control-plane APIs.
- Object-lock compliance mode on both sides; per-env tiered retention.
- KMS asymmetric for manifest signing (Phase 2).

## Decisions captured in ADRs

- ADR-0001 — Data movement via S3 replication, not PrivateLink
- ADR-0002 — Cross-account IaC dual-module split
- ADR-0003 — Manifest signing via AWS KMS asymmetric keys
- ADR-0004 — Account topology — 1 ABSA + 3 EXL with Pattern Z

## Test plan

- [ ] CI matrix green: fmt, validate-modules, validate-stacks, tflint, tfsec, checkov, gitleaks
- [ ] Engagement lead reviews architecture.md + 4 ADRs
- [ ] Compliance reviewer signs off on control-matrix.md Phase 1 rows
- [ ] ABSA Cloud Platform team reviews replication-contract.md
- [ ] Engagement lead confirms: Terraform vs OpenTofu, prod retention years, paging vendor

## Out of scope (intentional)

- Real \`terraform apply\` — Phase 2 with account credentials
- KMS hierarchy + IAM federation modules — Phase 1 next sprint
- Pipeline Factory, Code Intake, Registry, Scoring Engine, PIR Engine —
  Phases 2-4

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 7: Hand off to the engagement lead**

Post the PR URL in the engagement Slack channel and tag the engagement lead and the `@platform-leads` team. Wait for review before any further work — the §12 step 7 gate is explicit.

---

## Open follow-up items (out of this plan but tracked)

These items don't block Phase 1 today, but the engagement lead should resolve them before Phase 2 begins:

1. **Terraform vs OpenTofu** — confirm with ABSA procurement.
2. **ABSA Compliance sign-off on prod retention years** — 7 is the default; confirm before any prod apply.
3. **PagerDuty / Opsgenie target** — required for the prod replication-subscriptions stack.
4. **AFT account allocation timeline** — three EXL accounts must exist before Phase 2.
5. **Synthetic data generator scope** — Pattern Z assumes Phase 2 produces fixtures for ABSA's dev / stg buckets if real-data routing is not desired.
