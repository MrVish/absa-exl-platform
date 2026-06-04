from __future__ import annotations

import base64
import copy

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from manifest_signer.errors import VerificationError
from manifest_signer.signer import sign_envelope
from manifest_signer.verifier import verify_offline


@pytest.fixture
def public_key_pem(kms_client, signing_key) -> bytes:
    """Fetch the moto-generated public key and PEM-encode it."""
    resp = kms_client.get_public_key(KeyId=signing_key["KeyId"])
    der_bytes = resp["PublicKey"]
    pub = serialization.load_der_public_key(der_bytes)
    return pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def test_sign_then_verify_offline_passes(
    unsigned_envelope, kms_client, signing_key, signer_principal, public_key_pem
):
    signed = sign_envelope(
        unsigned_envelope,
        key_arn=signing_key["Arn"],
        kms_client=kms_client,
        signer_principal=signer_principal,
    )
    verify_offline(signed, public_key_pem=public_key_pem)  # must not raise


def test_tampered_payload_fails_offline_verify(
    unsigned_envelope, kms_client, signing_key, signer_principal, public_key_pem
):
    signed = sign_envelope(
        unsigned_envelope,
        key_arn=signing_key["Arn"],
        kms_client=kms_client,
        signer_principal=signer_principal,
    )
    tampered = copy.deepcopy(signed)
    tampered["payload"]["model_name"] = "different-model"
    with pytest.raises(VerificationError):
        verify_offline(tampered, public_key_pem=public_key_pem)


def test_tampered_signature_fails_offline_verify(
    unsigned_envelope, kms_client, signing_key, signer_principal, public_key_pem
):
    signed = sign_envelope(
        unsigned_envelope,
        key_arn=signing_key["Arn"],
        kms_client=kms_client,
        signer_principal=signer_principal,
    )
    tampered = copy.deepcopy(signed)
    sig_bytes = bytearray(base64.b64decode(tampered["signature"]))
    sig_bytes[0] ^= 0xFF
    tampered["signature"] = base64.b64encode(bytes(sig_bytes)).decode("ascii")
    with pytest.raises(VerificationError):
        verify_offline(tampered, public_key_pem=public_key_pem)


def test_mismatched_public_key_fails_offline_verify(
    unsigned_envelope, kms_client, signing_key, signer_principal
):
    signed = sign_envelope(
        unsigned_envelope,
        key_arn=signing_key["Arn"],
        kms_client=kms_client,
        signer_principal=signer_principal,
    )
    # Generate an unrelated public key
    other_priv = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    other_pub_pem = other_priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    with pytest.raises(VerificationError):
        verify_offline(signed, public_key_pem=other_pub_pem)
