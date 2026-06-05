"""Checker protocol + result dataclasses shared by all checkers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Finding:
    """A single issue detected by a checker.

    `severity` is "error" or "warning". `code` is the checker-prefixed
    identifier (e.g. PY001, SAS003, PIR002) so log lines are self-describing.
    `file` and `line` are optional location hints.
    """

    severity: str
    code: str
    message: str
    file: str | None = None
    line: int | None = None


@dataclass(frozen=True)
class CheckResult:
    """One checker's output.

    `passed` is True iff there are no error-severity findings (warnings are
    OK unless --strict is on). The orchestrator measures `duration_seconds`
    around each call so CI logs surface slow checks.
    """

    checker: str
    passed: bool
    findings: list[Finding] = field(default_factory=list)
    duration_seconds: float = 0.0


class Checker(Protocol):
    """The interface every checker implements.

    Implementations are stateless and idempotent — calling `run` twice on the
    same `package_path` returns equivalent CheckResults (modulo wall-clock
    timestamps). The orchestrator catches exceptions and never propagates
    them up.
    """

    name: str

    def run(self, package_path: Path) -> CheckResult: ...
