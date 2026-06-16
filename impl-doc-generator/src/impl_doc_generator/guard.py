"""Raw-data / PII guard (ADR-0012 hard rule).

The LLM receives code + dev doc + schemas + metadata ONLY — never raw data rows
or PII. This guard inspects the content bundle and raises on the first thing that
looks like a data payload. It never silently drops a file: a violation means an
input was wrongly included and the run must stop.
"""

from __future__ import annotations

from .bundle import (
    KIND_CONFIG,
    KIND_DEV_DOC,
    KIND_PIR,
    KIND_PYTHON,
    KIND_SAS,
    KIND_TEST,
    ContextBundle,
)
from .docparse import DATA_EXTENSIONS
from .errors import RawDataGuardError

ALLOWED_KINDS = frozenset({KIND_PYTHON, KIND_SAS, KIND_TEST, KIND_DEV_DOC, KIND_CONFIG, KIND_PIR})

# Path segments that indicate a data directory.
DATA_PATH_SEGMENTS = frozenset({"data", "datasets", "dataset", "raw", "samples", "sample-data"})

# A single reviewable code/config file larger than this is suspicious (likely a
# data dump, not source code or schema).
MAX_FILE_BYTES = 2_000_000
# Development documents are legitimately large — a ~100-page dev doc extracts to
# hundreds of KB of text (bundle.py budgets what actually reaches the LLM). Give
# the dev-doc kind more headroom so a real document is never rejected for size.
DEV_DOC_MAX_BYTES = 16_000_000


def _max_bytes_for(kind: str) -> int:
    return DEV_DOC_MAX_BYTES if kind == KIND_DEV_DOC else MAX_FILE_BYTES


def _looks_like_tabular_data(text: str) -> bool:
    """A file whose lines are *overwhelmingly* wide + delimited is a data dump.

    Judged over the whole file (capped for performance), not just the head, so a
    real dev doc that merely *embeds* a few tables stays well under the threshold,
    while a CSV/TSV masquerading as a document trips it.
    """
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 20:
        return False
    sample = lines[:5000]
    for delim in (",", "\t", "|"):
        wide = sum(1 for ln in sample if ln.count(delim) >= 3)
        if wide >= 0.9 * len(sample):  # ~all lines are wide + delimited -> a table
            return True
    return False


def guard_bundle(bundle: ContextBundle) -> None:
    """Raise RawDataGuardError if the bundle's content looks like raw data / PII."""
    for cf in bundle.content_files:
        path_lower = cf.path.replace("\\", "/").lower()

        if cf.kind not in ALLOWED_KINDS:
            raise RawDataGuardError(
                f"content file {cf.path!r} has disallowed kind {cf.kind!r}",
                hint=f"only {sorted(ALLOWED_KINDS)} may be sent to the LLM",
            )

        for ext in DATA_EXTENSIONS:
            if path_lower.endswith(ext):
                raise RawDataGuardError(
                    f"content file {cf.path!r} has a data extension ({ext})",
                    hint="data files must never be sent to the LLM (ADR-0012)",
                )

        segments = set(path_lower.split("/"))
        if segments & DATA_PATH_SEGMENTS:
            raise RawDataGuardError(
                f"content file {cf.path!r} sits under a data directory",
                hint="move it or exclude it; the LLM receives code + docs only",
            )

        cap = _max_bytes_for(cf.kind)
        if len(cf.text.encode("utf-8")) > cap:
            raise RawDataGuardError(
                f"content file {cf.path!r} exceeds {cap} bytes",
                hint="oversized reviewable files are likely data dumps",
            )

        # Tabular heuristic on prose/config only — code legitimately has commas.
        if cf.kind in (KIND_DEV_DOC, KIND_CONFIG, KIND_PIR) and _looks_like_tabular_data(cf.text):
            raise RawDataGuardError(
                f"content file {cf.path!r} looks like tabular data",
                hint="the dev doc / config appears to embed a data table",
            )
