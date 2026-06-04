from __future__ import annotations

from datetime import UTC, datetime
from importlib.metadata import version as _pkg_version
from typing import Any

from .hashing import canonical_json, sha256_of_bytes

UNSIGNED_SIGNATURE = "UNSIGNED"
UNSIGNED_KEY_ARN = "arn:aws:kms:placeholder:000000000000:key/unsigned"
UNSIGNED_SIGNING_ALGORITHM = "RSASSA_PKCS1_V1_5_SHA_256"
UNSIGNED_PRINCIPAL = "unsigned"


def _generator_version() -> str:
    try:
        return _pkg_version("pipeline-factory")
    except Exception:  # pragma: no cover — fallback for source checkout without install
        return "0.1.0"


def build_payload(
    *,
    model_name: str,
    version: str,
    tier: str,
    artifact_hashes: dict[str, str],
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Construct the payload object that goes inside the manifest envelope."""
    return {
        "schema_version": 1,
        "generator_version": _generator_version(),
        "model_name": model_name,
        "version": version,
        "tier": tier,
        "generated_at": generated_at or datetime.now(UTC).isoformat(),
        "artifact_hashes": artifact_hashes,
    }


def build_envelope(
    *,
    payload: dict[str, Any],
    subject_ref: str,
    signed_at: str | None = None,
) -> dict[str, Any]:
    """Wrap *payload* in a manifest-envelope.

    Unsigned by design — sub-sprint 2.3 (Code Intake) fills the signature fields.
    """
    digest = sha256_of_bytes(canonical_json(payload))
    return {
        "digest": digest,
        "digest_algorithm": "SHA-256",
        "signature": UNSIGNED_SIGNATURE,
        "signing_key_arn": UNSIGNED_KEY_ARN,
        "signing_algorithm": UNSIGNED_SIGNING_ALGORITHM,
        "subject_type": "pipeline",
        "subject_ref": subject_ref,
        "signed_at": signed_at or datetime.now(UTC).isoformat(),
        "signer_principal": UNSIGNED_PRINCIPAL,
        "payload": payload,
    }


def is_signed(envelope: dict[str, Any]) -> bool:
    """Return True iff the envelope's signature has been overwritten with a real value."""
    return envelope.get("signature") != UNSIGNED_SIGNATURE
