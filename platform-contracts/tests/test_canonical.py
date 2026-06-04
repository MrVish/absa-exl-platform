from __future__ import annotations

from platform_contracts.canonical import canonical_json


def test_canonical_json_returns_bytes_with_trailing_newline():
    out = canonical_json({"a": 1})
    assert isinstance(out, bytes)
    assert out.endswith(b"\n")


def test_canonical_json_sorts_keys():
    a = canonical_json({"b": 2, "a": 1})
    b = canonical_json({"a": 1, "b": 2})
    assert a == b


def test_canonical_json_uses_two_space_indent():
    out = canonical_json({"a": 1, "b": [2, 3]})
    assert out == b'{\n  "a": 1,\n  "b": [\n    2,\n    3\n  ]\n}\n'


def test_canonical_json_preserves_unicode():
    out = canonical_json({"name": "Sécurité"})
    assert b"S\xc3\xa9curit\xc3\xa9" in out  # UTF-8 bytes, not \uXXXX escapes


def test_canonical_json_is_byte_identical_to_legacy_implementation():
    # Mirror the exact form pipeline_factory.hashing.canonical_json produced
    # before this refactor. Any change here breaks Sprint 2's existing manifests.
    import json
    payload = {
        "schema_version": 1,
        "generator_version": "0.1.0",
        "model_name": "credit-risk-pd",
        "version": "1.0.0",
        "tier": "standard-batch",
        "generated_at": "2026-05-26T00:00:00+00:00",
        "artifact_hashes": {"model": "abc123", "config": "def456"},
    }
    legacy = (
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    )
    assert canonical_json(payload) == legacy
