variables {
  bucket_name              = "absa-model-handoff-dev"
  env                      = "dev"
  retention_years          = 1
  prefix_filter            = "model-ready/"
  destination_bucket_arn   = "arn:aws:s3:::exl-model-landing-dev"
  destination_kms_key_arn  = "arn:aws:kms:af-south-1:222222222222:key/abc-123"
  destination_account_id   = "222222222222"
  tags = {
    cost_center = "ml-platform"
    module      = "s3-replication-source"
  }
}

run "bucket_has_object_lock_compliance_mode" {
  command = plan

  assert {
    condition     = aws_s3_bucket_object_lock_configuration.this.rule[0].default_retention[0].mode == "COMPLIANCE"
    error_message = "Object lock must use COMPLIANCE mode for audit-grade immutability"
  }
}

run "default_retention_matches_var" {
  command = plan

  variables {
    retention_years = 7
  }

  assert {
    condition     = aws_s3_bucket_object_lock_configuration.this.rule[0].default_retention[0].years == 7
    error_message = "Default retention must equal var.retention_years"
  }
}

run "kms_key_rotation_is_enabled" {
  command = plan

  assert {
    condition     = aws_kms_key.this.enable_key_rotation == true
    error_message = "Source KMS key must have rotation enabled"
  }
}

run "replication_uses_rtc_with_15_minute_metric" {
  command = plan

  assert {
    condition = (
      aws_s3_bucket_replication_configuration.this.rule[0].destination[0].replication_time[0].time[0].minutes == 15
    )
    error_message = "Replication time control must be set to 15 minutes"
  }
}

run "prefix_filter_is_applied" {
  command = plan

  assert {
    condition     = aws_s3_bucket_replication_configuration.this.rule[0].filter[0].prefix == "model-ready/"
    error_message = "Replication rule must filter on the model-ready/ prefix"
  }
}

run "delete_marker_replication_disabled_by_default" {
  command = plan

  assert {
    condition     = aws_s3_bucket_replication_configuration.this.rule[0].delete_marker_replication[0].status == "Disabled"
    error_message = "Delete marker replication must be disabled by default"
  }
}

run "env_validation_rejects_unknown_value" {
  command = plan

  variables {
    env = "qa"
  }

  expect_failures = [
    var.env,
  ]
}
