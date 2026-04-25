variable "region" {
  description = "AWS region for the ABSA-side dev resources."
  type        = string
  default     = "af-south-1"
}

variable "destination_bucket_arn" {
  description = "Output bucket_arn from the dev destination stack."
  type        = string
}

variable "destination_kms_key_arn" {
  description = "Output kms_key_arn from the dev destination stack."
  type        = string
}

variable "destination_account_id" {
  description = "AWS account ID of exl-dev."
  type        = string
}
