"""Assemble the deterministic context bundle from platform artefacts.

The bundle separates two things cleanly:

* **Grounded facts** — pulled verbatim from the package manifest, pipeline
  manifest, PIR mapping, and validation summary. These are never LLM-authored.
* **Content files** — the code + dev doc + schemas whose *text* the LLM is
  allowed to read to draft the narrative. The guard (guard.py) enforces that
  this set contains no raw data / PII.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .errors import BundleError

# Content kinds the LLM may receive. Everything else is rejected by the guard.
KIND_PYTHON = "code-python"
KIND_SAS = "code-sas"
KIND_TEST = "code-test"
KIND_DEV_DOC = "dev-doc"
KIND_CONFIG = "config"
KIND_PIR = "pir"


@dataclass(frozen=True)
class FileRef:
    """A file recorded in the package layout, by path + grounded digest."""

    path: str
    sha256: str
    kind: str


@dataclass(frozen=True)
class ContentFile:
    """A file whose text is included for the LLM to read."""

    path: str
    kind: str
    text: str


@dataclass
class ContextBundle:
    """Grounded facts + reviewable content for one model version."""

    model_name: str
    model_version: str
    package_digest: str
    pipeline_digest: str | None
    tier: str
    pir_inputs: list[dict[str, Any]] = field(default_factory=list)
    pir_outputs: list[dict[str, Any]] = field(default_factory=list)
    validation_checks: list[dict[str, Any]] = field(default_factory=list)
    upstream_refs: list[dict[str, Any]] = field(default_factory=list)
    file_inventory: list[FileRef] = field(default_factory=list)
    content_files: list[ContentFile] = field(default_factory=list)
    dev_doc_present: bool = False

    def input_digests(self) -> dict[str, str]:
        """Digests of the artefacts that grounded this bundle (for provenance)."""
        d: dict[str, str] = {"package_manifest": self.package_digest}
        if self.pipeline_digest:
            d["pipeline_manifest"] = self.pipeline_digest
        return d


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise BundleError(
            f"missing required artefact: {path}", hint="run Code Intake / Pipeline Factory first"
        ) from e
    except json.JSONDecodeError as e:
        raise BundleError(f"malformed JSON in {path}: {e}") from e
    if not isinstance(data, dict):
        raise BundleError(f"expected a JSON object in {path}")
    return data


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise BundleError(f"missing required artefact: {path}") from e
    except yaml.YAMLError as e:
        raise BundleError(f"malformed YAML in {path}: {e}") from e
    if not isinstance(data, dict):
        raise BundleError(f"expected a YAML mapping in {path}")
    return data


def _layout_files(layout: dict[str, Any]) -> list[FileRef]:
    refs: list[FileRef] = []
    for key, kind in (
        ("sas_files", KIND_SAS),
        ("python_files", KIND_PYTHON),
        ("test_files", KIND_TEST),
    ):
        for entry in layout.get(key, []) or []:
            refs.append(FileRef(path=entry["path"], sha256=entry["sha256"], kind=kind))
    for key, kind in (
        ("pir_ref", KIND_PIR),
        ("model_config_ref", KIND_CONFIG),
        ("python_pyproject_ref", KIND_CONFIG),
    ):
        ref = layout.get(key)
        if ref:
            refs.append(FileRef(path=ref["path"], sha256=ref["sha256"], kind=kind))
    return refs


# File kinds whose *content* we send for drafting. (Tests + pyproject are listed
# in the inventory as facts but their text is not needed for the narrative.)
_CONTENT_KINDS = {KIND_SAS, KIND_PYTHON, KIND_PIR, KIND_CONFIG}


def build_context_bundle(
    package_dir: Path,
    *,
    pipeline_manifest: Path | None = None,
    dev_doc: Path | None = None,
) -> ContextBundle:
    """Build the context bundle for the package at ``package_dir``.

    ``package_dir`` must contain ``model_config.yaml``, ``manifest.json`` and
    ``pir.yaml`` (the Code Intake outputs). ``pipeline_manifest`` is the Pipeline
    Factory output; ``dev_doc`` is ABSA's development documentation (optional but
    expected for a real run).
    """
    package_dir = package_dir.resolve()
    if not package_dir.is_dir():
        raise BundleError(f"package dir not found: {package_dir}")

    pkg_manifest = _read_json(package_dir / "manifest.json")
    payload = pkg_manifest.get("payload", {})
    if not isinstance(payload, dict):
        raise BundleError("package manifest has no payload object")

    model_name = str(payload.get("model_name", ""))
    model_version = str(payload.get("version", ""))
    if not model_name or not model_version:
        raise BundleError("package manifest payload missing model_name/version")

    layout = payload.get("package_layout", {})
    inventory = _layout_files(layout if isinstance(layout, dict) else {})

    validation = payload.get("validation_summary", {})
    checks = validation.get("checks", []) if isinstance(validation, dict) else []

    pir = _read_yaml(package_dir / "pir.yaml")

    tier = "(pending pipeline)"
    pipeline_digest: str | None = None
    upstream_refs: list[dict[str, Any]] = []
    if pipeline_manifest is not None:
        pm = _read_json(pipeline_manifest)
        pm_payload = pm.get("payload", {})
        if isinstance(pm_payload, dict):
            tier = str(pm_payload.get("tier", tier))
            upstream_refs = list(pm_payload.get("upstream_refs", []) or [])
        pipeline_digest = pm.get("digest")

    # Gather reviewable content (text) for the files whose kind warrants it.
    content: list[ContentFile] = []
    for ref in inventory:
        if ref.kind not in _CONTENT_KINDS:
            continue
        fpath = package_dir / ref.path
        if not fpath.is_file():
            raise BundleError(f"package layout references a missing file: {ref.path}")
        content.append(
            ContentFile(path=ref.path, kind=ref.kind, text=fpath.read_text(encoding="utf-8"))
        )

    dev_doc_present = False
    if dev_doc is not None:
        if not dev_doc.is_file():
            raise BundleError(f"dev doc not found: {dev_doc}")
        content.append(
            ContentFile(
                path=dev_doc.name, kind=KIND_DEV_DOC, text=dev_doc.read_text(encoding="utf-8")
            )
        )
        dev_doc_present = True

    return ContextBundle(
        model_name=model_name,
        model_version=model_version,
        package_digest=str(pkg_manifest.get("digest", "")),
        pipeline_digest=pipeline_digest,
        tier=tier,
        pir_inputs=list(pir.get("inputs", []) or []),
        pir_outputs=list(pir.get("outputs", []) or []),
        validation_checks=list(checks),
        upstream_refs=upstream_refs,
        file_inventory=inventory,
        content_files=content,
        dev_doc_present=dev_doc_present,
    )
