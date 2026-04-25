# ADR-0005: kms-hierarchy module — audit-evidence keys only

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-04-25 |
| Deciders | Engagement lead, EXL Platform Engineering |
| Consulted | EXL InfoSec |

## Context

Phase 1 sprint 2 introduces a `kms-hierarchy` Terraform module to own KMS Customer Master Keys that span multiple stacks. The architectural question: should this module own ALL CMKs across the platform (full centralisation), or only audit-evidence-grade keys that genuinely cross stack boundaries?

Three options were considered:

1. **Full centralisation.** Every CMK in the platform — including the S3 source bucket key, S3 destination bucket key, KMS asymmetric signing key, future per-service keys — flows through this module. Modules consume key ARNs as inputs.
2. **Audit-evidence keys only.** Module owns the CMKs that several stacks consume: CloudTrail bucket key, flow-logs / CW Logs key, and a Phase 2 placeholder for the manifest-signing key. Per-data-class keys (S3 source / destination) remain in their owning modules.
3. **Single account "trunk" key.** One CMK per account named `audit-evidence-{env}` that covers CloudTrail + flow logs + future Config snapshots. Cheaper, but every consumer shares the same key.

## Decision

Option 2 — audit-evidence keys only.

The module owns:
- `${env}-cloudtrail-bucket` — used by the CloudTrail S3 bucket SSE configuration
- `${env}-flow-logs-cw` — used by VPC flow-logs CW Log group AND the CloudTrail event stream CW Log group (both are CW Logs encryption use cases at the same compliance grade)
- `manifest_signing_key_arn` — placeholder output returning `null` until Phase 2 implements ADR-0003

The module does NOT own:
- S3 source bucket key (in `s3-replication-source`)
- S3 destination bucket key (in `s3-replication-destination`)
- Per-data-class keys for stateful workloads added in later phases

## Consequences

### Positive

- Clean separation of concerns. Auditors can point to a single module for audit-evidence-grade encryption.
- Per-data-class key lifecycle (rotation, key policy changes) is owned by the module that consumes the key — no PR-back bottleneck through the central kms module.
- Module surface stays small. Two active resources today, one placeholder. Future audit-evidence keys (e.g. AWS Config snapshot key in Phase 4) extend this module.

### Negative

- Two patterns for KMS in the codebase: centralised (this module) and module-owned (s3-replication-*). Convention drift is possible if future modules don't follow the convention.
- Mitigation: code review enforces the split. The convention is documented in this ADR and referenced from `kms-hierarchy/README.md`.

## Alternatives considered

1. **Full centralisation (Option 1).** Rejected. Centralisation creates a PR-back bottleneck for every key-policy change downstream modules need. The audit benefit ("all keys live here") doesn't outweigh the operational cost. Different consumer modules legitimately have different key-policy needs (e.g. the S3 destination key needs to grant a cross-account replication role; that's not a generic concern).
2. **Single account "trunk" key (Option 3).** Rejected. SR 11-7 reviewers expect blast-radius separation between trail logs and flow logs at the key level — a single trunk key violates that expectation. Cost difference (~$2/mo per account) does not justify the audit risk.

## Compliance mapping

| Control | Reference |
| --- | --- |
| ISO 27001 A.10.1 — cryptographic controls | Both CMKs have rotation enabled and tightly scoped key policies |
| POPIA s19 — security safeguards | Audit-evidence at rest under customer-managed keys |
| SOC 2 CC6.1 — logical access | Service-principal scoped grants with aws:SourceArn / EncryptionContext conditions |
| SR 11-7 III.4 — model implementation evidence | Per-purpose CMKs with separation between trail logs and CW Logs encryption |
