from __future__ import annotations

import json

import pytest
from click.testing import CliRunner
from cryptography.hazmat.primitives import serialization
from manifest_signer.cli import main
from manifest_signer.signer import sign_envelope


@pytest.fixture
def runner():
    return CliRunner()


def test_help_lists_all_subcommands(runner):
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    for cmd in ("sign", "sign-all", "verify-online", "verify-offline", "publish-key"):
        assert cmd in result.output


def test_sign_dry_run_does_not_call_kms(runner, unsigned_envelope, tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(unsigned_envelope, indent=2) + "\n")
    # No KMS mock -- if --dry-run actually called KMS, this would fail with
    # a connection error.
    result = runner.invoke(
        main,
        [
            "sign",
            "--manifest",
            str(manifest),
            "--key-arn",
            "arn:aws:kms:eu-west-1:111:key/abc",
            "--signer-principal",
            "test-principal",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    # Local file is unchanged
    assert json.loads(manifest.read_text())["signature"] == "UNSIGNED"


def test_sign_in_place_overwrites_file(
    runner,
    unsigned_envelope,
    signing_key,
    kms_client,
    tmp_path,
):
    """Full sign with --in-place modifies the file on disk."""
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(unsigned_envelope, indent=2) + "\n")
    result = runner.invoke(
        main,
        [
            "sign",
            "--manifest",
            str(manifest),
            "--key-arn",
            signing_key["Arn"],
            "--signer-principal",
            "test-principal",
            "--in-place",
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(manifest.read_text())["signature"] != "UNSIGNED"


def test_sign_all_signs_unsigned_uploads_skips_existing(
    runner,
    pipelines_tree,
    signing_key,
    kms_client,
    s3_client,
):
    bucket = "test-signed-manifests"
    s3_client.create_bucket(
        Bucket=bucket,
        CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
    )
    result = runner.invoke(
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
            "test-principal",
        ],
    )
    assert result.exit_code == 0, result.output
    # Both manifests uploaded
    objs = s3_client.list_objects_v2(Bucket=bucket)
    keys = {o["Key"] for o in objs.get("Contents", [])}
    assert "credit-risk-pd/1.0.0/manifest.json" in keys
    assert "fraud-detection/0.1.0/manifest.json" in keys


def test_sign_all_second_run_is_idempotent(
    runner,
    pipelines_tree,
    signing_key,
    kms_client,
    s3_client,
):
    bucket = "test-signed-manifests"
    s3_client.create_bucket(
        Bucket=bucket,
        CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
    )
    args = [
        "sign-all",
        "--root",
        str(pipelines_tree),
        "--key-arn",
        signing_key["Arn"],
        "--upload-to-bucket",
        bucket,
        "--signer-principal",
        "test-principal",
    ]
    r1 = runner.invoke(main, args)
    r2 = runner.invoke(main, args)
    assert r1.exit_code == 0 and r2.exit_code == 0
    # First run signs both manifests; second run sees them already in S3
    # and falls through the `IfNoneMatch="*"` 412 branch. Asserting on
    # the specific markers proves the idempotency branch actually fired
    # rather than the test trivially passing on identical exit codes.
    assert "[signed]" in r1.output
    assert "[skip-existing]" in r2.output
    assert "[signed]" not in r2.output


def test_verify_online_exits_zero_on_valid(
    runner,
    unsigned_envelope,
    signing_key,
    kms_client,
    tmp_path,
):
    signed = sign_envelope(
        unsigned_envelope,
        key_arn=signing_key["Arn"],
        kms_client=kms_client,
        signer_principal="test",
    )
    manifest = tmp_path / "signed.json"
    manifest.write_text(json.dumps(signed, indent=2))
    result = runner.invoke(main, ["verify-online", "--manifest", str(manifest)])
    assert result.exit_code == 0, result.output


def test_verify_offline_exits_zero_on_valid(
    runner,
    unsigned_envelope,
    signing_key,
    kms_client,
    tmp_path,
):
    signed = sign_envelope(
        unsigned_envelope,
        key_arn=signing_key["Arn"],
        kms_client=kms_client,
        signer_principal="test",
    )
    manifest = tmp_path / "signed.json"
    manifest.write_text(json.dumps(signed, indent=2))

    der = kms_client.get_public_key(KeyId=signing_key["KeyId"])["PublicKey"]
    pub = serialization.load_der_public_key(der)
    pem = pub.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    pem_path = tmp_path / "pub.pem"
    pem_path.write_bytes(pem)

    result = runner.invoke(
        main,
        [
            "verify-offline",
            "--manifest",
            str(manifest),
            "--public-key",
            str(pem_path),
        ],
    )
    assert result.exit_code == 0, result.output


def test_publish_key_uploads_pem(runner, kms_client, s3_client, signing_key):
    bucket = "test-keys"
    s3_client.create_bucket(
        Bucket=bucket,
        CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
    )
    result = runner.invoke(
        main,
        [
            "publish-key",
            "--key-arn",
            signing_key["Arn"],
            "--bucket",
            bucket,
            "--version",
            "v1",
        ],
    )
    assert result.exit_code == 0, result.output
