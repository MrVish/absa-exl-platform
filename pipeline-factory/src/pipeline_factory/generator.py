from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from platform_contracts.loader import validate as validate_contract

from .hashing import canonical_json, sha256_of_text, terraform_fmt
from .manifest import build_envelope, build_payload
from .renderer import render_pipeline_tf, render_statemachine
from .upstream_resolver import resolve_upstream_refs

OUTPUTS_ROOT = Path("pipelines")


def _existing_manifest_timestamps(out_dir: Path) -> tuple[str | None, str | None]:
    """Return (generated_at, signed_at) from an existing manifest.json.

    Returns (None, None) if the file is absent or unreadable.
    """
    manifest_path = out_dir / "manifest.json"
    if not manifest_path.exists():
        return None, None
    try:
        envelope = json.loads(manifest_path.read_text(encoding="utf-8"))
        generated_at = envelope.get("payload", {}).get("generated_at")
        signed_at = envelope.get("signed_at")
        return generated_at, signed_at
    except (json.JSONDecodeError, OSError):
        return None, None


class PipelineDriftError(Exception):
    """Raised when re-generating would change a file that already exists, without --force."""


def load_config(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(text)
    if not isinstance(parsed, dict):
        raise ValueError(f"{path} did not parse as a YAML mapping")
    validate_contract("model-config", parsed)
    return parsed


def _model_context(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": config["model_name"],
        "version": config["version"],
        "schedule_cadence": config["schedule_cadence"],
        "input_schema_ref": config["input_schema_ref"],
        "output_schema_ref": config["output_schema_ref"],
        "pir_doc_ref": config["pir_doc_ref"],
    }


def _build_registration(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "model_name": config["model_name"],
        "version": config["version"],
        "sas_code_version": config.get("sas_code_version"),
        "inference_code_version": config.get("inference_code_version"),
        "schedule_cadence": config["schedule_cadence"],
        "execution_tier": config["execution_tier"],
        "input_schema_ref": config["input_schema_ref"],
        "output_schema_ref": config["output_schema_ref"],
        "pir_doc_ref": config["pir_doc_ref"],
        "owner_email": config["owner_email"],
        "accountable_executive": config["accountable_executive"],
        "sla_seconds": config["sla_seconds"],
        "cab_record_id": config.get("cab_record_id"),
        "ivu_evidence_ref": config.get("ivu_evidence_ref"),
    }


def _write_or_check(path: Path, content: str, *, force: bool) -> None:
    if path.exists() and not force:
        existing = path.read_text(encoding="utf-8")
        if existing != content:
            raise PipelineDriftError(
                f"drift detected in {path}: existing content differs from re-rendered output. "
                f"Re-run with --force to overwrite, or investigate the divergence."
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def generate(
    config_path: Path,
    *,
    force: bool = False,
    outputs_root: Path = OUTPUTS_ROOT,
) -> Path:
    """Validate the config and render the four artifacts under outputs_root/<name>/<version>/."""
    config = load_config(config_path)
    model_name: str = config["model_name"]
    version: str = config["version"]
    tier: str = config["execution_tier"]
    out_dir = outputs_root / model_name / version

    upstream_refs = resolve_upstream_refs(
        upstream_package=config.get("upstream_package"),
        packages_root=Path("packages"),
    )

    statemachine_json = render_statemachine(tier, {"model": _model_context(config)})
    pipeline_tf_raw = render_pipeline_tf({"tier": tier, "model": _model_context(config)})
    pipeline_tf = terraform_fmt(pipeline_tf_raw)
    registration = _build_registration(config)
    registration_json = canonical_json(registration).decode("utf-8")

    artifact_hashes = {
        "statemachine_sha256": sha256_of_text(statemachine_json),
        "terraform_sha256": sha256_of_text(pipeline_tf),
        "model_config_sha256": sha256_of_text(config_path.read_text(encoding="utf-8")),
        "registration_sha256": sha256_of_text(registration_json),
    }
    existing_generated_at, existing_signed_at = _existing_manifest_timestamps(out_dir)
    payload = build_payload(
        model_name=model_name,
        version=version,
        tier=tier,
        artifact_hashes=artifact_hashes,
        generated_at=existing_generated_at,
        upstream_refs=upstream_refs,
    )
    envelope = build_envelope(
        payload=payload,
        subject_ref=f"pipelines/{model_name}/{version}/",
        signed_at=existing_signed_at,
    )
    manifest_json = canonical_json(envelope).decode("utf-8")

    files: dict[Path, str] = {
        out_dir / "statemachine.json": statemachine_json,
        out_dir / "registration.json": registration_json,
        out_dir / "manifest.json": manifest_json,
        out_dir / "terraform" / "main.tf": pipeline_tf,
    }
    for path, content in files.items():
        _write_or_check(path, content, force=force)
    return out_dir
