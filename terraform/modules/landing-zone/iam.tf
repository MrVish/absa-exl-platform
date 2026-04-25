resource "aws_iam_account_password_policy" "this" {
  minimum_password_length        = 14
  require_lowercase_characters   = true
  require_uppercase_characters   = true
  require_numbers                = true
  require_symbols                = true
  allow_users_to_change_password = true
  max_password_age               = 90
  password_reuse_prevention      = 24
  hard_expiry                    = false
}

resource "aws_iam_policy" "env_scoped_boundary" {
  name        = "${local.name_prefix}-env-scoped-boundary"
  description = "Permissions boundary for ${var.env} workload roles. Forbids access to resources tagged with a different env."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "AllowMostActions"
        Effect   = "Allow"
        Action   = "*"
        Resource = "*"
      },
      {
        Sid    = "DenyCrossEnvResourceAccess"
        Effect = "Deny"
        Action = "*"
        Resource = "*"
        Condition = {
          StringNotEquals = {
            "aws:ResourceTag/env" = var.env
          }
          StringEquals = {
            "aws:RequestedRegion" = var.region
          }
          "Null" = {
            "aws:ResourceTag/env" = "false"
          }
        }
      },
      {
        Sid    = "DenyIamModification"
        Effect = "Deny"
        Action = [
          "iam:CreateUser",
          "iam:DeleteUser",
          "iam:PutUserPolicy",
          "iam:AttachUserPolicy",
        ]
        Resource = "*"
      },
    ]
  })
}
