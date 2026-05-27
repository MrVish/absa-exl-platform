import pytest
from jsonschema import ValidationError
from platform_contracts.loader import validate

VALID = {
    "digest": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
    "digest_algorithm": "SHA-256",
    "signature": "QUJDRA==",
    "signing_key_arn": "arn:aws:kms:eu-west-1:111122223333:key/abc",
    "signing_algorithm": "RSASSA_PKCS1_V1_5_SHA_256",
    "subject_type": "pipeline",
    "subject_ref": "s3://exl-platform/pipelines/credit-risk-pd/1.0.0/manifest.json",
    "signed_at": "2026-05-26T06:00:00+00:00",
    "signer_principal": "arn:aws:iam::111122223333:role/ci-signer",
    "payload": {"any": "shape"},
}


def test_valid_envelope_passes() -> None:
    validate("manifest-envelope", VALID)


def test_bad_subject_type_fails() -> None:
    with pytest.raises(ValidationError):
        validate("manifest-envelope", {**VALID, "subject_type": "model"})


def test_missing_signature_fails() -> None:
    bad = {k: v for k, v in VALID.items() if k != "signature"}
    with pytest.raises(ValidationError):
        validate("manifest-envelope", bad)
