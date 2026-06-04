"""Click CLI for manifest-signer.

Subcommands:
- sign            -- sign a single manifest file (developer / one-off)
- sign-all        -- discover and sign every UNSIGNED manifest under a root (CI)
- verify-online   -- kms:Verify against the live CMK
- verify-offline  -- local verify against a PEM-encoded public key
- publish-key     -- kms:GetPublicKey -> upload PEM to S3 (one-shot)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import boto3
import click
from platform_contracts.canonical import canonical_json

from .errors import VerificationError
from .publisher import publish_public_key
from .signer import sign_envelope
from .verifier import verify_offline, verify_online


@click.group(help=__doc__)
def main() -> None:
    pass


@main.command("sign")
@click.option(
    "--manifest",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option("--key-arn", required=True, help="KMS key ARN or alias")
@click.option(
    "--signer-principal",
    required=True,
    help="STS session ARN of the assumed signer role",
)
@click.option("--upload-to", default=None, help="s3:// URI to upload the signed envelope to")
@click.option(
    "--in-place",
    is_flag=True,
    help="Overwrite the local manifest file with the signed envelope",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Compute and report what would be signed; do not call KMS",
)
def sign_cmd(
    manifest: Path,
    key_arn: str,
    signer_principal: str,
    upload_to: str | None,
    in_place: bool,
    dry_run: bool,
) -> None:
    envelope = json.loads(manifest.read_text())
    if dry_run:
        import hashlib

        digest = hashlib.sha256(canonical_json(envelope["payload"])).hexdigest()
        click.echo(f"[dry-run] would sign payload digest={digest} with key={key_arn}")
        return

    kms = boto3.client("kms")
    signed = sign_envelope(
        envelope,
        key_arn=key_arn,
        kms_client=kms,
        signer_principal=signer_principal,
    )

    # Always serialise via canonical_json so on-disk and S3 bytes are
    # deterministic regardless of future envelope field-ordering changes —
    # this is what makes the sign-all `IfNoneMatch="*"` idempotency story
    # robust against accidental key-insertion-order drift.
    if upload_to:
        _upload_signed_envelope(signed, s3_uri=upload_to)
    if in_place:
        manifest.write_bytes(canonical_json(signed))
    if not upload_to and not in_place:
        click.echo(canonical_json(signed).decode("utf-8").rstrip("\n"))


@main.command("sign-all")
@click.option(
    "--root",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option("--key-arn", required=True)
@click.option("--upload-to-bucket", required=True)
@click.option("--signer-principal", required=True)
@click.option("--continue-on-error", is_flag=True)
def sign_all_cmd(
    root: Path,
    key_arn: str,
    upload_to_bucket: str,
    signer_principal: str,
    continue_on_error: bool,
) -> None:
    """Discover pipelines/*/*/manifest.json, sign each UNSIGNED one, upload to S3.

    Derives <name>/<version> from the manifest payload (not the file path) for
    robustness. Treats S3 412 PreconditionFailed as success (idempotent re-run).
    """
    kms = boto3.client("kms")
    s3 = boto3.client("s3")

    manifests = sorted(root.glob("*/*/manifest.json"))
    if not manifests:
        click.echo(f"No manifests found under {root}")
        return

    signed_count = 0
    skipped_count = 0
    error_count = 0
    for manifest_path in manifests:
        try:
            envelope = json.loads(manifest_path.read_text())
            signed = sign_envelope(
                envelope,
                key_arn=key_arn,
                kms_client=kms,
                signer_principal=signer_principal,
            )
            name = signed["payload"]["model_name"]
            version = signed["payload"]["version"]
            s3_key = f"{name}/{version}/manifest.json"

            try:
                s3.put_object(
                    Bucket=upload_to_bucket,
                    Key=s3_key,
                    Body=canonical_json(signed),
                    ContentType="application/json",
                    IfNoneMatch="*",
                )
                click.echo(f"[signed] {name}@{version} -> s3://{upload_to_bucket}/{s3_key}")
                signed_count += 1
            except Exception as e:
                if _is_precondition_failed(e):
                    click.echo(f"[skip-existing] {name}@{version} already in S3")
                    skipped_count += 1
                else:
                    raise
        except Exception as e:
            error_count += 1
            click.echo(f"[error] {manifest_path}: {e}", err=True)
            if not continue_on_error:
                raise

    click.echo(f"Done. signed={signed_count} skipped-existing={skipped_count} errors={error_count}")
    if error_count and continue_on_error:
        sys.exit(1)


def _is_precondition_failed(exc: Exception) -> bool:
    """Detect S3 PutObject IfNoneMatch=\"*\" returning 412."""
    response = getattr(exc, "response", None)
    if not isinstance(response, dict):
        return False
    error: Any = response.get("Error", {})
    if not isinstance(error, dict):
        return False
    code = error.get("Code")
    return code in ("PreconditionFailed", "412")


@main.command("verify-online")
@click.option(
    "--manifest",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
def verify_online_cmd(manifest: Path) -> None:
    envelope = json.loads(manifest.read_text())
    kms = boto3.client("kms")
    try:
        verify_online(envelope, kms_client=kms)
    except VerificationError as e:
        click.echo(f"FAIL: {e}", err=True)
        sys.exit(1)
    click.echo("OK")


@main.command("verify-offline")
@click.option(
    "--manifest",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--public-key",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
def verify_offline_cmd(manifest: Path, public_key: Path) -> None:
    envelope = json.loads(manifest.read_text())
    pem_bytes = public_key.read_bytes()
    try:
        verify_offline(envelope, public_key_pem=pem_bytes)
    except VerificationError as e:
        click.echo(f"FAIL: {e}", err=True)
        sys.exit(1)
    click.echo("OK")


@main.command("publish-key")
@click.option("--key-arn", required=True)
@click.option("--bucket", required=True)
@click.option("--version", default="v1")
def publish_key_cmd(key_arn: str, bucket: str, version: str) -> None:
    kms = boto3.client("kms")
    s3 = boto3.client("s3")
    uri = publish_public_key(
        key_arn=key_arn,
        bucket=bucket,
        kms_client=kms,
        s3_client=s3,
        version=version,
    )
    click.echo(uri)


def _upload_signed_envelope(envelope: dict[str, Any], *, s3_uri: str) -> None:
    """Upload a signed envelope dict to an s3:// URI using IfNoneMatch=\"*\"."""
    if not s3_uri.startswith("s3://"):
        # User-supplied via --upload-to; use a real check that survives
        # python -O (asserts can be optimised out).
        raise click.BadParameter(f"--upload-to must be an s3:// URI, got {s3_uri!r}")
    bucket, _, key = s3_uri[5:].partition("/")
    s3 = boto3.client("s3")
    body = canonical_json(envelope)
    try:
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType="application/json",
            IfNoneMatch="*",
        )
    except Exception as e:
        if _is_precondition_failed(e):
            return
        raise
