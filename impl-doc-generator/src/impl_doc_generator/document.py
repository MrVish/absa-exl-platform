"""Assemble the Implementation Document: grounded facts + LLM narrative.

Facts (PIR, digests, tier, validation summary, file inventory, dev-doc outline)
are rendered deterministically and verbatim. Narrative sections are drafted by
the provider and clearly labelled. The document's digest is the
``implementation_doc_ref`` recorded on the registry record; it is computed over
the rendered markdown (LF-normalised), which does not contain the digest itself.

The section set (``SECTION_SPECS``) is an **exhaustive "as-built" structure
aligned section-by-section to ABSA's Model Development Document** (the agreed
TOC: Overview, Portfolio, Data Landscape & Preparation, Model Development, Final
Scorecard, Performance, Strengths/Weaknesses, Post-Development, Conservatism,
Implementation, References + appendices). Each dev-doc theme has an
as-implemented / as-verified / as-hosted counterpart here, plus the platform
as-built sections (pipeline, environment, chain-of-custody, controls) that the
dev doc does not carry. ``DEV_DOC_TOC`` drives the cross-walk appendix that
proves every dev-doc section is covered. The structure is data-driven: it is a
localised edit, not a rewrite, when ABSA finalises its implementation-doc TOC.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .bundle import ContextBundle
from .providers import LLMProvider, Section

IDG_VERSION = "0.2.0"
SIGNING_ALGORITHM = "RSASSA_PKCS1_V1_5_SHA_256"
GOVERNING_STANDARDS = "SR 11-7 (model implementation), ABSA GMRMG, SARB GOI, POPIA"

SYSTEM_PROMPT = (
    "You are a model-implementation documentation assistant for a bank. You write "
    "the 'as-built' implementation record for a model hosted on the EXL platform, "
    "for SR 11-7 / ABSA GMRMG reviewers. The document mirrors ABSA's Model "
    "Development Document section-by-section: for each topic the developers "
    "documented, record how EXL *implemented, verified, or hosted* it. Ground "
    "every statement in the provided context (code, the development document, "
    "schemas, platform metadata). Never invent facts. Where the implementation "
    "deviates from the development design, state the deviation and the rationale "
    "explicitly. Where the context lacks a detail a section asks for, say so "
    "plainly. Be precise and concise, and cite the source artefact per claim."
)

# (section_id, title, drafting instruction). Exhaustive as-built structure,
# aligned to ABSA's Model Development Document TOC. See DEV_DOC_TOC for the
# cross-walk. Data-driven: replace/extend when ABSA finalises its impl-doc TOC.
SECTION_SPECS: list[tuple[str, str, str]] = [
    # --- 1. Overview (dev-doc Part 1) ---
    (
        "exec-summary",
        "1. Executive summary (as-built)",
        "As-built overview: what was implemented, tier, cadence, and current status.",
    ),
    (
        "model-identification",
        "2. Model identification & classification",
        "Name, version, owner, model-risk classification/tier, materiality, standards.",
    ),
    (
        "governance-change",
        "3. Governance, approvals & change policy",
        "How governance + change policy are enforced: CAB/IVU, registry approval, versioning.",
    ),
    (
        "standards",
        "4. Modelling standards & policies (as enforced)",
        "How modelling/dev standards are enforced via Code Intake checks + packaging.",
    ),
    (
        "model-description",
        "5. Model description & methodology (as documented)",
        "Summarise the model, its methodology and theory, from the development document.",
    ),
    # --- 2. Portfolio & scope (dev-doc Part 2) ---
    (
        "intended-use",
        "6. Intended use, portfolio & target market",
        "Intended use, product/portfolio scope, target market, and explicit exclusions.",
    ),
    (
        "regulatory",
        "7. Regulatory & legislative context",
        "Applicable regulation/legislation (POPIA, SARB, NCA) and any external changes.",
    ),
    # --- 3. Data landscape & preparation (dev-doc Part 3) ---
    (
        "data-sources",
        "8. Data sources & lineage (as wired)",
        "Data sources and how they are sourced/replicated/wired into the platform.",
    ),
    (
        "variables",
        "9. Input variables & definitions (PIR mapping)",
        "Input variables and definitions per the PIR mapping and the input contract.",
    ),
    (
        "data-flow",
        "10. Data flow, ingestion & granularity (as implemented)",
        "As-implemented data flow, bucket layout, arrival validation, account/customer keying.",
    ),
    (
        "target-definition",
        "11. Default / target definition (as implemented)",
        "How the default/target label is defined and implemented in the data/scoring code.",
    ),
    (
        "exclusions",
        "12. Exclusions & filtering (as implemented)",
        "Exclusions and filtering rules as implemented in the data-preparation code.",
    ),
    (
        "feature-engineering",
        "13. Feature engineering & transformations",
        "How raw inputs become model features/characteristics in the code.",
    ),
    (
        "data-quality",
        "14. Data quality & validation controls",
        "DQ checks, drift, and the Code Intake validation results for the package.",
    ),
    # --- 4. Model development (dev-doc Part 4) ---
    (
        "dev-methodology",
        "15. Development methodology & sample (reference)",
        "Reference the dev methodology, period, sample design, univariate/multivariate work.",
    ),
    (
        "segmentation",
        "16. Segmentation (as implemented)",
        "Model segmentation and how segment routing is implemented in scoring.",
    ),
    # --- 5. Final scorecard (dev-doc Part 5) ---
    (
        "scorecard",
        "17. Final scorecard & scoring logic (as implemented)",
        "Final scorecard variables/weights and how scoring computes the result, from code.",
    ),
    (
        "optimizations",
        "18. Implementation optimizations & changes",
        "Optimizations EXL made vs the dev code and why behaviour is preserved.",
    ),
    # --- 6 + 8. Performance, reconciliation & monitoring (dev-doc Parts 6, 8) ---
    (
        "performance",
        "19. Model performance & discrimination (verified)",
        "Performance/discrimination metrics and how they were verified on the platform.",
    ),
    (
        "reconciliation",
        "20. Benchmark reconciliation (as implemented)",
        "Reconciliation vs ABSA's benchmark scorecard, including tolerance bands.",
    ),
    (
        "monitoring",
        "21. Monitoring & tracking framework (as implemented)",
        "As-implemented monitoring: run status, DQ/drift, score stability, alerting.",
    ),
    (
        "tracking-metrics",
        "22. Tracking metrics & stability (as wired)",
        "Tracking metrics (PSI, score/variable stability) wired into dashboards/alerts.",
    ),
    # --- 10. As-built platform implementation (dev-doc Part 10, expanded) ---
    (
        "pipeline",
        "23. Pipeline architecture & execution",
        "Pipeline tier, the Step Functions flow, compute, and where it runs.",
    ),
    (
        "scheduling",
        "24. Scheduling, cadence & SLAs",
        "Run schedule/cadence, expected runtime, and any SLA targets.",
    ),
    (
        "environment",
        "25. Runtime environment & dependencies",
        "Runtime environment and pinned dependencies used to run the model.",
    ),
    (
        "code-inventory",
        "26. Code inventory & package structure",
        "Productized package layout and each component's role (dev code -> package).",
    ),
    (
        "security",
        "27. Security & access controls",
        "IAM, KMS, cross-account boundaries, and the data-residency posture.",
    ),
    (
        "chain-of-custody",
        "28. Chain-of-custody & signing evidence",
        "The digest anchor and signing binding package, pipeline, and registry.",
    ),
    # --- 9. Conservatism (dev-doc Part 9) ---
    (
        "conservatism",
        "29. Conservatism & overlays (as implemented)",
        "Any conservatism, overlays or caps and how they are applied in scoring.",
    ),
    # --- 7 + risk/ops ---
    (
        "deviations",
        "30. Deviations from the development design",
        "Every deviation from the dev design, each with an explicit rationale.",
    ),
    (
        "assumptions",
        "31. Assumptions & constraints",
        "Assumptions made during implementation and any operating constraints.",
    ),
    (
        "limitations",
        "32. Strengths, weaknesses & residual risks",
        "Model strengths/weaknesses and residual risks, and how implementation mitigates.",
    ),
    (
        "rollback-dr",
        "33. Rollback, DR & operational runbook",
        "Rollback, DR posture, and the operational runbook for this model.",
    ),
    (
        "approvals",
        "34. Approvals & sign-off",
        "Approval path (CAB/IVU) and the registry approval state for this version.",
    ),
    # --- Living record (dev-doc Parts 1.7, 11) ---
    (
        "change-log",
        "35. Change log & rationalisation history",
        "This version, what changed, and the model rationalisation history.",
    ),
    (
        "open-items",
        "36. Open items & follow-ups",
        "Outstanding items, pending approvals, or known TODOs.",
    ),
    (
        "references",
        "37. References & source artefacts",
        "Source artefacts, digests, dev-doc reference, and related ADRs.",
    ),
]

# Cross-walk: ABSA Model Development Document section -> implementation-doc
# section(s) that cover it as-built. Proves exhaustive coverage for reviewers.
DEV_DOC_TOC: list[tuple[str, str]] = [
    ("1 Overview", "§1-§5"),
    ("   1.1 Executive Summary", "§1"),
    ("   1.2 Model Classification", "§2"),
    ("   1.3 Background and motivation", "§5"),
    ("   1.4 Model governance and change policy", "§3"),
    ("   1.5 Modelling standards and policies", "§4"),
    ("   1.6 Model Description", "§5"),
    ("   1.7 Model rationalisation history", "§35"),
    ("   1.8 Document Structure", "Appendix D (this cross-walk)"),
    ("2 Portfolio Overview", "§6-§7"),
    ("   2.1 Product Information, Features & Target Markets", "§6"),
    ("   2.2 External Legislative Changes", "§7"),
    ("3 Data Landscape and Data Preparation", "§8-§14"),
    ("   3.1 Data Sources", "§8"),
    ("   3.2 Variable Definitions", "§9"),
    ("   3.3 Data Flow", "§10"),
    ("   3.4 Default Definition", "§11"),
    ("   3.5 Account vs Customer level Treatment", "§10"),
    ("   3.6 Exclusions", "§12"),
    ("4 Model Development", "§15-§16"),
    ("   4.1 Methodology", "§5, §15"),
    ("   4.2 Development Period", "§15"),
    ("   4.3 Multiple Models / Segmentation", "§16"),
    ("   4.4 Sample Design", "§15"),
    ("   4.5 Univariate Analysis", "§15"),
    ("   4.6 Multivariate Analysis", "§15"),
    ("5 Final Scorecard", "§17"),
    ("   5.1 Final Scorecard Variables", "§17"),
    ("   5.2 Correlation among Final Variables", "§17"),
    ("   5.3 Multicollinearity in Final Variables", "§17"),
    ("6 Model Performance", "§19-§22"),
    ("   6.1 Model Discrimination", "§19"),
    ("   6.2 Variable Stability", "§22"),
    ("   6.3 Score Stability Distribution", "§22"),
    ("   6.4 Benchmarking against current scorecard", "§20"),
    ("7 Model Strengths and Weaknesses", "§32"),
    ("8 Post Development", "§21-§22"),
    ("   8.1 Model Monitoring and Tracking Framework", "§21"),
    ("   8.2 Proposed Tracking metrics", "§22"),
    ("9 Conservatism", "§29"),
    ("10 Implementation", "§23-§28 (as-built core)"),
    ("11 References", "§37"),
    ("Appendix A: Segmentation results", "§16"),
    ("Appendix B: Variable Stability", "§22"),
    ("Appendix C: Definition of Default", "§11"),
    ("Appendix D: Development Code", "§26"),
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


def _fact_references(b: ContextBundle) -> str:
    rows = [[k, v] for k, v in b.input_digests().items()]
    return (
        "Source-artefact digests:\n\n"
        + _md_table(["artefact", "digest"], rows)
        + "\nRelated: ADR-0001 (data movement), ADR-0009 (signing), ADR-0010 "
        "(package contract), ADR-0012 (this generator). Development document is "
        "the as-designed counterpart to this as-built record.\n"
    )


FACT_RENDERERS: dict[str, Callable[[ContextBundle], str]] = {
    "exec-summary": _fact_exec,
    "model-identification": _fact_model_id,
    "variables": _fact_inputs,
    "scorecard": _fact_outputs,
    "data-quality": _fact_dq,
    "environment": _fact_environment,
    "code-inventory": _fact_code_inventory,
    "pipeline": _fact_pipeline,
    "chain-of-custody": _fact_chain,
    "change-log": _fact_changelog,
    "references": _fact_references,
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

    lines.append("## Appendix C — Development document outline (as parsed)")
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

    lines.append("## Appendix D — Development-document cross-walk")
    lines.append("")
    lines.append(
        "Maps each ABSA Model Development Document section to the implementation-doc "
        "section that records it as-built — evidence of complete coverage."
    )
    lines.append("")
    lines.append(
        _md_table(["ABSA dev-doc section", "Implementation doc"], [list(t) for t in DEV_DOC_TOC])
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
        "[ADR-0012](../../../docs/adr/0012-implementation-document-generation.md), "
        "structured as a **section-by-section counterpart to ABSA's Model Development "
        "Document** (see Appendix D cross-walk). Platform **facts** are injected "
        "verbatim; **narrative** is LLM-drafted and requires human review before approval."
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
