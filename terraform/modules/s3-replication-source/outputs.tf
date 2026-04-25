output "bucket_arn" {
  description = "ARN of the source bucket."
  value       = aws_s3_bucket.this.arn
}

output "bucket_id" {
  description = "ID (name) of the source bucket."
  value       = aws_s3_bucket.this.id
}

output "kms_key_arn" {
  description = "ARN of the source-side KMS CMK."
  value       = aws_kms_key.this.arn
}

output "kms_key_alias" {
  description = "Alias of the source-side KMS CMK."
  value       = aws_kms_alias.this.name
}

output "replication_role_arn" {
  description = "ARN of the IAM role used by S3 to replicate. Pass this to the destination side."
  value       = aws_iam_role.replication.arn
}
