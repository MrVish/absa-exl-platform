variable "env" {
  type        = string
  description = "Deployment environment. Must be one of dev, stg, prod."
  validation {
    condition     = contains(["dev", "stg", "prod"], var.env)
    error_message = "env must be one of dev, stg, prod."
  }
}

variable "table_name" {
  type        = string
  description = "Name of the DynamoDB table that stores model registry records."
  default     = "model_pipeline_registry"
}

variable "lambda_source_dir" {
  type        = string
  description = "Path to the registry_api source tree zipped into the deployment artifact."
}

variable "lambda_runtime" {
  type        = string
  description = "Lambda runtime identifier (e.g. python3.12)."
  default     = "python3.12"
}

variable "log_retention_days" {
  type        = number
  description = "Number of days to retain CloudWatch log events."
  default     = 365
}

variable "enable_deletion_protection" {
  type        = bool
  description = "Whether to enable DynamoDB deletion protection. Set false only for ephemeral dev teardowns."
  default     = true
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to every resource. Must include cost_center."

  validation {
    condition     = contains(keys(var.tags), "cost_center")
    error_message = "tags must include cost_center."
  }
}
