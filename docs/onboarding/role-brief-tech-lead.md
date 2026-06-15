# Role Brief - Tech Lead (Vishnu)

**Sprint 1: Mon Jun 15 -> Fri Jun 26, 2026** (10 working days). Source of truth: [`docs/absa-exl-agile-plan.xlsx`](../absa-exl-agile-plan.xlsx) Backlog sheet - task IDs match.

## Mission

You built the platform; now you scale yourself through eight people. Your job is three things: **transfer context fast** (the team's week-1 productivity is a direct function of your walkthrough), **make and record decisions** (ADR amendments, the D01-D09 register, the S5 capacity review), and **chase ABSA relentlessly** (every top program risk is an ABSA dependency). You stay the platform-code owner via PR review to keep the chain-of-custody invariants intact.

Two sprints are your peak by design and should be protected: **S8 (Group 1 sign-off + audit evidence pack, ~92%)** and **S12 (Group 2 sign-off + handover + go-live, ~92%)**. Keep the sprints around them light so you can absorb slippage into the gates.

## Sprint 1 plan

Your Sprint 1 load: **4.5 effort-days** (cap 6).

| Task | Est (d) | Acceptance / Notes | Blocked on |
|---|---|---|---|
| T-0109 Host architecture walkthrough: chain-of-custody, repo tour, ADR index | 1.0 | Record for future joiners | - |
| T-0110 Stand up Jira/ADO board; import this EPIC/Story/Task tree | 1.0 | Backlog sheet is the import source | - |
| T-0111 Publish Definition of Ready/Done + PR / branch-protection workflow | 0.5 | Jira board mirrors this backlog; DoR/DoD + ceremony calendar published. | - |
| T-0112 Ceremony calendar: standup, planning, review+demo, retro | 0.5 | Jira board mirrors this backlog; DoR/DoD + ceremony calendar published. | - |
| T-0113 Send 8-item dependency ask-list to ABSA SPOC | 0.5 | Accounts, IAM, SAS runtime, PIR, data movement, CAB/IVU, network, model docs | - |
| T-0114 Stand up weekly dependency-chase cadence + escalation path | 0.5 | 8-item ask-list sent; weekly chase cadence running with named SPOC. | - |
| T-0203 Amend ADR-0011 with the standalone-Jenkins identity decision | 0.5 | Topology documented; auth path chosen; ADR-0011 amended. | - |

## Your load across the program (effort-days/sprint)

| Seat | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 | S9 | S10 | S11 | S12 | Cap |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| TL | 4.5 | - | 1.0 | 2.5 | 4.0 | 4.0 | 2.5 | 5.5 | 0.5 | 0.5 | 2.5 | 5.5 | 6 |

_Cap is 8 d/sprint per engineer (6 for TL), i.e. 10 working days x 0.8 focus factor. Loads sit below cap on purpose - the gap is ceremonies, review, and slack for the unknowns._

## Sprint-by-sprint focus

**S1 (Jun 15-Jun 26)** - _Team onboarded; Jenkins identity decided; python-validate green on Jenkins; ABSA ask-list sent_
- Host architecture walkthrough: chain-of-custody, repo tour, ADR index (1.0d)
- Stand up Jira/ADO board; import this EPIC/Story/Task tree (1.0d)
- Publish Definition of Ready/Done + PR / branch-protection workflow (0.5d)
- Ceremony calendar: standup, planning, review+demo, retro (0.5d)
- Send 8-item dependency ask-list to ABSA SPOC (0.5d)
- Stand up weekly dependency-chase cadence + escalation path (0.5d)
- Amend ADR-0011 with the standalone-Jenkins identity decision (0.5d)

**S3 (Jul 13-Jul 24)** - _Jenkins cutover complete (GHA retired); signing foundation live on real AWS; model-1 optimized_
- Docs sweep: ADR-0003/0009 final edits; control-matrix rows -> Live (1.0d)

**S4 (Jul 27-Aug 07)** - _Registry API live on Lambda (dev); replication path validated; model-1 packaged; threat model done_
- SigV4 register smoke from pipeline-factory (1.0d)
- Threat model workshop (STRIDE) on cross-account signing chain (1.5d)

**S5 (Aug 10-Aug 21)** - _SFN executes model-1 in dev; PIR sync; model-2 optimized; CAPACITY REVIEW (scale-up decision)_
- Map CAB/IVU contract onto registry approve/retire routes (D02) (2.0d)
- Integration test suite on real AWS (beyond LocalStack) (1.5d)
- 2-month capacity & velocity review; confirm 3rd SAS dev + AWS ramp-down plan (0.5d)

**S6 (Aug 24-Sep 04)** - _DRESS REHEARSAL: full chain on real AWS for models 1-2; dashboards + perf harness; POPIA/SARB check_
- POPIA/SARB control verification vs control-matrix (1.5d)
- Dress rehearsal orchestration: full chain on real AWS, models 1-2 (2.0d)
- Initiate 3rd SAS dev sourcing/transfer; plan AWS redeploy after S7 (0.5d)

**S7 (Sep 07-Sep 18)** - _Group 1 initial production scoring; reconciliation; perf + resilience tests; UAT plan_
- Defect triage facilitation + ABSA comms (1.0d)
- UAT plan + scripts with ABSA (1.5d)

**S8 (Sep 21-Oct 02)** - _GROUP 1 ABSA SIGN-OFF; pen-test remediation; 2nd SAS dev onboarded; G2 plan_
- Audit evidence pack assembly (G1) for ABSA risk + external audit (1.5d)
- ABSA sign-off review meeting + written sign-off (2.0d)
- Group 2 onboarding plan + per-model checklist from G1 lessons (1.0d)
- UAT sign-off capture (0.5d)
- Onboard 3rd SAS dev: access + repo + walkthrough (0.5d)

**S9 (Oct 05-Oct 16)** - _Group 2 wave 1 (models 3-5) live; dashboards validated with ABSA; cost dashboard_
- Wave review + ABSA checkpoint (S9) (0.5d)

**S10 (Oct 19-Oct 30)** - _Group 2 wave 2 (models 6-8) live; output delivery automated_
- Wave review + ABSA checkpoint (S10) (0.5d)

**S11 (Nov 02-Nov 13)** - _Group 2 wave 3 (models 9-10) live - ALL 10 MODELS SCORING; runbooks; DR verified_
- Support rota + escalation matrix (1.0d)
- Quarterly service review template + first review scheduled (1.0d)
- Wave review + ABSA checkpoint (S11) (0.5d)

**S12 (Nov 16-Nov 27)** - _HARDENING ONLY (no new models): GROUP 2 SIGN-OFF; handover; hypercare; steady-state go-live_
- Group 2 sign-off pack + ABSA meeting (2.0d)
- Handover sessions: ops team + ABSA (2.0d)
- Steady-state go-live checklist + cutover (1.0d)
- Define hypercare period + staffing (0.5d)

## ABSA dependencies that block your work

| Dependency | First bites | What it is |
|---|---|---|
| ABSA: CAB/IVU contract | S5 | CAB / IVU API contract |

The Tech Lead sends the consolidated ABSA ask-list in Sprint 1 (T-0113) and chases weekly. If any of the above is unanswered approaching its sprint, raise it in standup.

## Reading list (in order)

1. [docs/absa-exl-agile-plan.xlsx](../absa-exl-agile-plan.xlsx) - the backlog you own and import to Jira
2. [docs/program-flow.md](../program-flow.md) - the techno-functional narrative for ABSA
3. all ADRs in [docs/adr/](../adr/) - you're the decision-record owner
4. [docs/compliance/control-matrix.md](../compliance/control-matrix.md) - POPIA/SARB control mapping

## Working agreement & Definition of Done

- Branch-based flow; no direct pushes to `main`; CI green before merge; CODEOWNERS review.
- Daily 15-min standup; a blocker older than a day is escalated, not rediscovered at review.
- **Done** = merged to `main`, tests green, docs updated if behaviour changed, acceptance met, demoed on the 2nd-Friday review.
- Estimates are effort, not elapsed. If a task is running long, say so at standup - re-planning is normal; silent slippage is not.
