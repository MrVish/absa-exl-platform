from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner
from pipeline_factory.cli import main


def test_validate_subcommand_ok(sample_config: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["validate", "--config", str(sample_config)])
    assert result.exit_code == 0
    assert "OK" in result.output


def test_generate_subcommand_writes_outputs(sample_config: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["generate", "--config", str(sample_config), "--outputs-root", str(tmp_path / "pipelines")],
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "pipelines" / "credit-risk-pd" / "1.0.0" / "statemachine.json").exists()
