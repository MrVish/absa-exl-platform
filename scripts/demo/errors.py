"""Exception hierarchy for the demo orchestrator.

Three exception types, with exit-code semantics defined in spec §7.2:

  DemoError              base — anything the demo orchestrator raises
  └─ DemoStepFailed      → exit 1 (platform regression)
  └─ DemoCleanupFailed   → exit 3 (teardown failed; primary may still be set)
                           Used by infra failures too (Docker, Terraform, uvicorn)
                           which the runner remaps to exit 2 — see __main__.py.
"""

from __future__ import annotations


class DemoError(Exception):
    """Base for all demo-orchestrator-raised exceptions."""


class DemoStepFailed(DemoError):
    """A producer/verifier sub-step failed. Carries triage detail."""

    def __init__(
        self,
        *,
        step: str,
        account: str,
        exit_code: int,
        stdout: bytes | str = b"",
        stderr: bytes | str = b"",
        hint: str | None = None,
    ) -> None:
        self.step = step
        self.account = account
        self.exit_code = exit_code
        self.stdout = (
            stdout if isinstance(stdout, bytes) else stdout.encode("utf-8", errors="replace")
        )
        self.stderr = (
            stderr if isinstance(stderr, bytes) else stderr.encode("utf-8", errors="replace")
        )
        self.hint = hint
        super().__init__(
            f"step {step!r} ({account}) failed with exit_code={exit_code}"
            + (f"; hint: {hint}" if hint else "")
        )


class DemoCleanupFailed(DemoError):
    """Teardown failed. Carries the primary error (if any) for context."""

    def __init__(
        self,
        *,
        primary_error: BaseException | None,
        cleanup_errors: list[BaseException],
    ) -> None:
        self.primary_error = primary_error
        self.cleanup_errors = cleanup_errors
        summary = "; ".join(repr(e) for e in cleanup_errors)
        super().__init__(f"cleanup failed: {summary}")
