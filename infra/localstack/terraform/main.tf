# AWS provider pointed at LocalStack instead of real AWS.
# Per spec section 4.3, every endpoint resolves to http://localhost:4566.
# LocalStack accepts any creds and any account; we use the canonical
# 111111111111 "exl-prod" sim account here. ABSA's 222222222222 sim
# account is referenced via var.external_verifier_arns and is
# materialised at runtime via the x-localstack-account-id header.
#
# NOTE on cleanup order: the reused signing-foundation module declares
# lifecycle { prevent_destroy = true } on both the signed-manifests
# and public-keys S3 buckets. As a result, `terraform destroy` against
# this stack will FAIL with "Resource cannot be destroyed". The demo
# orchestrator handles this in scripts/demo/__main__.py (T12) by
# registering cleanups in this order (LIFO unwind in reverse):
#   1. uvicorn kill        (innermost, registered last, fires first)
#   2. docker compose down -v   (discards LocalStack container + volumes)
#   3. terraform destroy   (best-effort; once docker-down has fired,
#                           the bucket resources are gone and destroy
#                           is a no-op against an empty state)
# If T12 ever reorders these, terraform destroy will start failing
# again and the demo will exit code 3 (DemoCleanupFailed) at teardown.

provider "aws" {
  region                      = "eu-west-1"
  access_key                  = "test"
  secret_key                  = "test"
  s3_use_path_style           = true
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true

  default_tags {
    tags = {
      Environment = "demo"
      ManagedBy   = "absa-exl-localstack-demo"
      Owner       = "exl-platform"
    }
  }

  endpoints {
    kms      = "http://localhost:4566"
    s3       = "http://localhost:4566"
    dynamodb = "http://localhost:4566"
    sts      = "http://localhost:4566"
    iam      = "http://localhost:4566"
  }
}

variable "external_verifier_arns" {
  description = <<-EOT
    Cross-account IAM ARNs granted kms:Verify + kms:GetPublicKey on the
    signing CMK (mapped to signing-foundation's absa_verifier_principals
    input) and s3:GetObject/s3:ListBucket on the signed-manifest bucket.
    The demo orchestrator passes [arn:aws:iam::222222222222:root] for the
    absa-sim account.
  EOT
  type        = list(string)
  default     = ["arn:aws:iam::222222222222:root"]
}

variable "env_name" {
  description = "Environment suffix used in resource names (one of dev/stg/prod, matches pipeline-registry validator)."
  type        = string
  default     = "dev"
}

variable "exl_account_id" {
  description = <<-EOT
    Canonical 'exl-prod' sim account ID used to synthesise the dummy
    OIDC provider ARN and root-account principal for the demo signer
    role. LocalStack doesn't actually verify these; the values just
    need to be syntactically valid.
  EOT
  type        = string
  default     = "111111111111"
}
