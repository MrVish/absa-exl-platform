variable "bucket_name" {
  description = "Destination bucket name. Convention: exl-model-landing-{env}."
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
  description = "Default object-lock retention in years. 7 prod default; shorter overrides for dev / stg."
  type        = number
  default     = 7

  validation {
    condition     = var.retention_years >= 1 && var.retention_years <= 100
    error_message = "retention_years must be between 1 and 100."
  }
}

variable "source_replication_role_arn" {
  description = "ARN of the source-side replication role. Granted permission to write into this bucket and use this KMS key."
  type        = string
}

variable "source_account_id" {
  description = "AWS account ID of the ABSA source side."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{12}$", var.source_account_id))
    error_message = "source_account_id must be a 12-digit AWS account ID."
  }
}

variable "alarm_threshold_seconds" {
  description = "ReplicationLatency alarm threshold. Default 900s = 15 minutes (matches RTC SLA)."
  type        = number
  default     = 900
}

variable "tags" {
  description = "Tags applied to every resource. Must include cost_center."
  type        = map(string)

  validation {
    condition     = contains(keys(var.tags), "cost_center")
    error_message = "tags must include cost_center."
  }
}
