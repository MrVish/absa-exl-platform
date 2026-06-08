"""subprocess wrapper around the terraform CLI.

Per spec section 6.2 phase 1 steps 1.3-1.5. Captures all output for
transcript/failure diagnosis. Raises bare DemoError on non-zero exit so
__main__.py classifies terraform failures as infra (exit 2), matching
the localstack.up()/down() pattern. Real .tf module errors get the same
treatment; CI's `terraform validate` catches those before they reach
the demo.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from demo.errors import DemoError


def _hint_for_step(step: str) -> str:
    """Per-subcommand hint for terraform failures."""
    if step == "init":
        return "check provider/module source paths are resolvable."
    if step == "apply":
        return (
            "if you see endpoint/connection errors, verify LocalStack is "
            "running (`docker compose -f infra/localstack/docker-compose.yml ps`)."
        )
    if step == "output":
        return "ensure `terraform apply` succeeded first; output reads from .tfstate."
    if step == "destroy":
        return "containers may be wedged; `docker ps` + `docker kill` if needed."
    return "check the terraform CLI output above."


@dataclass(frozen=True)
class TerraformRunner:
    """All terraform calls scoped to one stack directory."""

    stack_dir: Path
    timeout_s: int = 120

    def init(self) -> None:
        self._run(
            ["terraform", f"-chdir={self.stack_dir}", "init", "-input=false"],
            "init",
        )

    def apply(self, *, variables: dict[str, str]) -> None:
        args = [
            "terraform",
            f"-chdir={self.stack_dir}",
            "apply",
            "-input=false",
            "-auto-approve",
        ]
        for k, v in variables.items():
            args.extend(["-var", f"{k}={v}"])
        self._run(args, "apply")

    def output(self) -> bytes:
        return self._run(
            ["terraform", f"-chdir={self.stack_dir}", "output", "-json"],
            "output",
            return_stdout=True,
        )

    def destroy(self) -> None:
        self._run(
            [
                "terraform",
                f"-chdir={self.stack_dir}",
                "destroy",
                "-auto-approve",
                "-input=false",
            ],
            "destroy",
        )

    def _run(self, args: list[str], step: str, *, return_stdout: bool = False) -> bytes:
        try:
            proc = subprocess.run(args, capture_output=True, timeout=self.timeout_s)
        except subprocess.TimeoutExpired as e:
            stdout = (e.stdout or b"").decode("utf-8", errors="replace")
            stderr = (e.stderr or b"").decode("utf-8", errors="replace")
            raise DemoError(
                f"terraform {step} timed out after {self.timeout_s}s.\n"
                f"stdout:\n{stdout}\n"
                f"stderr:\n{stderr}"
            ) from e
        if proc.returncode != 0:
            stdout = proc.stdout.decode("utf-8", errors="replace")
            stderr = proc.stderr.decode("utf-8", errors="replace")
            raise DemoError(
                f"terraform {step} failed with exit code {proc.returncode}.\n"
                f"stdout:\n{stdout}\n"
                f"stderr:\n{stderr}\n"
                f"Hint: {_hint_for_step(step)}"
            )
        return proc.stdout if return_stdout else b""
