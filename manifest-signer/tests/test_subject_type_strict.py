from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from manifest_signer.cli import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def unknown_subject_type_tree(tmp_path: Path) -> Path:
    """Build a manifest tree with one manifest carrying subject_type='dataset'."""
    root = tmp_path / "manifests"
    pkg_dir = root / "credit-risk-pd" / "1.0.0"
    pkg_dir.mkdir(parents=True)
    envelope = {
        "envelope_version": 1,
        "subject_type": "dataset",  # not in {"package", "pipeline"}
        "subject_ref": "credit-risk-pd@1.0.0",
        "payload": {
            "schema_version": 1,
            "generator_version": "0.1.0",
            "model_name": "credit-risk-pd",
            "version": "1.0.0",
            "tier": "standard",
            "generated_at": "2026-06-05T00:00:00Z",
            "artifact_hashes": {
                "statemachine_sha256": "a" * 64,
                "terraform_sha256": "b" * 64,
                "model_config_sha256": "c" * 64,
                "registration_sha256": "d" * 64,
            },
        },
        "digest": "0" * 64,
        "signature": "UNSIGNED",
        "key_arn": "arn:aws:kms:placeholder:000000000000:key/unsigned",
        "signing_algorithm": "RSASSA_PKCS1_V1_5_SHA_256",
        "signer_principal": "unsigned",
        "signed_at": "2026-06-05T00:00:00Z",
    }
    (pkg_dir / "manifest.json").write_text(json.dumps(envelope, indent=2))
    return root


def test_sign_all_rejects_unknown_subject_type(
    runner: CliRunner,
    unknown_subject_type_tree: Path,
    signing_key,
    kms_client,
    s3_client,
) -> None:
    """sign-all must raise on unknown subject_type rather than silently
    routing to pipelines/ prefix.
    """
    bucket = "test-strict-bucket"
    s3_client.create_bucket(
        Bucket=bucket,
        CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
    )

    result = runner.invoke(
        main,
        [
            "sign-all",
            "--root",
            str(unknown_subject_type_tree),
            "--key-arn",
            signing_key["Arn"],
            "--upload-to-bucket",
            bucket,
            "--signer-principal",
            "test-principal",
        ],
    )
    assert result.exit_code != 0, result.output
    assert "unknown subject_type" in result.output
    assert "dataset" in result.output  # the offending value is mentioned


def test_sign_all_continue_on_error_logs_unknown_subject_type(
    runner: CliRunner,
    unknown_subject_type_tree: Path,
    signing_key,
    kms_client,
    s3_client,
) -> None:
    """With --continue-on-error, unknown subject_type becomes a per-item
    error logged to stderr — process exits 1 at the end.
    """
    bucket = "test-strict-bucket"
    s3_client.create_bucket(
        Bucket=bucket,
        CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
    )

    result = runner.invoke(
        main,
        [
            "sign-all",
            "--root",
            str(unknown_subject_type_tree),
            "--key-arn",
            signing_key["Arn"],
            "--upload-to-bucket",
            bucket,
            "--signer-principal",
            "test-principal",
            "--continue-on-error",
        ],
    )
    assert result.exit_code != 0  # at end, after loop
    assert "errors=1" in result.output
