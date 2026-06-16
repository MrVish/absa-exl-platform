"""Typed errors for the IDG, each with a stable code, message, and hint."""

from __future__ import annotations


class IdgError(Exception):
    """Base class for all IDG errors."""

    code = "IDG000"

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        base = f"[{self.code}] {self.message}"
        return f"{base}\n  hint: {self.hint}" if self.hint else base


class BundleError(IdgError):
    """A required artefact is missing or malformed while assembling the bundle."""

    code = "IDG010"


class RawDataGuardError(IdgError):
    """The context bundle contains something that looks like raw data / PII.

    The guard is a hard rule (ADR-0012): the LLM receives code + docs + schemas
    + metadata ONLY, never raw data rows. Hitting this means an input file was
    wrongly included; it is never auto-skipped.
    """

    code = "IDG020"


class ProviderError(IdgError):
    """The LLM provider could not be constructed or failed to draft."""

    code = "IDG030"
