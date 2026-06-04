terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.100" }
  }
}

variable "env" {
  type        = string
  description = "Deployment environment (dev / uat / prod)."
}
variable "region" {
  type        = string
  description = "AWS region to deploy into (e.g. eu-west-1)."
}
variable "cmk_arn" {
  type        = string
  description = "ARN of the KMS customer-managed key used for log-group encryption."
}
variable "notify_topic_arn" {
  type        = string
  description = "ARN of the SNS topic that receives pipeline completion / failure notifications."
}
variable "validate_input_lambda_arn" {
  type        = string
  description = "ARN of the Lambda that validates input data against the registered schema."
}
variable "great_expectations_runner_arn" {
  type        = string
  description = "ARN of the Lambda that executes Great Expectations data-quality suites."
}
variable "write_output_lambda_arn" {
  type        = string
  description = "ARN of the Lambda that persists scoring output to the output bucket."
}
variable "pir_checker_arn" {
  type        = string
  description = "ARN of the Lambda that performs PIR variance checking."
}
variable "tags" {
  type        = map(string)
  description = "Tags to apply to every resource. Must include cost_center."
  validation {
    condition     = contains(keys(var.tags), "cost_center")
    error_message = "tags must include cost_center."
  }
}

provider "aws" {
  region = var.region
}

locals {
  name = "${var.env}-credit-risk-pd-1-0-0"

  asl_substitutions = merge(
    {
      ValidateInputLambdaArn     = var.validate_input_lambda_arn
      GreatExpectationsRunnerArn = var.great_expectations_runner_arn
      WriteOutputLambdaArn       = var.write_output_lambda_arn
      PirCheckerArn              = var.pir_checker_arn
      NotifyTopicArn             = var.notify_topic_arn
    },
    {}
  )
}

data "aws_iam_policy_document" "sfn_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "sfn" {
  name               = "${local.name}-sfn"
  assume_role_policy = data.aws_iam_policy_document.sfn_assume.json
  tags               = var.tags
}

data "aws_iam_policy_document" "schedule_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "schedule" {
  name               = "${local.name}-schedule"
  assume_role_policy = data.aws_iam_policy_document.schedule_assume.json
  tags               = var.tags
}

resource "aws_cloudwatch_log_group" "sfn" {
  name              = "/aws/sfn/${local.name}"
  retention_in_days = 365
  kms_key_id        = var.cmk_arn
  tags              = var.tags
}

resource "aws_sfn_state_machine" "this" {
  name       = local.name
  role_arn   = aws_iam_role.sfn.arn
  type       = "STANDARD"
  definition = templatefile("${path.module}/../statemachine.json", local.asl_substitutions)

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.sfn.arn}:*"
    include_execution_data = false
    level                  = "ERROR"
  }

  tags = var.tags
}

resource "aws_cloudwatch_event_rule" "schedule" {
  name                = "${local.name}-schedule"
  schedule_expression = "cron(0 6 * * ? *)"
  tags                = var.tags
}

resource "aws_cloudwatch_event_target" "this" {
  rule     = aws_cloudwatch_event_rule.schedule.name
  arn      = aws_sfn_state_machine.this.arn
  role_arn = aws_iam_role.schedule.arn
}

output "state_machine_arn" {
  value       = aws_sfn_state_machine.this.arn
  description = "ARN of the Step Functions state machine."
}
output "state_machine_name" {
  value       = aws_sfn_state_machine.this.name
  description = "Name of the Step Functions state machine."
}
