variable "bucket_name" {
  description = "S3 bucket name for the source side. Convention: absa-model-handoff-{env}."
  type        = string
}

variable "env" {
  description = "Environment identifier."
  type        = string

  validation {
    condition     = contains(["dev", "stg", "prod"], var.env)
    error_message = "env must be one of dev, stg, prod."
  }
}

variable "retention_years" {
  description = "Default object-lock retention in years. 7 in prod; shorter overrides for dev / stg."
  type        = number
  default     = 7

  validation {
    condition     = var.retention_years >= 1 && var.retention_years <= 100
    error_message = "retention_years must be between 1 and 100."
  }
}

variable "prefix_filter" {
  description = "Object key prefix that scopes replication. Only objects under this prefix replicate."
  type        = string
  default     = "model-ready/"
}

variable "replication_time_control_enabled" {
  description = "Whether to enable Replication Time Control (15-minute SLA). Default true."
  type        = bool
  default     = true
}

variable "delete_marker_replication" {
  description = "Whether to replicate delete markers. Default false (deletes do not propagate)."
  type        = bool
  default     = false
}

variable "destination_bucket_arn" {
  description = "ARN of the EXL destination bucket. Output of s3-replication-destination."
  type        = string
}

variable "destination_kms_key_arn" {
  description = "ARN of the EXL destination KMS key. Output of s3-replication-destination."
  type        = string
}

variable "destination_account_id" {
  description = "AWS account ID of the EXL env account that owns the destination."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{12}$", var.destination_account_id))
    error_message = "destination_account_id must be a 12-digit AWS account ID."
  }
}

variable "tags" {
  description = "Tags applied to every resource. Must include cost_center."
  type        = map(string)

  validation {
    condition     = contains(keys(var.tags), "cost_center")
    error_message = "tags must include cost_center."
  }
}
