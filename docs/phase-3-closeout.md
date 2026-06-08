# Phase 3 Closeout

**Status:** Phase 3 Sprints 1-3 merged to `main`. Ready for ABSA-side input or Phase 4 work.

**Last merged:** Sprint 3 (2a7fa8a) · `manifest-signer verify-from-bucket` CLI + KMS rotation runbook.

---

## What's now possible (delivered across Sprints 1-3)

### Demo and validation

- **`make demo`** runs the full producer + verifier chain against LocalStack CE on any developer's machine and on every PR via GitHub Actions. Producer chain: Code Intake → Pipeline Factory → manifest-signer → publish-key → register. Verifier chain: cross-account S3 fetch → verify-offline (pipeline + package) → re-computed chain-digest assertion → registry lookup.
- **Cross-account boundary** simulated via LocalStack CE's `x-localstack-account-id` header. Producer chain under `111111111111` (`exl-prod-sim`), verifier under `222222222222` (`absa-sim`). Exercises every cross-account IAM grant Sprint 3 wired into the signing-foundation module.
- **Chain-of-custody anchor** verified end-to-end: package envelope's `digest` field equals pipeline payload's `upstream_refs[0].digest` equals re-computed `sha256(canonical_json(package.payload))`. Holds across signing, S3 round-trip, and cross-account read.
- **Sample transcript** committed at `docs/runbooks/sample-transcripts/2026-06-09-demo.md` captures the canonical "what success looks like" for future regressions.

### Per-package isolation

- **`code-intake validate`** runs each package's `ruff`/`mypy`/`pytest` inside an **ephemeral per-package venv** materialized from `python/pyproject.toml`. Workspace toolchain is no longer used for package validation — what gets installed is exactly what the package declared.
- New finding code `PY004` hard-fails on packages missing `python/pyproject.toml`. No silent fallback to workspace deps.
- `python_pyproject_ref` field added to the package manifest payload, cryptographically anchoring the deps file in the signed envelope. An attacker can't swap pyproject.toml between sign and verify to change what the verifier installs.

### Stricter validation

- **PIR column extraction** handles f-string column names (`data[f"col_{n}"]` → glob `col_*`) and variable column names (`col = "tenure"; data[col]` → `"tenure"`) via intra-function constant propagation.
- New finding code `PIR002` warns when an f-string-derived glob matches zero PIR-declared columns (suspicious but not fatal).
- `manifest-signer sign-all` is strict on unknown `subject_type` (raises rather than silently routing to `pipelines/` prefix). Defense-in-depth against future schema additions.
- Subprocess timeouts on every `ruff`/`mypy`/`pytest` invocation in code-intake (`{CHECKER}998` finding on timeout vs `{CHECKER}999` on crash). CI hangs surfaced as findings instead of infrastructure failures.

### Operational tools

