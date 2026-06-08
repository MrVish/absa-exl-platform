"""Resolve a pipeline-factory model_config's upstream_package block to an
upstream_refs[] entry suitable for the pipeline manifest payload."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Re-export so ``from pipeline_factory.upstream_resolver import GeneratorError``
# keeps working. The canonical definition lives in errors.py.
from .errors import GeneratorError

__all__ = ["GeneratorError", "resolve_upstream_refs"]


def resolve_upstream_refs(
    *,
    upstream_package: dict[str, str] | None,
    packages_root: Path,
) -> list[dict[str, Any]]:
    """Read packages/<name>/<version>/manifest.json and return a single
    upstream_refs entry. Returns [] when upstream_package is None.

    Raises:
        GeneratorError: when the package manifest is missing or lacks a
            `digest` field.
    """
    if upstream_package is None:
        return []

    name = upstream_package["name"]
    version = upstream_package["version"]
    manifest_path = packages_root / name / version / "manifest.json"

    if not manifest_path.exists():
        raise GeneratorError(
            f"upstream_package references {name}@{version} but "
            f"{manifest_path} does not exist. "
            f"Run `code-intake generate-manifest --package {manifest_path.parent}` first."
        )

    envelope = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = envelope.get("digest")
    if not digest:
        raise GeneratorError(
            f"upstream package manifest at {manifest_path} is missing the "
            f"`digest` field; cannot embed cross-link."
        )

    return [
        {
            "type": "package",
            "ref": f"{name}@{version}",
            "digest": digest,
        }
    ]
