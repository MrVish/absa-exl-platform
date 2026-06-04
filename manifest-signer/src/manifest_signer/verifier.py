"""verify_online (kms:Verify) and verify_offline (cryptography) — both paths
required by ADR-0003. Both share the canonical-payload pipeline.

Wire format: signatures are produced by ``sign_envelope`` over the canonical
JSON bytes of ``envelope["payload"]`` with ``MessageType=RAW``; AWS KMS and the
``cryptography`` library both apply SHA-256 to those bytes before the RSA
PKCS#1 v1.5 operation, yielding identical signatures by either path.
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from platform_contracts.canonical import canonical_json

from .errors import VerificationError

if TYPE_CHECKING:
    from mypy_boto3_kms.client import KMSClient
else:
    KMSClient = Any


def verify_online(envelope: dict[str, Any], *, kms_client: KMSClient) -> None:
    """Raises VerificationError on any failure. One KMS round-trip."""
    message = _payload_message(envelope)
    try:
        resp = kms_client.verify(
            KeyId=envelope["signing_key_arn"],
            Message=message,
            MessageType="RAW",
            SigningAlgorithm=envelope["signing_algorithm"],
            Signature=base64.b64decode(envelope["signature"]),
        )
    except Exception as e:
        raise VerificationError(f"kms:Verify raised: {e}") from e
    if not resp.get("SignatureValid", False):
        raise VerificationError("kms:Verify returned SignatureValid=false")


def verify_offline(envelope: dict[str, Any], *, public_key_pem: bytes) -> None:
    """Raises VerificationError on any failure. No AWS access required."""
    message = _payload_message(envelope)
    public_key = serialization.load_pem_public_key(public_key_pem)
    if not isinstance(public_key, RSAPublicKey):
        raise VerificationError(f"expected RSA public key, got {type(public_key).__name__}")
    try:
        public_key.verify(
            base64.b64decode(envelope["signature"]),
            message,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except InvalidSignature as e:
        raise VerificationError(f"offline verification failed: {e}") from e


def _payload_message(envelope: dict[str, Any]) -> bytes:
    return canonical_json(envelope["payload"])
