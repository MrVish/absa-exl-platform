"""Build the Code Intake package manifest payload + envelope.

Mirrors Sprint 2's pipeline-factory manifest builder. The envelope's
sentinel fields stay UNSIGNED in git; Sprint 3's manifest-signer fills
them in CI."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from importlib.metadata import version as _pkg_version
from pathlib import Path
from typing import Any

import yaml
from platform_contracts.canonical import canonical_json

from .checkers.base import CheckResult

# Sentinel constants (mirror pipeline-factory.manifest — both packages
# define their own to avoid a cross-package dependency).
UNSIGNED_SIGNATURE = "UNSIGNED"
UNSIGNED_KEY_ARN = "arn:aws:kms:placeholder:000000000000:key/unsigned"
UNSIGNED_SIGNING_ALGORITHM = "RSASSA_PKCS1_V1_5_SHA_256"
UNSIGNED_PRINCIPAL = "unsigned"


def _code_intake_version() -> str:
    try:
        return _pkg_version("code-intake")
    except Exception:  # pragma: no cover — source checkout without install
        return "0.1.0"


def _file_ref(package_path: Path, file_path: Path) -> dict[str, str]:
    # Normalize CRLF -> LF before hashing so the manifest digest is stable
    # across platforms (Windows checkouts may have CRLF text files via
    # autocrlf; Linux/macOS use LF). All hashed file types in a package are
    # text (yaml, py, toml, sas) so this normalization is always safe; for
    # any future binary file types, a separate code path would be needed.
    raw = file_path.read_bytes()
    normalized = raw.replace(b"\r\n", b"\n")
    return {
        "path": str(file_path.relative_to(package_path).as_posix()),
        "sha256": hashlib.sha256(normalized).hexdigest(),
    }


def _build_layout(package_path: Path) -> dict[str, Any]:
    sas_files = (
        [_file_ref(package_path, p) for p in sorted((package_path / "sas").rglob("*.sas"))]
        if (package_path / "sas").is_dir()
        else []
    )
    python_dir = package_path / "python"
    python_files: list[dict[str, str]] = []
    test_files: list[dict[str, str]] = []
    # Directories that must never appear in the hashed payload:
    #   - .venv/       (leaks from `uv pip install` even with --python; see venv.py)
    #   - __pycache__/ (bytecode caches; non-deterministic)
    #   - .pytest_cache/, .ruff_cache/, .mypy_cache/ (tool caches)
    _EXCLUDE_DIRS = frozenset(
        {".venv", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
    )
    if python_dir.is_dir():
        for py in sorted(python_dir.rglob("*.py")):
            rel_parts = py.relative_to(python_dir).parts
            # Skip any file under an excluded directory anywhere in the tree
            if any(part in _EXCLUDE_DIRS for part in rel_parts):
                continue
            # Walk only the in-package tests/ subdir (NOT absolute path "tests/")
            if "tests" in rel_parts:
                test_files.append(_file_ref(package_path, py))
            else:
                python_files.append(_file_ref(package_path, py))

    return {
        "sas_files": sas_files,
        "python_files": python_files,
        "test_files": test_files,
        "pir_ref": _file_ref(package_path, package_path / "pir.yaml"),
        "model_config_ref": _file_ref(package_path, package_path / "model_config.yaml"),
        # Per Sprint 2 §7.3: cryptographically anchor python deps so an attacker
        # can't swap pyproject.toml between sign and verify to change what gets
        # installed in the per-package venv. The build will hard-fail if the
        # file is missing — packages are required to declare deps per spec §5.3.
        "python_pyproject_ref": _file_ref(package_path, python_dir / "pyproject.toml"),
    }


def _build_validation_summary(results: list[CheckResult], ran_at: str) -> dict[str, Any]:
    return {
        "ran_at": ran_at,
        "checks": [
            {
                "name": r.checker,
                "passed": r.passed,
                "finding_count": len(r.findings),
                "codes": sorted({f.code for f in r.findings}),
            }
            for r in results
        ],
    }


def build_package_payload(
    *,
    package_path: Path,
    results: list[CheckResult],
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Construct the payload object that goes inside the package envelope.

    Deferred validation rules (see ADR-0010 "Deferred checks"):

    * DEFERRED-CHECK: SCH002 — schema-version drift detection. The schema
      checker (``code_intake.checkers.schema``) only validates SCH001
      (model_config.yaml shape). SCH002 — drift between the code's declared
      schema_version and the contracted schema version — runs here at
      manifest-build time, because at that point we have access to the full
      payload AND the contracted schema version. A future ``_validate_schema_version``
      hook on the returned payload is the intended landing point.
    * DEFERRED-CHECK: SCH003 — PIR mapping referential integrity. The PIR
      checker (``code_intake.checkers.pir``) verifies PIR001 (pir.yaml shape)
      + PIR002 (every column the Python references appears in
      ``pir.inputs[]``). SCH003 — "the PIR mapping does not reference columns
      missing from the extracted column set" — also runs at manifest-build
      time because it needs the union of all columns referenced across
      ``python/``, which is computed during payload assembly.

    Both deferrals are deliberate: per-checker execution does not yet have
    the cross-cutting context these rules need.
    """
    config_path = package_path / "model_config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    now = generated_at or datetime.now(UTC).isoformat(timespec="seconds")
    return {
        "schema_version": 1,
        "code_intake_version": _code_intake_version(),
        "model_name": config["model_name"],
        "version": config["version"],
        "generated_at": now,
        "package_layout": _build_layout(package_path),
        "validation_summary": _build_validation_summary(results, now),
    }


def build_package_envelope(
    *,
    payload: dict[str, Any],
    subject_ref: str,
    signed_at: str | None = None,
) -> dict[str, Any]:
    """Wrap payload in a manifest-envelope. UNSIGNED by design — Sprint 3's
    signer fills the signature fields in CI."""
    digest = hashlib.sha256(canonical_json(payload)).hexdigest()
    return {
        "digest": digest,
        "digest_algorithm": "SHA-256",
        "signature": UNSIGNED_SIGNATURE,
        "signing_key_arn": UNSIGNED_KEY_ARN,
        "signing_algorithm": UNSIGNED_SIGNING_ALGORITHM,
        "subject_type": "package",
        "subject_ref": subject_ref,
        "signed_at": signed_at or datetime.now(UTC).isoformat(timespec="seconds"),
        "signer_principal": UNSIGNED_PRINCIPAL,
        "payload": payload,
    }
