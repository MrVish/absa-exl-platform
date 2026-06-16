# Role Brief - SAS Development

**Sprint 1: Mon Jun 15 -> Fri Jun 26, 2026** (10 working days). Source of truth: [`docs/absa-exl-agile-plan.xlsx`](../absa-exl-agile-plan.xlsx) Backlog sheet - task IDs match.

## Mission

You own the model code - the heart of the program. Ten ABSA SAS models must be reviewed, optimized, packaged, and reconciled against ABSA's benchmark outputs, and the program's hardest gate (Group 1 sign-off, end of Sprint 8) sits on your reconciliation work.

- **SAS #1 + SAS #2 (from S1):** run Group 1 models 1 and 2 **in parallel** from Sprint 2. Two people on the proof removes the bus-factor-of-one risk and means two trained reviewers before scale-out. SAS #2 also upgrades the `static_sas` checker from structural to real SAS linting (once ABSA's runtime lands).
- **SAS #3 (from S8):** onboards in Sprint 8 (shadowing a Group 1 reconciliation) and joins the Group 2 scale-out.

**Group 2 is compressed:** three of you onboard 3 models/sprint in S9-S10 and the last 2 in S11, so **all 10 models are live by the end of Sprint 11.** Sprint 12 has no new models - it's reconciliation sweep, defect closure, and knowledge transfer. The single most important quality activity across the whole program is benchmark reconciliation within agreed tolerance bands; everything else serves that.

## The seats in this role

- **SAS** - SAS Developer #1 (Model 1 / Group 2)
- **SAS2** - SAS Developer #2 (Model 2 / Group 2)
- **SAS3** - SAS Developer #3 (Group 2, from S8)

## Sprint 1 plan

### SAS (SAS Developer #1 (Model 1 / Group 2)) - 5.0 effort-days

| Task | Est (d) | Acceptance / Notes | Blocked on |
|---|---|---|---|
| T-0103 Clone repo, uv sync, run full 278-test suite locally | 0.5 | All engineers: 278-test suite green + `make demo` exit 0 locally; walkthrough attended. | - |
| T-0107 Run `make demo` (LocalStack chain) green locally | 0.5 | All engineers: 278-test suite green + `make demo` exit 0 locally; walkthrough attended. | - |
| T-0501 Study credit-risk-pd package + static_sas checker internals | 2.0 | Prod-readiness standards published; SAS runtime obtained; static_sas upgraded to real lint | - |
| T-0502 SAS prod-readiness standards doc (naming, macros, errors, logging) | 2.0 | Prod-readiness standards published; SAS runtime obtained; static_sas upgraded to real lint | - |

### SAS2 (SAS Developer #2 (Model 2 / Group 2)) - 2.5 effort-days

