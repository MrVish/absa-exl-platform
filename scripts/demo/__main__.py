"""Click CLI entry point for the demo orchestrator.

Subcommands:
  up      - docker compose up + terraform apply
  run     - composite: up + registry + producer + verifier + down
  down    - tear down
  status  - report what's running

See docs/superpowers/specs/2026-06-05-absa-exl-phase-3-sprint-1-localstack-demo-design.md
"""

from __future__ import annotations

import os
import signal
import sys
from collections.abc import Callable
from pathlib import Path

import click

from demo.chain import run_producer_chain
from demo.endpoints import DemoEndpoints
from demo.errors import DemoError, DemoStepFailed
from demo.localstack import down as ls_down
from demo.localstack import up as ls_up
from demo.localstack import wait_healthy
from demo.terraform_runner import TerraformRunner
from demo.transcript import Transcript
from demo.uvicorn_runner import run_registry
from demo.verifier import run_verifier_chain

COMPOSE_FILE = Path("infra/localstack/docker-compose.yml")
TF_STACK_DIR = Path("infra/localstack/terraform")
PACKAGE_PATH = Path("packages/credit-risk-pd/1.0.0")


def _check_prereqs(transcript: Transcript) -> None:
    """Phase 0: check docker/terraform/uv on PATH."""
    import shutil

    for tool in ("docker", "terraform", "uv"):
        if shutil.which(tool) is None:
            raise DemoError(
                f"{tool!r} not found on PATH. Install before running the demo. "
                f"See docs/runbooks/localstack-demo.md."
            )
    transcript.demo("prereqs OK: docker, terraform, uv")


@click.group(help=__doc__)
def main() -> None:
    pass


@main.command("up")
@click.option(
    "--transcript",
    "transcript_path",
    default="demo-transcript.md",
    type=click.Path(path_type=Path),
)
@click.option("--no-color", is_flag=True)
def up_cmd(transcript_path: Path, no_color: bool) -> None:
    """Stand up LocalStack + apply Terraform; do not run the chain."""
    transcript = Transcript(use_color=not no_color)
    try:
        _phase_up(transcript)
    finally:
        transcript.write_markdown(transcript_path)


@main.command("down")
@click.option("--keep-state", is_flag=True)
@click.option(
    "--transcript",
    "transcript_path",
    default="demo-transcript.md",
    type=click.Path(path_type=Path),
)
def down_cmd(keep_state: bool, transcript_path: Path) -> None:
    """Tear down the demo environment."""
    transcript = Transcript(use_color=True)
    try:
        ls_down(COMPOSE_FILE, keep_state=keep_state)
        transcript.demo("docker compose down complete")
    finally:
        transcript.write_markdown(transcript_path)


@main.command("status")
def status_cmd() -> None:
    """Report container / uvicorn state."""
    import subprocess

    proc = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "ps"],
        capture_output=True,
        text=True,
    )
    click.echo(proc.stdout)


@main.command("run")
@click.option("--keep-state", is_flag=True, help="Skip docker compose down on exit.")
@click.option("--no-cleanup", is_flag=True, help="Skip all teardown (for CI artifact capture).")
@click.option(
    "--transcript",
    "transcript_path",
    default="demo-transcript.md",
    type=click.Path(path_type=Path),
)
@click.option("--no-color", is_flag=True)
def run_cmd(keep_state: bool, no_cleanup: bool, transcript_path: Path, no_color: bool) -> None:
    """Composite: up + registry + producer + verifier + down."""
    transcript = Transcript(use_color=not no_color)
    primary_error: DemoError | None = None
    cleanups: list[Callable[[], None]] = []

    def _install_signal_handlers() -> None:
        def handler(signum: int, _frame: object) -> None:
            signame = signal.Signals(signum).name
            raise DemoError(f"received {signame} - running cleanup")

        signal.signal(signal.SIGINT, handler)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, handler)

    _install_signal_handlers()
    cleanup_errors: list[BaseException] = []
    exit_code = 0

    try:
        _check_prereqs(transcript)
        endpoints = _phase_up(transcript)
        # CRITICAL: register terraform destroy FIRST so it fires LAST
        # (after docker compose down has already discarded LocalStack).
        # This avoids the prevent_destroy=true conflict on the
        # signing-foundation S3 buckets. See infra/localstack/terraform/
        # main.tf header for the rationale.
        tf = TerraformRunner(stack_dir=TF_STACK_DIR)
        if not no_cleanup:
            cleanups.append(lambda: tf.destroy())
            cleanups.append(lambda: ls_down(COMPOSE_FILE, keep_state=keep_state))
        with run_registry(endpoints=endpoints, port=8080) as registry_url:
            transcript.demo(f"pipeline-registry up at {registry_url}")
            endpoints = endpoints.with_registry_url(registry_url)
            producer_result = run_producer_chain(endpoints, PACKAGE_PATH, transcript)
            run_verifier_chain(endpoints, producer_result, transcript)
        transcript.demo("DEMO PASSED")
    except DemoStepFailed as e:
        primary_error = e
        transcript.step_failed(e.account, e.step, exit_code=e.exit_code)
        if e.hint:
            transcript.demo(f"hint: {e.hint}")
        exit_code = 1
    except DemoError as e:
        primary_error = e
        transcript.demo(f"DEMO FAILED (infra): {e}")
        exit_code = 2
    finally:
        # LIFO cleanup: last-registered runs first.
        # Per the comment above, this means docker compose down (registered
        # second) fires before terraform destroy (registered first), which
        # is what we need to dodge the prevent_destroy=true buckets.
        for cleanup in reversed(cleanups):
            try:
                cleanup()
            except Exception as e:
                cleanup_errors.append(e)
        transcript.write_markdown(transcript_path)

    if cleanup_errors and exit_code == 0:
        # Successful demo + failed cleanup -> exit 3 per spec section 7.2.
        click.echo(f"::warning::Cleanup failed: {cleanup_errors}", err=True)
        exit_code = 3

    # Expose exit_code for GitHub Actions step output
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"exit_code={exit_code}\n")

    # Reference primary_error to silence "assigned but not used" lints; the
    # variable is retained for future enhancement (e.g. structured logging
    # of the failing exception alongside cleanup errors).
    _ = primary_error
    sys.exit(exit_code)


def _phase_up(transcript: Transcript) -> DemoEndpoints:
    """Phase 1: docker compose up + terraform apply. Returns DemoEndpoints."""
    transcript.demo("up: docker compose up -d")
    ls_up(COMPOSE_FILE)
    transcript.demo("up: waiting for LocalStack health")
    wait_healthy(timeout_s=60.0)
    transcript.demo("up: LocalStack ready")

    tf = TerraformRunner(stack_dir=TF_STACK_DIR)
    transcript.demo("up: terraform init")
    tf.init()
    transcript.demo("up: terraform apply")
    tf.apply(
        variables={
            "external_verifier_arns": '["arn:aws:iam::222222222222:root"]',
            "env_name": "dev",
        }
    )
    transcript.demo("up: terraform apply complete")
    output_bytes = tf.output()
    endpoints = DemoEndpoints.from_terraform_output(output_bytes)
    transcript.demo(
        f"endpoints: kms={endpoints.kms_key_arn[:48]}... "
        f"manifest_bucket={endpoints.manifest_bucket} "
        f"registry_table={endpoints.registry_table}"
    )
    return endpoints


if __name__ == "__main__":
    main()
