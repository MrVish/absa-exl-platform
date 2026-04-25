variable "region" {
  description = "AWS region for the exl-stg account."
  type        = string
  default     = "af-south-1"
}

variable "transit_gateway_id" {
  type        = string
  description = "Upstream TGW ID. Provided by ABSA central platform team."
}

variable "source_replication_role_arn" {
  type        = string
  nullable    = true
  default     = null
  description = "ARN of the stg ABSA source replication role. Pass null on first apply (before source-side has applied); set to the real ARN via tfvars or -var for Phase 3 re-apply. See module README 'Apply order' for the full bootstrap sequence."
}

variable "source_account_id" {
  type        = string
  description = "AWS account ID of the ABSA account."
}
