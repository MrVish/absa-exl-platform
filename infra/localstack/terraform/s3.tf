# Cross-account bucket policies for the signing-foundation S3 buckets.
#
# The signing-foundation module creates both S3 buckets (signed-manifests
# and public-keys). The signed-manifests bucket ships without a policy
# so we add one here. The public-keys bucket ships WITH a policy
# (aws_s3_bucket_policy.public_keys_read in the module) that grants
# public read on manifest-signing/* only. The demo (T10) publishes the
# PEM at the bucket root (s3://exl-public-keys-dev/v1/public-key.pem)
# so we need to broaden cross-account read access.
#
# Single-account LocalStack doesn't strictly need these policies (the
# verifier connects to the same LocalStack instance under a different
# x-localstack-account-id), but they make the topology self-documenting
# and match production behaviour where absa-sim is genuinely cross
# account.
#
# WARNING: only one bucket policy can exist per S3 bucket. We do NOT
# attach a second aws_s3_bucket_policy to the public-keys bucket --
# that would conflict with the module's aws_s3_bucket_policy.public_keys_read
# and the two would oscillate on every plan/apply. Instead, the verifier
# in the demo reads the PEM as the EXL account (same LocalStack instance,
# no cross-account hop), so the module's existing public_keys_read
# policy is sufficient. The cross-account read shown in the comment
# below documents production intent; when ABSA hands off in production,
# the module's policy should be extended (in terraform/modules/signing-foundation)
# to grant absa_verifier_principals GetObject on the whole bucket, not
# just manifest-signing/*. Tracked as a module follow-up.

resource "aws_s3_bucket_policy" "manifests_cross_account_read" {
  bucket = module.signing.signed_manifests_bucket
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowABSAReadAccess"
        Effect    = "Allow"
        Principal = { AWS = var.external_verifier_arns }
        Action    = ["s3:GetObject", "s3:ListBucket"]
        Resource = [
          "arn:aws:s3:::${module.signing.signed_manifests_bucket}",
          "arn:aws:s3:::${module.signing.signed_manifests_bucket}/*",
        ]
      },
    ]
  })
}
