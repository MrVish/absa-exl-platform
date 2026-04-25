# Plan-only test fixture — uses mock_provider so the AWS provider's data
# sources don't make real API calls. Real apply uses the caller's provider.
mock_provider "aws" {
  mock_data "aws_caller_identity" {
    defaults = {
      account_id = "222222222222"
    }
  }
}

variables {
  bucket_name                 = "exl-model-landing-dev"
  env                         = "dev"
  retention_years             = 1
  source_replication_role_arn = "arn:aws:iam::111111111111:role/dev-s3-replication-role"
  source_account_id           = "111111111111"
  alarm_threshold_seconds     = 900
  tags = {
    cost_center = "ml-platform"
    module      = "s3-replication-destination"
  }
}

run "bucket_has_object_lock_compliance_mode" {
  command = plan

  assert {
    condition     = aws_s3_bucket_object_lock_configuration.this.rule[0].default_retention[0].mode == "COMPLIANCE"
    error_message = "Object lock must use COMPLIANCE mode"
  }
}

run "kms_key_rotation_is_enabled" {
  command = plan

  assert {
    condition     = aws_kms_key.this.enable_key_rotation == true
    error_message = "Destination KMS key must have rotation enabled"
  }
}

run "replication_latency_alarm_exists" {
  command = plan

  assert {
    condition     = aws_cloudwatch_metric_alarm.replication_latency.threshold == 900
    error_message = "ReplicationLatency alarm threshold must equal alarm_threshold_seconds"
  }
}

run "replication_latency_alarm_uses_correct_metric" {
  command = plan

  assert {
    condition     = aws_cloudwatch_metric_alarm.replication_latency.metric_name == "ReplicationLatency"
    error_message = "Latency alarm must watch ReplicationLatency metric"
  }
}

run "failed_replication_alarm_fires_on_any_failure" {
  command = plan

  assert {
    condition = (
      aws_cloudwatch_metric_alarm.failed_replication.threshold == 0 &&
      aws_cloudwatch_metric_alarm.failed_replication.comparison_operator == "GreaterThanThreshold"
    )
    error_message = "FailedReplication alarm must fire when count > 0"
  }
}

run "sns_topic_exists_and_is_kms_encrypted" {
  command = plan

  assert {
    condition     = aws_sns_topic.replication_alerts.kms_master_key_id == "alias/aws/sns"
    error_message = "SNS topic must be encrypted with the AWS-managed SNS key"
  }
}

# Removed runs that depended on strcontains() over computed policy attributes:
#   - "bucket_policy_grants_source_replication_role"
#   - "null_source_role_omits_kms_grant_in_policy"
#   - "non_null_source_role_includes_kms_and_bucket_grants"
#
# Under mock_provider, aws_kms_key.this.policy and aws_s3_bucket_policy.this.policy
# are treated as computed-unknown at plan time, so strcontains() on them fails to
# evaluate. Switching the runs to command = apply trips on mocked SNS topic ARN
# validation in CloudWatch alarms (alarm_actions ARN regex rejects the
# random-string mock value).
#
# The chicken-and-egg null/non-null behaviour is verifiable by code review —
# see kms.tf local.source_role_kms_grant and policy.tf local.source_role_bucket_grant
# (both gated on var.source_replication_role_arn != null). Phase 2 (real apply)
# re-introduces stronger versions of these tests once the mocked-ARN regex
# constraint is lifted by using ephemeral AWS test accounts.
