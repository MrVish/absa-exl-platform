import pytest
from jsonschema import ValidationError
from platform_contracts.loader import validate

VALID = {
    "model_name": "credit-risk-pd",
    "version": "1.0.0",
    "sas_code_version": "sas-2026.04.1",
    "inference_code_version": "py-2026.04.1",
    "schedule_cadence": "cron(0 6 * * ? *)",
    "execution_tier": "standard",
    "input_schema_ref": "s3://absa-exl/in.json",
    "output_schema_ref": "s3://absa-exl/out.json",
    "pir_doc_ref": "s3://absa-exl/pir.json",
    "owner_email": "owner@absa.africa",
    "accountable_executive": "Jane Exec",
    "approval_status": "pending",
    "sla_seconds": 3600,
    "cab_record_id": None,
    "ivu_evidence_ref": None,
    "created_at": "2026-05-26T06:00:00+00:00",
    "updated_at": "2026-05-26T06:00:00+00:00",
    "last_scored_at": None,
    "rev": 0,
}


def test_valid_record_passes() -> None:
    validate("registry-record", VALID)


def test_bad_status_enum_fails() -> None:
    with pytest.raises(ValidationError):
        validate("registry-record", {**VALID, "approval_status": "live"})


def test_missing_rev_fails() -> None:
    bad = {k: v for k, v in VALID.items() if k != "rev"}
    with pytest.raises(ValidationError):
        validate("registry-record", bad)


def test_additional_property_fails() -> None:
    with pytest.raises(ValidationError):
        validate("registry-record", {**VALID, "surprise": "x"})
