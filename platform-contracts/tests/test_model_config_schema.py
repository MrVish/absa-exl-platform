import pytest
from jsonschema import ValidationError
from platform_contracts.loader import load_schema, validate

VALID = {
    "model_name": "credit-risk-pd",
    "version": "1.0.0",
    "execution_tier": "standard",
    "schedule_cadence": "cron(0 6 * * ? *)",
    "input_schema_ref": "s3://absa-exl/in.json",
    "output_schema_ref": "s3://absa-exl/out.json",
    "pir_doc_ref": "s3://absa-exl/pir.json",
    "owner_email": "owner@absa.africa",
    "accountable_executive": "Jane Exec",
    "sla_seconds": 3600,
}


def test_valid_config_passes() -> None:
    validate("model-config", VALID)


def test_unknown_schema_name_raises() -> None:
    with pytest.raises(KeyError):
        load_schema("does-not-exist")


def test_missing_required_field_fails() -> None:
    bad = {k: v for k, v in VALID.items() if k != "execution_tier"}
    with pytest.raises(ValidationError):
        validate("model-config", bad)


def test_bad_tier_enum_fails() -> None:
    with pytest.raises(ValidationError):
        validate("model-config", {**VALID, "execution_tier": "realtime"})


def test_additional_property_fails() -> None:
    with pytest.raises(ValidationError):
        validate("model-config", {**VALID, "surprise": "x"})
