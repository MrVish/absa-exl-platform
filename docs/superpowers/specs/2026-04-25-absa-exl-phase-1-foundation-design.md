# ABSA × EXL Model Hosting & Delivery Operations — Phase 1 Foundation Design

| Field | Value |
| --- | --- |
| Date | 2026-04-25 |
| Engagement | ABSA × EXL Model Hosting & Delivery Operations (5-month build, 10-FTE pod) |
| Phase | 1 — Foundation kickoff |
| Authoring source | `CLAUDE_CODE_BRIEF.md` §12 today's task list |
| Checkpoint gate | §12 step 7 — engagement-lead review before Pipeline Factory begins |
| Status | Design approved; awaiting written-spec review before implementation plan |

## TL;DR

Today builds the engagement-lead-checkpoint artifact: a greenfield repo scaffold
for the ABSA × EXL Model Hosting platform, plus the architecture document, four
ADRs, three Terraform modules, and a CI validation pipeline. ABSA hands
model-ready data to EXL via S3 cross-account replication — explicitly not
PrivateLink. Account topology is one ABSA account holding three env-suffixed
source buckets, replicating Pattern-Z to three EXL accounts (`exl-dev`,
`exl-stg`, `exl-prod`). The Terraform modules split along the
cross-account boundary: `s3-replication-source` deploys into ABSA, the
`s3-replication-destination` and `landing-zone` modules deploy into EXL.
Today's scope is plan-validate testing only; apply-time tests and the
Pipeline Factory wait for Phase 2.

## 1. Context

ABSA Group needs to productionise developer-authored SAS / Python models.
EXL is delivering a 5-month build of an audit-ready ML hosting platform on
AWS for an initial cohort of 10 models. The brief at
`CLAUDE_CODE_BRIEF.md` describes two operating tracks (model onboarding /
pipeline factory + scheduled scoring execution) and a four-phase plan. This
specification covers Phase 1 — Foundation only. Specifically, it covers the
work in `CLAUDE_CODE_BRIEF.md` §12 ("How to start") that runs before the
hard checkpoint at §12 step 7. The KMS-hierarchy and IAM-federation modules
listed in §11 Phase 1 are deliberately deferred to the next sprint of
Phase 1; they are out of scope for today.

## 2. Decisions locked this session

Six clarifying questions were asked during brainstorming and answered by
the engagement lead. The chosen options are recorded here so an auditor or
new engineer can reconstruct the design lineage without re-running the
conversation.

| # | Topic | Choice | Rationale | Captured by |
| - | --- | --- | --- | --- |
| 1 | Cross-account IaC scope | Split modules per side (Option C) | Each side owns its IaC; module split mirrors operational ownership and aligns with "good connect with ABSA" working pattern | ADR-0002 |
| 2 | Object identity convention | Sidecar manifest (`manifest.json` next to data) | Signed, hashable, schema-extensible; survives S3 path changes; fits SR 11-7 evidence patterns | ADR-0001 (with manifest schema in Phase 2) |
| 3 | Alert chain on RTC breach | SNS topic owned by module, subscriptions per env (Option C) | Module portable; per-env subscriptions avoid baked-in vendor secrets; non-prod can run with email subscribers only | ADR-0001 |
| 4 | Object lock retention | Per-env tiered, default 7 years prod (Option C) | Bank act + SARB GOI 5 compliance for prod; dev/stg avoid the compliance-mode "lock-trap" | ADR-0001 |
| 5 | Pipeline Factory generator runtime | Dual-mode — local for dev, CI canonical (Option C) | Fast iteration loop for the Industrialization Team; only signed-by-CI artifacts reach the registry | (Phase 2 ADR) |
| 6 | Manifest signing primitive | AWS KMS asymmetric (Option A) | AWS-native, CloudTrail-logged, single-vendor trust root, public key publishable for offline verification | ADR-0003 |

A seventh consequential clarification — **AWS account topology** — was
made during the design-section reviews and is captured separately in §3.

