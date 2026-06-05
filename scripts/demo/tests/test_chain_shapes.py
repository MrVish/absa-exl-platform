from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from demo.chain import (
    ProducerResult,
    _compute_payload_digest,
    _localstack_env,
    run_producer_chain,
)
from demo.endpoints import DemoEndpoints
from demo.errors import DemoStepFailed
from demo.transcript import Transcript


def _make_endpoints(registry_url: str = "http://localhost:8080") -> DemoEndpoints:
    return DemoEndpoints(
        kms_key_arn="arn:aws:kms:eu-west-1:111111111111:key/abc",
        kms_key_alias="alias/exl-signing",
        manifest_bucket="exl-signed-manifests-dev",
        public_key_bucket="exl-public-keys-dev",
        registry_table="pipeline-registry-dev",
    ).with_registry_url(registry_url)


def test_localstack_env_includes_account_id() -> None:
    """The env passed to subprocess includes LOCALSTACK_ACCOUNT_ID."""
    env = _localstack_env(account_id="111111111111")
    assert env["LOCALSTACK_ACCOUNT_ID"] == "111111111111"
    assert env["AWS_ENDPOINT_URL_KMS"] == "http://localhost:4566"
    assert env["AWS_ENDPOINT_URL_S3"] == "http://localhost:4566"
    assert env["AWS_ACCESS_KEY_ID"] == "test"
    assert env["AWS_REGION"] == "eu-west-1"


def test_compute_payload_digest_uses_canonical_json() -> None:
    """Verifier-side digest computation matches signer's hash convention."""
    from platform_contracts.canonical import canonical_json

    payload = {"key": "value", "another": 42}
    expected = hashlib.sha256(canonical_json(payload)).hexdigest()
    assert _compute_payload_digest(payload) == expected


def test_run_producer_chain_calls_subprocesses_in_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The 7 producer-chain CLIs run in the correct sequence."""
    pkg_path = tmp_path / "packages" / "credit-risk-pd" / "1.0.0"
    pkg_path.mkdir(parents=True)
    manifest = pkg_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "subject_type": "package",
                "payload": {"model_name": "credit-risk-pd", "version": "1.0.0"},
                "digest": "a" * 64,
                "signature": "fakebase64",
            }
        )
    )

    pipeline_dir = tmp_path / "pipelines" / "credit-risk-pd" / "1.0.0"
    pipeline_dir.mkdir(parents=True)
    (pipeline_dir / "manifest.json").write_text(
        json.dumps(
            {
                "subject_type": "pipeline",
                "payload": {
                    "model_name": "credit-risk-pd",
                    "version": "1.0.0",
                    "upstream_refs": [
                        {"type": "package", "ref": "credit-risk-pd@1.0.0", "digest": "a" * 64},
                    ],
                },
                "signature": "fakebase64",
            }
        )
    )

    endpoints = _make_endpoints()
    transcript = Transcript(use_color=False)
    invocations: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        invocations.append(list(args))
        result = MagicMock()
        result.returncode = 0
        if "sign-all" in args:
            result.stdout = b"[signed] credit-risk-pd@1.0.0 -> s3://...\n"
        elif "register" in args:
            result.stdout = (
                b"{'status': 'created', 'body': {'pk': 'pipeline#credit-risk-pd', 'sk': '1.0.0'}}\n"
            )
        else:
            result.stdout = b""
        result.stderr = b""
        return result

    monkeypatch.chdir(tmp_path)
    with patch("demo.chain.subprocess.run", side_effect=fake_run):
        run_producer_chain(endpoints, pkg_path, transcript)

    cli_names = []
    for args in invocations:
        for i, a in enumerate(args):
            if a in ("code-intake", "manifest-signer", "generate-pipeline", "register-pipeline"):
                cli_names.append(f"{a} {args[i + 1]}" if i + 1 < len(args) else a)
                break
    expected = [
        "code-intake validate",
        "code-intake generate-manifest",
        "manifest-signer sign",
        "generate-pipeline generate",
        "manifest-signer sign-all",
        "manifest-signer publish-key",
        "generate-pipeline register",
    ]
    assert cli_names == expected, f"got order: {cli_names}"


def test_run_producer_chain_asserts_chain_digest_between_3_4_and_3_5(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Producer-side chain assertion: package digest must equal pipeline upstream_refs[0].digest."""
    pkg_path = tmp_path / "packages" / "credit-risk-pd" / "1.0.0"
    pkg_path.mkdir(parents=True)
    (pkg_path / "manifest.json").write_text(
        json.dumps(
            {
                "subject_type": "package",
                "payload": {"model_name": "credit-risk-pd", "version": "1.0.0"},
                "digest": "a" * 64,
                "signature": "fake",
            }
        )
    )

    pipeline_dir = tmp_path / "pipelines" / "credit-risk-pd" / "1.0.0"
    pipeline_dir.mkdir(parents=True)
    # DELIBERATELY MISMATCHED digest in upstream_refs:
    (pipeline_dir / "manifest.json").write_text(
        json.dumps(
            {
                "subject_type": "pipeline",
                "payload": {
                    "model_name": "credit-risk-pd",
                    "version": "1.0.0",
                    "upstream_refs": [
                        {"type": "package", "ref": "credit-risk-pd@1.0.0", "digest": "b" * 64},
                    ],
                },
                "signature": "fake",
            }
        )
    )

    endpoints = _make_endpoints()
    transcript = Transcript(use_color=False)

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        result = MagicMock()
        result.returncode = 0
        result.stdout = b"[signed] x\n" if "sign-all" in args else b""
        result.stderr = b""
        return result

    monkeypatch.chdir(tmp_path)
    with patch("demo.chain.subprocess.run", side_effect=fake_run):
        with pytest.raises(DemoStepFailed) as exc_info:
            run_producer_chain(endpoints, pkg_path, transcript)
        assert "chain digest" in str(exc_info.value).lower() or "upstream_refs" in str(
            exc_info.value
        )


