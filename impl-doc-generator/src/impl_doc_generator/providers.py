"""LLM provider adapter — swappable by config (ADR-0012).

Providers draft *narrative* sections only; facts are added deterministically in
document.py. A provider receives a system instruction, a context string (the
grounded facts + reviewable content), and the list of sections to draft, and
returns ``{section_id: narrative_text}``.

- ``offline`` — deterministic, no network. The default; used in tests + CI and
  whenever no cloud provider is configured. Emits clearly-labelled placeholders
  so an unreviewed draft can never be mistaken for finished narrative.
- ``azure_openai`` / ``anthropic`` — managed enterprise services, lazy-imported
  so the package installs + tests without the SDKs or any credentials.
"""

from __future__ import annotations

import importlib
import json
import os
from typing import Any, Protocol, runtime_checkable

from .errors import ProviderError

Section = tuple[str, str]  # (section_id, drafting instruction)


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    def draft(self, *, system: str, context: str, sections: list[Section]) -> dict[str, str]: ...


class OfflineProvider:
    """Deterministic placeholder provider. No network, no randomness, no clock."""

    name = "offline"

    def draft(self, *, system: str, context: str, sections: list[Section]) -> dict[str, str]:
        out: dict[str, str] = {}
        for section_id, instruction in sections:
            out[section_id] = (
                f"_Drafted by the **offline** provider — replace with reviewed LLM "
                f"narrative before approval._\n\n"
                f"Drafting brief: {instruction}"
            )
        return out


def _build_prompt(system: str, context: str, sections: list[Section]) -> str:
    section_lines = "\n".join(f"- {sid}: {instr}" for sid, instr in sections)
    return (
        f"{system}\n\n"
        "Draft each requested section as grounded narrative. Cite the source "
        "artefact (file path or fact) for each claim. Do not invent facts; if a "
        "detail is not in the context, say so.\n\n"
        "Return ONLY a JSON object mapping each section id to its markdown text.\n\n"
        f"Sections:\n{section_lines}\n\n"
        f"=== CONTEXT (code + docs + metadata only; no raw data) ===\n{context}\n"
    )


def _parse_sections(raw: str, sections: list[Section]) -> dict[str, str]:
    try:
        data: Any = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ProviderError("LLM did not return valid JSON", hint=str(e)) from e
    if not isinstance(data, dict):
        raise ProviderError("LLM JSON was not an object of section_id -> text")
    return {sid: str(data.get(sid, "")) for sid, _ in sections}


class AzureOpenAIProvider:
    """Azure OpenAI (enterprise, no-retention terms). Lazy-imports `openai`."""

    name = "azure_openai"

    def draft(self, *, system: str, context: str, sections: list[Section]) -> dict[str, str]:
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")
        if not (endpoint and api_key and deployment):
            raise ProviderError(
                "Azure OpenAI not configured",
                hint="set AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT",
            )
        try:
            openai = importlib.import_module("openai")
        except ImportError as e:
            raise ProviderError("openai SDK not installed", hint="install the 'azure' extra") from e

        client: Any = openai.AzureOpenAI(
            azure_endpoint=endpoint, api_key=api_key, api_version=api_version
        )
        resp: Any = client.chat.completions.create(
            model=deployment,
            messages=[{"role": "user", "content": _build_prompt(system, context, sections)}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        return _parse_sections(resp.choices[0].message.content or "{}", sections)


class AnthropicProvider:
    """Anthropic (enterprise terms). Lazy-imports `anthropic`."""

    name = "anthropic"

    def draft(self, *, system: str, context: str, sections: list[Section]) -> dict[str, str]:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        if not api_key:
            raise ProviderError("Anthropic not configured", hint="set ANTHROPIC_API_KEY")
        try:
            anthropic = importlib.import_module("anthropic")
        except ImportError as e:
            raise ProviderError(
                "anthropic SDK not installed", hint="install the 'anthropic' extra"
            ) from e

        client: Any = anthropic.Anthropic(api_key=api_key)
        # The exhaustive default structure is ~25 sections; allow ample output.
        # (For very large outputs, drafting per-section in batches is a planned
        # enhancement — see ADR-0012 open questions.)
        msg: Any = client.messages.create(
            model=model,
            max_tokens=16384,
            messages=[{"role": "user", "content": _build_prompt(system, context, sections)}],
        )
        return _parse_sections(msg.content[0].text, sections)


_PROVIDERS: dict[str, type[Any]] = {
    "offline": OfflineProvider,
    "azure_openai": AzureOpenAIProvider,
    "anthropic": AnthropicProvider,
}


def get_provider(name: str) -> LLMProvider:
    """Return a provider instance by name (offline | azure_openai | anthropic)."""
    try:
        cls = _PROVIDERS[name]
    except KeyError as e:
        raise ProviderError(
            f"unknown provider {name!r}",
            hint=f"one of: {', '.join(sorted(_PROVIDERS))}",
        ) from e
    provider: LLMProvider = cls()
    return provider