## 3. Account topology

ABSA allocates a single AWS account. EXL follows its standard three-account
dev/stg/prod model. Pattern Z is adopted: ABSA's single account hosts three
env-suffixed source buckets, each replicating to its matching EXL account.

```
ABSA account (1)                                EXL accounts (3)
┌───────────────────────────────┐              ┌────────────────────┐
│ absa-model-handoff-dev   ─────┼─── replica ──▶│ exl-dev            │
│   KMS: alias/handoff-dev      │              │   landing-zone     │
│   replication role (dev)      │              │   landing bucket   │
├───────────────────────────────┤              ├────────────────────┤
│ absa-model-handoff-stg   ─────┼─── replica ──▶│ exl-stg            │
├───────────────────────────────┤              ├────────────────────┤
│ absa-model-handoff-prod  ─────┼─── replica ──▶│ exl-prod           │
└───────────────────────────────┘              └────────────────────┘
```

Implications:

- ABSA-side resources (bucket, KMS, replication role) are env-isolated even
  inside a single account — a misrouted dev rule cannot decrypt prod data.
- EXL-side strong isolation comes "for free" from three separate AWS accounts.
- ABSA's account-level controls (CloudTrail, GuardDuty, password policy,
  Organization SCPs) are owned by ABSA's central platform team. EXL's
  Terraform footprint inside ABSA is bounded to the bucket + KMS key +
  replication role per env. Assumed ABSA-side baseline is captured in
  `terraform/shared/replication-contract.md`.
- EXL-side account-singleton resources (CloudTrail, GuardDuty, Security
  Hub, password policy, IAM permissions boundaries) live in
  `terraform/account-bootstrap/exl-{env}/` and apply once per EXL account.
- Per-env workload resources (VPC, subnets, KMS data keys, S3 destination
  bucket) live in `terraform/envs/{env}/destination/`.

## 4. Repo layout — what gets created today

The directory tree below shows files that are written by hand today (marked
"WRITTEN") versus files that are placeholder stubs (single-line README
indicating the phase in which they will be built).

```
absa-exl-platform/
├── README.md                                          # WRITTEN — repo landing page, two-track summary
├── CLAUDE_CODE_BRIEF.md                               # exists — preserved verbatim
├── ABSA_EXL_Model_Hosting_Proposal_v3.0.pptx          # exists — preserved
├── .gitignore                                         # WRITTEN — tf/state/.terraform/.tfstate*/etc.
├── .editorconfig                                      # WRITTEN — LF, utf-8, 2-space tf, 4-space py
├── .pre-commit-config.yaml                            # WRITTEN — terraform_fmt, validate, tflint, tfsec, gitleaks
├── CODEOWNERS                                         # WRITTEN — @platform-leads on terraform/modules/**
├── docs/
│   ├── architecture.md                                # WRITTEN — two-track + S3 replication narrative + topology
│   ├── adr/
│   │   ├── 0001-data-movement-s3-replication.md       # WRITTEN
│   │   ├── 0002-cross-account-iac-dual-module-split.md # WRITTEN
│   │   ├── 0003-manifest-signing-kms-asymmetric.md    # WRITTEN
│   │   └── 0004-account-topology-1-absa-3-exl.md      # WRITTEN
│   ├── runbooks/.gitkeep                              # Phase 4
│   ├── compliance/control-matrix.md                   # WRITTEN — header + Phase 1 rows only
│   └── superpowers/specs/
│       └── 2026-04-25-absa-exl-phase-1-foundation-design.md   # this document
├── terraform/
│   ├── modules/
│   │   ├── landing-zone/                              # WRITTEN, full module + tests
│   │   ├── s3-replication-source/                     # WRITTEN, full (deploys into ABSA account)
│   │   ├── s3-replication-destination/                # WRITTEN, full (deploys into EXL account)
│   │   ├── kms-hierarchy/README.md                    # stub: "Phase 1, next sprint"
│   │   ├── iam-federation/README.md                   # stub: "Phase 1, next sprint"
│   │   ├── sagemaker-domain/README.md                 # stub: "Phase 3"
│   │   ├── eks-scoring/README.md                      # stub: "Phase 3"
│   │   ├── pipeline-registry/README.md                # stub: "Phase 2"
│   │   ├── pir-engine/README.md                       # stub: "Phase 4"
│   │   └── observability/README.md                    # stub: "Phase 4"
│   ├── envs/
│   │   ├── dev/
│   │   │   ├── source/{main.tf, variables.tf, locals.tf, terraform.tfvars}            # provider → ABSA account
│   │   │   └── destination/{main.tf, variables.tf, locals.tf, replication-subscriptions.tf, terraform.tfvars}  # provider → exl-dev
│   │   ├── stg/
│   │   │   ├── source/{...}
│   │   │   └── destination/{...}
│   │   └── prod/
│   │       ├── source/{...}
│   │       └── destination/{...}
│   ├── account-bootstrap/
│   │   ├── exl-dev/{main.tf, variables.tf, terraform.tfvars}                          # CloudTrail/GuardDuty/SecHub/IAM-baseline
│   │   ├── exl-stg/{...}
│   │   └── exl-prod/{...}
│   └── shared/
│       └── replication-contract.md                                                    # WRITTEN — cross-account wiring spec
├── pipeline-factory/README.md                         # stub: "Phase 2"
├── code-intake/README.md                              # stub: "Phase 2"
├── pir-engine/README.md                               # stub: "Phase 4"
├── scoring-engine/README.md                           # stub: "Phase 3"
├── registry/README.md                                 # stub: "Phase 2"
└── ci/
    ├── pipelines/
    │   └── terraform-validate.yml                     # WRITTEN — GH Actions: fmt/validate/tflint/tfsec/test on PR
    └── policies/.gitkeep                              # OPA / Sentinel — Phase 2
```

