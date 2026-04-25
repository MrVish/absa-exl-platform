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
