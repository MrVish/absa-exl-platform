"""Loader for the package's model_config.yaml (validates against
package-manifest-payload.schema.json)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml
from jsonschema import ValidationError
from platform_contracts.loader import validate as validate_contract

from .errors import PackageConfigError


def load_package_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PackageConfigError(f"missing model_config.yaml at {path}")

    try:
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise PackageConfigError(f"model_config.yaml is not valid YAML: {e}") from e

    if not isinstance(parsed, dict):
        raise PackageConfigError("model_config.yaml top-level must be a mapping")

    try:
        validate_contract("package-manifest-payload", cast(dict[str, Any], parsed))
    except ValidationError as e:
        raise PackageConfigError(f"model_config.yaml fails schema validation: {e.message}") from e

    return cast(dict[str, Any], parsed)
