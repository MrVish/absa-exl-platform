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
