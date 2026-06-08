from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from demo.errors import DemoError
from demo.localstack import (
    LocalStackHealthClient,
    down,
    up,
    wait_healthy,
)


def test_up_invokes_docker_compose_up_d(tmp_path: Path) -> None:
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services: {}")
    with patch("demo.localstack.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        up(compose)
    args = mock_run.call_args.args[0]
    assert args[0] == "docker"
    assert "compose" in args
    assert "-f" in args
    assert str(compose) in args
    assert "up" in args
    assert "-d" in args


def test_up_raises_demoerror_on_nonzero_exit(tmp_path: Path) -> None:
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services: {}")
    with patch("demo.localstack.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1, stdout=b"", stderr=b"Cannot connect to the Docker daemon"
        )
        with pytest.raises(DemoError) as exc_info:
            up(compose)
        assert "docker" in str(exc_info.value).lower()


def test_down_invokes_docker_compose_down(tmp_path: Path) -> None:
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services: {}")
    with patch("demo.localstack.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
        down(compose, keep_state=False)
    args = mock_run.call_args.args[0]
    assert "down" in args
    assert "-v" in args


def test_down_with_keep_state_skips_volume_removal(tmp_path: Path) -> None:
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services: {}")
    with patch("demo.localstack.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
        down(compose, keep_state=True)
    args = mock_run.call_args.args[0]
    assert "down" in args
    assert "-v" not in args


def _health_response(services: dict[str, str]) -> bytes:
    return json.dumps({"services": services, "edition": "community", "version": "3.8.1"}).encode(
        "utf-8"
    )


def test_wait_healthy_succeeds_when_all_services_available() -> None:
    health = LocalStackHealthClient(
        endpoint="http://localhost:4566",
        required_services=("kms", "s3", "dynamodb"),
    )
    with patch("demo.localstack.urllib.request.urlopen") as mock_open:
        mock_response = MagicMock()
        mock_response.read.return_value = _health_response(
            {"kms": "available", "s3": "available", "dynamodb": "available"}
        )
        mock_open.return_value.__enter__.return_value = mock_response
        health.wait_until_ready(timeout_s=5, poll_interval_s=0.1)


def test_wait_healthy_times_out_with_clear_message() -> None:
    health = LocalStackHealthClient(
        endpoint="http://localhost:4566",
        required_services=("kms", "s3", "dynamodb"),
    )
    with patch("demo.localstack.urllib.request.urlopen") as mock_open:
        mock_response = MagicMock()
        mock_response.read.return_value = _health_response(
            {"kms": "available", "s3": "available", "dynamodb": "starting"}
        )
        mock_open.return_value.__enter__.return_value = mock_response
        with pytest.raises(DemoError) as exc_info:
            health.wait_until_ready(timeout_s=0.5, poll_interval_s=0.1)
        assert "dynamodb" in str(exc_info.value)
        assert "timeout" in str(exc_info.value).lower()


def test_up_raises_demoerror_on_timeout(tmp_path: Path) -> None:
    """If `docker compose up -d` hangs past timeout, raise DemoError."""
    import subprocess as sp

    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services: {}")
    with patch("demo.localstack.subprocess.run") as mock_run:
        mock_run.side_effect = sp.TimeoutExpired(cmd="docker", timeout=180)
        with pytest.raises(DemoError) as exc_info:
            up(compose)
        assert "hung" in str(exc_info.value).lower() or "timeout" in str(exc_info.value).lower()


def test_down_raises_demoerror_on_timeout(tmp_path: Path) -> None:
    """If `docker compose down` hangs past timeout, raise DemoError."""
    import subprocess as sp

    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services: {}")
    with patch("demo.localstack.subprocess.run") as mock_run:
        mock_run.side_effect = sp.TimeoutExpired(cmd="docker", timeout=30)
        with pytest.raises(DemoError) as exc_info:
            down(compose, keep_state=False)
        assert "hung" in str(exc_info.value).lower() or "timeout" in str(exc_info.value).lower()


def test_wait_healthy_uses_localhost_4566_by_default() -> None:
    """wait_healthy's defaults match the LocalStack convention.

    Regression guard for spec §4.1 services list and the default endpoint.
    """
    with patch("demo.localstack.LocalStackHealthClient") as mock_cls:
        # The client's wait_until_ready is also mocked because we want
        # to assert on construction args without actually polling.
        mock_cls.return_value.wait_until_ready = MagicMock(return_value=None)
        wait_healthy()
    mock_cls.assert_called_once_with(
        endpoint="http://localhost:4566",
        required_services=("kms", "s3", "dynamodb", "sts", "iam"),
    )


def test_wait_healthy_forwards_timeout_s() -> None:
    """The timeout_s arg reaches LocalStackHealthClient.wait_until_ready."""
    with patch("demo.localstack.LocalStackHealthClient") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        wait_healthy(timeout_s=42.0)
    mock_instance.wait_until_ready.assert_called_once_with(timeout_s=42.0)
