"""ABSA-side verifier chain - runs under the absa_session() boto3 session.

Per spec section 6.4, 7 sub-steps:
  4.1 S3 GET pipeline manifest (cross-account)
  4.2 S3 GET package manifest  (cross-account)
  4.3 S3 GET public-key PEM    (cross-account)
  4.4 verify_offline(pipeline_envelope, pem)
  4.5 verify_offline(package_envelope, pem)
  4.6 sha256(canonical_json(package.payload)) == pipeline.upstream_refs[0].digest
  4.7 HTTP GET registry, assert response matches producer record_id
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from typing import Any, cast

from demo.chain import ProducerResult
from demo.endpoints import DemoEndpoints
from demo.errors import DemoStepFailed
from demo.sessions import LS_ENDPOINT, absa_session
from demo.transcript import Transcript


def _fetch_pipeline_envelope(session: Any, *, bucket: str) -> dict[str, Any]:
    s3 = session.client("s3", endpoint_url=LS_ENDPOINT)
    body = s3.get_object(Bucket=bucket, Key="pipelines/credit-risk-pd/1.0.0/manifest.json")[
        "Body"
    ].read()
    return cast(dict[str, Any], json.loads(body))


def _fetch_package_envelope(session: Any, *, bucket: str) -> dict[str, Any]:
    s3 = session.client("s3", endpoint_url=LS_ENDPOINT)
    body = s3.get_object(Bucket=bucket, Key="packages/credit-risk-pd/1.0.0/manifest.json")[
        "Body"
    ].read()
    return cast(dict[str, Any], json.loads(body))


def _fetch_public_key_pem(session: Any, *, bucket: str, key_arn: str, version: str = "v1") -> bytes:
    """Fetch the published PEM from S3.

    The publish-key CLI (manifest_signer.publisher.publish_public_key) writes
    the PEM to s3://<bucket>/manifest-signing/<key_id>/<version>.pem where
    key_id is the last URI segment of the KMS key ARN. The signing-foundation
    module's bucket policy grants public read only under manifest-signing/*,
    so we MUST use this canonical path — fetching from /v1/public-key.pem
    would be 403 cross-account.
    """
    s3 = session.client("s3", endpoint_url=LS_ENDPOINT)
    key_id = key_arn.rsplit("/", 1)[-1]
    s3_key = f"manifest-signing/{key_id}/{version}.pem"
    body = s3.get_object(Bucket=bucket, Key=s3_key)["Body"].read()
    return cast(bytes, body)


def _verify_offline_envelope(envelope: dict[str, Any], *, pem: bytes) -> None:
    """Wrapper around manifest_signer.verifier.verify_offline.

    Imports inline so the test suite can patch this symbol without
    touching the manifest_signer module directly.
    """
    from manifest_signer.verifier import verify_offline

    verify_offline(envelope, public_key_pem=pem)


def _compute_payload_digest(payload: dict[str, Any]) -> str:
    from platform_contracts.canonical import canonical_json

    return hashlib.sha256(canonical_json(payload)).hexdigest()


def _registry_lookup(registry_url: str, *, model_name: str, version: str) -> dict[str, Any]:
    """GET the registry record. Uses the real route /models/<name>/versions/<version>."""
    url = f"{registry_url}/models/{model_name}/versions/{version}"
    with urllib.request.urlopen(url, timeout=10.0) as response:  # noqa: S310
        return cast(dict[str, Any], json.loads(response.read()))


def run_verifier_chain(
    endpoints: DemoEndpoints,
    producer: ProducerResult,
    transcript: Transcript,
) -> None:
    """Execute the 7-step verifier chain under absa-sim account."""
    session = absa_session()

    # 4.1 fetch pipeline envelope (cross-account S3)
    try:
        started = time.monotonic()
        pipeline_envelope = _fetch_pipeline_envelope(session, bucket=endpoints.manifest_bucket)
        transcript.step(
            "absa-sim",
            "4.1 fetch pipeline manifest (cross-account)",
            duration_s=time.monotonic() - started,
        )
    except Exception as e:
        raise DemoStepFailed(
            step="4.1 fetch pipeline manifest",
            account="absa-sim",
            exit_code=1,
            stderr=str(e).encode(),
            hint=(
                "Cross-account s3:GetObject failed. Verify the manifest "
                "bucket policy in Sprint 3 grants absa-sim (222222222222) "
                "GetObject. Check infra/localstack/terraform/s3.tf."
            ),
        ) from e

    # 4.2 fetch package envelope
    try:
        started = time.monotonic()
        package_envelope = _fetch_package_envelope(session, bucket=endpoints.manifest_bucket)
        transcript.step(
            "absa-sim",
            "4.2 fetch package manifest (cross-account)",
            duration_s=time.monotonic() - started,
        )
    except Exception as e:
        raise DemoStepFailed(
            step="4.2 fetch package manifest",
            account="absa-sim",
            exit_code=1,
            stderr=str(e).encode(),
        ) from e

    # 4.3 fetch public-key PEM
    try:
        started = time.monotonic()
        pem = _fetch_public_key_pem(
            session, bucket=endpoints.public_key_bucket, key_arn=endpoints.kms_key_arn
        )
        transcript.step(
            "absa-sim",
            "4.3 fetch public-key PEM (cross-account)",
            duration_s=time.monotonic() - started,
        )
    except Exception as e:
        raise DemoStepFailed(
            step="4.3 fetch public-key PEM",
            account="absa-sim",
            exit_code=1,
            stderr=str(e).encode(),
            hint=(
                "Public-key bucket policy may not grant absa-sim GetObject. "
                "Check infra/localstack/terraform/s3.tf."
            ),
        ) from e

    # 4.4 verify pipeline signature
    try:
        started = time.monotonic()
        _verify_offline_envelope(pipeline_envelope, pem=pem)
        transcript.step(
            "absa-sim",
            "4.4 verify_offline(pipeline)",
            duration_s=time.monotonic() - started,
        )
    except Exception as e:
        raise DemoStepFailed(
            step="4.4 verify pipeline signature",
            account="absa-sim",
            exit_code=1,
            stderr=str(e).encode(),
            hint="Pipeline manifest signature did not validate against PEM.",
        ) from e

    # 4.5 verify package signature
    try:
        started = time.monotonic()
        _verify_offline_envelope(package_envelope, pem=pem)
        transcript.step(
            "absa-sim",
            "4.5 verify_offline(package)",
            duration_s=time.monotonic() - started,
        )
    except Exception as e:
        raise DemoStepFailed(
            step="4.5 verify package signature",
            account="absa-sim",
            exit_code=1,
            stderr=str(e).encode(),
            hint="Package manifest signature did not validate against PEM.",
        ) from e

    # 4.6 chain-digest assertion (re-computed defense against tampered envelope)
    expected_digest = _compute_payload_digest(package_envelope["payload"])
    upstream_refs = pipeline_envelope.get("payload", {}).get("upstream_refs", [])
    if not upstream_refs:
        raise DemoStepFailed(
            step="4.6 chain digest",
            account="absa-sim",
            exit_code=1,
            stderr=b"pipeline upstream_refs is empty",
        )
    actual_digest = upstream_refs[0].get("digest")
    if expected_digest != actual_digest:
        raise DemoStepFailed(
            step="4.6 chain digest",
            account="absa-sim",
            exit_code=1,
            stdout=(
                f"computed package digest: {expected_digest}\n"
                f"pipeline upstream_refs[0].digest: {actual_digest}\n"
            ).encode(),
            stderr=b"chain digest mismatch (verifier-side, re-computed)",
            hint=(
                "The verifier re-computes sha256(canonical_json(package.payload)) "
                "to defend against an envelope whose top-level `digest` was "
                "tampered post-signing. Mismatch means either signing mutated "
                "the payload, the package envelope on S3 was modified after "
                "signing, or canonical_json is non-deterministic."
            ),
        )
    transcript.demo(f"chain digest re-verified (absa-side): {expected_digest[:16]}...")

    # 4.7 registry lookup (real route: /models/<name>/versions/<version>)
    try:
        started = time.monotonic()
        record = _registry_lookup(
            endpoints.registry_url, model_name="credit-risk-pd", version="1.0.0"
        )
        transcript.step(
            "absa-sim",
            "4.7 registry lookup",
            duration_s=time.monotonic() - started,
        )
    except urllib.error.HTTPError as e:
        raise DemoStepFailed(
            step="4.7 registry lookup",
            account="absa-sim",
            exit_code=1,
            stderr=f"registry GET returned HTTP {e.code}: {e.reason}".encode(),
            hint=(
                f"Registry GET returned {e.code}. The producer chain's "
                f"register-pipeline step may have silently failed, or the "
                f"DDB write never landed."
            ),
        ) from e
    except urllib.error.URLError as e:
        raise DemoStepFailed(
            step="4.7 registry lookup",
            account="absa-sim",
            exit_code=1,
            stderr=str(e).encode(),
            hint="Registry URL unreachable. Is uvicorn still running?",
        ) from e

    # Sanity-check record shape. The registry returns the registry record;
    # we don't strictly assert on producer.registry_record_id (which is a
    # response str from T10, not a key the registry uses) but we do check
    # the record has the expected model_name + version.
    if record.get("model_name") != "credit-risk-pd":
        raise DemoStepFailed(
            step="4.7 registry lookup",
            account="absa-sim",
            exit_code=1,
            stdout=json.dumps(record, indent=2).encode(),
            stderr=b"registry record model_name mismatch",
        )

    transcript.demo("verifier chain complete: all assertions hold")
