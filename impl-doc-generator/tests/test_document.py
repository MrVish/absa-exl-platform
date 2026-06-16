from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from impl_doc_generator.bundle import build_context_bundle
from impl_doc_generator.document import SECTION_SPECS, render_document
from impl_doc_generator.errors import ProviderError
from impl_doc_generator.providers import OfflineProvider, get_provider

FIXED_TS = "2026-06-16T00:00:00+00:00"


def test_get_provider_offline() -> None:
    assert isinstance(get_provider("offline"), OfflineProvider)


def test_get_provider_unknown_raises() -> None:
    with pytest.raises(ProviderError):
        get_provider("gpt-from-nowhere")


def test_offline_provider_drafts_all_sections() -> None:
    sections = [(sid, instr) for sid, _t, instr in SECTION_SPECS]
    out = OfflineProvider().draft(system="s", context="c", sections=sections)
    assert set(out) == {sid for sid, _t, _i in SECTION_SPECS}
    assert all(v for v in out.values())


def test_render_contains_facts_and_sections(
    package_dir: Path, pipeline_manifest: Path, dev_doc: Path
) -> None:
    b = build_context_bundle(package_dir, pipeline_manifest=pipeline_manifest, dev_doc=dev_doc)
    doc = render_document(b, OfflineProvider(), generated_at=FIXED_TS)
    md = doc.markdown
    # title + provenance + every section title present
    assert "# Implementation Document — credit-risk-pd 1.0.0" in md
    assert "## Provenance" in md
    for _sid, title, _instr in SECTION_SPECS:
        assert f"## {title}" in md
    # grounded facts present verbatim
    assert b.package_digest in md
    assert "income_band" in md  # PIR input fact
    assert "RSASSA_PKCS1_V1_5_SHA_256" in md  # signing fact
    assert "standard" in md  # tier fact
    # draft status + pending review by default
    assert "Status: DRAFT" in md
    assert "PENDING REVIEW" in md


def test_digest_deterministic_and_sensitive(
    package_dir: Path, pipeline_manifest: Path, dev_doc: Path
) -> None:
    b = build_context_bundle(package_dir, pipeline_manifest=pipeline_manifest, dev_doc=dev_doc)
    d1 = render_document(b, OfflineProvider(), generated_at=FIXED_TS)
    d2 = render_document(b, OfflineProvider(), generated_at=FIXED_TS)
    assert d1.doc_digest == d2.doc_digest and len(d1.doc_digest) == 64
    # changing a grounded fact changes the digest
    b2 = replace(b, model_version="2.0.0")
    d3 = render_document(b2, OfflineProvider(), generated_at=FIXED_TS)
    assert d3.doc_digest != d1.doc_digest


def test_approver_sets_status(package_dir: Path, dev_doc: Path) -> None:
    b = build_context_bundle(package_dir, dev_doc=dev_doc)
    doc = render_document(
        b, OfflineProvider(), generated_at=FIXED_TS, approver="Jane Risk", status="APPROVED"
    )
    assert "Status: APPROVED" in doc.markdown
    assert "Jane Risk" in doc.markdown
    assert doc.provenance["approver"] == "Jane Risk"
