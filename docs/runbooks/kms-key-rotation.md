# KMS Asymmetric CMK Rotation Runbook

> **Audience:** EXL platform ops (this side). For ABSA-side actions, see
> the cross-account verifier handoff doc (TBD when ABSA accounts onboard).

This runbook covers rotation of the manifest-signing asymmetric CMK (the
RSA-3072 SIGN_VERIFY key used by `manifest-signer sign`). The
verification side must continue to work for ALL historical manifests
even after rotation — the runbook is structured to preserve that.

## When to rotate

| Trigger | Cadence |
|---|---|
| Suspected compromise | Immediately. Revoke + rotate in one transaction. |
| ABSA contract milestone (handover, audit) | As contracted. |
| Annual default | Yearly, on the anniversary of the previous rotation. |
| KMS automatic rotation | **N/A.** AWS KMS does not auto-rotate asymmetric keys. Manual procedure only. |

## Pre-rotation checklist

- [ ] Announce a 24h freeze window for `manifest-signer sign` operations.
- [ ] Confirm no in-flight CI runs are mid-sign (`gh run list --workflow pipeline-factory --status in_progress`).
- [ ] Snapshot the current public-key bucket (`aws s3 sync s3://<bucket>/manifest-signing/ ./pem-archive/`).
- [ ] Record the existing key alias + key ARN in the rotation ticket.
- [ ] Identify the new version label (default: increment `vN` → `vN+1`).

## Rotation steps

### 1. Create the new asymmetric CMK

```bash
# In the exl-prod account, eu-west-1
aws kms create-key \
  --description "ABSA EXL manifest signing CMK (rotation 2026-MM-DD)" \
  --key-usage SIGN_VERIFY \
  --key-spec RSA_3072 \
  --policy file://signing-foundation-key-policy.json
```

Capture the new key ARN — record in the rotation ticket.

### 2. Publish the new public key

```bash
uv run manifest-signer publish-key \
  --key-arn <new-key-arn> \
  --bucket <public-keys-bucket> \
  --version v2
```

This uploads the PEM to `s3://<public-keys-bucket>/manifest-signing/<new-key-id>/v2.pem`.
The previous key's PEM at `manifest-signing/<old-key-id>/v1.pem` stays in
place — DO NOT delete it. Historical manifests reference the old key
via `envelope.signing_key_arn`; their verification still requires the
old PEM.

### 3. Update the signing-foundation Terraform module to point at the new key

In `terraform/envs/<env>/signing/main.tf`, change the key alias to
target the new CMK:

```hcl
module "signing" {
  source = "../../../modules/signing-foundation"

  env                      = "prod"
  kms_alias_name           = "alias/absa-exl-manifest-signer-prod"
  kms_key_id_override      = "<new-key-id>"   # NEW
  # ... other inputs unchanged ...
}
```

Apply:

```bash
terraform -chdir=terraform/envs/prod/signing apply
```

The alias now resolves to the new key. Future `manifest-signer sign`
calls automatically use the new key (they look up the alias).

### 4. Verify both PEMs accessible

```bash
# Old PEM (must remain for historical manifests)
aws s3 head-object --bucket <public-keys-bucket> \
  --key manifest-signing/<old-key-id>/v1.pem

# New PEM
aws s3 head-object --bucket <public-keys-bucket> \
  --key manifest-signing/<new-key-id>/v2.pem
```

### 5. Smoke-test new key end-to-end

```bash
# Sign a fresh test manifest with the new key
uv run manifest-signer sign \
  --manifest /tmp/test-manifest.json \
  --key-arn alias/absa-exl-manifest-signer-prod \
  --signer-principal "arn:aws:iam::<exl-account>:role/pipeline-factory-signer"

# Verify with the new PEM
uv run manifest-signer verify-from-bucket \
  --bucket <signed-manifests-bucket> \
  --key test/<test-name>/manifest.json \
  --public-key-bucket <public-keys-bucket>
```

Both must succeed.

### 6. Smoke-test old-key verification still works

Pick a historical manifest (e.g., from credit-risk-pd@1.0.0) and verify
it with the OLD PEM:

```bash
uv run manifest-signer verify-from-bucket \
  --bucket <signed-manifests-bucket> \
  --key pipelines/credit-risk-pd/1.0.0/manifest.json \
  --public-key-bucket <public-keys-bucket>
```

The `verify-from-bucket` CLI auto-derives the PEM path from
`envelope.signing_key_arn`, which still references the OLD key. The
OLD PEM at `manifest-signing/<old-key-id>/v1.pem` must answer the
GetObject — otherwise historical verification breaks.

If verification fails, ROLLBACK (re-point the alias to the old key,
investigate why the historical PEM was lost).

## Post-rotation

- [ ] Update [`docs/adr/0009-signing-foundation-kms-asymmetric.md`](../adr/0009-signing-foundation-kms-asymmetric.md)
      with the rotation date + new key ID.
- [ ] Tag the rotation ticket as completed.
- [ ] Announce end-of-freeze to consumers.
- [ ] Schedule the next annual rotation.

## What we explicitly do NOT do

- **Delete the old CMK.** AWS KMS has a mandatory 7-30 day waiting period
  before scheduled deletion. We don't delete asymmetric keys at all —
  verification of historical signed artifacts must remain possible
  indefinitely (audit requirements).
- **Delete old PEMs from the public-keys bucket.** Same reason.
- **Re-sign historical manifests with the new key.** Signature on a
  manifest must remain stable across the manifest's lifetime; re-signing
  would invalidate downstream registry records that captured the old
  digest. If a manifest needs to be re-signed (e.g., to attest a security
  patch), bump the package version and produce a new artifact instead.

## See also

- [ADR-0009](../adr/0009-signing-foundation-kms-asymmetric.md) — signing foundation
- [`manifest-signer/README.md`](../../manifest-signer/README.md) — CLI reference
- AWS docs: [Asymmetric KMS keys](https://docs.aws.amazon.com/kms/latest/developerguide/symmetric-asymmetric.html)
