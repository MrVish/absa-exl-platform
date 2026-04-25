resource "aws_s3_bucket_policy" "this" {
  bucket = aws_s3_bucket.this.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowSourceReplicationRoleWrite"
        Effect = "Allow"
        Principal = {
          AWS = var.source_replication_role_arn
        }
        Action = [
          "s3:ReplicateObject",
          "s3:ReplicateDelete",
          "s3:ReplicateTags",
          "s3:ObjectOwnerOverrideToBucketOwner",
        ]
        Resource = "${aws_s3_bucket.this.arn}/*"
      },
      {
        Sid    = "AllowSourceAccountListBucket"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${var.source_account_id}:root"
        }
        Action = [
          "s3:GetBucketVersioning",
          "s3:PutBucketVersioning",
        ]
        Resource = aws_s3_bucket.this.arn
      },
    ]
  })
}
