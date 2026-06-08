from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from code_intake.errors import VenvCreationError
from code_intake.venv import VenvContext, create_ephemeral_venv


def test_create_ephemeral_venv_raises_PY004_when_pyproject_missing(tmp_path: Path) -> None:
    pkg = tmp_path / "broken-package"
    (pkg / "python").mkdir(parents=True)
    # NO pyproject.toml
    with pytest.raises(VenvCreationError) as exc_info, create_ephemeral_venv(pkg):
        pass
    assert exc_info.value.code == "PY004"
    assert "pyproject.toml" in exc_info.value.message
    assert exc_info.value.hint is not None


def test_create_ephemeral_venv_succeeds_and_yields_context(tmp_path: Path) -> None:
    pkg = tmp_path / "good-package"
    (pkg / "python").mkdir(parents=True)
    (pkg / "python" / "pyproject.toml").write_text('[project]\nname = "test"\nversion = "0.1"\n')

    with patch("code_intake.venv.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
        with create_ephemeral_venv(pkg) as ctx:
            assert isinstance(ctx, VenvContext)
            assert ctx.venv_dir.exists()
            assert "VIRTUAL_ENV" in ctx.env_vars
            assert ctx.env_vars["VIRTUAL_ENV"] == str(ctx.venv_dir)
            assert "PATH" in ctx.env_vars
            # PATH includes the venv's bin dir
            assert str(ctx.python_path.parent) in ctx.env_vars["PATH"]


def test_create_ephemeral_venv_tears_down_on_exception(tmp_path: Path) -> None:
    pkg = tmp_path / "good-package"
    (pkg / "python").mkdir(parents=True)
    (pkg / "python" / "pyproject.toml").write_text('[project]\nname = "test"\nversion = "0.1"\n')

    captured_venv_dir: Path | None = None
    with patch("code_intake.venv.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        with pytest.raises(RuntimeError, match="body"), create_ephemeral_venv(pkg) as ctx:
            captured_venv_dir = ctx.venv_dir
            raise RuntimeError("body raised")
    assert captured_venv_dir is not None
    # After context exit, the tmpdir is gone
    assert not captured_venv_dir.exists()


def test_create_ephemeral_venv_raises_PY998_on_uv_venv_failure(tmp_path: Path) -> None:
    pkg = tmp_path / "good-package"
    (pkg / "python").mkdir(parents=True)
    (pkg / "python" / "pyproject.toml").write_text('[project]\nname = "test"\nversion = "0.1"\n')

    with patch("code_intake.venv.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1, stdout=b"", stderr=b"uv venv failed: permission denied"
        )
        with pytest.raises(VenvCreationError) as exc_info, create_ephemeral_venv(pkg):
            pass
        msg = exc_info.value.message
        assert exc_info.value.code == "PY998"
        assert "uv venv" in msg.lower() or "permission denied" in msg


def test_create_ephemeral_venv_raises_PY998_on_pip_install_failure(tmp_path: Path) -> None:
    pkg = tmp_path / "good-package"
    (pkg / "python").mkdir(parents=True)
    (pkg / "python" / "pyproject.toml").write_text('[project]\nname = "test"\nversion = "0.1"\n')

    call_count = [0]

    def fake_run(args: list[str], **kwargs: object) -> MagicMock:
        call_count[0] += 1
        if call_count[0] == 1:
            # First call: uv venv succeeds
            return MagicMock(returncode=0, stdout=b"", stderr=b"")
        # Second call: uv pip install fails
        return MagicMock(returncode=1, stdout=b"", stderr=b"resolution-impossible")

    with (
        patch("code_intake.venv.subprocess.run", side_effect=fake_run),
        pytest.raises(VenvCreationError) as exc_info,
        create_ephemeral_venv(pkg),
    ):
        pass
    msg = exc_info.value.message
    assert exc_info.value.code == "PY998"
    assert "install" in msg.lower() or "resolution-impossible" in msg