Approximate counts: ~25 hand-written files of substance, ~40 placeholder /
stub files, three full Terraform modules with their tests.

## 5. Terraform module contracts

Three modules are written in full today. The contracts below define the
public interface (variables and outputs); the resource list summarises what
each module owns.

### 5.1 `terraform/modules/landing-zone/`

This module is a **workload-account landing zone**, not an organisation-level
landing zone. It does not manage AWS Organizations resources; account
creation is owned by ABSA's central platform team via Control Tower / AFT.

Inputs:

- `env` — one of `dev`, `stg`, `prod` (validated). The same identifier is used across all three modules to avoid translation glue.
- `region`
- `vpc_cidr` — non-overlapping per env (e.g. `10.40.0.0/20` dev, `10.40.16.0/20` stg, `10.40.32.0/20` prod)
- `availability_zones` (default 3)
- `transit_gateway_id` — string ARN passed in from upstream platform
- `enable_guardduty` (default `true`)
- `enable_security_hub` (default `true`)
- `flow_logs_retention_days` (default 365 prod, 30 non-prod via env tfvars)
- `tags` — map; the module ensures `env`, `module`, `cost_center` are present

Resources owned:

- 3-tier VPC: public / private / data subnets across the configured AZs
- Internet gateway, NAT gateways (1 per AZ in prod, 1 total in non-prod), route tables
- Transit gateway attachment to the upstream TGW
- VPC flow logs to CloudWatch Logs and S3
- GuardDuty detector (when enabled)
- Security Hub enable + AWS Foundational Security Best Practices standard
- Account-level password policy
- Baseline IAM permissions boundary policy that env-scoped roles can attach (forbids cross-env resource access via `aws:ResourceTag/env` deny-when-mismatched conditions). Note: root MFA enforcement is owned by ABSA's central platform team via SCP at the OU level — the module documents the assumption but does not provision it.

Outputs:

- `vpc_id`
- `private_subnet_ids`
- `data_subnet_ids`
- `flow_logs_log_group_arn`
- `guardduty_detector_id`

