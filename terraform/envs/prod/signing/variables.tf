variable "region" {
  description = "AWS region for the signing stack."
  type        = string
  default     = "eu-west-1"
}

variable "repo_full_name" {
  description = "GitHub repository in <owner>/<repo> form. Must match the OIDC sub-claim trust on the signer / registrar roles."
  type        = string
}

variable "key_admin_principals" {
  description = "ARNs allowed to administer the signing CMK (Describe/Update/Schedule deletion). Typically the platform-engineer role from iam-federation."
  type        = list(string)
}

variable "github_oidc_provider_arn" {
  description = "ARN of the GitHub Actions OIDC provider in the exl-prod account. Source: terraform output github_oidc_provider_arn from terraform/account-bootstrap/exl-prod after that stack is applied."
  type        = string
}

variable "writer_policy_arn" {
  description = "ARN of the registry writer IAM policy. Source: terraform output writer_policy_arn from terraform/envs/prod/registry after that stack is applied."
  type        = string
}

variable "absa_verifier_principals" {
  description = "Cross-account ABSA IAM principals allowed kms:Verify on the signing CMK. Defaults to empty until ABSA handoff."
  type        = list(string)
  default     = []
}
