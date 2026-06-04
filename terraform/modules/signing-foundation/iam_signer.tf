resource "aws_iam_role" "signer" {
  name               = "pipeline-factory-signer"
  description        = "Assumed by GitHub Actions on push to main to sign manifest envelopes via kms:Sign."
  assume_role_policy = data.aws_iam_policy_document.github_trust.json
}

data "aws_iam_policy_document" "signer_perms" {
  statement {
    sid       = "SignManifestsWithFixedAlgorithm"
    actions   = ["kms:Sign"]
    resources = [aws_kms_key.manifest_signer.arn]
    condition {
      test     = "StringEquals"
      variable = "kms:SigningAlgorithm"
      values   = ["RSASSA_PKCS1_V1_5_SHA_256"]
    }
  }

  statement {
    sid       = "GetPublicKeyForVerifyHelpers"
    actions   = ["kms:GetPublicKey", "kms:DescribeKey"]
    resources = [aws_kms_key.manifest_signer.arn]
  }

  statement {
    sid       = "WriteSignedManifests"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.signed_manifests.arn}/*"]
  }

  statement {
    sid       = "PublishPublicKeyArtifact"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.public_keys.arn}/manifest-signing/*"]
  }
}

resource "aws_iam_role_policy" "signer_perms" {
  name   = "signer-perms"
  role   = aws_iam_role.signer.id
  policy = data.aws_iam_policy_document.signer_perms.json
}
