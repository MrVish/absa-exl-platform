terraform {
  required_version = ">= 1.9.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.50.0, < 6.0.0"
    }
  }

  # backend "s3" {
  #   bucket         = "exl-tfstate-dev"
  #   key            = "envs/dev/destination/terraform.tfstate"
  #   region         = "af-south-1"
  #   dynamodb_table = "exl-tfstate-lock-dev"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      env         = "dev"
      cost_center = "ml-platform"
      managed_by  = "terraform"
      stack       = "envs/dev/destination"
    }
  }
}

module "landing_zone" {
  source = "../../../modules/landing-zone"

  env                = "dev"
  vpc_cidr           = "10.40.0.0/20"
  availability_zones = 3
  transit_gateway_id = var.transit_gateway_id

  flow_logs_retention_days = 30

  tags = {
    cost_center = "ml-platform"
  }
}

module "replication_destination" {
  source = "../../../modules/s3-replication-destination"

  bucket_name                 = "exl-model-landing-dev"
  env                         = "dev"
  retention_years             = local.retention_years
  # Two-phase bootstrap — see s3-replication-destination README "Apply order".
  # First apply: keep source_replication_role_arn = null; the destination
  # provisions without source-role grants.
  # After the source-side has applied, replace this null with the real
  # role ARN (e.g. data.terraform_remote_state.source.outputs.replication_role_arn)
  # and re-apply.
  source_replication_role_arn = null
  source_account_id           = var.source_account_id
  alarm_threshold_seconds     = 900

  tags = {
    cost_center = "ml-platform"
  }
}
