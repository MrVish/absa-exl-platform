from __future__ import annotations

import json
from pathlib import Path

import pytest
from pipeline_factory.upstream_resolver import resolve_upstream_refs


def test_returns_empty_when_no_upstream(tmp_path: Path) -> None:
    assert resolve_upstream_refs(upstream_package=None, packages_root=tmp_path) == []


def test_returns_ref_for_existing_package(tmp_path: Path) -> None:
    pkg = tmp_path / "credit-risk-pd" / "1.0.0"
    pkg.mkdir(parents=True)
    manifest = {
        "digest": "f" * 64,
        "digest_algorithm": "SHA-256",
        "signature": "UNSIGNED",
        "payload": {"model_name": "credit-risk-pd", "version": "1.0.0"},
    }
    (pkg / "manifest.json").write_text(json.dumps(manifest))

    result = resolve_upstream_refs(
        upstream_package={"name": "credit-risk-pd", "version": "1.0.0"},
        packages_root=tmp_path,
    )
    assert result == [
        {
            "type": "package",
            "ref": "credit-risk-pd@1.0.0",
            "digest": "f" * 64,
        }
    ]


def test_raises_on_missing_manifest(tmp_path: Path) -> None:
    from pipeline_factory.upstream_resolver import GeneratorError

    with pytest.raises(GeneratorError, match="does not exist"):
        resolve_upstream_refs(
            upstream_package={"name": "credit-risk-pd", "version": "1.0.0"},
            packages_root=tmp_path,
        )


def test_raises_when_manifest_missing_digest(tmp_path: Path) -> None:
    from pipeline_factory.upstream_resolver import GeneratorError

    pkg = tmp_path / "credit-risk-pd" / "1.0.0"
    pkg.mkdir(parents=True)
    (pkg / "manifest.json").write_text(json.dumps({"foo": "bar"}))

    with pytest.raises(GeneratorError, match="digest"):
        resolve_upstream_refs(
            upstream_package={"name": "credit-risk-pd", "version": "1.0.0"},
            packages_root=tmp_path,
        )
