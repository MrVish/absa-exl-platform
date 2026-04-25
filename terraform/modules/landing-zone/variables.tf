variable "env" {
  description = "Deployment environment. Used as a tag and as a name prefix on every taggable resource."
  type        = string

  validation {
    condition     = contains(["dev", "stg", "prod"], var.env)
    error_message = "env must be one of dev, stg, prod."
  }
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC. Must not overlap with other env CIDRs in the same account."
  type        = string

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "vpc_cidr must be a valid IPv4 CIDR."
  }
}

variable "availability_zones" {
  description = "Number of AZs to span. Must be at most the count of AZs in the region."
  type        = number
  default     = 3

  validation {
    condition     = var.availability_zones >= 2 && var.availability_zones <= 4
    error_message = "availability_zones must be between 2 and 4."
  }
}

variable "transit_gateway_id" {
  description = "ID of the upstream Transit Gateway. Owned by the central platform team."
  type        = string
}

variable "flow_logs_retention_days" {
  description = "Retention for VPC flow logs in CloudWatch. Defaults to 365 in prod, 30 elsewhere via env tfvars."
  type        = number
  default     = 30
}

variable "tags" {
  description = "Tags to apply to every resource. Must include cost_center."
  type        = map(string)

  validation {
    condition     = contains(keys(var.tags), "cost_center")
    error_message = "tags must include cost_center."
  }
}
