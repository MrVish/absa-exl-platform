terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.100" }
  }
}

provider "aws" {
  region = var.region
}

module "registry" {
  source                     = "../../../modules/pipeline-registry"
  env                        = local.env
  lambda_source_dir          = "${path.module}/../../../../registry/api/src"
  log_retention_days         = 30
  enable_deletion_protection = false
  tags                       = local.tags
}
