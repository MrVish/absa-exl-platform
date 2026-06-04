terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.100" }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = local.tags
  }
}

module "signing" {
  source = "../../../modules/signing-foundation"

  env                      = local.env
  region                   = var.region
  repo_full_name           = var.repo_full_name
  key_admin_principals     = var.key_admin_principals
  github_oidc_provider_arn = var.github_oidc_provider_arn
  writer_policy_arn        = var.writer_policy_arn
  absa_verifier_principals = var.absa_verifier_principals
}
