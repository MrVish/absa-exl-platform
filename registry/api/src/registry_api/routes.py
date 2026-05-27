from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from platform_contracts.loader import validate as validate_contract

from .api_models import CreateModelRequest, UpdateModelRequest
from .audit import emit_audit
from .repository import RegistryRepository
from .settings import get_settings

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


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


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
