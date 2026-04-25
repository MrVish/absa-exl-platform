locals {
  common_tags = merge(var.tags, {
    env    = var.env
    module = "iam-federation"
  })

  # GitHub Actions OIDC thumbprint, updated 2023 to use the current root CA.
  # Note: AWS provider 5.36+ ignores thumbprint_list at runtime for JWKS-backed
  # providers like GitHub Actions — token validation goes through the JWKS
  # endpoint. The thumbprint is required by the resource schema but not
  # load-bearing for security. Update if GitHub publishes a new value.
  github_oidc_thumbprint = "6938fd4d98bab03faadb97b34396831e3780aea1"

  # Build the list of OIDC sub conditions, one per allowed branch.
  ci_deploy_sub_conditions = [
    for branch in var.allowed_github_branches_for_apply :
    "repo:${var.github_org_slash_repo}:ref:refs/heads/${branch}"
  ]
}
