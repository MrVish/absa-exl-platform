# Role Brief - Data Engineering

**Sprint 1: Mon Jun 15 -> Fri Jun 26, 2026** (10 working days). Source of truth: [`docs/absa-exl-agile-plan.xlsx`](../absa-exl-agile-plan.xlsx) Backlog sheet - task IDs match.

## Mission

You own the data plane solo, and you're the one role continuously engaged start to finish (~4-5 effort-days every sprint). You build the contracts that define each model's inputs, the ingestion path that validates files the moment ABSA lands them, the data-quality framework (volume bands + PSI drift), source-vs-landing reconciliation, lineage capture, retention, and the PIR integration. In steady state your DQ checks are the first thing that catches a bad scoring run - before the model ever executes.

Your load is deliberately even rather than spiky: you absorb the unpredictable work (real data never behaves) and provide the data evidence for both Group 1 and Group 2 sign-off.

## Sprint 1 plan

Your Sprint 1 load: **4.0 effort-days** (cap 8).

| Task | Est (d) | Acceptance / Notes | Blocked on |
|---|---|---|---|
| T-0102 Clone repo, uv sync, run full 278-test suite locally | 0.5 | All engineers: 278-test suite green + `make demo` exit 0 locally; walkthrough attended. | - |
| T-0106 Run `make demo` (LocalStack chain) green locally | 0.5 | All engineers: 278-test suite green + `make demo` exit 0 locally; walkthrough attended. | - |
| T-0401 Study platform-contracts schemas + PIR mapping + demo data flow | 1.0 | Data dictionary template + input schemas for models 1-2; volume/cadence matrix for all 10. | - |
| T-0402 Data dictionary template (input schema, types, nullability, PIR link) | 2.0 | Data dictionary template + input schemas for models 1-2; volume/cadence matrix for all 10. | - |

## Your load across the program (effort-days/sprint)

| Seat | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 | S9 | S10 | S11 | S12 | Cap |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DE | 4.0 | 4.0 | 5.0 | 4.0 | 5.5 | 4.5 | 5.5 | 6.0 | 4.5 | 4.5 | 3.0 | 1.5 | 8 |

_Cap is 8 d/sprint per engineer (6 for TL), i.e. 10 working days x 0.8 focus factor. Loads sit below cap on purpose - the gap is ceremonies, review, and slack for the unknowns._

## Sprint-by-sprint focus

**S1 (Jun 15-Jun 26)** - _Team onboarded; Jenkins identity decided; python-validate green on Jenkins; ABSA ask-list sent_
- Clone repo, uv sync, run full 278-test suite locally (0.5d)
- Run `make demo` (LocalStack chain) green locally (0.5d)
- Study platform-contracts schemas + PIR mapping + demo data flow (1.0d)
- Data dictionary template (input schema, types, nullability, PIR link) (2.0d)

**S2 (Jun 29-Jul 10)** - _All no-AWS Jenkins jobs live; AWS bootstrap applied; data contracts started; SAS model-1 review done_
- Input schemas for models 1-2 (2.0d)
- Volume/cadence matrix for all 10 models (1.0d)
- Bucket layout + partitioning convention for scoring inputs (1.0d)

**S3 (Jul 13-Jul 24)** - _Jenkins cutover complete (GHA retired); signing foundation live on real AWS; model-1 optimized_
- Arrival validation job: schema check on landing (3.0d)
- Reject / return-to-ABSA workflow for failed files (1.0d)
- Source-vs-landing row-count reconciliation check (1.0d)

**S4 (Jul 27-Aug 07)** - _Registry API live on Lambda (dev); replication path validated; model-1 packaged; threat model done_
- Volume checks: row-count expectation bands per model (2.0d)
- Drift metric design (PSI per feature) -> D01 proposal to ABSA (2.0d)

**S5 (Aug 10-Aug 21)** - _SFN executes model-1 in dev; PIR sync; model-2 optimized; CAPACITY REVIEW (scale-up decision)_
- DQ report artifact published per scoring run (2.0d)
- PIR feed/API contract session with ABSA (0.5d)
- pir.yaml sync from ABSA PIR system (3.0d)

