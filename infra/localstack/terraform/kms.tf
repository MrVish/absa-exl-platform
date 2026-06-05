# Reuse the production signing-foundation module as-is.
#
# Module path: terraform/modules/signing-foundation
#   - creates the RSA-3072 SIGN_VERIFY KMS CMK + alias
#   - creates the signed-manifests + public-keys S3 buckets
#   - creates pipeline-factory-signer + pipeline-factory-registrar IAM roles
#
# Inputs mapped for LocalStack:
#   - env_name       -> env
#   - external_verifier_arns -> absa_verifier_principals (cross-account kms:Verify)
#   - github_oidc_provider_arn: synthesised dummy ARN. LocalStack accepts
#     any syntactically valid ARN here; the OIDC trust is never exercised
#     by the demo (the demo signs via static creds against LocalStack).
#   - key_admin_principals: account root, so any LocalStack caller in the
#     EXL account can administer the key.
#   - writer_policy_arn: wired from module.registry.writer_policy_arn,
#     so the registrar role can POST/PATCH the registry API.
#
# The signing-foundation module already creates the two S3 buckets with
# safe defaults (versioning, SSE, public-access-block). We don't redefine
# them in s3.tf -- s3.tf only adds the cross-account read policy for the
# signed-manifests bucket.

module "signing" {
  source = "../../../terraform/modules/signing-foundation"

  env                      = var.env_name
  region                   = "eu-west-1"
  repo_full_name           = "absa-exl/platform"
  github_oidc_provider_arn = "arn:aws:iam::${var.exl_account_id}:oidc-provider/token.actions.githubusercontent.com"
  key_admin_principals     = ["arn:aws:iam::${var.exl_account_id}:root"]
  absa_verifier_principals = var.external_verifier_arns
  writer_policy_arn        = module.registry.writer_policy_arn

  signed_manifests_bucket_name = "exl-signed-manifests-${var.env_name}"
  public_keys_bucket_name      = "exl-public-keys-${var.env_name}"
  kms_alias_name               = "alias/absa-exl-manifest-signer-${var.env_name}"
}
