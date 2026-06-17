# Implementation Document — credit-risk-pd 1.0.0

> **Status: DRAFT** · as-built record per [ADR-0012](../../../docs/adr/0012-implementation-document-generation.md), structured as a **section-by-section counterpart to ABSA's Model Development Document** (see Appendix D cross-walk). Platform **facts** are injected verbatim; **narrative** is LLM-drafted and requires human review before approval.

## Provenance

| Field | Value |
|---|---|
| IDG version | 0.2.0 |
| LLM provider | offline |
| Generated at | 2026-06-16T00:00:00+00:00 |
| Status | DRAFT |
| Approver | **PENDING REVIEW** |
| Sections | 37 |
| Package manifest digest | 654d040760572c54879c05154cc9b9c9a7af0b6faa504a20a0755e5bd6355028 |
| Pipeline manifest digest | 707de58b5ebe4135f6f68d153d81025e8f2f7105d6272122327f33ca26105874 |
| Development document | md, 5,245 chars, 49 sections; sent in full |

## 1. Executive summary (as-built)

**Facts (verbatim from platform artefacts):**

Model **credit-risk-pd v1.0.0**; pipeline tier **standard**; package digest `654d040760572c54…`. Development document: md, 5,245 chars, 49 sections; sent in full.

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: As-built overview: what was implemented, tier, cadence, and current status.

## 2. Model identification & classification

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

Drafting brief: Name, version, owner, model-risk classification/tier, materiality, standards.

## 3. Governance, approvals & change policy

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: How governance + change policy are enforced: CAB/IVU, registry approval, versioning.

## 4. Modelling standards & policies (as enforced)

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: How modelling/dev standards are enforced via Code Intake checks + packaging.

## 5. Model description & methodology (as documented)

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Summarise the model, its methodology and theory, from the development document.

## 6. Intended use, portfolio & target market

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Intended use, product/portfolio scope, target market, and explicit exclusions.

## 7. Regulatory & legislative context

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Applicable regulation/legislation (POPIA, SARB, NCA) and any external changes.

## 8. Data sources & lineage (as wired)

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Data sources and how they are sourced/replicated/wired into the platform.

## 9. Input variables & definitions (PIR mapping)

**Facts (verbatim from platform artefacts):**

Inputs (from PIR mapping):

| name | type | source | nullable | description |
|---|---|---|---|---|
| income_band | float | customer.income_band_lookup | no | Discretised income tier (1..5) |
| tenure_months | int | customer.tenure_months | no | Months since account opening |
| delinquencies | float | customer.delinquencies_12m | yes | Count of 30+ DPD events in last 12 months |

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Input variables and definitions per the PIR mapping and the input contract.

## 10. Data flow, ingestion & granularity (as implemented)

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: As-implemented data flow, bucket layout, arrival validation, account/customer keying.

## 11. Default / target definition (as implemented)

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: How the default/target label is defined and implemented in the data/scoring code.

## 12. Exclusions & filtering (as implemented)

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Exclusions and filtering rules as implemented in the data-preparation code.

## 13. Feature engineering & transformations

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: How raw inputs become model features/characteristics in the code.

## 14. Data quality & validation controls

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

Drafting brief: DQ checks, drift, and the Code Intake validation results for the package.

## 15. Development methodology & sample (reference)

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Reference the dev methodology, period, sample design, univariate/multivariate work.

## 16. Segmentation (as implemented)

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Model segmentation and how segment routing is implemented in scoring.

## 17. Final scorecard & scoring logic (as implemented)

**Facts (verbatim from platform artefacts):**

Outputs (from PIR mapping):

| name | type | description |
|---|---|---|
| pd_score | float | Probability of default (0..1) |
| risk_band | string | HIGH / MEDIUM / LOW |

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Final scorecard variables/weights and how scoring computes the result, from code.

## 18. Implementation optimizations & changes

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Optimizations EXL made vs the dev code and why behaviour is preserved.

## 19. Model performance & discrimination (verified)

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Performance/discrimination metrics and how they were verified on the platform.

## 20. Benchmark reconciliation (as implemented)

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Reconciliation vs ABSA's benchmark scorecard, including tolerance bands.

## 21. Monitoring & tracking framework (as implemented)

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: As-implemented monitoring: run status, DQ/drift, score stability, alerting.

## 22. Tracking metrics & stability (as wired)

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Tracking metrics (PSI, score/variable stability) wired into dashboards/alerts.

