locals {
  env = "prod"
  tags = {
    project     = "absa-exl-model-hosting"
    env         = local.env
    cost_center = "model-hosting"
  }
}
