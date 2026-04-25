variable "env" {
  description = "Deployment environment."
  type        = string

  validation {
    condition     = contains(["dev", "stg", "prod"], var.env)
    error_message = "env must be one of dev, stg, prod."
  }
}

variable "absa_identity_center_saml_provider_arn" {
  description = "ARN of the ABSA-managed AWS IAM Identity Center SAML provider. Provided by ABSA's central platform team. Treated as opaque by this module."
  type        = string
}

variable "permissions_boundary_arn" {
  description = "ARN of the env-scoped permissions boundary policy created by the landing-zone module. Attached to all 5 roles in this module."
  type        = string
}

variable "github_org_slash_repo" {
  description = "GitHub repository in 'org/repo' form. Used to scope the OIDC trust policy sub condition."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$", var.github_org_slash_repo))
    error_message = "github_org_slash_repo must be in 'org/repo' form."
  }
}

variable "allowed_github_branches_for_apply" {
  description = "List of branch names from which the ci-deploy role may be assumed. Each entry produces a sub condition. Must contain at least one branch — empty list would remove the repo-scoping protection entirely."
  type        = list(string)
  default     = ["main"]

  validation {
    condition     = length(var.allowed_github_branches_for_apply) > 0
    error_message = "allowed_github_branches_for_apply must contain at least one branch (passing an empty list would remove repo-scoping in the ci-deploy OIDC trust policy)."
  }
}

variable "tags" {
  description = "Tags applied to every resource. Must include cost_center."
  type        = map(string)

  validation {
    condition     = contains(keys(var.tags), "cost_center")
    error_message = "tags must include cost_center."
  }
}