**S6 (Aug 24-Sep 04)** - _DRESS REHEARSAL: full chain on real AWS for models 1-2; dashboards + perf harness; POPIA/SARB check_
- PIR coverage report on real model inputs (1.0d)
- Dress-rehearsal data preparation (models 1-2) (2.0d)
- Data lineage capture (input dataset -> run -> output) (1.5d)

**S7 (Sep 07-Sep 18)** - _Group 1 initial production scoring; reconciliation; perf + resilience tests; UAT plan_
- DQ on first production runs + threshold tuning (2.0d)
- Backfill / re-run capability for missed cadence windows (1.5d)
- Implement + verify S3 retention/archival per model class (1.0d)
- Raw-data / PII guard on the context bundle (pre-flight checker) (1.0d)

**S8 (Sep 21-Oct 02)** - _GROUP 1 ABSA SIGN-OFF; pen-test remediation; 2nd SAS dev onboarded; G2 plan_
- PIR data evidence: lineage + DQ reports (1.0d)
- DQ + drift panels alongside run status (2.0d)
- UAT execution support (G1) with ABSA (1.5d)
- Wire implementation_doc_ref into package-manifest + registry schema (regen models) (1.5d)

**S9 (Oct 05-Oct 16)** - _Group 2 wave 1 (models 3-5) live; dashboards validated with ABSA; cost dashboard_
- Model 3: contract + input schema (1.0d)
- Model 3: DQ rules + verification (0.5d)
- Model 4: contract + input schema (1.0d)
- Model 4: DQ rules + verification (0.5d)
- Model 5: contract + input schema (1.0d)
- Model 5: DQ rules + verification (0.5d)

**S10 (Oct 19-Oct 30)** - _Group 2 wave 2 (models 6-8) live; output delivery automated_
- Model 6: contract + input schema (1.0d)
- Model 6: DQ rules + verification (0.5d)
- Model 7: contract + input schema (1.0d)
- Model 7: DQ rules + verification (0.5d)
- Model 8: contract + input schema (1.0d)
- Model 8: DQ rules + verification (0.5d)

**S11 (Nov 02-Nov 13)** - _Group 2 wave 3 (models 9-10) live - ALL 10 MODELS SCORING; runbooks; DR verified_
- Model 9: contract + input schema (1.0d)
- Model 9: DQ rules + verification (0.5d)
- Model 10: contract + input schema (1.0d)
- Model 10: DQ rules + verification (0.5d)

**S12 (Nov 16-Nov 27)** - _HARDENING ONLY (no new models): GROUP 2 SIGN-OFF; handover; hypercare; steady-state go-live_
- Group 2 DQ + lineage evidence pack (1.5d)

## ABSA dependencies that block your work

| Dependency | First bites | What it is |
|---|---|---|
| ABSA: PIR contract | S5 | PIR system API/feed contract |
| ABSA: model docs | S2 | Approved model docs + code + benchmarks (models 1-2 first) |

The Tech Lead sends the consolidated ABSA ask-list in Sprint 1 (T-0113) and chases weekly. If any of the above is unanswered approaching its sprint, raise it in standup.

## Reading list (in order)

1. [ADR-0006](../adr/0006-contract-strategy-json-schema-canonical.md) - JSON Schema + canonical JSON contract backbone
2. `platform-contracts/src/platform_contracts/schemas/` - all three schemas, esp. `pir-mapping.schema.json`
3. [`packages/credit-risk-pd/1.0.0/pir.yaml`](../../packages/credit-risk-pd/1.0.0/) - a real PIR file
4. [`code-intake/README.md`](../../code-intake/README.md) - the PIR checker section (PIR00x codes)
5. [ADR-0001](../adr/0001-data-movement-s3-replication.md) - how data moves cross-account

## Working agreement & Definition of Done

- Branch-based flow; no direct pushes to `main`; CI green before merge; CODEOWNERS review.
- Daily 15-min standup; a blocker older than a day is escalated, not rediscovered at review.
- **Done** = merged to `main`, tests green, docs updated if behaviour changed, acceptance met, demoed on the 2nd-Friday review.
- Estimates are effort, not elapsed. If a task is running long, say so at standup - re-planning is normal; silent slippage is not.