- **`manifest-signer verify-from-bucket`** — one-command verifier: `--bucket exl-signed-manifests-prod --key pipelines/<name>/<version>/manifest.json`. Auto-derives PEM path from envelope's `signing_key_arn`. Exits 0 valid / 1 invalid.
- **KMS asymmetric CMK rotation runbook** at `docs/runbooks/kms-key-rotation.md`. Closes the ADR-0009 day-2 ops deferral.
- **LocalStack demo runbook** at `docs/runbooks/localstack-demo.md` with troubleshooting for the top 5 failure modes.
- **CI gate semantics**: exit 0 = chain verified, exit 1 = platform regression (blocks merge), exit 2 = infra failure (warning, doesn't block), exit 3 = teardown leak (warning).

### Hygiene + reviewer follow-ups closed

From Sprint 2's bundled F0-F8:

- F0: `/healthz` + `/readyz` on `registry-api`
- F1: subprocess timeouts in code-intake checkers
- F2: `sign-all` strict on unknown `subject_type`
- F3: compliance matrix rows for ADR-0009 + ADR-0010
- F4: `DEFERRED-CHECK: SCH002/SCH003` markers in code-intake
- F5: `PipelineDriftError ← GeneratorError` consolidation
- F6: mypy duplicate-module `score` cleanup
- F7: regression test for `sign-all --continue-on-error`
- F8: `PirDataType.INT_TYPE` rename (no more builtin shadow)

---

## What's still deferred (Phase 4 candidates)

### Blocked on ABSA input

| Item | What we need | Where it surfaces |
|---|---|---|
| Real `exl-prod` + ABSA account onboarding | Account IDs, IAM principal ARNs | `infra/localstack/terraform/` → real per-env stacks |
| Real SAS validation | ABSA's SAS runtime Docker image + license terms | `code-intake/checkers/static_sas.py` (currently structural-only) |
| PIR system integration | ABSA's PIR system API spec | `code-intake/checkers/pir.py` (currently reads local `pir.yaml`) |
| First REAL Track A scoring run | All above, plus data-movement decision (S3 cross-account vs SFTP) | First production manifest in real S3 |
| CAB / IVU integration | ABSA governance API contract | `registry-api`'s approval state machine |
| Cross-account verifier exercise against real AWS | ABSA principal ARN with `kms:Verify` + `s3:GetObject` | Already wired in Sprint 3 IAM; awaits real ARN |

### Not blocked — platform-internal work

| Item | Effort | Source |
|---|---|---|
| **Lambda packaging for `registry-api`** | ~5-7 days | Sprint 1 §10 |
| **Real cross-account IAM with `sts:AssumeRole`** | ~4-5 days | Sprint 1 §10 |
| **Step Functions ASL runtime execution** | ~5-8 days + LocalStack Pro license decision | Sprint 1 §10 |
| **Multi-region KMS replica** | ~3-4 days + real AWS | Sprint 3 spec §11 |
| **Multi-package scenarios** (package-A → package-B chaining) | ~3-5 days | Sprint 1 §10 |
| **Promote `scripts/demo/` to `platform-demo/` workspace package** | ~2-3 days | Sprint 1 §10 |
| **Stricter PIR extraction**: dict aliases, `.get()`, cross-function flow | ~5-7 days | Sprint 2 §6.2 |
| **Asymmetric CMK key rotation automation** (currently runbook only) | ~3-4 days | Sprint 3 §4 |

---

## Phase 4 readiness checklist (for ABSA conversation)

When the ABSA team is ready to start real Phase 3 / Phase 4 work, they need to provide:

1. **AWS Account IDs** for:
   - ABSA receiving account(s)
   - Any additional EXL accounts beyond `exl-dev`/`exl-stg`/`exl-prod`
2. **IAM Principal ARNs** that need:
   - `kms:Verify` + `kms:GetPublicKey` on the EXL signing CMK
   - `s3:GetObject` on the EXL public-keys + signed-manifests buckets
3. **SAS runtime** — Docker image + license terms for full SAS validation (we currently do structural-only checks)
4. **PIR system contract** — API spec or feed format for the PIR mapping authority
5. **Data movement choice** — S3 cross-account replication or SFTP transfer for scoring inputs/outputs
6. **CAB / IVU API contract** for governance integration
7. **Network connectivity decision** — VPC peering, Transit Gateway, or PrivateLink for the cross-account data plane

Each of these unlocks 1-3 deferred items in the "blocked on ABSA input" table above.

---

## How the demo proves we're ready

The `make demo` exit-code-0 invariant captures the entire chain we can validate without ABSA inputs. As long as that stays green on every PR (gated by `.github/workflows/localstack-demo.yml`), we know:

- Code Intake validates packages correctly under per-package venv isolation
- Pipeline Factory generates byte-stable manifests + ASL templates
- The signer produces deterministic RSASSA-PKCS1-V1_5-SHA-256 signatures via KMS
- The cross-account boundary (header-simulated, but real IAM policy evaluation) grants the right principals the right permissions
- The chain-of-custody digest survives signing, S3 round-trip, and re-computation by a different boto3 session
- The registry API accepts SigV4-signed POSTs and returns canonical records
- An offline verifier with only the published PEM can validate any signed manifest

When real Phase 3 starts, the demo's structure becomes the real production flow — same CLIs, same code paths, same chain-of-custody assertions. Only the env-var-driven endpoints change (LocalStack → real AWS) and the boto3 session shape change (header-sim → real STS assume-role).

---

## Commits since Sprint 4 (Phase 2)

```
2a7fa8a Phase 3 Sprint 3: verify-from-bucket CLI + Key Rotation Runbook (#9)
49a5338 Phase 3 Sprint 2: CI Hardening + Per-Package Venv + Stricter PIR (#8)
3ac6835 Phase 3 Sprint 1: LocalStack End-to-End Demo + 9 Hygiene Follow-ups (#7)
```

Three sprints, ~50 commits, +5000 LOC across `scripts/demo/`, `code-intake/`, `manifest-signer/`, `infra/localstack/`, `docs/runbooks/`. 278 workspace tests passing. Chain digest: `7905ac3a51b0076e71c3b129fd071eec177d87196ccb715ad5a8ede2e9c8870b`.

---

## Recommended next sprint (when work resumes)

**Option A — Lambda packaging for `registry-api` (highest production value).** Today the registry runs as `uvicorn` locally for the demo. Real prod needs Lambda+APIGW deploy artifacts. This is the largest gap between "demo works" and "deployable to real AWS".

**Option B — Promote `scripts/demo/` to `platform-demo/` workspace package (smallest, fastest).** Refactor: gives the orchestrator its own `pyproject.toml`, dedicated tests, importable from CI scripts. Cleans up the "not-quite-a-workspace-member" carveout from Phase 3 Sprint 1.

**Option C — Multi-package scenario fixture (medium, exercises chain).** Add a second package that depends on `credit-risk-pd@1.0.0`. Exercises the `upstream_refs[]` array as more than a one-element-list. Validates the cryptographic chain handles N-deep manifests.

**Recommendation: A (Lambda packaging)** when real-AWS work is on the horizon. Otherwise **C (multi-package)** for the highest demonstrable improvement to the demo's narrative.
