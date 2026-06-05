# The demo runs the registry as a local uvicorn process (T9) against
# this DDB table. We do NOT reuse the production pipeline-registry
# module because that module also creates Lambda + APIGW + CloudWatch
# Logs resources that LocalStack CE doesn't have enabled in our
# docker-compose.yml SERVICES list (only kms,s3,dynamodb,sts,iam).
# Reusing the module would cause terraform apply to hit real AWS
# Lambda/APIGW/Logs endpoints and fail.
#
# This thin local resource mirrors the table schema the production
# module creates (see terraform/modules/pipeline-registry/main.tf
# aws_dynamodb_table.this for the canonical schema). Keep this in
# sync if the production module's schema evolves -- the FastAPI
# registry app (T9) queries this table directly and depends on the
# hash/range keys + the by_status GSI.
#
# Differences from production:
#   - billing_mode/PAY_PER_REQUEST: same
#   - hash_key=model_name, range_key=version: same
#   - by_status GSI: same
#   - point_in_time_recovery: false here (LocalStack CE doesn't
#     actually support PITR; production uses true)
#   - deletion_protection: false here (demo tears down + redeploys)
#   - server_side_encryption: wired to the signing module's KMS key
#     since this stack doesn't create a dedicated registry CMK

resource "aws_dynamodb_table" "registry" {
  name         = "model_pipeline_registry-${var.env_name}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "model_name"
  range_key    = "version"

  attribute {
    name = "model_name"
    type = "S"
  }

  attribute {
    name = "version"
    type = "S"
  }

  attribute {
    name = "approval_status"
    type = "S"
  }

  attribute {
    name = "updated_at"
    type = "S"
  }

  global_secondary_index {
    name            = "by_status"
    hash_key        = "approval_status"
    range_key       = "updated_at"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = false # LocalStack CE doesn't support PITR; production uses true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = module.signing.kms_key_arn
  }

  tags = {
    Environment = "demo"
    Purpose     = "pipeline-registry-table"
  }
}
