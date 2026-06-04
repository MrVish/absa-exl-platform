from __future__ import annotations

import json
from pathlib import Path

import pytest
from pipeline_factory.registration import RegistrationError, register
from pytest_httpx import HTTPXMock


def _write_registration(tmp_path: Path, **overrides: object) -> Path:
    body = {
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
        "sla_seconds": 3600,
        "cab_record_id": None,
        "ivu_evidence_ref": None,
    }
    body.update(overrides)
    path = tmp_path / "registration.json"
    path.write_text(json.dumps(body, sort_keys=True, indent=2), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _aws_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
    monkeypatch.setenv("REGISTRY_API_ENDPOINT", "https://api.example.test")


def test_register_dry_run_does_not_call_network(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
    reg = _write_registration(tmp_path)
    result = register(reg, dry_run=True)
    assert result["status"] == "dry_run"
    assert result["would_post"]["model_name"] == "credit-risk-pd"
    assert httpx_mock.get_requests() == []


def test_register_201_succeeds(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url="https://api.example.test/models",
        status_code=201,
        json={
            "model_name": "credit-risk-pd",
            "version": "1.0.0",
            "approval_status": "pending",
            "rev": 0,
        },
    )
    reg = _write_registration(tmp_path)
    result = register(reg)
    assert result["status"] == "created"
    assert result["body"]["approval_status"] == "pending"


def test_register_409_treated_as_idempotent(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url="https://api.example.test/models",
        status_code=409,
        json={"error": {"code": "conflict", "message": "exists"}},
    )
    reg = _write_registration(tmp_path)
    result = register(reg)
    assert result["status"] == "already_exists"


def test_register_5xx_retries_then_succeeds(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(method="POST", url="https://api.example.test/models", status_code=502)
    httpx_mock.add_response(
        method="POST",
        url="https://api.example.test/models",
        status_code=201,
        json={"approval_status": "pending"},
    )
    reg = _write_registration(tmp_path)
    result = register(reg, backoff_initial=0.0)
    assert result["status"] == "created"
    assert len(httpx_mock.get_requests()) == 2


def test_register_missing_code_version_raises(tmp_path: Path) -> None:
    reg = _write_registration(tmp_path, sas_code_version=None)
    with pytest.raises(RegistrationError, match="sas_code_version"):
        register(reg, dry_run=True)


def test_register_4xx_other_raises(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url="https://api.example.test/models",
        status_code=422,
        json={"error": {"code": "validation_error"}},
    )
    reg = _write_registration(tmp_path)
    with pytest.raises(RegistrationError, match="422"):
        register(reg)
