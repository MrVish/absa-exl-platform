from __future__ import annotations

import json
from typing import Any

from jinja2 import Environment, PackageLoader, StrictUndefined

from .hashing import canonical_json


def _env() -> Environment:
    return Environment(
        loader=PackageLoader("pipeline_factory", "templates"),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=False,
    )


def render_statemachine(tier: str, context: dict[str, Any]) -> str:
    """Render the tier-specific ASL template and return canonical JSON."""
    if tier == "realtime":
        raise ValueError("realtime tier template is a placeholder; not implemented (brief §6)")
    if tier not in ("standard", "scalable"):
        raise ValueError(f"unknown tier: {tier!r}")
    template = _env().get_template(f"statemachines/{tier}-batch.json.j2")
    rendered = template.render(**context)
    parsed = json.loads(rendered)  # validate it parses; raises on bad template output
    return canonical_json(parsed).decode("utf-8")


def render_pipeline_tf(context: dict[str, Any]) -> str:
    """Render the per-pipeline Terraform stub. Caller is responsible for terraform-fmt."""
    template = _env().get_template("terraform/pipeline.tf.j2")
    return template.render(**context)
