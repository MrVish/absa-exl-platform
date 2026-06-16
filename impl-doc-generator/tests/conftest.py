"""Shared fixtures: paths to the committed worked example."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DIR = REPO_ROOT / "packages" / "credit-risk-pd" / "1.0.0"
PIPELINE_MANIFEST = REPO_ROOT / "pipelines" / "credit-risk-pd" / "1.0.0" / "manifest.json"
DEV_DOC = REPO_ROOT / "impl-doc-generator" / "examples" / "dev-doc-credit-risk-pd.md"


@pytest.fixture
def package_dir() -> Path:
    return PACKAGE_DIR


@pytest.fixture
def pipeline_manifest() -> Path:
    return PIPELINE_MANIFEST


@pytest.fixture
def dev_doc() -> Path:
    return DEV_DOC
