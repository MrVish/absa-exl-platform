# ADR-0009: Signing Foundation Topology

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-06-04 |
| Deciders | Engagement lead, EXL Platform Engineering |
| Consulted | ABSA Information Security |
| Related | [ADR-0003](0003-manifest-signing-kms-asymmetric.md) (parent decision: KMS asymmetric signing), [ADR-0008](0008-generator-runtime-dual-mode.md), [Sprint 3 spec](../superpowers/specs/2026-06-04-absa-exl-phase-2-sprint-3-signing-foundation-design.md) |

> **Note (2026-06-11):** the OIDC provider section
> (`github_oidc_provider_arn`, `repo_full_name`, `allowed_refs`) is
> superseded by [ADR-0011: CI Platform — Jenkins](0011-ci-platform-jenkins.md).
> The KMS hierarchy, S3 keyspace, and registrar role's IAM scope are
> unchanged. The signer/registrar trust principal will be replaced with
> a Jenkins identity (IRSA on EKS preferred) once ABSA confirms the
> EKS cluster topology — see ADR-0011 §"Open questions".

## Context

ADR-0003 chose KMS asymmetric CMK signing for manifest envelopes but did not
pin the bucket layout, the IAM trust scopes, the signing algorithm, or the
idempotency posture. Sprint 3 needs those decisions concrete enough to build
infrastructure code against — and concrete enough that a reader in 2032 can
explain *why* a given bucket exists, why the CMK is configured the way it is,
and why a CI re-run does not corrupt the audit trail.

## Decision

### Key spec

RSA-3072 with signing algorithm `RSASSA_PKCS1_V1_5_SHA_256`. Chosen because
the algorithm is **deterministic** — signing the same digest twice produces
byte-identical output. This property is what makes content-addressable S3
storage and `s3:PutObject IfNoneMatch="*"`-based idempotency work
end-to-end. Re-signing the same manifest on a CI re-run produces the same
envelope, the same S3 object body, and a `412 PreconditionFailed` that the
signer treats as success.

### Wire form

The Python signer sends `MessageType="RAW"` with `canonical_json(payload)`
bytes rather than `MessageType="DIGEST"` with a precomputed SHA-256 digest.
Both paths produce byte-identical signatures under real AWS KMS (which
hashes RAW input server-side under `RSASSA_PKCS1_V1_5_SHA_256`). RAW is what
unblocks the moto v5 round-trip test (moto does not implement
`MessageType=DIGEST`).

### Location

The CMK lives in `exl-prod` only. No multi-region replica in Phase 2.
Cross-account verification is enabled via the key policy granting
`kms:Verify` + `kms:GetPublicKey` + `kms:DescribeKey` to a parameterised
list of ABSA principals (defaulted empty until handoff).

### OIDC IdP

The GitHub Actions OIDC provider in `exl-prod` is provisioned by the
`iam-federation` module (already in use). The `signing-foundation` module
**consumes** the existing provider ARN as a required input rather than
creating a duplicate (AWS allows only one OIDC IdP per (URL, account) pair).

### Roles & trust

Two distinct IAM roles assumed via GitHub Actions OIDC:

- `pipeline-factory-signer` — `kms:Sign` + `s3:PutObject` on the
  signed-manifests bucket.
- `pipeline-factory-registrar` — attaches the existing `pipeline-registry`
  writer policy granting `execute-api:Invoke`.

Both roles trust the same OIDC IdP and both gate on the same subject pattern
(`repo:MrVish/absa-exl-platform:ref:refs/heads/main` by default). The two
roles never share permissions.

### Algorithm enforcement

The KMS key policy's signer statement carries a `kms:SigningAlgorithm`
equality condition. Even if the signer role were over-permissioned, KMS
itself refuses any `kms:Sign` call with the wrong algorithm. The signer's
inline policy carries the same condition for defence-in-depth.

### Storage

- `s3://exl-platform-signed-manifests/<name>/<version>/manifest.json` —
  versioned, SSE-S3, all-public-access-blocked, `prevent_destroy` lifecycle.
  The audit-grade signed envelope.
- `s3://exl-platform-public-keys/manifest-signing/<key_id>/<version>.pem` —
  versioned, scoped public-read on `manifest-signing/*` (with
  `aws:SecureTransport=true` condition so anonymous reads require HTTPS).
  The audit-trail surface for offline verification by ABSA, internal
  auditors, and external regulators.

