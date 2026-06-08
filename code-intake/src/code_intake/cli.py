"""Click CLI for code-intake.

Subcommands:
- validate          - run all five checkers; exit 0/1
- generate-manifest - validate then write manifest.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from platform_contracts.canonical import canonical_json

from .checkers.base import CheckResult
from .manifest import build_package_envelope, build_package_payload
from .orchestrator import validate as run_validate


def _read_existing_manifest_timestamps(
    out: Path,
) -> tuple[str | None, str | None]:
    if not out.is_file():
        return None, None
    try:
        envelope = json.loads(out.read_text(encoding="utf-8"))
        return (
            envelope.get("payload", {}).get("generated_at"),
            envelope.get("signed_at"),
        )
    except (json.JSONDecodeError, OSError):
        return None, None


def _summarise(results: list[CheckResult], *, as_json: bool) -> str:
    if as_json:
        return json.dumps(
            {
                "passed": all(r.passed for r in results),
                "checks": [
                    {
                        "name": r.checker,
                        "passed": r.passed,
                        "finding_count": len(r.findings),
                        "duration_seconds": round(r.duration_seconds, 3),
                        "findings": [
                            {
                                "severity": f.severity,
                                "code": f.code,
                                "message": f.message,
                                "file": f.file,
                                "line": f.line,
                                "hint": f.hint,
                                "location": f.location,
                            }
                            for f in r.findings
                        ],
                    }
                    for r in results
                ],
            },
            sort_keys=True,
        )

    lines = []
    for r in results:
        status = "OK" if r.passed else "FAIL"
        lines.append(f"[{status}] {r.checker} ({r.duration_seconds:.2f}s)")
        for f in r.findings:
            lines.append(f"    {f.code} ({f.severity}): {f.message}")
            if f.file:
                location = f.file + (f":{f.line}" if f.line else "")
                lines.append(f"        at {location}")
            elif f.location:
                lines.append(f"        at {f.location}")
            if f.hint:
                lines.append(f"        hint: {f.hint}")
    overall = "PASSED" if all(r.passed for r in results) else "FAILED"
    lines.append(f"\nOverall: {overall}")
    return "\n".join(lines)


@click.group(help=__doc__)
def main() -> None:
    pass


@main.command("validate")
@click.option(
    "--package",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option("--strict", is_flag=True, help="Flip warning-severity findings into errors")
@click.option("--json", "as_json", is_flag=True, help="Emit a single JSON object on stdout")
def validate_cmd(package: Path, strict: bool, as_json: bool) -> None:
    results = run_validate(package, strict=strict)
    click.echo(_summarise(results, as_json=as_json))
    if not all(r.passed for r in results):
        sys.exit(1)


@main.command("generate-manifest")
@click.option(
    "--package",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option("--strict", is_flag=True)
def generate_manifest_cmd(package: Path, strict: bool) -> None:
    """Run validate; on success, write packages/<name>/<version>/manifest.json."""
    results = run_validate(package, strict=strict)
    if not all(r.passed for r in results):
        click.echo(_summarise(results, as_json=False), err=True)
        click.echo("\nValidation failed - manifest NOT written.", err=True)
        sys.exit(1)

    manifest_path = package / "manifest.json"
    existing_generated_at, existing_signed_at = _read_existing_manifest_timestamps(manifest_path)
    payload = build_package_payload(
        package_path=package,
        results=results,
        generated_at=existing_generated_at,
    )
    envelope = build_package_envelope(
        payload=payload,
        subject_ref=f"packages/{payload['model_name']}/{payload['version']}/",
        signed_at=existing_signed_at,
    )

    manifest_path.write_bytes(canonical_json(envelope))
    click.echo(f"Wrote {manifest_path}")
