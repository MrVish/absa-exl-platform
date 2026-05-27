# registry

Phase 2 sprint 1 — Model & Pipeline Registry. The system of record for every model
version and its generated pipeline.

- `api/` — FastAPI app (single Lambda via Mangum) over DynamoDB; routes for
  create / get / list / patch and `:approve` / `:retire` transitions with a
  CAB+IVU-guarded approval gate (ADR-0007).
- `schema/` — pointer to the canonical schemas in `platform-contracts` (ADR-0006).

Terraform for the table + API lives in `terraform/modules/pipeline-registry/` and is
instantiated per env in `terraform/envs/{env}/registry/`.

Local dev: `uv run uvicorn registry_api.app:app --reload` (set `TABLE_NAME`).
Tests: `uv run pytest registry/api/tests`.
