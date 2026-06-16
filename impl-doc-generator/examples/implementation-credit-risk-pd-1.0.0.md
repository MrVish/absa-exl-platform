# Implementation Document — credit-risk-pd 1.0.0

> **Status: DRAFT** · as-built record per [ADR-0012](../../../docs/adr/0012-implementation-document-generation.md). Platform **facts** are injected verbatim; **narrative** is LLM-drafted and requires human review before approval. Section structure is the platform default, pending alignment with ABSA's agreed implementation-document outline.

## Provenance

| Field | Value |
|---|---|
| IDG version | 0.1.0 |
| LLM provider | offline |
| Generated at | 2026-06-16T00:00:00+00:00 |
| Status | DRAFT |
| Approver | **PENDING REVIEW** |
| Sections | 25 |
| Package manifest digest | 654d040760572c54879c05154cc9b9c9a7af0b6faa504a20a0755e5bd6355028 |
| Pipeline manifest digest | 707de58b5ebe4135f6f68d153d81025e8f2f7105d6272122327f33ca26105874 |
| Development document | md, 1,270 chars, 7 sections; sent in full |

## 1. Executive summary

**Facts (verbatim from platform artefacts):**

Model **credit-risk-pd v1.0.0**; pipeline tier **standard**; package digest `654d040760572c54…`. Development document: md, 1,270 chars, 7 sections; sent in full.

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: As-built overview: what was implemented, tier, cadence, and current status.

## 2. Model identification & governance

**Facts (verbatim from platform artefacts):**

| Field | Value |
|---|---|
| Model name | credit-risk-pd |
| Version | 1.0.0 |
| Pipeline tier | standard |
| Governing standards | SR 11-7 (model implementation), ABSA GMRMG, SARB GOI, POPIA |
| Package manifest digest | 654d040760572c54879c05154cc9b9c9a7af0b6faa504a20a0755e5bd6355028 |
| Pipeline manifest digest | 707de58b5ebe4135f6f68d153d81025e8f2f7105d6272122327f33ca26105874 |

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: State model name, version, owner, model-risk tier, and governing standards.

## 3. Intended use & restrictions

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: From the dev doc: intended use, approved scope, exclusions, and limitations.

## 4. Model methodology (as documented)

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Summarise the model methodology and theory from the development document.

## 5. Inputs & data lineage

**Facts (verbatim from platform artefacts):**

Inputs (from PIR mapping):

| name | type | source | nullable | description |
|---|---|---|---|---|
| income_band | float | customer.income_band_lookup | no | Discretised income tier (1..5) |
| tenure_months | int | customer.tenure_months | no | Months since account opening |
| delinquencies | float | customer.delinquencies_12m | yes | Count of 30+ DPD events in last 12 months |

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Explain the inputs and how data is sourced/wired, per the PIR and data code.

## 6. Feature engineering & transformations

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Describe how raw inputs become model features in the data/scoring code.

## 7. Data quality & validation controls

**Facts (verbatim from platform artefacts):**

Code Intake validation summary:

| checker | findings | codes |
|---|---|---|
| static_sas | 0 | — |
| schema | 0 | — |
| pir | 0 | — |
| static_python | 0 | — |
| tests | 0 | — |

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Describe the DQ checks and the Code Intake validation results for the package.

## 8. Outputs & downstream consumption

**Facts (verbatim from platform artefacts):**

Outputs (from PIR mapping):

| name | type | description |
|---|---|---|
| pd_score | float | Probability of default (0..1) |
| risk_band | string | HIGH / MEDIUM / LOW |

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Explain the outputs, the output contract, and how results are consumed.

## 9. Scoring logic as implemented

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Explain step by step how the scoring code computes the result, from the code.

## 10. Implementation optimizations & changes

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Describe optimizations EXL made vs the dev code and why behaviour is preserved.

## 11. Pipeline architecture

**Facts (verbatim from platform artefacts):**

Tier **standard**; upstream refs: credit-risk-pd@1.0.0 (package); pipeline manifest digest `707de58b5ebe4135f6f68d153d81025e8f2f7105d6272122327f33ca26105874`.

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Describe the pipeline: tier, the Step Functions flow, compute, and where it runs.

## 12. Scheduling, cadence & SLAs

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Describe the run schedule/cadence, expected runtime, and any SLA targets.

## 13. Environment & dependencies

