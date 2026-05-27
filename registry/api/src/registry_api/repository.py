from __future__ import annotations

from decimal import Decimal
from typing import Any, cast

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

_CONFLICT = "ConditionalCheckFailedException"


def _native(value: Any) -> Any:
    """Recursively convert DynamoDB Decimal values to native int/float."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: _native(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_native(v) for v in value]
    return value


class RecordNotFoundError(Exception):
    """Raised when a (model_name, version) record does not exist."""


class RecordConflictError(Exception):
    """Raised on create-duplicate or optimistic-lock (rev) mismatch."""


class RegistryRepository:
    def __init__(self, table_name: str, region: str) -> None:
        self._table = boto3.resource("dynamodb", region_name=region).Table(table_name)

    def create(self, record: dict[str, Any]) -> dict[str, Any]:
        try:
            self._table.put_item(
                Item=record,
                ConditionExpression=(
                    "attribute_not_exists(model_name) AND attribute_not_exists(#version)"
                ),
                ExpressionAttributeNames={"#version": "version"},
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == _CONFLICT:
                raise RecordConflictError(
                    f"{record['model_name']}@{record['version']} already exists"
                ) from exc
            raise
        return dict(record)

    def get(self, model_name: str, version: str) -> dict[str, Any]:
        response = self._table.get_item(Key={"model_name": model_name, "version": version})
        item: dict[str, Any] | None = response.get("Item")
        if item is None:
            raise RecordNotFoundError(f"{model_name}@{version} not found")
        return cast(dict[str, Any], _native(item))

    def list_versions(self, model_name: str) -> list[dict[str, Any]]:
        resp = self._table.query(KeyConditionExpression=Key("model_name").eq(model_name))
        return [_native(i) for i in resp.get("Items", [])]

    def list_by_status(self, status: str) -> list[dict[str, Any]]:
        resp = self._table.query(
            IndexName="by_status",
            KeyConditionExpression=Key("approval_status").eq(status),
        )
        return [_native(i) for i in resp.get("Items", [])]

    def scan_all(self) -> list[dict[str, Any]]:
        # Single-page scan; adequate for the <=~100 records at current platform scale.
        resp = self._table.scan()
        return [_native(i) for i in resp.get("Items", [])]

    def update(
        self,
        model_name: str,
        version: str,
        changes: dict[str, Any],
        expected_rev: int,
    ) -> dict[str, Any]:
        if not changes:
            raise ValueError("update requires at least one field to change")
        names: dict[str, str] = {"#rev": "rev"}
        values: dict[str, Any] = {":new_rev": expected_rev + 1, ":exp_rev": expected_rev}
        set_parts = ["#rev = :new_rev"]
        for i, (key, val) in enumerate(changes.items()):
            names[f"#k{i}"] = key
            values[f":v{i}"] = val
            set_parts.append(f"#k{i} = :v{i}")
        try:
            resp = self._table.update_item(
                Key={"model_name": model_name, "version": version},
                UpdateExpression="SET " + ", ".join(set_parts),
                ConditionExpression="attribute_exists(model_name) AND #rev = :exp_rev",
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=values,
                ReturnValues="ALL_NEW",
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == _CONFLICT:
                raise RecordConflictError(
                    f"rev mismatch or missing record for {model_name}@{version}"
                ) from exc
            raise
        return cast(dict[str, Any], _native(dict(resp["Attributes"])))
