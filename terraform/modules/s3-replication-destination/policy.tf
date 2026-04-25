locals {
  source_role_bucket_grant = var.source_replication_role_arn == null ? [] : [{
    Sid       = "AllowSourceReplicationRoleWrite"
    Effect    = "Allow"
    Principal = { AWS = var.source_replication_role_arn }
    Action = [
      "s3:ReplicateObject",
      "s3:ReplicateDelete",
      "s3:ReplicateTags",
      "s3:ObjectOwnerOverrideToBucketOwner",
    ]
    Resource = "${aws_s3_bucket.this.arn}/*"
  }]

  source_account_bucket_grant = {
    Sid       = "AllowSourceAccountReadBucketVersioning"
    Effect    = "Allow"
    Principal = { AWS = "arn:aws:iam::${var.source_account_id}:root" }
    Action    = "s3:GetBucketVersioning"
    Resource  = aws_s3_bucket.this.arn
  }
}

resource "aws_s3_bucket_policy" "this" {
  bucket = aws_s3_bucket.this.id

  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = concat(local.source_role_bucket_grant, [local.source_account_bucket_grant])
  })
}