**Facts (verbatim from platform artefacts):**

Runtime: Python 3.12 (per package pyproject); 2 Python file(s), 1 SAS file(s). Pinned configuration artefacts:

| config artefact | sha256 |
|---|---|
| model_config.yaml | eaa4a43b34f2… |
| python/pyproject.toml | 392661b1eae0… |

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Describe the runtime environment and pinned dependencies used to run the model.

## 14. Code inventory & structure

**Facts (verbatim from platform artefacts):**

| path | kind | sha256 |
|---|---|---|
| sas/score.sas | code-sas | 5a9b62b8b1d5… |
| python/conftest.py | code-python | 88781673f7b0… |
| python/score.py | code-python | 2f4d5147177e… |
| python/tests/test_score.py | code-test | 153c78ec7482… |
| pir.yaml | pir | d45facf803fc… |
| model_config.yaml | config | eaa4a43b34f2… |
| python/pyproject.toml | config | 392661b1eae0… |

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Walk through the package file layout and each component's responsibility.

## 15. Reconciliation & benchmark validation

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Describe reconciliation vs ABSA's benchmark, including tolerance bands.

## 16. Monitoring & performance tracking

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Describe post-deployment monitoring: drift, volumes, stability, and alerting.

## 17. Security & access controls

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Describe IAM, KMS, cross-account boundaries, and the data-residency posture.

## 18. Chain-of-custody & signing evidence

**Facts (verbatim from platform artefacts):**

Signing: `RSASSA_PKCS1_V1_5_SHA_256` (KMS asymmetric CMK, cross-account verify). The digest anchor binds package → pipeline → registry: the package digest equals the pipeline's first upstream ref, which is recorded on the registry record. Tamper-evidence is end-to-end.

| artefact | digest |
|---|---|
| Package manifest | 654d040760572c54879c05154cc9b9c9a7af0b6faa504a20a0755e5bd6355028 |
| Pipeline manifest | 707de58b5ebe4135f6f68d153d81025e8f2f7105d6272122327f33ca26105874 |

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Explain the digest anchor and signing binding package, pipeline, and registry.

## 19. Approvals & sign-off

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Record the approval path (CAB/IVU) and the registry approval state.

## 20. Deviations from the development design

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: List every deviation from the dev design, each with an explicit rationale.

## 21. Assumptions & constraints

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: List assumptions made during implementation and any operating constraints.

## 22. Known limitations & residual risks

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: List known limitations and residual risks of the implementation.

## 23. Rollback, DR & operational runbook

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Describe rollback, DR posture, and the operational runbook for this model.

## 24. Change log

**Facts (verbatim from platform artefacts):**

| version | note |
|---|---|
| 1.0.0 | initial implementation |

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Note this version and what changed relative to any prior version.

## 25. Open items & follow-ups

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: List outstanding items, pending approvals, or known TODOs.

## Appendix A — File inventory & digests

| path | kind | sha256 |
|---|---|---|
| sas/score.sas | code-sas | 5a9b62b8b1d5… |
| python/conftest.py | code-python | 88781673f7b0… |
| python/score.py | code-python | 2f4d5147177e… |
| python/tests/test_score.py | code-test | 153c78ec7482… |
| pir.yaml | pir | d45facf803fc… |
| model_config.yaml | config | eaa4a43b34f2… |
| python/pyproject.toml | config | 392661b1eae0… |

## Appendix B — Source artefact provenance

| artefact | digest |
|---|---|
| package_manifest | 654d040760572c54879c05154cc9b9c9a7af0b6faa504a20a0755e5bd6355028 |
| pipeline_manifest | 707de58b5ebe4135f6f68d153d81025e8f2f7105d6272122327f33ca26105874 |

## Appendix C — Development document outline

Source: md, 1,270 chars, 7 sections; sent in full.

| # | section |
|---|---|
| 1 | Credit Risk PD — Model Development Document (synthetic) |
| 2 | Overview |
| 3 | Methodology |
| 4 | Inputs |
| 5 | Outputs |
| 6 | Intended use & limitations |
| 7 | Owner |


---

*Facts above are sourced verbatim from the package + pipeline manifests, the PIR mapping, the validation summary, and the package file inventory. Narrative sections are LLM-drafted and must be human-reviewed before this document is approved and its digest recorded as `implementation_doc_ref`.*
