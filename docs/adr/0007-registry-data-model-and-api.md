# ADR-0007: Registry data model & API

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-05-26 |
| Deciders | Engagement lead, EXL Platform Engineering |

## Context

The Model & Pipeline Registry is the Phase 2 system of record. The brief (§7)
fixes a DynamoDB table keyed by (model_name, version), fronted by a FastAPI API on
Lambda + API Gateway, with IAM-authed writes and CloudTrail audit. Open choices were
the API packaging, the access patterns / indexes, the approval workflow, and the
encryption key ownership.

## Decision

- Single DynamoDB table `model_pipeline_registry`, composite key
  `model_name` (PK) + `version` (SK); on-demand billing; PITR on; one GSI
  `by_status` (`approval_status` + `updated_at`) for approval/ops listing; full
  listing via scan (acceptable at 10-model scale).
- FastAPI runs as one Lambda via Mangum behind an API Gateway HTTP API with
  `AWS_IAM` (SigV4) authorization. Lambda Web Adapter is the documented migration
  path if scale/real-time needs arrive.
- Approval state machine `pending -> approved -> retired`, strictly ordered;
  `:approve` requires `cab_record_id` and `ivu_evidence_ref` (brief §9); status
  changes only via `:approve`/`:retire`, never via `PATCH`.
- The table SSE CMK and the API/Lambda log-group CMK are module-owned, per ADR-0005
  (workload data-class keys live in their owning module).
- Optimistic concurrency via a `rev` counter with DynamoDB condition expressions.

## Consequences

### Positive
- Matches the brief; minimal infra; strong local/`moto` test story.
- Audit-critical approval gate is enforced server-side and cannot be bypassed.

### Negative
- One IAM role spans all routes (read/write separation is by caller-role policy +
  CloudTrail), accepted at this scale.
- Scan-based full listing would need a rethink well beyond 10 models.

## Alternatives considered
1. Per-route Lambdas. Rejected: contradicts the brief's "FastAPI"; heavy infra.
2. Lambda Web Adapter container now. Rejected: needs ECR + build pipeline for no
   present benefit; retained as the future migration path.
