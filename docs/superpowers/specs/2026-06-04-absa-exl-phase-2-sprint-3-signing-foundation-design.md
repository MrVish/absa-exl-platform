# ABSA × EXL Phase 2 Sprint 3 — Signing & OIDC Foundation (Design)

**Status:** Accepted (design phase)
**Date:** 2026-06-04
**Branch:** `phase-2/sprint-3-signing-foundation`
**Predecessors:** Sprint 1 (Registry & Shared Contracts, merged `dbac0e5`), Sprint 2 (Pipeline Factory, merged `f028b65`).
**Successor:** Sprint 4 (Code Intake + First Track A Run) — depends on this sprint's CMK, OIDC provider, and `manifest-signer` module.

---

## 1 · Goal

Stand up the cryptographic and identity foundation that turns the unsigned manifest envelopes produced by the Pipeline Factory (and, in Sprint 4, by Code Intake) into audit-grade signed artefacts. Concretely:

- A KMS asymmetric customer-managed key (CMK) for envelope signing.
- A GitHub Actions OpenID Connect identity provider in AWS, and two least-privileged IAM roles assumed via that provider — one for signing, one for registry writes (deferred from Sprint 2).
- A small Python package (`manifest-signer`) that fills the four sentinel placeholders the Pipeline Factory emits (`signature`, `signing_key_arn`, `signing_algorithm`, `signer_principal`) and uploads the resulting signed envelope to S3.
- A CI step in `pipeline-factory.yml` that runs the signer on merges to `main` before the registrar invokes the API.
- Public-key publication so any party — internal auditor, ABSA reviewer, external regulator — can verify any historical signed manifest offline without holding AWS credentials.

Out of this sprint, Code Intake's signing path (Sprint 4) and the first end-to-end Track A run reuse this foundation unchanged.

---

## 2 · Decomposition context

The original Phase 2 plan in the Sprint 1 spec (§1) treated "Code Intake + first end-to-end run" as a single sub-sprint 2.3. During the design phase we split that into two:

- **Sprint 3 (this document)** — Signing & OIDC Foundation. Pure infrastructure plus a small shared Python module. Once shipped, both Sprint 2's Pipeline Factory and Sprint 4's Code Intake produce signed manifests through the same path.
- **Sprint 4 (next)** — Code Intake validators (SAS / Python static scans, schema, tests, PIR mapping), plus the first end-to-end Track A run wiring a worked example through Code Intake → Pipeline Factory → Registry.

The split mirrors the earlier decomposition of Phase 2 itself into three sub-sprints (Registry, Pipeline Factory, Code Intake+run): the signing foundation is independently shippable, de-risks Code Intake by providing the signing prerequisites up front, and lets Sprint 2's existing UNSIGNED manifests be retroactively signed by the first merge after this sprint lands.

---

## 3 · Scope and non-goals

### 3.1 In scope

1. **KMS asymmetric CMK** `absa-exl-manifest-signer-v1` in `exl-prod`, key spec `RSA_3072`, key usage `SIGN_VERIFY`, signing algorithm `RSASSA_PKCS1_V1_5_SHA_256`. Aliased; multi-region disabled; key rotation `false` (asymmetric KMS keys do not support automatic rotation — the rotation strategy is documented in ADR-0009 as a `v2`-alongside-`v1` operation). Key policy grants `kms:Sign` only to the signer role and only when the algorithm condition is met; grants `kms:Verify` + `kms:GetPublicKey` + `kms:DescribeKey` to a parameterised list of verifier principals (ABSA accounts, defaulted empty until handoff).
2. **GitHub Actions OIDC identity provider** in `exl-prod`. One-time bootstrap; reused by both new IAM roles.
3. **`signer` IAM role.** Trust policy gates on the IdP, the `aud` claim (`sts.amazonaws.com`), and the `sub` claim (`repo:MrVish/absa-exl-platform:ref:refs/heads/main`). Inline policy grants `kms:Sign` with an `kms:SigningAlgorithm` equality condition + `kms:GetPublicKey` + `kms:DescribeKey` + `s3:PutObject` on the signed-manifest bucket prefix + `s3:PutObject` on the public-keys bucket `manifest-signing/*` prefix.
4. **`pipeline-factory-registrar` IAM role** (deferred from Sprint 2). Same trust template as the signer role. Inline policy attaches the `writer_policy_arn` exported by the existing `pipeline-registry` Terraform module — `execute-api:Invoke` on the registry's POST and PATCH routes.
5. **Two S3 buckets** in `exl-prod`:
   - `exl-platform-signed-manifests` — versioned, SSE-S3, bucket-owner-enforced object ownership, all four public-access-block flags `true`. Stores the audit-grade signed envelope at `<name>/<version>/manifest.json`.
   - `exl-platform-public-keys` — versioned, SSE-S3, bucket-owner-enforced, `block_public_policy = false` and `restrict_public_buckets = false` so a scoped read policy can apply. Bucket policy grants `s3:GetObject` to `Principal: "*"` on the `manifest-signing/*` prefix only. Stores the published public key at `manifest-signing/<key_id>/<version>.pem`.
6. **`manifest-signer` uv workspace member.** Four modules — `signer.py`, `verifier.py`, `publisher.py`, `cli.py` — with a Click CLI exposing `sign`, `sign-all`, `verify-online`, `verify-offline`, `publish-key`. Online verifier uses `kms:Verify`; offline verifier uses `cryptography` against a PEM-encoded public key — both code paths required by ADR-0003 and exercised by tests.
7. **One small refactor of prior sprint code:** move `canonical_json` from `pipeline-factory/src/pipeline_factory/hashing.py` to `platform-contracts/src/platform_contracts/canonical.py`. The canonicalisation rules belong to the envelope contract, not to any one consumer. `pipeline-factory`'s internal imports update accordingly. The `writer_policy_arn` output on the `pipeline-registry` module already exists from Sprint 1 ([`outputs.tf:41-44`](terraform/modules/pipeline-registry/outputs.tf)); the new registrar role attaches to it via `terraform_remote_state` lookup.
8. **CI signing step.** New `sign` job inserted between the existing `drift-gate` and `register` jobs in `.github/workflows/pipeline-factory.yml`. Runs on push to `main` only, gated by `vars.AWS_SIGNER_ROLE_ARN != ''`. Assumes the signer role via OIDC, calls `manifest-signer sign-all`, uploads signed envelopes to S3. Concurrency group prevents back-to-back merges racing. `register` then runs with `needs: sign`.
9. **Key-publication workflow.** New `.github/workflows/publish-signing-key.yml` (manual `workflow_dispatch`) runs `manifest-signer publish-key` to upload the CMK's public key to the public-keys bucket. One-shot after first apply; re-run on each rotation.
10. **ADR-0009 — Signing Foundation Topology** (new) and a minor edit to ADR-0003 (point to concrete bucket names + cross-reference 0009).

