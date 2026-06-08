from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from code_intake.checkers.base import CheckResult, Finding
from code_intake.manifest import build_package_envelope, build_package_payload
from platform_contracts.canonical import canonical_json
from platform_contracts.loader import validate as validate_contract

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_results() -> list[CheckResult]:
    return [
        CheckResult(checker="static_python", passed=True, findings=[]),
        CheckResult(checker="static_sas", passed=True, findings=[]),
        CheckResult(checker="schema", passed=True, findings=[]),
        CheckResult(
            checker="tests",
            passed=False,
            findings=[Finding(severity="error", code="TST002", message="boom")],
        ),
        CheckResult(checker="pir", passed=True, findings=[]),
    ]


def test_build_payload_passes_schema(sample_results):
    payload = build_package_payload(
        package_path=FIXTURES / "valid_package",
        results=sample_results,
        generated_at="2026-06-04T00:00:00+00:00",
    )
    validate_contract("package-manifest-payload", payload)


def test_build_payload_records_validation_summary(sample_results):
    payload = build_package_payload(
        package_path=FIXTURES / "valid_package",
        results=sample_results,
        generated_at="2026-06-04T00:00:00+00:00",
    )
    summary = payload["validation_summary"]
    by_name = {c["name"]: c for c in summary["checks"]}
    assert by_name["static_python"]["passed"] is True
    assert by_name["tests"]["passed"] is False
    assert by_name["tests"]["finding_count"] == 1
    assert "TST002" in by_name["tests"]["codes"]


def test_build_payload_computes_file_hashes_from_disk(sample_results):
    payload = build_package_payload(
        package_path=FIXTURES / "valid_package",
        results=sample_results,
        generated_at="2026-06-04T00:00:00+00:00",
    )
    layout = payload["package_layout"]
    # python_files[0] is python/score.py — verify its hash matches the
    # CRLF-normalized on-disk bytes. The manifest builder normalizes line
    # endings before hashing so the digest is stable across Windows
    # (CRLF) and Linux (LF) checkouts; the test mirrors that normalization.
    score_path = FIXTURES / "valid_package" / "python" / "score.py"
    expected = hashlib.sha256(score_path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    python_files = layout["python_files"]
    assert any(f["sha256"] == expected for f in python_files), (
        f"score.py hash {expected} not found in {[f['sha256'] for f in python_files]}"
    )


def test_build_envelope_wraps_with_unsigned_sentinel(sample_results):
    payload = build_package_payload(
        package_path=FIXTURES / "valid_package",
        results=sample_results,
        generated_at="2026-06-04T00:00:00+00:00",
    )
    envelope = build_package_envelope(
        payload=payload,
        subject_ref="packages/valid-package/1.0.0/",
        signed_at="2026-06-04T00:00:00+00:00",
    )
    assert envelope["signature"] == "UNSIGNED"
    assert envelope["subject_type"] == "package"
    assert envelope["digest"] == hashlib.sha256(canonical_json(payload)).hexdigest()


def test_build_envelope_preserves_existing_timestamps(tmp_path, sample_results):
    """Re-rendering reads the existing manifest's generated_at/signed_at
    so the drift gate is byte-stable across re-runs."""
    payload_a = build_package_payload(
        package_path=FIXTURES / "valid_package",
        results=sample_results,
        generated_at="2026-06-04T00:00:00+00:00",
    )
    envelope_a = build_package_envelope(
        payload=payload_a,
        subject_ref="packages/valid-package/1.0.0/",
        signed_at="2026-06-04T00:00:00+00:00",
    )
    # Same explicit timestamps → byte-identical canonical bytes
    payload_b = build_package_payload(
        package_path=FIXTURES / "valid_package",
        results=sample_results,
        generated_at=payload_a["generated_at"],
    )
    envelope_b = build_package_envelope(
        payload=payload_b,
        subject_ref="packages/valid-package/1.0.0/",
        signed_at=envelope_a["signed_at"],
    )
    assert canonical_json(envelope_a) == canonical_json(envelope_b)
