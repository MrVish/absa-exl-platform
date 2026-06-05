"""Producer chain orchestrator - calls the 7 existing CLIs in sequence.

Per spec section 6.3. The chain is:

  3.1 code-intake validate
  3.2 code-intake generate-manifest
  3.3 manifest-signer sign        (package; --in-place + --upload-to)
  3.4 generate-pipeline generate  (regenerates pipeline manifest)
  3.5 manifest-signer sign-all    (pipeline; pipelines/ prefix)
  3.6 manifest-signer publish-key
  3.7 register-pipeline register

Critical assertion between 3.4 and 3.5: the package manifest's `digest`
field must equal the pipeline manifest's `payload.upstream_refs[0].digest`.
This is the cryptographic anchor Sprint 4 established (commit 3b1134c4);
the demo proves it survives signing.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from demo.endpoints import DemoEndpoints
from demo.errors import DemoStepFailed
from demo.sessions import LS_ENDPOINT, PRODUCER_ACCOUNT_ID
from demo.transcript import Transcript


@dataclass(frozen=True)
class ProducerResult:
    """Captured state from the producer chain for the verifier to consume."""

    package_manifest_path: Path
    pipeline_manifest_path: Path
    public_key_s3_uri: str
    registry_record_id: str
    chain_digest: str  # the digest that links package -> pipeline


def _localstack_env(*, account_id: str = PRODUCER_ACCOUNT_ID) -> dict[str, str]:
    """Env that points boto3 inside the producer CLIs at LocalStack."""
    env = dict(os.environ)
    env.update(
        {
            "AWS_ENDPOINT_URL_KMS": LS_ENDPOINT,
            "AWS_ENDPOINT_URL_S3": LS_ENDPOINT,
            "AWS_ENDPOINT_URL_DYNAMODB": LS_ENDPOINT,
            "AWS_ENDPOINT_URL_STS": LS_ENDPOINT,
            "AWS_ENDPOINT_URL_IAM": LS_ENDPOINT,
            "AWS_REGION": "eu-west-1",
            "AWS_DEFAULT_REGION": "eu-west-1",
            "AWS_ACCESS_KEY_ID": "test",
            "AWS_SECRET_ACCESS_KEY": "test",
            "LOCALSTACK_ACCOUNT_ID": account_id,
        }
    )
    return env


def _compute_payload_digest(payload: dict[str, Any]) -> str:
    """Same hash convention used by manifest-signer: sha256(canonical_json(payload))."""
    from platform_contracts.canonical import canonical_json

    return hashlib.sha256(canonical_json(payload)).hexdigest()


def _run_cli(
    args: list[str],
    *,
    step_name: str,
    transcript: Transcript,
    account: str = "exl-prod-sim",
    env: dict[str, str] | None = None,
) -> bytes:
    """Run a CLI, log to transcript, raise DemoStepFailed on non-zero."""
    started = time.monotonic()
    proc = subprocess.run(args, capture_output=True, env=env or _localstack_env(), timeout=120)
    duration = time.monotonic() - started
    if proc.returncode != 0:
        transcript.step_failed(account, step_name, exit_code=proc.returncode, duration_s=duration)
        raise DemoStepFailed(
            step=step_name,
            account=account,
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            hint=f"CLI {args[:3]} failed; see stdout/stderr in transcript.",
        )
    transcript.step(account, step_name, duration_s=duration)
    return proc.stdout


def run_producer_chain(
    endpoints: DemoEndpoints,
    package_path: Path,
    transcript: Transcript,
) -> ProducerResult:
    """Execute the 7-step producer chain. Per spec section 6.3."""
    pkg_manifest_path = package_path / "manifest.json"

    # 3.1 code-intake validate
    _run_cli(
        ["uv", "run", "code-intake", "validate", str(package_path), "--strict"],
        step_name="3.1 code-intake validate",
        transcript=transcript,
    )

    # 3.2 code-intake generate-manifest
    _run_cli(
        ["uv", "run", "code-intake", "generate-manifest", str(package_path)],
        step_name="3.2 code-intake generate-manifest",
        transcript=transcript,
    )

    # 3.3 manifest-signer sign (package)
    s3_uri_pkg = f"s3://{endpoints.manifest_bucket}/packages/credit-risk-pd/1.0.0/manifest.json"
    _run_cli(
        [
            "uv",
            "run",
            "manifest-signer",
            "sign",
            "--manifest",
            str(pkg_manifest_path),
            "--key-arn",
            endpoints.kms_key_arn,
            "--signer-principal",
            "arn:aws:iam::111111111111:role/exl-demo-signer-dev",
            "--upload-to",
            s3_uri_pkg,
            "--in-place",
        ],
        step_name="3.3 manifest-signer sign (package)",
        transcript=transcript,
    )

    # 3.4 generate-pipeline generate
    _run_cli(
        [
            "uv",
            "run",
            "generate-pipeline",
            "generate",
            "credit-risk-pd",
            "1.0.0",
            "--force",
        ],
        step_name="3.4 generate-pipeline generate",
        transcript=transcript,
    )

    # CRITICAL ASSERTION: chain digest must hold between package and pipeline.
    pipeline_manifest_path = Path("pipelines/credit-risk-pd/1.0.0/manifest.json")
    pkg_envelope = json.loads(pkg_manifest_path.read_text())
    pipe_envelope = json.loads(pipeline_manifest_path.read_text())
    pkg_digest = pkg_envelope.get("digest")
    upstream_refs = pipe_envelope.get("payload", {}).get("upstream_refs", [])
    if not upstream_refs:
        raise DemoStepFailed(
            step="chain-digest-check",
            account="exl-prod-sim",
            exit_code=2,
            stderr=b"pipeline manifest has no upstream_refs",
            hint=(
                "generate-pipeline did not emit upstream_refs[]; check "
                "pipeline-factory upstream_resolver."
            ),
        )
    pipeline_upstream_digest = upstream_refs[0].get("digest")
    if pkg_digest != pipeline_upstream_digest:
        raise DemoStepFailed(
            step="chain-digest-check",
            account="exl-prod-sim",
            exit_code=2,
            stdout=(
                f"package digest: {pkg_digest}\n"
                f"pipeline upstream_refs[0].digest: {pipeline_upstream_digest}\n"
            ).encode(),
            stderr=b"chain digest mismatch between package and pipeline manifests",
            hint=(
                f"chain digest mismatch: package digest {pkg_digest!r} != "
                f"pipeline upstream_refs[0].digest {pipeline_upstream_digest!r}. "
                "upstream_resolver produced wrong digest, or code-intake "
                "generate-manifest regenerated with different payload than "
                "before sign. Re-run; if persistent, this is a regression."
            ),
        )
    transcript.demo(f"chain digest verified between 3.4 and 3.5: {pkg_digest[:16]}...")

    # 3.5 manifest-signer sign-all (pipeline)
    out_3_5 = _run_cli(
        [
            "uv",
            "run",
            "manifest-signer",
            "sign-all",
            "--root",
            "pipelines",
            "--key-arn",
            endpoints.kms_key_arn,
            "--upload-to-bucket",
            endpoints.manifest_bucket,
            "--signer-principal",
            "arn:aws:iam::111111111111:role/exl-demo-signer-dev",
        ],
        step_name="3.5 manifest-signer sign-all (pipeline)",
        transcript=transcript,
    )
    # On a fresh run, must report [signed] not [skip-existing] (per spec section 3.5)
    if b"[skip-existing]" in out_3_5 and b"[signed]" not in out_3_5:
        raise DemoStepFailed(
            step="3.5 sign-all idempotency check",
            account="exl-prod-sim",
            exit_code=2,
            stdout=out_3_5,
            stderr=b"sign-all reported [skip-existing] on a fresh run",
            hint=(
                "sign-all reported [skip-existing] but no [signed] on a fresh "
                "run. Either LocalStack persistence leaked across demo runs "
                "(check PERSISTENCE: 0 in docker-compose.yml) or T15 fix "
                "regressed and the package's S3 key now collides with "
                "the pipeline's."
            ),
        )

    # 3.6 manifest-signer publish-key
    _run_cli(
        [
            "uv",
            "run",
            "manifest-signer",
            "publish-key",
            "--key-arn",
            endpoints.kms_key_arn,
            "--bucket",
            endpoints.public_key_bucket,
            "--version",
            "v1",
        ],
        step_name="3.6 manifest-signer publish-key",
        transcript=transcript,
    )
    public_key_uri = f"s3://{endpoints.public_key_bucket}/v1/public-key.pem"

    # 3.7 register-pipeline register
    out_3_7 = _run_cli(
        [
            "uv",
            "run",
            "register-pipeline",
            "register",
            "--manifest",
            str(pipeline_manifest_path),
            "--api-url",
            endpoints.registry_url,
        ],
        step_name="3.7 register-pipeline register",
        transcript=transcript,
    )
    record_id = ""
    for line in out_3_7.decode("utf-8", errors="replace").splitlines():
        if line.startswith("record_id="):
            record_id = line[len("record_id=") :].strip()
            break

    return ProducerResult(
        package_manifest_path=pkg_manifest_path,
        pipeline_manifest_path=pipeline_manifest_path,
        public_key_s3_uri=public_key_uri,
        registry_record_id=record_id,
        chain_digest=pkg_digest,
    )
