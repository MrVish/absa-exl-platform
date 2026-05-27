import pytest
from registry_api.repository import (
    RecordConflictError,
    RecordNotFoundError,
    RegistryRepository,
)

from .conftest import REGION, make_record


def _repo(table: str) -> RegistryRepository:
    return RegistryRepository(table, REGION)


def test_create_then_get(dynamo_table: str) -> None:
    repo = _repo(dynamo_table)
    repo.create(make_record())
    got = repo.get("credit-risk-pd", "1.0.0")
    assert got["model_name"] == "credit-risk-pd"
    assert got["rev"] == 0


def test_create_duplicate_conflicts(dynamo_table: str) -> None:
    repo = _repo(dynamo_table)
    repo.create(make_record())
    with pytest.raises(RecordConflictError):
        repo.create(make_record())


def test_get_missing_raises(dynamo_table: str) -> None:
    with pytest.raises(RecordNotFoundError):
        _repo(dynamo_table).get("missing", "1.0.0")


def test_update_optimistic_lock(dynamo_table: str) -> None:
    repo = _repo(dynamo_table)
    repo.create(make_record())
    updated = repo.update(
        "credit-risk-pd",
        "1.0.0",
        {"sla_seconds": 7200, "updated_at": "2026-05-26T07:00:00+00:00"},
        expected_rev=0,
    )
    assert updated["rev"] == 1
    assert updated["sla_seconds"] == 7200
    with pytest.raises(RecordConflictError):
        repo.update("credit-risk-pd", "1.0.0", {"sla_seconds": 10}, expected_rev=0)


def test_list_versions_and_by_status(dynamo_table: str) -> None:
    repo = _repo(dynamo_table)
    repo.create(make_record())
    repo.create(make_record(version="1.1.0"))
    assert len(repo.list_versions("credit-risk-pd")) == 2
    assert len(repo.list_by_status("pending")) == 2
    assert repo.list_by_status("approved") == []
