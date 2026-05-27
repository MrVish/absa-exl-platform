# pipeline-registry

Phase 2 sprint 1. Provisions the Model & Pipeline Registry: a DynamoDB table
`model_pipeline_registry` (composite key `model_name` + `version`, `by_status` GSI,
PITR, module-owned KMS SSE, deletion protection) fronted by a single-Lambda FastAPI
app (`registry_api.app.handler`) behind an API Gateway HTTP API with `AWS_IAM` auth.

The CMK is module-owned per ADR-0005 (workload data-class keys live in their owning
module; `kms-hierarchy` owns audit-evidence keys only).

Plan-validate only in sprint 1; real dependency packaging and `apply` land when AWS
credentials are available.

## Deferred to apply sprint

The following hardening items are tracked for the apply sprint and are intentionally
out of scope for the plan-validate sprint 1:

- **Reserved concurrency** — set `reserved_concurrent_executions` on
  `aws_lambda_function.this` to cap blast radius; value TBD with ops team.
- **X-Ray tracing** — enable `tracing_config { mode = "Active" }` on the Lambda and
  add `xray:PutTraceSegments` / `xray:PutTelemetryRecords` to the Lambda IAM policy.
- **API Gateway stage throttling** — configure `default_route_settings` throttling
  (`throttling_burst_limit`, `throttling_rate_limit`) on `aws_apigatewayv2_stage.default`.
- **Configurable log level** — expose a `log_level` input variable (default `"INFO"`)
  and wire it into the Lambda `environment.variables` block; currently hardcoded.
- **`lambda_runtime` validation** — add a `validation` block to `var.lambda_runtime`
  constraining it to known supported runtimes (e.g. `python3.12`, `python3.11`).
- **`table_name` validation** — add a `validation` block to `var.table_name` enforcing
  DynamoDB naming rules (1–255 chars, alphanumeric / `-` / `_` / `.`).
