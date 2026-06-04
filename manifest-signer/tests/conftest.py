"""Shared test fixtures: moto KMS asymmetric key, sample envelope, S3 bucket."""

from __future__ import annotations

import json

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


@pytest.fixture
def pipelines_tree(tmp_path, unsigned_envelope):
    """Build a fixture pipelines/ tree with two UNSIGNED manifests so sign-all
    has work to discover. The 'already-signed' path is exercised separately by
    test_sign_all_second_run_is_idempotent which runs sign-all twice."""
    root = tmp_path / "pipelines"
    one = root / "credit-risk-pd" / "1.0.0"
    one.mkdir(parents=True)
    (one / "manifest.json").write_text(
        json.dumps(unsigned_envelope, sort_keys=True, indent=2) + "\n"
    )

    # Second manifest: another UNSIGNED envelope (the signer will sign it on the
    # first run; the second run is exercised separately by the idempotency test).
    # Mutate model_name + version so the s3_key (derived from payload, not path)
    # matches the directory layout `fraud-detection/0.1.0/`.
    other_payload = dict(unsigned_envelope["payload"])
    other_payload["model_name"] = "fraud-detection"
    other_payload["version"] = "0.1.0"
    other_envelope = {
        **unsigned_envelope,
        "payload": other_payload,
        "subject_ref": "pipeline:fraud-detection:0.1.0",
    }
    two = root / "fraud-detection" / "0.1.0"
    two.mkdir(parents=True)
    (two / "manifest.json").write_text(json.dumps(other_envelope, sort_keys=True, indent=2) + "\n")
    return root
