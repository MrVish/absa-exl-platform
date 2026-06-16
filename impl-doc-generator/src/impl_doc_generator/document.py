"""Assemble the Implementation Document: grounded facts + LLM narrative.

Facts (PIR, digests, tier, validation summary) are rendered deterministically and
verbatim. Narrative sections are drafted by the provider and clearly labelled.
The document's digest is the ``implementation_doc_ref`` recorded on the registry
record; it is computed over the rendered markdown (LF-normalised), which does not
contain the digest itself.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from .bundle import ContextBundle
from .providers import LLMProvider, Section

IDG_VERSION = "0.1.0"
SIGNING_ALGORITHM = "RSASSA_PKCS1_V1_5_SHA_256"

SYSTEM_PROMPT = (
    "You are a model-implementation documentation assistant for a bank. You write "
    "the 'as-built' implementation record for a model hosted on the EXL platform, "
    "for SR 11-7 / ABSA GMRMG reviewers. Ground every statement in the provided "
    "context (code, the development document, schemas, platform metadata). Never "
    "invent facts. Where the implementation deviates from the development design, "
    "state the deviation and the rationale explicitly. Be precise and concise."
)

# (section_id, title, drafting instruction)
SECTION_SPECS: list[tuple[str, str, str]] = [
    (
        "model-summary",
        "Model summary",
        "Summarise what the model is, its intended use, owner, and version, from the dev doc.",
    ),
    (
        "inputs-lineage",
        "Inputs & data lineage",
        "Explain the inputs and how data is prepared/wired, per the PIR mapping and the data code.",
    ),
    (
        "scoring-logic",
        "Scoring logic as implemented",
        "Explain how the scoring code works and the optimizations EXL made vs the dev code.",
    ),
    (
        "pipeline-impl",
        "Pipeline implementation",
        "Describe the pipeline: tier, the Step Functions flow, schedule/cadence, and compute.",
    ),
    (
        "reconciliation",
        "Reconciliation approach",
        "Describe how outputs are validated against ABSA's benchmark, including tolerance bands.",
    ),
    (
        "controls-evidence",
        "Controls & evidence",
        "Summarise controls + evidence: signing, chain-of-custody digests, approvals, retention.",
    ),
    (
        "deviations",
        "Deviations & assumptions",
        "List every deviation from the dev design, each with a rationale, plus assumptions.",
    ),
    (
        "change-log",
        "Change log",
        "Note this version and what changed relative to any prior version.",
    ),
]


@dataclass
class ImplementationDocument:
    """The rendered document + its digest + provenance."""

    markdown: str
    doc_digest: str
    provenance: dict[str, Any]


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "_(none)_\n"
    head = "| " + " | ".join(headers) + " |\n"
    sep = "|" + "|".join("---" for _ in headers) + "|\n"
    body = "".join("| " + " | ".join(r) + " |\n" for r in rows)
    return head + sep + body


def _pir_rows(items: list[dict[str, Any]], with_source: bool) -> list[list[str]]:
    rows: list[list[str]] = []
    for it in items:
        name = str(it.get("name", ""))
        typ = str(it.get("type", ""))
        desc = str(it.get("description", "")).replace("|", "/")
        if with_source:
            rows.append(
                [name, typ, str(it.get("source", "")), "yes" if it.get("nullable") else "no", desc]
            )
        else:
            rows.append([name, typ, desc])
    return rows


def _validation_rows(checks: list[dict[str, Any]]) -> list[list[str]]:
    rows: list[list[str]] = []
    for c in checks:
        codes = ", ".join(str(x) for x in c.get("codes", [])) or "—"
        rows.append([str(c.get("name", "")), str(c.get("finding_count", 0)), codes])
    return rows


def _build_context(bundle: ContextBundle) -> str:
    """The text handed to the provider — facts summary + reviewable content."""
    parts: list[str] = []
    parts.append(
        f"MODEL: {bundle.model_name} v{bundle.model_version}\n"
        f"PIPELINE TIER: {bundle.tier}\n"
        f"PACKAGE DIGEST: {bundle.package_digest}\n"
        f"PIR INPUTS: {bundle.pir_inputs}\n"
        f"PIR OUTPUTS: {bundle.pir_outputs}\n"
        f"VALIDATION CHECKS: {bundle.validation_checks}\n"
    )
    for cf in bundle.content_files:
        parts.append(f"--- FILE: {cf.path} ({cf.kind}) ---\n{cf.text}")
    return "\n\n".join(parts)


def render_document(
    bundle: ContextBundle,
    provider: LLMProvider,
    *,
    generated_at: str,
    approver: str | None = None,
    status: str = "DRAFT",
) -> ImplementationDocument:
    """Render the Implementation Document for ``bundle`` using ``provider``."""
    context = _build_context(bundle)
    sections: list[Section] = [(sid, instr) for sid, _title, instr in SECTION_SPECS]
    narrative = provider.draft(system=SYSTEM_PROMPT, context=context, sections=sections)

    pipeline_digest = bundle.pipeline_digest or "(no pipeline manifest)"
    provenance: dict[str, Any] = {
        "idg_version": IDG_VERSION,
        "llm_provider": provider.name,
        "generated_at": generated_at,
        "status": status,
        "approver": approver or "PENDING REVIEW",
        "input_digests": bundle.input_digests(),
    }

    lines: list[str] = []
    lines.append(f"# Implementation Document — {bundle.model_name} {bundle.model_version}")
    lines.append("")
    lines.append(
        f"> **Status: {status}** · as-built record per "
        "[ADR-0012](../../../docs/adr/0012-implementation-document-generation.md). "
        "Platform **facts** are injected verbatim; **narrative** is LLM-drafted and "
        "requires human review before approval."
    )
    lines.append("")
    lines.append("## Provenance")
    lines.append("")
    lines.append(
        _md_table(
            ["Field", "Value"],
            [
                ["IDG version", IDG_VERSION],
                ["LLM provider", provider.name],
                ["Generated at", generated_at],
                ["Status", status],
                ["Approver", approver or "**PENDING REVIEW**"],
                ["Package manifest digest", bundle.package_digest or "—"],
                ["Pipeline manifest digest", pipeline_digest],
            ],
        )
    )

    def emit(section_id: str, title: str, facts_md: str = "") -> None:
        lines.append(f"## {title}")
        lines.append("")
        if facts_md:
            lines.append("**Facts (verbatim from platform artefacts):**")
            lines.append("")
            lines.append(facts_md)
        lines.append("**Narrative:**")
        lines.append("")
        lines.append(narrative.get(section_id, "_(not drafted)_"))
        lines.append("")

    titles = {sid: title for sid, title, _ in SECTION_SPECS}
    emit(
        "model-summary",
        titles["model-summary"],
        f"Model {bundle.model_name} v{bundle.model_version}; pipeline tier {bundle.tier}.\n",
    )
    emit(
        "inputs-lineage",
        titles["inputs-lineage"],
        "Inputs:\n\n"
        + _md_table(
            ["name", "type", "source", "nullable", "description"],
            _pir_rows(bundle.pir_inputs, with_source=True),
        )
        + "\nOutputs:\n\n"
        + _md_table(
            ["name", "type", "description"], _pir_rows(bundle.pir_outputs, with_source=False)
        ),
    )
    emit("scoring-logic", titles["scoring-logic"])
    upstream = (
        ", ".join(f"{r.get('ref', '?')} ({r.get('type', '?')})" for r in bundle.upstream_refs)
        or "—"
    )
    emit(
        "pipeline-impl",
        titles["pipeline-impl"],
        f"Tier {bundle.tier}; upstream: {upstream}; pipeline digest {pipeline_digest}.\n",
    )
    emit("reconciliation", titles["reconciliation"])
    emit(
        "controls-evidence",
        titles["controls-evidence"],
        _md_table(["checker", "findings", "codes"], _validation_rows(bundle.validation_checks))
        + f"\nSigning: `{SIGNING_ALGORITHM}` (KMS asymmetric CMK). "
        f"Chain-of-custody digest anchors package -> pipeline -> registry.\n",
    )
    emit("deviations", titles["deviations"])
    emit(
        "change-log",
        titles["change-log"],
        _md_table(["version", "note"], [[bundle.model_version, "initial implementation"]]),
    )

    lines.append("---")
    lines.append("")
    lines.append(
        "*Facts above are sourced verbatim from the package + pipeline manifests, "
        "the PIR mapping, and the validation summary. Narrative sections are "
        "LLM-drafted and must be human-reviewed before this document is approved.*"
    )
    lines.append("")

    markdown = "\n".join(lines)
    doc_digest = hashlib.sha256(markdown.replace("\r\n", "\n").encode("utf-8")).hexdigest()
    return ImplementationDocument(markdown=markdown, doc_digest=doc_digest, provenance=provenance)
