from __future__ import annotations

import json

import pytest
from click.testing import CliRunner
from cryptography.hazmat.primitives import serialization
from manifest_signer.cli import main
from manifest_signer.signer import sign_envelope


@pytest.fixture
def runner():
    return CliRunner()


def test_help_lists_all_subcommands(runner):
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    for cmd in ("sign", "sign-all", "verify-online", "verify-offline", "publish-key"):
        assert cmd in result.output


def test_sign_dry_run_does_not_call_kms(runner, unsigned_envelope, tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(unsigned_envelope, indent=2) + "\n")
    # No KMS mock -- if --dry-run actually called KMS, this would fail with
    # a connection error.
    result = runner.invoke(
        main,
        [
            "sign",
            "--manifest",
            str(manifest),
            "--key-arn",
            "arn:aws:kms:eu-west-1:111:key/abc",
            "--signer-principal",
            "test-principal",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    # Local file is unchanged
    assert json.loads(manifest.read_text())["signature"] == "UNSIGNED"


def test_sign_in_place_overwrites_file(
    runner,
    unsigned_envelope,
    signing_key,
    kms_client,
    tmp_path,
):
    """Full sign with --in-place modifies the file on disk."""
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(unsigned_envelope, indent=2) + "\n")
    result = runner.invoke(
        main,
        [
            "sign",
            "--manifest",
            str(manifest),
            "--key-arn",
            signing_key["Arn"],
            "--signer-principal",
            "test-principal",
            "--in-place",
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(manifest.read_text())["signature"] != "UNSIGNED"


def test_sign_all_signs_unsigned_uploads_skips_existing(
    runner,
    pipelines_tree,
    signing_key,
    kms_client,
    s3_client,
):
    bucket = "test-signed-manifests"
    s3_client.create_bucket(
        Bucket=bucket,
        CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
    )
    result = runner.invoke(
        main,
        [
            "sign-all",
            "--root",
            str(pipelines_tree),
            "--key-arn",
            signing_key["Arn"],
            "--upload-to-bucket",
            bucket,
            "--signer-principal",
            "test-principal",
        ],
    )
    assert result.exit_code == 0, result.output
    # Both manifests uploaded under the `pipelines/` prefix derived from the
    # envelope's subject_type field.
    objs = s3_client.list_objects_v2(Bucket=bucket)
    keys = {o["Key"] for o in objs.get("Contents", [])}
    assert "pipelines/credit-risk-pd/1.0.0/manifest.json" in keys
    assert "pipelines/fraud-detection/0.1.0/manifest.json" in keys


def test_sign_all_second_run_is_idempotent(
    runner,
    pipelines_tree,
    signing_key,
    kms_client,
    s3_client,
):
    bucket = "test-signed-manifests"
    s3_client.create_bucket(
        Bucket=bucket,
        CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
    )
    args = [
        "sign-all",
        "--root",
        str(pipelines_tree),
        "--key-arn",
        signing_key["Arn"],
        "--upload-to-bucket",
        bucket,
        "--signer-principal",
        "test-principal",
    ]
    r1 = runner.invoke(main, args)
    r2 = runner.invoke(main, args)
    assert r1.exit_code == 0 and r2.exit_code == 0
    # First run signs both manifests; second run sees them already in S3
    # and falls through the `IfNoneMatch="*"` 412 branch. Asserting on
    # the specific markers proves the idempotency branch actually fired
    # rather than the test trivially passing on identical exit codes.
    assert "[signed]" in r1.output
    assert "[skip-existing]" in r2.output
    assert "[signed]" not in r2.output


def test_sign_all_packages_and_pipelines_dont_collide_on_s3_key(
    runner,
    packages_and_pipelines_tree,
    signing_key,
    kms_client,
    s3_client,
):
    """Regression test for the T15-surfaced bug: when both packages/<name>/<ver>
    and pipelines/<name>/<ver> exist with the SAME model_name + version, the
    pre-fix sign-all derived s3_key purely from payload, producing identical
    keys. The second upload returned 412 PreconditionFailed which the signer
    silently treats as success — net effect: the pipeline manifest never
    landed in S3.

    The fix namespaces s3_key by envelope.subject_type so both manifests land
    at distinct S3 paths matching the on-disk structure.
    """
    packages_root, pipelines_root, _ = packages_and_pipelines_tree
    bucket = "test-signed-manifests"
    s3_client.create_bucket(
        Bucket=bucket,
        CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
    )

    # Sign packages first (matches T15's CI loop order: `for root in packages pipelines`).
    r1 = runner.invoke(
        main,
        [
            "sign-all",
            "--root",
            str(packages_root),
            "--key-arn",
            signing_key["Arn"],
            "--upload-to-bucket",
            bucket,
            "--signer-principal",
            "test-principal",
        ],
    )
    assert r1.exit_code == 0, r1.output
    assert "[signed]" in r1.output

    # Then sign pipelines.
    r2 = runner.invoke(
        main,
        [
            "sign-all",
            "--root",
            str(pipelines_root),
            "--key-arn",
            signing_key["Arn"],
            "--upload-to-bucket",
            bucket,
            "--signer-principal",
            "test-principal",
        ],
    )
    assert r2.exit_code == 0, r2.output
    # Pre-fix: this would print "[skip-existing]" because the package's
    # s3_key already exists. Post-fix: a fresh "[signed]" because the
    # pipeline lands at a distinct key.
    assert "[signed]" in r2.output, (
        "Pipeline manifest collided with package manifest on the same S3 key. "
        f"r2.output={r2.output!r}"
    )
    assert "[skip-existing]" not in r2.output

    # Both manifests must be present at their namespaced S3 keys.
    objs = s3_client.list_objects_v2(Bucket=bucket)
    keys = {o["Key"] for o in objs.get("Contents", [])}
    assert "packages/credit-risk-pd/1.0.0/manifest.json" in keys, (
        f"Expected package manifest at packages/ prefix; got keys={keys}"
    )
    assert "pipelines/credit-risk-pd/1.0.0/manifest.json" in keys, (
        f"Expected pipeline manifest at pipelines/ prefix; got keys={keys}"
    )

    # And their subject_type fields must round-trip correctly: pulling the
    # objects back should give one package, one pipeline.
    pkg_body = s3_client.get_object(
        Bucket=bucket, Key="packages/credit-risk-pd/1.0.0/manifest.json"
    )["Body"].read()
    pipe_body = s3_client.get_object(
        Bucket=bucket, Key="pipelines/credit-risk-pd/1.0.0/manifest.json"
    )["Body"].read()
    assert json.loads(pkg_body)["subject_type"] == "package"
    assert json.loads(pipe_body)["subject_type"] == "pipeline"


def test_sign_all_continue_on_error_reports_failed_count(
    runner,
    unsigned_envelope,
    signing_key,
    kms_client,
    s3_client,
    tmp_path,
):
    """sign-all --continue-on-error: bad manifest doesn't abort the loop;
    process exits 1 at the end but logs each good and each bad result.

    Builds a fixture with 3 manifests (2 valid pipeline, 1 malformed JSON).
    Asserts exit code is non-zero, errors=1 in output, and both good
    manifests land in S3 at their namespaced keys.
    """
    root = tmp_path / "manifests"
    for name in ("good-1", "bad-malformed", "good-2"):
        pkg_dir = root / name / "1.0.0"
        pkg_dir.mkdir(parents=True)
        if name == "bad-malformed":
            (pkg_dir / "manifest.json").write_text("{not valid json")
        else:
            envelope = {
                **unsigned_envelope,
                "payload": {**unsigned_envelope["payload"], "model_name": name},
                "subject_ref": f"pipeline:{name}:1.0.0",
            }
            (pkg_dir / "manifest.json").write_text(
                json.dumps(envelope, sort_keys=True, indent=2) + "\n"
            )

    bucket = "test-coe-bucket"
    s3_client.create_bucket(
        Bucket=bucket,
        CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
    )

    result = runner.invoke(
        main,
        [
            "sign-all",
            "--root",
            str(root),
            "--key-arn",
            signing_key["Arn"],
            "--upload-to-bucket",
            bucket,
            "--signer-principal",
            "test-principal",
            "--continue-on-error",
        ],
    )
    assert result.exit_code != 0
    assert "errors=1" in result.output
    # Both good manifests landed in S3 under the pipelines/ prefix.
    keys = {o["Key"] for o in s3_client.list_objects_v2(Bucket=bucket).get("Contents", [])}
    assert any("good-1" in k for k in keys), f"good-1 missing; keys={keys}"
    assert any("good-2" in k for k in keys), f"good-2 missing; keys={keys}"


def test_verify_online_exits_zero_on_valid(
    runner,
    unsigned_envelope,
    signing_key,
    kms_client,
    tmp_path,
):
    signed = sign_envelope(
        unsigned_envelope,
        key_arn=signing_key["Arn"],
        kms_client=kms_client,
        signer_principal="test",
    )
    manifest = tmp_path / "signed.json"
    manifest.write_text(json.dumps(signed, indent=2))
    result = runner.invoke(main, ["verify-online", "--manifest", str(manifest)])
    assert result.exit_code == 0, result.output


def test_verify_offline_exits_zero_on_valid(
    runner,
    unsigned_envelope,
    signing_key,
    kms_client,
    tmp_path,
):
    signed = sign_envelope(
        unsigned_envelope,
        key_arn=signing_key["Arn"],
        kms_client=kms_client,
        signer_principal="test",
    )
    manifest = tmp_path / "signed.json"
    manifest.write_text(json.dumps(signed, indent=2))

    der = kms_client.get_public_key(KeyId=signing_key["KeyId"])["PublicKey"]
    pub = serialization.load_der_public_key(der)
    pem = pub.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    pem_path = tmp_path / "pub.pem"
    pem_path.write_bytes(pem)

    result = runner.invoke(
        main,
        [
            "verify-offline",
            "--manifest",
            str(manifest),
            "--public-key",
            str(pem_path),
        ],
    )
    assert result.exit_code == 0, result.output


def test_publish_key_uploads_pem(runner, kms_client, s3_client, signing_key):
    bucket = "test-keys"
    s3_client.create_bucket(
        Bucket=bucket,
        CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
    )
    result = runner.invoke(
        main,
        [
            "publish-key",
            "--key-arn",
            signing_key["Arn"],
            "--bucket",
            bucket,
            "--version",
            "v1",
        ],
    )
    assert result.exit_code == 0, result.output
