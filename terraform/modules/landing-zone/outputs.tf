output "vpc_id" {
  description = "VPC ID for the env."
  value       = aws_vpc.this.id
}

output "private_subnet_ids" {
  description = "Private subnet IDs for compute workloads."
  value       = aws_subnet.private[*].id
}

output "data_subnet_ids" {
  description = "Data subnet IDs for stateful workloads (DB, ElastiCache, etc.)."
  value       = aws_subnet.data[*].id
}

output "public_subnet_ids" {
  description = "Public subnet IDs (NAT gateways live here)."
  value       = aws_subnet.public[*].id
}

output "flow_logs_log_group_arn" {
  description = "ARN of the CloudWatch log group capturing VPC flow logs."
  value       = aws_cloudwatch_log_group.flow_logs.arn
}

output "guardduty_detector_id" {
  description = "GuardDuty detector ID, or null if disabled."
  value       = try(aws_guardduty_detector.this[0].id, null)
}

output "permissions_boundary_arn" {
  description = "ARN of the env-scoped permissions boundary policy. Attach this to workload IAM roles."
  value       = aws_iam_policy.env_scoped_boundary.arn
}
