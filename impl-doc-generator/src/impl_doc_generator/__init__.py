"""Implementation Document Generator (IDG).

Produces the per-model-version, LLM-assisted, human-approved "as-built"
Implementation Document. See docs/adr/0012-implementation-document-generation.md.

Pipeline: build_context_bundle -> guard_bundle -> provider.draft -> render_document.
"""

from .bundle import ContentFile, ContextBundle, build_context_bundle
from .document import ImplementationDocument, render_document
from .errors import (
    BundleError,
    IdgError,
    ProviderError,
    RawDataGuardError,
)
from .guard import guard_bundle
from .providers import LLMProvider, get_provider

__all__ = [
    "BundleError",
    "ContentFile",
    "ContextBundle",
    "IdgError",
    "ImplementationDocument",
    "LLMProvider",
    "ProviderError",
    "RawDataGuardError",
    "build_context_bundle",
    "get_provider",
    "guard_bundle",
    "render_document",
]
