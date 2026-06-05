"""End-to-end happy path: sign-all -> verify-online -> verify-offline."""

from __future__ import annotations

import json

from click.testing import CliRunner
from cryptography.hazmat.primitives import serialization
from manifest_signer.cli import main


def test_full_ci_happy_path(pipelines_tree, signing_key, kms_client, s3_client):
    runner = CliRunner()
    bucket = "ci-signed-manifests"
    s3_client.create_bucket(
        Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": "eu-west-1"}
    )

    # 1. sign-all
    r = runner.invoke(
        main,
        [
            "sign-all",
            "--root",
            str(pipelines_tree),
            "--key-arn",
            signing_key["Arn"],
            "--upload-to-bucket",
            bucket,
            "--signer-principal",
            "arn:aws:sts::111:assumed-role/signer/run-42",
        ],
    )
    assert r.exit_code == 0, r.output

    # 2. Re-run sign-all -> should be idempotent
    r2 = runner.invoke(
        main,
        [
            "sign-all",
            "--root",
            str(pipelines_tree),
            "--key-arn",
            signing_key["Arn"],
            "--upload-to-bucket",
            bucket,
            "--signer-principal",
            "arn:aws:sts::111:assumed-role/signer/run-42",
        ],
    )
    assert r2.exit_code == 0, r2.output

    # 3. Download both signed manifests; verify online and offline
    der = kms_client.get_public_key(KeyId=signing_key["KeyId"])["PublicKey"]
    pub = serialization.load_der_public_key(der)
    pem = pub.public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )

    from manifest_signer.verifier import verify_offline, verify_online

    for s3_key in (
        "pipelines/credit-risk-pd/1.0.0/manifest.json",
        "pipelines/fraud-detection/0.1.0/manifest.json",
    ):
        body = s3_client.get_object(Bucket=bucket, Key=s3_key)["Body"].read()
        envelope = json.loads(body)
        assert envelope["signature"] != "UNSIGNED"
        verify_online(envelope, kms_client=kms_client)
        verify_offline(envelope, public_key_pem=pem)
