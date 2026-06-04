from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from pipeline_factory.cli import main
from pytest_httpx import HTTPXMock


@pytest.fixture(autouse=True)
def _aws_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")


def _write_registration(out_dir: Path) -> None:
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
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "registration.json").write_text(
        json.dumps(body, sort_keys=True, indent=2), encoding="utf-8"
    )


def test_cli_register_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_registration(tmp_path / "pipelines" / "credit-risk-pd" / "1.0.0")
    runner = CliRunner()
    result = runner.invoke(main, ["register", "--pipeline", "credit-risk-pd@1.0.0", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "dry_run" in result.output


def test_cli_register_posts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, httpx_mock: HTTPXMock
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("REGISTRY_API_ENDPOINT", "https://api.example.test")
    _write_registration(tmp_path / "pipelines" / "credit-risk-pd" / "1.0.0")
    httpx_mock.add_response(
        method="POST",
        url="https://api.example.test/models",
        status_code=201,
        json={"approval_status": "pending"},
    )
    runner = CliRunner()
    result = runner.invoke(main, ["register", "--pipeline", "credit-risk-pd@1.0.0"])
    assert result.exit_code == 0, result.output
    assert "created" in result.output
