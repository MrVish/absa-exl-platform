"""Session factories for the demo's two simulated AWS accounts.

Per spec §4.2, LocalStack CE supports multi-account via the
`x-localstack-account-id` HTTP header. We attach the header on every
botocore request via a `before-sign` event hook, scoped per-session.

Producer chain runs under 111111111111 ("exl-prod-sim"); verifier runs
under 222222222222 ("absa-sim") and exercises the cross-account IAM
grants set up by Sprint 3's signing-foundation Terraform module.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import boto3

LS_ENDPOINT = "http://localhost:4566"
PRODUCER_ACCOUNT_ID = "111111111111"
ABSA_ACCOUNT_ID = "222222222222"
REGION = "eu-west-1"


def producer_session() -> boto3.Session:
    """boto3 Session for exl-prod-sim (signer, registry, packages)."""
    return _session(account_id=PRODUCER_ACCOUNT_ID)


def absa_session() -> boto3.Session:
    """boto3 Session for absa-sim (verifier).

    Every request from this session carries `x-localstack-account-id:
    222222222222`, so LocalStack evaluates IAM as if from the ABSA account.
    """
    return _session(account_id=ABSA_ACCOUNT_ID)


def _session(*, account_id: str) -> boto3.Session:
    sess = boto3.Session(
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name=REGION,
    )
    sess.events.register("before-sign.*.*", _inject_account_id_header(account_id))
    return sess


def _inject_account_id_header(account_id: str) -> Callable[..., None]:
    """Return a botocore event hook that adds the LocalStack account header."""

    def hook(request: Any, **kwargs: object) -> None:
        request.headers["x-localstack-account-id"] = account_id

    return hook
