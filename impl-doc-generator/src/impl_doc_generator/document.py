"""Assemble the Implementation Document: grounded facts + LLM narrative.

Facts (PIR, digests, tier, validation summary, file inventory, dev-doc outline)
are rendered deterministically and verbatim. Narrative sections are drafted by
the provider and clearly labelled. The document's digest is the
``implementation_doc_ref`` recorded on the registry record; it is computed over
the rendered markdown (LF-normalised), which does not contain the digest itself.

The section set (``SECTION_SPECS``) is the platform **default** — an exhaustive
"as-built" structure aligned to SR 11-7 (model implementation), ABSA GMRMG, and
the platform's chain-of-custody. It is data-driven on purpose: ABSA's agreed
implementation-document structure replaces/extends this list with no change to
the rendering engine. Each section is narrative-by-default; sections that have
deterministic platform facts attach them via ``FACT_RENDERERS``.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .bundle import ContextBundle
from .providers import LLMProvider, Section

IDG_VERSION = "0.1.0"
SIGNING_ALGORITHM = "RSASSA_PKCS1_V1_5_SHA_256"
GOVERNING_STANDARDS = "SR 11-7 (model implementation), ABSA GMRMG, SARB GOI, POPIA"

SYSTEM_PROMPT = (
    "You are a model-implementation documentation assistant for a bank. You write "
    "the 'as-built' implementation record for a model hosted on the EXL platform, "
    "for SR 11-7 / ABSA GMRMG reviewers. Ground every statement in the provided "
    "context (code, the development document, schemas, platform metadata). Never "
    "invent facts. Where the implementation deviates from the development design, "
    "state the deviation and the rationale explicitly. Where the context does not "
    "contain a detail a section asks for, say so plainly rather than guessing. Be "
    "precise and concise, and cite the source artefact (file path or fact) per claim."
)

# (section_id, title, drafting instruction). The platform default — exhaustive
# and data-driven; ALIGN/REPLACE with ABSA's agreed structure when supplied.
SECTION_SPECS: list[tuple[str, str, str]] = [
    (
        "executive-summary",
        "1. Executive summary",
        "As-built overview: what was implemented, tier, cadence, and current status.",
    ),
    (
        "model-identification",
        "2. Model identification & governance",
        "State model name, version, owner, model-risk tier, and governing standards.",
    ),
    (
        "intended-use",
        "3. Intended use & restrictions",
        "From the dev doc: intended use, approved scope, exclusions, and limitations.",
    ),
    (
        "methodology",
        "4. Model methodology (as documented)",
        "Summarise the model methodology and theory from the development document.",
    ),
    (
        "inputs-lineage",
        "5. Inputs & data lineage",
        "Explain the inputs and how data is sourced/wired, per the PIR and data code.",
    ),
    (
        "feature-engineering",
        "6. Feature engineering & transformations",
        "Describe how raw inputs become model features in the data/scoring code.",
    ),
    (
        "data-quality",
        "7. Data quality & validation controls",
        "Describe the DQ checks and the Code Intake validation results for the package.",
    ),
    (
        "outputs",
        "8. Outputs & downstream consumption",
        "Explain the outputs, the output contract, and how results are consumed.",
    ),
    (
        "scoring-logic",
        "9. Scoring logic as implemented",
        "Explain step by step how the scoring code computes the result, from the code.",
    ),
    (
        "optimizations",
        "10. Implementation optimizations & changes",
        "Describe optimizations EXL made vs the dev code and why behaviour is preserved.",
    ),
    (
        "pipeline-impl",
        "11. Pipeline architecture",
        "Describe the pipeline: tier, the Step Functions flow, compute, and where it runs.",
    ),
    (
        "scheduling",
        "12. Scheduling, cadence & SLAs",
        "Describe the run schedule/cadence, expected runtime, and any SLA targets.",
    ),
    (
        "environment",
        "13. Environment & dependencies",
        "Describe the runtime environment and pinned dependencies used to run the model.",
    ),
    (
        "code-inventory",
        "14. Code inventory & structure",
        "Walk through the package file layout and each component's responsibility.",
    ),
    (
        "reconciliation",
        "15. Reconciliation & benchmark validation",
        "Describe reconciliation vs ABSA's benchmark, including tolerance bands.",
    ),
    (
        "monitoring",
        "16. Monitoring & performance tracking",
        "Describe post-deployment monitoring: drift, volumes, stability, and alerting.",
    ),
    (
        "security",
        "17. Security & access controls",
        "Describe IAM, KMS, cross-account boundaries, and the data-residency posture.",
    ),
    (
        "chain-of-custody",
        "18. Chain-of-custody & signing evidence",
        "Explain the digest anchor and signing binding package, pipeline, and registry.",
    ),
    (
        "approvals",
        "19. Approvals & sign-off",
        "Record the approval path (CAB/IVU) and the registry approval state.",
    ),
    (
        "deviations",
        "20. Deviations from the development design",
        "List every deviation from the dev design, each with an explicit rationale.",
    ),
    (
        "assumptions",
        "21. Assumptions & constraints",
        "List assumptions made during implementation and any operating constraints.",
    ),
    (
        "limitations",
        "22. Known limitations & residual risks",
        "List known limitations and residual risks of the implementation.",
    ),
    (
        "rollback-dr",
        "23. Rollback, DR & operational runbook",
        "Describe rollback, DR posture, and the operational runbook for this model.",
    ),
    (
        "change-log",
        "24. Change log",
        "Note this version and what changed relative to any prior version.",
    ),
    (
        "open-items",
        "25. Open items & follow-ups",
        "List outstanding items, pending approvals, or known TODOs.",
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
        return "_(none recorded — see narrative)_\n"
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


def _dev_doc_descriptor(b: ContextBundle) -> str:
    if not b.dev_doc_present:
        return "no development document supplied"
    pages = f"{b.dev_doc_pages} pages, " if b.dev_doc_pages else ""
    budget = "; budgeted for LLM context" if b.dev_doc_truncated else "; sent in full"
    return (
        f"{b.dev_doc_format}, {pages}{b.dev_doc_chars:,} chars, "
        f"{len(b.dev_doc_section_titles)} sections{budget}"
    )


# --- deterministic fact blocks, keyed by section id -------------------------


def _fact_exec(b: ContextBundle) -> str:
    return (
        f"Model **{b.model_name} v{b.model_version}**; pipeline tier **{b.tier}**; "
        f"package digest `{(b.package_digest or '—')[:16]}…`. "
        f"Development document: {_dev_doc_descriptor(b)}.\n"
    )


def _fact_model_id(b: ContextBundle) -> str:
    return _md_table(
        ["Field", "Value"],
        [
            ["Model name", b.model_name],
            ["Version", b.model_version],
            ["Pipeline tier", b.tier],
            ["Governing standards", GOVERNING_STANDARDS],
            ["Package manifest digest", b.package_digest or "—"],
            ["Pipeline manifest digest", b.pipeline_digest or "(no pipeline manifest)"],
        ],
    )


def _fact_inputs(b: ContextBundle) -> str:
    return "Inputs (from PIR mapping):\n\n" + _md_table(
        ["name", "type", "source", "nullable", "description"],
        _pir_rows(b.pir_inputs, with_source=True),
    )


def _fact_outputs(b: ContextBundle) -> str:
    return "Outputs (from PIR mapping):\n\n" + _md_table(
        ["name", "type", "description"], _pir_rows(b.pir_outputs, with_source=False)
    )


def _fact_dq(b: ContextBundle) -> str:
    return "Code Intake validation summary:\n\n" + _md_table(
        ["checker", "findings", "codes"], _validation_rows(b.validation_checks)
    )


def _fact_environment(b: ContextBundle) -> str:
    configs = [f for f in b.file_inventory if f.kind == "config"]
    py = sum(1 for f in b.file_inventory if f.kind == "code-python")
    sas = sum(1 for f in b.file_inventory if f.kind == "code-sas")
    rows = [[c.path, c.sha256[:12] + "…"] for c in configs]
    return (
        f"Runtime: Python 3.12 (per package pyproject); {py} Python file(s), "
        f"{sas} SAS file(s). Pinned configuration artefacts:\n\n"
        + _md_table(["config artefact", "sha256"], rows)
    )


def _fact_code_inventory(b: ContextBundle) -> str:
    rows = [[f.path, f.kind, f.sha256[:12] + "…"] for f in b.file_inventory]
    return _md_table(["path", "kind", "sha256"], rows)


def _fact_pipeline(b: ContextBundle) -> str:
    upstream = (
        ", ".join(f"{r.get('ref', '?')} ({r.get('type', '?')})" for r in b.upstream_refs) or "—"
    )
    return (
        f"Tier **{b.tier}**; upstream refs: {upstream}; "
        f"pipeline manifest digest `{(b.pipeline_digest or '—')}`.\n"
    )


def _fact_chain(b: ContextBundle) -> str:
    return (
        f"Signing: `{SIGNING_ALGORITHM}` (KMS asymmetric CMK, cross-account verify). "
        "The digest anchor binds package → pipeline → registry: the package digest "
        "equals the pipeline's first upstream ref, which is recorded on the registry "
        "record. Tamper-evidence is end-to-end.\n\n"
        + _md_table(
            ["artefact", "digest"],
            [
                ["Package manifest", b.package_digest or "—"],
                ["Pipeline manifest", b.pipeline_digest or "(no pipeline manifest)"],
            ],
        )
    )


def _fact_changelog(b: ContextBundle) -> str:
    return _md_table(["version", "note"], [[b.model_version, "initial implementation"]])


FACT_RENDERERS: dict[str, Callable[[ContextBundle], str]] = {
    "executive-summary": _fact_exec,
    "model-identification": _fact_model_id,
    "inputs-lineage": _fact_inputs,
    "outputs": _fact_outputs,
    "data-quality": _fact_dq,
    "environment": _fact_environment,
    "code-inventory": _fact_code_inventory,
    "pipeline-impl": _fact_pipeline,
    "chain-of-custody": _fact_chain,
    "change-log": _fact_changelog,
}


def _build_context(bundle: ContextBundle) -> str:
    """The text handed to the provider — facts summary + reviewable content."""
    parts: list[str] = []
    toc = "; ".join(bundle.dev_doc_section_titles) or "(none)"
    parts.append(
        f"MODEL: {bundle.model_name} v{bundle.model_version}\n"
        f"PIPELINE TIER: {bundle.tier}\n"
        f"PACKAGE DIGEST: {bundle.package_digest}\n"
        f"PIPELINE DIGEST: {bundle.pipeline_digest}\n"
        f"PIR INPUTS: {bundle.pir_inputs}\n"
        f"PIR OUTPUTS: {bundle.pir_outputs}\n"
        f"VALIDATION CHECKS: {bundle.validation_checks}\n"
        f"DEV DOC: {_dev_doc_descriptor(bundle)}\n"
        f"DEV DOC OUTLINE: {toc}\n"
    )
    for cf in bundle.content_files:
        parts.append(f"--- FILE: {cf.path} ({cf.kind}) ---\n{cf.text}")
    return "\n\n".join(parts)


def _render_appendices(bundle: ContextBundle) -> list[str]:
    lines: list[str] = []

    lines.append("## Appendix A — File inventory & digests")
    lines.append("")
    lines.append(_fact_code_inventory(bundle))

    lines.append("## Appendix B — Source artefact provenance")
    lines.append("")
    rows = [[k, v] for k, v in bundle.input_digests().items()]
    lines.append(_md_table(["artefact", "digest"], rows))

    lines.append("## Appendix C — Development document outline")
    lines.append("")
    lines.append(f"Source: {_dev_doc_descriptor(bundle)}.")
    lines.append("")
    if bundle.dev_doc_section_titles:
        lines.append(
            _md_table(
                ["#", "section"],
                [[str(i + 1), t] for i, t in enumerate(bundle.dev_doc_section_titles)],
            )
        )
    else:
        lines.append("_(no development document supplied)_")
    if bundle.dev_doc_truncated:
        lines.append("")
        lines.append(
            "> ⚠️ The development document exceeded the LLM context budget; trailing "
            "sections were summarised by heading (the full document remains the "
            "source of record). Increase `--dev-doc-max-chars` to widen the budget."
        )
    lines.append("")
    return lines


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
        "section_count": len(SECTION_SPECS),
        "dev_doc": {
            "present": bundle.dev_doc_present,
            "format": bundle.dev_doc_format,
            "pages": bundle.dev_doc_pages,
            "chars": bundle.dev_doc_chars,
            "sections": len(bundle.dev_doc_section_titles),
            "truncated_for_llm": bundle.dev_doc_truncated,
        },
    }

    lines: list[str] = []
    lines.append(f"# Implementation Document — {bundle.model_name} {bundle.model_version}")
    lines.append("")
    lines.append(
        f"> **Status: {status}** · as-built record per "
        "[ADR-0012](../../../docs/adr/0012-implementation-document-generation.md). "
        "Platform **facts** are injected verbatim; **narrative** is LLM-drafted and "
        "requires human review before approval. Section structure is the platform "
        "default, pending alignment with ABSA's agreed implementation-document outline."
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
                ["Sections", str(len(SECTION_SPECS))],
                ["Package manifest digest", bundle.package_digest or "—"],
                ["Pipeline manifest digest", pipeline_digest],
                ["Development document", _dev_doc_descriptor(bundle)],
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

    for sid, title, _instr in SECTION_SPECS:
        renderer = FACT_RENDERERS.get(sid)
        emit(sid, title, renderer(bundle) if renderer else "")

    lines.extend(_render_appendices(bundle))

    lines.append("---")
    lines.append("")
    lines.append(
        "*Facts above are sourced verbatim from the package + pipeline manifests, "
        "the PIR mapping, the validation summary, and the package file inventory. "
        "Narrative sections are LLM-drafted and must be human-reviewed before this "
        "document is approved and its digest recorded as `implementation_doc_ref`.*"
    )
    lines.append("")

    markdown = "\n".join(lines)
    doc_digest = hashlib.sha256(markdown.replace("\r\n", "\n").encode("utf-8")).hexdigest()
    return ImplementationDocument(markdown=markdown, doc_digest=doc_digest, provenance=provenance)
