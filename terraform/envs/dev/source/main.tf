terraform {
  required_version = ">= 1.9.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.50.0, < 6.0.0"
    }
  }

  # backend "s3" {
  #   bucket         = "absa-tfstate-handoff-dev"
  #   key            = "s3-replication-source/terraform.tfstate"
  #   region         = "af-south-1"
  #   dynamodb_table = "absa-tfstate-lock-dev"
  #   encrypt        = true
  # }
  # Backend block is commented out for Phase 1 — uncomment when the
  # state bucket is provisioned (ABSA Cloud Platform team task).
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      env         = "dev"
      cost_center = "ml-platform"
      managed_by  = "terraform"
      stack       = "envs/dev/source"
    }
  }
}

module "replication_source" {
  source = "../../../modules/s3-replication-source"

  bucket_name             = "absa-model-handoff-dev"
  env                     = "dev"
  retention_years         = local.retention_years
  prefix_filter           = "model-ready/"
  destination_bucket_arn  = var.destination_bucket_arn
  destination_kms_key_arn = var.destination_kms_key_arn
  destination_account_id  = var.destination_account_id

  tags = {
    cost_center = "ml-platform"
  }
}
