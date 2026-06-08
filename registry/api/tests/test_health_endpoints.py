"""Tests for /healthz and /readyz endpoints.

- /healthz: liveness; always 200 if the FastAPI process is responsive.
- /readyz: readiness; 200 when the registry DDB table is reachable, 503 otherwise.

These are exercised by the LocalStack demo orchestrator (Phase 3 Sprint 1, T9)
which polls /readyz before allowing the producer chain to call /registry endpoints.
"""

from __future__ import annotations

from collections.abc import Iterator

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from .conftest import REGION, TABLE_NAME


def _reset_settings_cache() -> None:
    """Clear lru_cache so env-var changes are picked up by a fresh create_app()."""
    from registry_api.routes import get_repository
    from registry_api.settings import get_settings

    get_settings.cache_clear()
    get_repository.cache_clear()


@pytest.fixture
def client_with_table(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Create a fresh mock DDB table and a TestClient that knows about it."""
    monkeypatch.setenv("TABLE_NAME", TABLE_NAME)
    monkeypatch.setenv("AWS_REGION", REGION)
    _reset_settings_cache()
    with mock_aws():
        resource = boto3.resource("dynamodb", region_name=REGION)
        resource.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "model_name", "KeyType": "HASH"},
                {"AttributeName": "version", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "model_name", "AttributeType": "S"},
                {"AttributeName": "version", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        from registry_api.app import create_app

        yield TestClient(create_app())
    _reset_settings_cache()


@pytest.fixture
def client_without_table(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """No table is created in the mocked AWS account; /readyz should report 503."""
    monkeypatch.setenv("TABLE_NAME", "nonexistent-table")
    monkeypatch.setenv("AWS_REGION", REGION)
    _reset_settings_cache()
    with mock_aws():
        from registry_api.app import create_app

        yield TestClient(create_app())
    _reset_settings_cache()


def test_healthz_returns_200_always(client_without_table: TestClient) -> None:
    """Liveness probe doesn't depend on DDB; always 200 if the app is up."""
    response = client_without_table.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_returns_200_when_table_exists(client_with_table: TestClient) -> None:
    """Readiness probe checks the DDB table exists."""
    response = client_with_table.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readyz_returns_503_when_table_absent(client_without_table: TestClient) -> None:
    """Readiness probe returns 503 if the DDB table is missing or inaccessible."""
    response = client_without_table.get("/readyz")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert "reason" in body
