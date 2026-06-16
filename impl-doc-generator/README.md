# impl-doc-generator

**Implementation Document Generator (IDG)** — design in
[ADR-0012](../docs/adr/0012-implementation-document-generation.md).

Produces the per-model-version, LLM-assisted, **human-approved** "as-built"
**Implementation Document** — the counterpart to ABSA's development
documentation, recording *how EXL implemented the model*: optimizations, the
pipeline tier/schedule, data lineage, reconciliation approach, controls, and
every deviation from the design with rationale.

## Pipeline

```
build_context_bundle → guard_bundle → provider.draft → render_document
```

- **bundle.py** — assembles grounded facts (package + pipeline manifests, PIR,
  validation summary, digests, file inventory) and gathers the reviewable content
  (code + dev doc + schemas). Facts are pulled verbatim and are never LLM-authored.
- **docparse.py** — ingests the development document (`.md`/`.txt`, or `.pdf` /
  `.docx` via the `pdf` / `docx` extras), parses it into a **section outline**,
  and **budgets** a large document (a ~100-page dev doc) into the LLM context
  window section-by-section, with an explicit truncation marker so nothing is
  dropped silently.
- **guard.py** — the raw-data/PII guard (hard rule): the content set is code +
  docs + schemas + metadata only; raises on anything resembling a data payload
  (data extensions, data directories, oversized files, wholly-tabular blobs). A
  dev doc that merely *embeds* tables passes; a CSV/Parquet masquerading as a doc
  does not.
- **providers.py** — `offline` (deterministic, default), `azure_openai`,
  `anthropic`, behind one adapter. Cloud SDKs are lazy-imported, so the package
  installs + tests with neither SDK nor credentials.
- **document.py** — renders the markdown (facts verbatim + LLM narrative, clearly
  separated) + a provenance block, and computes the document digest
  (`implementation_doc_ref`). The **exhaustive 25-section + 3-appendix** structure
  is data-driven (`SECTION_SPECS` + `FACT_RENDERERS`) and is the platform default,
  **pending alignment with ABSA's agreed implementation-document outline** —
  swapping it is a localised edit, not a rewrite.

## CLI

```bash
generate-impl-doc \
  --package  packages/credit-risk-pd/1.0.0 \
  --pipeline pipelines/credit-risk-pd/1.0.0/manifest.json \
  --dev-doc  impl-doc-generator/examples/dev-doc-credit-risk-pd.md \
  --provider offline \
  --out      impl-doc-generator/examples/implementation-credit-risk-pd-1.0.0.md
```

Prints the `implementation_doc_ref` (sha256) that goes on the registry record.
`--provider offline` is the default and needs no network/keys. For a real run,
pass `--provider azure_openai` (env `AZURE_OPENAI_ENDPOINT` / `_API_KEY` /
`_DEPLOYMENT`) or `--provider anthropic` (env `ANTHROPIC_API_KEY`), and
`--approver "<name>"` to record sign-off (sets status APPROVED). Without an
approver the document is a **DRAFT** and is not platform evidence.

## Large development documents (PDF / DOCX, ~100 pages)

The dev doc is usually a **PDF or Word** file, not markdown, and can run to ~100
pages. Install the parser extra for the format you have:

```bash
uv pip install -e "impl-doc-generator[pdf]"    # pypdf, for .pdf
uv pip install -e "impl-doc-generator[docx]"   # python-docx, for .docx
```

The doc is parsed into sections and **budgeted** into the LLM context with
`--dev-doc-max-chars` (default 200,000). Whole sections are kept in order; any
that overflow the budget are listed by heading with a `[TRUNCATED FOR LLM
CONTEXT …]` marker — the full document stays the source of record, and its
outline + size + truncation status are recorded in the output (Appendix C) and
provenance. Raise `--dev-doc-max-chars` to widen the budget for a larger model.

## Data-minimisation (ADR-0012 hard rule)

The LLM receives **code + the dev document + schemas + metadata only — never raw
data rows or PII** (consistent with the data-residency posture in ADR-0001). The
guard enforces this before any provider is called; a violation stops the run
(`IDG020`), it is never silently skipped.

## Worked example

[`examples/implementation-credit-risk-pd-1.0.0.md`](examples/implementation-credit-risk-pd-1.0.0.md)
— generated from the committed `credit-risk-pd@1.0.0` package + pipeline manifest
+ the synthetic [dev doc](examples/dev-doc-credit-risk-pd.md), using the offline
provider. Reproducible with the CLI above (`--generated-at` pins the timestamp).

## Status

Generator built and fully tested (offline provider + worked example): exhaustive
25-section + 3-appendix structure, PDF/DOCX/markdown dev-doc ingestion, and
section-aware budgeting for ~100-page documents. Cloud LLM adapters are wired but
gated on the ABSA data-processing agreement (RAID DEP-09).

**Pending alignment / follow-ups (epic E14):** the section structure is the
platform default until ABSA supplies its agreed implementation-document outline;
per-section drafting for very large inputs (ADR-0012 open question 4); per-model
rollout across Group 1/2; and the `implementation_doc_ref` schema wiring into the
package manifest + registry record.
