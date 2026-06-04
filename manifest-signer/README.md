# `manifest-signer`

KMS-backed signing and verification for manifest envelopes produced by the Phase 2 Pipeline Factory (and, in Sprint 4, by Code Intake).

See [Sprint 3 spec](../docs/superpowers/specs/2026-06-04-absa-exl-phase-2-sprint-3-signing-foundation-design.md), [ADR-0003](../docs/adr/0003-manifest-signing-kms-asymmetric.md), and [ADR-0009](../docs/adr/0009-signing-foundation-topology.md).

## Subcommands

| Command | Use case |
|---|---|
| `manifest-signer sign --manifest <path> --key-arn <arn> --signer-principal <arn> [--upload-to s3://...] [--in-place] [--dry-run]` | Sign a single manifest file. `--dry-run` skips KMS and prints what would be signed. `--upload-to` uploads to S3 with `IfNoneMatch="*"`. `--in-place` overwrites the local file. |
| `manifest-signer sign-all --root <dir> --key-arn <arn> --upload-to-bucket <bucket> --signer-principal <arn>` | CI workhorse. Globs `<root>/*/*/manifest.json`, signs every UNSIGNED one, uploads to S3. Derives `<name>/<version>` from the manifest's payload. `412 PreconditionFailed` is treated as success. |
| `manifest-signer verify-online --manifest <path>` | KMS round-trip verification against the live CMK. Exit 0 / 1. |
| `manifest-signer verify-offline --manifest <path> --public-key <path>` | Local verification with no AWS access required, against a PEM-encoded public key. |
| `manifest-signer publish-key --key-arn <arn> --bucket <name> [--version v1]` | One-shot: fetch CMK public key, PEM-encode, upload to S3. Run after first apply and on each key rotation. |

## Library API

```python
from manifest_signer.signer import sign_envelope
from manifest_signer.verifier import verify_online, verify_offline
from manifest_signer.publisher import publish_public_key
```

All three functions are pure with respect to their `kms_client` / `s3_client` parameters — pass moto-mocked clients in tests, real boto3 clients in production.

## Idempotency

`sign_envelope` follows a three-state contract: UNSIGNED → sign; same-key signed → no-op (returns the input object unchanged); different-key signed → `KeyMismatchError`. Combined with the deterministic `RSASSA_PKCS1_V1_5_SHA_256` algorithm, this makes CI re-runs safe at the S3 layer (same bytes, same object, `IfNoneMatch="*"` returns 412 silently).

## Testing

The package's 34 tests (across `test_signer.py`, `test_verifier_online.py`, `test_verifier_offline.py`, `test_publisher.py`, `test_cli.py`, `test_canonical_compat.py`, `test_errors.py`, `test_smoke.py`, `test_e2e.py`) all use `moto v5` for AWS mocking — no real AWS credentials required to run them. From the repo root:

```bash
uv run pytest manifest-signer/tests
```

The end-to-end test (`test_e2e.py`) exercises the full sign-all → verify-online → verify-offline flow inside one moto context, proving the CI signing step works without AWS credentials.

## Architecture

| Module | Responsibility |
|---|---|
| `manifest_signer.signer` | Fills the four UNSIGNED sentinel fields via `kms:Sign`. Idempotent three-state contract. |
| `manifest_signer.verifier` | `verify_online` via `kms:Verify`; `verify_offline` via `cryptography` against a PEM. |
| `manifest_signer.publisher` | `kms:GetPublicKey` → PEM-encode → upload to S3. |
| `manifest_signer.cli` | Click CLI exposing `sign`, `sign-all`, `verify-online`, `verify-offline`, `publish-key`. |
| `manifest_signer.errors` | `SignerError`, `KeyMismatchError`, `VerificationError`. |

Canonical-JSON encoding (used for the signature digest) lives in `platform_contracts.canonical.canonical_json` — shared with `pipeline-factory` so both producer and consumer agree byte-for-byte.
