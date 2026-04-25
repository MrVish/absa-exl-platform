# SAML federation trust shared by 4 workload roles
locals {
  saml_assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = var.absa_identity_center_saml_provider_arn }
      Action    = "sts:AssumeRoleWithSAML"
      Condition = {
        StringEquals = {
          "SAML:aud" = "https://signin.aws.amazon.com/saml"
        }
      }
    }]
  })

  break_glass_assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = var.absa_identity_center_saml_provider_arn }
      Action    = "sts:AssumeRoleWithSAML"
      Condition = {
        StringEquals = {
          "SAML:aud" = "https://signin.aws.amazon.com/saml"
        }
        Bool = {
          "aws:MultiFactorAuthPresent" = "true"
        }
      }
    }]
  })
}

resource "aws_iam_role" "platform_engineer" {
  name                 = "${var.env}-platform-engineer"
  assume_role_policy   = local.saml_assume_role_policy
  permissions_boundary = var.permissions_boundary_arn
  max_session_duration = 28800

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "platform_engineer_admin" {
  role       = aws_iam_role.platform_engineer.name
  policy_arn = "arn:aws:iam::aws:policy/job-function/SystemAdministrator"
}

resource "aws_iam_role" "platform_operator" {
  name                 = "${var.env}-platform-operator"
  assume_role_policy   = local.saml_assume_role_policy
  permissions_boundary = var.permissions_boundary_arn
  max_session_duration = 14400

  tags = local.common_tags
}

resource "aws_iam_role_policy" "platform_operator" {
  name = "${var.env}-platform-operator-policy"
  role = aws_iam_role.platform_operator.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "AllowReadEverything"
        Effect   = "Allow"
        Action   = ["*:Get*", "*:List*", "*:Describe*", "logs:FilterLogEvents"]
        Resource = "*"
      },
      {
        Sid      = "AllowOperationalWrite"
        Effect   = "Allow"
        Action = [
          "ec2:RebootInstances",
          "ec2:StartInstances",
          "ec2:StopInstances",
          "ecs:UpdateService",
          "lambda:InvokeFunction",
          "states:StartExecution",
          "states:StopExecution",
        ]
        Resource = "*"
      },
      {
        Sid    = "DenyDangerousActions"
        Effect = "Deny"
        Action = [
          "iam:*",
          "kms:ScheduleKeyDeletion",
          "kms:DisableKey",
          "cloudtrail:StopLogging",
          "cloudtrail:DeleteTrail",
          "cloudtrail:UpdateTrail",
        ]
        Resource = "*"
      },
    ]
  })
}

resource "aws_iam_role" "platform_readonly" {
  name                 = "${var.env}-platform-readonly"
  assume_role_policy   = local.saml_assume_role_policy
  permissions_boundary = var.permissions_boundary_arn
  max_session_duration = 28800

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "platform_readonly" {
  role       = aws_iam_role.platform_readonly.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

resource "aws_iam_role" "break_glass" {
  name                 = "${var.env}-break-glass"
  assume_role_policy   = local.break_glass_assume_role_policy
  permissions_boundary = var.permissions_boundary_arn
  max_session_duration = 3600

  tags = merge(local.common_tags, {
    purpose = "incident-response"
    audit   = "high"
  })
}

resource "aws_iam_role_policy_attachment" "break_glass_admin" {
  role       = aws_iam_role.break_glass.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}
