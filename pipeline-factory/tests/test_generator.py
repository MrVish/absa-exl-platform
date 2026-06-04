from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError
from pipeline_factory.generator import PipelineDriftError, generate, load_config


def test_load_config_validates(sample_config: Path) -> None:
    config = load_config(sample_config)
    assert config["model_name"] == "credit-risk-pd"


def test_load_config_rejects_bad_tier(sample_config: Path, tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(sample_config.read_text().replace("standard", "realtime"), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_config(bad)


def test_generate_writes_four_artifacts(sample_config: Path, tmp_path: Path) -> None:
    out_dir = generate(sample_config, outputs_root=tmp_path / "pipelines")
    assert out_dir == tmp_path / "pipelines" / "credit-risk-pd" / "1.0.0"
    assert (out_dir / "statemachine.json").exists()
    assert (out_dir / "registration.json").exists()
    assert (out_dir / "manifest.json").exists()
    assert (out_dir / "terraform" / "main.tf").exists()


def test_generated_registration_matches_create_request_shape(
    sample_config: Path, tmp_path: Path
) -> None:
    out_dir = generate(sample_config, outputs_root=tmp_path / "pipelines")
    body = json.loads((out_dir / "registration.json").read_text())
    assert body["model_name"] == "credit-risk-pd"
    assert body["sas_code_version"] == "sas-2026.04.1"
    assert body["inference_code_version"] == "py-2026.04.1"
    for forbidden in ("approval_status", "created_at", "updated_at", "rev", "last_scored_at"):
        assert forbidden not in body


def test_generated_manifest_is_unsigned(sample_config: Path, tmp_path: Path) -> None:
    out_dir = generate(sample_config, outputs_root=tmp_path / "pipelines")
    envelope = json.loads((out_dir / "manifest.json").read_text())
    assert envelope["signature"] == "UNSIGNED"
    assert envelope["subject_type"] == "pipeline"
    assert envelope["subject_ref"] == "pipelines/credit-risk-pd/1.0.0/"


def test_regenerate_without_force_raises_on_drift(sample_config: Path, tmp_path: Path) -> None:
    out_dir = generate(sample_config, outputs_root=tmp_path / "pipelines")
    (out_dir / "statemachine.json").write_text("{}", encoding="utf-8")
    with pytest.raises(PipelineDriftError):
        generate(sample_config, outputs_root=tmp_path / "pipelines")


def test_regenerate_with_force_overwrites(sample_config: Path, tmp_path: Path) -> None:
    out_dir = generate(sample_config, outputs_root=tmp_path / "pipelines")
    (out_dir / "statemachine.json").write_text("{}", encoding="utf-8")
    generate(sample_config, outputs_root=tmp_path / "pipelines", force=True)
    content = (out_dir / "statemachine.json").read_text()
    assert "StartAt" in content
