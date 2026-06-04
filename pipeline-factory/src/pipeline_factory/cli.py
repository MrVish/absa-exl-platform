from __future__ import annotations

from pathlib import Path

import click
import yaml
from platform_contracts.loader import validate as validate_contract

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
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite existing outputs without drift check",
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


if __name__ == "__main__":  # pragma: no cover
    main()
