from __future__ import annotations

from pathlib import Path

import pytest
from code_intake.errors import PackageConfigError
from code_intake.package_config import load_package_config

FIXTURES = Path(__file__).parent / "fixtures"


def test_loads_valid_package_config():
    cfg = load_package_config(FIXTURES / "valid_package" / "model_config.yaml")
    assert cfg["model_name"] == "valid-package"
    assert cfg["version"] == "1.0.0"


def test_rejects_invalid_schema():
    with pytest.raises(PackageConfigError, match="schema"):
        load_package_config(FIXTURES / "broken_schema" / "model_config.yaml")


def test_rejects_missing_file(tmp_path):
    with pytest.raises(PackageConfigError, match="missing"):
        load_package_config(tmp_path / "model_config.yaml")
