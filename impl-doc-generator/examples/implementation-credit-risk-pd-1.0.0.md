# Implementation Document — credit-risk-pd 1.0.0

> **Status: DRAFT** · as-built record per [ADR-0012](../../../docs/adr/0012-implementation-document-generation.md). Platform **facts** are injected verbatim; **narrative** is LLM-drafted and requires human review before approval.

## Provenance

| Field | Value |
|---|---|
| IDG version | 0.1.0 |
| LLM provider | offline |
| Generated at | 2026-06-16T00:00:00+00:00 |
| Status | DRAFT |
| Approver | **PENDING REVIEW** |
| Package manifest digest | 654d040760572c54879c05154cc9b9c9a7af0b6faa504a20a0755e5bd6355028 |
| Pipeline manifest digest | 707de58b5ebe4135f6f68d153d81025e8f2f7105d6272122327f33ca26105874 |

## Model summary

**Facts (verbatim from platform artefacts):**

Model credit-risk-pd v1.0.0; pipeline tier standard.

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Summarise what the model is, its intended use, owner, and version, from the dev doc.

## Inputs & data lineage

**Facts (verbatim from platform artefacts):**

Inputs:

| name | type | source | nullable | description |
|---|---|---|---|---|
| income_band | float | customer.income_band_lookup | no | Discretised income tier (1..5) |
| tenure_months | int | customer.tenure_months | no | Months since account opening |
| delinquencies | float | customer.delinquencies_12m | yes | Count of 30+ DPD events in last 12 months |

Outputs:

| name | type | description |
|---|---|---|
| pd_score | float | Probability of default (0..1) |
| risk_band | string | HIGH / MEDIUM / LOW |

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Explain the inputs and how data is prepared/wired, per the PIR mapping and the data code.

## Scoring logic as implemented

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Explain how the scoring code works and the optimizations EXL made vs the dev code.

## Pipeline implementation

**Facts (verbatim from platform artefacts):**

Tier standard; upstream: credit-risk-pd@1.0.0 (package); pipeline digest 707de58b5ebe4135f6f68d153d81025e8f2f7105d6272122327f33ca26105874.

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Describe the pipeline: tier, the Step Functions flow, schedule/cadence, and compute.

## Reconciliation approach

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Describe how outputs are validated against ABSA's benchmark, including tolerance bands.

## Controls & evidence

**Facts (verbatim from platform artefacts):**

| checker | findings | codes |
|---|---|---|
| static_sas | 0 | — |
| schema | 0 | — |
| pir | 0 | — |
| static_python | 0 | — |
| tests | 0 | — |

Signing: `RSASSA_PKCS1_V1_5_SHA_256` (KMS asymmetric CMK). Chain-of-custody digest anchors package -> pipeline -> registry.

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Summarise controls + evidence: signing, chain-of-custody digests, approvals, retention.

## Deviations & assumptions

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: List every deviation from the dev design, each with a rationale, plus assumptions.

## Change log

**Facts (verbatim from platform artefacts):**

| version | note |
|---|---|
| 1.0.0 | initial implementation |

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Note this version and what changed relative to any prior version.

---

*Facts above are sourced verbatim from the package + pipeline manifests, the PIR mapping, and the validation summary. Narrative sections are LLM-drafted and must be human-reviewed before this document is approved.*
