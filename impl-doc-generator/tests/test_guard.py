from __future__ import annotations

from pathlib import Path

import pytest
from impl_doc_generator.bundle import (
    KIND_DEV_DOC,
    KIND_PYTHON,
    ContentFile,
    ContextBundle,
    build_context_bundle,
)
from impl_doc_generator.errors import RawDataGuardError
from impl_doc_generator.guard import guard_bundle


def _bundle(*content: ContentFile) -> ContextBundle:
    return ContextBundle(
        model_name="m",
        model_version="1.0.0",
        package_digest="x",
        pipeline_digest=None,
        tier="standard",
        content_files=list(content),
    )


def test_clean_worked_example_passes(package_dir: Path, dev_doc: Path) -> None:
    guard_bundle(build_context_bundle(package_dir, dev_doc=dev_doc))  # no raise


def test_data_extension_rejected() -> None:
    b = _bundle(ContentFile(path="features.csv", kind=KIND_PYTHON, text="a,b,c\n1,2,3\n"))
    with pytest.raises(RawDataGuardError):
        guard_bundle(b)


def test_data_directory_rejected() -> None:
    b = _bundle(ContentFile(path="data/score.py", kind=KIND_PYTHON, text="x = 1\n"))
    with pytest.raises(RawDataGuardError):
        guard_bundle(b)


def test_oversized_file_rejected() -> None:
    b = _bundle(ContentFile(path="score.py", kind=KIND_PYTHON, text="x = 1\n" * 400_000))
    with pytest.raises(RawDataGuardError):
        guard_bundle(b)


def test_tabular_dev_doc_rejected() -> None:
    table = "id,name,income,tenure\n" + "\n".join(f"{i},n{i},5,12" for i in range(50))
    b = _bundle(ContentFile(path="dev-doc.md", kind=KIND_DEV_DOC, text=table))
    with pytest.raises(RawDataGuardError):
        guard_bundle(b)


def test_code_with_commas_not_flagged() -> None:
    code = "\n".join(f"def f{i}(a, b, c, d): return a + b" for i in range(40))
    b = _bundle(ContentFile(path="score.py", kind=KIND_PYTHON, text=code))
    guard_bundle(b)  # commas in code must not trip the tabular heuristic
