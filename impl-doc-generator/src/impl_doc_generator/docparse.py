"""Development-document ingestion: PDF / DOCX / Markdown / text -> structured text.

ABSA's model development document can be ~100 pages and is typically a PDF or
Word file, not markdown. This module extracts text, captures the page count, and
parses the document into sections (heading-aware) so downstream code can:

* show a table of contents as a grounded fact,
* budget the text sent to the LLM section-by-section (a 100-page doc rarely fits
  a single context window, and sending it whole is wasteful), and
* keep the most relevant front-matter + methodology when budgeting.

PDF/DOCX support is via optional extras (`pdf` -> pypdf, `docx` -> python-docx),
lazy-imported so the package installs + tests without them.
"""

from __future__ import annotations

import importlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import BundleError, RawDataGuardError

MARKDOWN_EXTS = frozenset({".md", ".markdown"})
TEXT_EXTS = frozenset({".txt", ".rst", ".text"})
PDF_EXTS = frozenset({".pdf"})
DOCX_EXTS = frozenset({".docx"})

# Extensions that indicate a data payload, never a document. A dev doc with one
# of these is rejected at ingestion by the data-minimisation guard (ADR-0012);
# guard.py reuses this set for the reviewable content files too.
DATA_EXTENSIONS = frozenset(
    {
        ".csv",
        ".tsv",
        ".psv",
        ".parquet",
        ".feather",
        ".orc",
        ".avro",
        ".xls",
        ".xlsx",
        ".xlsm",
        ".pkl",
        ".pickle",
        ".npy",
        ".npz",
        ".h5",
        ".hdf5",
        ".sas7bdat",
        ".sav",
        ".dta",
        ".db",
        ".sqlite",
    }
)

_MD_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
# Numbered ("3.2 Methodology") or short ALL-CAPS / Title-Case lines used as
# headings in extracted PDF/Word text.
_NUM_HEADING = re.compile(r"^(\d+(?:\.\d+){0,3})\s+(\S.{0,80})$")


@dataclass(frozen=True)
class DevDocSection:
    title: str
    level: int
    text: str

    def char_count(self) -> int:
        return len(self.text)


@dataclass
class DevDoc:
    source_format: str  # md | txt | pdf | docx
    full_text: str
    sections: list[DevDocSection] = field(default_factory=list)
    page_count: int | None = None

    @property
    def char_count(self) -> int:
        return len(self.full_text)


def _parse_markdown_sections(text: str) -> list[DevDocSection]:
    sections: list[DevDocSection] = []
    title: str = "Preamble"
    level: int = 0
    buf: list[str] = []
    for line in text.splitlines():
        m = _MD_HEADING.match(line)
        if m:
            if buf or sections:
                sections.append(
                    DevDocSection(title=title, level=level, text="\n".join(buf).strip())
                )
            title, level, buf = m.group(2).strip(), len(m.group(1)), []
        else:
            buf.append(line)
    sections.append(DevDocSection(title=title, level=level, text="\n".join(buf).strip()))
    return [s for s in sections if s.text or s.title != "Preamble"]


def _parse_generic_sections(text: str) -> list[DevDocSection]:
    """Heuristic heading detection for extracted PDF / Word text."""
    sections: list[DevDocSection] = []
    title: str = "Document"
    level: int = 0
    buf: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        m = _NUM_HEADING.match(line)
        is_caps = (
            bool(line)
            and 3 <= len(line) <= 80
            and line == line.upper()
            and any(c.isalpha() for c in line)
        )
        if m or is_caps:
            if buf or len(sections) > 0:
                sections.append(
                    DevDocSection(title=title, level=level, text="\n".join(buf).strip())
                )
            if m:
                title = f"{m.group(1)} {m.group(2).strip()}"
                level = m.group(1).count(".") + 1
            else:
                title, level = line, 1
            buf = []
        else:
            buf.append(raw)
    sections.append(DevDocSection(title=title, level=level, text="\n".join(buf).strip()))
    return [s for s in sections if s.text or s.title != "Document"]


