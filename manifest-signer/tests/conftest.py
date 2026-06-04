"""Shared test fixtures: moto KMS asymmetric key, sample envelope, S3 bucket."""

from __future__ import annotations

import boto3
import pytest
from moto import mock_aws
from pipeline_factory.manifest import build_envelope, build_payload


@pytest.fixture(autouse=True)
def aws_creds(monkeypatch):
    """moto requires AWS_DEFAULT_REGION + dummy creds to be set."""
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")


@pytest.fixture
def mock_aws_ctx():
    with mock_aws():
        yield


@pytest.fixture
def kms_client(mock_aws_ctx):
    return boto3.client("kms", region_name="eu-west-1")


@pytest.fixture
def s3_client(mock_aws_ctx):
    return boto3.client("s3", region_name="eu-west-1")


@pytest.fixture
def signing_key(kms_client) -> dict:
    """Create a moto-backed RSA-3072 asymmetric KMS key. Returns the key's
       metadata dict (KeyId, Arn) for tests."""
    resp = kms_client.create_key(
        Description="test signing key",
        KeyUsage="SIGN_VERIFY",
        KeySpec="RSA_3072",
    )
    return resp["KeyMetadata"]


@pytest.fixture
def unsigned_envelope() -> dict:
    payload = build_payload(
        model_name="credit-risk-pd",
        version="1.0.0",
        tier="standard-batch",
        artifact_hashes={"model": "abc123", "config": "def456"},
        generated_at="2026-05-26T00:00:00+00:00",
    )
    return build_envelope(
        payload=payload,
        subject_ref="pipeline:credit-risk-pd:1.0.0",
        signed_at="2026-05-26T00:00:00+00:00",
    )


@pytest.fixture
def signer_principal() -> str:
    return "arn:aws:sts::111122223333:assumed-role/pipeline-factory-signer/test-session"
