from pipeline_factory.manifest import (
    UNSIGNED_KEY_ARN,
    UNSIGNED_SIGNATURE,
    build_envelope,
    build_payload,
    is_signed,
)
from platform_contracts.loader import validate


def _hashes() -> dict[str, str]:
    return {
        "statemachine_sha256": "a" * 64,
        "terraform_sha256": "b" * 64,
        "model_config_sha256": "c" * 64,
        "registration_sha256": "d" * 64,
    }


def test_payload_validates_against_schema() -> None:
    payload = build_payload(
        model_name="credit-risk-pd",
        version="1.0.0",
        tier="standard",
        artifact_hashes=_hashes(),
        generated_at="2026-05-26T06:00:00+00:00",
    )
    validate("pipeline-manifest-payload", payload)


def test_envelope_validates_against_schema() -> None:
    payload = build_payload(
        model_name="credit-risk-pd",
        version="1.0.0",
        tier="standard",
        artifact_hashes=_hashes(),
        generated_at="2026-05-26T06:00:00+00:00",
    )
    envelope = build_envelope(payload=payload, subject_ref="pipelines/credit-risk-pd/1.0.0/")
    validate("manifest-envelope", envelope)


def test_unsigned_is_detectable() -> None:
    payload = build_payload(
        model_name="credit-risk-pd",
        version="1.0.0",
        tier="standard",
        artifact_hashes=_hashes(),
        generated_at="2026-05-26T06:00:00+00:00",
    )
    envelope = build_envelope(payload=payload, subject_ref="pipelines/credit-risk-pd/1.0.0/")
    assert envelope["signature"] == UNSIGNED_SIGNATURE
    assert envelope["signing_key_arn"] == UNSIGNED_KEY_ARN
    assert is_signed(envelope) is False


def test_is_signed_true_when_signature_overwritten() -> None:
    payload = build_payload(
        model_name="credit-risk-pd",
        version="1.0.0",
        tier="standard",
        artifact_hashes=_hashes(),
        generated_at="2026-05-26T06:00:00+00:00",
    )
    envelope = build_envelope(payload=payload, subject_ref="pipelines/credit-risk-pd/1.0.0/")
    envelope["signature"] = "REAL_BASE64_SIG_VALUE=="
    assert is_signed(envelope) is True


def test_build_envelope_uses_provided_signed_at() -> None:
    payload = build_payload(
        model_name="credit-risk-pd",
        version="1.0.0",
        tier="standard",
        artifact_hashes=_hashes(),
        generated_at="2026-05-26T06:00:00+00:00",
    )
    envelope = build_envelope(
        payload=payload,
        subject_ref="pipelines/credit-risk-pd/1.0.0/",
        signed_at="2026-05-26T06:00:00+00:00",
    )
    assert envelope["signed_at"] == "2026-05-26T06:00:00+00:00"


def test_build_payload_embeds_upstream_refs() -> None:
    from pipeline_factory.manifest import build_payload

    payload = build_payload(
        model_name="credit-risk-pd",
        version="1.0.0",
        tier="standard",
        artifact_hashes={
            "statemachine_sha256": "a" * 64,
            "terraform_sha256": "b" * 64,
            "model_config_sha256": "c" * 64,
            "registration_sha256": "d" * 64,
        },
        upstream_refs=[{"type": "package", "ref": "credit-risk-pd@1.0.0", "digest": "f" * 64}],
    )
    assert payload["upstream_refs"] == [
        {"type": "package", "ref": "credit-risk-pd@1.0.0", "digest": "f" * 64},
    ]


def test_build_payload_defaults_upstream_refs_to_empty_list() -> None:
    from pipeline_factory.manifest import build_payload

    payload = build_payload(
        model_name="credit-risk-pd",
        version="1.0.0",
        tier="standard",
        artifact_hashes={
            "statemachine_sha256": "a" * 64,
            "terraform_sha256": "b" * 64,
            "model_config_sha256": "c" * 64,
            "registration_sha256": "d" * 64,
        },
    )
    assert payload["upstream_refs"] == []
