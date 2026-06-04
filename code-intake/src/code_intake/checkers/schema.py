"""schema checker: validates model_config.yaml against
package-manifest-payload.schema.json. Hash-cross-check is performed as part
of the orchestrator's full validation when a manifest exists."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml
from jsonschema import ValidationError
from platform_contracts.loader import validate as validate_contract

from .base import CheckResult, Finding


class SchemaChecker:
    name = "schema"

    def run(self, package_path: Path) -> CheckResult:
        config_path = package_path / "model_config.yaml"
        findings: list[Finding] = []

        if not config_path.is_file():
            findings.append(
                Finding(
                    severity="error",
                    code="SCH001",
                    message=f"missing model_config.yaml at {config_path}",
                    file="model_config.yaml",
                )
            )
            return CheckResult(checker=self.name, passed=False, findings=findings)

        try:
            parsed = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            findings.append(
                Finding(
                    severity="error",
                    code="SCH001",
                    message=f"model_config.yaml is not valid YAML: {e}",
                    file="model_config.yaml",
                )
            )
            return CheckResult(checker=self.name, passed=False, findings=findings)

        if not isinstance(parsed, dict):
            findings.append(
                Finding(
                    severity="error",
                    code="SCH001",
                    message="model_config.yaml top-level must be a mapping",
                    file="model_config.yaml",
                )
            )
            return CheckResult(checker=self.name, passed=False, findings=findings)

        try:
            validate_contract("package-manifest-payload", cast(dict[str, Any], parsed))
        except ValidationError as e:
            findings.append(
                Finding(
                    severity="error",
                    code="SCH001",
                    message=f"model_config.yaml fails schema validation: {e.message}",
                    file="model_config.yaml",
                )
            )
            return CheckResult(checker=self.name, passed=False, findings=findings)

        return CheckResult(checker=self.name, passed=True, findings=[])
