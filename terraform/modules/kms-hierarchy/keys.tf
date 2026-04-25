resource "aws_kms_key" "cloudtrail_bucket" {
  description             = "Audit-evidence CMK for the ${var.env} CloudTrail S3 bucket. Rotation enabled."
  deletion_window_in_days = 30
  enable_key_rotation     = true
  key_usage               = "ENCRYPT_DECRYPT"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowAccountRoot"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" }
        Action    = "kms:*"
        Resource  = "*"
      },
      {
        Sid       = "AllowCloudTrailEncryptDecrypt"
        Effect    = "Allow"
        Principal = { Service = "cloudtrail.amazonaws.com" }
        Action = [
          "kms:GenerateDataKey",
          "kms:Decrypt",
          "kms:DescribeKey",
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "aws:SourceArn" = "arn:aws:cloudtrail:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:trail/exl-${var.env}-trail"
          }
        }
      },
    ]
  })

  tags = local.common_tags
}

resource "aws_kms_alias" "cloudtrail_bucket" {
  name          = "alias/${var.env}-cloudtrail-bucket"
  target_key_id = aws_kms_key.cloudtrail_bucket.key_id
}

resource "aws_kms_key" "flow_logs_cw" {
  description             = "Audit-evidence CMK for the ${var.env} CloudWatch Log groups holding VPC flow logs and CloudTrail event stream. Rotation enabled."
  deletion_window_in_days = 30
  enable_key_rotation     = true
  key_usage               = "ENCRYPT_DECRYPT"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowAccountRoot"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" }
        Action    = "kms:*"
        Resource  = "*"
      },
      {
        Sid       = "AllowCloudWatchLogsEncryptDecrypt"
        Effect    = "Allow"
        Principal = { Service = "logs.${data.aws_region.current.name}.amazonaws.com" }
        Action = [
          "kms:Encrypt*",
          "kms:Decrypt*",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:Describe*",
        ]
        Resource = "*"
        Condition = {
          ArnLike = {
            "kms:EncryptionContext:aws:logs:arn" = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:*"
          }
        }
      },
    ]
  })

  tags = local.common_tags
}

resource "aws_kms_alias" "flow_logs_cw" {
  name          = "alias/${var.env}-flow-logs-cw"
  target_key_id = aws_kms_key.flow_logs_cw.key_id
}

# Phase 2 placeholder. The manifest-signing CMK will be created here when ADR-0003
# is implemented (Code Intake + Pipeline Factory). Asymmetric RSA-3072, key_usage =
# "SIGN_VERIFY". Until then, the manifest_signing_key_arn output returns null and
# downstream consumers must guard for null.
#
# resource "aws_kms_key" "manifest_signing" {
#   description              = "Asymmetric signing key for Code Intake and Pipeline Factory manifests. Phase 2."
#   deletion_window_in_days  = 30
#   enable_key_rotation      = false
#   customer_master_key_spec = "RSA_3072"
#   key_usage                = "SIGN_VERIFY"
#   policy                   = jsonencode({...})
#   tags                     = local.common_tags
# }
