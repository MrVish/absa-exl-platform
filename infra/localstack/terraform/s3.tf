# Cross-account bucket policy on the signed-manifests bucket.
#
# The signing-foundation module creates both S3 buckets (signed-manifests
# and public-keys) along with a public-read policy on
# public-keys/manifest-signing/*. That public-read covers the demo's
# offline-verify chain end-to-end.
#
# The signed-manifests bucket ships from the module without a bucket
# policy, so we attach one here that grants absa-sim (222222222222)
# read+list -- this is the verifier-chain dependency spec section 6.4
# calls out. Single-account LocalStack doesn't strictly need the policy
# (the verifier connects to the same LocalStack instance under a
# different x-localstack-account-id), but the policy makes the topology
# self-documenting and matches production behaviour.

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
