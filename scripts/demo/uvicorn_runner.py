"""Background uvicorn lifecycle for the registry-api FastAPI app.

Per spec section 6.3 phase 2: spawn uvicorn pointed at LocalStack DDB,
poll /readyz until 200, yield the URL, kill on context exit. Uses a
pid-file at infra/localstack/.uvicorn.pid for cross-run cleanup.

The FastAPI app lives in the registry-api workspace member (Python
package: registry_api). Its create_app() factory reads TABLE_NAME from
env and points boto3 at the AWS_ENDPOINT_URL_DYNAMODB endpoint, so we
inject the LocalStack endpoint there.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

from demo.endpoints import DemoEndpoints
from demo.errors import DemoError
from demo.sessions import LS_ENDPOINT, PRODUCER_ACCOUNT_ID

_PID_FILE = Path("infra/localstack/.uvicorn.pid")
_LOG_FILE = Path("infra/localstack/.uvicorn.log")


def _build_uvicorn_env(endpoints: DemoEndpoints) -> dict[str, str]:
    """Compose the env vars uvicorn must see to talk to LocalStack DDB."""
    env = dict(os.environ)
    env.update(
        {
            "AWS_ENDPOINT_URL_DYNAMODB": LS_ENDPOINT,
            "AWS_REGION": "eu-west-1",
            "AWS_DEFAULT_REGION": "eu-west-1",
            "AWS_ACCESS_KEY_ID": "test",
            "AWS_SECRET_ACCESS_KEY": "test",
            "TABLE_NAME": endpoints.registry_table,
            "LOCALSTACK_ACCOUNT_ID": PRODUCER_ACCOUNT_ID,
        }
    )
    return env


def _wait_for_readyz(url: str, *, timeout_s: float = 30.0, poll_interval_s: float = 0.5) -> None:
    """Block until GET <url>/readyz returns 200."""
    deadline = time.monotonic() + timeout_s
    last_status: int | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/readyz", timeout=2.0) as response:
                if response.status == 200:
                    body = json.loads(response.read())
                    if body.get("status") == "ready":
                        return
                last_status = response.status
        except urllib.error.HTTPError as e:
            last_status = e.code  # 503 from /readyz when DDB table missing
        except (urllib.error.URLError, OSError):
            # OSError covers socket.timeout, ConnectionResetError, etc. on
            # edge cases where the socket layer raises before urllib wraps it.
            pass  # uvicorn not yet listening
        time.sleep(poll_interval_s)
    raise DemoError(
        f"registry-api /readyz did not return 200 within {timeout_s}s "
        f"(last status: {last_status}). Check {_LOG_FILE} for uvicorn output. "
        f"Common cause: DDB table not yet created - make sure terraform apply "
        f"completed before run_registry()."
    )


def _write_pid_file(pid: int) -> None:
    _PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PID_FILE.write_text(str(pid), encoding="utf-8")


def _kill_stale_uvicorn_if_any() -> None:
    """If a previous demo run left a uvicorn alive, SIGTERM it."""
    if not _PID_FILE.exists():
        return
    try:
        pid = int(_PID_FILE.read_text().strip())
    except (OSError, ValueError):
        return
    try:
        os.kill(pid, signal.SIGTERM)
        # On POSIX: SIGTERM, graceful shutdown signal.
        # On Windows: CPython maps os.kill(*, SIGTERM) to TerminateProcess
        # (immediate hard kill). Fine for cleaning up a stale orphan.
        time.sleep(0.5)
    except (ProcessLookupError, PermissionError):
        pass
    finally:
        with contextlib.suppress(OSError):
            _PID_FILE.unlink()


@contextlib.contextmanager
def run_registry(*, endpoints: DemoEndpoints, port: int = 8080) -> Iterator[str]:
    """Spawn uvicorn registry_api.app:create_app as a background subprocess.

    Yields http://localhost:<port> once /readyz returns 200. Tears down
    via SIGTERM on context exit, even on exception.

    Caller must invoke from the repo root; pid and log files are written
    under infra/localstack/ relative to cwd.
    """
    _kill_stale_uvicorn_if_any()

    log_handle = _LOG_FILE.open("wb")
    try:
        proc = subprocess.Popen(
            [
                "uv",
                "run",
                "uvicorn",
                "registry_api.app:create_app",
                "--factory",
                "--port",
                str(port),
                "--host",
                "127.0.0.1",
                "--log-level",
                "info",
            ],
            env=_build_uvicorn_env(endpoints),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )
        _write_pid_file(proc.pid)
        url = f"http://localhost:{port}"
        try:
            _wait_for_readyz(url)
            yield url
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                proc.kill()
            with contextlib.suppress(OSError):
                _PID_FILE.unlink()
    finally:
        log_handle.close()
