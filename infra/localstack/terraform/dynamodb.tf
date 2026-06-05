# Reuse the pipeline-registry module for the registry DDB table.
#
# Module path: terraform/modules/pipeline-registry
#   - creates the model_pipeline_registry DDB table + by_status GSI
#   - creates a module-owned KMS CMK for DDB SSE + CloudWatch log encryption
#   - creates the registry Lambda + API Gateway v2 (HTTP API) + IAM policies
#
# Inputs mapped for LocalStack:
#   - env: "dev" (must be one of dev/stg/prod per the module's validator)
#   - lambda_source_dir: registry/api/src, relative to this stack
#     (path.module = infra/localstack/terraform; needs 3x ../ to reach repo root)
#   - enable_deletion_protection: false -- the demo tears down + redeploys
#     every run, so deletion protection would block destroy
#   - log_retention_days: 1 -- minimum retention saves LocalStack a touch
#     of bookkeeping; the demo logs are ephemeral
#   - tags: cost_center is required by the module validator
#
# Output: module.registry.table_name (consumed by outputs.tf as registry_table),
# module.registry.writer_policy_arn (consumed by signing-foundation in kms.tf
# to wire the registrar role to POST/PATCH the registry API).

module "registry" {
  source = "../../../terraform/modules/pipeline-registry"

  env                        = var.env_name
  lambda_source_dir          = "${path.module}/../../../registry/api/src"
  log_retention_days         = 1
  enable_deletion_protection = false
  tags = {
    cost_center = "model-hosting"
    env         = var.env_name
  }
}
