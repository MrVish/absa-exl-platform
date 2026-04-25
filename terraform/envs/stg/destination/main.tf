terraform {
  required_version = ">= 1.9.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.50.0, < 6.0.0"
    }
  }

  # backend "s3" {
  #   bucket         = "exl-tfstate-stg"
  #   key            = "envs/stg/destination/terraform.tfstate"
  #   region         = "af-south-1"
  #   dynamodb_table = "exl-tfstate-lock-stg"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      env         = "stg"
      cost_center = "ml-platform"
      managed_by  = "terraform"
      stack       = "envs/stg/destination"
    }
  }
}

module "landing_zone" {
  source = "../../../modules/landing-zone"

  env                = "stg"
  vpc_cidr           = "10.40.16.0/20"
  availability_zones = 3
  transit_gateway_id = var.transit_gateway_id

  flow_logs_retention_days = 30

  tags = {
    cost_center = "ml-platform"
  }
}

module "replication_destination" {
  source = "../../../modules/s3-replication-destination"

  bucket_name                 = "exl-model-landing-stg"
  env                         = "stg"
  retention_years             = local.retention_years
  source_replication_role_arn = var.source_replication_role_arn
  source_account_id           = var.source_account_id
  alarm_threshold_seconds     = 900

  tags = {
    cost_center = "ml-platform"
  }
}
