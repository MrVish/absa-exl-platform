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
  #   key            = "envs/prod/destination/terraform.tfstate"
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
      stack       = "envs/prod/destination"
    }
  }
}

module "landing_zone" {
  source = "../../../modules/landing-zone"

  env                = "prod"
  vpc_cidr           = "10.40.32.0/20"
  availability_zones = 3
  transit_gateway_id = var.transit_gateway_id

  flow_logs_retention_days = 365

  tags = {
    cost_center = "ml-platform"
  }
}

module "replication_destination" {
  source = "../../../modules/s3-replication-destination"

  bucket_name     = "exl-model-landing-prod"
  env             = "prod"
  retention_years = local.retention_years
  # Two-phase bootstrap — see s3-replication-destination README "Apply order".
  # First apply: leave var.source_replication_role_arn unset (defaults to null).
  # Phase 3 (after source-side has applied): set the real role ARN in
  # terraform.tfvars (or via -var) and re-apply. The variable forwards
  # through to the module.
  source_replication_role_arn = var.source_replication_role_arn
  source_account_id           = var.source_account_id
  alarm_threshold_seconds     = 900

  tags = {
    cost_center = "ml-platform"
  }
}
