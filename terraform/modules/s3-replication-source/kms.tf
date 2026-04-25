resource "aws_kms_key" "this" {
  description             = "Source-side CMK for ${var.bucket_name}"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  key_usage               = "ENCRYPT_DECRYPT"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowAccountRoot"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowReplicationRoleDecrypt"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.replication.arn
        }
        Action   = "kms:Decrypt"
        Resource = "*"
      },
    ]
  })

  tags = local.common_tags
}

resource "aws_kms_alias" "this" {
  name          = "alias/handoff-${var.env}"
  target_key_id = aws_kms_key.this.key_id
}

data "aws_caller_identity" "current" {}
