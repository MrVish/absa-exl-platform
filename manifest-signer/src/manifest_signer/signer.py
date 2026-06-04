"""sign_envelope — fill the manifest envelope's sentinel fields via kms:Sign."""

from __future__ import annotations

import base64
import copy
import hashlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from platform_contracts.canonical import canonical_json

from .errors import KeyMismatchError

if TYPE_CHECKING:
    from mypy_boto3_kms.client import KMSClient
else:
    KMSClient = Any

# Mirrors pipeline_factory.manifest.UNSIGNED_SIGNATURE. Hardcoded here so
# manifest-signer does not depend on pipeline-factory (the dep direction is
# manifest-signer -> platform-contracts, and pipeline-factory ->
# platform-contracts; the two sibling packages never cross-import).
UNSIGNED_SENTINEL = "UNSIGNED"
SIGNING_ALGORITHM = "RSASSA_PKCS1_V1_5_SHA_256"


def sign_envelope(
    unsigned_envelope: dict[str, Any],
    *,
    key_arn: str,
    kms_client: KMSClient,
    signer_principal: str,
    signed_at: str | None = None,
) -> dict[str, Any]:
    """Return a NEW envelope dict with the four sentinel fields filled in.

    Idempotency contract:
      - signature == "UNSIGNED"                                -> sign and fill
      - signature != "UNSIGNED", same resolved key + algorithm -> return input unchanged
      - signature != "UNSIGNED", different key or algorithm    -> raise KeyMismatchError

    The signature covers canonical_json(envelope["payload"]), NOT the envelope
    itself (the envelope contains the signature field — signing it would be
    circular).

    `signed_at` is preserved if passed (CI idempotency story); otherwise filled
    with datetime.now(UTC).isoformat(timespec="seconds").

    `signer_principal` is the caller's resolved STS session ARN — convention
    documented in ADR-0009.
    """
    digest = hashlib.sha256(canonical_json(unsigned_envelope["payload"])).digest()

    # Resolve the key ARN up front. If the caller passed an alias, KMS resolves
    # it via DescribeKey; we need the resolved ARN for both the idempotency
    # check and the final envelope.
    resolved_key_arn = _resolve_key_arn(kms_client, key_arn)

    current_signature = unsigned_envelope.get("signature", UNSIGNED_SENTINEL)
    if current_signature != UNSIGNED_SENTINEL:
        current_key = unsigned_envelope.get("signing_key_arn")
        current_alg = unsigned_envelope.get("signing_algorithm")
        if current_key == resolved_key_arn and current_alg == SIGNING_ALGORITHM:
            return unsigned_envelope  # idempotent re-sign
        raise KeyMismatchError(
            f"envelope already signed by {current_key} ({current_alg}); "
            f"refusing to re-sign with {resolved_key_arn} ({SIGNING_ALGORITHM})"
        )

    resp = kms_client.sign(
        KeyId=resolved_key_arn,
        Message=digest,
        MessageType="DIGEST",
        SigningAlgorithm=SIGNING_ALGORITHM,
    )

    out = copy.deepcopy(unsigned_envelope)
    out["signature"] = base64.b64encode(resp["Signature"]).decode("ascii")
    out["signing_key_arn"] = resolved_key_arn
    out["signing_algorithm"] = SIGNING_ALGORITHM
    out["signer_principal"] = signer_principal
    out["signed_at"] = signed_at or datetime.now(UTC).isoformat(timespec="seconds")
    return out


def _resolve_key_arn(kms_client: KMSClient, key_arn_or_alias: str) -> str:
    """If the caller passed an alias, resolve to the underlying key ARN.
    If they passed a real ARN, return it unchanged.

    Callers MUST pass either an alias (``alias/...`` or qualified alias ARN)
    or a full key ARN. Bare key UUIDs are returned unchanged and would land
    in the envelope's ``signing_key_arn`` field as a UUID rather than an
    ARN — defeating the audit-trail's immutable-identifier requirement. The
    pipeline-factory CLI and CI workflow both pass full ARNs, so the
    UUID path is not a supported caller shape.
    """
    if not key_arn_or_alias.startswith("alias/") and ":alias/" not in key_arn_or_alias:
        return key_arn_or_alias
    resp = kms_client.describe_key(KeyId=key_arn_or_alias)
    return cast(str, resp["KeyMetadata"]["Arn"])
