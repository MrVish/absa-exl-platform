from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner
from impl_doc_generator.cli import main

FIXED_TS = "2026-06-16T00:00:00+00:00"


def test_cli_end_to_end(
    package_dir: Path, pipeline_manifest: Path, dev_doc: Path, tmp_path: Path
) -> None:
    out = tmp_path / "implementation.md"
    r = CliRunner().invoke(
        main,
        [
            "--package",
            str(package_dir),
            "--pipeline",
            str(pipeline_manifest),
            "--dev-doc",
            str(dev_doc),
            "--provider",
            "offline",
            "--out",
            str(out),
            "--generated-at",
            FIXED_TS,
        ],
    )
    assert r.exit_code == 0, r.output
    assert out.is_file()
    assert "implementation_doc_ref (sha256):" in r.output
    assert "# Implementation Document — credit-risk-pd 1.0.0" in out.read_text(encoding="utf-8")


def test_cli_is_reproducible(
    package_dir: Path, pipeline_manifest: Path, dev_doc: Path, tmp_path: Path
) -> None:
    def run(p: Path) -> str:
        CliRunner().invoke(
            main,
            [
                "--package",
                str(package_dir),
                "--pipeline",
                str(pipeline_manifest),
                "--dev-doc",
                str(dev_doc),
                "--out",
                str(p),
                "--generated-at",
                FIXED_TS,
            ],
        )
        return p.read_text(encoding="utf-8")

    assert run(tmp_path / "a.md") == run(tmp_path / "b.md")


def test_cli_guard_blocks_data_file(package_dir: Path, tmp_path: Path) -> None:
    # a dev doc that is actually a CSV data dump must be rejected
    bad = tmp_path / "rows.csv"
    bad.write_text(
        "id,income,tenure\n" + "\n".join(f"{i},5,12" for i in range(40)), encoding="utf-8"
    )
    r = CliRunner().invoke(
        main,
        [
            "--package",
            str(package_dir),
            "--dev-doc",
            str(bad),
            "--out",
            str(tmp_path / "x.md"),
            "--generated-at",
            FIXED_TS,
        ],
    )
    assert r.exit_code == 1
    assert "IDG020" in r.output
