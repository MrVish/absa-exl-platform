mock_provider "aws" {
  mock_data "aws_iam_policy_document" {
    defaults = {
      json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}"
    }
  }
}

variables {
  env               = "dev"
  region            = "eu-west-1"
  lambda_source_dir = "../../../registry/api/src"
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
