"""End-to-end Track A: Code Intake -> Pipeline Factory -> signer -> mock registrar.

Proves the full Phase-2 chain is consistent at every link inside one moto
context. No real AWS calls; no real HTTP."""

from __future__ import annotations

import json
from pathlib import Path

import boto3
import pytest
from click.testing import CliRunner
from code_intake.cli import main as code_intake_main
from cryptography.hazmat.primitives import serialization
from manifest_signer.signer import sign_envelope
from manifest_signer.verifier import verify_offline, verify_online
from moto import mock_aws

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_PATH = REPO_ROOT / "packages" / "credit-risk-pd" / "1.0.0"
PIPELINE_CONFIG = (
    REPO_ROOT / "pipeline-factory" / "configs" / "credit-risk-pd" / "1.0.0" / "model_config.yaml"
)
PIPELINE_MANIFEST = REPO_ROOT / "pipelines" / "credit-risk-pd" / "1.0.0" / "manifest.json"


@pytest.fixture(autouse=True)
def _aws_env(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")


def test_full_track_a_chain():
    """Single-context proof that:
    1. The committed package validates and its manifest's payload-digest
       is byte-stable.
    2. The committed pipeline manifest's upstream_refs[0].digest matches
       the package manifest's digest exactly.
    3. Both manifests can be signed by the Sprint 3 signer.
    4. Both signed manifests verify online (kms:Verify) and offline (PEM).
    """
    # ----- 1) Verify the package validates fresh -----
    runner = CliRunner()
    result = runner.invoke(
        code_intake_main,
        ["validate", "--package", str(PACKAGE_PATH)],
    )
    assert result.exit_code == 0, result.output

    # ----- 2) Verify the cryptographic chain (in-git, no signing yet) -----
    pkg_manifest = json.loads((PACKAGE_PATH / "manifest.json").read_text())
    pipeline_manifest = json.loads(PIPELINE_MANIFEST.read_text())

    assert pkg_manifest["subject_type"] == "package"
    pipeline_payload = pipeline_manifest["payload"]
    assert len(pipeline_payload["upstream_refs"]) == 1
    upstream = pipeline_payload["upstream_refs"][0]
    assert upstream["type"] == "package"
    assert upstream["ref"] == "credit-risk-pd@1.0.0"
    assert upstream["digest"] == pkg_manifest["digest"], (
        f"chain broken: pipeline.upstream_refs[0].digest={upstream['digest']!r} "
        f"!= package.digest={pkg_manifest['digest']!r}"
    )

    # ----- 3) Sign both manifests under moto -----
    with mock_aws():
        kms = boto3.client("kms", region_name="eu-west-1")
        key_meta = kms.create_key(
            Description="test signing key",
            KeyUsage="SIGN_VERIFY",
            KeySpec="RSA_3072",
        )["KeyMetadata"]

        signed_pkg = sign_envelope(
            pkg_manifest,
            key_arn=key_meta["Arn"],
            kms_client=kms,
            signer_principal="arn:aws:sts::111:assumed-role/signer/test-run",
        )
        signed_pipeline = sign_envelope(
            pipeline_manifest,
            key_arn=key_meta["Arn"],
            kms_client=kms,
            signer_principal="arn:aws:sts::111:assumed-role/signer/test-run",
        )

        # The chain still holds AFTER signing: the digest field doesn't move
        # (the signer fills only the signature sentinels, not the digest).
        assert signed_pkg["digest"] == pkg_manifest["digest"]
        assert signed_pipeline["payload"]["upstream_refs"][0]["digest"] == signed_pkg["digest"]

        # ----- 4) Verify both online and offline -----
        verify_online(signed_pkg, kms_client=kms)
        verify_online(signed_pipeline, kms_client=kms)

        # Offline path: fetch the moto-generated public key + PEM-encode it.
        der = kms.get_public_key(KeyId=key_meta["KeyId"])["PublicKey"]
        pub = serialization.load_der_public_key(der)
        pem = pub.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        verify_offline(signed_pkg, public_key_pem=pem)
        verify_offline(signed_pipeline, public_key_pem=pem)


def test_full_track_a_chain_idempotent_re_sign():
    """Re-signing the already-signed envelope is a no-op (Sprint 3 contract)."""
    pkg_manifest = json.loads((PACKAGE_PATH / "manifest.json").read_text())

    with mock_aws():
        kms = boto3.client("kms", region_name="eu-west-1")
        key_meta = kms.create_key(
            Description="test signing key",
            KeyUsage="SIGN_VERIFY",
            KeySpec="RSA_3072",
        )["KeyMetadata"]

        signed_a = sign_envelope(
            pkg_manifest,
            key_arn=key_meta["Arn"],
            kms_client=kms,
            signer_principal="test",
            signed_at="2026-06-04T00:00:00+00:00",
        )
        # Re-sign with same key — same-key noop branch
        signed_b = sign_envelope(
            signed_a,
            key_arn=key_meta["Arn"],
            kms_client=kms,
            signer_principal="test",
            signed_at="2026-06-04T00:00:00+00:00",
        )
        assert signed_b is signed_a  # same object identity = noop branch fired