def test_run_producer_chain_asserts_signed_not_skip_existing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If sign-all reports [skip-existing] on a fresh run, that's a regression."""
    pkg_path = tmp_path / "packages" / "credit-risk-pd" / "1.0.0"
    pkg_path.mkdir(parents=True)
    (pkg_path / "manifest.json").write_text(
        json.dumps(
            {
                "subject_type": "package",
                "payload": {"model_name": "credit-risk-pd", "version": "1.0.0"},
                "digest": "a" * 64,
                "signature": "fake",
            }
        )
    )

    pipeline_dir = tmp_path / "pipelines" / "credit-risk-pd" / "1.0.0"
    pipeline_dir.mkdir(parents=True)
    (pipeline_dir / "manifest.json").write_text(
        json.dumps(
            {
                "subject_type": "pipeline",
                "payload": {
                    "model_name": "credit-risk-pd",
                    "version": "1.0.0",
                    "upstream_refs": [
                        {"type": "package", "ref": "credit-risk-pd@1.0.0", "digest": "a" * 64},
                    ],
                },
                "signature": "fake",
            }
        )
    )

    endpoints = _make_endpoints()
    transcript = Transcript(use_color=False)

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        result = MagicMock()
        result.returncode = 0
        # WRONG: report [skip-existing] instead of [signed]
        result.stdout = (
            b"[skip-existing] credit-risk-pd@1.0.0 already in S3\n" if "sign-all" in args else b""
        )
        result.stderr = b""
        return result

    monkeypatch.chdir(tmp_path)
    with patch("demo.chain.subprocess.run", side_effect=fake_run):
        with pytest.raises(DemoStepFailed) as exc_info:
            run_producer_chain(endpoints, pkg_path, transcript)
        assert "skip-existing" in str(exc_info.value).lower() or "[signed]" in str(exc_info.value)


def test_producer_result_is_frozen_dataclass() -> None:
    """ProducerResult must be frozen so callers can't mutate it after creation."""
    result = ProducerResult(
        package_manifest_path=Path("a/manifest.json"),
        pipeline_manifest_path=Path("b/manifest.json"),
        public_key_s3_uri="s3://bucket/key.pem",
        registry_record_id="rec_abc123",
        chain_digest="a" * 64,
    )
    with pytest.raises(Exception):  # FrozenInstanceError
        result.registry_record_id = "rec_other"  # type: ignore[misc]