Tests (`tests/landing_zone.tftest.hcl`): plan-validate against a dev fixture; assert subnet count, NAT GW count, flow-logs enabled, GuardDuty detector present, Security Hub enabled.

### 5.2 `terraform/modules/s3-replication-source/`

Deploys into ABSA's AWS account. Provisions the source-side resources for one env.

Inputs:

- `bucket_name`
- `env` — one of `dev`, `stg`, `prod`
- `retention_years` (default 7)
- `prefix_filter` (default `"model-ready/"`)
- `replication_time_control_enabled` (default `true`)
- `delete_marker_replication` (default `false`)
- `destination_bucket_arn`
- `destination_kms_key_arn`
- `destination_account_id`
- `tags`

Resources:

- `aws_s3_bucket` — versioning + object-lock compliance mode + default retention from `var.retention_years`
- `aws_kms_key` — symmetric SSE-KMS with rotation enabled, key policy granting EXL replication role `kms:Decrypt` on source-side reads
- `aws_iam_role` — replication role + policies (S3 read on source, KMS decrypt on source, S3 replicate on destination, KMS encrypt on destination)
- `aws_s3_bucket_replication_configuration` — RTC enabled with 15-minute SLA, prefix filter, dest KMS encryption, delete-marker replication off

Outputs:

- `bucket_arn`
- `kms_key_arn`
- `replication_role_arn`
- `replication_metric_namespace`

Tests (`tests/source.tftest.hcl`): assert RTC enabled with 15-minute threshold, prefix filter, object-lock compliance mode, KMS rotation true.

### 5.3 `terraform/modules/s3-replication-destination/`

Deploys into the EXL env account. Provisions the destination-side bucket and the replication-lag observability surface.

Inputs:

- `bucket_name`
- `env`
- `retention_years` (default 7)
- `source_replication_role_arn`
- `source_account_id`
- `prefix_filter` (default `"model-ready/"`)
- `alarm_threshold_seconds` (default 900 = 15-minute RTC)
- `tags`

Resources:

- `aws_s3_bucket` — versioning + object-lock compliance mode + default retention
- `aws_kms_key` — symmetric, rotation enabled, key policy granting source replication role `kms:Encrypt` and `kms:GenerateDataKey`
- Bucket policy — grants source role `s3:ReplicateObject`, `s3:ReplicateDelete`, `s3:ReplicateTags`
- `aws_sns_topic` — owned by module, no subscriptions (those live in `envs/{env}/destination/replication-subscriptions.tf`)
- `aws_cloudwatch_metric_alarm` — `AWS/S3 ReplicationLatency` greater than `var.alarm_threshold_seconds`; alarm action is the SNS topic ARN
- `aws_cloudwatch_metric_alarm` — `FailedReplication` greater than 0 (paranoid alarm)

Outputs:

- `bucket_arn`
- `kms_key_arn`
- `sns_topic_arn`
- `replication_metric_alarm_arn`
- `failed_replication_alarm_arn`

Tests (`tests/destination.tftest.hcl`): assert latency alarm threshold = 900s, FailedReplication alarm exists, SNS topic exists with no subscriptions, KMS rotation true, bucket policy grants source account.

### 5.4 `terraform/shared/replication-contract.md`

Markdown specification listing exactly which outputs from
`s3-replication-source` feed which inputs of `s3-replication-destination`
and vice versa, with example wiring via `terraform_remote_state` data
sources. This is the contract artifact that ABSA's IaC team and EXL's IaC
team both reference when applying their respective sides. The contract
also documents the assumed ABSA-side account-level baseline (CloudTrail,
GuardDuty, etc.) that is owned by ABSA's central platform team.

## 6. Testing strategy

### 6.1 Static layer

Runs in pre-commit hook and in CI:

- `terraform fmt -check -recursive`
- `terraform init -backend=false && terraform validate` per module and per env stack
- `tflint` with the AWS ruleset plus a custom rule asserting every resource name is prefixed `${var.env}-`
- `tfsec` — severity ≥ MEDIUM fails the build
- `checkov` — framework `terraform`; severity ≥ HIGH fails, MEDIUM warns
- `gitleaks` — no AWS keys or IAM secrets in commits

