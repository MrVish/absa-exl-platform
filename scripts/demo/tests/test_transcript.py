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


def test_write_markdown_escapes_pipe_characters(tmp_path: Path) -> None:
    """Pipe characters in messages don't break the Markdown table."""
    t = Transcript(use_color=False)
    t.step("exl-prod-sim", "s3://bucket/key | manifest_uri")
    report_path = tmp_path / "t.md"
    t.write_markdown(report_path)
    contents = report_path.read_text(encoding="utf-8")
    assert "\\|" in contents, f"pipe not escaped; row text: {contents!r}"
    # And the row should still have exactly 5 column separators after the leading |
    table_lines = [
        line for line in contents.splitlines() if line.startswith("|") and "exl-prod-sim" in line
    ]
    assert len(table_lines) == 1
    # Count un-escaped pipes (escape sequence \| should not count as a separator)
    bare_pipes = table_lines[0].replace("\\|", "").count("|")
    assert bare_pipes == 6, f"expected 6 cell separators, got {bare_pipes} in {table_lines[0]!r}"


def test_step_and_step_failed_align_message_column(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The message text starts at the same column for both ok and FAIL lines."""
    t = Transcript(use_color=False)
    t.step("exl-prod-sim", "ok-message")
    t.step_failed("exl-prod-sim", "fail-message", exit_code=1)
    captured = capsys.readouterr()
    ok_line, fail_line, *_ = captured.out.strip().splitlines()
    ok_msg_col = ok_line.index("ok-message")
    fail_msg_col = fail_line.index("fail-message")
    assert ok_msg_col == fail_msg_col, (
        f"message column misaligned: ok={ok_msg_col} fail={fail_msg_col}\n"
        f"ok:   {ok_line!r}\nfail: {fail_line!r}"
    )
