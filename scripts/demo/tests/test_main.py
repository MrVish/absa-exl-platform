from __future__ import annotations

from click.testing import CliRunner

from demo.__main__ import main


def test_main_lists_subcommands() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    for cmd in ("up", "run", "down", "status"):
        assert cmd in result.output


def test_run_subcommand_lists_options() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["run", "--help"])
    assert result.exit_code == 0
    for opt in ("--keep-state", "--no-cleanup", "--transcript", "--no-color"):
        assert opt in result.output
