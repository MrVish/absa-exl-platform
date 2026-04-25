# ADR-0003: Manifest signing via AWS KMS asymmetric keys

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-04-25 |
| Deciders | Engagement lead, EXL Platform Engineering |
| Consulted | ABSA Information Security |

## Context

Two pipelines produce manifests that downstream systems and auditors must verify, potentially years after the fact:

- **Code Intake (Phase 2)** signs the productized package handed off from the EXL Industrialization Team.
- **Pipeline Factory (Phase 2)** signs the generated pipeline manifest before it is registered.

Long-term verifiability is the load-bearing requirement. Verification must work in 2032 even if the original CI infrastructure is offline, and the cryptographic primitive must satisfy ABSA's information security review (which favours single-vendor AWS-rooted trust over web-of-trust constructs).

## Decision

Use **AWS KMS asymmetric CMKs (RSA-3072 default; ECC-NIST-P384 supported)** for all signing operations.

- The CMK lives in the EXL prod account (`exl-prod`). Cross-environment signatures are not part of the threat model — dev / stg pipelines either do not sign at all (drafts) or sign with a separate non-prod CMK.
- Signing is performed by GitHub Actions runners via `kms:Sign`. CI is the only signer (per the dual-mode generator-runtime decision; ADR for that follows in Phase 2).
- Each manifest stores: the signature bytes (base64), the CMK ARN, the algorithm, and the manifest's SHA-256 digest.
- Verification is supported via two paths:
  1. **Online** via `kms:Verify` against the live CMK.
  2. **Offline** by fetching the published public key from `s3://exl-platform-public-keys/manifest-signing/<key_id>/v<version>.pem` (versioned, world-readable bucket) and verifying with any standard RSA / ECC tooling.

## Consequences

### Positive

- AWS-native; no third-party transparency log dependency.
- CloudTrail logs every `kms:Sign` and `kms:Verify` automatically — first-class audit trail.
- Single-vendor trust root, which ABSA InfoSec preferred over Sigstore / cosign during the brainstorm.
- Public key publication means an auditor in 2032 can verify any historical signature even if the CMK has been disabled or the original CI runners no longer exist.
- Cost: ~$1/month per CMK plus a fraction of a cent per signing operation. Negligible for the 10-model cohort.

### Negative

- KMS asymmetric throughput is rate-limited (default 300 requests / second). Fine for a 10-model cohort signing manifests at most a few times per day per model. If the platform ever scales to thousands of pipelines / day, sharding across multiple CMKs is the documented workaround.
- IAM grant management: every CI workflow that signs needs `kms:Sign` granted on the specific CMK. Mitigated by a single shared GitHub Actions OIDC role that holds the grant.
- KMS asymmetric is region-bound: the CMK lives in one region. The published public key is region-agnostic, so verification works anywhere; signing requires that region to be available.

## Alternatives considered

1. **Sigstore / cosign with keyless OIDC signing.** Rejected: introduces Fulcio + Rekor as third-party dependencies. ABSA InfoSec was uncomfortable with the transparency-log model relative to KMS-rooted trust for a regulated bank workload.
2. **GPG / OpenPGP.** Rejected: key management (revocation, rotation, escrow) becomes the platform's problem; bank auditors today generally prefer cloud-rooted trust.
3. **AWS Signer (ACM Private CA backed).** Rejected: stronger fit for code-signing certificates than for arbitrary manifest signing; introduces ACM PCA as additional infrastructure for marginal benefit over raw KMS.
