"""publish_public_key — fetch the CMK's public key, PEM-encode, upload to S3.

Run once after the first terraform apply for a new CMK, then again on each
key rotation. The bucket policy on exl-platform-public-keys grants read to
Principal: "*" so any party can fetch and verify offline (ADR-0003)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cryptography.hazmat.primitives import serialization

if TYPE_CHECKING:
    from mypy_boto3_kms.client import KMSClient
    from mypy_boto3_s3.client import S3Client
else:
    KMSClient = Any
    S3Client = Any


def publish_public_key(
    *,
    key_arn: str,
    bucket: str,
    kms_client: KMSClient,
    s3_client: S3Client,
    version: str = "v1",
) -> str:
    """Fetches the CMK's public key via kms:GetPublicKey, PEM-encodes it,
       uploads to s3://<bucket>/manifest-signing/<key_id>/<version>.pem.
       Returns the s3:// URI.

       Idempotent — the public key for a given CMK is immutable, so re-runs
       upload identical content. We do not use IfNoneMatch here because the
       expected case is "republish on rotation" where overwrite is acceptable;
       overwrite of the same content is a no-op at the audit layer."""
    resp = kms_client.get_public_key(KeyId=key_arn)
    der_bytes = resp["PublicKey"]
    key_id = resp["KeyId"].rsplit("/", 1)[-1]   # extract UUID suffix from full ARN

    pub = serialization.load_der_public_key(der_bytes)
    pem_bytes = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    s3_key = f"manifest-signing/{key_id}/{version}.pem"
    s3_client.put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=pem_bytes,
        ContentType="application/x-pem-file",
    )
    return f"s3://{bucket}/{s3_key}"
