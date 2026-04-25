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

- Workload-account landing zone (VPC, subnets, TGW attachment, flow logs (KMS-encrypted), permissions boundary policy) for each EXL account.
- S3 replication module pair (source + destination).
- ADRs and architecture documentation.
- CI validation pipeline (plan-validate, no apply).

KMS-hierarchy and IAM-federation modules built in Phase 1 sprint 2 (see `docs/adr/0005-kms-hierarchy-audit-evidence-only.md`). Account-singleton resources (CloudTrail, GuardDuty, Security Hub, password policy) live in `terraform/account-bootstrap/exl-{env}/`. Pipeline Factory, Code Intake, Registry, Scoring Engine, and PIR Engine follow in later phases per the brief's plan.
