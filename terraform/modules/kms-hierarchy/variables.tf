variable "env" {
  description = "Deployment environment. Used in alias names and as a tag value."
  type        = string

  validation {
    condition     = contains(["dev", "stg", "prod"], var.env)
    error_message = "env must be one of dev, stg, prod."
  }
}

variable "tags" {
  description = "Tags applied to every CMK. Must include cost_center."
  type        = map(string)

  validation {
    condition     = contains(keys(var.tags), "cost_center")
    error_message = "tags must include cost_center."
  }
}