### 3.2 Out of scope (explicitly deferred)

- Code Intake validators (SAS / Python static scans, schema, tests, PIR mapping) → Sprint 4.
- First end-to-end Track A run with a worked-example model → Sprint 4.
- Signing the Code Intake "package manifest" payload (same envelope contract, different `subject_ref.type`) → Sprint 4 uses this sprint's `manifest-signer` module unchanged.
- Cross-account `kms:Verify` exercised from a real ABSA principal — included in the key policy but no ABSA-side runner exists yet → exercised in Sprint 4 or Phase 3.
- Multi-region KMS replica → Phase 4 DR.
- Live `terraform apply` against real AWS accounts — still dev-mode (the brief has not handed over real account IDs). All Terraform passes `validate` / `tflint` / `tfsec` cleanly; runtime behaviour is exercised entirely via `moto v5` until real accounts exist.
- `signed_manifest_ref` field on the registry record — re-evaluate in Sprint 4 once Code Intake's audit story makes the cost of the schema change concrete.
- Key rotation runbook (operational mechanics of bringing `v2` alongside `v1`, publishing both public keys, retiring `v1`). ADR-0009 documents the approach; the actual runbook is a Phase 3 ops concern.

### 3.3 Platform-boundary statement

A property of the whole platform, not just this sprint, but worth nailing down here because the IAM and KMS resources we are about to define depend on it:

- **All control-plane components run in EXL accounts.** That includes the Pipeline Registry (DynamoDB, Lambda, API Gateway in `exl-prod`), the KMS signing CMK, the GitHub Actions OIDC provider, the signer/registrar IAM roles, the two S3 buckets specified above, the Step Functions state machines (per-pipeline, `exl-prod` for tier-1, `exl-runtime` for tier-2 EKS), and the SageMaker/EKS scoring runtimes.
- **ABSA's role on the control plane is read-only verification and audit.** Specifically: `kms:Verify` against the CMK, `s3:GetObject` on the public-keys bucket, IAM-signed reads against the Registry API (a reader-policy is surfaced in Sprint 4 or Phase 3), and access to the registry audit log.
- **Scoring data movement is a parallel concern with two open options**, neither of which is part of this sprint and neither of which changes the signing/registration design:
  - *Option A* — ABSA→EXL S3 cross-account replication with Replication Time Control (Pattern Z in the proposal deck v3.0). The brief's recommended option; still open pending ABSA infra confirmation.
  - *Option B* — SFTP. Legacy fallback if cross-account replication is rejected.

  Whichever wins plugs into the data-source step at the front of each per-pipeline Step Functions definition (the `DataQuality` precursor step templated in Sprint 2). Manifests and registry records describe the **model**, not its data path; this sprint is unaffected by the choice.

---

## 4 · Architecture

### 4.1 Account topology and resources

Everything net-new in this sprint lives in `exl-prod`. The four-account Pattern Z topology from the proposal deck is unchanged.

```
exl-prod (this sprint adds:)
├── KMS CMK    absa-exl-manifest-signer-v1     (RSA-3072, SIGN_VERIFY)
│   └── alias/absa-exl-manifest-signer-v1
├── IAM
│   ├── OIDC IdP  token.actions.githubusercontent.com
│   ├── Role      pipeline-factory-signer       (kms:Sign + s3:PutObject)
│   └── Role      pipeline-factory-registrar    (execute-api:Invoke)
└── S3
    ├── bucket    exl-platform-signed-manifests (private, versioned, SSE-S3)
    └── bucket    exl-platform-public-keys      (Principal:* on manifest-signing/*)

ABSA accounts (absa-prod, absa-mod, absa-shared)
└── (no resources; read-only via the CMK's key policy + public-keys bucket policy)
```

### 4.2 Per-pipeline CI flow on push to `main`

```
                    +---------------+
                    | drift-gate    |   (PR + push to main; unchanged from Sprint 2)
                    +-------+-------+
                            |
                            v
                    +---------------+
                    | sign          |   (push to main only; this sprint's net-new step)
                    | role: signer  |
                    +-------+-------+
                            |
                            |  for each pipelines/*/*/manifest.json
                            |    where .signature == "UNSIGNED":
                            |      1. canonical_json(payload)        --> bytes
                            |      2. sha256(canonical_bytes)        --> 32-byte digest
                            |      3. kms:Sign(KeyId, Digest,
                            |                  SigningAlgorithm=RSASSA_PKCS1_V1_5_SHA_256,
                            |                  MessageType=DIGEST)   --> signature
                            |      4. fill envelope sentinel fields
                            |      5. s3:PutObject(IfNoneMatch="*")  --> uploaded or 412 (idempotent)
                            v
                    +---------------+
                    | register      |   (push to main only; Sprint 2 logic; needs: sign)
                    | role:registrar|
                    +---------------+
                            |
                            v
              POST/PATCH Pipeline Registry API   (IAM-signed via SigV4)
```

### 4.3 Key design properties

