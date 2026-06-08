from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from demo.chain import ProducerResult
from demo.endpoints import DemoEndpoints
from demo.errors import DemoStepFailed
from demo.transcript import Transcript
from demo.verifier import run_verifier_chain


def _make_endpoints() -> DemoEndpoints:
    return DemoEndpoints(
        kms_key_arn="arn:aws:kms:eu-west-1:111111111111:key/abc",
        kms_key_alias="alias/exl-signing",
        manifest_bucket="exl-signed-manifests-dev",
        public_key_bucket="exl-public-keys-dev",
        registry_table="pipeline-registry-dev",
    ).with_registry_url("http://localhost:8080")


def _make_producer_result(tmp_path: Path) -> ProducerResult:
    return ProducerResult(
        package_manifest_path=tmp_path / "packages" / "credit-risk-pd" / "1.0.0" / "manifest.json",
        pipeline_manifest_path=tmp_path
        / "pipelines"
        / "credit-risk-pd"
        / "1.0.0"
        / "manifest.json",
        public_key_s3_uri="s3://exl-public-keys-dev/v1/public-key.pem",
        registry_record_id="rec_abc123",
        chain_digest="a" * 64,
    )


def test_verifier_uses_absa_session() -> None:
    """All boto3 clients in the verifier must come from absa_session(), not the default."""
    endpoints = _make_endpoints()
    transcript = Transcript(use_color=False)
    result = _make_producer_result(Path("/tmp"))

    captured_sessions: list[str] = []

    def fake_absa_session() -> MagicMock:
        sess = MagicMock()
        captured_sessions.append("absa")
        return sess

    with (
        patch("demo.verifier.absa_session", side_effect=fake_absa_session),
        patch("demo.verifier._fetch_pipeline_envelope") as mock_pipe,
        patch("demo.verifier._fetch_package_envelope") as mock_pkg,
        patch("demo.verifier._fetch_public_key_pem") as mock_pem,
        patch("demo.verifier._verify_offline_envelope"),
        patch("demo.verifier._registry_lookup") as mock_reg,
        patch("demo.verifier._compute_payload_digest", return_value="a" * 64),
    ):
        mock_pipe.return_value = {
            "payload": {"upstream_refs": [{"type": "package", "ref": "x", "digest": "a" * 64}]}
        }
        mock_pkg.return_value = {"payload": {"model_name": "credit-risk-pd"}}
        mock_pem.return_value = b"-----BEGIN PUBLIC KEY-----\n..."
        mock_reg.return_value = {"model_name": "credit-risk-pd", "version": "1.0.0"}
        run_verifier_chain(endpoints, result, transcript)

    assert captured_sessions, "absa_session was never called"


def test_verifier_raises_on_signature_mismatch() -> None:
    """If verify_offline raises VerificationError, demo step fails."""
    from manifest_signer.errors import VerificationError

    endpoints = _make_endpoints()
    transcript = Transcript(use_color=False)
    result = _make_producer_result(Path("/tmp"))

    with (
        patch("demo.verifier.absa_session", return_value=MagicMock()),
        patch(
            "demo.verifier._fetch_pipeline_envelope",
            return_value={"payload": {"upstream_refs": [{"digest": "a" * 64}]}},
        ),
        patch("demo.verifier._fetch_package_envelope", return_value={"payload": {}}),
        patch("demo.verifier._fetch_public_key_pem", return_value=b"pem"),
        patch(
            "demo.verifier._verify_offline_envelope",
            side_effect=VerificationError("signature mismatch"),
        ),
        patch("demo.verifier._registry_lookup"),
    ):
        with pytest.raises(DemoStepFailed) as exc_info:
            run_verifier_chain(endpoints, result, transcript)
        assert "verify" in str(exc_info.value).lower() or "signature" in str(exc_info.value).lower()


def test_verifier_raises_on_chain_digest_mismatch() -> None:
    """Step 4.6: re-computed package digest must equal pipeline upstream_refs[0].digest."""
    endpoints = _make_endpoints()
    transcript = Transcript(use_color=False)
    result = _make_producer_result(Path("/tmp"))

    with (
        patch("demo.verifier.absa_session", return_value=MagicMock()),
        patch(
            "demo.verifier._fetch_pipeline_envelope",
            return_value={"payload": {"upstream_refs": [{"digest": "a" * 64}]}},
        ),
        patch(
            "demo.verifier._fetch_package_envelope",
            return_value={"payload": {"model_name": "x"}},
        ),
        patch("demo.verifier._fetch_public_key_pem", return_value=b"pem"),
        patch("demo.verifier._verify_offline_envelope"),
        patch("demo.verifier._compute_payload_digest", return_value="b" * 64),
        patch("demo.verifier._registry_lookup"),
    ):
        with pytest.raises(DemoStepFailed) as exc_info:
            run_verifier_chain(endpoints, result, transcript)
        assert (
            "chain digest" in str(exc_info.value).lower()
            or "upstream" in str(exc_info.value).lower()
        )


def test_verifier_raises_on_registry_404() -> None:
    """Step 4.7: registry GET returning 404 fails the demo."""
    import urllib.error

    endpoints = _make_endpoints()
    transcript = Transcript(use_color=False)
    result = _make_producer_result(Path("/tmp"))

    with (
        patch("demo.verifier.absa_session", return_value=MagicMock()),
        patch(
            "demo.verifier._fetch_pipeline_envelope",
            return_value={"payload": {"upstream_refs": [{"digest": "a" * 64}]}},
        ),
        patch("demo.verifier._fetch_package_envelope", return_value={"payload": {}}),
        patch("demo.verifier._fetch_public_key_pem", return_value=b"pem"),
        patch("demo.verifier._verify_offline_envelope"),
        patch("demo.verifier._compute_payload_digest", return_value="a" * 64),
        patch(
            "demo.verifier._registry_lookup",
            side_effect=urllib.error.HTTPError(
                "http://localhost:8080/models/x/versions/y",
                404,
                "Not Found",
                __import__("email.message", fromlist=["Message"]).Message(),
                None,
            ),
        ),
    ):
        with pytest.raises(DemoStepFailed) as exc_info:
            run_verifier_chain(endpoints, result, transcript)
        assert "registry" in str(exc_info.value).lower() or "404" in str(exc_info.value)