### 6.2 Module unit layer

Each module owns `tests/{module}.tftest.hcl` files using Terraform's native
test framework. Plan-validate only — no apply. Coverage rule: every variable
that has a default gets one positive test (default works) and one negative
test (override is honoured). Variables without defaults get a test that
fails clearly when omitted.

### 6.3 Apply-time integration tests

Deferred to Phase 2. They require either ephemeral AWS accounts (preferred)
or LocalStack Pro. Today's plan-validate is sufficient for the
engagement-lead checkpoint.

## 7. CI strategy

Single GitHub Actions workflow at `ci/pipelines/terraform-validate.yml`.

Trigger: `pull_request` on any branch.

The workflow has two job matrices. The first iterates over the three full
modules under `terraform/modules/`. The second iterates over the env stacks
under `terraform/envs/{dev,stg,prod}/{source,destination}/` and the
account-bootstrap stacks under `terraform/account-bootstrap/exl-{dev,stg,prod}/`.
Both matrices run the same step list:

1. `actions/checkout`
2. `hashicorp/setup-terraform`
3. `terraform fmt -check -recursive` against the whole repo
4. `terraform init -backend=false` for the matrix module
5. `terraform validate`
6. `terraform test`
7. `terraform-linters/setup-tflint` and `tflint --init && tflint`
8. `aquasecurity/tfsec-action`
9. `bridgecrewio/checkov-action`

A separate job runs `gitleaks/gitleaks-action` once for the whole repo.

Branch protection on `main`:

- The `validate` workflow must pass
- One review from CODEOWNERS (`@platform-leads` on `terraform/modules/**`)
- Linear history; squash-only merges
- Conventional-commit subject (regex check in CI)

No `terraform apply` runs from CI in Phase 1. Apply will be wired in
Phase 2 once the team has account credentials and a state backend.

State backend assumption: S3 plus DynamoDB lock per EXL account. Not
provisioned today because nothing applies today;
`terraform/account-bootstrap/exl-{env}/state-backend.tf` is the placeholder
file each bootstrap stack will populate when account access lands.

## 8. ADRs to be authored today

Four ADRs capture the irreversible decisions made in this brainstorm:

| ID | Title | One-line summary |
| - | --- | --- |
| 0001 | Data movement via S3 replication, not PrivateLink | Bulk model-ready data crosses the trust boundary via S3 cross-account replication; PrivateLink is reserved for control-plane API calls and score delivery. Includes the manifest, retention, RTC, and alert-chain decisions folded in. |
| 0002 | Cross-account IaC — dual-module split | The `s3-replication` module is split into `s3-replication-source` (deploys into ABSA) and `s3-replication-destination` (deploys into EXL). Each side owns its own Terraform state; they wire via a shared markdown contract. |
| 0003 | Manifest signing via AWS KMS asymmetric keys | Code-intake and Pipeline-Factory manifests are signed by the EXL CI pipeline using KMS asymmetric CMKs. Verifiable in CloudTrail or offline against a published public key. |
| 0004 | Account topology — 1 ABSA + 3 EXL with Pattern Z | One ABSA account holds three env-suffixed source buckets; three EXL accounts hold one destination each. Replication is env-symmetric: each ABSA source replicates only to its matching EXL env. |

ADR template follows MADR 3.0 (status / context / decision / consequences /
alternatives considered).

## 9. Out-of-scope today

