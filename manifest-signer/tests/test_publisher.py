from __future__ import annotations

from cryptography.hazmat.primitives import serialization
from manifest_signer.publisher import publish_public_key


def test_publish_uploads_pem_to_expected_key(kms_client, s3_client, signing_key):
    bucket = "test-public-keys"
    s3_client.create_bucket(
        Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": "eu-west-1"}
    )

    uri = publish_public_key(
        key_arn=signing_key["Arn"],
        bucket=bucket,
        kms_client=kms_client,
        s3_client=s3_client,
        version="v1",
    )

    key_id = signing_key["KeyId"]
    expected_key = f"manifest-signing/{key_id}/v1.pem"
    assert uri == f"s3://{bucket}/{expected_key}"

    obj = s3_client.get_object(Bucket=bucket, Key=expected_key)
    body = obj["Body"].read()
    pub = serialization.load_pem_public_key(body)
    assert pub.key_size == 3072


def test_publish_is_idempotent_on_rerun(kms_client, s3_client, signing_key):
    bucket = "test-public-keys"
    s3_client.create_bucket(
        Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": "eu-west-1"}
    )

    uri_a = publish_public_key(
        key_arn=signing_key["Arn"],
        bucket=bucket,
        kms_client=kms_client,
        s3_client=s3_client,
        version="v1",
    )
    uri_b = publish_public_key(
        key_arn=signing_key["Arn"],
        bucket=bucket,
        kms_client=kms_client,
        s3_client=s3_client,
        version="v1",
    )
    assert uri_a == uri_b
    s3_key = f"manifest-signing/{signing_key['KeyId']}/v1.pem"
    body_a = s3_client.get_object(Bucket=bucket, Key=s3_key)["Body"].read()
    body_b = s3_client.get_object(Bucket=bucket, Key=s3_key)["Body"].read()
    assert body_a == body_b
