resource "aws_iam_role" "replication" {
  name = "${var.env}-s3-replication-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "s3.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_policy" "replication" {
  name        = "${var.env}-s3-replication-policy"
  description = "Permissions for the ${var.env} S3 replication role to read source and write destination."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadSourceBucket"
        Effect = "Allow"
        Action = [
          "s3:GetObjectVersionForReplication",
          "s3:GetObjectVersionAcl",
          "s3:GetObjectVersionTagging",
          "s3:ListBucket",
          "s3:GetReplicationConfiguration",
        ]
        Resource = [
          aws_s3_bucket.this.arn,
          "${aws_s3_bucket.this.arn}/*",
        ]
      },
      {
        Sid      = "DecryptWithSourceKey"
        Effect   = "Allow"
        Action   = "kms:Decrypt"
        Resource = aws_kms_key.this.arn
      },
      {
        Sid    = "WriteDestinationBucket"
        Effect = "Allow"
        Action = [
          "s3:ReplicateObject",
          "s3:ReplicateDelete",
          "s3:ReplicateTags",
          "s3:ObjectOwnerOverrideToBucketOwner",
        ]
        Resource = "${var.destination_bucket_arn}/*"
      },
      {
        Sid    = "EncryptWithDestinationKey"
        Effect = "Allow"
        Action = [
          "kms:Encrypt",
          "kms:GenerateDataKey",
        ]
        Resource = var.destination_kms_key_arn
      },
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "replication" {
  role       = aws_iam_role.replication.name
  policy_arn = aws_iam_policy.replication.arn
}
