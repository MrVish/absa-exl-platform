"""Error hierarchy for the manifest-signer package."""

from __future__ import annotations


class SignerError(Exception):
    """Base class for signer-side failures."""


class KeyMismatchError(SignerError):
    """Raised when a re-sign is attempted against a different key/algorithm than
    the envelope's current signature."""


class VerificationError(Exception):
    """Raised by verifier paths (online or offline) when signature validation
    fails for any reason."""