| Item | Phase | Reason |
| --- | --- | --- |
| `kms-hierarchy/` module | 1 (next sprint) | Not in §12 today's task list |
| `iam-federation/` module | 1 (next sprint) | Not in §12 today's task list |
| Pipeline Factory, Code Intake, Registry | 2 | Section 4 ships stub READMEs only |
| Scoring Engine, SageMaker Domain, EKS Scoring | 3 | Stub READMEs only |
| PIR Engine, Observability, DR runbooks | 4 | Stub READMEs only |
| Manifest signing implementation | 2 | ADR-0003 captures the decision today |
| Synthetic data generator (for dev/stg) | 2 | Pattern Z makes this a Phase 2 dependency |
| Real `terraform apply` against AWS | 2 | No account credentials yet |
| LocalStack / ephemeral-account integration tests | 2 | Same |
| OPA / Sentinel policy bundles in `ci/policies/` | 2 | `.gitkeep` only today |
| PagerDuty / Opsgenie subscriptions | per-env | env stacks expose stubs only |
| Compliance evidence-pack assembly | 4 | `control-matrix.md` Phase 1 rows only |

## 10. Open items to flag for the engagement lead

These items don't block today's work but warrant a quick conversation before
or shortly after the §12 step 7 checkpoint.

1. **Terraform vs OpenTofu.** The brief defaults us to Terraform (HashiCorp
   BSL). Some bank procurement teams have moved to OpenTofu (MPL-2.0).
   Worth confirming with ABSA procurement before the module count grows.
2. **ABSA Compliance sign-off on prod retention years.** The default of
   7 years is the safe baseline; if ABSA's internal MRMG policy mandates
   10, we want to know now (compliance-mode S3 lets you extend retention
   but not recreate buckets in place).
3. **PagerDuty / Opsgenie integration target.** The destination module
   exposes an SNS topic; the env stacks need to know which paging platform
   subscribes. Email-only is fine for dev/stg but prod needs an answer
   before first live data flows.
4. **AFT account allocation timeline.** The three EXL accounts must exist
   before Phase 2 can apply anything. Confirm dates with ABSA's central
   platform team.
5. **Synthetic data generator scope.** Pattern Z assumes ABSA provides
   per-env source buckets even for dev/stg. If ABSA's dev/stg buckets will
   only ever receive synthetic data, EXL needs a generator for it —
   designed in Phase 2.

## 11. Phase 1 today — deliverables manifest

Concrete artifacts produced before the §12 step 7 checkpoint:

- [ ] Repo scaffold per §4 of this spec
- [ ] `README.md`
- [ ] `.gitignore`, `.editorconfig`, `.pre-commit-config.yaml`, `CODEOWNERS`
- [ ] `docs/architecture.md`
- [ ] `docs/adr/0001-data-movement-s3-replication.md`
- [ ] `docs/adr/0002-cross-account-iac-dual-module-split.md`
- [ ] `docs/adr/0003-manifest-signing-kms-asymmetric.md`
- [ ] `docs/adr/0004-account-topology-1-absa-3-exl.md`
- [ ] `docs/compliance/control-matrix.md` (Phase 1 rows only)
- [ ] `terraform/modules/landing-zone/` — full module + tests + README
- [ ] `terraform/modules/s3-replication-source/` — full module + tests + README
- [ ] `terraform/modules/s3-replication-destination/` — full module + tests + README
- [ ] `terraform/envs/{dev,stg,prod}/{source,destination}/` — env stack scaffolds
- [ ] `terraform/account-bootstrap/exl-{dev,stg,prod}/` — bootstrap stack scaffolds
- [ ] `terraform/shared/replication-contract.md`
- [ ] `terraform/modules/{kms-hierarchy,iam-federation,sagemaker-domain,eks-scoring,pipeline-registry,pir-engine,observability}/README.md` — stubs
- [ ] `pipeline-factory/`, `code-intake/`, `pir-engine/`, `scoring-engine/`, `registry/` — top-level stub READMEs
- [ ] `ci/pipelines/terraform-validate.yml`
- [ ] `ci/policies/.gitkeep`

Branch / commit strategy: `phase-1/foundation-kickoff` off `main`; one
squash-merged PR for engagement-lead review at the §12 step 7 gate. Inside
the branch, commits are organised by logical chunk (scaffold; arch + ADRs;
landing-zone; s3-replication-source; s3-replication-destination; ci) for
reviewer ergonomics.
