# Role Brief - AWS / MLOps Engineering

**Sprint 1: Mon Jun 15 -> Fri Jun 26, 2026** (10 working days). Source of truth: [`docs/absa-exl-agile-plan.xlsx`](../absa-exl-agile-plan.xlsx) Backlog sheet - task IDs match.

## Mission

You are three engineers running three parallel streams so the AWS foundation - the tightest track in any single-engineer version of this plan - never becomes the bottleneck. The platform's Terraform already exists (modules + per-env stacks) but has only ever run against LocalStack; your job is to take it to real EXL accounts and operate it.

- **AWS #1 - Foundation/Infra:** account bootstrap, state backends, landing zone, networking to ABSA, S3 replication, retention. The base everything else sits on.
- **AWS #2 - Platform Services:** signing foundation (KMS), registry-on-Lambda, cross-account verify, plus the IAM least-privilege + encryption-validation security work.
- **AWS #3 - Compute/MLOps:** the D04 compute decision, real Step Functions execution, the compute layer, EventBridge schedules, production scoring, performance, and DR.

**Front-loading is deliberate:** all three of you are busy S1-S7 building the foundation, then load drops sharply. After S7, AWS #2 and AWS #3 can ramp down or redeploy to model-optimization / MLOps support - that plan is made at the S5 capacity review. The late-program slack you'll see in your grid is the buffer that absorbs a late-ABSA-account-IDs slip without moving any gate date.

## The seats in this role

- **AWS** - AWS/MLOps Eng #1 - Foundation/Infra
- **AWS2** - AWS/MLOps Eng #2 - Platform Services
- **AWS3** - AWS/MLOps Eng #3 - Compute/MLOps

## Sprint 1 plan

### AWS (AWS/MLOps Eng #1 - Foundation/Infra) - 5.0 effort-days

| Task | Est (d) | Acceptance / Notes | Blocked on |
|---|---|---|---|
| T-0101 Clone repo, uv sync, run full 278-test suite locally | 0.5 | All engineers: 278-test suite green + `make demo` exit 0 locally; walkthrough attended. | - |
| T-0105 Run `make demo` (LocalStack chain) green locally | 0.5 | All engineers: 278-test suite green + `make demo` exit 0 locally; walkthrough attended. | - |
| T-0301 Module/stack review: gap notes vs real-AWS apply | 2.0 | terraform/ + account-bootstrap | - |
| T-0302 tfvars templates per env (awaiting account IDs) | 1.0 | CloudTrail/GuardDuty/SecurityHub live in 3 EXL accounts; TF state backends operational. | - |
| T-0303 State backend design: S3 + DynamoDB locks per account | 1.0 | CloudTrail/GuardDuty/SecurityHub live in 3 EXL accounts; TF state backends operational. | - |

### AWS2 (AWS/MLOps Eng #2 - Platform Services) - 1.0 effort-days

| Task | Est (d) | Acceptance / Notes | Blocked on |
|---|---|---|---|
| T-0101b Clone repo, uv sync, tests green locally | 0.5 | All engineers: 278-test suite green + `make demo` exit 0 locally; walkthrough attended. | - |
| T-0105b Run `make demo` green locally | 0.5 | All engineers: 278-test suite green + `make demo` exit 0 locally; walkthrough attended. | - |

### AWS3 (AWS/MLOps Eng #3 - Compute/MLOps) - 1.0 effort-days

| Task | Est (d) | Acceptance / Notes | Blocked on |
|---|---|---|---|
| T-0101c Clone repo, uv sync, tests green locally | 0.5 | All engineers: 278-test suite green + `make demo` exit 0 locally; walkthrough attended. | - |
| T-0105c Run `make demo` green locally | 0.5 | All engineers: 278-test suite green + `make demo` exit 0 locally; walkthrough attended. | - |

## Your load across the program (effort-days/sprint)

| Seat | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 | S9 | S10 | S11 | S12 | Cap |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AWS | 5.0 | 6.0 | 3.0 | 2.5 | - | 2.0 | 2.0 | - | 3.0 | 3.0 | 5.5 | - | 8 |
| AWS2 | 1.0 | 2.0 | 3.5 | 5.0 | - | - | 3.0 | - | - | - | - | - | 8 |
| AWS3 | 1.0 | - | 1.0 | - | 5.0 | 6.0 | 2.0 | 0.5 | - | - | - | - | 8 |

