output "bucket_arn" {
  description = "ARN of the destination bucket. Pass this to the source-side module."
  value       = aws_s3_bucket.this.arn
}

output "bucket_id" {
  description = "ID (name) of the destination bucket."
  value       = aws_s3_bucket.this.id
}

output "kms_key_arn" {
  description = "ARN of the destination KMS CMK. Pass this to the source-side module."
  value       = aws_kms_key.this.arn
}

output "kms_key_alias" {
  description = "KMS alias for the destination key."
  value       = aws_kms_alias.this.name
}

output "sns_topic_arn" {
  description = "SNS topic ARN. Per-env stacks attach subscriptions to this topic."
  value       = aws_sns_topic.replication_alerts.arn
}

output "replication_metric_alarm_arn" {
  description = "ARN of the ReplicationLatency CloudWatch alarm."
  value       = aws_cloudwatch_metric_alarm.replication_latency.arn
}

output "failed_replication_alarm_arn" {
  description = "ARN of the OperationsFailedReplication CloudWatch alarm."
  value       = aws_cloudwatch_metric_alarm.failed_replication.arn
}
