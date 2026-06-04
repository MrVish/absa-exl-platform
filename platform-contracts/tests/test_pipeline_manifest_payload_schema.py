import pytest
from jsonschema import ValidationError
from platform_contracts.loader import validate

VALID = {
    "schema_version": 1,
    "generator_version": "0.1.0",
    "model_name": "credit-risk-pd",
    "version": "1.0.0",
    "tier": "standard",
    "generated_at": "2026-05-26T06:00:00+00:00",
    "artifact_hashes": {
        "statemachine_sha256": "a" * 64,
        "terraform_sha256": "b" * 64,
        "model_config_sha256": "c" * 64,
        "registration_sha256": "d" * 64,
    },
}


def test_valid_payload_passes() -> None:
    validate("pipeline-manifest-payload", VALID)


def test_bad_tier_enum_fails() -> None:
    with pytest.raises(ValidationError):
        validate("pipeline-manifest-payload", {**VALID, "tier": "realtime"})


def test_missing_artifact_hash_fails() -> None:
    bad = {**VALID, "artifact_hashes": {"statemachine_sha256": "a" * 64}}
    with pytest.raises(ValidationError):
        validate("pipeline-manifest-payload", bad)


def test_short_hash_fails() -> None:
    bad_hashes = {**VALID["artifact_hashes"], "statemachine_sha256": "abc"}
    with pytest.raises(ValidationError):
        validate("pipeline-manifest-payload", {**VALID, "artifact_hashes": bad_hashes})


def test_additional_property_fails() -> None:
    with pytest.raises(ValidationError):
        validate("pipeline-manifest-payload", {**VALID, "surprise": "x"})
