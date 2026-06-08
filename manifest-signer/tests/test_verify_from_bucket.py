"""Tests for `manifest-signer verify-from-bucket` (Sprint 3 T1)."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner
from manifest_signer.cli import main
from manifest_signer.publisher import publish_public_key
from manifest_signer.signer import sign_envelope


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def signed_envelope_in_s3(
    unsigned_envelope, signing_key, kms_client, s3_client
) -> dict:
    """Sign a sample envelope, upload manifest + PEM to moto S3.

    Returns a dict with 'manifest_bucket', 'manifest_key', 'pem_bucket',
    'pem_key' so the test can pass them to the CLI.
    """
    manifest_bucket = "test-manifests"
    pem_bucket = "test-public-keys"
    s3_client.create_bucket(
        Bucket=manifest_bucket,
        CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
    )
    s3_client.create_bucket(
        Bucket=pem_bucket,
        CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
    )

    signed = sign_envelope(
        unsigned_envelope,
        key_arn=signing_key["Arn"],
        kms_client=kms_client,
        signer_principal="test-principal",
    )
    manifest_key = "pipelines/credit-risk-pd/1.0.0/manifest.json"
    s3_client.put_object(
        Bucket=manifest_bucket,
        Key=manifest_key,
        Body=json.dumps(signed).encode("utf-8"),
        ContentType="application/json",
    )

    publish_public_key(
        key_arn=signing_key["Arn"],
        bucket=pem_bucket,
        kms_client=kms_client,
        s3_client=s3_client,
        version="v1",
    )
    # publish_public_key writes to manifest-signing/<key_id>/<version>.pem
    key_id = signing_key["Arn"].rsplit("/", 1)[-1]
    pem_key = f"manifest-signing/{key_id}/v1.pem"

    return {
        "manifest_bucket": manifest_bucket,
        "manifest_key": manifest_key,
        "pem_bucket": pem_bucket,
        "pem_key": pem_key,
        "signed_envelope": signed,
    }


def test_verify_from_bucket_succeeds_on_valid(
    runner, signed_envelope_in_s3, signing_key, kms_client, s3_client
):
    """Happy path: fetch envelope + PEM from S3, verify, exit 0."""
    result = runner.invoke(
        main,
        [
            "verify-from-bucket",
            "--bucket", signed_envelope_in_s3["manifest_bucket"],
            "--key", signed_envelope_in_s3["manifest_key"],
            "--public-key-bucket", signed_envelope_in_s3["pem_bucket"],
        ],
    )
    assert result.exit_code == 0, result.output
    assert "OK" in result.output


def test_verify_from_bucket_fails_on_tampered_envelope(
    runner, signed_envelope_in_s3, signing_key, kms_client, s3_client
):
    """Tamper with the envelope payload after signing → verify_offline fails → exit 1."""
    bad = dict(signed_envelope_in_s3["signed_envelope"])
    bad["payload"] = {**bad["payload"], "model_name": "tampered-name"}
    s3_client.put_object(
        Bucket=signed_envelope_in_s3["manifest_bucket"],
        Key=signed_envelope_in_s3["manifest_key"],
        Body=json.dumps(bad).encode("utf-8"),
    )
    result = runner.invoke(
        main,
        [
            "verify-from-bucket",
            "--bucket", signed_envelope_in_s3["manifest_bucket"],
            "--key", signed_envelope_in_s3["manifest_key"],
            "--public-key-bucket", signed_envelope_in_s3["pem_bucket"],
        ],
    )
    assert result.exit_code == 1, result.output
    assert "FAIL" in result.output


def test_verify_from_bucket_fails_when_pem_missing(
    runner, signed_envelope_in_s3, kms_client, s3_client
):
    """No PEM at the derived path → exit 1 with clear error."""
    result = runner.invoke(
        main,
        [
            "verify-from-bucket",
            "--bucket", signed_envelope_in_s3["manifest_bucket"],
            "--key", signed_envelope_in_s3["manifest_key"],
            "--public-key-bucket", "nonexistent-bucket",
        ],
    )
    assert result.exit_code == 1, result.output
    assert "FAIL" in result.output
    assert "PEM" in result.output or "pem" in result.output


def test_verify_from_bucket_accepts_explicit_pem_uri(
    runner, signed_envelope_in_s3, kms_client, s3_client
):
    """--public-key-uri override bypasses auto-derivation."""
    pem_uri = (
        f"s3://{signed_envelope_in_s3['pem_bucket']}/"
        f"{signed_envelope_in_s3['pem_key']}"
    )
    result = runner.invoke(
        main,
        [
            "verify-from-bucket",
            "--bucket", signed_envelope_in_s3["manifest_bucket"],
            "--key", signed_envelope_in_s3["manifest_key"],
            "--public-key-uri", pem_uri,
        ],
    )
    assert result.exit_code == 0, result.output
    assert "OK" in result.output