## 23. Pipeline architecture & execution

**Facts (verbatim from platform artefacts):**

Tier **standard**; upstream refs: credit-risk-pd@1.0.0 (package); pipeline manifest digest `707de58b5ebe4135f6f68d153d81025e8f2f7105d6272122327f33ca26105874`.

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Pipeline tier, the Step Functions flow, compute, and where it runs.

## 24. Scheduling, cadence & SLAs

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Run schedule/cadence, expected runtime, and any SLA targets.

## 25. Runtime environment & dependencies

**Facts (verbatim from platform artefacts):**

Runtime: Python 3.12 (per package pyproject); 2 Python file(s), 1 SAS file(s). Pinned configuration artefacts:

| config artefact | sha256 |
|---|---|
| model_config.yaml | eaa4a43b34f2… |
| python/pyproject.toml | 392661b1eae0… |

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Runtime environment and pinned dependencies used to run the model.

## 26. Code inventory & package structure

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

Drafting brief: Productized package layout and each component's role (dev code -> package).

## 27. Security & access controls

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: IAM, KMS, cross-account boundaries, and the data-residency posture.

## 28. Chain-of-custody & signing evidence

**Facts (verbatim from platform artefacts):**

Signing: `RSASSA_PKCS1_V1_5_SHA_256` (KMS asymmetric CMK, cross-account verify). The digest anchor binds package → pipeline → registry: the package digest equals the pipeline's first upstream ref, which is recorded on the registry record. Tamper-evidence is end-to-end.

| artefact | digest |
|---|---|
| Package manifest | 654d040760572c54879c05154cc9b9c9a7af0b6faa504a20a0755e5bd6355028 |
| Pipeline manifest | 707de58b5ebe4135f6f68d153d81025e8f2f7105d6272122327f33ca26105874 |

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: The digest anchor and signing binding package, pipeline, and registry.

## 29. Conservatism & overlays (as implemented)

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Any conservatism, overlays or caps and how they are applied in scoring.

## 30. Deviations from the development design

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Every deviation from the dev design, each with an explicit rationale.

## 31. Assumptions & constraints

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Assumptions made during implementation and any operating constraints.

## 32. Strengths, weaknesses & residual risks

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Model strengths/weaknesses and residual risks, and how implementation mitigates.

## 33. Rollback, DR & operational runbook

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Rollback, DR posture, and the operational runbook for this model.

## 34. Approvals & sign-off

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Approval path (CAB/IVU) and the registry approval state for this version.

## 35. Change log & rationalisation history

**Facts (verbatim from platform artefacts):**

| version | note |
|---|---|
| 1.0.0 | initial implementation |

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: This version, what changed, and the model rationalisation history.

## 36. Open items & follow-ups

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Outstanding items, pending approvals, or known TODOs.

## 37. References & source artefacts

**Facts (verbatim from platform artefacts):**

Source-artefact digests:

| artefact | digest |
|---|---|
| package_manifest | 654d040760572c54879c05154cc9b9c9a7af0b6faa504a20a0755e5bd6355028 |
| pipeline_manifest | 707de58b5ebe4135f6f68d153d81025e8f2f7105d6272122327f33ca26105874 |

Related: ADR-0001 (data movement), ADR-0009 (signing), ADR-0010 (package contract), ADR-0012 (this generator). Development document is the as-designed counterpart to this as-built record.

**Narrative:**

_Drafted by the **offline** provider — replace with reviewed LLM narrative before approval._

Drafting brief: Source artefacts, digests, dev-doc reference, and related ADRs.

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

## Appendix C — Development document outline (as parsed)

Source: md, 5,245 chars, 49 sections; sent in full.

