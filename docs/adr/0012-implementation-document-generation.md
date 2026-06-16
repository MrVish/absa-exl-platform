# ADR-0012: LLM-assisted Implementation Document generation

| Field | Value |
| --- | --- |
| Status | Proposed |
| Date | 2026-06-16 |
| Deciders | Vishnu S (EXL ML Platform), Tech Lead |
| Consulted | ABSA Model Risk, ABSA Compliance (LLM data-processing terms), EXL Security |
| Related | [ADR-0006](0006-contract-strategy-json-schema-canonical.md), [ADR-0007](0007-registry-data-model-and-api.md), [ADR-0010](0010-productized-package-contract.md), [ADR-0001](0001-data-movement-s3-replication.md) |

## Context

ABSA delivers each model with **development documentation** (what the model is,
the methodology, the input variables, intended use, assumptions, limitations)
alongside the scoring code and the data code. What the platform does not produce
today is the **"as-built" counterpart**: a document that states *how EXL actually
implemented the model* on the hosting platform — the optimizations made, the
pipeline tier and schedule, the data lineage as wired, the reconciliation
approach, and every deviation from the development design with its rationale.

This is not a nice-to-have. **SR 11-7 (III — model implementation), ABSA GMRMG,
and SARB GOI all expect implementation evidence** — "how was this model put into
production, and how do we know it matches what was designed?" Producing that by
hand for 10 models (then ongoing) is slow and inconsistent. An LLM can draft it
well from the artefacts we already hold, provided the facts are grounded and a
human owns accuracy.

## Decision

Build an **Implementation Document Generator (IDG)** — a new workspace component
+ CLI — that produces a **per-model-version Implementation Document**, an
LLM-drafted, human-approved, living "as-built" record.

### What the document contains

A structured `implementation.md` (rendered to PDF for sign-off):

1. **Model summary** — from the dev doc: what it is, intended use, owner, version.
2. **Inputs & data lineage** — inputs consumed, PIR mapping, input contract, how
   data is prepared (data code), DQ checks applied.
3. **Scoring logic as implemented** — how the scoring code works, and the
   optimizations EXL made relative to the developer's code.
4. **Pipeline implementation** — tier (standard/scalable/realtime), the ASL flow,
   schedule/cadence, compute, where it runs.
5. **Reconciliation approach** — how outputs are validated against ABSA
   benchmarks; tolerance bands.
6. **Controls & evidence** — signing, chain-of-custody digests, approvals
   (CAB/IVU), retention.
7. **Deviations & assumptions** — explicit list of where the implementation
   differs from the dev doc, each with justification.
8. **Change log** — version history (the "living" dimension).

### How it is generated — facts are grounded, narrative is drafted

- The IDG assembles a **deterministic context bundle** from artefacts the
  platform already holds: the package + pipeline manifests (tier, ASL, schedule,
  digests), the registry record, the Code Intake validation summary, `pir.yaml`,
  and the input schemas. **These facts are injected verbatim and are never
  LLM-authored.**
- The LLM drafts only the **narrative** sections (model summary, scoring-logic
  explanation, deviation analysis) from the dev doc + code. The rendered document
  clearly distinguishes **platform-sourced facts** from **LLM-drafted narrative**.
- The LLM is instructed to **cite the source artefact** for each claim; ungrounded
  claims are a review-rejection criterion.

### LLM provider — managed enterprise service, behind an adapter

- The drafting LLM is a **managed enterprise service — Azure OpenAI or Anthropic**
  — accessed through a **provider adapter** so the choice is configuration and is
  swappable. Use enterprise terms only: **no prompt retention / no training on our
  data**, region-pinned, accessed over a controlled channel.
- **Hard data-minimisation guard (non-negotiable):** the context bundle sent to
  the LLM contains **code + the development document + schemas + platform metadata
  only — never raw data rows, never PII**. This keeps IDG consistent with the
  data-residency posture (ADR-0001): raw PII stays in ABSA, and even model-ready
  *data* is not sent — only the *code* that processes it and the *documentation*
  about it. A pre-flight checker fails the run if the bundle contains anything
  resembling a data payload.

### Governance — human-in-the-loop + provenance

- The LLM **drafts**; the model's **SAS owner + Tech Lead review and approve**.
  Only an **approved** document becomes part of the model's record. The LLM
  accelerates; humans own accuracy. (Auto-publishing without review is rejected —
  see Alternatives.)
- Every document records its **provenance**: the provider + model + version that
  produced each draft, the input artefact **digests**, and the **human approver** —
  so the document itself is auditable.

### Living + versioned, anchored to the model version

- One implementation document **per model version**, stored at
  `packages/<name>/<version>/implementation.md` (approved PDF in S3 next to the
  signed manifest).
- A new field **`implementation_doc_ref`** is added to the package-manifest
  payload (same digest-reference pattern as `python_pyproject_ref` from ADR-0010)
  and surfaced on the registry record — so the implementation doc is part of the
  chain-of-custody and a model version cannot be considered "implemented" without
  it.
- Re-versioning a model regenerates the document; the change-log section captures
  the diff.

### Where it sits in Track A

Between **Pipeline Factory generate** and **registration**: once the package is
validated and the pipeline manifest exists (the "how we implement" facts are
known), the IDG drafts the document → human approval → `implementation_doc_ref`
is recorded at registration.

## Consequences

### Positive
- Produces SR 11-7 / GMRMG implementation evidence as a **by-product of
  onboarding**, consistently, for every model + version.
- The deviation/assumption section forces explicit, reviewed reconciliation
  between design and implementation — exactly what model-risk reviewers probe.
- Living + version-anchored: the document can never silently drift from the
  hosted model version (it's digest-referenced).
- Provider-agnostic adapter avoids lock-in and lets ABSA approve the specific
  service under their terms.

### Negative
- Introduces an **external managed LLM** into the toolchain — requires an ABSA-
  approved data-processing agreement and a region/terms decision before first
  real use (open question below). The data-minimisation guard mitigates the
  residency concern but the DPA is still a gate.
- LLM drafts can be wrong or confabulate — mitigated by grounding + the mandatory
  human review, but review effort is real (~0.5 d/model).
- Adds a step to Track A and a field to the package contract (schema bump +
  regenerated models).

### Neutral
- The document is markdown-first (diff-able, versioned in git) with a rendered
  PDF for sign-off — same dual-form pattern as other evidence.

## Alternatives considered

1. **Manual authoring.** Rejected as the default: slow, inconsistent across 10+
   models, and the artefacts to ground it already exist. (Manual remains the
   fallback if the LLM DPA is not approved in time.)
2. **Fully automated, no human review.** Rejected: model-risk governance requires
   a human accountable for implementation evidence; an unreviewed LLM document
   cannot be regulatory evidence.
3. **Bedrock in-EXL-account (Claude/Titan).** Considered (keeps inference fully
   in-boundary). Deferred in favour of Azure OpenAI / Anthropic managed services
   per delivery direction; the provider adapter keeps Bedrock available as a
   future swap with no architecture change.
4. **Send raw/model-ready data to the LLM for richer context.** Rejected on
   data-residency grounds — the data-minimisation guard forbids it.

## Open questions

1. **Primary provider** — Azure OpenAI vs Anthropic (the adapter supports both;
   which is primary for the first models?).
2. **Data-processing terms** — ABSA-approved enterprise agreement (no retention /
   no training), region pinning, and the approved channel. Gates first real use.
3. **PDF rendering toolchain** in the EXL CI/runtime (markdown → PDF).
