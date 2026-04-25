variable "region" {
  description = "AWS region for the exl-prod account."
  type        = string
  default     = "af-south-1"
}

variable "transit_gateway_id" {
  type        = string
  description = "Upstream TGW ID. Provided by ABSA central platform team."
}

variable "source_replication_role_arn" {
  type        = string
  description = "Output replication_role_arn from the prod source stack."
}

variable "source_account_id" {
  type        = string
  description = "AWS account ID of the ABSA account."
}
