variable "env" {
  description = "Environment identifier (exl-prod, exl-stg, etc.)."
  type        = string
}

variable "region" {
  description = "AWS region. Defaults to eu-west-1 for POPIA proximity to ABSA; override per-env if needed."
  type        = string
  default     = "eu-west-1"
}

variable "repo_full_name" {
  description = "GitHub repository in <owner>/<repo> form for OIDC sub-claim trust."
  type        = string
  validation {
    condition     = can(regex("^[^/[:space:]]+/[^/[:space:]]+$", var.repo_full_name))
    error_message = "repo_full_name must be in <owner>/<repo> form (no protocol, no extra slashes, no whitespace)."
  }
}

variable "allowed_refs" {
  description = "List of GitHub refs allowed to assume the signer and registrar roles. Defaults to refs/heads/main only."
  type        = list(string)
  default     = ["refs/heads/main"]
  validation {
    condition     = alltrue([for r in var.allowed_refs : startswith(r, "refs/")])
    error_message = "allowed_refs entries must start with 'refs/' (e.g. refs/heads/main, refs/tags/v1.0.0)."
  }
}

variable "github_oidc_provider_arn" {
  description = "ARN of the GitHub Actions OIDC identity provider in this AWS account. Created upstream by the iam-federation module (see terraform/modules/iam-federation/outputs.tf:26 `github_oidc_provider_arn`). This module consumes the existing provider rather than creating a duplicate (only one OIDC provider per (URL, account) pair is allowed in AWS)."
  type        = string
}

variable "key_admin_principals" {
  description = "ARNs allowed to administer the KMS key (Describe/Update/Schedule deletion). Human admins or break-glass roles."
  type        = list(string)
}

variable "absa_verifier_principals" {
  description = "Cross-account ABSA IAM principals allowed kms:Verify + kms:GetPublicKey on the signing CMK. Defaults to empty until ABSA handoff."
  type        = list(string)
  default     = []
}

variable "writer_policy_arn" {
  description = "ARN of the pipeline-registry writer IAM policy. Attached to the registrar role for execute-api:Invoke on POST/PATCH routes."
  type        = string
}

variable "signed_manifests_bucket_name" {
  description = "Name of the S3 bucket holding signed manifest envelopes."
  type        = string
  default     = "exl-platform-signed-manifests"
}

variable "public_keys_bucket_name" {
  description = "Name of the S3 bucket holding published public keys for offline verification."
  type        = string
  default     = "exl-platform-public-keys"
}

variable "kms_alias_name" {
  description = "Alias for the signing CMK (must start with alias/)."
  type        = string
  default     = "alias/absa-exl-manifest-signer-v1"
}
