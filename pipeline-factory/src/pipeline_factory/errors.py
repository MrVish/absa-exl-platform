"""Shared exception types for pipeline-factory.

Both error types mean "generator cannot produce; user must fix and re-run".
PipelineDriftError is a subclass of GeneratorError so callers can use a
single ``except GeneratorError`` to catch both:

  - GeneratorError      — generator can't resolve a required input
                          (e.g. missing upstream package manifest)
  - PipelineDriftError  — re-generating would change a file that already
                          exists, without --force

The subclass relationship is also a forward-compatible contract: future
"generator can't produce" errors should extend GeneratorError.
"""

from __future__ import annotations


class GeneratorError(Exception):
    """Raised when pipeline generation can't resolve a required input."""


class PipelineDriftError(GeneratorError):
    """Raised when re-generating would change a file that already exists, without --force."""
