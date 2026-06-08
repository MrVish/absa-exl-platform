"""Error hierarchy for the code-intake package."""

from __future__ import annotations


class CodeIntakeError(Exception):
    """Base class for code-intake failures."""


class ValidationError(CodeIntakeError):
    """Raised when validate() found error-severity findings.

    Carries the list of CheckResults as the first arg if available.
    """


class PackageConfigError(CodeIntakeError):
    """Raised when a package's model_config.yaml doesn't parse or doesn't
    match its schema."""


class VenvCreationError(CodeIntakeError):
    """Raised by venv.create_ephemeral_venv() when venv setup fails.

    The orchestrator catches this and surfaces it as a Finding so the
    'checkers never propagate exceptions to the caller' invariant holds.

    Carries code (PY004 or PY998), message, and optional hint for the
    Finding's user-facing description.
    """

    def __init__(self, *, code: str, message: str, hint: str | None = None) -> None:
        self.code = code
        self.message = message
        self.hint = hint
        super().__init__(message)
