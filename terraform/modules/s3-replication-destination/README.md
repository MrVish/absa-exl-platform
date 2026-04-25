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

This module applies before the source-side module exists. On the first apply (Phase 1 of the bootstrap in [`terraform/shared/replication-contract.md`](../../shared/replication-contract.md)):

1. Pass any plausible-looking ARN as `var.source_replication_role_arn` — for example, `arn:aws:iam::<source_account_id>:role/placeholder-replication-role`. The bucket itself, KMS CMK, alarms, and SNS topic will provision successfully.
2. **Known gap (Phase 2 fix):** AWS KMS validates IAM principals in key policies at PUT time. If the placeholder role ARN does not exist when the destination first applies, the `AllowSourceReplicationRoleEncrypt` KMS key policy statement will be rejected with `MalformedPolicyDocumentException`.
3. **Workaround for Phase 1 plan-validate:** plan-validate testing does not invoke the AWS API, so this gap surfaces only at apply time. Phase 1's deliverable is the module + tests; Phase 2 will refactor `source_replication_role_arn` to be optional (`default = null`) and conditionally include the KMS statement so the bootstrap is genuinely two-phase-applicable. For now, document this constraint and defer the apply-time work.
4. After the source side has applied (Phase 2 of bootstrap), pass the real `var.source_replication_role_arn` and re-apply. The KMS key policy and bucket policy will both be updated to grant the actual source role.

The bucket policy half of this is not affected — S3 accepts unknown principal ARNs in bucket policies and resolves them lazily. Only the KMS key policy validation is the apply-time blocker.

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
