# `kms-hierarchy` Terraform module

Audit-evidence-grade KMS keys shared across stacks within a single EXL account. Owns the CMKs for the CloudTrail S3 bucket and the CloudWatch Log groups that hold VPC flow logs and CloudTrail event streams. Per-data-class keys (S3 source / destination buckets) remain in their owning modules and are NOT centralised here. Rationale: [ADR-0005](../../../docs/adr/0005-kms-hierarchy-audit-evidence-only.md).

## What this module does NOT own

- S3 source bucket key — owned by `s3-replication-source`
- S3 destination bucket key — owned by `s3-replication-destination`
- VPC data subnet KMS keys — owned by their consuming modules (Phase 2+)

## Usage

```hcl
module "kms_hierarchy" {
  source = "../../modules/kms-hierarchy"

  env = "dev"

  tags = {
    cost_center = "ml-platform"
  }
}

# Use outputs:
resource "aws_s3_bucket_server_side_encryption_configuration" "trail" {
  bucket = aws_s3_bucket.cloudtrail.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = module.kms_hierarchy.cloudtrail_bucket_key_arn
    }
    bucket_key_enabled = true
  }
}
```

## Inputs

See `variables.tf`. Required: `env`, `tags`.

## Outputs

See `outputs.tf`. Notable: `cloudtrail_bucket_key_arn`, `flow_logs_cw_key_arn`, `manifest_signing_key_arn` (Phase 2 placeholder, returns null today).

## Tests

`terraform test` from this directory. Plan-validate only. CI runs the same.

## Compliance mapping

| Control | Where |
| --- | --- |
| ISO 27001 A.10.1 — cryptographic controls | Both keys with rotation enabled, audit-friendly key policies |
| POPIA s19 — security safeguards | Audit-evidence at rest under customer-managed keys |
| SOC 2 CC6.1 — logical access | Service-principal-scoped key policies with aws:SourceArn (CloudTrail) and EncryptionContext (CW Logs) conditions |
| SR 11-7 III.4 — model implementation evidence | CloudTrail and flow logs encrypted under separate CMKs for blast-radius separation |