_Cap is 8 d/sprint per engineer (6 for TL), i.e. 10 working days x 0.8 focus factor. Loads sit below cap on purpose - the gap is ceremonies, review, and slack for the unknowns._

## Sprint-by-sprint focus

**S1 (Jun 15-Jun 26)** - _Team onboarded; Jenkins identity decided; python-validate green on Jenkins; ABSA ask-list sent_
- [AWS] Clone repo, uv sync, run full 278-test suite locally (0.5d)
- [AWS2] Clone repo, uv sync, tests green locally (0.5d)
- [AWS3] Clone repo, uv sync, tests green locally (0.5d)
- [AWS] Run `make demo` (LocalStack chain) green locally (0.5d)
- [AWS2] Run `make demo` green locally (0.5d)
- [AWS3] Run `make demo` green locally (0.5d)
- [AWS] Module/stack review: gap notes vs real-AWS apply (2.0d)
- [AWS] tfvars templates per env (awaiting account IDs) (1.0d)
- [AWS] State backend design: S3 + DynamoDB locks per account (1.0d)

**S2 (Jun 29-Jul 10)** - _All no-AWS Jenkins jobs live; AWS bootstrap applied; data contracts started; SAS model-1 review done_
- [AWS] Apply account-bootstrap to exl-dev/stg/prod (2.0d)
- [AWS] Apply state backends (1.0d)
- [AWS] Apply landing-zone module (dev first) (2.0d)
- [AWS] IP whitelisting coordination with ABSA network team (1.0d)
- [AWS2] identity_provider variable in signing-foundation TF (per T-0202) (2.0d)

**S3 (Jul 13-Jul 24)** - _Jenkins cutover complete (GHA retired); signing foundation live on real AWS; model-1 optimized_
- [AWS] Implement network connectivity per ABSA decision (3.0d)
- [AWS2] Apply signing stack to exl-prod; CMK + buckets + roles live (1.0d)
- [AWS2] Run publish-key; PEM in public bucket (0.5d)
- [AWS2] Lambda packaging for registry-api (adapter + artifact build) (2.0d)
- [AWS3] ADR: D04 compute choice (SFN+Lambda vs SageMaker) w/ architecture board (1.0d)

**S4 (Jul 27-Aug 07)** - _Registry API live on Lambda (dev); replication path validated; model-1 packaged; threat model done_
- [AWS2] Cross-account verify test with real ABSA principal (1.0d)
- [AWS2] Finish Lambda packaging + tests (1.0d)
- [AWS2] Apply APIGW+Lambda+DynamoDB registry stack (dev) + smoke (2.0d)
- [AWS2] Promote registry to stg + prod (1.0d)
- [AWS] Apply s3-replication source + destination modules (1.5d)
- [AWS] Encrypted transfer validated end-to-end with ABSA test object (1.0d)

**S5 (Aug 10-Aug 21)** - _SFN executes model-1 in dev; PIR sync; model-2 optimized; CAPACITY REVIEW (scale-up decision)_
- [AWS3] Deploy real ASL standard-batch for model-1 (dev) (3.0d)
- [AWS3] Build compute layer - core (Lambda container / SM Processing per D04) (2.0d)

**S6 (Aug 24-Sep 04)** - _DRESS REHEARSAL: full chain on real AWS for models 1-2; dashboards + perf harness; POPIA/SARB check_
- [AWS3] Build compute layer - finalize + integrate (2.0d)
- [AWS3] EventBridge schedules per model cadence (1.0d)
- [AWS3] Promote pipeline infra to prod (2.0d)
- [AWS3] Define SLA bands per model cadence (1.0d)
- [AWS] Dress rehearsal infra support + fixes (2.0d)

