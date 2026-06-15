# Role Brief - DevOps Engineering

**Sprint 1: Mon Jun 15 -> Fri Jun 26, 2026** (10 working days). Source of truth: [`docs/absa-exl-agile-plan.xlsx`](../absa-exl-agile-plan.xlsx) Backlog sheet - task IDs match.

## Mission

You own the CI/CD layer and, later, observability and operations. EXL's standard is Jenkins, not GitHub Actions, and a standalone Jenkins is already running - your first job (S1-S3) is migrating all six CI gates onto it per ADR-0011 and retiring GHA without breaking the platform's signing guarantees. Then you own dashboards + alerting (S4-S9), and runbooks + hypercare (S11-S12).

**You are the only un-doubled role,** so two sprints are deliberately your peak: **S2 (~88%, the Jenkins shared-library + no-AWS jobs crunch)** and **S6 (dashboards + dress-rehearsal ops)**. The Tech Lead pairs with you at those peaks. If those weeks slip, flag in standup early - they're the only single-person pinch points in the plan.

## Sprint 1 plan

Your Sprint 1 load: **5.5 effort-days** (cap 8).

| Task | Est (d) | Acceptance / Notes | Blocked on |
|---|---|---|---|
| T-0104 Clone repo, uv sync, run full 278-test suite locally | 0.5 | All engineers: 278-test suite green + `make demo` exit 0 locally; walkthrough attended. | - |
| T-0108 Run `make demo` (LocalStack chain) green locally | 0.5 | All engineers: 278-test suite green + `make demo` exit 0 locally; walkthrough attended. | - |
| T-0201 Document Jenkins topology: host, agents, executors, plugins, versions | 1.0 | Standalone instance already running | - |
| T-0202 Choose AWS auth path: instance profile / OIDC IdP plugin / keys+rotation | 1.0 | Drives signing-foundation trust policy | - |
| T-0204 Register absa-ci as Global Pipeline Library | 0.5 | ci/jenkins/ path in this repo | - |
| T-0205 Create multibranch job for python-validate; first run | 1.0 | absa-ci registered; ci/python-validate status visible on a GitHub PR. | - |
| T-0206 Verify ci/python-validate commit status lands on a GitHub PR | 1.0 | Branch-protection sandbox check | - |

## Your load across the program (effort-days/sprint)

| Seat | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 | S9 | S10 | S11 | S12 | Cap |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DevOps | 5.5 | 7.0 | 5.5 | 2.5 | 2.0 | 6.5 | 5.5 | 6.0 | 5.5 | 1.5 | 4.0 | 2.0 | 8 |

_Cap is 8 d/sprint per engineer (6 for TL), i.e. 10 working days x 0.8 focus factor. Loads sit below cap on purpose - the gap is ceremonies, review, and slack for the unknowns._

## Sprint-by-sprint focus

**S1 (Jun 15-Jun 26)** - _Team onboarded; Jenkins identity decided; python-validate green on Jenkins; ABSA ask-list sent_
- Clone repo, uv sync, run full 278-test suite locally (0.5d)
- Run `make demo` (LocalStack chain) green locally (0.5d)
- Document Jenkins topology: host, agents, executors, plugins, versions (1.0d)
- Choose AWS auth path: instance profile / OIDC IdP plugin / keys+rotation (1.0d)
- Register absa-ci as Global Pipeline Library (0.5d)
- Create multibranch job for python-validate; first run (1.0d)
- Verify ci/python-validate commit status lands on a GitHub PR (1.0d)

**S2 (Jun 29-Jul 10)** - _All no-AWS Jenkins jobs live; AWS bootstrap applied; data contracts started; SAS model-1 review done_
- Fix shared-library Groovy issues surfaced by first runs (2.0d)
- code-intake job live (0.5d)
- terraform-validate job live (docker tflint/tfsec/checkov/gitleaks) (1.5d)
- localstack-demo job live (Docker on agent, 0/1/2/3 exit-code gate) (2.0d)
- Wire platform secrets into Jenkins credentials store (1.0d)

**S3 (Jul 13-Jul 24)** - _Jenkins cutover complete (GHA retired); signing foundation live on real AWS; model-1 optimized_
- pipeline-factory sign+register stages green against real AWS (2.0d)
- publish-signing-key job (1.0d)
- 1-week GHA-vs-Jenkins parallel run; byte-equivalence report (2.0d)
- Flip branch protection to Jenkins contexts; GHA -> *.disabled.yml (0.5d)

**S4 (Jul 27-Aug 07)** - _Registry API live on Lambda (dev); replication path validated; model-1 packaged; threat model done_
- Rotation cadence doc: Jenkins creds, bot PAT, registrar tokens (D03) (1.0d)
- D08 tooling decision: CloudWatch / Grafana / QuickSight (1.5d)

