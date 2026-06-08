# Phase 3 Sprint 3 — Verify-from-bucket CLI + Key Rotation Runbook

**Status:** Design approved (autonomous mode) · 2026-06-09
**Sprint window:** ~3-4 engineer-days
**Branch:** `phase-3/sprint-3-verify-cli-rotation`

---

## 1. Goal

Two small, independent capabilities that unblock ABSA-side operations
without depending on real-AWS handover:

1. **`manifest-signer verify-from-bucket` CLI subcommand** — gives ABSA ops a
   one-command verifier flow: `manifest-signer verify-from-bucket --bucket
   exl-signed-manifests-prod --key pipelines/credit-risk-pd/1.0.0/manifest.json`.
   Today verification requires manually downloading the manifest, then running
   `verify-offline` against a locally-cached PEM. The new command does both
   in one shot.

2. **Asymmetric CMK key rotation runbook** — ADR-0009 deferred. Documents the
   day-2 ops procedure: when to rotate, how to rotate without breaking
   verification of historical manifests (kept under previous key version),
   and a small CLI helper to publish the new public key. No infra changes;
   pure documentation + a small CLI helper.

## 2. Scope decisions

| Decision | Choice |
|---|---|
| New CLI subcommand | `manifest-signer verify-from-bucket --bucket X --key Y [--region eu-west-1] [--public-key-uri s3://...]` |
| PEM auto-discovery | If `--public-key-uri` omitted, derive from KMS key ARN in the envelope (`manifest-signing/<key_id>/<version>.pem`) using the same bucket — fall back to `--bucket-public-keys`-style override |
| Runbook location | `docs/runbooks/kms-key-rotation.md` |
| Rotation helper | `manifest-signer publish-key --key-arn ... --version v2` is already there from Sprint 3; runbook references it |
| Tests | Unit tests for the new CLI subcommand with moto-mocked S3 + KMS |

## 3. Architecture

```
manifest-signer verify-from-bucket
├── Reads manifest envelope from s3://<bucket>/<key>
├── Extracts key_arn from envelope.key_arn
├── Derives PEM path: manifest-signing/<key_id>/<version>.pem
│   (or uses --public-key-uri override)
├── Reads PEM from s3://<public_keys_bucket>/<derived_path>
├── Calls manifest_signer.verifier.verify_offline(envelope, pem)
└── Exits 0 on valid; 1 on invalid (prints VerificationError detail)
```

Out of scope (deferred):
- Online verification flag (`--use-kms-verify` — already available via existing `verify-online`)
- Cross-account assume-role chain (uses default boto3 session)
- Batch verify (verify multiple manifests in one invocation)

## 4. Key rotation runbook content

Sections:
- **When to rotate:** schedule + ad-hoc triggers (suspected compromise, ABSA contract milestone, annual default)
- **Pre-rotation checklist:** announce, confirm no in-flight sign workflows, snapshot current public key archive
- **Rotation steps:**
  1. KMS `CreateKey` for new asymmetric CMK (or rotate alias to new key)
  2. `manifest-signer publish-key --key-arn <new> --version v2` uploads new PEM
  3. Update `manifest-signer/terraform/signing-foundation` key alias variable + `terraform apply`
  4. Verify both old (v1) and new (v2) PEMs accessible
  5. Smoke test: sign a fresh manifest with new key, verify-offline against new PEM
- **Post-rotation:** retain old PEM forever (historical manifests still verify), update ADR-0009 with rotation date

## 5. Implementation tasks

```
T1. manifest-signer verify-from-bucket CLI                          [1.5d]
   - Add cli.py subcommand
   - Add tests with moto mocks
   - Update README

T2. Key rotation runbook                                            [1d]
   - docs/runbooks/kms-key-rotation.md
   - Cross-reference from ADR-0009

T3. Final verification + PR                                         [0.5d]
```

## 6. Acceptance criteria

1. `manifest-signer verify-from-bucket --help` lists the new flags
2. `uv run pytest manifest-signer/` passes including new CLI tests
3. `manifest-signer verify-from-bucket` against a moto-mocked valid manifest exits 0
4. Same against a tampered manifest exits 1 with `VerificationError` detail
5. Runbook lives at `docs/runbooks/kms-key-rotation.md` and is referenced from ADR-0009
6. `uv run pytest && uv run ruff check && uv run mypy` all green
7. PR opened
