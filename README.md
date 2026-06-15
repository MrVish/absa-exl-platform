# ABSA × EXL Model Hosting & Delivery Operations

> **This is the single source of truth for the programme.** It explains what
> we're building and *why*, how it works, what is already done, what remains,
> who does what, how it sequences, and the language we use — and it links every
> other document. New to the project? Read this top to bottom, then follow the
> links that matter for your role. Returning? Jump via the [Contents](#contents).

**Status (2026-06):** Platform **built and regression-tested end-to-end** on
LocalStack (Phases 1–3 — 278 tests green, 23 PRs merged, full producer→verifier
chain runs on every PR). Next: a **12-sprint delivery programme** with an
8-person team to put it on real AWS, migrate CI to Jenkins, and onboard 10 ABSA
models to production.

---

## Contents

1. [What we're building](#1-what-were-building)
   - [1.1 The problem & context](#11-the-problem--context)
   - [1.2 The two tracks](#12-the-two-tracks)
   - [1.3 Model classes / pipeline tiers](#13-model-classes--pipeline-tiers)
   - [1.4 The PII / trust-boundary principle](#14-the-pii--trust-boundary-principle)
2. [Status at a glance](#2-status-at-a-glance)
3. [Architecture](#3-architecture)
   - [3.1 Diagrams](#31-diagrams)
   - [3.2 Chain of custody](#32-chain-of-custody-the-core-guarantee)
   - [3.3 Environments & account topology](#33-environments--account-topology)
   - [3.4 Tech stack](#34-tech-stack)
4. [Platform components](#4-platform-components)
5. [Platform invariants](#5-platform-invariants-the-rules-that-keep-it-trustworthy)
6. [What's done vs what's pending](#6-whats-done-vs-whats-pending)
7. [Dependencies on ABSA](#7-dependencies-on-absa)
8. [Delivery plan — 12 sprints](#8-delivery-plan--12-sprints)
9. [Team & roles](#9-team--roles)
10. [Open decisions](#10-open-decisions)
11. [Top risks](#11-top-risks)
12. [Compliance](#12-compliance)
13. [Getting started & conventions](#13-getting-started--conventions)
14. [Glossary](#14-glossary)
15. [Full documentation index](#15-full-documentation-index)
16. [Repository layout](#16-repository-layout)

---

## 1. What we're building

### 1.1 The problem & context

ABSA Group develops risk and decision models (credit PD, scorecards, etc.) in
SAS and Python. Today those models live in developer environments; getting them
into **governed, auditable, scheduled production scoring** is slow, manual, and
hard to evidence for regulators. ABSA's model-industrialisation programme exists
to fix that, and ABSA has engaged **EXL** to build and operate the hosting
platform.

EXL delivers a **production-grade, audit-ready ML hosting platform** that:

- takes a developer-authored model and **industrialises** it (standardises,
  optimises, packages, signs);
- **scores it on a schedule** on EXL-operated AWS infrastructure;
- **reconciles every run** against the developer's reference outputs;
- returns auditable results to ABSA — keeping **raw PII inside ABSA's AWS
  account**: only curated, model-ready data (no raw identifiers) crosses to EXL
  (see [1.4](#14-the-pii--trust-boundary-principle)).

Initial cohort: **10 models.** The platform is deliberately built so onboarding
the 11th / 20th / 50th model is **template-driven configuration, not a bespoke
project** each time.

### 1.2 The two tracks

The platform supports two distinct, registry-linked flows.

**Track A — Model Onboarding & Pipeline Factory** *(one-time per model)*

1. ABSA shares an approved model: dev code, supporting artefacts, input-variable
   spec, and **benchmark (reference) outputs**.
2. EXL's industrialisation team standardises and optimises the scoring code and
   assembles a **productized package** (`packages/<name>/<version>/`: SAS code,
   Python `score.py` + tests, `pir.yaml`, `model_config.yaml`).
3. **Code Intake** validates the package with five checkers and produces an
   **unsigned package manifest** (a digest over every artefact byte).
4. **Manifest Signer** signs the manifest with a KMS asymmetric key; the signed
   envelope lands in S3.
5. **Pipeline Factory** generates a scoring pipeline (Step Functions ASL +
   Terraform) for the model's class, cross-linking the upstream package by
   **digest**.
6. The pipeline is **registered** (SigV4-authenticated) into the registry, which
   gates promotion behind an approval state machine and writes an audit record.

**Track B — Scheduled Scoring & Delivery** *(recurring)*

1. ABSA's scheduler triggers a data hand-off; **model-ready** scoring inputs
   (curated in ABSA, raw identifiers removed) replicate cross-account into EXL
   via **encrypted S3 replication**. Raw PII stays in ABSA.
2. **EventBridge** fires the model's schedule → **Step Functions** runs the
   generated pipeline.
3. The **scoring compute** (Lambda container / SageMaker Processing) executes the
   signed, registered model code over the input data.
4. **Data-quality checks** (volume bands, PSI drift) and **reconciliation**
   against ABSA's benchmark run; deltas are reported within agreed tolerances.
5. Outputs are **signed** and delivered cross-account back to ABSA, who **verifies
   offline** with the published public key.
6. Every run emits an **audit trail**; CloudWatch + SNS handle monitoring and
   alerting.

### 1.3 Model classes / pipeline tiers

Pipeline Factory renders a pipeline from a **template chosen by the model's
class**, so each tier's controls are built once and reused:

| Tier | For | Status |
|---|---|---|
| **standard-batch** | Most batch-scored models (Lambda + Step Functions) | ✅ Implemented template |
| **scalable-batch** | High-volume batch (distributed / larger compute) | ✅ Implemented template |
| **realtime** | Synchronous / low-latency scoring | ⏳ Placeholder — SLA decision (D05) drives the build |

### 1.4 The PII / trust-boundary principle

The hard constraint that shapes the whole architecture: **raw PII never leaves
ABSA's AWS account.** What actually crosses the ABSA → EXL boundary — via
encrypted S3 replication, per [ADR-0001](docs/adr/0001-data-movement-s3-replication.md)
— is **model-ready data** (already curated inside ABSA, with raw identifiers
removed) plus the signed model code. So data *does* land in EXL's account, but
**raw PII does not**; this is the POPIA data-sovereignty posture (consistent with
[technical-overview](docs/technical-overview.md)).

Everything that crosses is held to a controlled, auditable perimeter:

- **Encrypted at rest both sides** with per-env KMS CMKs; **object-lock**
  (7-yr prod retention) on the buckets.
- **PrivateLink is control-plane only** (registry / status / delivery APIs);
  bulk data uses S3 replication, never the public internet, with no third-party
  data-mover in the path.
- **Full CloudTrail lineage** in both accounts; least-privilege replication role.
- Cross-account hand-offs are **cryptographically verifiable** — ABSA verifies
  every artefact EXL produces with only the published public key, never having
  to trust EXL's word, only the maths.

> Whether "model-ready, de-identified" data is fully outside POPIA scope is an
> ABSA compliance determination, tracked separately — not asserted here.

---

## 2. Status at a glance

| Area | Status | Notes |
|---|---|---|
| Platform code (registry, pipeline-factory, signer, code-intake, contracts) | ✅ **Built + tested** | 278 tests; runs the full chain on LocalStack every PR |
| LocalStack end-to-end demo (`make demo`) | ✅ **Green in CI** | Producer + verifier chain, cross-account simulated |
| Terraform (modules + per-env stacks) | ✅ **Written + validated** | ⏳ Not yet applied to real AWS (needs ABSA account IDs) |
| Scoring runtime (Step Functions execution) | ⏳ **Templates render; runtime not built** | `scoring-engine/` is a placeholder |
| PIR reconciliation engine | ⏳ **Not built** | `pir-engine/` is a placeholder (Phase 4) |
| CI on Jenkins (ADR-0011) | 🟡 **Scaffold done (M1)** | Shared library + 5 example Jenkinsfiles; cutover (M2/M3) pending |
| Real-AWS deployment | ⏳ **Pending** | Blocked on ABSA inputs — see §7 |
| 10-model onboarding | ⏳ **Pending** | The substance of the 12-sprint plan — see §8 |

**The one sentence:** the platform is built and proven on LocalStack; the work
ahead is putting it on real AWS, swapping CI to Jenkins, and onboarding 10
models — all captured in the delivery plan (§8), most of it gated on ABSA inputs
(§7). Detailed build closeout: **[docs/phase-3-closeout.md](docs/phase-3-closeout.md)**.

---

## 3. Architecture

### 3.1 Diagrams

Five rendered, regenerate-from-code diagrams in
**[docs/architecture/](docs/architecture/README.md)**:

| Diagram | Shows |
|---|---|
| [Platform overview](docs/architecture/01-platform-overview.png) | Cross-account topology, both tracks, security baseline |
| [Track A — onboarding](docs/architecture/02-track-a-onboarding.png) | Code Intake → Sign → Pipeline Factory → Registry |
| [Track B — scoring](docs/architecture/03-track-b-scoring.png) | EventBridge → Step Functions → compute → DQ → sign → deliver |
| [Chain of custody](docs/architecture/04-chain-of-custody.png) | KMS asymmetric signing + cross-account verification |
| [CI/CD — Jenkins](docs/architecture/05-cicd-jenkins.png) | The ADR-0011 migration |

Written architecture: [docs/architecture.md](docs/architecture.md) ·
End-to-end technical walkthrough: [docs/technical-overview.md](docs/technical-overview.md) ·
Decisions (11 ADRs): [docs/adr/](docs/adr/) (index in §15).

### 3.2 Chain of custody (the core guarantee)

The platform's signature property — what makes EXL's outputs trustworthy to
ABSA and auditors:

- Every manifest is a **canonical-JSON envelope** (`payload` + `signature` +
  `signing_key_arn` + `subject_type`). Canonical JSON makes the byte
  representation **deterministic**, so a signature is reproducible.
- Signing uses a **KMS asymmetric CMK** — RSA-3072, key usage `SIGN_VERIFY`,
  algorithm `RSASSA_PKCS1_V1_5_SHA_256`. The private key never leaves KMS; the
  public key is published (PEM) to a cross-account-readable S3 bucket.
- **The digest anchor:** a package manifest's `digest` equals the pipeline
  manifest's `upstream_refs[0].digest` equals `sha256(canonical_json(payload))`.
  This chains package → pipeline → registry record, and **holds across signing,
  the S3 round-trip, and a cross-account read** by a different AWS session. The
  canonical demo proves it end-to-end (chain digest
  `7905ac3a…c8870b`).
- ABSA **verifies offline** with only the published PEM — no live call to EXL's
  KMS required.

This is specified in [ADR-0003](docs/adr/0003-manifest-signing-kms-asymmetric.md)
and [ADR-0009](docs/adr/0009-signing-foundation-topology.md).

### 3.3 Environments & account topology

Per [ADR-0004](docs/adr/0004-account-topology-1-absa-3-exl.md): **1 ABSA account
+ 3 EXL accounts** (`exl-dev`, `exl-stg`, `exl-prod`). The signing CMK and
production scoring live in `exl-prod`; lower environments mirror the topology for
safe iteration.

The **LocalStack demo simulates the cross-account boundary** with header-based
account IDs — producer under `111111111111` (`exl-prod-sim`), verifier under
`222222222222` (`absa-sim`) — exercising the real IAM policy evaluation without
real accounts. When real accounts land, the demo's structure becomes the
production flow: same CLIs, same code paths, same chain-of-custody assertions;
only the endpoints and the boto3 session shape change.

### 3.4 Tech stack

| Layer | Technology |
|---|---|
| Language / tooling | Python 3.12, **uv** workspace (monorepo), ruff, mypy --strict, pytest |
| Contracts | JSON Schema (Draft 2020-12), **canonical JSON**, datamodel-code-generator → Pydantic v2 |
| Services (apps/CLIs) | FastAPI (registry), **Click** CLIs (code-intake, pipeline-factory, manifest-signer) |
| AWS | IAM (cross-account), **KMS** (asymmetric CMK), S3 (replication, object-lock), DynamoDB, Lambda, API Gateway, **Step Functions** (ASL), EventBridge, CloudTrail, GuardDuty, Security Hub |
| IaC | Terraform 1.9.5 (modules + per-env stacks), tflint / tfsec / checkov |
| Local / test | **LocalStack** CE 3.8.1, moto, Docker / docker-compose |
| CI/CD | GitHub Actions (today) → **Jenkins** shared library / Groovy (ADR-0011, in migration) |
| Compute (Track B) | Lambda container and/or SageMaker Processing (**D04** decides) |

---

## 4. Platform components

Python **uv workspace** (monorepo). Each member is independently testable; the
full suite runs on every PR.

| Component | Purpose | Key surface | Status |
|---|---|---|---|
| [`platform-contracts/`](platform-contracts/) | The contract backbone — JSON-Schema definitions, generated Pydantic models (with a drift guard so code can't diverge from schema), and the shared `canonical_json` | `schemas/*.schema.json`, `models.py`, `canonical.py` | ✅ Built |
| [`code-intake/`](code-intake/README.md) | Validates a productized package and produces the signed package manifest | 5 checkers (`static_python`, `static_sas`, `schema`, `tests`, `pir`) in per-package venvs; CLI `validate` / `generate-manifest`; finding codes PY/SAS/SCH/TST/PIR | ✅ Built (real SAS lint deferred — needs ABSA runtime) |
| [`pipeline-factory/`](pipeline-factory/) | Generates the scoring pipeline from a model config and registers it | CLI `generate` / `register` (SigV4); standard-batch + scalable-batch ASL templates; realtime placeholder; per-pipeline Terraform stub | ✅ Built |
| [`manifest-signer/`](manifest-signer/) | KMS asymmetric signing + verification | CLI `sign` / `sign-all` / `verify-online` / `verify-offline` / `verify-from-bucket` / `publish-key`; idempotent S3 upload | ✅ Built |
| [`registry/api/`](registry/) | Model & Pipeline Registry | FastAPI + DynamoDB; approval state machine (CAB/IVU evidence gates promotion); append-only audit log; `/healthz` `/readyz` | ✅ Built (Lambda packaging pending) |
| [`packages/`](packages/) | Worked-example productized package | `credit-risk-pd@1.0.0` | ✅ Example |
| [`pipelines/`](pipelines/) | Generated per-version pipeline artifacts | `credit-risk-pd/1.0.0/` (manifest, registration, terraform) | ✅ Example |
| [`scoring-engine/`](scoring-engine/README.md) | Step Functions / Spark scorers (runtime execution) | — | ⏳ Placeholder (Bucket A) |
| [`pir-engine/`](pir-engine/README.md) | Post-implementation-review reconciliation | — | ⏳ Placeholder (Phase 4) |
| [`terraform/`](terraform/) | All IaC | modules: landing-zone, s3-replication-{source,destination}, kms-hierarchy, iam-federation, pipeline-registry, signing-foundation; per-env stacks; account-bootstrap | ✅ Written/validated; apply pending |
| [`infra/localstack/`](infra/localstack/) | LocalStack compose + terraform for the demo | `docker-compose.yml`, `terraform/` | ✅ Built |
| [`ci/jenkins/`](ci/jenkins/README.md) | Jenkins shared library (`absa-ci`) + 5 example Jenkinsfiles | `vars/` steps (setupUv, awsLogin, publishStatus, postPrComment); `examples/*.Jenkinsfile` | 🟡 Scaffold (M1) |
| [`scripts/demo/`](scripts/) | `make demo` orchestrator | 7-step producer chain + 7-step verifier chain against LocalStack | ✅ Built |
| [`scripts/`](scripts/) | Programme tooling | agile-plan / kickoff-brief / architecture-diagram generators + `audit_agile_plan.py` | ✅ Built |

---

## 5. Platform invariants (the rules that keep it trustworthy)

These are the properties that must never silently break — CI enforces most of
them. If you're changing the platform, protect these:

1. **Byte-stable manifests.** `code-intake generate-manifest` and
   `pipeline-factory generate` are deterministic; CI re-renders every fixture
   and fails on any diff (`git diff --exit-code`). A "drift gate."
2. **Schema ↔ model parity.** Generated Pydantic models must match the JSON
   schemas; the drift guard regenerates and fails on diff.
3. **The chain-of-custody digest anchor** (§3.2) must hold end-to-end — the
   LocalStack demo asserts it on every PR.
4. **No hand-edited manifests.** `manifest.json` is generated; signed copies
   live in S3, unsigned copies in git. Edit the source + regenerate.
5. **Signatures are reproducible.** Canonical JSON + a fixed KMS algorithm mean
   the same payload always produces a verifiable signature.
6. **CI green before merge.** Branch protection + CODEOWNERS; the
   `localstack-demo` gate distinguishes platform regressions (block) from infra
   flakes (warn) via exit codes 0/1/2/3.
7. **Generated docs regenerate from code.** The agile plan, role briefs,
   architecture diagrams, and skills matrix are emitted by `scripts/` — edit the
   generator, not the output.

---

## 6. What's done vs what's pending

The **build phase is essentially closed.** What remains splits into three buckets:

### Bucket A — buildable now (the demo→production gap, ~7–11 engineer-weeks)
No ABSA input required; the code between "works on LocalStack" and "deployable to real AWS":

| Item | Effort |
|---|---|
| Lambda packaging for `registry-api` | ~5–7 d |
| Step Functions ASL **runtime** execution (`scoring-engine`) | ~5–8 d |
| Real cross-account IAM via `sts:AssumeRole` | ~4–5 d |
| Stricter PIR extraction (dict aliases, `.get()`, cross-function) | ~5–7 d |
| Multi-package chaining scenarios | ~3–5 d |
| KMS key-rotation automation (runbook exists) | ~3–4 d |
| Multi-region KMS replica | ~3–4 d |
| SCH002 / SCH003 deferred checks | ~2–3 d |
| Realtime ASL template (only if a realtime model is in scope) | ~5–8 d |

### Bucket B — blocked on ABSA (can't complete until inputs land)
Real account onboarding · real SAS validation (SAS runtime) · PIR system
integration · CAB/IVU integration · first real Track A scoring run ·
cross-account verifier against real AWS. See §7.

### Bucket C — Jenkins migration (ADR-0011, ~10–15 DevOps-days)
M1 scaffold **done**; M2 (AWS-touching ports + `identity_provider` Terraform) and
M3 (cutover, GHA retirement) pending; partly gated on the AWS identity decision.

> **Key framing:** Buckets A, B and C are not separate from the delivery plan —
> they *are* its early epics (§8). The genuinely *new, unplanned* code is small:
> the realtime template and SCH002/003 (~5 days total).

---

## 7. Dependencies on ABSA

Every top programme risk is an ABSA dependency. Tracked live in the **RAID Log**
sheet of [docs/absa-exl-agile-plan.xlsx](docs/absa-exl-agile-plan.xlsx); the Tech
Lead sends the consolidated ask-list in Sprint 1 and chases weekly.

| # | Dependency | First needed | If late |
|---|---|---|---|
| 1 | AWS account IDs (3 EXL + ABSA receiving) | Sprint 2 | Bootstrap blocked; everything downstream slips day-for-day |
| 2 | IAM principal ARNs (`kms:Verify` / `s3:GetObject`) | Sprint 4 | Cross-account verify untestable |
| 3 | SAS runtime Docker image + license | Sprint 2–3 | SAS validation stays structural-only |
| 4 | PIR system API / feed contract | Sprint 5 | `pir.yaml` stays hand-maintained |
| 5 | Data-movement decision (S3 replication vs SFTP) | Sprint 4 | Transfer + delivery automation blocked |
| 6 | CAB / IVU API contract | Sprint 5 | Change workflow stays manual |
| 7 | Network connectivity (peering / TGW / PrivateLink) | Sprint 3 | Data plane to ABSA blocked |
| 8 | Approved model docs + code + benchmarks (models 1–2) | Sprint 2 | SAS + DE model work blocked |

**Sprint 1 is fully unblocked** by design — the team is productive from day one
regardless of ABSA's timing.

---

## 8. Delivery plan — 12 sprints

Two-week sprints, **start Mon 2026-06-15**, ~6 months. Full backlog (13 epics /
52 stories / ~248 tasks, capacity-validated, feasibility-audited) in
**[docs/absa-exl-agile-plan.xlsx](docs/absa-exl-agile-plan.xlsx)**; client-facing
walkthrough in
[docs/absa-exl-program-walkthrough.pptx](docs/absa-exl-program-walkthrough.pptx).

| Sprint | Dates (approx) | Focus | Milestone |
|---|---|---|---|
| S1 | Jun 15–26 | Onboarding; Jenkins identity decided; ABSA ask-list sent | |
| S2 | Jun 29–Jul 10 | No-AWS Jenkins jobs; AWS bootstrap; data contracts; model-1 review | |
| S3 | Jul 13–24 | Jenkins cutover; signing foundation on real AWS; model-1 optimized | **GHA retired** |
| S4 | Jul 27–Aug 7 | Registry on Lambda (dev); replication validated; threat model | **Registry live (dev)** |
| S5 | Aug 10–21 | SFN executes model-1; PIR sync; model-2 optimized; **capacity review** | |
| S6 | Aug 24–Sep 4 | **Dress rehearsal** (full chain, real AWS, models 1–2); dashboards | **Dress rehearsal** |
| S7 | Sep 7–18 | Group 1 production scoring; reconciliation; perf + resilience; UAT plan | |
| S8 | Sep 21–Oct 2 | Pen-test remediation; 3rd SAS onboarded; G2 plan | ⭐ **GROUP 1 SIGN-OFF** |
| S9 | Oct 5–16 | Group 2 wave 1 (models 3–5); dashboards validated; cost dashboard | |
| S10 | Oct 19–30 | Group 2 wave 2 (models 6–8); output delivery automated | |
| S11 | Nov 2–13 | Group 2 wave 3 (models 9–10); runbooks; DR verified | **All 10 live** |
| S12 | Nov 16–27 | Hardening only; handover; hypercare | ⭐ **GROUP 2 SIGN-OFF + go-live** |

Group 2's 8 models are compressed into S9–S11 so S12 is hardening + sign-off, not
a race. The plan is **feasibility-audited** (`scripts/audit_agile_plan.py`):
dependency ordering clean, no capacity overloads, S1 unblocked, all 10 models
covered.

---

## 9. Team & roles

**8 people.** Per-role kickoff briefs (mission, Sprint 1 tasks, full-program
load, ABSA blockers, reading list) in
**[docs/onboarding/](docs/onboarding/README.md)**, generated from the backlog so
they never drift.

| Seat | Role | Brief |
|---|---|---|
| AWS, AWS2 | AWS/MLOps — Foundation/Infra + Platform/Compute/MLOps | [aws-mlops](docs/onboarding/role-brief-aws-mlops.md) |
| SAS, SAS2, SAS3 | SAS Developers (2 from S1, 1 from S8) | [sas](docs/onboarding/role-brief-sas.md) |
| DE | Data Engineer | [data-engineer](docs/onboarding/role-brief-data-engineer.md) |
| DevOps | DevOps Engineer | [devops](docs/onboarding/role-brief-devops.md) |
| TL | Tech Lead (Vishnu) | [tech-lead](docs/onboarding/role-brief-tech-lead.md) |

**Onboarding a new joiner?** Per-role skillsets (Core / Ramp-up / Bonus) in
**[docs/onboarding/skills-matrix.md](docs/onboarding/skills-matrix.md)**.

---

## 10. Open decisions

Tracked as D01–D09 (RAID Log + the program-plan workbook). Status as of 2026-06:
all **Open**.

| ID | Decision | Owner(s) | Gates |
|---|---|---|---|
| D01 | Data-drift framework — metrics (PSI/KL), window, manual vs automated | ABSA Risk + EXL ML | DQ/drift dashboards (S8); steady-state anomaly review |
| D02 | Change-management workflow — registry approval vs separate CAB/IVU flow | Compliance + ABSA Risk | First production change (Group 1) |
| D03 | Access / secret rotation cadence (IAM, tokens, dashboard access) | Compliance | Audit posture before steady state |
| **D04** | **ML compute platform — Step Functions + Lambda vs SageMaker** | Tech Lead + Arch Board | **Track B build (S5)** |
| D05 | Real-time tier SLA + implementation (Lambda+APIGW / Fargate / SM endpoint) | Tech Lead + ABSA Architect | Realtime template (placeholder today) |
| D06 | Data-movement — S3 cross-account replication vs SFTP | ABSA Architect + EXL Cloud | Secure transfer build (S4) |
| D07 | Single-region (eu-west-1) vs multi-region | ABSA Architect | KMS replica + signing-foundation scope |
| D08 | Dashboard hosting — Grafana / CloudWatch / QuickSight | Program Mgr + ABSA Risk | Dashboard build (S8b) |
| D09 | Output-delivery format — signed S3 / SFTP push / API pull | ABSA Architect + EXL Cloud | Delivery runbook + automation |
| (ADR-0011) | Jenkins identity model — IRSA-on-EKS / instance profile / OIDC | DevOps + ABSA Cloud | Signing-foundation trust policy (M2) |

---

## 11. Top risks

From the RAID Log (probability / impact). Full register in the agile-plan
workbook.

| ID | Risk | P/I | Mitigation |
|---|---|---|---|
| RISK-01 | ABSA account onboarding delayed past S2 | High / Med | 2 AWS engineers + ~2 d/sprint S2–S5 slack; pre-stage TF; LocalStack keeps CI green; escalate end S1 |
| RISK-02 | Group 1 sign-off (S8) slips → cascades to Group 2 | Med / High | Models 1–2 run in **parallel** (2 SAS) from S2; dress rehearsal S6; defect buffer S7–S8 |
| RISK-03 | D04 compute choice blocks the S5 build | Med / Med | Decision required end S3 at architecture board; AWS2 owns it |
| RISK-04 | Benchmark reconciliation forces scoring-code rewrite | Med / High | Incremental validation; per-variable deltas; tolerance bands agreed early; S11 float + S12 hardening absorb rework |
| RISK-07 | DevOps is the only un-doubled role (S2 / S6 peaks) | Med / Med | TL pairs at peaks; watch S2 (Jenkins crunch) + S6 |

---

## 12. Compliance

POPIA · SARB GOI 3/5 · SR 11-7 · ISO 27001 · SOC 2 Type II · ABSA GMRMG.
Control matrix (per-phase, with evidence pointers):
**[docs/compliance/control-matrix.md](docs/compliance/control-matrix.md)**.

The chain-of-custody design (§3.2), the append-only audit log, object-lock
retention, and the per-account security baseline (CloudTrail / GuardDuty /
Security Hub / CIS alarms) are the primary evidence-producing controls.

---

## 13. Getting started & conventions

```bash
# Prereqs: Python 3.12, uv, Docker, Terraform 1.9.5
uv sync --frozen --all-extras       # install the workspace
uv run pytest -v                    # run the full test suite (278 tests)
make demo                           # run the end-to-end chain on LocalStack
```

**Fastest way to understand the platform** (any role): run `make demo`, then
trace one model through `packages/credit-risk-pd/1.0.0/` → `code-intake validate`
→ `pipeline-factory` → `manifest-signer` → the verifier. That single trace
touches ~80% of the concepts. Demo runbook:
[docs/runbooks/localstack-demo.md](docs/runbooks/localstack-demo.md).

**Conventions**
- **Branch-based flow** — no direct pushes to `main`; every change is a PR; CI
  green before merge; CODEOWNERS review.
- **Definition of Done** — merged, tests green, docs updated if behaviour
  changed, acceptance criteria met, demoed on the sprint review.
- **Regenerating generated docs** — edit the generator in `scripts/`, not the
  output: `build_agile_plan.py` (the Excel), `build_kickoff_briefs.py` (role
  briefs), `build_aws_diagrams.py` (architecture PNGs), `audit_agile_plan.py`
  (feasibility check). Keep the schema-generated `models.py` in sync via
  `platform-contracts/regenerate-models.sh`.
- **This README first** — when the plan or platform changes, update this file
  before anything else; it's the spine.

---

## 14. Glossary

| Term | Meaning |
|---|---|
| **ABSA** | The client bank; owns the models, the data, and the trust boundary |
| **EXL** | The delivery partner; builds + operates the hosting platform |
| **Track A** | One-time model onboarding → packaged, signed, registered (§1.2) |
| **Track B** | Recurring scheduled scoring + delivery (§1.2) |
| **Productized package** | A git-tracked `packages/<name>/<version>/` bundle: SAS + Python code, tests, `pir.yaml`, `model_config.yaml`, manifest |
| **`model_config.yaml`** | The package contract — declares model class, inputs, schedule, etc. |
| **Manifest** | A signed JSON envelope describing an artefact. *Package* manifest (Code Intake) and *pipeline* manifest (Pipeline Factory) |
| **Manifest envelope** | `payload` + `signature` + `signing_key_arn` + `subject_type` |
| **Canonical JSON** | Deterministic byte serialisation so signatures are reproducible |
| **Chain of custody / digest anchor** | package.digest == pipeline.upstream_ref == sha256(canonical_json(payload)) (§3.2) |
| **Code Intake** | Validator that produces the signed package manifest (5 checkers) |
| **Pipeline Factory** | Generates the scoring pipeline (ASL + Terraform) from a model config |
| **Manifest Signer** | KMS asymmetric sign / verify / publish |
| **Registry** | Model & pipeline registry — approval gate + audit log |
| **PIR** | Production Input Register — the authority on a model's input variables; used for reconciliation evidence |
| **CAB / IVU** | Change Advisory Board / Independent Validation Unit — ABSA governance bodies that gate production changes |
| **ASL** | Amazon States Language — the Step Functions definition language |
| **CMK** | Customer Master Key (AWS KMS); here an asymmetric RSA-3072 SIGN_VERIFY key |
| **SigV4** | AWS Signature Version 4 — used to authenticate registry calls |
| **IRSA** | IAM Roles for Service Accounts (EKS) — a Jenkins↔AWS auth option (ADR-0011) |
| **Drift gate** | CI check that re-renders artefacts and fails on any diff (byte-stability) |
| **LocalStack / moto** | Local AWS emulation for the demo / unit tests |
| **uv** | The Python package/workspace manager used across the monorepo |
| **ADR** | Architecture Decision Record (`docs/adr/`) |
| **RAID** | Risks, Assumptions, Issues, Dependencies (a sheet in the agile plan) |
| **MoSCoW** | Must / Should / Could / Won't prioritisation (on backlog stories) |
| **DoR / DoD** | Definition of Ready / Definition of Done |
| **SR 11-7 / POPIA / SARB GOI / GMRMG** | US model-risk guidance / SA data-protection law / SA Reserve Bank governance / ABSA Group Model Risk Mgmt Guideline |

---

## 15. Full documentation index

### Start here
- **This README** — single source of truth
- [docs/program-flow.md](docs/program-flow.md) — end-to-end techno-functional narrative
- [docs/technical-overview.md](docs/technical-overview.md) — technical deep-dive
- [docs/phase-3-closeout.md](docs/phase-3-closeout.md) — what's built vs deferred
- [CLAUDE_CODE_BRIEF.md](CLAUDE_CODE_BRIEF.md) — original engagement brief

### Architecture & decisions
- [docs/architecture/](docs/architecture/README.md) — the 5 rendered diagrams
- [docs/architecture.md](docs/architecture.md) — written architecture
- ADRs: [0001 data-movement](docs/adr/0001-data-movement-s3-replication.md) ·
  [0002 dual-module IaC](docs/adr/0002-cross-account-iac-dual-module-split.md) ·
  [0003 KMS signing](docs/adr/0003-manifest-signing-kms-asymmetric.md) ·
  [0004 account topology](docs/adr/0004-account-topology-1-absa-3-exl.md) ·
  [0005 KMS hierarchy](docs/adr/0005-kms-hierarchy-audit-evidence-only.md) ·
  [0006 contract strategy](docs/adr/0006-contract-strategy-json-schema-canonical.md) ·
  [0007 registry model/API](docs/adr/0007-registry-data-model-and-api.md) ·
  [0008 generator dual-mode](docs/adr/0008-generator-runtime-dual-mode.md) ·
  [0009 signing foundation](docs/adr/0009-signing-foundation-topology.md) ·
  [0010 package contract](docs/adr/0010-productized-package-contract.md) ·
  [0011 CI → Jenkins](docs/adr/0011-ci-platform-jenkins.md)

### Delivery & planning
- [docs/absa-exl-agile-plan.xlsx](docs/absa-exl-agile-plan.xlsx) — backlog + Sprint Plan + Role Load + RAID + Per-Model Tracker
- [docs/absa-exl-program-plan.xlsx](docs/absa-exl-program-plan.xlsx) — phase-level program plan
- [docs/absa-exl-program-walkthrough.pptx](docs/absa-exl-program-walkthrough.pptx) — client walkthrough deck
- [docs/onboarding/](docs/onboarding/README.md) — role briefs + [skills matrix](docs/onboarding/skills-matrix.md)

### Operations
- [docs/runbooks/localstack-demo.md](docs/runbooks/localstack-demo.md)
- [docs/runbooks/kms-key-rotation.md](docs/runbooks/kms-key-rotation.md)
- [docs/runbooks/sample-transcripts/](docs/runbooks/sample-transcripts/2026-06-09-demo.md) — canonical green-demo transcript

### Specs & plans (per sprint)
- [docs/superpowers/specs/](docs/superpowers/specs/) — design specs, Phase 1 → Phase 3
- [docs/superpowers/plans/](docs/superpowers/plans/) — implementation plans

### Component READMEs
- [code-intake](code-intake/README.md) · [ci/jenkins](ci/jenkins/README.md) ·
  Terraform module READMEs under [terraform/modules/](terraform/)

---

## 16. Repository layout

```
docs/             Architecture, ADRs, runbooks, compliance, delivery plans, onboarding
platform-contracts/  JSON-Schema contracts + generated Pydantic models + canonical_json
code-intake/      Package validators (5 checkers) + signed package manifest
pipeline-factory/ Pipeline generator: validate / generate / register CLI
manifest-signer/  KMS asymmetric sign / verify / publish
registry/         Model & Pipeline Registry API (FastAPI + DynamoDB)
packages/         Worked-example productized package (credit-risk-pd)
pipelines/        Generated per-version pipeline artifacts
scoring-engine/   Step Functions / Spark scorers (placeholder)
pir-engine/       PIR reconciliation (placeholder, Phase 4)
terraform/        Infrastructure as code (modules + per-env stacks)
infra/localstack/ LocalStack compose + terraform for the demo
ci/jenkins/       Jenkins shared library + example Jenkinsfiles (ADR-0011)
scripts/          demo orchestrator + programme tooling (plan/brief/diagram generators)
```

---

*Maintained by the EXL ML Platform team. When the plan or platform changes,
update this file first — it is the source everything else hangs off.*
