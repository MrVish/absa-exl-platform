# ABSA × EXL Model Hosting & Delivery Operations

> **This is the single source of truth for the programme.** It explains what
> we're building, what is already done, what remains, who does what, and how it
> all sequences — and links every other document. New to the project? Read this
> top to bottom, then follow the links that matter for your role.

**Status (2026-06):** Platform **built and regression-tested end-to-end** on
LocalStack (Phases 1–3, 278 tests green, 22 PRs merged). Next: a **12-sprint
delivery programme** with an 8-person team to put it on real AWS, migrate CI to
Jenkins, and onboard 10 ABSA models to production.

---

## Contents

1. [What we're building](#1-what-were-building)
2. [Status at a glance](#2-status-at-a-glance)
3. [Architecture](#3-architecture)
4. [Platform components](#4-platform-components)
5. [What's done vs what's pending](#5-whats-done-vs-whats-pending)
6. [Dependencies on ABSA](#6-dependencies-on-absa)
7. [Delivery plan — 12 sprints](#7-delivery-plan--12-sprints)
8. [Team & roles](#8-team--roles)
9. [Open decisions](#9-open-decisions)
10. [Compliance](#10-compliance)
11. [Getting started](#11-getting-started)
12. [Full documentation index](#12-full-documentation-index)

---

## 1. What we're building

EXL is delivering a **production-grade, audit-ready ML hosting platform** for
ABSA Group's model-industrialisation programme. It productionises
developer-authored **SAS / Python** models, scores them on a schedule, and
reconciles every run against the developer's reference evidence — **without raw
PII ever leaving the ABSA trust boundary.**

Initial cohort: **10 models.** The platform is built to make onboarding the
11th, 20th, 50th model a repeatable, template-driven exercise rather than a
bespoke project each time.

### The two tracks

| Track | What it does | Cadence |
|---|---|---|
| **A — Model Onboarding & Pipeline Factory** | A developer model is industrialised, packaged with a **signed manifest**, validated by Code Intake, and registered. A scoring pipeline is generated from a template based on the model's class. | One-time per model |
| **B — Scheduled Scoring & Delivery** | ABSA hands off data via cross-account S3 replication. EXL validates, scores, runs data-quality + reconciliation checks, signs the output, and delivers results back to ABSA. | Recurring (per-model schedule) |

### The non-negotiables (why the platform is shaped the way it is)

- **Auditable** — every artifact is cryptographically signed; every state
  change is logged; a full chain-of-custody runs from intake to delivery.
- **Repeatable** — pipeline templates + a model registry turn onboarding into
  configuration, not construction.
- **Cross-account** — ABSA and EXL operate in separate AWS accounts with
  cryptographically verifiable hand-offs; PII stays in ABSA's boundary.
- **Banking-grade** — POPIA / SARB / SR 11-7 / model-risk governance are
  designed in, not bolted on.

Full narrative for a techno-functional audience: **[docs/program-flow.md](docs/program-flow.md)**.
Original engagement brief: **[CLAUDE_CODE_BRIEF.md](CLAUDE_CODE_BRIEF.md)**.

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
| Real-AWS deployment | ⏳ **Pending** | Blocked on ABSA inputs — see §6 |
| 10-model onboarding | ⏳ **Pending** | The substance of the 12-sprint plan — see §7 |

**The one sentence:** the platform is built and proven on LocalStack; the work
ahead is putting it on real AWS, swapping CI to Jenkins, and onboarding 10
models — all captured in the delivery plan (§7), most of it gated on ABSA
inputs (§6).

Detailed build closeout: **[docs/phase-3-closeout.md](docs/phase-3-closeout.md)**.

---

## 3. Architecture

Five rendered, regenerate-from-code diagrams live in
**[docs/architecture/](docs/architecture/README.md)**:

| Diagram | Shows |
|---|---|
| [Platform overview](docs/architecture/01-platform-overview.png) | Cross-account topology, both tracks, security baseline |
| [Track A — onboarding](docs/architecture/02-track-a-onboarding.png) | Code Intake → Sign → Pipeline Factory → Registry |
| [Track B — scoring](docs/architecture/03-track-b-scoring.png) | EventBridge → Step Functions → compute → DQ → sign → deliver |
| [Chain of custody](docs/architecture/04-chain-of-custody.png) | KMS asymmetric signing + cross-account verification |
| [CI/CD — Jenkins](docs/architecture/05-cicd-jenkins.png) | The ADR-0011 migration |

- **Written architecture:** [docs/architecture.md](docs/architecture.md)
- **End-to-end technical walkthrough:** [docs/technical-overview.md](docs/technical-overview.md)
- **Decisions (11 ADRs):** [docs/adr/](docs/adr/) — see the index in §12.

**The chain-of-custody anchor** (the platform's signature guarantee): a package
manifest's `digest` equals the pipeline manifest's `upstream_refs[0].digest`
equals `sha256(canonical_json(payload))` — and it holds across signing, the S3
round-trip, and a cross-account read. KMS asymmetric CMK (RSA-3072,
`RSASSA_PKCS1_V1_5_SHA_256`); ABSA verifies offline with only the published PEM.

---

## 4. Platform components

Python **uv workspace** (monorepo). Each member is independently testable.

| Component | Purpose | Status |
|---|---|---|
| [`platform-contracts/`](platform-contracts/) | JSON-Schema contracts (Draft 2020-12) + generated Pydantic models + drift guard + `canonical_json` | ✅ Built |
| [`code-intake/`](code-intake/README.md) | Validates a productized package — 5 checkers (static_python, static_sas, schema, tests, pir) in per-package venvs; builds the signed package manifest | ✅ Built (real SAS lint deferred) |
| [`pipeline-factory/`](pipeline-factory/) | Generates the scoring pipeline (ASL + Terraform) from a model config; registers it (SigV4). Standard-batch + scalable-batch templates; realtime is a placeholder | ✅ Built |
| [`manifest-signer/`](manifest-signer/) | KMS asymmetric signing + verify (online / offline / from-bucket) + public-key publish | ✅ Built |
| [`registry/api/`](registry/) | Model & Pipeline Registry — FastAPI + DynamoDB, approval state machine, append-only audit log | ✅ Built (Lambda packaging pending) |
| [`packages/`](packages/) | Worked-example productized package (`credit-risk-pd@1.0.0`) | ✅ Example |
| [`pipelines/`](pipelines/) | Generated per-version pipeline artifacts | ✅ Example |
| [`scoring-engine/`](scoring-engine/README.md) | Step Functions / Spark scorers (runtime execution) | ⏳ Placeholder |
| [`pir-engine/`](pir-engine/README.md) | Post-implementation-review reconciliation | ⏳ Placeholder (Phase 4) |
| [`terraform/`](terraform/) | All IaC — landing-zone, s3-replication, kms-hierarchy, iam-federation, pipeline-registry, signing-foundation modules + per-env stacks | ✅ Written/validated; apply pending |
| [`infra/localstack/`](infra/localstack/) | LocalStack compose + terraform for the end-to-end demo | ✅ Built |
| [`ci/jenkins/`](ci/jenkins/README.md) | Jenkins shared library (`absa-ci`) + 5 example Jenkinsfiles (ADR-0011) | 🟡 Scaffold (M1) |
| [`scripts/demo/`](scripts/) | `make demo` orchestrator — producer + verifier chain | ✅ Built |
| [`scripts/`](scripts/) | Programme tooling: agile-plan / kickoff-brief / architecture-diagram generators + feasibility audit | ✅ Built |

---

## 5. What's done vs what's pending

The **build phase is essentially closed.** What remains splits into three
buckets:

### Bucket A — buildable now (the demo→production gap, ~7–11 engineer-weeks)
No ABSA input required; this is the code between "works on LocalStack" and
"deployable to real AWS":

| Item | Effort |
|---|---|
| Lambda packaging for `registry-api` | ~5–7 d |
| Step Functions ASL **runtime** execution | ~5–8 d |
| Real cross-account IAM via `sts:AssumeRole` | ~4–5 d |
| Stricter PIR extraction (dict aliases, `.get()`, cross-function) | ~5–7 d |
| Multi-package chaining scenarios | ~3–5 d |
| KMS key-rotation automation (runbook exists) | ~3–4 d |
| Multi-region KMS replica | ~3–4 d |
| SCH002 / SCH003 deferred checks | ~2–3 d |
| Realtime ASL template (only if a realtime model is in scope) | ~5–8 d |

### Bucket B — blocked on ABSA (can't complete until inputs land)
Real account onboarding · real SAS validation (SAS runtime) · PIR system
integration · CAB/IVU integration · first real Track A scoring run · cross-account
verifier against real AWS. See §6.

### Bucket C — Jenkins migration (ADR-0011, ~10–15 DevOps-days)
M1 scaffold **done**; M2 (AWS-touching ports + `identity_provider` Terraform)
and M3 (cutover, GHA retirement) pending; partly gated on the AWS identity
decision.

> **Key framing:** Buckets A, B and C are not separate from the delivery plan —
> they *are* its early epics (§7). The genuinely *new, unplanned* code is small:
> the realtime template and SCH002/003 (~5 days total).

---

## 6. Dependencies on ABSA

Every top programme risk is an ABSA dependency. These are tracked live in the
**RAID Log** sheet of [docs/absa-exl-agile-plan.xlsx](docs/absa-exl-agile-plan.xlsx);
the Tech Lead sends the consolidated ask-list in Sprint 1 and chases weekly.

| # | Dependency | First needed |
|---|---|---|
| 1 | AWS account IDs (3 EXL + ABSA receiving) | Sprint 2 |
| 2 | IAM principal ARNs (`kms:Verify` / `s3:GetObject`) | Sprint 4 |
| 3 | SAS runtime Docker image + license | Sprint 2–3 |
| 4 | PIR system API / feed contract | Sprint 5 |
| 5 | Data-movement decision (S3 replication vs SFTP) | Sprint 4 |
| 6 | CAB / IVU API contract | Sprint 5 |
| 7 | Network connectivity choice (peering / TGW / PrivateLink) | Sprint 3 |
| 8 | Approved model docs + code + benchmarks (models 1–2 first) | Sprint 2 |

**Sprint 1 is fully unblocked** by design — the team is productive from day one
regardless of ABSA's timing.

---

## 7. Delivery plan — 12 sprints

Two-week sprints, **start Mon 2026-06-15**, ~6 months. Full backlog (13 epics /
52 stories / ~248 tasks, capacity-validated) in
**[docs/absa-exl-agile-plan.xlsx](docs/absa-exl-agile-plan.xlsx)**; a
client-facing walkthrough in
[docs/absa-exl-program-walkthrough.pptx](docs/absa-exl-program-walkthrough.pptx).

| Milestone | Sprint | Target |
|---|---|---|
| Jenkins cutover complete (GHA retired) | S3 | ~Jul 24 |
| Registry live on Lambda (dev) | S4 | ~Aug 7 |
| Dress rehearsal — full chain on real AWS, models 1–2 | S6 | ~Sep 4 |
| ⭐ **GROUP 1 ABSA SIGN-OFF** (the programme gate) | S8 | ~Oct 2 |
| All 10 models live (Group 2 onboarding complete) | S11 | ~Nov 13 |
| Group 2 sign-off + handover + steady-state go-live | S12 | ~Nov 27 |

The plan is **audited for feasibility** (dependency ordering, capacity,
unblocked S1, model coverage) by `scripts/audit_agile_plan.py` — it passes.
Group 2's 8 models are compressed into S9–S11 so S12 is hardening + sign-off,
not a race to finish.

---

## 8. Team & roles

**8 people.** Per-role kickoff briefs (mission, Sprint 1 tasks, full-program
load, ABSA blockers, reading list) are in
**[docs/onboarding/](docs/onboarding/README.md)**, generated from the backlog so
they never drift.

| Seat | Role | Brief |
|---|---|---|
| AWS, AWS2 | AWS/MLOps — Foundation/Infra + Platform/Compute/MLOps | [aws-mlops](docs/onboarding/role-brief-aws-mlops.md) |
| SAS, SAS2, SAS3 | SAS Developers (2 from S1, 1 from S8) | [sas](docs/onboarding/role-brief-sas.md) |
| DE | Data Engineer | [data-engineer](docs/onboarding/role-brief-data-engineer.md) |
| DevOps | DevOps Engineer | [devops](docs/onboarding/role-brief-devops.md) |
| TL | Tech Lead (Vishnu) | [tech-lead](docs/onboarding/role-brief-tech-lead.md) |

**Onboarding a new joiner?** The per-role skillsets (Core / Ramp-up / Bonus)
needed to contribute are in
**[docs/onboarding/skills-matrix.md](docs/onboarding/skills-matrix.md)**.

---

## 9. Open decisions

Tracked as D01–D09 (RAID Log + the program-plan workbook). The ones that gate
build work:

- **D04 — ML compute platform:** Step Functions + Lambda vs SageMaker
  Pipelines/Processing (gates the Track B build).
- **D01 — Data-drift framework:** which metrics (PSI / KL), window, alerting.
- **D02 — Change-management workflow:** CAB/IVU vs the registry approval state machine.
- **D08 / D09 — Dashboard tool + output-delivery format.**
- Plus the **Jenkins identity model** (IRSA-on-EKS / instance profile / OIDC) —
  see [ADR-0011](docs/adr/0011-ci-platform-jenkins.md).

---

## 10. Compliance

POPIA · SARB GOI 3/5 · SR 11-7 · ISO 27001 · SOC 2 Type II · ABSA GMRMG.
Control matrix (per-phase, with evidence pointers):
**[docs/compliance/control-matrix.md](docs/compliance/control-matrix.md)**.

---

## 11. Getting started

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

---

## 12. Full documentation index

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
- [docs/absa-exl-agile-plan.xlsx](docs/absa-exl-agile-plan.xlsx) — the backlog + Sprint Plan + Role Load + RAID + Per-Model Tracker
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

## Repository layout

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