**S5 (Aug 10-Aug 21)** - _SFN executes model-1 in dev; PIR sync; model-2 optimized; CAPACITY REVIEW (scale-up decision)_
- Alert routing: SNS -> email/Slack; severity mapping (2.0d)

**S6 (Aug 24-Sep 04)** - _DRESS REHEARSAL: full chain on real AWS for models 1-2; dashboards + perf harness; POPIA/SARB check_
- Dress rehearsal CI/pipeline ops (1.0d)
- Run-status dashboard build (runs, exceptions, durations) (3.0d)
- Per-pipeline CloudWatch alarms + dashboard baseline (1.0d)
- Performance/load test harness (1.5d)

**S7 (Sep 07-Sep 18)** - _Group 1 initial production scoring; reconciliation; perf + resilience tests; UAT plan_
- KMS rotation drill per docs/runbooks/kms-key-rotation.md (1.0d)
- Pen-test coordination + scope with ABSA security (1.0d)
- Production run monitoring + incident handling (1.0d)
- Performance test execution vs SLA bands (1.5d)
- Failure-mode / resilience test (retry, partial failure, teardown) (1.0d)

**S8 (Sep 21-Oct 02)** - _GROUP 1 ABSA SIGN-OFF; pen-test remediation; 2nd SAS dev onboarded; G2 plan_
- Pen-test remediation window (1.5d)
- Automated signed output delivery to ABSA + confirmation evidence (2.0d)
- G1 production readiness review (go/no-go checklist) (0.5d)
- Cutover rehearsal (G1) (1.0d)
- Regression test pack for ongoing changes (1.0d)

**S9 (Oct 05-Oct 16)** - _Group 2 wave 1 (models 3-5) live; dashboards validated with ABSA; cost dashboard_
- Failure notifications to ABSA SPOC path tested (1.0d)
- Delivery validation with ABSA recipients (1.0d)
- Dashboard access + validation with ABSA recipients (1.0d)
- Cost & usage dashboard (1.0d)
- Model 3: CI + monitoring wiring (0.5d)
- Model 4: CI + monitoring wiring (0.5d)
- Model 5: CI + monitoring wiring (0.5d)

**S10 (Oct 19-Oct 30)** - _Group 2 wave 2 (models 6-8) live; output delivery automated_
- Model 6: CI + monitoring wiring (0.5d)
- Model 7: CI + monitoring wiring (0.5d)
- Model 8: CI + monitoring wiring (0.5d)

**S11 (Nov 02-Nov 13)** - _Group 2 wave 3 (models 9-10) live - ALL 10 MODELS SCORING; runbooks; DR verified_
- Runbooks: incident, recovery, rollback per model family (3.0d)
- Model 9: CI + monitoring wiring (0.5d)
- Model 10: CI + monitoring wiring (0.5d)

**S12 (Nov 16-Nov 27)** - _HARDENING ONLY (no new models): GROUP 2 SIGN-OFF; handover; hypercare; steady-state go-live_
- Handover support + docs finalization (1.0d)
- Ops handbook / knowledge base (1.0d)

## ABSA dependencies that block your work

| Dependency | First bites | What it is |
|---|---|---|
| ABSA: data movement | S8 | Data movement decision (S3 replication vs SFTP) |

The Tech Lead sends the consolidated ABSA ask-list in Sprint 1 (T-0113) and chases weekly. If any of the above is unanswered approaching its sprint, raise it in standup.

## Reading list (in order)

1. [ADR-0011](../adr/0011-ci-platform-jenkins.md) - the whole migration; the Open Questions are your S1 homework
2. [`ci/jenkins/README.md`](../../ci/jenkins/README.md) - library wiring, credentials, migration map
3. the 5 Jenkinsfiles in [`ci/jenkins/examples/`](../../ci/jenkins/examples/) - you'll run all of them by S3
4. [`.github/workflows/`](../../.github/workflows/) - what you're replacing; note the localstack-demo exit-code gate
5. [docs/runbooks/localstack-demo.md](../runbooks/localstack-demo.md) - troubleshooting for the S2 port

## Working agreement & Definition of Done

- Branch-based flow; no direct pushes to `main`; CI green before merge; CODEOWNERS review.
- Daily 15-min standup; a blocker older than a day is escalated, not rediscovered at review.
- **Done** = merged to `main`, tests green, docs updated if behaviour changed, acceptance met, demoed on the 2nd-Friday review.
- Estimates are effort, not elapsed. If a task is running long, say so at standup - re-planning is normal; silent slippage is not.
