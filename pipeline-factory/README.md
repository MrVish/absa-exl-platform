# pipeline-factory

Phase 2 Sprint 2. Turns a `model_config.yaml` into a complete, registry-routed
scoring pipeline. Built as a uv workspace member.

## What it produces

For every `pipeline-factory/configs/<name>/<version>/model_config.yaml`, the
generator writes four artifacts under `pipelines/<name>/<version>/`:

- `statemachine.json` — the rendered Step Functions ASL (parameterized; Phase 3
  fills in the real Lambda/SageMaker/EKS ARNs).
- `registration.json` — the body the registrar POSTs to the Registry API.
- `manifest.json` — the manifest envelope. Emitted **unsigned** (sentinel
  placeholders); sub-sprint 2.3 signs it with the KMS asymmetric CMK.
- `terraform/main.tf` — the per-pipeline Terraform stub (`aws_sfn_state_machine`
  + EventBridge schedule + IAM + KMS-encrypted log group). Plan-validate only
  in this sprint; Phase 3 wires it into env stacks.

## Onboarding a model

1. Add `pipeline-factory/configs/<name>/<version>/model_config.yaml` (validates
   against the canonical `model-config` JSON Schema from 2.1).
2. Run locally: `uv run generate-pipeline generate --config <path>`.
3. Commit both the config and the generated `pipelines/<name>/<version>/` dir.
4. Open the PR. CI re-renders and diffs (the drift gate) to confirm
   reproducibility.
5. On merge to `main`, CI runs `register` (when AWS credentials are available)
   and the new model lands in the Registry as `approval_status=pending`.
6. CAB + IVU evidence + `:approve` then flips it to `approved` (per ADR-0007).

## CLI

- `generate-pipeline validate --config <path>` — schema check, no side effects.
- `generate-pipeline generate --config <path>` — render the artifacts;
  `--force` overwrites without the drift check.
- `generate-pipeline register --pipeline <name>@<version>` — POST registration
  to the Registry API (SigV4); `--dry-run` logs what would be posted.

## Runtime modes (ADR-0008)

- **Local dev** — no creds, no API calls.
- **CI canonical** — drift gate on PR; `register` on merge to `main`. Only CI
  POSTs to the API.

See [`docs/adr/0008-generator-runtime-dual-mode.md`](../docs/adr/0008-generator-runtime-dual-mode.md).
