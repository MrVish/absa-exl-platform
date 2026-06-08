"""docker-compose lifecycle + LocalStack health polling.

Per spec sections 6.2 and 6.5: this module owns the docker compose
surface and the /_localstack/health poll. No boto3 here.
"""

from __future__ import annotations

import http.client
import json
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from demo.errors import DemoError
from demo.sessions import LS_ENDPOINT


def up(compose_file: Path) -> None:
    """Run `docker compose -f <compose_file> up -d`."""
    try:
        proc = subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "up", "-d"],
            capture_output=True,
            timeout=180,  # accommodates LocalStack image first-pull on cold CI
        )
    except subprocess.TimeoutExpired as e:
        raise DemoError(
            "docker compose up -d hung for 180s without completing. "
            "Hint: check Docker daemon health (`docker ps`), or pull the "
            "LocalStack image manually with `docker pull localstack/localstack:3.8.1`."
        ) from e
    if proc.returncode != 0:
        stderr_text = (
            proc.stderr.decode("utf-8", errors="replace")
            if isinstance(proc.stderr, bytes)
            else proc.stderr
        )
        raise DemoError(
            f"docker compose up -d failed with exit {proc.returncode}:\n{stderr_text}\n\n"
            f"Hint: ensure Docker Desktop (or dockerd) is running and "
            f"port 4566 is free."
        )


def down(compose_file: Path, *, keep_state: bool) -> None:
    """Run `docker compose down`. With keep_state=False, also passes -v
    to remove the LocalStack volume so the next run starts clean.
    """
    args = ["docker", "compose", "-f", str(compose_file), "down"]
    if not keep_state:
        args.append("-v")
    try:
        proc = subprocess.run(args, capture_output=True, timeout=30)
    except subprocess.TimeoutExpired as e:
        raise DemoError(
            "docker compose down hung for 30s. Container may be stuck. "
            "Hint: `docker ps` to check, then `docker kill <container>` if needed."
        ) from e
    if proc.returncode != 0:
        stderr_text = (
            proc.stderr.decode("utf-8", errors="replace")
            if isinstance(proc.stderr, bytes)
            else proc.stderr
        )
        raise DemoError(f"docker compose down failed: {stderr_text}")


@dataclass(frozen=True)
class LocalStackHealthClient:
    """Polls /_localstack/health until all required services are available."""

    endpoint: str
    required_services: tuple[str, ...]

    def wait_until_ready(self, *, timeout_s: float = 60.0, poll_interval_s: float = 1.0) -> None:
        deadline = time.monotonic() + timeout_s
        last_status: dict[str, str] = {}
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(
                    f"{self.endpoint}/_localstack/health", timeout=2.0
                ) as response:
                    payload = json.loads(response.read())
            except (
                urllib.error.URLError,
                json.JSONDecodeError,
                http.client.HTTPException,
                # LocalStack's gateway is racy during startup: TCP accepts
                # arrive before HTTP service is ready, producing varied
                # errors depending on OS and gateway state:
                #   - http.client.RemoteDisconnected (Linux/macOS)
                #   - ConnectionResetError (Linux raw socket)
                #   - ConnectionAbortedError - WinError 10053 (Windows)
                #   - socket.timeout / TimeoutError
                # OSError is the common ancestor of every connection-tier
                # error we want to retry on. Catching it here is broad but
                # the loop has a deadline, so we won't retry forever.
                OSError,
            ):
                time.sleep(poll_interval_s)
                continue
            services = payload.get("services", {})
            last_status = {k: v for k, v in services.items() if k in self.required_services}
            if all(last_status.get(s) == "available" for s in self.required_services):
                return
            time.sleep(poll_interval_s)

        unavailable = [s for s in self.required_services if last_status.get(s) != "available"]
        raise DemoError(
            f"LocalStack health check timeout after {timeout_s}s (timed out waiting "
            f"for services). Services not available: {unavailable}. "
            f"Last status: {last_status}. "
            f"Hint: docker logs absa-exl-localstack to see startup logs."
        )


def wait_healthy(
    endpoint: str = LS_ENDPOINT,
    *,
    required_services: tuple[str, ...] = ("kms", "s3", "dynamodb", "sts", "iam"),
    timeout_s: float = 60.0,
) -> None:
    """Convenience wrapper used by __main__.py."""
    client = LocalStackHealthClient(endpoint=endpoint, required_services=required_services)
    client.wait_until_ready(timeout_s=timeout_s)
