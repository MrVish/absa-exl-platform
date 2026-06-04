from __future__ import annotations

from pathlib import Path

import click
import yaml
from platform_contracts.loader import validate as validate_contract

from . import registration as _registration
from .generator import OUTPUTS_ROOT, generate


@click.group()
def main() -> None:
    """ABSA x EXL Pipeline Factory generator (validate | generate | register)."""


@main.command("validate")
@click.option("--config", "config", required=True, type=click.Path(exists=True, path_type=Path))
def cmd_validate(config: Path) -> None:
    """Validate a model_config.yaml against the canonical schema."""
    parsed = yaml.safe_load(config.read_text(encoding="utf-8"))
    validate_contract("model-config", parsed)
    click.echo(f"OK: {config}")


@main.command("generate")
@click.option("--config", "config", required=True, type=click.Path(exists=True, path_type=Path))
@click.option(
    "--force", is_flag=True, default=False, help="Overwrite existing outputs without drift check"
)
@click.option(
    "--outputs-root",
    "outputs_root",
    type=click.Path(path_type=Path),
    default=OUTPUTS_ROOT,
    show_default=True,
)
def cmd_generate(config: Path, force: bool, outputs_root: Path) -> None:
    """Render the four pipeline artifacts into <outputs_root>/<name>/<version>/."""
    out_dir = generate(config, force=force, outputs_root=outputs_root)
    click.echo(f"generated: {out_dir}")


@main.command("register")
@click.option(
    "--pipeline",
    "pipeline",
    default=None,
    help="<name>@<version> — resolves pipelines/<name>/<version>/registration.json",
)
@click.option(
    "--registration",
    "registration_path",
    default=None,
    type=click.Path(exists=True, path_type=Path),
)
@click.option(
    "--endpoint", default=None, help="Registry API endpoint (default: env REGISTRY_API_ENDPOINT)"
)
@click.option("--region", default=None, help="AWS region (default: env AWS_REGION)")
@click.option("--dry-run", is_flag=True, default=False)
def cmd_register(
    pipeline: str | None,
    registration_path: Path | None,
    endpoint: str | None,
    region: str | None,
    dry_run: bool,
) -> None:
    """POST the registration body to the Registry API (SigV4)."""
    if pipeline and registration_path:
        raise click.UsageError("specify either --pipeline or --registration, not both")
    if not pipeline and not registration_path:
        raise click.UsageError("specify --pipeline or --registration")
    if pipeline:
        name, _, ver = pipeline.partition("@")
        if not ver:
            raise click.UsageError("--pipeline must be <name>@<version>")
        registration_path = Path("pipelines") / name / ver / "registration.json"
        if not registration_path.exists():
            raise click.UsageError(f"not found: {registration_path}")
    # mypy: at this point registration_path is guaranteed non-None by the guards above
    assert registration_path is not None
    result = _registration.register(
        registration_path, endpoint=endpoint, region=region, dry_run=dry_run
    )
    click.echo(result)


if __name__ == "__main__":  # pragma: no cover
    main()
