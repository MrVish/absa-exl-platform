resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [local.github_oidc_thumbprint]

  tags = local.common_tags
}

resource "aws_iam_role" "ci_deploy" {
  name = "${var.env}-ci-deploy"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.github.arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        StringLike = {
          "token.actions.githubusercontent.com:sub" = local.ci_deploy_sub_conditions
        }
      }
    }]
  })

  permissions_boundary = var.permissions_boundary_arn
  max_session_duration = 3600

  tags = local.common_tags
}

resource "aws_iam_role_policy" "ci_deploy" {
  name = "${var.env}-ci-deploy-policy"
  role = aws_iam_role.ci_deploy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "AllowAllByDefault"
        Effect   = "Allow"
        Action   = "*"
        Resource = "*"
      },
      {
        Sid    = "DenyCredentialMutation"
        Effect = "Deny"
        Action = [
          "iam:CreateUser",
          "iam:DeleteUser",
          "iam:CreateAccessKey",
          "iam:DeleteAccessKey",
          "iam:UpdateLoginProfile",
          "iam:CreateLoginProfile",
          "iam:DeleteLoginProfile",
          "iam:DeactivateMFADevice",
          "iam:DeleteVirtualMFADevice",
          "iam:PutUserPolicy",
          "iam:AttachUserPolicy",
          "iam:UpdateAssumeRolePolicy",
        ]
        Resource = "*"
      },
      {
        Sid    = "DenyKeyAndAuditDestruction"
        Effect = "Deny"
        Action = [
          "kms:ScheduleKeyDeletion",
          "kms:DisableKey",
          "kms:DisableKeyRotation",
          "s3:DeleteBucket",
          "cloudtrail:StopLogging",
          "cloudtrail:DeleteTrail",
        ]
        Resource = "*"
      },
    ]
  })
}
