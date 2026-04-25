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

This module supports a two-phase bootstrap because AWS validates IAM principals in KMS key policies at PUT time — passing a non-existent source role ARN would fail with `MalformedPolicyDocumentException`. The fix: `var.source_replication_role_arn` is nullable. When null, the module omits the source-role statements from both the KMS key policy and the bucket policy.

**Phase 1 (first destination apply, source role does not exist yet):**
- Caller passes `source_replication_role_arn = null`.
- KMS key, bucket, alarms, SNS topic all provision.
- KMS key policy contains only the `AllowAccountRoot` statement.
- Bucket policy contains only the `AllowSourceAccountReadBucketVersioning` statement.
- **S3 replication writes from the source side will fail in this state.** This is expected — replication does not begin until Phase 3 grants the source role its required permissions on the destination KMS key and bucket.

**Phase 2 (source side applies):**
- Source side provisions the replication role + bucket + KMS key + replication configuration.
- Source side outputs `replication_role_arn`.

**Phase 3 (destination re-apply with the real source role ARN):**
- Caller passes `source_replication_role_arn = module.replication_source.replication_role_arn` (or via terraform_remote_state).
- KMS key policy is updated to add `AllowSourceReplicationRoleEncrypt`.
- Bucket policy is updated to add `AllowSourceReplicationRoleWrite`.

After Phase 3, ongoing changes to either side can apply in any order; the dependency direction is symmetric once both sides exist.

## Inputs

See `variables.tf`. Required: `bucket_name`, `env`, `source_account_id`, `tags`. Optional / nullable: `source_replication_role_arn` (default null — see Apply order section).

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
