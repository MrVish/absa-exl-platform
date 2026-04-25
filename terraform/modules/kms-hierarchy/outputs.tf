output "cloudtrail_bucket_key_arn" {
  description = "ARN of the CloudTrail bucket CMK. Pass to aws_s3_bucket_server_side_encryption_configuration on the trail bucket."
  value       = aws_kms_key.cloudtrail_bucket.arn
}

output "cloudtrail_bucket_key_alias" {
  description = "Alias of the CloudTrail bucket CMK."
  value       = aws_kms_alias.cloudtrail_bucket.name
}

output "flow_logs_cw_key_arn" {
  description = "ARN of the flow-logs / CloudWatch Logs CMK. Pass as kms_key_id on aws_cloudwatch_log_group resources."
  value       = aws_kms_key.flow_logs_cw.arn
}

output "flow_logs_cw_key_alias" {
  description = "Alias of the flow-logs / CW Logs CMK."
  value       = aws_kms_alias.flow_logs_cw.name
}

output "manifest_signing_key_arn" {
  description = "ARN of the manifest-signing CMK. Returns null until Phase 2 implements ADR-0003."
  value       = null
}