The committed manifest in git stays UNSIGNED (drift-gated). The signed copy
lives only in S3. This separation keeps the drift gate uncomplicated and
removes the need for CI to push commits.

### Idempotency

Sign-all on CI uses `s3:PutObject IfNoneMatch="*"` on every upload. The
deterministic algorithm guarantees the second-attempt body equals the
first; the precondition-failed response is silently swallowed by the
signer (412 treated as success). A workflow-level
`concurrency.group = pipeline-factory-sign` serialises near-simultaneous
merges to `main`. The publisher does NOT use `IfNoneMatch` — rotation is a
valid overwrite case for the same versioned path.

## Consequences

### Positive

- **Clean separation.** Signing and registration are independent CI jobs
  with separate IAM roles. Either can be replaced or extended without
  touching the other.
- **Offline-verifiable.** Anyone holding the public key from the published
  S3 bucket can verify any historical signed manifest with any standard
  RSA tooling. No AWS credentials needed. This is the audit story for
  ABSA, internal auditors, SARB GOI 3/5, ISO 27001, SOC 2 Type II.
- **CI-only signer.** No human path to `kms:Sign`. Key admins can
  describe / update / schedule deletion but cannot themselves sign.
- **Deterministic algorithm.** Bit-for-bit idempotent re-signs make CI
  re-runs safe.
- **Three-layer least privilege.** OIDC trust gates on the repo + ref.
  Inline role policy gates on actions + resources. KMS key policy gates on
  the algorithm.

### Negative (accepted)

- **No KMS auto-rotation.** Asymmetric KMS keys do not support automatic
  rotation. Rotation is a deliberate `v2`-alongside-`v1` operation:
  provision `v2` via Terraform, update the signer role's resource list to
  include both keys, switch the application config to sign with `v2`,
  publish `v2`'s public key, keep `v1` indefinitely for verification of
  historical manifests. The runbook is a Phase 3 ops deliverable.
- **Public-read S3 policy.** The public-keys bucket carries
  `Principal: "*"` on `s3:GetObject` for the `manifest-signing/*` prefix.
  `tfsec:ignore:aws-s3-no-public-buckets` annotated with a link to this
  ADR. The policy carries an `aws:SecureTransport=true` condition so reads
  must use HTTPS. Public read is the audit story, not a misconfiguration.
- **Sprint 4 schema decision deferred.** Whether to add a
  `signed_manifest_ref` field to the registry record is deferred to
  Sprint 4 once Code Intake's audit story makes the cost of the schema
  change concrete.

## Alternatives considered

1. **Symmetric HMAC.** Rejected. Verification by ABSA / external auditors
   would require shared secret distribution, defeating the audit story.
2. **ECC-NIST-P384.** Deferred. The deterministic property of
   `RSASSA_PKCS1_V1_5_SHA_256` matters more than the smaller key size;
   revisit if RSA performance ever becomes a bottleneck.
3. **Storing the signed manifest inline in the registry record.** Deferred
   to Sprint 4.
4. **Auto-committing the signed manifest back to git.** Rejected. Would
   require CI write perms, complicate the drift gate, and conflate
   source-of-truth with audit-grade artefact.

## Key rotation operational notes (informational)

Asymmetric KMS rotation is the inverse of standard symmetric rotation:

1. Provision `aws_kms_key.manifest_signer_v2` via the same Terraform module.
2. Keep `alias/absa-exl-manifest-signer-v1` pointing at `v1`; create new
   alias `alias/absa-exl-manifest-signer-v2` for `v2`.
3. Update the signer role's inline policy to include `kms:Sign` on both
   keys.
4. Update the application config (`AWS_KMS_SIGNING_KEY_ARN` secret) to
   point at `v2`.
5. Publish `v2`'s public key via `manifest-signer publish-key`.
6. Verifiers route on `envelope.signing_key_arn` — historical manifests
   signed by `v1` continue to verify against `v1`'s public key.
7. Retire `v1` only after all referenced manifests have expired (Phase 3
   ops decision).

**For the full step-by-step rotation procedure**, see the runbook at
[`docs/runbooks/kms-key-rotation.md`](../runbooks/kms-key-rotation.md)
(Phase 3 Sprint 3 deliverable). It covers triggers, pre-rotation
checklist, the 6-step rotation, dual-key verification smoke-tests,
and the explicit non-actions (don't delete old CMK, don't delete old
PEMs, don't re-sign historical manifests).
