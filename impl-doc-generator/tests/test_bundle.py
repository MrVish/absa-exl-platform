from __future__ import annotations

from pathlib import Path

import pytest
from impl_doc_generator.bundle import KIND_PYTHON, KIND_SAS, build_context_bundle
from impl_doc_generator.errors import BundleError


def test_build_bundle_from_worked_example(
    package_dir: Path, pipeline_manifest: Path, dev_doc: Path
) -> None:
    b = build_context_bundle(package_dir, pipeline_manifest=pipeline_manifest, dev_doc=dev_doc)
    assert b.model_name == "credit-risk-pd"
    assert b.model_version == "1.0.0"
    assert b.tier == "standard"
    assert b.package_digest and len(b.package_digest) == 64
    assert b.pipeline_digest and len(b.pipeline_digest) == 64
    # PIR facts came through
    assert {i["name"] for i in b.pir_inputs} == {"income_band", "tenure_months", "delinquencies"}
    assert {o["name"] for o in b.pir_outputs} == {"pd_score", "risk_band"}
    # upstream ref chains package -> pipeline
    assert any(r.get("digest") == b.package_digest for r in b.upstream_refs)
    assert b.dev_doc_present


def test_bundle_content_includes_code_not_tests(package_dir: Path, dev_doc: Path) -> None:
    b = build_context_bundle(package_dir, dev_doc=dev_doc)
    kinds = {cf.kind for cf in b.content_files}
    assert KIND_PYTHON in kinds and KIND_SAS in kinds
    paths = {cf.path.replace("\\", "/") for cf in b.content_files}
    assert "python/score.py" in paths
    assert "sas/score.sas" in paths
    # test files are inventoried but their content is not sent for drafting
    assert "python/tests/test_score.py" not in paths
    assert dev_doc.name in paths


def test_bundle_without_pipeline_is_pending(package_dir: Path) -> None:
    b = build_context_bundle(package_dir)
    assert b.pipeline_digest is None
    assert "pending" in b.tier.lower()


def test_missing_package_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(BundleError):
        build_context_bundle(tmp_path / "nope")
