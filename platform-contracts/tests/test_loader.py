import pytest
from platform_contracts.loader import validate

# --- package-manifest-payload ---


def test_package_manifest_payload_minimum_valid():
    validate(
        "package-manifest-payload",
        {
            "schema_version": 1,
            "code_intake_version": "0.1.0",
            "model_name": "credit-risk-pd",
            "version": "1.0.0",
            "generated_at": "2026-06-04T12:00:00+00:00",
            "package_layout": {
                "sas_files": [{"path": "sas/score.sas", "sha256": "a" * 64}],
                "python_files": [{"path": "python/score.py", "sha256": "b" * 64}],
                "test_files": [{"path": "python/tests/test_score.py", "sha256": "c" * 64}],
                "pir_ref": {"path": "pir.yaml", "sha256": "d" * 64},
                "model_config_ref": {"path": "model_config.yaml", "sha256": "e" * 64},
                "python_pyproject_ref": {"path": "python/pyproject.toml", "sha256": "f" * 64},
            },
            "validation_summary": {
                "ran_at": "2026-06-04T12:00:00+00:00",
                "checks": [{"name": "static_python", "passed": True, "finding_count": 0}],
            },
        },
    )


def test_package_manifest_payload_rejects_bad_sha256_format():
    from jsonschema import ValidationError

    with pytest.raises(ValidationError):
        validate(
            "package-manifest-payload",
            {
                "schema_version": 1,
                "code_intake_version": "0.1.0",
                "model_name": "credit-risk-pd",
                "version": "1.0.0",
                "generated_at": "2026-06-04T12:00:00+00:00",
                "package_layout": {
                    "sas_files": [{"path": "x", "sha256": "not-hex"}],
                    "python_files": [],
                    "test_files": [],
                    "pir_ref": {"path": "p", "sha256": "d" * 64},
                    "model_config_ref": {"path": "m", "sha256": "e" * 64},
                },
                "validation_summary": {"ran_at": "2026-06-04T12:00:00+00:00", "checks": []},
            },
        )


# --- pir-mapping ---


def test_pir_mapping_minimum_valid():
    validate(
        "pir-mapping",
        {
            "mapping_version": 1,
            "model_name": "credit-risk-pd",
            "model_version": "1.0.0",
            "inputs": [{"name": "income_band", "type": "float", "source": "customer.income_band"}],
            "outputs": [{"name": "pd_score", "type": "float"}],
        },
    )


def test_pir_mapping_rejects_unknown_type():
    from jsonschema import ValidationError

    with pytest.raises(ValidationError):
        validate(
            "pir-mapping",
            {
                "mapping_version": 1,
                "model_name": "credit-risk-pd",
                "model_version": "1.0.0",
                "inputs": [{"name": "x", "type": "complex128", "source": "s"}],
                "outputs": [{"name": "y", "type": "float"}],
            },
        )


# --- pipeline-manifest-payload extension ---


def test_pipeline_manifest_payload_accepts_upstream_refs():
    validate(
        "pipeline-manifest-payload",
        {
            "schema_version": 1,
            "generator_version": "0.1.0",
            "model_name": "credit-risk-pd",
            "version": "1.0.0",
            "tier": "standard",
            "generated_at": "2026-06-04T12:00:00+00:00",
            "artifact_hashes": {
                "statemachine_sha256": "a" * 64,
                "terraform_sha256": "b" * 64,
                "model_config_sha256": "c" * 64,
                "registration_sha256": "d" * 64,
            },
            "upstream_refs": [
                {"type": "package", "ref": "credit-risk-pd@1.0.0", "digest": "f" * 64},
            ],
        },
    )


def test_pipeline_manifest_payload_accepts_no_upstream_refs():
    """The field is optional with default [] — Sprint 2's existing manifest stays valid."""
    validate(
        "pipeline-manifest-payload",
        {
            "schema_version": 1,
            "generator_version": "0.1.0",
            "model_name": "credit-risk-pd",
            "version": "1.0.0",
            "tier": "standard",
            "generated_at": "2026-06-04T12:00:00+00:00",
            "artifact_hashes": {
                "statemachine_sha256": "a" * 64,
                "terraform_sha256": "b" * 64,
                "model_config_sha256": "c" * 64,
                "registration_sha256": "d" * 64,
            },
        },
    )


def test_pipeline_manifest_payload_rejects_unknown_upstream_type():
    from jsonschema import ValidationError

    with pytest.raises(ValidationError):
        validate(
            "pipeline-manifest-payload",
            {
                "schema_version": 1,
                "generator_version": "0.1.0",
                "model_name": "credit-risk-pd",
                "version": "1.0.0",
                "tier": "standard",
                "generated_at": "2026-06-04T12:00:00+00:00",
                "artifact_hashes": {
                    "statemachine_sha256": "a" * 64,
                    "terraform_sha256": "b" * 64,
                    "model_config_sha256": "c" * 64,
                    "registration_sha256": "d" * 64,
                },
                "upstream_refs": [{"type": "dataset", "ref": "x", "digest": "f" * 64}],
            },
        )


# --- model-config extension ---


def test_model_config_accepts_optional_upstream_package():
    validate(
        "model-config",
        {
            "model_name": "credit-risk-pd",
            "version": "1.0.0",
            "execution_tier": "standard",
            "schedule_cadence": "cron(0 6 * * ? *)",
            "input_schema_ref": "s3://x/in.json",
            "output_schema_ref": "s3://x/out.json",
            "pir_doc_ref": "s3://x/pir.json",
            "owner_email": "a@absa.africa",
            "accountable_executive": "Jane Exec",
            "sla_seconds": 3600,
            "upstream_package": {"name": "credit-risk-pd", "version": "1.0.0"},
        },
    )


def test_model_config_still_accepts_no_upstream_package():
    """Sprint 2's existing model_config.yaml stays valid."""
    validate(
        "model-config",
        {
            "model_name": "credit-risk-pd",
            "version": "1.0.0",
            "execution_tier": "standard",
            "schedule_cadence": "cron(0 6 * * ? *)",
            "input_schema_ref": "s3://x/in.json",
            "output_schema_ref": "s3://x/out.json",
            "pir_doc_ref": "s3://x/pir.json",
            "owner_email": "a@absa.africa",
            "accountable_executive": "Jane Exec",
            "sla_seconds": 3600,
        },
    )


def test_model_config_rejects_upstream_package_missing_version():
    from jsonschema import ValidationError

    with pytest.raises(ValidationError):
        validate(
            "model-config",
            {
                "model_name": "credit-risk-pd",
                "version": "1.0.0",
                "execution_tier": "standard",
                "schedule_cadence": "cron(0 6 * * ? *)",
                "input_schema_ref": "s3://x/in.json",
                "output_schema_ref": "s3://x/out.json",
                "pir_doc_ref": "s3://x/pir.json",
                "owner_email": "a@absa.africa",
                "accountable_executive": "Jane Exec",
                "sla_seconds": 3600,
                "upstream_package": {"name": "credit-risk-pd"},  # missing version
            },
        )
