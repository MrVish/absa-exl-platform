# LocalStack End-to-End Demo Runbook

## What this demo proves

The full producer + verifier audit chain runs end-to-end against
LocalStack: Code Intake → Pipeline Factory → manifest-signer → publish
public key → register, then ABSA-side verifier fetches from S3, verifies
signatures, re-computes the chain digest, and queries the registry —
all under a simulated cross-account boundary using LocalStack CE's
`x-localstack-account-id` header.

Spec: `docs/superpowers/specs/2026-06-05-absa-exl-phase-3-sprint-1-localstack-demo-design.md`

## Prerequisites

- Docker Desktop running (Windows/macOS) or `dockerd` (Linux)
- Terraform >= 1.9.0
- `uv` (installed via `pip install uv` or platform installer)
- Port 4566 free (LocalStack) and port 8080 free (uvicorn)

Verify:

```bash
docker --version
terraform --version
uv --version
```

If any tool is missing, `python -m demo run` exits at Phase 0 with a clear hint.

## Running the demo

### One-shot

```bash
make demo
```

Equivalent to `uv run python -m demo run`. Typical wall-clock:
- ~15-30s on a warm Docker host (image already pulled)
- ~60-90s on a fresh runner (first-pull of `localstack/localstack:3.8.1` adds ~30s)

### Step-by-step

```bash
make demo-up         # docker compose up + terraform apply
make demo-status     # show container state
make demo-down       # tear down + remove volume
```

### Keep state for debugging

```bash
make demo-keep
# inspect LocalStack manually:
curl http://localhost:4566/_localstack/health | jq .
aws --endpoint-url http://localhost:4566 s3 ls s3://exl-signed-manifests-dev/
# tear down when done:
make demo-down
```

## What you should see

The demo prints structured progress to stdout. A green run looks like:

```
[demo]             prereqs OK: docker, terraform, uv
[demo]             up: docker compose up -d
[exl-prod-sim]     up: LocalStack ready
[exl-prod-sim]     up: terraform apply complete
[demo]             endpoints: kms=arn:aws:kms:eu-west-1:111111111111... manifest_bucket=exl-signed-manifests-dev registry_table=model_pipeline_registry-dev
[demo]             pipeline-registry up at http://localhost:8080
[exl-prod-sim]     3.1 code-intake validate                           (0.8s)
[exl-prod-sim]     3.2 code-intake generate-manifest                  (0.3s)
[exl-prod-sim]     3.3 manifest-signer sign (package)                 (1.4s)
[exl-prod-sim]     3.4 generate-pipeline generate                     (0.6s)
[demo]             chain digest verified between 3.4 and 3.5: 3b1134c4...
[exl-prod-sim]     3.5 manifest-signer sign-all (pipeline)            (1.2s)
[exl-prod-sim]     3.6 manifest-signer publish-key                    (0.4s)
[exl-prod-sim]     3.7 generate-pipeline register                     (0.7s)
[absa-sim]         4.1 fetch pipeline manifest (cross-account)        (0.2s)
[absa-sim]         4.2 fetch package manifest (cross-account)         (0.2s)
[absa-sim]         4.3 fetch public-key PEM (cross-account)           (0.2s)
[absa-sim]         4.4 verify_offline(pipeline)                       (0.3s)
[absa-sim]         4.5 verify_offline(package)                        (0.3s)
[demo]             chain digest re-verified (absa-side): 3b1134c4...
[absa-sim]         4.7 registry lookup                                (0.1s)
[demo]             verifier chain complete: all assertions hold
[demo]             DEMO PASSED
```

Exit code `0`. `demo-transcript.md` written.

## Troubleshooting

### "Cannot connect to the Docker daemon"

Docker Desktop isn't running (Windows/Mac) or the `dockerd` service is
stopped (Linux). Start Docker before running the demo.

### "port 4566 is already in use"

Another LocalStack instance is running. Either stop it (`make demo-down`)
or change the port mapping in `infra/localstack/docker-compose.yml`.

### "/readyz did not return 200 within 30s"

The pipeline-registry uvicorn process started but couldn't reach the
DDB table. Common causes:
- Terraform apply didn't actually create the table — check `infra/localstack/.uvicorn.log` for the boto3 stack trace
- DDB endpoint env var not propagating — verify `AWS_ENDPOINT_URL_DYNAMODB` in `scripts/demo/uvicorn_runner.py:_build_uvicorn_env`

### Chain digest mismatch

If you see "chain digest mismatch between package and pipeline manifests"
at step 3.5: either `upstream_resolver` produced a wrong digest, or
`code-intake generate-manifest` regenerated with a different payload
than what was signed at 3.3. Run the demo again; if persistent, this
is a regression worth filing.

### "[skip-existing] on a fresh run" at step 3.5

LocalStack persistence leaked across demo runs. Check that
`PERSISTENCE: 0` is set in `infra/localstack/docker-compose.yml`. Then
`make demo-clean` to force-tear-down and retry.

## CI behavior

The same demo runs in `.github/workflows/localstack-demo.yml` on every
PR touching producer-chain code. Exit code semantics:

| Exit | Meaning | Annotation | Blocks merge? |
|------|---------|------------|----------------|
| 0 | Chain verified | (none) | No |
| 1 | Platform regression | `::error::` | Yes |
| 2 | Infra failure | `::warning::` | No |
| 3 | Cleanup failed | `::warning::` | No |

Exit 1 produces a `demo-failure-bundle` artifact containing the
transcript, Terraform state, and uvicorn log.

## Architecture references

- Spec: `docs/superpowers/specs/2026-06-05-absa-exl-phase-3-sprint-1-localstack-demo-design.md`
- Implementation plan: `docs/superpowers/plans/2026-06-05-absa-exl-phase-3-sprint-1-localstack-demo.md`
- ADR-0009 (Signing): `docs/adr/0009-signing-foundation-kms-asymmetric.md`
- ADR-0010 (Package contract): `docs/adr/0010-productized-package-contract.md`
- Chain-of-custody anchor: package envelope's `digest` field == pipeline payload's `upstream_refs[0].digest`. Sprint 4 established this at digest `3b1134c4775a2b58ea8a57888a33e12ec697ea86fe6f905020427dcefabcbdf6`.
