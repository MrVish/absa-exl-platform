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