**S7 (Sep 07-Sep 18)** - _Group 1 initial production scoring; reconciliation; perf + resilience tests; UAT plan_
- [AWS] S3 lifecycle/retention policies authored per retention rules (1.0d)
- [AWS] Pre-go-live access review + least-privilege audit (1.0d)
- [AWS2] IAM least-privilege audit (automated policy analysis) (1.5d)
- [AWS2] Encryption validation: in-transit (TLS/replication) + at-rest (KMS) evidence (1.5d)
- [AWS3] Initial production scoring runs (models 1-2) (2.0d)

**S8 (Sep 21-Oct 02)** - _GROUP 1 ABSA SIGN-OFF; pen-test remediation; 2nd SAS dev onboarded; G2 plan_
- [AWS3] G1 production schedules confirmed live (0.5d)

**S9 (Oct 05-Oct 16)** - _Group 2 wave 1 (models 3-5) live; dashboards validated with ABSA; cost dashboard_
- [AWS] Model 3: deploy to prod + smoke (0.5d)
- [AWS] Model 3: pipeline config + EventBridge schedule (0.5d)
- [AWS] Model 4: deploy to prod + smoke (0.5d)
- [AWS] Model 4: pipeline config + EventBridge schedule (0.5d)
- [AWS] Model 5: deploy to prod + smoke (0.5d)
- [AWS] Model 5: pipeline config + EventBridge schedule (0.5d)

**S10 (Oct 19-Oct 30)** - _Group 2 wave 2 (models 6-8) live; output delivery automated_
- [AWS] Model 6: deploy to prod + smoke (0.5d)
- [AWS] Model 6: pipeline config + EventBridge schedule (0.5d)
- [AWS] Model 7: deploy to prod + smoke (0.5d)
- [AWS] Model 7: pipeline config + EventBridge schedule (0.5d)
- [AWS] Model 8: deploy to prod + smoke (0.5d)
- [AWS] Model 8: pipeline config + EventBridge schedule (0.5d)

**S11 (Nov 02-Nov 13)** - _Group 2 wave 3 (models 9-10) live - ALL 10 MODELS SCORING; runbooks; DR verified_
- [AWS] Cost review + right-sizing pass (2.0d)
- [AWS] DR plan + backup/restore verification (1.5d)
- [AWS] Model 9: deploy to prod + smoke (0.5d)
- [AWS] Model 9: pipeline config + EventBridge schedule (0.5d)
- [AWS] Model 10: deploy to prod + smoke (0.5d)
- [AWS] Model 10: pipeline config + EventBridge schedule (0.5d)

## ABSA dependencies that block your work

| Dependency | First bites | What it is |
|---|---|---|
| ABSA: IAM ARNs | S4 | IAM principal ARNs (kms:Verify / s3:GetObject) |
| ABSA: account IDs | S2 | AWS account IDs (3 EXL + ABSA receiving) |
| ABSA: data movement | S4 | Data movement decision (S3 replication vs SFTP) |
| ABSA: network choice | S2 | Network connectivity decision (peering / TGW / PrivateLink) |

The Tech Lead sends the consolidated ABSA ask-list in Sprint 1 (T-0113) and chases weekly. If any of the above is unanswered approaching its sprint, raise it in standup.

## Reading list (in order)

1. [docs/technical-overview.md](../technical-overview.md) - the system end-to-end
2. [ADR-0004](../adr/0004-account-topology-1-absa-3-exl.md) - account topology
3. [ADR-0009](../adr/0009-signing-foundation-topology.md) + [ADR-0003](../adr/0003-manifest-signing-kms-asymmetric.md) - signing trust model (AWS #2)
4. [ADR-0011](../adr/0011-ci-platform-jenkins.md) - the Jenkins identity decision shapes your signing-foundation trust policy
5. [docs/phase-3-closeout.md](../phase-3-closeout.md) - the 'Blocked on ABSA' + 'Not blocked' tables are your backlog rationale

## Working agreement & Definition of Done

- Branch-based flow; no direct pushes to `main`; CI green before merge; CODEOWNERS review.
- Daily 15-min standup; a blocker older than a day is escalated, not rediscovered at review.
- **Done** = merged to `main`, tests green, docs updated if behaviour changed, acceptance met, demoed on the 2nd-Friday review.
- Estimates are effort, not elapsed. If a task is running long, say so at standup - re-planning is normal; silent slippage is not.