def _extract_pdf(path: Path) -> tuple[str, int]:
    try:
        pypdf = importlib.import_module("pypdf")
    except ImportError as e:
        raise BundleError(
            "pypdf not installed; cannot read a PDF dev doc",
            hint="install the 'pdf' extra, or supply the dev doc as markdown/text",
        ) from e
    reader: Any = pypdf.PdfReader(str(path))
    pages: list[str] = [(p.extract_text() or "") for p in reader.pages]
    return "\n\n".join(pages), len(pages)


def _extract_docx(path: Path) -> str:
    try:
        docx = importlib.import_module("docx")
    except ImportError as e:
        raise BundleError(
            "python-docx not installed; cannot read a .docx dev doc",
            hint="install the 'docx' extra or supply markdown/text",
        ) from e
    document: Any = docx.Document(str(path))
    lines: list[str] = []
    for para in document.paragraphs:
        style = getattr(para.style, "name", "") or ""
        if style.startswith("Heading") and para.text.strip():
            # Re-emit as a markdown heading so the markdown parser captures it.
            try:
                level = int(style.split()[-1])
            except ValueError:
                level = 1
            lines.append(f"{'#' * min(level, 6)} {para.text.strip()}")
        else:
            lines.append(para.text)
    return "\n".join(lines)


def load_dev_doc(path: Path) -> DevDoc:
    """Load + structure a development document by extension."""
    if not path.is_file():
        raise BundleError(f"dev doc not found: {path}")
    ext = path.suffix.lower()

    if ext in DATA_EXTENSIONS:
        raise RawDataGuardError(
            f"dev doc {path.name!r} is a data file ({ext})",
            hint="the LLM receives code + docs only, never raw data (ADR-0012)",
        )

    if ext in MARKDOWN_EXTS:
        text = path.read_text(encoding="utf-8")
        return DevDoc("md", text, _parse_markdown_sections(text))
    if ext in TEXT_EXTS:
        text = path.read_text(encoding="utf-8")
        return DevDoc("txt", text, _parse_generic_sections(text))
    if ext in PDF_EXTS:
        text, pages = _extract_pdf(path)
        return DevDoc("pdf", text, _parse_generic_sections(text), page_count=pages)
    if ext in DOCX_EXTS:
        text = _extract_docx(path)
        # python-docx emits markdown headings, so use the markdown parser.
        return DevDoc("docx", text, _parse_markdown_sections(text))

    raise BundleError(
        f"unsupported dev-doc format: {ext}",
        hint="supported: .md/.markdown, .txt/.rst, .pdf (extra: pdf), .docx (extra: docx)",
    )


@dataclass
class BudgetResult:
    text: str
    included_sections: int
    omitted_sections: int
    omitted_chars: int
    truncated: bool


def budget_dev_doc(doc: DevDoc, max_chars: int) -> BudgetResult:
    """Fit the dev doc into ``max_chars`` by including whole sections in order.

    Front-matter + methodology (which lead a dev doc) are kept; trailing sections
    that don't fit are summarised by heading with an explicit omission marker, so
    the LLM never silently receives a truncated document.
    """
    if doc.char_count <= max_chars:
        return BudgetResult(doc.full_text, len(doc.sections), 0, 0, truncated=False)

    parts: list[str] = []
    used = 0
    included = 0
    omitted_titles: list[str] = []
    omitted_chars = 0
    for sec in doc.sections:
        block = f"{'#' * max(sec.level, 1)} {sec.title}\n{sec.text}".strip()
        if used + len(block) <= max_chars:
            parts.append(block)
            used += len(block)
            included += 1
        else:
            omitted_titles.append(sec.title)
            omitted_chars += sec.char_count()

    if omitted_titles:
        toc = "\n".join(f"  - {t}" for t in omitted_titles)
        parts.append(
            f"\n[TRUNCATED FOR LLM CONTEXT — {len(omitted_titles)} later section(s) "
            f"(~{omitted_chars} chars) omitted; titles:\n{toc}\n"
            f"See the full source dev doc for these.]"
        )
    return BudgetResult(
        "\n\n".join(parts), included, len(omitted_titles), omitted_chars, truncated=True
    )
