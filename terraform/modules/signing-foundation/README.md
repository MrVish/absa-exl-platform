# `signing-foundation` Terraform module

Provisions the KMS asymmetric CMK, the GitHub Actions OIDC identity provider, two scoped IAM roles (`pipeline-factory-signer`, `pipeline-factory-registrar`), and two S3 buckets (`exl-platform-signed-manifests`, `exl-platform-public-keys`) used by the Phase 2 manifest-signing pipeline.

See [ADR-0009](../../../docs/adr/0009-signing-foundation-topology.md) for design rationale, [ADR-0003](../../../docs/adr/0003-manifest-signing-kms-asymmetric.md) for the broader signing posture, and [the Sprint 3 spec](../../../docs/superpowers/specs/2026-06-04-absa-exl-phase-2-sprint-3-signing-foundation-design.md) for the full context.

## Inputs

| Variable | Required | Default | Notes |
|---|---|---|---|
| `env` | yes | — | `exl-prod`, `exl-stg`, etc. |
| `region` | no | `eu-west-1` | POPIA proximity default |
| `repo_full_name` | yes | — | `<owner>/<repo>` for OIDC sub-claim |
| `allowed_refs` | no | `["refs/heads/main"]` | Refs allowed to assume signer / registrar |
| `key_admin_principals` | yes | — | Human admins / break-glass IAM principals |
| `absa_verifier_principals` | no | `[]` | Cross-account verifiers (populated post ABSA handoff) |
| `writer_policy_arn` | yes | — | From `pipeline-registry` module's existing output |
| `signed_manifests_bucket_name` | no | `exl-platform-signed-manifests` | |
| `public_keys_bucket_name` | no | `exl-platform-public-keys` | |
| `kms_alias_name` | no | `alias/absa-exl-manifest-signer-v1` | |

## Outputs

`kms_key_arn`, `kms_key_alias`, `signer_role_arn`, `registrar_role_arn`, `signed_manifests_bucket`, `public_keys_bucket`, `oidc_provider_arn`.

## Key policy

Four statements:
- `EnableRootAccount` — account root, `kms:*`.
- `KeyAdminsManage` — Describe/Update/Schedule deletion to `var.key_admin_principals`.
- `SignerSigns` — `kms:Sign` + `kms:GetPublicKey` + `kms:DescribeKey` to the signer role, conditioned on `kms:SigningAlgorithm = "RSASSA_PKCS1_V1_5_SHA_256"`.
- `AbsaVerifiers` (dynamic, only emitted when `var.absa_verifier_principals` non-empty) — `kms:Verify` + `kms:GetPublicKey` + `kms:DescribeKey` to ABSA cross-account principals.

## OIDC trust

Both roles use the same trust document — `sts:AssumeRoleWithWebIdentity` from the GitHub Actions IdP, conditioned on `token.actions.githubusercontent.com:aud = "sts.amazonaws.com"` and `:sub LIKE repo:<repo>:ref:<allowed-ref>`.

## tfsec

One expected suppression: `aws-s3-no-public-buckets` on `aws_s3_bucket_policy.public_keys_read`. Justified in ADR-0009 — public read on `manifest-signing/*` is the offline-audit story.
