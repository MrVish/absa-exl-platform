locals {
  common_tags = merge(var.tags, {
    env    = var.env
    module = "kms-hierarchy"
  })
}

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}
