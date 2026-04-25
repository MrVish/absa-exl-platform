terraform {
  required_version = ">= 1.9.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.50.0, < 6.0.0"
    }
  }

  # backend "s3" {
  #   bucket         = "exl-tfstate-prod"
  #   key            = "account-bootstrap/terraform.tfstate"
  #   region         = "af-south-1"
  #   dynamodb_table = "exl-tfstate-lock-prod"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      env         = "prod"
      cost_center = "ml-platform"
      managed_by  = "terraform"
      stack       = "account-bootstrap/exl-prod"
    }
  }
}

module "kms_hierarchy" {
  source = "../../modules/kms-hierarchy"

  env = "prod"

  tags = {
    cost_center = "ml-platform"
  }
}

# CloudTrail multi-region trail for the prod account
resource "aws_cloudtrail" "this" {
  name                          = "exl-prod-trail"
  s3_bucket_name                = aws_s3_bucket.cloudtrail.id
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_log_file_validation    = true

  cloud_watch_logs_group_arn = "${aws_cloudwatch_log_group.cloudtrail.arn}:*"
  cloud_watch_logs_role_arn  = aws_iam_role.cloudtrail_to_cwlogs.arn

  event_selector {
    read_write_type           = "All"
    include_management_events = true

    data_resource {
      type   = "AWS::S3::Object"
      values = ["arn:aws:s3:::"]
    }
  }
}

# ---------------------------------------------------------------------
# CloudTrail → CloudWatch Logs (sprint 2 task 5)
# Near-real-time event stream for security operations + metric filters.
# ---------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "cloudtrail" {
  name              = "/aws/cloudtrail/exl-prod"
  retention_in_days = 365
  kms_key_id        = module.kms_hierarchy.flow_logs_cw_key_arn
}

resource "aws_iam_role" "cloudtrail_to_cwlogs" {
  name = "exl-prod-cloudtrail-to-cwlogs"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "cloudtrail.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "cloudtrail_to_cwlogs" {
  name = "exl-prod-cloudtrail-to-cwlogs"
  role = aws_iam_role.cloudtrail_to_cwlogs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogStream",
        "logs:PutLogEvents",
      ]
      Resource = "${aws_cloudwatch_log_group.cloudtrail.arn}:*"
    }]
  })
}