- **Deterministic algorithm.** `RSASSA_PKCS1_V1_5_SHA_256` produces byte-identical signatures for the same digest. Re-signing the same manifest yields the same envelope, so the S3 object is content-addressable. `s3:PutObject` with `IfNoneMatch="*"` returns `412 PreconditionFailed` on the second attempt; the signer treats `412` as success.
- **Decoupling.** The signer does not know about the registry. The registrar does not know about KMS. They are sequenced by CI, not by code. Either can be replaced in isolation.
- **Offline verifiability.** Any party holding the public key from `s3://exl-platform-public-keys/manifest-signing/<key_id>/<version>.pem` can recompute the canonical digest of the payload, verify the signature with any standard RSA tooling, and prove the envelope is authentic. No AWS credentials required. This is the audit story for ABSA, internal auditors, and external regulators (SARB GOI 3/5, ISO 27001, SOC 2 Type II).
- **Least privilege at three layers.** (a) The IdP trust policy gates which repo and which ref can assume each role; (b) the role's inline policy gates which actions and which resources; (c) the KMS key policy enforces the algorithm at the platform boundary, refusing any `kms:Sign` call with the wrong `SigningAlgorithm` even if a role is somehow over-permissioned.
- **Dev-mode friendly.** Until ABSA hands over real account IDs, `moto v5` provides full asymmetric KMS coverage (sign / verify / get-public-key) and S3 coverage (put-object with `IfNoneMatch`, get-object). All tests run with no AWS credentials. Terraform stays at `validate` + `tflint` + `tfsec` until real accounts exist.

---

## 5 · Repository layout

### 5.1 Net-new directories and files

```
manifest-signer/                                  (new uv workspace member)
├── pyproject.toml                                (entry point: manifest-signer)
├── README.md
├── src/manifest_signer/
│   ├── __init__.py
│   ├── signer.py                                 # sign_envelope()
│   ├── verifier.py                               # verify_online(), verify_offline()
│   ├── publisher.py                              # publish_public_key()
│   ├── cli.py                                    # Click: sign / sign-all / verify-online / verify-offline / publish-key
│   └── errors.py                                 # SignerError, VerificationError, KeyMismatchError
└── tests/
    ├── conftest.py                               # moto KMS + S3 fixtures, sample envelope, real RSA keypair fixture
    ├── test_signer.py
    ├── test_verifier_online.py
    ├── test_verifier_offline.py
    ├── test_publisher.py
    ├── test_cli.py
    ├── test_canonical_compat.py                  # guards the canonical_json move (Section 7.4)
    └── test_e2e.py                               # full sign-all CLI flow vs moto

platform-contracts/src/platform_contracts/
└── canonical.py                                  # MOVED from pipeline_factory.hashing.canonical_json

terraform/modules/signing-foundation/             (new TF module)
├── README.md
├── versions.tf                                   # terraform >= 1.5, aws ~> 5.0
├── variables.tf
├── outputs.tf
├── kms.tf                                        # aws_kms_key + aws_kms_alias + key policy
├── oidc.tf                                       # aws_iam_openid_connect_provider
├── iam_signer.tf                                 # signer role + trust + inline perms
├── iam_registrar.tf                              # registrar role + trust + writer_policy attachment
└── s3.tf                                         # signed-manifests + public-keys buckets

terraform/envs/exl-prod/signing/                  (new per-env stack)
├── main.tf
├── backend.tf                                    # s3 backend, state-prefix = signing
├── variables.tf
├── outputs.tf
└── terraform.tfvars

terraform/modules/pipeline-registry/outputs.tf    (additive: writer_policy_arn output)

.github/workflows/pipeline-factory.yml            (extend: sign job between drift-gate and register)
.github/workflows/publish-signing-key.yml         (new: manual workflow_dispatch)

docs/adr/
├── 0009-signing-foundation-topology.md           (new)
└── 0003-controlled-handoff.md                    (minor edit: storage layout subsection)

docs/superpowers/specs/2026-06-04-...-design.md   (this spec)
docs/superpowers/plans/2026-06-04-...-plan.md     (written next, by the writing-plans skill)

pyproject.toml (root)                             # add "manifest-signer" to workspace members
```

### 5.2 Refactor notes (`canonical_json` move)

Currently `pipeline_factory.hashing.canonical_json` does deterministic JSON encoding for Sprint 2's manifest builder: `json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"`. (Pretty-printed sort-keys form with a trailing newline — chosen for human-readability of the committed manifest file; the digest is over the byte output, so the format choice is fixed by Sprint 2's existing manifests.) We move it to `platform_contracts.canonical.canonical_json` because the encoding rules belong to the envelope contract — both producers (Pipeline Factory, future Code Intake) and consumers (signer, verifier) need to agree on them byte-for-byte.

Mechanics:
- New module `platform-contracts/src/platform_contracts/canonical.py` with the same function (verbatim — the implementation is the contract).
- `pipeline-factory/src/pipeline_factory/hashing.py` loses the `canonical_json` definition; its internal callers (`manifest.py`, `generator.py`, `renderer.py`) update their imports to `from platform_contracts.canonical import canonical_json`.
- `pipeline-factory/pyproject.toml` has `platform-contracts` as a workspace dependency already (from Sprint 2); no dependency change.
- `manifest-signer/pyproject.toml` adds `platform-contracts` as a workspace dependency.
- `test_canonical_compat.py` in `manifest-signer` and `pipeline-factory` re-asserts byte-identical output on a battery of fixture payloads. If the move accidentally changes encoding, the test fails before the refactor lands.

No external consumer imports `pipeline_factory.hashing.canonical_json` today (verified during Sprint 2 design); no backwards-compatibility shim required.

### 5.3 Pre-existing `writer_policy_arn` output

Sprint 1's `pipeline-registry` module already exports `output "writer_policy_arn"` at `terraform/modules/pipeline-registry/outputs.tf:41-44` (the IAM policy itself is `aws_iam_policy.writer`). The Sprint 3 `signing-foundation` module declares `var.writer_policy_arn` and uses it via `aws_iam_role_policy_attachment`; the per-env `exl-prod/signing` stack reads the value via `data "terraform_remote_state"` lookup against the registry stack's output. No changes required to the `pipeline-registry` module itself.

---

## 6 · Terraform module — `signing-foundation`

### 6.1 KMS CMK and key policy

