from __future__ import annotations

import json
from importlib.resources import files
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker


def _schema_resource(name: str):  # type: ignore[no-untyped-def]
    return files("platform_contracts") / "schemas" / f"{name}.schema.json"


def load_schema(name: str) -> dict[str, Any]:
    resource = _schema_resource(name)
    if not resource.is_file():
        raise KeyError(f"unknown schema: {name!r}")
    return cast(dict[str, Any], json.loads(resource.read_text(encoding="utf-8")))


def validate(name: str, document: dict[str, Any]) -> None:
    """Validate a document against a named schema. Raises jsonschema.ValidationError."""
    Draft202012Validator(load_schema(name), format_checker=FormatChecker()).validate(document)