| Task | Est (d) | Acceptance / Notes | Blocked on |
|---|---|---|---|
| T-0103b Clone repo, uv sync, tests green locally | 0.5 | All engineers: 278-test suite green + `make demo` exit 0 locally; walkthrough attended. | - |
| T-0107b Run `make demo` green locally | 0.5 | All engineers: 278-test suite green + `make demo` exit 0 locally; walkthrough attended. | - |
| T-0501b Study credit-risk-pd package + SAS standards (with SAS #1) | 1.5 | Prod-readiness standards published; SAS runtime obtained; static_sas upgraded to real lint | - |

### SAS3 (SAS Developer #3 (Group 2, from S8)) - 0.0 effort-days

_Not yet on the team in Sprint 1 (joins later - see load table)._

## Your load across the program (effort-days/sprint)

| Seat | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 | S9 | S10 | S11 | S12 | Cap |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SAS | 5.0 | 3.0 | 4.0 | 5.0 | - | 3.0 | 3.0 | 4.5 | 6.5 | 6.5 | 6.5 | 3.0 | 8 |
| SAS2 | 2.5 | 0.5 | 5.0 | 4.0 | 3.0 | - | 3.0 | 0.5 | 6.5 | 6.5 | 6.5 | 3.0 | 8 |
| SAS3 | - | - | - | - | - | - | - | 3.0 | 6.5 | 6.5 | 4.0 | 2.0 | 8 |

_Cap is 8 d/sprint per engineer (6 for TL), i.e. 10 working days x 0.8 focus factor. Loads sit below cap on purpose - the gap is ceremonies, review, and slack for the unknowns._

## Sprint-by-sprint focus

**S1 (Jun 15-Jun 26)** - _Team onboarded; Jenkins identity decided; python-validate green on Jenkins; ABSA ask-list sent_
- [SAS] Clone repo, uv sync, run full 278-test suite locally (0.5d)
- [SAS2] Clone repo, uv sync, tests green locally (0.5d)
- [SAS] Run `make demo` (LocalStack chain) green locally (0.5d)
- [SAS2] Run `make demo` green locally (0.5d)
- [SAS] Study credit-risk-pd package + static_sas checker internals (2.0d)
- [SAS2] Study credit-risk-pd package + SAS standards (with SAS #1) (1.5d)
- [SAS] SAS prod-readiness standards doc (naming, macros, errors, logging) (2.0d)

**S2 (Jun 29-Jul 10)** - _All no-AWS Jenkins jobs live; AWS bootstrap applied; data contracts started; SAS model-1 review done_
- [SAS2] Obtain SAS runtime image + license terms from ABSA (0.5d)
- [SAS] Model-1 dev-code review vs benchmark spec (2.0d)
- [SAS] Benchmark spec gap notes; clarify with ABSA model owner (1.0d)

**S3 (Jul 13-Jul 24)** - _Jenkins cutover complete (GHA retired); signing foundation live on real AWS; model-1 optimized_
- [SAS2] Upgrade static_sas checker from structural to real lint (3.0d)
- [SAS] Optimize + standardize model-1 scoring code (profile, refactor, unit-test) (4.0d)
- [SAS2] Model-2 dev-code review vs benchmark spec (2.0d)

**S4 (Jul 27-Aug 07)** - _Registry API live on Lambda (dev); replication path validated; model-1 packaged; threat model done_
- [SAS] Regression harness vs ABSA benchmark outputs (2.0d)
- [SAS] Package model-1 per ADR-0010; code-intake validate green (1.0d)
- [SAS2] Optimize + standardize model-2 scoring code (profile, refactor, unit-test) (4.0d)
- [SAS] Output diff tool: tolerance bands, per-variable deltas (2.0d)

**S5 (Aug 10-Aug 21)** - _SFN executes model-1 in dev; PIR sync; model-2 optimized; CAPACITY REVIEW (scale-up decision)_
- [SAS2] Model-2 regression harness (2.0d)
- [SAS2] Package model-2 + code-intake green (1.0d)

**S6 (Aug 24-Sep 04)** - _DRESS REHEARSAL: full chain on real AWS for models 1-2; dashboards + perf harness; POPIA/SARB check_
- [SAS] Reconciliation report template (PIR-ready) (1.0d)
- [SAS] Dress rehearsal model runs + output checks (2.0d)

**S7 (Sep 07-Sep 18)** - _Group 1 initial production scoring; reconciliation; perf + resilience tests; UAT plan_
- [SAS] Reconcile G1 outputs vs benchmarks (tolerance report) (3.0d)
- [SAS2] Defect triage + fix cycle (3.0d)

**S8 (Sep 21-Oct 02)** - _GROUP 1 ABSA SIGN-OFF; pen-test remediation; 2nd SAS dev onboarded; G2 plan_
- [SAS] Model-1 implementation doc: generate (IDG) + review + approve (0.5d)
- [SAS2] Model-2 implementation doc: generate (IDG) + review + approve (0.5d)
- [SAS] Defect closure + re-run + final reconciliation (2.0d)
- [SAS] PIR evidence pack (reconciliation, DQ, audit trail) (2.0d)
- [SAS3] Clone repo, uv sync, tests green (0.5d)
- [SAS3] Run `make demo` green locally (0.5d)
- [SAS3] Study SAS standards + a packaged G1 model (1.0d)
- [SAS3] Shadow a G1 reconciliation cycle (1.0d)

**S9 (Oct 05-Oct 16)** - _Group 2 wave 1 (models 3-5) live; dashboards validated with ABSA; cost dashboard_
- [SAS] Model 3: implementation doc: generate (IDG) + approve (0.5d)
- [SAS] Model 3: profile + optimize + unit-test scoring code (2.5d)
- [SAS] Model 3: PIR pack + sign-off prep (0.5d)
- [SAS] Model 3: package per ADR-0010 + code-intake green (0.5d)
- [SAS] Model 3: reconcile vs benchmark + defect fix (1.5d)
- [SAS] Model 3: code review vs benchmark spec (1.0d)
- [SAS2] Model 4: implementation doc: generate (IDG) + approve (0.5d)
- [SAS2] Model 4: profile + optimize + unit-test scoring code (2.5d)
- [SAS2] Model 4: PIR pack + sign-off prep (0.5d)
- [SAS2] Model 4: package per ADR-0010 + code-intake green (0.5d)
- [SAS2] Model 4: reconcile vs benchmark + defect fix (1.5d)
- [SAS2] Model 4: code review vs benchmark spec (1.0d)
- [SAS3] Model 5: implementation doc: generate (IDG) + approve (0.5d)
- [SAS3] Model 5: profile + optimize + unit-test scoring code (2.5d)
- [SAS3] Model 5: PIR pack + sign-off prep (0.5d)
- [SAS3] Model 5: package per ADR-0010 + code-intake green (0.5d)
- [SAS3] Model 5: reconcile vs benchmark + defect fix (1.5d)
- [SAS3] Model 5: code review vs benchmark spec (1.0d)

**S10 (Oct 19-Oct 30)** - _Group 2 wave 2 (models 6-8) live; output delivery automated_
- [SAS] Model 6: implementation doc: generate (IDG) + approve (0.5d)
- [SAS] Model 6: profile + optimize + unit-test scoring code (2.5d)
- [SAS] Model 6: PIR pack + sign-off prep (0.5d)
- [SAS] Model 6: package per ADR-0010 + code-intake green (0.5d)
- [SAS] Model 6: reconcile vs benchmark + defect fix (1.5d)
- [SAS] Model 6: code review vs benchmark spec (1.0d)
- [SAS2] Model 7: implementation doc: generate (IDG) + approve (0.5d)
- [SAS2] Model 7: profile + optimize + unit-test scoring code (2.5d)
- [SAS2] Model 7: PIR pack + sign-off prep (0.5d)
- [SAS2] Model 7: package per ADR-0010 + code-intake green (0.5d)
- [SAS2] Model 7: reconcile vs benchmark + defect fix (1.5d)
- [SAS2] Model 7: code review vs benchmark spec (1.0d)
- [SAS3] Model 8: implementation doc: generate (IDG) + approve (0.5d)
- [SAS3] Model 8: profile + optimize + unit-test scoring code (2.5d)
- [SAS3] Model 8: PIR pack + sign-off prep (0.5d)
- [SAS3] Model 8: package per ADR-0010 + code-intake green (0.5d)
- [SAS3] Model 8: reconcile vs benchmark + defect fix (1.5d)
- [SAS3] Model 8: code review vs benchmark spec (1.0d)

**S11 (Nov 02-Nov 13)** - _Group 2 wave 3 (models 9-10) live - ALL 10 MODELS SCORING; runbooks; DR verified_
- [SAS3] Reconciliation depth + defect sweep across wave 3 (4.0d)
- [SAS] Model 9: implementation doc: generate (IDG) + approve (0.5d)
- [SAS] Model 9: profile + optimize + unit-test scoring code (2.5d)
- [SAS] Model 9: PIR pack + sign-off prep (0.5d)
- [SAS] Model 9: package per ADR-0010 + code-intake green (0.5d)
- [SAS] Model 9: reconcile vs benchmark + defect fix (1.5d)
- [SAS] Model 9: code review vs benchmark spec (1.0d)
- [SAS2] Model 10: implementation doc: generate (IDG) + approve (0.5d)
- [SAS2] Model 10: profile + optimize + unit-test scoring code (2.5d)
- [SAS2] Model 10: PIR pack + sign-off prep (0.5d)
- [SAS2] Model 10: package per ADR-0010 + code-intake green (0.5d)
- [SAS2] Model 10: reconcile vs benchmark + defect fix (1.5d)
- [SAS2] Model 10: code review vs benchmark spec (1.0d)

**S12 (Nov 16-Nov 27)** - _HARDENING ONLY (no new models): GROUP 2 SIGN-OFF; handover; hypercare; steady-state go-live_
- [SAS] Final cross-model reconciliation sweep + tolerance sign-off (3.0d)
- [SAS2] Group 2 defect closure + re-run verification (3.0d)
- [SAS3] Group 2 knowledge transfer + per-model runbooks (2.0d)

## ABSA dependencies that block your work

| Dependency | First bites | What it is |
|---|---|---|
| ABSA: SAS runtime | S2 | SAS runtime Docker image + license |
| ABSA: model docs | S2 | Approved model docs + code + benchmarks (models 1-2 first) |

The Tech Lead sends the consolidated ABSA ask-list in Sprint 1 (T-0113) and chases weekly. If any of the above is unanswered approaching its sprint, raise it in standup.

## Reading list (in order)

1. [ADR-0010](../adr/0010-productized-package-contract.md) - the package contract; your bible
2. [`code-intake/README.md`](../../code-intake/README.md) - checkers, finding codes, deferred checks
3. [`packages/credit-risk-pd/1.0.0/`](../../packages/credit-risk-pd/1.0.0/) - the worked example you clone the shape of ten times
4. `code-intake/src/code_intake/checkers/static_sas.py` + `pir.py` - enforced vs deferred
5. [docs/program-flow.md](../program-flow.md) - where your work sits in the 6-month arc

## Working agreement & Definition of Done

- Branch-based flow; no direct pushes to `main`; CI green before merge; CODEOWNERS review.
- Daily 15-min standup; a blocker older than a day is escalated, not rediscovered at review.
- **Done** = merged to `main`, tests green, docs updated if behaviour changed, acceptance met, demoed on the 2nd-Friday review.
- Estimates are effort, not elapsed. If a task is running long, say so at standup - re-planning is normal; silent slippage is not.
