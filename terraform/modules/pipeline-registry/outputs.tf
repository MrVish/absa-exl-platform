output "table_name" {
  description = "Name of the DynamoDB model registry table."
  value       = aws_dynamodb_table.this.name
}

output "table_arn" {
  description = "ARN of the DynamoDB model registry table."
  value       = aws_dynamodb_table.this.arn
}

output "kms_key_arn" {
  description = "ARN of the module-owned KMS CMK used for DynamoDB SSE and CloudWatch log encryption."
  value       = aws_kms_key.this.arn
}

output "lambda_function_arn" {
  description = "ARN of the registry Lambda function."
  value       = aws_lambda_function.this.arn
}

output "api_id" {
  description = "ID of the API Gateway v2 HTTP API."
  value       = aws_apigatewayv2_api.this.id
}

output "api_endpoint" {
  description = "Invoke URL for the API Gateway v2 HTTP API (e.g. https://<id>.execute-api.<region>.amazonaws.com)."
  value       = aws_apigatewayv2_api.this.api_endpoint
}

output "audit_log_group_name" {
  description = "Name of the CloudWatch log group for Lambda execution logs."
  value       = aws_cloudwatch_log_group.lambda.name
}

output "reader_policy_arn" {
  description = "ARN of the IAM policy granting read-only (GET) access to the registry API."
  value       = aws_iam_policy.reader.arn
}

output "writer_policy_arn" {
  description = "ARN of the IAM policy granting write (POST/PATCH) access to the registry API."
  value       = aws_iam_policy.writer.arn
}
