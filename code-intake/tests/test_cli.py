from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from code_intake.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def runner():
    return CliRunner()


def test_help_lists_subcommands(runner):
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    for cmd in ("validate", "generate-manifest"):
        assert cmd in result.output


def test_validate_valid_package_exits_zero(runner):
    result = runner.invoke(main, ["validate", "--package", str(FIXTURES / "valid_package")])
    assert result.exit_code == 0, result.output


def test_validate_broken_package_exits_one(runner):
    result = runner.invoke(main, ["validate", "--package", str(FIXTURES / "broken_python")])
    assert result.exit_code == 1, result.output


def test_validate_json_emits_single_object(runner):
    result = runner.invoke(
        main, ["validate", "--package", str(FIXTURES / "valid_package"), "--json"]
    )
    assert result.exit_code == 0, result.output
    parsed = json.loads(result.output.strip().splitlines()[-1])
    assert "checks" in parsed
    assert "passed" in parsed


def test_generate_manifest_writes_file_on_success(runner, tmp_path):
    import shutil

    pkg = tmp_path / "pkg"
    shutil.copytree(FIXTURES / "valid_package", pkg)
    result = runner.invoke(main, ["generate-manifest", "--package", str(pkg)])
    assert result.exit_code == 0, result.output
    assert (pkg / "manifest.json").exists()
    envelope = json.loads((pkg / "manifest.json").read_text())
    assert envelope["signature"] == "UNSIGNED"
    assert envelope["subject_type"] == "package"


def test_generate_manifest_refuses_on_validation_failure(runner, tmp_path):
    import shutil

    pkg = tmp_path / "pkg"
    shutil.copytree(FIXTURES / "broken_python", pkg)
    # broken_python has only python/ — add the other required structure so
    # only the static_python check fails (otherwise SCH001 dominates).
    shutil.copytree(FIXTURES / "valid_package" / "sas", pkg / "sas")
    shutil.copy(FIXTURES / "valid_package" / "model_config.yaml", pkg / "model_config.yaml")
    shutil.copy(FIXTURES / "valid_package" / "pir.yaml", pkg / "pir.yaml")

    result = runner.invoke(main, ["generate-manifest", "--package", str(pkg)])
    assert result.exit_code == 1
    assert not (pkg / "manifest.json").exists()


def test_generate_manifest_is_byte_stable_on_rerender(runner, tmp_path):
    """The CLI's `_read_existing_manifest_timestamps` is what makes the
    drift gate work — re-rendering must produce byte-identical output.
    Without this test a regression that breaks timestamp preservation
    (e.g. someone changes the key from payload.generated_at to
    generated_at) would silently break the drift gate."""
    import shutil

    pkg = tmp_path / "pkg"
    shutil.copytree(FIXTURES / "valid_package", pkg)

    assert runner.invoke(main, ["generate-manifest", "--package", str(pkg)]).exit_code == 0
    first = (pkg / "manifest.json").read_bytes()

    assert runner.invoke(main, ["generate-manifest", "--package", str(pkg)]).exit_code == 0
    second = (pkg / "manifest.json").read_bytes()

    assert first == second, "re-rendering produced different bytes; drift gate would fail"
