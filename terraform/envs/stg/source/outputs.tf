output "replication_role_arn" {
  description = "ARN of the replication IAM role. Pass to the matching exl-stg destination stack as var.source_replication_role_arn."
  value       = module.replication_source.replication_role_arn
}

output "bucket_arn" {
  description = "ARN of the source bucket."
  value       = module.replication_source.bucket_arn
}

output "kms_key_arn" {
  description = "ARN of the source-side KMS CMK."
  value       = module.replication_source.kms_key_arn
}
