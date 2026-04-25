# ADR-0002: Cross-account IaC dual-module split

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-04-25 |
| Deciders | Engagement lead, EXL Platform Engineering |
| Consulted | ABSA Cloud Platform team |

## Context

The brief at `CLAUDE_CODE_BRIEF.md` §4 lists a single `terraform/modules/s3-replication/` module taking `source_bucket_name` (in ABSA) and `destination_bucket_name` (in EXL) as inputs. Three interpretations were possible:

1. **Single-state, dual-account module.** This repo owns Terraform for both sides; one `terraform apply` provisions both accounts via assumed-role.
2. **EXL-side-only module with a contract to ABSA.** This repo provisions EXL-side resources; ABSA's IaC team owns the source-side module.
3. **Both, with module split.** Two modules, one per side, each with its own state, wired via a shared contract.

The engagement lead confirmed that EXL has a working relationship with ABSA's cloud platform team that supports option 3 — EXL can ship a Terraform module that ABSA will deploy into ABSA's own account, and vice versa, with each side owning the apply.

## Decision

Split the canonical `s3-replication` module into two siblings:

- `terraform/modules/s3-replication-source/` — deployed into the ABSA account by ABSA's IaC team. Provisions the source bucket, source-side KMS CMK, replication role, and replication configuration.
- `terraform/modules/s3-replication-destination/` — deployed into the matching EXL env account by EXL's IaC team. Provisions the destination bucket, destination-side KMS CMK, bucket policy granting the replication role, an SNS topic, and CloudWatch alarms on `ReplicationLatency` and `FailedReplication`.

Each side keeps its own Terraform state. Outputs from the source module feed inputs of the destination module (and vice versa for KMS and role ARNs); the wiring is documented in [`terraform/shared/replication-contract.md`](../../terraform/shared/replication-contract.md) and exchanged via `terraform_remote_state` data sources or a shared variable file once both apply destinations exist.

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
