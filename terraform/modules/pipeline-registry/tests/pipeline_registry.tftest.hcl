mock_provider "aws" {
  mock_data "aws_iam_policy_document" {
    defaults = {
      json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}"
    }
  }
  mock_resource "aws_kms_key" {
    defaults = {
      arn                 = "arn:aws:kms:eu-west-1:123456789012:key/mock-key-id"
      key_id              = "mock-key-id"
      enable_key_rotation = true
    }
  }
  mock_resource "aws_cloudwatch_log_group" {
    defaults = {
      arn        = "arn:aws:logs:eu-west-1:123456789012:log-group:mock-lg"
      kms_key_id = "arn:aws:kms:eu-west-1:123456789012:key/mock-key-id"
    }
  }
  mock_resource "aws_iam_role" {
    defaults = {
      arn = "arn:aws:iam::123456789012:role/mock-role"
    }
  }
  mock_resource "aws_apigatewayv2_api" {
    defaults = {
      execution_arn = "arn:aws:execute-api:eu-west-1:123456789012:mock-api-id"
      api_endpoint  = "https://mock-api-id.execute-api.eu-west-1.amazonaws.com"
    }
  }
}

variables {
  env               = "dev"
  lambda_source_dir = "../../../registry/api/src"
  tags              = { cost_center = "model-hosting" }
}

run "defaults_validate" {
  command = plan

  assert {
    condition     = aws_dynamodb_table.this.billing_mode == "PAY_PER_REQUEST"
    error_message = "table must be on-demand"
  }
  assert {
    condition     = aws_dynamodb_table.this.hash_key == "model_name" && aws_dynamodb_table.this.range_key == "version"
    error_message = "composite key must be (model_name, version)"
  }
  assert {
    condition     = one(aws_dynamodb_table.this.point_in_time_recovery[*].enabled) == true
    error_message = "PITR must be enabled"
  }
  assert {
    condition     = length([for gsi in aws_dynamodb_table.this.global_secondary_index : gsi if gsi.name == "by_status"]) == 1
    error_message = "by_status GSI must exist"
  }
  assert {
    condition     = aws_dynamodb_table.this.deletion_protection_enabled == true
    error_message = "deletion protection default must be true"
  }
  assert {
    condition     = one(aws_dynamodb_table.this.server_side_encryption[*].enabled) == true
    error_message = "table SSE must be enabled (module-owned CMK)"
  }
  assert {
    condition     = aws_lambda_function.this.runtime == "python3.12"
    error_message = "lambda runtime must be python3.12"
  }
  assert {
    condition     = aws_lambda_function.this.environment[0].variables["TABLE_NAME"] == "model_pipeline_registry"
    error_message = "TABLE_NAME env var must be set"
  }
  assert {
    condition     = aws_apigatewayv2_route.default.authorization_type == "AWS_IAM"
    error_message = "route auth must be AWS_IAM"
  }
  assert {
    condition     = aws_kms_key.this.enable_key_rotation == true
    error_message = "KMS key rotation must be enabled"
  }
  assert {
    condition     = aws_cloudwatch_log_group.lambda.retention_in_days == 365
    error_message = "Lambda log group retention must be 365 days"
  }
  assert {
    condition     = aws_iam_policy.reader.name == "dev-registry-reader"
    error_message = "reader policy name must be dev-registry-reader"
  }
  assert {
    condition     = aws_iam_policy.writer.name == "dev-registry-writer"
    error_message = "writer policy name must be dev-registry-writer"
  }
}

# kms_key_id is a cross-resource computed attribute; it can only be
# verified after apply. Uses mock_provider so no real AWS calls are made.
run "kms_log_group_wiring" {
  command = apply

  assert {
    condition     = aws_cloudwatch_log_group.lambda.kms_key_id != null && aws_cloudwatch_log_group.lambda.kms_key_id != ""
    error_message = "Lambda log group must be encrypted with the module CMK"
  }
}

run "deletion_protection_override" {
  command = plan
  variables {
    enable_deletion_protection = false
  }
  assert {
    condition     = aws_dynamodb_table.this.deletion_protection_enabled == false
    error_message = "deletion protection override must be honoured"
  }
}
