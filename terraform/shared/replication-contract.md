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
