# Exactly the 5 outputs DemoEndpoints.from_terraform_output() expects.
# Keep names in sync with scripts/demo/endpoints.py:_REQUIRED_KEYS:
#   kms_key_arn, kms_key_alias, manifest_bucket, public_key_bucket, registry_table
#
# Values come from the production modules' real output names (verified
# against terraform/modules/{signing-foundation,pipeline-registry}/outputs.tf).

output "kms_key_arn" {
  description = "ARN of the manifest-signing KMS asymmetric CMK."
  value       = module.signing.kms_key_arn
}

output "kms_key_alias" {
  description = "Alias name of the manifest-signing CMK (e.g. alias/absa-exl-manifest-signer-dev)."
  value       = module.signing.kms_key_alias
}

output "manifest_bucket" {
  description = "Bucket holding signed manifest envelopes (verifier reads from here)."
  value       = module.signing.signed_manifests_bucket
}

output "public_key_bucket" {
  description = "Bucket holding published RSA public keys for offline verification."
  value       = module.signing.public_keys_bucket
}

output "registry_table" {
  description = "DynamoDB table name for the model pipeline registry."
  value       = module.registry.table_name
}
