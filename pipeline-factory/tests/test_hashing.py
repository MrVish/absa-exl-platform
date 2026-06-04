from pipeline_factory.hashing import (
    canonical_json,
    sha256_of_bytes,
    sha256_of_json,
    sha256_of_text,
    terraform_fmt,
)


def test_canonical_json_sorts_keys() -> None:
    out = canonical_json({"b": 1, "a": 2})
    assert out == b'{\n  "a": 2,\n  "b": 1\n}\n'


def test_canonical_json_is_deterministic() -> None:
    a = canonical_json({"z": [3, 2, 1], "y": {"q": 1, "p": 2}})
    b = canonical_json({"y": {"p": 2, "q": 1}, "z": [3, 2, 1]})
    assert a == b


def test_sha256_of_json_is_stable() -> None:
    h1 = sha256_of_json({"a": 1, "b": 2})
    h2 = sha256_of_json({"b": 2, "a": 1})
    assert h1 == h2
    assert len(h1) == 64


def test_sha256_of_text_matches_bytes() -> None:
    assert sha256_of_text("hello") == sha256_of_bytes(b"hello")


def test_terraform_fmt_canonicalises() -> None:
    messy = 'variable    "x"   {\n  type=string\n}\n'
    out = terraform_fmt(messy)
    # `terraform fmt -` normalises whitespace and alignment
    assert "variable" in out
    assert "string" in out
    # idempotent on re-application
    assert terraform_fmt(out) == out