```hcl
resource "aws_kms_key" "manifest_signer" {
  description              = "ABSA x EXL manifest envelope signer (RSA-3072)"
  key_usage                = "SIGN_VERIFY"
  customer_master_key_spec = "RSA_3072"
  deletion_window_in_days  = 30
  enable_key_rotation      = false               # asymmetric KMS keys do not support auto-rotation
  policy                   = data.aws_iam_policy_document.kms_key.json
}

resource "aws_kms_alias" "manifest_signer" {
  name          = var.kms_alias_name             # alias/absa-exl-manifest-signer-v1
  target_key_id = aws_kms_key.manifest_signer.id
}

data "aws_iam_policy_document" "kms_key" {
  statement {
    sid       = "EnableRootAccount"
    actions   = ["kms:*"]
    resources = ["*"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
  }

  statement {
    sid       = "KeyAdminsManage"
    actions   = [
      "kms:Describe*", "kms:Get*", "kms:List*",
      "kms:Update*", "kms:TagResource", "kms:UntagResource",
      "kms:ScheduleKeyDeletion", "kms:CancelKeyDeletion",
    ]
    resources = ["*"]
    principals {
      type        = "AWS"
      identifiers = var.key_admin_principals
    }
  }

  statement {
    sid       = "SignerSigns"
    actions   = ["kms:Sign", "kms:GetPublicKey", "kms:DescribeKey"]
    resources = ["*"]
    principals {
      type        = "AWS"
      identifiers = [aws_iam_role.signer.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "kms:SigningAlgorithm"
      values   = ["RSASSA_PKCS1_V1_5_SHA_256"]
    }
  }

  dynamic "statement" {
    for_each = length(var.absa_verifier_principals) > 0 ? [1] : []
    content {
      sid       = "AbsaVerifiers"
      actions   = ["kms:Verify", "kms:GetPublicKey", "kms:DescribeKey"]
      resources = ["*"]
      principals {
        type        = "AWS"
        identifiers = var.absa_verifier_principals
      }
    }
  }
}
```

The verifier statement is wrapped in a `dynamic` block so the policy applies cleanly when the ABSA principals list is empty (the default before handoff).

### 6.2 GitHub Actions OIDC identity provider

```hcl
resource "aws_iam_openid_connect_provider" "github_actions" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]   # GitHub's documented root CA thumbprint
}
```

AWS no longer strictly requires thumbprint validation for GitHub's OIDC provider (it issues a known-good signing chain), but the field is required by the resource. Pinning to GitHub's published thumbprint is the conventional safety net.

### 6.3 Signer role — trust policy and inline policy

```hcl
data "aws_iam_policy_document" "signer_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github_actions.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = [for r in var.allowed_refs : "repo:${var.repo_full_name}:ref:${r}"]
    }
  }
}

resource "aws_iam_role" "signer" {
  name               = "pipeline-factory-signer"
  assume_role_policy = data.aws_iam_policy_document.signer_trust.json
}

data "aws_iam_policy_document" "signer_perms" {
  statement {
    sid       = "SignManifestsWithFixedAlgorithm"
    actions   = ["kms:Sign"]
    resources = [aws_kms_key.manifest_signer.arn]
    condition {
      test     = "StringEquals"
      variable = "kms:SigningAlgorithm"
      values   = ["RSASSA_PKCS1_V1_5_SHA_256"]
    }
  }
  statement {
    sid       = "GetPublicKeyForVerifyHelpers"
    actions   = ["kms:GetPublicKey", "kms:DescribeKey"]
    resources = [aws_kms_key.manifest_signer.arn]
  }
  statement {
    sid       = "WriteSignedManifests"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.signed_manifests.arn}/*"]
  }
  statement {
    sid       = "PublishPublicKeyArtifact"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.public_keys.arn}/manifest-signing/*"]
  }
}

resource "aws_iam_role_policy" "signer_perms" {
  name   = "signer-perms"
  role   = aws_iam_role.signer.id
  policy = data.aws_iam_policy_document.signer_perms.json
}
```

`var.allowed_refs` defaults to `["refs/heads/main"]`. The `kms:SigningAlgorithm` IAM condition is defence-in-depth — the Python signer always passes the correct algorithm, but IAM refuses any malformed call at the platform boundary.

### 6.4 Registrar role

```hcl
resource "aws_iam_role" "registrar" {
  name               = "pipeline-factory-registrar"
  assume_role_policy = data.aws_iam_policy_document.signer_trust.json   # same trust template
}

resource "aws_iam_role_policy_attachment" "registrar_writer" {
  role       = aws_iam_role.registrar.name
  policy_arn = var.writer_policy_arn                                    # from pipeline-registry module
}
```

