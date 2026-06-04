output "writer_policy_arn" {
  description = "ARN of the registry writer IAM policy (execute-api:Invoke on POST/PATCH routes). Consumed by terraform/envs/prod/signing."
  value       = module.registry.writer_policy_arn
}

output "reader_policy_arn" {
  description = "ARN of the registry reader IAM policy (execute-api:Invoke on GET routes)."
  value       = module.registry.reader_policy_arn
}

output "api_endpoint" {
  description = "Invoke URL for the registry API Gateway."
  value       = module.registry.api_endpoint
}