| # | section |
|---|---|
| 1 | Credit Risk PD — Model Development Document (synthetic) |
| 2 | 1. Overview |
| 3 | 1.1 Executive Summary |
| 4 | 1.2 Model Classification |
| 5 | 1.3 Background and motivation |
| 6 | 1.4 Model governance and change policy |
| 7 | 1.5 Modelling standards and policies |
| 8 | 1.6 Model Description |
| 9 | 1.7 Model rationalisation history |
| 10 | 2. Portfolio Overview |
| 11 | 2.1 Product Information, Features and Target Markets |
| 12 | 2.2 External Legislative Changes |
| 13 | 3. Data Landscape and Data Preparation |
| 14 | 3.1 Data Sources |
| 15 | 3.2 Variable Definitions |
| 16 | 3.3 Data Flow |
| 17 | 3.4 Default Definition |
| 18 | 3.5 Account level versus Customer level Treatment |
| 19 | 3.6 Exclusions |
| 20 | 4. Model Development |
| 21 | 4.1 Methodology |
| 22 | 4.2 Development Period |
| 23 | 4.3 Investigate Multiple Models / Segmentation |
| 24 | 4.4 Sample Design |
| 25 | 4.5 Univariate Analysis |
| 26 | 4.6 Multivariate Analysis |
| 27 | 5. Final Scorecard |
| 28 | 5.1 Final Scorecard Variables |
| 29 | 5.2 Correlation among Final Variables |
| 30 | 5.3 Multicollinearity in Final Variables |
| 31 | 6. Model Performance |
| 32 | 6.1 Model Discrimination |
| 33 | 6.2 Variable Stability |
| 34 | 6.3 Score Stability Distribution |
| 35 | 6.4 Benchmarking against the current scorecard |
| 36 | 7. Model Strengths and Weaknesses |
| 37 | 7.1 Strengths of the Approach |
| 38 | 7.2 Weaknesses of the Approach |
| 39 | 8. Post Development |
| 40 | 8.1 Model Monitoring and Tracking Framework |
| 41 | 8.2 Proposed Tracking metrics |
| 42 | 9. Conservatism |
| 43 | 10. Implementation |
| 44 | 11. References |
| 45 | Appendix A: Segmentation results |
| 46 | Appendix B: Variable Stability |
| 47 | Appendix C: Structured Mortgages – Definition of Default document |
| 48 | Appendix D: Development Code |
| 49 | Owner |


## Appendix D — Development-document cross-walk

Maps each ABSA Model Development Document section to the implementation-doc section that records it as-built — evidence of complete coverage.

| ABSA dev-doc section | Implementation doc |
|---|---|
| 1 Overview | §1-§5 |
|    1.1 Executive Summary | §1 |
|    1.2 Model Classification | §2 |
|    1.3 Background and motivation | §5 |
|    1.4 Model governance and change policy | §3 |
|    1.5 Modelling standards and policies | §4 |
|    1.6 Model Description | §5 |
|    1.7 Model rationalisation history | §35 |
|    1.8 Document Structure | Appendix D (this cross-walk) |
| 2 Portfolio Overview | §6-§7 |
|    2.1 Product Information, Features & Target Markets | §6 |
|    2.2 External Legislative Changes | §7 |
| 3 Data Landscape and Data Preparation | §8-§14 |
|    3.1 Data Sources | §8 |
|    3.2 Variable Definitions | §9 |
|    3.3 Data Flow | §10 |
|    3.4 Default Definition | §11 |
|    3.5 Account vs Customer level Treatment | §10 |
|    3.6 Exclusions | §12 |
| 4 Model Development | §15-§16 |
|    4.1 Methodology | §5, §15 |
|    4.2 Development Period | §15 |
|    4.3 Multiple Models / Segmentation | §16 |
|    4.4 Sample Design | §15 |
|    4.5 Univariate Analysis | §15 |
|    4.6 Multivariate Analysis | §15 |
| 5 Final Scorecard | §17 |
|    5.1 Final Scorecard Variables | §17 |
|    5.2 Correlation among Final Variables | §17 |
|    5.3 Multicollinearity in Final Variables | §17 |
| 6 Model Performance | §19-§22 |
|    6.1 Model Discrimination | §19 |
|    6.2 Variable Stability | §22 |
|    6.3 Score Stability Distribution | §22 |
|    6.4 Benchmarking against current scorecard | §20 |
| 7 Model Strengths and Weaknesses | §32 |
| 8 Post Development | §21-§22 |
|    8.1 Model Monitoring and Tracking Framework | §21 |
|    8.2 Proposed Tracking metrics | §22 |
| 9 Conservatism | §29 |
| 10 Implementation | §23-§28 (as-built core) |
| 11 References | §37 |
| Appendix A: Segmentation results | §16 |
| Appendix B: Variable Stability | §22 |
| Appendix C: Definition of Default | §11 |
| Appendix D: Development Code | §26 |


---

*Facts above are sourced verbatim from the package + pipeline manifests, the PIR mapping, the validation summary, and the package file inventory. Narrative sections are LLM-drafted and must be human-reviewed before this document is approved and its digest recorded as `implementation_doc_ref`.*