Same trust template (the `signer_trust` document above), different inline policy (the writer policy ARN from Sprint 1's `pipeline-registry` module). The two roles can never be conflated: they have different names, different ARNs, and each CI job assumes exactly one.

### 6.5 S3 buckets

```hcl
resource "aws_s3_bucket" "signed_manifests" {
  bucket = var.signed_manifests_bucket_name      # exl-platform-signed-manifests
}
resource "aws_s3_bucket_versioning" "signed_manifests" {
  bucket = aws_s3_bucket.signed_manifests.id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_ownership_controls" "signed_manifests" {
  bucket = aws_s3_bucket.signed_manifests.id
  rule { object_ownership = "BucketOwnerEnforced" }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "signed_manifests" {
  bucket = aws_s3_bucket.signed_manifests.id
  rule { apply_server_side_encryption_by_default { sse_algorithm = "AES256" } }
}
resource "aws_s3_bucket_public_access_block" "signed_manifests" {
  bucket                  = aws_s3_bucket.signed_manifests.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket" "public_keys" {
  bucket = var.public_keys_bucket_name           # exl-platform-public-keys
}
resource "aws_s3_bucket_versioning" "public_keys" {
  bucket = aws_s3_bucket.public_keys.id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_ownership_controls" "public_keys" {
  bucket = aws_s3_bucket.public_keys.id
  rule { object_ownership = "BucketOwnerEnforced" }
}
resource "aws_s3_bucket_public_access_block" "public_keys" {
  bucket                  = aws_s3_bucket.public_keys.id
  block_public_acls       = true
  block_public_policy     = false                # required for the scoped read policy
  ignore_public_acls      = true
  restrict_public_buckets = false
}
# tfsec:ignore:aws-s3-no-public-buckets see docs/adr/0009-signing-foundation-topology.md
resource "aws_s3_bucket_policy" "public_keys_read" {
  bucket = aws_s3_bucket.public_keys.id
  policy = data.aws_iam_policy_document.public_keys_read.json
}
data "aws_iam_policy_document" "public_keys_read" {
  statement {
    sid       = "AllowPublicReadOfPublishedKeys"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.public_keys.arn}/manifest-signing/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
  }
}
```

The `tfsec:ignore` suppression on the public-keys bucket policy is intentional and documented in ADR-0009. Public read on `manifest-signing/*` is the audit story: anyone can fetch a public key and verify any historical signed envelope without AWS credentials.

### 6.6 Module variables and outputs

```hcl
# variables.tf
variable "env"                         { type = string }                              # "exl-prod"
variable "region"                      { type = string  default = "eu-west-1" }
variable "repo_full_name"              { type = string }                              # "MrVish/absa-exl-platform"
variable "allowed_refs"                { type = list(string)  default = ["refs/heads/main"] }
variable "key_admin_principals"        { type = list(string) }
variable "absa_verifier_principals"    { type = list(string)  default = [] }
variable "writer_policy_arn"           { type = string }                              # from pipeline-registry
variable "signed_manifests_bucket_name"{ type = string  default = "exl-platform-signed-manifests" }
variable "public_keys_bucket_name"     { type = string  default = "exl-platform-public-keys" }
variable "kms_alias_name"              { type = string  default = "alias/absa-exl-manifest-signer-v1" }

# outputs.tf
output "kms_key_arn"               { value = aws_kms_key.manifest_signer.arn }
output "kms_key_alias"             { value = aws_kms_alias.manifest_signer.name }
output "signer_role_arn"           { value = aws_iam_role.signer.arn }
output "registrar_role_arn"        { value = aws_iam_role.registrar.arn }
output "signed_manifests_bucket"   { value = aws_s3_bucket.signed_manifests.id }
output "public_keys_bucket"        { value = aws_s3_bucket.public_keys.id }
output "oidc_provider_arn"         { value = aws_iam_openid_connect_provider.github_actions.arn }
```

All variables have descriptions; all outputs have descriptions — `tflint` will check.

---

## 7 · `manifest-signer` Python package

### 7.1 `signer.py`

```python
def sign_envelope(
    unsigned_envelope: dict,
    *,
    key_arn: str,
    kms_client: "KMSClient",
    signer_principal: str,
    signed_at: str | None = None,
) -> dict:
    """Returns a NEW envelope dict with sentinel fields filled. Input untouched.

    Idempotency contract:
      - signature == "UNSIGNED"                              -> sign and fill
      - signature != "UNSIGNED", same key_arn + algorithm    -> return input unchanged (CI re-run safe)
      - signature != "UNSIGNED", DIFFERENT key or algorithm  -> raise KeyMismatchError

    The signature covers the canonicalised payload (envelope.payload), not the
    envelope itself. Signing the envelope would be circular: the signature field
    is part of the envelope.

    `signed_at` is preserved if passed (matches Sprint 2's idempotency pattern for
    `generated_at`). If None, set to datetime.now(UTC).isoformat().

    `signer_principal` is the assumed-role STS session ARN — formatted by the
    caller as `arn:aws:sts::<acct>:assumed-role/<role-name>/<session-name>`. The
    convention is documented in ADR-0009.
    """
```

Internal flow:

1. Read `payload = unsigned_envelope["payload"]`. Refuse if missing.
2. Check the idempotency conditions above; short-circuit or raise as documented.
3. `canonical = canonical_json(payload)` — bytes, via `platform_contracts.canonical.canonical_json`.
4. `digest = hashlib.sha256(canonical).digest()` — 32 bytes.
5. `resp = kms_client.sign(KeyId=key_arn, Message=digest, MessageType="DIGEST", SigningAlgorithm="RSASSA_PKCS1_V1_5_SHA_256")`.
6. `signature_b64 = base64.b64encode(resp["Signature"]).decode("ascii")`.
7. Build a new envelope dict (deep-copy input, then replace the four sentinel fields):
   - `signature = signature_b64`
   - `signing_key_arn = resp["KeyId"]` — the resolved key ARN, not the alias the caller may have passed.
   - `signing_algorithm = "RSASSA_PKCS1_V1_5_SHA_256"`
   - `signer_principal = signer_principal`
   - `signed_at = signed_at or datetime.now(UTC).isoformat(timespec="seconds")`
8. Return the new dict.

### 7.2 `verifier.py`

```python
def verify_online(envelope: dict, *, kms_client: "KMSClient") -> None:
    """Raises VerificationError on any failure. One KMS round-trip."""
    digest = _payload_digest(envelope)
    resp = kms_client.verify(
        KeyId=envelope["signing_key_arn"],
        Message=digest,
        MessageType="DIGEST",
        SigningAlgorithm=envelope["signing_algorithm"],
        Signature=base64.b64decode(envelope["signature"]),
    )
    if not resp["SignatureValid"]:
        raise VerificationError("kms:Verify returned SignatureValid=false")


def verify_offline(envelope: dict, *, public_key_pem: bytes) -> None:
    """Raises VerificationError on any failure. No AWS access required."""
    digest = _payload_digest(envelope)
    pub = serialization.load_pem_public_key(public_key_pem)
    try:
        pub.verify(
            signature=base64.b64decode(envelope["signature"]),
            data=digest,
            padding=padding.PKCS1v15(),
            algorithm=Prehashed(hashes.SHA256()),
        )
    except InvalidSignature as e:
        raise VerificationError(str(e)) from e


def _payload_digest(envelope: dict) -> bytes:
    """Canonicalise envelope.payload and SHA-256 it. Shared by both paths."""
    return hashlib.sha256(canonical_json(envelope["payload"])).digest()
```

Two paths, one canonical-digest pipeline. The `test_canonical_compat.py` test (Section 8) proves the two verifiers agree byte-for-byte on the same envelope on a battery of fixtures.

### 7.3 `publisher.py`

```python
def publish_public_key(
    *,
    key_arn: str,
    bucket: str,
    kms_client: "KMSClient",
    s3_client: "S3Client",
    version: str = "v1",
) -> str:
    """Fetches the public key via kms:GetPublicKey, PEM-encodes, uploads to
       s3://<bucket>/manifest-signing/<key_id>/<version>.pem. Returns the s3 URI.

       Idempotent — re-runs upload the same PEM content (the public key is
       immutable for a given KMS key). Unlike the signer's S3 uploads, the
       publisher does NOT use IfNoneMatch="*": key rotation is a valid
       use case where a new CMK version produces new bytes for the same
       `<key_id>/<version>.pem` path (when the operator chooses to reuse
       the version label), and 412-on-rotation would block that flow.
       Overwriting byte-identical PEM bytes is a no-op at the audit layer.
    """
```

### 7.4 `cli.py`

Click command group with five subcommands:

| Command | Behaviour |
|---|---|
| `manifest-signer sign --manifest <path> --key-arn <arn> [--upload-to s3://...] [--in-place] [--dry-run]` | Single-file signer. `--dry-run` skips KMS and prints what would be signed (canonical digest, planned envelope). `--upload-to` writes the signed envelope to S3 with `s3:PutObject IfNoneMatch="*"`. `--in-place` overwrites the local file (developer flow). |
| `manifest-signer sign-all --root <dir> --key-arn <arn> --upload-to-bucket <bucket> [--continue-on-error]` | CI workhorse. Globs `<root>/*/*/manifest.json`, filters where `signature == "UNSIGNED"`, signs each, uploads to `s3://<bucket>/<name>/<version>/manifest.json` deriving `<name>/<version>` from the manifest's **payload** (not the file path — robust to layout drift). Treats S3 `412 PreconditionFailed` as success. Stops at first error unless `--continue-on-error`. |
| `manifest-signer verify-online --manifest <path>` | Picks up `signing_key_arn` from the envelope, calls `verify_online`. Exit 0 / 1. |
| `manifest-signer verify-offline --manifest <path> --public-key <path>` | Local-only verification. Exit 0 / 1. |
| `manifest-signer publish-key --key-arn <arn> --bucket <name> [--version v1]` | One-shot for first deploy + on each key rotation. |

### 7.5 Errors

```python
class SignerError(Exception):                 ...    # base
class KeyMismatchError(SignerError):          ...    # re-sign with different key
class VerificationError(Exception):           ...    # base for verifier failures
```

### 7.6 Dependencies

- `boto3` — KMS + S3 calls.
- `cryptography` — offline verifier path (`load_pem_public_key`, `padding.PKCS1v15`, `Prehashed(hashes.SHA256())`).
- `click` — CLI.
- `platform-contracts` (workspace) — `canonical_json`.
- Dev/test: `moto[kms,s3] >= 5.0`, `pytest`, `pytest-httpx` (already in workspace dev deps).

---

## 8 · Testing strategy

### 8.1 Unit tests

| File | Asserts |
|---|---|
| `tests/test_signer.py` | UNSIGNED → fills sentinels; resolved `signing_key_arn` lands in envelope (not the alias passed in). Same-key re-sign returns input unchanged. Different-key re-sign raises `KeyMismatchError`. **Determinism** — signing the same envelope twice yields byte-identical signature (the `RSASSA_PKCS1_V1_5_SHA_256` property). `signed_at` passed in is preserved; `signed_at` omitted is a valid ISO-8601 string. |
| `tests/test_verifier_online.py` | Sign + `verify_online` round trip passes. Tampered payload / signature / `signing_key_arn` → `VerificationError`. |
| `tests/test_verifier_offline.py` | Sign + `verify_offline` round trip using moto's actually-generated public key (PEM). Same tamper checks. Public key from a different keypair → `VerificationError`. |
| `tests/test_publisher.py` | `publish_public_key` writes PEM to `s3://<bucket>/manifest-signing/<key_id>/<version>.pem`. PEM round-trips through `serialization.load_pem_public_key`. Re-run is idempotent. |
| `tests/test_cli.py` | All five subcommands. `--dry-run` short-circuits KMS. `--in-place` updates file. `sign-all` discovers UNSIGNED only, derives `name`/`version` from payload, treats 412 as success. Exit codes correct on success and failure. |
| `tests/test_canonical_compat.py` | After moving `canonical_json` to `platform-contracts`, output is byte-identical to Sprint 2's encoder on a battery of fixture payloads. **Catches drift in the refactor before it lands.** |

### 8.2 End-to-end test

`tests/test_e2e.py` exercises the full CI happy path inside one test:

1. Build a fixture `pipelines/` tree containing two manifests — one already signed (with sentinel placeholders replaced via the same fixture KMS), one UNSIGNED.
2. Spin up moto KMS + moto S3.
3. Call `sign-all` via `Click.testing.CliRunner`.
4. Assert the UNSIGNED manifest landed in the expected S3 location with `signature != "UNSIGNED"`.
5. Assert the already-signed manifest was a no-op (S3 PUT returned 412, treated as success; no envelope mutation).
6. Re-run the same `sign-all` invocation; assert both branches are idempotent (no errors, no new S3 versions).
7. Run `verify_online` against the signed envelope in-memory; assert pass.
8. Call `kms:GetPublicKey`, PEM-encode, run `verify_offline`; assert pass.

This is the test that proves "the CI flow works without AWS."

### 8.3 Terraform validation

Extends the existing `terraform-validate.yml` matrix:

- `terraform validate` on `terraform/modules/signing-foundation`.
- `terraform validate` on `terraform/envs/exl-prod/signing`.
- `tflint` on both — all variables and outputs documented, no unused vars.
- `tfsec` on both — one expected suppression (`aws-s3-no-public-buckets`) on the public-keys bucket policy, with a `tfsec:ignore` comment referencing ADR-0009 for review-time defensibility.

### 8.4 Workflow validation

`actionlint` runs (via the existing pre-commit hook from Sprint 2) on the modified `pipeline-factory.yml` and the new `publish-signing-key.yml`. No shell injection (parameters passed via env-var or `${{ vars }}` blocks, never string-concatenated into the script).

### 8.5 Out of test scope

- Code Intake validators end-to-end → Sprint 4.
- Actual `kms:Verify` round-trip from an ABSA principal → no ABSA runner exists yet; deferred to Sprint 4 or Phase 3.
- Real (non-moto) `terraform apply` → Phase 4, once real accounts exist.

---

## 9 · CI integration

### 9.1 Modified `.github/workflows/pipeline-factory.yml`

Workflow-level permissions consolidated (the existing 2.2 register job had its own per-job declaration; we move it to the workflow level for one auditable surface).

```yaml
name: pipeline-factory
on:
  pull_request:
    paths: [pipeline-factory/**, platform-contracts/**, manifest-signer/**,
            pipelines/**, .github/workflows/pipeline-factory.yml]
  push:
    branches: [main]
    paths:   [pipeline-factory/**, platform-contracts/**, manifest-signer/**,
              pipelines/**, .github/workflows/pipeline-factory.yml]

permissions:
  contents: read
  id-token: write          # OIDC; both sign and register jobs need this

jobs:
  drift-gate: { ... }      # unchanged from Sprint 2

  sign:
    needs: drift-gate
    if: github.event_name == 'push'
        && github.ref == 'refs/heads/main'
        && vars.AWS_SIGNER_ROLE_ARN != ''
    runs-on: ubuntu-latest
    concurrency:
      group: pipeline-factory-sign
      cancel-in-progress: false
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - uses: astral-sh/setup-uv@v3
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ vars.AWS_SIGNER_ROLE_ARN }}
          aws-region:     ${{ vars.AWS_REGION }}
      - name: Sign all unsigned manifests
        run: |
          set -euo pipefail
          uv run --package manifest-signer manifest-signer sign-all \
            --root             pipelines \
            --key-arn          "${{ vars.AWS_KMS_SIGNING_KEY_ARN }}" \
            --upload-to-bucket "${{ vars.AWS_SIGNED_MANIFESTS_BUCKET }}"

  register:
    needs: sign
    if: github.event_name == 'push'
        && github.ref == 'refs/heads/main'
        && vars.AWS_REGISTRAR_ROLE_ARN != ''
    # existing Sprint 2 register job body
    # only behavioural changes:
    #   - rename AWS_ROLE_ARN -> AWS_REGISTRAR_ROLE_ARN
    #   - needs: sign  (was: needs: drift-gate)
```

Sequencing properties:
- `drift-gate` → `sign` → `register`. Sign runs only on push to `main` (PR runs stop at drift-gate).
- A skipped `sign` job (variables unset in dev) skips `register` too via GitHub's default downstream-skip behaviour. Neither side accidentally activates without the other.
- The concurrency group serialises back-to-back merges on `main` so two sign jobs never race on `s3:PutObject IfNoneMatch="*"` on the same key. The signer's 412-as-success behaviour is defence-in-depth against the edge case if the group is ever bypassed.

### 9.2 New `.github/workflows/publish-signing-key.yml`

```yaml
name: publish-signing-key
on:
  workflow_dispatch:
    inputs:
      version:
        description: 'Version label for the published public key'
        required: true
        default:  'v1'

permissions:
  contents: read
  id-token: write

jobs:
  publish:
    if: vars.AWS_SIGNER_ROLE_ARN != ''
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - uses: astral-sh/setup-uv@v3
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ vars.AWS_SIGNER_ROLE_ARN }}
          aws-region:     ${{ vars.AWS_REGION }}
      - name: Publish public key
        run: |
          set -euo pipefail
          uv run --package manifest-signer manifest-signer publish-key \
            --key-arn ${{ vars.AWS_KMS_SIGNING_KEY_ARN }} \
            --bucket  ${{ vars.AWS_PUBLIC_KEYS_BUCKET }} \
            --version ${{ inputs.version }}
```

Manual `workflow_dispatch` — run once after first `terraform apply`, then again on each key rotation.

### 9.3 Repo variables (all blank-OK in dev)

| Variable | Purpose | Example |
|---|---|---|
| `AWS_REGION` | All AWS calls in both jobs | `eu-west-1` |
| `AWS_SIGNER_ROLE_ARN` | `sign` job assumes this | `arn:aws:iam::<exl-prod>:role/pipeline-factory-signer` |
| `AWS_REGISTRAR_ROLE_ARN` | `register` job assumes this (renamed from Sprint 2's `AWS_ROLE_ARN`) | `arn:aws:iam::<exl-prod>:role/pipeline-factory-registrar` |
| `AWS_KMS_SIGNING_KEY_ARN` | Resolved CMK ARN | `arn:aws:kms:eu-west-1:...:key/<uuid>` |
| `AWS_SIGNED_MANIFESTS_BUCKET` | Sign-step destination bucket | `exl-platform-signed-manifests` |
| `AWS_PUBLIC_KEYS_BUCKET` | Publisher destination bucket | `exl-platform-public-keys` |
| `REGISTRY_API_URL` | Already set by Sprint 2 | `https://api.../v1/pipelines` |

All variables are GitHub Actions repo **variables** (not secrets) — IAM role ARNs and bucket names are not sensitive and `vars.` is GitHub's recommended pattern for OIDC role ARNs.

---

## 10 · ADRs

### 10.1 ADR-0009 — Signing Foundation Topology (new)

Outline:

- **Context.** ADR-0003 chose KMS asymmetric CMK signing but did not pin the bucket layout, the IAM trust scopes, the signing algorithm, or the idempotency posture. This sprint pins them.
- **Decisions.** RSA-3072 + `RSASSA_PKCS1_V1_5_SHA_256` (deterministic — the property that makes content-addressable S3 storage + `IfNoneMatch:*` idempotency work). CMK in `exl-prod` only; no multi-region replica. Main-only OIDC trust on both roles. Two scoped IAM roles (signer, registrar), never combined. Two buckets with the exact layouts in Section 6.5. Signer treats S3 `412 PreconditionFailed` as success.
- **Consequences (pros).** Clean separation of signing and registration. Offline-verifiable by anyone holding the public key. CI-only signer with no human path. Deterministic algorithm = bit-for-bit idempotent re-signs.
- **Consequences (cons accepted).** Asymmetric KMS keys cannot auto-rotate — rotation is a deliberate `v2`-alongside-`v1` operation; the runbook is a Phase 3 concern. The public-keys bucket carries `Principal: "*"` on `s3:GetObject` for `manifest-signing/*` only — `tfsec:ignore` annotation references this ADR for audit-time defensibility.
- **Alternatives considered.**
  - *Symmetric HMAC* — rejected. Verification by ABSA / external auditors would require shared secret distribution, defeating the audit story.
  - *ECC-NIST-P384* — deferred. The deterministic property of `RSASSA_PKCS1_V1_5_SHA_256` matters more than the smaller key size; revisit if RSA performance ever becomes a bottleneck (extremely unlikely at our volume — one sign per merge).
  - *Storing signed manifest inline in the registry record* — deferred to Sprint 4 if Code Intake's audit story benefits from the cross-link. Adds schema-change surface for marginal benefit today.
- **Rotation strategy (informational).** Produce `absa-exl-manifest-signer-v2` via Terraform alongside `v1`. Update the signer role's resource list to include both. Switch the application config to sign with `v2`. Publish `v2`'s public key to `manifest-signing/<v2-key-id>/v1.pem`. Verify any historical manifest by routing on its `signing_key_arn`. Retire `v1` only after all referenced manifests have expired (Phase 3 ops runbook).

### 10.2 ADR-0003 minor edit

Add a *Storage layout* paragraph to ADR-0003 (Controlled Handoff):

> Signed manifest envelopes are uploaded to `s3://exl-platform-signed-manifests/<name>/<version>/manifest.json` by the CI signer immediately after generation. Public keys for offline verification are published to `s3://exl-platform-public-keys/manifest-signing/<key_id>/<version>.pem`. See ADR-0009 for the IAM, KMS, and OIDC topology that supports these paths.

No semantic change to the original decision.

---

## 11 · Open questions and deferred items

Carried into Sprint 4 or later; not blockers for this sprint:

| Item | Why deferred | Owner |
|---|---|---|
| AWS region pinning (assume `eu-west-1` for POPIA proximity to ABSA) | ABSA confirms at handoff; until then `var.region` plumbs through everything with a default | ABSA ops |
| ABSA verifier IAM principals | No ABSA accounts yet; `var.absa_verifier_principals` defaults `[]` and the `AbsaVerifiers` statement is wrapped in a `dynamic` block | ABSA ops |
| Key rotation operational runbook (`v2`-alongside-`v1` mechanics) | Not exercised until first real rotation; ADR-0009 documents the approach | Phase 3 ops |
| `signed_manifest_ref` field on the registry record | Decide in Sprint 4 if Code Intake's audit story benefits from the cross-link | Sprint 4 |
| `signer_principal` provenance — STS session ARN vs. GitHub identity | Sprint 3 convention: STS session ARN. Switch to GH identity if auditors ask. | Future ADR |
| Real `terraform apply` (not `validate`-only) | No real accounts; Phase 4 readiness | ABSA |
| Cross-account verifier exercise from `absa-prod` | No ABSA-side runner exists yet | Sprint 4 or Phase 3 |

---

## 12 · Known limits of Sprint 3 as a delivery

Until ABSA hands over real AWS account IDs:

- All runtime behaviour exercised via `moto v5` only — no real `kms:Sign` calls land against a real CMK.
- All Terraform stays at `validate` / `tflint` / `tfsec` level; no `apply`.
- The `publish-signing-key` workflow exists but its `workflow_dispatch` execution requires real AWS — exercised only against moto in unit tests.

This is the same posture Sprint 1 and Sprint 2 ship in. The first real `kms:Sign` invocation happens in Phase 3 against ABSA's real CMK; the foundation we ship here is the code path that flips on at that moment with no application changes.

---

## 13 · Acceptance criteria

This sprint is done when:

1. All `manifest-signer` unit tests + the end-to-end test pass — `uv run pytest` is green on the merged result.
2. `terraform validate` + `tflint` + `tfsec` pass on the new module and the `exl-prod/signing` stack. The one `tfsec` suppression is annotated with a comment referencing ADR-0009.
3. `actionlint` passes on the modified `pipeline-factory.yml` and the new `publish-signing-key.yml`.
4. The `canonical_json` move lands without breaking Sprint 2: `test_canonical_compat.py` proves byte-identical encoding; Sprint 2's existing tests still pass after the import updates.
5. `pipeline-registry`'s existing `writer_policy_arn` output is consumed by the `signing-foundation` module via `terraform_remote_state` (verified by `terraform validate` on the `exl-prod/signing` stack).
6. ADR-0009 is committed; ADR-0003 has the storage-layout edit.
7. READMEs exist for `manifest-signer/` (usage examples) and `terraform/modules/signing-foundation/` (input/output reference).
8. The final review pass (subagent-driven code reviewer at the end of execution) finds no blocking issues.
9. A PR is opened against `main`; CI passes (drift-gate green, sign + register skipped because dev has no AWS variables set, terraform-validate green, python-validate green).

---

## 14 · Implementation handoff

After this spec is reviewed and approved, the writing-plans skill produces a tasked implementation plan covering:

- The `canonical_json` refactor — done first so subsequent tasks import from the new home.
- The `manifest-signer` Python package, built bottom-up: errors → canonical compat test → signer → online verifier → offline verifier → publisher → CLI commands → end-to-end test.
- The Terraform module: KMS → IAM (OIDC + signer + registrar) → S3 buckets → variables/outputs.
- The per-env `exl-prod/signing` stack.
- The CI workflow updates: `pipeline-factory.yml` (sign job) → `publish-signing-key.yml` (new).
- Documentation: ADR-0009 → ADR-0003 minor edit → READMEs → top-level CHANGELOG entry.
- Final verification pass.

Execution then proceeds via the subagent-driven-development pattern established in Sprints 1 and 2: a fresh implementer subagent per task, followed by a spec-compliance reviewer and a code-quality reviewer, with the controller dispatching one task at a time.
