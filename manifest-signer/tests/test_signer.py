from __future__ import annotations

import base64

import pytest
from manifest_signer.errors import KeyMismatchError
from manifest_signer.signer import sign_envelope


def test_sign_unsigned_fills_all_four_sentinel_fields(
    unsigned_envelope, kms_client, signing_key, signer_principal
):
    out = sign_envelope(
        unsigned_envelope,
        key_arn=signing_key["Arn"],
        kms_client=kms_client,
        signer_principal=signer_principal,
    )
    assert out["signature"] != "UNSIGNED"
    assert out["signing_key_arn"] == signing_key["Arn"]
    assert out["signing_algorithm"] == "RSASSA_PKCS1_V1_5_SHA_256"
    assert out["signer_principal"] == signer_principal


def test_sign_does_not_mutate_input(unsigned_envelope, kms_client, signing_key, signer_principal):
    snapshot = dict(unsigned_envelope)
    sign_envelope(
        unsigned_envelope,
        key_arn=signing_key["Arn"],
        kms_client=kms_client,
        signer_principal=signer_principal,
    )
    assert unsigned_envelope == snapshot


def test_signature_is_base64_decodable(
    unsigned_envelope, kms_client, signing_key, signer_principal
):
    out = sign_envelope(
        unsigned_envelope,
        key_arn=signing_key["Arn"],
        kms_client=kms_client,
        signer_principal=signer_principal,
    )
    sig = base64.b64decode(out["signature"])
    # RSA-3072 produces 384-byte signatures
    assert len(sig) == 384


def test_signed_at_is_preserved_when_provided(
    unsigned_envelope, kms_client, signing_key, signer_principal
):
    out = sign_envelope(
        unsigned_envelope,
        key_arn=signing_key["Arn"],
        kms_client=kms_client,
        signer_principal=signer_principal,
        signed_at="2026-06-01T12:00:00+00:00",
    )
    assert out["signed_at"] == "2026-06-01T12:00:00+00:00"


def test_signed_at_defaults_to_iso8601_utc(
    unsigned_envelope, kms_client, signing_key, signer_principal
):
    from datetime import datetime

    out = sign_envelope(
        unsigned_envelope,
        key_arn=signing_key["Arn"],
        kms_client=kms_client,
        signer_principal=signer_principal,
    )
    # Must parse as ISO-8601 UTC
    parsed = datetime.fromisoformat(out["signed_at"])
    assert parsed.utcoffset() is not None


def test_signing_is_deterministic(unsigned_envelope, kms_client, signing_key, signer_principal):
    """RSASSA_PKCS1_V1_5_SHA_256 is deterministic — same digest -> same signature.
    This is the property the CI idempotency story leans on."""
    a = sign_envelope(
        unsigned_envelope,
        key_arn=signing_key["Arn"],
        kms_client=kms_client,
        signer_principal=signer_principal,
        signed_at="2026-06-01T12:00:00+00:00",
    )
    b = sign_envelope(
        unsigned_envelope,
        key_arn=signing_key["Arn"],
        kms_client=kms_client,
        signer_principal=signer_principal,
        signed_at="2026-06-01T12:00:00+00:00",
    )
    assert a == b


def test_resign_with_same_key_is_noop(unsigned_envelope, kms_client, signing_key, signer_principal):
    signed = sign_envelope(
        unsigned_envelope,
        key_arn=signing_key["Arn"],
        kms_client=kms_client,
        signer_principal=signer_principal,
        signed_at="2026-06-01T12:00:00+00:00",
    )
    out = sign_envelope(
        signed,
        key_arn=signing_key["Arn"],
        kms_client=kms_client,
        signer_principal=signer_principal,
        signed_at="2026-06-01T12:00:00+00:00",
    )
    # `is` not `==` — proves the short-circuit returned the input object
    # itself rather than re-signing to produce an equal-but-distinct dict.
    # The short-circuit is what protects against KMS quota burn + audit-log
    # noise on CI re-runs; an `==` assertion would silently pass either way.
    assert out is signed


def test_resign_with_different_key_raises_key_mismatch(
    unsigned_envelope, kms_client, signing_key, signer_principal
):
    signed = sign_envelope(
        unsigned_envelope,
        key_arn=signing_key["Arn"],
        kms_client=kms_client,
        signer_principal=signer_principal,
    )
    other_key = kms_client.create_key(KeyUsage="SIGN_VERIFY", KeySpec="RSA_3072")["KeyMetadata"]
    with pytest.raises(KeyMismatchError):
        sign_envelope(
            signed,
            key_arn=other_key["Arn"],
            kms_client=kms_client,
            signer_principal=signer_principal,
        )


def test_signing_key_arn_is_resolved_arn_not_alias(
    unsigned_envelope, kms_client, signing_key, signer_principal
):
    """If caller passes the alias, the envelope must end up with the resolved
    key ARN — the immutable identifier. This is the audit-trail requirement."""
    kms_client.create_alias(AliasName="alias/test-signing-key", TargetKeyId=signing_key["KeyId"])
    out = sign_envelope(
        unsigned_envelope,
        key_arn="alias/test-signing-key",
        kms_client=kms_client,
        signer_principal=signer_principal,
    )
    assert out["signing_key_arn"] == signing_key["Arn"]
    assert "alias" not in out["signing_key_arn"]