resource "aws_s3_bucket" "cloudtrail" {
  bucket        = "exl-prod-cloudtrail-${data.aws_caller_identity.current.account_id}"
  force_destroy = false

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Phase 1 sprint 2: SSE-KMS via kms-hierarchy.cloudtrail_bucket_key_arn.
resource "aws_s3_bucket_server_side_encryption_configuration" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = module.kms_hierarchy.cloudtrail_bucket_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AWSCloudTrailAclCheck"
        Effect    = "Allow"
        Principal = { Service = "cloudtrail.amazonaws.com" }
        Action    = "s3:GetBucketAcl"
        Resource  = aws_s3_bucket.cloudtrail.arn
        Condition = {
          StringEquals = {
            "aws:SourceArn" = "arn:aws:cloudtrail:${var.region}:${data.aws_caller_identity.current.account_id}:trail/exl-prod-trail"
          }
        }
      },
      {
        Sid       = "AWSCloudTrailWrite"
        Effect    = "Allow"
        Principal = { Service = "cloudtrail.amazonaws.com" }
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.cloudtrail.arn}/AWSLogs/${data.aws_caller_identity.current.account_id}/*"
        Condition = {
          StringEquals = {
            "s3:x-amz-acl"  = "bucket-owner-full-control"
            "aws:SourceArn" = "arn:aws:cloudtrail:${var.region}:${data.aws_caller_identity.current.account_id}:trail/exl-prod-trail"
          }
        }
      },
    ]
  })
}

# ---------------------------------------------------------------------
# Account-singleton resources (moved from landing-zone in sprint 2).
# Each EXL account has exactly one of these.
# ---------------------------------------------------------------------

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

resource "aws_guardduty_detector" "this" {
  enable                       = true
  finding_publishing_frequency = "FIFTEEN_MINUTES"
}

resource "aws_securityhub_account" "this" {}

resource "aws_securityhub_standards_subscription" "foundational" {
  standards_arn = "arn:aws:securityhub:${var.region}::standards/aws-foundational-security-best-practices/v/1.0.0"

  depends_on = [aws_securityhub_account.this]
}

data "aws_caller_identity" "current" {}

# ---------------------------------------------------------------------
# Security alerts SNS topic — alarmed by metric filters below.
# Subscriptions live per-env (operator adds via console or a separate
# subscription stack), not in this module.
# ---------------------------------------------------------------------

resource "aws_sns_topic" "security_alerts" {
  name              = "prod-security-alerts"
  kms_master_key_id = "alias/aws/sns"
}

# ---------------------------------------------------------------------
# CIS AWS Benchmark v3 detective control metric filters.
# Each filter publishes a custom metric in the AbsaExlSecurity namespace;
# alarms below watch those metrics.
# ---------------------------------------------------------------------

locals {
  metric_namespace = "AbsaExlSecurity"
}

resource "aws_cloudwatch_log_metric_filter" "root_usage" {
  name           = "exl-prod-root-usage"
  log_group_name = aws_cloudwatch_log_group.cloudtrail.name
  pattern        = "{ $.userIdentity.type = \"Root\" && $.userIdentity.invokedBy NOT EXISTS && $.eventType != \"AwsServiceEvent\" }"

  metric_transformation {
    name      = "RootUsage"
    namespace = local.metric_namespace
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "iam_policy_change" {
  name           = "exl-prod-iam-policy-change"
  log_group_name = aws_cloudwatch_log_group.cloudtrail.name
  pattern        = "{ ($.eventName = DeleteGroupPolicy) || ($.eventName = DeleteRolePolicy) || ($.eventName = DeleteUserPolicy) || ($.eventName = PutGroupPolicy) || ($.eventName = PutRolePolicy) || ($.eventName = PutUserPolicy) || ($.eventName = CreatePolicy) || ($.eventName = DeletePolicy) || ($.eventName = AttachRolePolicy) || ($.eventName = DetachRolePolicy) || ($.eventName = AttachUserPolicy) || ($.eventName = DetachUserPolicy) || ($.eventName = AttachGroupPolicy) || ($.eventName = DetachGroupPolicy) }"

  metric_transformation {
    name      = "IAMPolicyChange"
    namespace = local.metric_namespace
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "kms_cmk_change" {
  name           = "exl-prod-kms-cmk-change"
  log_group_name = aws_cloudwatch_log_group.cloudtrail.name
  pattern        = "{ ($.eventSource = kms.amazonaws.com) && (($.eventName = DisableKey) || ($.eventName = ScheduleKeyDeletion)) }"

  metric_transformation {
    name      = "KMSCMKChange"
    namespace = local.metric_namespace
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "s3_policy_change" {
  name           = "exl-prod-s3-policy-change"
  log_group_name = aws_cloudwatch_log_group.cloudtrail.name
  pattern        = "{ ($.eventSource = s3.amazonaws.com) && (($.eventName = PutBucketAcl) || ($.eventName = PutBucketPolicy) || ($.eventName = PutBucketCors) || ($.eventName = PutBucketLifecycle) || ($.eventName = PutBucketReplication) || ($.eventName = DeleteBucketPolicy) || ($.eventName = DeleteBucketCors) || ($.eventName = DeleteBucketLifecycle) || ($.eventName = DeleteBucketReplication)) }"

  metric_transformation {
    name      = "S3PolicyChange"
    namespace = local.metric_namespace
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "sts_assume_role_fail" {
  name           = "exl-prod-sts-assume-role-fail"
  log_group_name = aws_cloudwatch_log_group.cloudtrail.name
  pattern        = "{ ($.eventSource = sts.amazonaws.com) && ($.errorCode EXISTS) }"

  metric_transformation {
    name      = "STSAssumeRoleFail"
    namespace = local.metric_namespace
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "cloudtrail_change" {
  name           = "exl-prod-cloudtrail-change"
  log_group_name = aws_cloudwatch_log_group.cloudtrail.name
  pattern        = "{ ($.eventSource = cloudtrail.amazonaws.com) && (($.eventName = StopLogging) || ($.eventName = DeleteTrail) || ($.eventName = UpdateTrail)) }"

  metric_transformation {
    name      = "CloudTrailChange"
    namespace = local.metric_namespace
    value     = "1"
  }
}

# ---------------------------------------------------------------------
# CIS AWS Benchmark v3 alarms paired with the metric filters above.
# All alarm actions go to the security_alerts SNS topic.
# ---------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "root_usage" {
  alarm_name          = "exl-prod-root-usage"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "RootUsage"
  namespace           = local.metric_namespace
  period              = 60
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "Root account usage detected in exl-prod"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.security_alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "iam_policy_change" {
  alarm_name          = "exl-prod-iam-policy-change"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "IAMPolicyChange"
  namespace           = local.metric_namespace
  period              = 60
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "IAM policy change detected in exl-prod"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.security_alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "kms_cmk_change" {
  alarm_name          = "exl-prod-kms-cmk-change"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "KMSCMKChange"
  namespace           = local.metric_namespace
  period              = 60
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "KMS key disabled or scheduled for deletion in exl-prod"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.security_alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "s3_policy_change" {
  alarm_name          = "exl-prod-s3-policy-change"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "S3PolicyChange"
  namespace           = local.metric_namespace
  period              = 60
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "S3 bucket policy change detected in exl-prod"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.security_alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "sts_assume_role_fail" {
  alarm_name          = "exl-prod-sts-assume-role-fail-burst"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 5
  datapoints_to_alarm = 5
  metric_name         = "STSAssumeRoleFail"
  namespace           = local.metric_namespace
  period              = 60
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = ">=10 failed STS AssumeRole attempts in 5 minutes — possible credential probing"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.security_alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "cloudtrail_change" {
  alarm_name          = "exl-prod-cloudtrail-change"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "CloudTrailChange"
  namespace           = local.metric_namespace
  period              = 60
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "CloudTrail config change detected in exl-prod (StopLogging / DeleteTrail / UpdateTrail)"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.security_alerts.arn]
}

# ---------------------------------------------------------------------
# IAM federation — workload roles (SAML) + GitHub Actions OIDC ci-deploy.
# permissions_boundary_arn is constructed deterministically from the
# known pattern of the policy created by the landing-zone module in
# the destination stack.
# ---------------------------------------------------------------------

locals {
  permissions_boundary_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/prod-env-scoped-boundary"
}

module "iam_federation" {
  source = "../../modules/iam-federation"

  env = "prod"
  # TODO: replace with the real ABSA Identity Center provider ARN before first apply
  absa_identity_center_saml_provider_arn = "arn:aws:iam::000000000000:saml-provider/AWSSSO_PLACEHOLDER_DO_NOT_DELETE"
  permissions_boundary_arn               = local.permissions_boundary_arn
  github_org_slash_repo                  = "absa-group/absa-exl-platform"
  allowed_github_branches_for_apply      = ["main"]

  tags = {
    cost_center = "ml-platform"
  }
}
