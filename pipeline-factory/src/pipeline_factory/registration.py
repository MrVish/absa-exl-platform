from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import boto3
import httpx
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest


class RegistrationError(Exception):
    """Raised when registration cannot be completed."""


def _sign_headers(*, method: str, url: str, body: str, region: str) -> dict[str, str]:
    session = boto3.Session()
    credentials = session.get_credentials()
    if credentials is None:
        raise RegistrationError("no AWS credentials available for SigV4 signing")
    request = AWSRequest(
        method=method, url=url, data=body, headers={"Content-Type": "application/json"}
    )
    SigV4Auth(credentials, "execute-api", region).add_auth(request)
    return dict(request.headers)


def _try_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return resp.text


def register(
    registration_path: Path,
    *,
    endpoint: str | None = None,
    region: str | None = None,
    dry_run: bool = False,
    max_attempts: int = 3,
    backoff_initial: float = 1.0,
) -> dict[str, Any]:
    """Read the registration body and POST it to the Registry API.

    Returns a small status dict. Raises RegistrationError on terminal failures.
    """
    body_text = registration_path.read_text(encoding="utf-8")
    body = json.loads(body_text)

    for required in ("sas_code_version", "inference_code_version"):
        if not body.get(required):
            raise RegistrationError(
                f"{required} is required for registration; populate it in model_config.yaml "
                f"(it is optional in the schema but required at register time)"
            )

    if dry_run:
        return {"status": "dry_run", "would_post": body}

    endpoint = endpoint or os.environ.get("REGISTRY_API_ENDPOINT")
    if not endpoint:
        raise RegistrationError("REGISTRY_API_ENDPOINT not set")
    region = (
        region or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION", "eu-west-1")
    )
    url = f"{endpoint.rstrip('/')}/models"

    backoff = backoff_initial
    last_status: int | None = None
    last_body: str = ""
    for attempt in range(1, max_attempts + 1):
        headers = _sign_headers(method="POST", url=url, body=body_text, region=region)
        with httpx.Client(timeout=30) as client:
            resp = client.post(url, content=body_text, headers=headers)
        last_status, last_body = resp.status_code, resp.text
        if resp.status_code == 201:
            return {"status": "created", "body": resp.json()}
        if resp.status_code == 409:
            return {"status": "already_exists", "body": _try_json(resp)}
        if 500 <= resp.status_code < 600 and attempt < max_attempts:
            time.sleep(backoff)
            backoff *= 4
            continue
        raise RegistrationError(f"registration failed: HTTP {resp.status_code} {resp.text}")
    raise RegistrationError(
        f"registration failed after {max_attempts} attempts (last HTTP {last_status}: {last_body})"
    )
