# pipeline-registry

Phase 2 sprint 1. Provisions the Model & Pipeline Registry: a DynamoDB table
`model_pipeline_registry` (composite key `model_name` + `version`, `by_status` GSI,
PITR, module-owned KMS SSE, deletion protection) fronted by a single-Lambda FastAPI
app (`registry_api.app.handler`) behind an API Gateway HTTP API with `AWS_IAM` auth.

The CMK is module-owned per ADR-0005 (workload data-class keys live in their owning
module; `kms-hierarchy` owns audit-evidence keys only).

Plan-validate only in sprint 1; real dependency packaging and `apply` land when AWS
credentials are available.
