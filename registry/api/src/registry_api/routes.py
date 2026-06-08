from __future__ import annotations

import os
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from platform_contracts.loader import validate as validate_contract

from .api_models import CreateModelRequest, UpdateModelRequest
from .audit import emit_audit
from .repository import RegistryRepository
from .settings import get_settings
from .transitions import assert_approval_preconditions, assert_transition_allowed

router = APIRouter()


@lru_cache
def get_repository() -> RegistryRepository:
    settings = get_settings()
    return RegistryRepository(settings.table_name, settings.region)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _principal(request: Request) -> str:
    event = request.scope.get("aws.event", {})
    try:
        return str(event["requestContext"]["authorizer"]["iam"]["userArn"])
    except (KeyError, TypeError):
        return "local-dev"


@router.get("/healthz", tags=["health"])
def healthz() -> dict[str, str]:
    """Liveness probe -- does NOT check downstream dependencies.

    Returns 200 as long as the FastAPI process is responsive. Used by
    uvicorn_runner.py during demo orchestration to detect that the process
    has started, and by container orchestrators (k8s, ECS) for liveness.
    """
    return {"status": "ok"}


@router.get("/readyz", tags=["health"])
def readyz() -> JSONResponse:
    """Readiness probe -- checks the DynamoDB table is accessible.

    Returns 200 if the registry can serve traffic, 503 otherwise. Used by
    uvicorn_runner.py to know when to allow the demo's producer chain to
    start calling /models endpoints.
    """
    settings = get_settings()
    client = boto3.client(
        "dynamodb",
        region_name=settings.region,
        endpoint_url=os.environ.get("AWS_ENDPOINT_URL_DYNAMODB"),
    )
    try:
        # DescribeTable is a lightweight metadata call (no row scan / no read units).
        client.describe_table(TableName=settings.table_name)
    except client.exceptions.ResourceNotFoundException:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": "table_not_found"},
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "Unknown")
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": f"ddb_error: {code}"},
        )
    return JSONResponse(status_code=200, content={"status": "ready"})


@router.post("/models", status_code=status.HTTP_201_CREATED)
def create_model(
    body: CreateModelRequest,
    request: Request,
    repo: RegistryRepository = Depends(get_repository),  # noqa: B008
) -> dict[str, Any]:
    now = _now()
    record = body.model_dump()
    record.update(
        {
            "approval_status": "pending",
            "created_at": now,
            "updated_at": now,
            "last_scored_at": None,
            "rev": 0,
        }
    )
    validate_contract("registry-record", record)
    created = repo.create(record)
    emit_audit(
        principal=_principal(request),
        action="create",
        model_name=created["model_name"],
        version=created["version"],
        new_status="pending",
        rev=0,
    )
    return created


@router.get("/models")
def list_models(
    repo: RegistryRepository = Depends(get_repository),  # noqa: B008
    status_filter: str | None = Query(default=None, alias="status"),
) -> dict[str, Any]:
    items = repo.list_by_status(status_filter) if status_filter else repo.scan_all()
    return {"items": items, "count": len(items)}


@router.get("/models/{model_name}")
def list_versions(
    model_name: str,
    repo: RegistryRepository = Depends(get_repository),  # noqa: B008
) -> dict[str, Any]:
    items = repo.list_versions(model_name)
    return {"items": items, "count": len(items)}


@router.get("/models/{model_name}/versions/{version}")
def get_model(
    model_name: str,
    version: str,
    repo: RegistryRepository = Depends(get_repository),  # noqa: B008
) -> dict[str, Any]:
    return repo.get(model_name, version)


@router.patch("/models/{model_name}/versions/{version}")
def update_model(
    model_name: str,
    version: str,
    body: UpdateModelRequest,
    request: Request,
    repo: RegistryRepository = Depends(get_repository),  # noqa: B008
) -> dict[str, Any]:
    changes = body.model_dump(exclude={"expected_rev"}, exclude_none=True)
    changes["updated_at"] = _now()
    updated = repo.update(model_name, version, changes, expected_rev=body.expected_rev)
    emit_audit(
        principal=_principal(request),
        action="update",
        model_name=model_name,
        version=version,
        rev=updated["rev"],
    )
    return updated


def _transition(
    model_name: str,
    version: str,
    target: str,
    request: Request,
    repo: RegistryRepository,
) -> dict[str, Any]:
    current = repo.get(model_name, version)
    assert_transition_allowed(current["approval_status"], target)
    if target == "approved":
        assert_approval_preconditions(current)
    updated = repo.update(
        model_name,
        version,
        {"approval_status": target, "updated_at": _now()},
        expected_rev=current["rev"],
    )
    emit_audit(
        principal=_principal(request),
        action=target,
        model_name=model_name,
        version=version,
        old_status=current["approval_status"],
        new_status=target,
        rev=updated["rev"],
    )
    return updated


@router.post("/models/{model_name}/versions/{version}:approve")
def approve_model(
    model_name: str,
    version: str,
    request: Request,
    repo: RegistryRepository = Depends(get_repository),  # noqa: B008
) -> dict[str, Any]:
    return _transition(model_name, version, "approved", request, repo)


@router.post("/models/{model_name}/versions/{version}:retire")
def retire_model(
    model_name: str,
    version: str,
    request: Request,
    repo: RegistryRepository = Depends(get_repository),  # noqa: B008
) -> dict[str, Any]:
    return _transition(model_name, version, "retired", request, repo)
