"""Terraform-output → DemoEndpoints parsing.

DemoEndpoints is the single source of truth for "what resources did
terraform create?" that the rest of the demo orchestrator consumes.
Constructed once after Phase 1 (terraform apply), threaded through every
later phase.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Any

from demo.errors import DemoError

_REQUIRED_KEYS = (
    "kms_key_arn",
    "kms_key_alias",
    "manifest_bucket",
    "public_key_bucket",
    "registry_table",
)


@dataclass(frozen=True)
class DemoEndpoints:
    """Outputs of the LocalStack Terraform stack + uvicorn registry URL.

    registry_url is populated post-uvicorn-boot via `with_registry_url`;
    everything else is populated by `from_terraform_output`.
    """

    kms_key_arn: str
    kms_key_alias: str
    manifest_bucket: str
    public_key_bucket: str
    registry_table: str
    registry_url: str = ""  # populated after uvicorn_runner.run_registry()

    @classmethod
    def from_terraform_output(cls, output_bytes: bytes) -> DemoEndpoints:
        """Parse `terraform output -json` bytes into DemoEndpoints.

        Raises DemoError on malformed JSON or missing keys.
        """
        try:
            parsed: dict[str, Any] = json.loads(output_bytes)
        except json.JSONDecodeError as e:
            raise DemoError(f"terraform output -json produced invalid JSON: {e}") from e

        values: dict[str, str] = {}
        missing: list[str] = []
        for key in _REQUIRED_KEYS:
            if key not in parsed:
                missing.append(key)
                continue
            entry = parsed[key]
            if not isinstance(entry, dict) or "value" not in entry:
                raise DemoError(
                    f"terraform output {key!r} is not in expected shape "
                    f"{{value: ...}}; got {entry!r}"
                )
            values[key] = str(entry["value"])

        if missing:
            raise DemoError(
                f"terraform output missing required keys: {missing}. "
                f"Check infra/localstack/terraform/outputs.tf."
            )

        return cls(**values)

    def with_registry_url(self, url: str) -> DemoEndpoints:
        """Return a new DemoEndpoints with registry_url set."""
        return replace(self, registry_url=url)
