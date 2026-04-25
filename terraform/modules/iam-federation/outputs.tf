output "platform_engineer_role_arn" {
  description = "ARN of the SAML-trust platform engineer role (8h session, SystemAdministrator-class permissions within boundary)."
  value       = aws_iam_role.platform_engineer.arn
}

output "platform_operator_role_arn" {
  description = "ARN of the SAML-trust platform operator role (4h session, read everything plus narrow operational write)."
  value       = aws_iam_role.platform_operator.arn
}

output "platform_readonly_role_arn" {
  description = "ARN of the SAML-trust readonly role (8h session, ReadOnlyAccess managed policy)."
  value       = aws_iam_role.platform_readonly.arn
}

output "break_glass_role_arn" {
  description = "ARN of the SAML-trust break-glass role (1h session, AdministratorAccess, MFA required). AssumeRole triggers a CloudTrail metric-filter alarm."
  value       = aws_iam_role.break_glass.arn
}

output "ci_deploy_role_arn" {
  description = "ARN of the OIDC-trust CI deploy role (1h session, * minus credential / key / audit destruction)."
  value       = aws_iam_role.ci_deploy.arn
}

output "github_oidc_provider_arn" {
  description = "ARN of the GitHub Actions OIDC provider for this account."
  value       = aws_iam_openid_connect_provider.github.arn
}
