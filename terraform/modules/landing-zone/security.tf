# Phase 1 sprint 2: SSE-KMS via kms-hierarchy.flow_logs_cw_key. The key
# is looked up by its alias to avoid cross-stack remote-state plumbing.
# Apply order: terraform/account-bootstrap/exl-{env}/ must apply before
# this destination stack so the alias exists.
resource "aws_cloudwatch_log_group" "flow_logs" {
  name              = "/aws/vpc/flow-logs/${local.name_prefix}"
  retention_in_days = var.flow_logs_retention_days
  kms_key_id        = data.aws_kms_alias.flow_logs_cw.target_key_arn

  tags = local.common_tags
}

resource "aws_iam_role" "flow_logs" {
  name = "${local.name_prefix}-flow-logs-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "vpc-flow-logs.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "flow_logs" {
  name = "${local.name_prefix}-flow-logs-policy"
  role = aws_iam_role.flow_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "WriteFlowLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams",
        ]
        Resource = "${aws_cloudwatch_log_group.flow_logs.arn}:*"
      },
      {
        Sid      = "DescribeLogGroups"
        Effect   = "Allow"
        Action   = "logs:DescribeLogGroups"
        Resource = "*"
      },
    ]
  })
}

resource "aws_flow_log" "vpc" {
  iam_role_arn    = aws_iam_role.flow_logs.arn
  log_destination = aws_cloudwatch_log_group.flow_logs.arn
  traffic_type    = "ALL"
  vpc_id          = aws_vpc.this.id

  tags = local.common_tags
}
