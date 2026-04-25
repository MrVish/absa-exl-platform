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
