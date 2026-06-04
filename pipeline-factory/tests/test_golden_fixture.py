from __future__ import annotations

from pathlib import Path

from pipeline_factory.generator import generate

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_CONFIG = (
    REPO_ROOT / "pipeline-factory" / "configs" / "credit-risk-pd" / "1.0.0" / "model_config.yaml"
)
EXPECTED_DIR = REPO_ROOT / "pipelines" / "credit-risk-pd" / "1.0.0"


def test_fixture_regenerate_is_byte_stable(tmp_path: Path) -> None:
    out_root = tmp_path / "pipelines"
    # Pre-seed the tmp output dir with the committed manifest so the idempotent
    # timestamp logic from T9 reuses the same generated_at / signed_at values.
    # Without this, the re-rendered manifest would carry fresh timestamps and
    # the comparison below would fail on those two fields.
    target_manifest_dir = out_root / "credit-risk-pd" / "1.0.0"
    target_manifest_dir.mkdir(parents=True, exist_ok=True)
    committed_manifest = EXPECTED_DIR / "manifest.json"
    (target_manifest_dir / "manifest.json").write_text(
        committed_manifest.read_text(encoding="utf-8"), encoding="utf-8"
    )

    out_dir = generate(FIXTURE_CONFIG, outputs_root=out_root, force=True)
    for rel in (
        "statemachine.json",
        "registration.json",
        "manifest.json",
        "terraform/main.tf",
    ):
        regenerated = (out_dir / rel).read_text(encoding="utf-8")
        expected = (EXPECTED_DIR / rel).read_text(encoding="utf-8")
        assert regenerated == expected, (
            f"drift in {rel}: re-generating from the committed config produced different output. "
            "Re-run `uv run generate-pipeline generate "
            "--config pipeline-factory/configs/credit-risk-pd/1.0.0/model_config.yaml --force` "
            "and commit, or investigate the divergence."
        )
