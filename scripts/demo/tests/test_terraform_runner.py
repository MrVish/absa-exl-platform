from __future__ import annotations

import subprocess as sp
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from demo.errors import DemoStepFailed
from demo.terraform_runner import TerraformRunner


def test_init_invokes_terraform_init(tmp_path: Path) -> None:
    runner = TerraformRunner(stack_dir=tmp_path)
    with patch("demo.terraform_runner.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
        runner.init()
    args = mock_run.call_args.args[0]
    assert "terraform" in args
    assert "init" in args
    assert "-input=false" in args
    assert any("-chdir=" in a for a in args)


def test_apply_passes_vars(tmp_path: Path) -> None:
    runner = TerraformRunner(stack_dir=tmp_path)
    with patch("demo.terraform_runner.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
        runner.apply(variables={"external_verifier_arns": '["arn:aws:iam::222222222222:root"]'})
    args = mock_run.call_args.args[0]
    assert "apply" in args
    assert "-auto-approve" in args
    assert any("external_verifier_arns" in a for a in args)


def test_apply_raises_on_nonzero(tmp_path: Path) -> None:
    runner = TerraformRunner(stack_dir=tmp_path)
    with patch("demo.terraform_runner.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1, stdout=b"Plan: 0 to add", stderr=b"Error: KMS key not found"
        )
        with pytest.raises(DemoStepFailed) as exc_info:
            runner.apply(variables={})
        assert exc_info.value.exit_code == 1
        assert b"KMS key not found" in exc_info.value.stderr


def test_output_returns_json_bytes(tmp_path: Path) -> None:
    expected = b'{"key": {"value": "v"}}'
    runner = TerraformRunner(stack_dir=tmp_path)
    with patch("demo.terraform_runner.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=expected, stderr=b"")
        result = runner.output()
    assert result == expected
    args = mock_run.call_args.args[0]
    assert "output" in args
    assert "-json" in args


def test_destroy_invokes_terraform_destroy(tmp_path: Path) -> None:
    runner = TerraformRunner(stack_dir=tmp_path)
    with patch("demo.terraform_runner.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
        runner.destroy()
    args = mock_run.call_args.args[0]
    assert "destroy" in args
    assert "-auto-approve" in args


def test_timeout_becomes_demostepfailed(tmp_path: Path) -> None:
    runner = TerraformRunner(stack_dir=tmp_path)
    with patch("demo.terraform_runner.subprocess.run") as mock_run:
        mock_run.side_effect = sp.TimeoutExpired(cmd="terraform apply", timeout=120)
        with pytest.raises(DemoStepFailed) as exc_info:
            runner.apply(variables={})
        assert "timed out" in str(exc_info.value).lower()
