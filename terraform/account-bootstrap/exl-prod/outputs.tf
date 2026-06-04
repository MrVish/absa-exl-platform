output "github_oidc_provider_arn" {
  description = "ARN of the GitHub Actions OIDC identity provider in the exl-prod account. Consumed by downstream env stacks (e.g. envs/prod/signing) so they do not attempt to create a duplicate provider (AWS allows only one per (URL, account) pair)."
  value       = module.iam_federation.github_oidc_provider_arn
}

output "platform_engineer_role_arn" {
  description = "ARN of the SAML-trust platform engineer role. Typically passed as a key admin principal to downstream stacks."
  value       = module.iam_federation.platform_engineer_role_arn
}

output "platform_operator_role_arn" {
  description = "ARN of the SAML-trust platform operator role."
  value       = module.iam_federation.platform_operator_role_arn
}

output "platform_readonly_role_arn" {
  description = "ARN of the SAML-trust readonly role."
  value       = module.iam_federation.platform_readonly_role_arn
}

output "ci_deploy_role_arn" {
  description = "ARN of the OIDC-trust CI deploy role used by terraform-apply workflows."
  value       = module.iam_federation.ci_deploy_role_arn
}
