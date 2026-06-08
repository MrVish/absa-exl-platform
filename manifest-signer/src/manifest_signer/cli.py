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
    """Discover <root>/*/*/manifest.json, sign each UNSIGNED one, upload to S3.

    The S3 key includes a top-level prefix derived from the envelope's
    ``subject_type`` field: ``packages/...`` for ``subject_type == "package"``,
    ``pipelines/...`` otherwise. This keeps package + pipeline manifests with
    the same ``model_name``/``version`` from colliding on the same S3 key (a
    silent failure mode pre-fix: the second upload returned 412
    PreconditionFailed which the idempotency story masks as success).

    Derives ``<name>/<version>`` from the manifest payload (not the file path)
    for robustness. Treats S3 412 PreconditionFailed as success (idempotent
    re-run).
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
            # Namespace by subject_type so packages/<name>/<ver>/manifest.json
            # and pipelines/<name>/<ver>/manifest.json don't collide on the
            # same S3 key. Strict on unknown values: schema is the source of
            # truth, so any subject_type we don't recognise indicates the
            # signer needs upgrading. Silent fallback to "pipeline" would
            # misroute a future format (e.g. "dataset") into the pipelines/
            # prefix, where the IfNoneMatch="*" idempotency story would
            # silently mask the misroute as [skip-existing] on a re-run.
            subject_type = signed.get("subject_type")
            if subject_type not in ("package", "pipeline"):
                raise click.ClickException(
                    f"unknown subject_type {subject_type!r} for {manifest_path}; "
                    f"manifest-signer needs upgrading to support new subject types. "
                    f"Expected one of: package, pipeline."
                )
            prefix = "packages" if subject_type == "package" else "pipelines"
            s3_key = f"{prefix}/{name}/{version}/manifest.json"

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


@main.command("verify-from-bucket")
@click.option(
    "--bucket",
    required=True,
    help="S3 bucket holding the signed manifest envelope",
)
@click.option(
    "--key",
    required=True,
    help="S3 object key for the manifest (e.g. pipelines/credit-risk-pd/1.0.0/manifest.json)",
)
@click.option(
    "--public-key-bucket",
    default=None,
    help="S3 bucket holding the published PEM (default: same as --bucket)",
)
@click.option(
    "--public-key-uri",
    default=None,
    help=(
        "Override PEM s3 URI. If omitted, derived from envelope.signing_key_arn "
        "+ version (manifest-signing/<key_id>/<version>.pem)"
    ),
)
@click.option(
    "--version",
    default="v1",
    help="PEM version suffix used in the derived path (default: v1)",
)
def verify_from_bucket_cmd(
    bucket: str,
    key: str,
    public_key_bucket: str | None,
    public_key_uri: str | None,
    version: str,
) -> None:
    """One-shot offline verification of a manifest already in S3.

    Fetches the envelope, derives or accepts the PEM URI, fetches the PEM,
    runs verify_offline. Exits 0 on valid, 1 on invalid (or any fetch
    failure), with a diagnostic on stderr.
    """
    s3 = boto3.client("s3")

    # 1. Fetch envelope from s3://<bucket>/<key>
    try:
        envelope_bytes = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        envelope = json.loads(envelope_bytes)
    except Exception as e:
        click.echo(f"FAIL: could not fetch s3://{bucket}/{key}: {e}", err=True)
        sys.exit(1)

    # 2. Derive PEM URI if not given
    if public_key_uri:
        # Parse s3://bucket/key
        if not public_key_uri.startswith("s3://"):
            click.echo(
                f"FAIL: --public-key-uri must be an s3:// URI, got {public_key_uri!r}",
                err=True,
            )
            sys.exit(1)
        pk_bucket, _, pk_key = public_key_uri[5:].partition("/")
    else:
        key_arn = envelope.get("signing_key_arn", "")
        key_id = key_arn.rsplit("/", 1)[-1] if key_arn else ""
        if not key_id:
            click.echo(
                "FAIL: envelope has no signing_key_arn -- cannot derive PEM path. "
                "Use --public-key-uri explicitly.",
                err=True,
            )
            sys.exit(1)
        pk_bucket = public_key_bucket or bucket
        pk_key = f"manifest-signing/{key_id}/{version}.pem"

    # 3. Fetch PEM
    try:
        pem_bytes = s3.get_object(Bucket=pk_bucket, Key=pk_key)["Body"].read()
    except Exception as e:
        click.echo(f"FAIL: could not fetch PEM at s3://{pk_bucket}/{pk_key}: {e}", err=True)
        sys.exit(1)

    # 4. Verify
    try:
        verify_offline(envelope, public_key_pem=pem_bytes)
    except VerificationError as e:
        click.echo(f"FAIL: {e}", err=True)
        sys.exit(1)

    click.echo(f"OK  manifest: s3://{bucket}/{key}")
    click.echo(f"    pem:      s3://{pk_bucket}/{pk_key}")


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
