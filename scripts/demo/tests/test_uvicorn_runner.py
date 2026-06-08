from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from demo.endpoints import DemoEndpoints
from demo.errors import DemoError
from demo.uvicorn_runner import _build_uvicorn_env, run_registry


@pytest.fixture(autouse=True)
def _isolate_runtime_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Redirect _PID_FILE and _LOG_FILE into tmp_path for test isolation."""
    monkeypatch.setattr("demo.uvicorn_runner._PID_FILE", tmp_path / ".uvicorn.pid")
    monkeypatch.setattr("demo.uvicorn_runner._LOG_FILE", tmp_path / ".uvicorn.log")


def _make_endpoints() -> DemoEndpoints:
    return DemoEndpoints(
        kms_key_arn="arn:aws:kms:eu-west-1:111111111111:key/abc",
        kms_key_alias="alias/exl-signing",
        manifest_bucket="exl-signed-manifests-dev",
        public_key_bucket="exl-public-keys-dev",
        registry_table="pipeline-registry-dev",
    )


def test_build_uvicorn_env_sets_localstack_endpoint() -> None:
    env = _build_uvicorn_env(_make_endpoints())
    assert env["AWS_ENDPOINT_URL_DYNAMODB"] == "http://localhost:4566"
    assert env["AWS_REGION"] == "eu-west-1"
    assert env["AWS_ACCESS_KEY_ID"] == "test"
    assert env["AWS_SECRET_ACCESS_KEY"] == "test"
    assert env["TABLE_NAME"] == "pipeline-registry-dev"
    assert env["LOCALSTACK_ACCOUNT_ID"] == "111111111111"


def test_run_registry_starts_uvicorn_and_polls_readyz() -> None:
    endpoints = _make_endpoints()
    with (
        patch("demo.uvicorn_runner.subprocess.Popen") as mock_popen,
        patch("demo.uvicorn_runner._wait_for_readyz") as mock_wait,
        patch("demo.uvicorn_runner._write_pid_file"),
    ):
        fake_proc = MagicMock()
        fake_proc.pid = 12345
        fake_proc.poll.return_value = None
        mock_popen.return_value = fake_proc
        with run_registry(endpoints=endpoints, port=8080) as url:
            assert url == "http://localhost:8080"
            mock_wait.assert_called_once()
        fake_proc.terminate.assert_called_once()


def test_run_registry_kills_process_on_exception() -> None:
    endpoints = _make_endpoints()
    with (
        patch("demo.uvicorn_runner.subprocess.Popen") as mock_popen,
        patch("demo.uvicorn_runner._wait_for_readyz"),
        patch("demo.uvicorn_runner._write_pid_file"),
    ):
        fake_proc = MagicMock()
        fake_proc.pid = 12345
        fake_proc.poll.return_value = None
        mock_popen.return_value = fake_proc
        with (
            pytest.raises(RuntimeError, match="body raised"),
            run_registry(endpoints=endpoints, port=8080),
        ):
            raise RuntimeError("body raised")
        fake_proc.terminate.assert_called_once()


def test_run_registry_raises_demoerror_if_readyz_never_ready() -> None:
    endpoints = _make_endpoints()
    with (
        patch("demo.uvicorn_runner.subprocess.Popen") as mock_popen,
        patch("demo.uvicorn_runner._wait_for_readyz") as mock_wait,
        patch("demo.uvicorn_runner._write_pid_file"),
    ):
        fake_proc = MagicMock()
        fake_proc.pid = 12345
        fake_proc.poll.return_value = None
        mock_popen.return_value = fake_proc
        mock_wait.side_effect = DemoError("readyz did not respond in 30s")
        with pytest.raises(DemoError), run_registry(endpoints=endpoints, port=8080):
            pass
        fake_proc.terminate.assert_called_once()
