locals {
  azs               = slice(data.aws_availability_zones.available.names, 0, var.availability_zones)
  is_prod           = var.env == "prod"
  nat_gateway_count = local.is_prod ? var.availability_zones : 1
  name_prefix       = var.env

  common_tags = merge(var.tags, {
    env    = var.env
    module = "landing-zone"
  })
}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_kms_alias" "flow_logs_cw" {
  name = "alias/${var.env}-flow-logs-cw"
}
