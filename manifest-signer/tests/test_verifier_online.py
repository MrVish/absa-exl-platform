from __future__ import annotations

import base64
import copy

import pytest
from manifest_signer.errors import VerificationError
from manifest_signer.signer import sign_envelope
from manifest_signer.verifier import verify_online


def test_sign_then_verify_online_passes(
    unsigned_envelope, kms_client, signing_key, signer_principal
):
    signed = sign_envelope(
        unsigned_envelope,
        key_arn=signing_key["Arn"],
        kms_client=kms_client,
        signer_principal=signer_principal,
    )
    verify_online(signed, kms_client=kms_client)  # must not raise


def test_tampered_payload_fails_online_verify(
    unsigned_envelope, kms_client, signing_key, signer_principal
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
        verify_online(tampered, kms_client=kms_client)


def test_tampered_signature_fails_online_verify(
    unsigned_envelope, kms_client, signing_key, signer_principal
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
        verify_online(tampered, kms_client=kms_client)
