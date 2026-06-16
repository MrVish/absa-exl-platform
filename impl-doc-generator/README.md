# impl-doc-generator

**Implementation Document Generator (IDG).** Not built yet — planned as epic
**E14** in the delivery plan; design in
[ADR-0012](../docs/adr/0012-implementation-document-generation.md).

Produces the per-model-version, LLM-assisted, **human-approved** "as-built"
**Implementation Document** — the counterpart to ABSA's development
documentation, recording *how EXL implemented the model*: optimizations, the
pipeline tier/schedule, data lineage, reconciliation approach, controls, and
every deviation from the design with rationale.

Key design points (see ADR-0012):

- **Facts grounded, narrative drafted** — deterministic platform facts (package
  + pipeline manifests, registry record, validation summary, digests) are
  injected verbatim; an LLM drafts only the narrative.
- **Provider adapter** — Azure OpenAI / Anthropic, swappable by config.
- **Data-minimisation guard (hard rule)** — the LLM receives code + dev doc +
  schemas + metadata only; **never raw data rows or PII**.
- **Human-in-the-loop + provenance** — SAS owner + Tech Lead approve; the doc
  records provider/version, input digests, and approver.
- **Living + version-anchored** — `packages/<name>/<version>/implementation.md`,
  digest-referenced from the registry record via `implementation_doc_ref`.

Sits in Track A between Pipeline Factory and registration. See
[docs/architecture/](../docs/architecture/README.md) (Track A) and the root
[README §1.5](../README.md).
