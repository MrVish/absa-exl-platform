# -------- Signed manifests bucket (private, audit anchor) --------

resource "aws_s3_bucket" "signed_manifests" {
  bucket = var.signed_manifests_bucket_name
  tags = {
    Sprint = "phase-2-sprint-3"
    ADR    = "0009"
    env    = var.env
    region = var.region
  }
}

resource "aws_s3_bucket_versioning" "signed_manifests" {
  bucket = aws_s3_bucket.signed_manifests.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_ownership_controls" "signed_manifests" {
  bucket = aws_s3_bucket.signed_manifests.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "signed_manifests" {
  bucket = aws_s3_bucket.signed_manifests.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "signed_manifests" {
  bucket                  = aws_s3_bucket.signed_manifests.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# -------- Public keys bucket (scoped public read on manifest-signing/*) --------

resource "aws_s3_bucket" "public_keys" {
  bucket = var.public_keys_bucket_name
  tags = {
    Sprint = "phase-2-sprint-3"
    ADR    = "0009"
    env    = var.env
    region = var.region
  }
}

resource "aws_s3_bucket_versioning" "public_keys" {
  bucket = aws_s3_bucket.public_keys.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_ownership_controls" "public_keys" {
  bucket = aws_s3_bucket.public_keys.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "public_keys" {
  bucket = aws_s3_bucket.public_keys.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "public_keys" {
  bucket                  = aws_s3_bucket.public_keys.id
  block_public_acls       = true
  block_public_policy     = false # required for the scoped read policy below
  ignore_public_acls      = true
  restrict_public_buckets = false # required for the scoped read policy below
}

data "aws_iam_policy_document" "public_keys_read" {
  statement {
    sid       = "AllowPublicReadOfPublishedKeys"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.public_keys.arn}/manifest-signing/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
  }
}

# tfsec:ignore:aws-s3-no-public-buckets see docs/adr/0009-signing-foundation-topology.md
resource "aws_s3_bucket_policy" "public_keys_read" {
  bucket = aws_s3_bucket.public_keys.id
  policy = data.aws_iam_policy_document.public_keys_read.json
}
