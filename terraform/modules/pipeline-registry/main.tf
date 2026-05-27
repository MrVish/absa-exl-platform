locals {
  name = "${var.env}-registry"
  tags = merge(var.tags, { env = var.env, module = "pipeline-registry", cost_center = "model-hosting" })
}

resource "aws_kms_key" "this" {
  description             = "${local.name} registry data + logs CMK (${var.region})"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  tags                    = local.tags
}

resource "aws_kms_alias" "this" {
  name          = "alias/${local.name}"
  target_key_id = aws_kms_key.this.key_id
}

resource "aws_dynamodb_table" "this" {
  name         = var.table_name
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
    enabled = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.this.arn
  }

  deletion_protection_enabled = var.enable_deletion_protection
  tags                        = local.tags
}

data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = var.lambda_source_dir
  output_path = "${path.module}/.build/${local.name}-lambda.zip"
}

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${local.name}-lambda"
  assume_role_policy = data.aws_iam_policy_document.assume.json
  tags               = local.tags
}

data "aws_iam_policy_document" "lambda" {
  statement {
    sid    = "TableAccess"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem",
      "dynamodb:Query", "dynamodb:Scan",
    ]
    resources = [aws_dynamodb_table.this.arn, "${aws_dynamodb_table.this.arn}/index/*"]
  }
  statement {
    sid       = "KmsData"
    effect    = "Allow"
    actions   = ["kms:Decrypt", "kms:GenerateDataKey"]
    resources = [aws_kms_key.this.arn]
  }
  statement {
    sid       = "Logs"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.lambda.arn}:*"]
  }
}

resource "aws_iam_role_policy" "lambda" {
  name   = "${local.name}-lambda"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda.json
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.name}"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.this.arn
  tags              = local.tags
}

resource "aws_lambda_function" "this" {
  function_name    = local.name
  role             = aws_iam_role.lambda.arn
  runtime          = var.lambda_runtime
  handler          = "registry_api.app.handler"
  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256
  timeout          = 15
  memory_size      = 256

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.this.name
      LOG_LEVEL  = "INFO"
    }
  }

  depends_on = [aws_cloudwatch_log_group.lambda]
  tags       = local.tags
}

resource "aws_apigatewayv2_api" "this" {
  name          = local.name
  protocol_type = "HTTP"
  tags          = local.tags
}

resource "aws_apigatewayv2_integration" "this" {
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.this.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "default" {
  api_id             = aws_apigatewayv2_api.this.id
  route_key          = "$default"
  target             = "integrations/${aws_apigatewayv2_integration.this.id}"
  authorization_type = "AWS_IAM"
}

resource "aws_cloudwatch_log_group" "apigw" {
  name              = "/aws/apigw/${local.name}"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.this.arn
  tags              = local.tags
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.this.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.apigw.arn
    format          = "$context.requestId $context.identity.caller $context.httpMethod $context.path $context.status"
  }
  tags = local.tags
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowApiGwInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}

# Caller policies for read/write IAM separation (attach to ABSA/EXL caller roles).
data "aws_iam_policy_document" "reader" {
  statement {
    effect    = "Allow"
    actions   = ["execute-api:Invoke"]
    resources = ["${aws_apigatewayv2_api.this.execution_arn}/*/GET/*"]
  }
}

resource "aws_iam_policy" "reader" {
  name   = "${local.name}-reader"
  policy = data.aws_iam_policy_document.reader.json
  tags   = local.tags
}

data "aws_iam_policy_document" "writer" {
  statement {
    effect  = "Allow"
    actions = ["execute-api:Invoke"]
    resources = [
      "${aws_apigatewayv2_api.this.execution_arn}/*/POST/*",
      "${aws_apigatewayv2_api.this.execution_arn}/*/PATCH/*",
    ]
  }
}

resource "aws_iam_policy" "writer" {
  name   = "${local.name}-writer"
  policy = data.aws_iam_policy_document.writer.json
  tags   = local.tags
}
