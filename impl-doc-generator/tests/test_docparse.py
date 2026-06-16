from __future__ import annotations

from pathlib import Path

import pytest
from impl_doc_generator.docparse import (
    DevDoc,
    DevDocSection,
    budget_dev_doc,
    load_dev_doc,
)
from impl_doc_generator.errors import BundleError


def test_markdown_is_split_into_sections(tmp_path: Path) -> None:
    p = tmp_path / "dev.md"
    p.write_text(
        "# Title\nintro\n## Methodology\nlogreg\n## Inputs\nthree features\n", encoding="utf-8"
    )
    doc = load_dev_doc(p)
    assert doc.source_format == "md"
    assert doc.page_count is None
    titles = [s.title for s in doc.sections]
    assert "Methodology" in titles and "Inputs" in titles


def test_text_numbered_headings_detected(tmp_path: Path) -> None:
    p = tmp_path / "dev.txt"
    p.write_text(
        "Intro paragraph.\n1 Overview\nbody\n2.1 Methodology\nmore body\n", encoding="utf-8"
    )
    doc = load_dev_doc(p)
    assert doc.source_format == "txt"
    titles = [s.title for s in doc.sections]
    assert any("Overview" in t for t in titles)
    assert any("Methodology" in t for t in titles)


def test_unsupported_extension_raises(tmp_path: Path) -> None:
    p = tmp_path / "dev.rtfx"
    p.write_text("hello", encoding="utf-8")
    with pytest.raises(BundleError):
        load_dev_doc(p)


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(BundleError):
        load_dev_doc(tmp_path / "nope.md")


def test_budget_keeps_small_doc_whole() -> None:
    doc = DevDoc("md", "x" * 100, [DevDocSection("S", 1, "x" * 100)])
    res = budget_dev_doc(doc, max_chars=10_000)
    assert res.truncated is False
    assert res.omitted_sections == 0
    assert res.text == doc.full_text


def test_budget_truncates_large_doc_with_marker() -> None:
    sections = [DevDocSection(f"Section {i}", 1, "y" * 1000) for i in range(10)]
    doc = DevDoc("pdf", full_text="y" * 10_000, sections=sections, page_count=100)
    res = budget_dev_doc(doc, max_chars=2_500)
    assert res.truncated is True
    assert res.omitted_sections > 0
    assert res.included_sections >= 1
    assert "TRUNCATED FOR LLM CONTEXT" in res.text
    # the omitted section titles are listed so nothing vanishes silently
    assert "Section 9" in res.text


def test_docx_headings_become_sections(tmp_path: Path) -> None:
    docx = pytest.importorskip("docx")
    document = docx.Document()
    document.add_heading("Overview", level=1)
    document.add_paragraph("intro text")
    document.add_heading("Methodology", level=1)
    document.add_paragraph("a logistic regression scorecard")
    p = tmp_path / "dev.docx"
    document.save(str(p))

    doc = load_dev_doc(p)
    assert doc.source_format == "docx"
    titles = [s.title for s in doc.sections]
    assert "Overview" in titles and "Methodology" in titles
