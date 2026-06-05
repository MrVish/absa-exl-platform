"""subprocess wrapper around the terraform CLI.

Per spec section 6.2 phase 1 steps 1.3-1.5. Captures all output for
transcript/failure diagnosis. Raises DemoStepFailed on non-zero exit.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from demo.errors import DemoStepFailed


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
            raise DemoStepFailed(
                step=f"terraform-{step}",
                account="exl-prod-sim",
                exit_code=-1,
                stdout=e.stdout or b"",
                stderr=e.stderr or b"",
                hint=f"terraform {step} timed out after {self.timeout_s}s",
            ) from e
        if proc.returncode != 0:
            raise DemoStepFailed(
                step=f"terraform-{step}",
                account="exl-prod-sim",
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                hint=(
                    f"Check `terraform {step}` output. If you see endpoint "
                    f"errors, verify LocalStack is running."
                ),
            )
        return proc.stdout if return_stdout else b""
