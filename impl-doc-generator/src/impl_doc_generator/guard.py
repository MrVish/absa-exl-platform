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
from .errors import RawDataGuardError

ALLOWED_KINDS = frozenset({KIND_PYTHON, KIND_SAS, KIND_TEST, KIND_DEV_DOC, KIND_CONFIG, KIND_PIR})

# Extensions that indicate a data payload, never code/docs/schema.
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

# Path segments that indicate a data directory.
DATA_PATH_SEGMENTS = frozenset({"data", "datasets", "dataset", "raw", "samples", "sample-data"})

# A single reviewable file larger than this is suspicious (likely a data dump,
# not source code or documentation).
MAX_FILE_BYTES = 2_000_000


def _looks_like_tabular_data(text: str) -> bool:
    """Heuristic: many lines with a consistent, high delimiter count = a table."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 20:
        return False
    sample = lines[:200]
    for delim in (",", "\t", "|"):
        counts = [ln.count(delim) for ln in sample]
        wide = [c for c in counts if c >= 3]
        if len(wide) >= 0.9 * len(sample):  # ~all sampled lines are wide + delimited
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

        if len(cf.text.encode("utf-8")) > MAX_FILE_BYTES:
            raise RawDataGuardError(
                f"content file {cf.path!r} exceeds {MAX_FILE_BYTES} bytes",
                hint="oversized reviewable files are likely data dumps",
            )

        # Tabular heuristic on prose/config only — code legitimately has commas.
        if cf.kind in (KIND_DEV_DOC, KIND_CONFIG, KIND_PIR) and _looks_like_tabular_data(cf.text):
            raise RawDataGuardError(
                f"content file {cf.path!r} looks like tabular data",
                hint="the dev doc / config appears to embed a data table",
            )
