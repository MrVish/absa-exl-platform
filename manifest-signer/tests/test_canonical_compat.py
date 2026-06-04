"""Guards the byte-for-byte contract between Sprint 2's manifest builder and
Sprint 3's signer/verifier. If this test fails, the envelope contract has
silently drifted and previously-signed manifests will no longer verify.
"""

from __future__ import annotations

import pytest
from pipeline_factory.manifest import build_envelope, build_payload
from platform_contracts.canonical import canonical_json


@pytest.fixture
def sample_payload() -> dict:
    return build_payload(
        model_name="credit-risk-pd",
        version="1.0.0",
        tier="standard-batch",
        artifact_hashes={"model": "abc123", "config": "def456"},
        generated_at="2026-05-26T00:00:00+00:00",
    )


def test_canonical_json_form_is_pretty_printed_sort_keys_utf8(sample_payload):
    out = canonical_json(sample_payload)
    assert out.endswith(b"\n")
    # First two keys in sorted order
    assert out.startswith(b'{\n  "artifact_hashes":')


def test_pipeline_factory_envelope_uses_canonical_json_for_digest(sample_payload):
    """build_envelope sets envelope.digest = sha256(canonical_json(payload)).
    If either side drifts, signatures stop verifying."""
    import hashlib

    envelope = build_envelope(
        payload=sample_payload,
        subject_ref="pipeline:credit-risk-pd:1.0.0",
        signed_at="2026-05-26T00:00:00+00:00",
    )
    expected_digest = hashlib.sha256(canonical_json(sample_payload)).hexdigest()
    assert envelope["digest"] == expected_digest
    assert envelope["digest_algorithm"] == "SHA-256"


def test_canonical_json_is_stable_across_dict_insertion_order(sample_payload):
    reordered = dict(reversed(list(sample_payload.items())))
    assert canonical_json(sample_payload) == canonical_json(reordered)
