from __future__ import annotations

import json

import pytest

from demo.endpoints import DemoEndpoints
from demo.errors import DemoError


def _terraform_output_bytes(**values: str) -> bytes:
    """Synthesize the JSON shape `terraform output -json` emits."""
    return json.dumps(
        {k: {"sensitive": False, "type": "string", "value": v} for k, v in values.items()}
    ).encode("utf-8")


def test_from_terraform_output_parses_happy_path() -> None:
    """All five required outputs present → returns populated DemoEndpoints."""
    data = _terraform_output_bytes(
        kms_key_arn="arn:aws:kms:eu-west-1:111111111111:key/abc",
        kms_key_alias="alias/exl-signing",
        manifest_bucket="exl-signed-manifests-dev",
        public_key_bucket="exl-public-keys-dev",
        registry_table="pipeline-registry-dev",
    )
    ep = DemoEndpoints.from_terraform_output(data)
    assert ep.kms_key_arn == "arn:aws:kms:eu-west-1:111111111111:key/abc"
    assert ep.kms_key_alias == "alias/exl-signing"
    assert ep.manifest_bucket == "exl-signed-manifests-dev"
    assert ep.public_key_bucket == "exl-public-keys-dev"
    assert ep.registry_table == "pipeline-registry-dev"
    assert ep.registry_url == ""  # populated post-uvicorn-boot


def test_from_terraform_output_raises_on_missing_key() -> None:
    """A missing required output is a hard error — DemoEndpoints can't be partial."""
    data = _terraform_output_bytes(
        kms_key_arn="arn:aws:kms:eu-west-1:111111111111:key/abc",
        # kms_key_alias missing
        manifest_bucket="b",
        public_key_bucket="b",
        registry_table="t",
    )
    with pytest.raises(DemoError) as exc_info:
        DemoEndpoints.from_terraform_output(data)
    assert "kms_key_alias" in str(exc_info.value)


def test_from_terraform_output_raises_on_malformed_json() -> None:
    with pytest.raises(DemoError):
        DemoEndpoints.from_terraform_output(b"not json at all")


def test_with_registry_url_returns_new_endpoints() -> None:
    """DemoEndpoints is frozen; we get a new instance with registry_url populated."""
    ep = DemoEndpoints.from_terraform_output(
        _terraform_output_bytes(
            kms_key_arn="a",
            kms_key_alias="b",
            manifest_bucket="c",
            public_key_bucket="d",
            registry_table="e",
        )
    )
    ep2 = ep.with_registry_url("http://localhost:8080")
    assert ep2.registry_url == "http://localhost:8080"
    assert ep.registry_url == ""  # original is unchanged
    assert ep2.kms_key_arn == ep.kms_key_arn  # other fields preserved
