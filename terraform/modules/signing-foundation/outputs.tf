output "kms_key_arn" {
  description = "ARN of the manifest-signing KMS asymmetric CMK."
  value       = aws_kms_key.manifest_signer.arn
}

output "kms_key_alias" {
  description = "Alias of the manifest-signing CMK."
  value       = aws_kms_alias.manifest_signer.name
}

output "signer_role_arn" {
  description = "ARN of the IAM role assumed by GitHub Actions to sign manifests."
  value       = aws_iam_role.signer.arn
}

output "registrar_role_arn" {
  description = "ARN of the IAM role assumed by GitHub Actions to POST/PATCH the registry."
  value       = aws_iam_role.registrar.arn
}

output "signed_manifests_bucket" {
  description = "Name of the S3 bucket holding signed manifest envelopes."
  value       = aws_s3_bucket.signed_manifests.id
}

output "public_keys_bucket" {
  description = "Name of the S3 bucket holding published public keys."
  value       = aws_s3_bucket.public_keys.id
}

output "oidc_provider_arn" {
  description = "ARN of the GitHub Actions OIDC identity provider."
  value       = aws_iam_openid_connect_provider.github_actions.arn
}
