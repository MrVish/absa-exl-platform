import pipeline_factory
from click.testing import CliRunner
from pipeline_factory.cli import main


def test_package_imports() -> None:
    assert pipeline_factory.__name__ == "pipeline_factory"


def test_cli_help_runs() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Pipeline Factory" in result.output
