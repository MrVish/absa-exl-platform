variables {
  env = "dev"
  tags = {
    cost_center = "ml-platform"
  }
}

run "cloudtrail_bucket_key_rotation_enabled" {
  command = plan

  assert {
    condition     = aws_kms_key.cloudtrail_bucket.enable_key_rotation == true
    error_message = "CloudTrail bucket key must have rotation enabled"
  }
}

run "flow_logs_cw_key_rotation_enabled" {
  command = plan

  assert {
    condition     = aws_kms_key.flow_logs_cw.enable_key_rotation == true
    error_message = "Flow-logs CW key must have rotation enabled"
  }
}

run "cloudtrail_bucket_key_alias_uses_env_prefix" {
  command = plan

  assert {
    condition     = aws_kms_alias.cloudtrail_bucket.name == "alias/dev-cloudtrail-bucket"
    error_message = "CloudTrail bucket key alias must be alias/{env}-cloudtrail-bucket"
  }
}

run "flow_logs_cw_key_alias_uses_env_prefix" {
  command = plan

  assert {
    condition     = aws_kms_alias.flow_logs_cw.name == "alias/dev-flow-logs-cw"
    error_message = "Flow-logs CW key alias must be alias/{env}-flow-logs-cw"
  }
}

run "cloudtrail_key_grants_cloudtrail_service" {
  command = plan

  assert {
    condition = strcontains(
      aws_kms_key.cloudtrail_bucket.policy,
      "cloudtrail.amazonaws.com",
    )
    error_message = "CloudTrail bucket key policy must grant the cloudtrail.amazonaws.com service principal"
  }
}

run "flow_logs_key_grants_cwlogs_service" {
  command = plan

  assert {
    condition = strcontains(
      aws_kms_key.flow_logs_cw.policy,
      "logs.",
    )
    error_message = "Flow-logs CW key policy must grant the logs.{region}.amazonaws.com service principal"
  }
}

run "env_validation_rejects_unknown_value" {
  command = plan

  variables {
    env = "uat"
  }

  expect_failures = [
    var.env,
  ]
}
