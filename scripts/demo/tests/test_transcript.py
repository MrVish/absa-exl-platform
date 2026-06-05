from __future__ import annotations

import re
from pathlib import Path

import pytest

from demo.transcript import Transcript


def test_step_writes_prefixed_line(capsys: pytest.CaptureFixture[str]) -> None:
    """Transcript.step() writes [account-name] prefixed message to stdout."""
    t = Transcript(use_color=False)
    t.step("exl-prod-sim", "code-intake validate")
    captured = capsys.readouterr()
    assert "[exl-prod-sim]" in captured.out
    assert "code-intake validate" in captured.out


def test_step_with_duration(capsys: pytest.CaptureFixture[str]) -> None:
    """Transcript.step() can record a duration that appears in output."""
    t = Transcript(use_color=False)
    t.step("absa-sim", "verify-offline", duration_s=1.23)
    captured = capsys.readouterr()
    assert "1.23" in captured.out or "1.2" in captured.out


def test_demo_prefix_for_orchestrator_messages(capsys: pytest.CaptureFixture[str]) -> None:
    """Messages from the orchestrator itself use [demo] prefix."""
    t = Transcript(use_color=False)
    t.demo("starting up")
    captured = capsys.readouterr()
    assert "[demo]" in captured.out
    assert "starting up" in captured.out


def test_write_markdown_produces_report(tmp_path: Path) -> None:
    """Transcript.write_markdown() writes a complete report."""
    t = Transcript(use_color=False)
    t.demo("up started")
    t.step("exl-prod-sim", "localstack: kms ok", duration_s=3.2)
    t.step("absa-sim", "verify-offline", duration_s=0.8)
    t.demo("DEMO PASSED")
    report_path = tmp_path / "transcript.md"
    t.write_markdown(report_path)
    contents = report_path.read_text(encoding="utf-8")
    assert "[demo]" in contents
    assert "[exl-prod-sim]" in contents
    assert "[absa-sim]" in contents
    assert "DEMO PASSED" in contents


def test_no_color_strips_ansi(capsys: pytest.CaptureFixture[str]) -> None:
    """use_color=False produces no ANSI escape codes in stdout."""
    t = Transcript(use_color=False)
    t.step("exl-prod-sim", "message")
    captured = capsys.readouterr()
    assert not re.search(r"\x1b\[\d+m", captured.out)


def test_step_failed_writes_red_prefix(capsys: pytest.CaptureFixture[str]) -> None:
    """Failures use a distinct visual marker."""
    t = Transcript(use_color=False)
    t.step_failed("exl-prod-sim", "code-intake validate", exit_code=1)
    captured = capsys.readouterr()
    assert "FAIL" in captured.out or "✗" in captured.out
    assert "code-intake validate" in captured.out
