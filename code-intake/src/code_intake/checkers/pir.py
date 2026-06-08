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


def _resolve_fstring_to_glob(node: ast.JoinedStr) -> str | None:
    """Convert an f-string to a glob pattern.

    Examples::

        f"month_{i}"           -> "month_*"
        f"col_{a}_{b}_data"    -> "col_*_*_data"
        f"{var}_only"          -> "*_only"
        f"{var}"               -> None (pure variable; skip)

    Pure-variable f-strings (no literal string segments) return ``None`` —
    they carry no information beyond "some column", and emitting a bare ``*``
    would match every PIR column spuriously.
    """
    parts: list[str] = []
    has_literal = False
    for piece in node.values:
        if isinstance(piece, ast.Constant) and isinstance(piece.value, str):
            parts.append(piece.value)
            has_literal = True
        else:
            parts.append("*")
    if not has_literal:
        return None
    return "".join(parts)


class _ConstantPropagator(ast.NodeVisitor):
    """Walks a single FunctionDef, tracks ``name = "literal"`` and
    ``name = f"prefix_{var}"`` assignments in a local table, then resolves
    ``data[name]`` subscript references against the table.

    Tables are intra-function only — a fresh instance is constructed per
    function in :func:`_extract_column_references`. This is conservative:
    cross-function flow + branch tracking are explicitly out of scope per
    the spec (section 6.2).
    """

    def __init__(self) -> None:
        self.const_table: dict[str, str] = {}
        self.column_refs: set[str] = set()

    def visit_Assign(self, node: ast.Assign) -> None:
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target_name = node.targets[0].id
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                self.const_table[target_name] = node.value.value
            elif isinstance(node.value, ast.JoinedStr):
                resolved = _resolve_fstring_to_glob(node.value)
                if resolved is not None:
                    self.const_table[target_name] = resolved
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if isinstance(node.value, ast.Name) and node.value.id == "data":
            key = self._resolve_subscript_key(node.slice)
            if key is not None:
                self.column_refs.add(key)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # data.col_name (literal attribute access)
        if isinstance(node.value, ast.Name) and node.value.id == "data":
            self.column_refs.add(node.attr)
        self.generic_visit(node)

    def _resolve_subscript_key(self, slice_node: ast.expr) -> str | None:
        if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
            return slice_node.value
        if isinstance(slice_node, ast.Name):
            return self.const_table.get(slice_node.id)
        if isinstance(slice_node, ast.JoinedStr):
            # Pure-variable f-string like f"{n}": try to resolve the lone
            # FormattedValue through the const_table before falling back
            # to glob conversion. This catches the common `n = "col"; data[f"{n}"]`
            # idiom without emitting an over-broad "*" glob.
            non_const = [
                v for v in slice_node.values
                if not (isinstance(v, ast.Constant) and isinstance(v.value, str))
            ]
            if (
                len(slice_node.values) == 1
                and len(non_const) == 1
                and isinstance(non_const[0], ast.FormattedValue)
                and isinstance(non_const[0].value, ast.Name)
            ):
                resolved = self.const_table.get(non_const[0].value.id)
                if resolved is not None:
                    return resolved
            return _resolve_fstring_to_glob(slice_node)
        return None


def _extract_column_references(source: str) -> set[str]:
    """Extract column-name references from Python source.

    Walks each function definition with a fresh :class:`_ConstantPropagator`
    (constant tables are intra-function only). Returns an empty set if the
    source doesn't parse.
    """
    refs: set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return refs

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            propagator = _ConstantPropagator()
            propagator.visit(node)
            refs.update(propagator.column_refs)
    return refs


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
