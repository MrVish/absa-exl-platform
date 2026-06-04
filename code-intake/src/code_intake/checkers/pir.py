"""pir checker: validates pir.yaml against pir-mapping.schema.json and
cross-checks that every column referenced by the Python code is mapped.

Column extraction uses stdlib `ast` to find:
  - data["col_name"]    (Subscript on Name `data`)
  - data.col_name       (Attribute on Name `data`)
within any function. Crude but sufficient for the Sprint-4 worked
example. Phase-3 packages can opt into stricter parsing via a future
PIR config flag.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, cast

import yaml
from jsonschema import ValidationError
from platform_contracts.loader import validate as validate_contract

from .base import CheckResult, Finding


def _extract_column_references(source: str) -> set[str]:
    """Parse Python source and return the set of `data["..."]` / `data....`
    column references. Returns an empty set if the source doesn't parse."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    columns: set[str] = set()
    for node in ast.walk(tree):
        # data["col_name"]  (Subscript)
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == "data"
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            columns.add(node.slice.value)
        # data.col_name     (Attribute)
        elif (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "data"
        ):
            columns.add(node.attr)
    return columns


class PirChecker:
    name = "pir"

    def run(self, package_path: Path) -> CheckResult:
        pir_path = package_path / "pir.yaml"
        findings: list[Finding] = []

        if not pir_path.is_file():
            findings.append(
                Finding(
                    severity="error",
                    code="PIR001",
                    message=f"missing pir.yaml at {pir_path}",
                    file="pir.yaml",
                )
            )
            return CheckResult(checker=self.name, passed=False, findings=findings)

        try:
            pir_data = yaml.safe_load(pir_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            findings.append(
                Finding(
                    severity="error",
                    code="PIR001",
                    message=f"pir.yaml is not valid YAML: {e}",
                    file="pir.yaml",
                )
            )
            return CheckResult(checker=self.name, passed=False, findings=findings)

        if not isinstance(pir_data, dict):
            findings.append(
                Finding(
                    severity="error",
                    code="PIR001",
                    message="pir.yaml top-level must be a mapping",
                    file="pir.yaml",
                )
            )
            return CheckResult(checker=self.name, passed=False, findings=findings)

        try:
            validate_contract("pir-mapping", cast(dict[str, Any], pir_data))
        except ValidationError as e:
            findings.append(
                Finding(
                    severity="error",
                    code="PIR001",
                    message=f"pir.yaml fails schema validation: {e.message}",
                    file="pir.yaml",
                )
            )
            return CheckResult(checker=self.name, passed=False, findings=findings)

        # Cross-check: every column referenced by Python sources must be in inputs[]
        pir_inputs = {item["name"] for item in pir_data.get("inputs", [])}
        python_dir = package_path / "python"
        if python_dir.is_dir():
            referenced: set[str] = set()
            for py_file in sorted(python_dir.rglob("*.py")):
                # Skip tests dir — pytest references won't be PIR columns.
                # Check the path *relative to* python_dir so an outer "tests/"
                # component in the fixture path doesn't false-match.
                rel_parts = py_file.relative_to(python_dir).parts
                if "tests" in rel_parts:
                    continue
                referenced |= _extract_column_references(py_file.read_text(encoding="utf-8"))

            unmapped = referenced - pir_inputs
            for col in sorted(unmapped):
                findings.append(
                    Finding(
                        severity="error",
                        code="PIR002",
                        message=f"column {col!r} referenced by Python code but not in pir.inputs[]",
                        file="pir.yaml",
                    )
                )

        passed = not any(f.severity == "error" for f in findings)
        return CheckResult(checker=self.name, passed=passed, findings=findings)
