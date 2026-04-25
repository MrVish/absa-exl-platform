locals {
  common_tags = merge(var.tags, {
    env    = var.env
    module = "iam-federation"
  })

  # GitHub Actions root CA thumbprint. Update if GitHub rotates the CA.
  # Confirmed at https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services
  github_oidc_thumbprint = "1c58a3a8518e8759bf075b76b750d4f2df264fcd"

  # Build the list of OIDC sub conditions, one per allowed branch.
  ci_deploy_sub_conditions = [
    for branch in var.allowed_github_branches_for_apply :
    "repo:${var.github_org_slash_repo}:ref:refs/heads/${branch}"
  ]
}

data "aws_caller_identity" "current" {}
