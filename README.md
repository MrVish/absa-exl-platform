# ABSA × EXL Model Hosting & Delivery Operations

Production-grade, audit-ready ML hosting platform delivered by EXL for ABSA Group's model industrialisation programme. The platform productionises developer-authored SAS / Python models, scores them on cadence, and reconciles every run against developer evidence — without raw PII ever leaving the ABSA trust boundary.

## Operating model — two tracks

1. **Track A — Model Onboarding & Pipeline Factory.** Developer-authored model is industrialised by the EXL onsite team, packaged with a signed manifest, intaked by validation pipelines, and registered. A pipeline is generated from a template based on the registered model's class.
2. **Track B — Scheduled Scoring Execution.** ABSA's SAS scheduler triggers data hand-off via S3 cross-account replication. EXL's scoring engine validates, scores, reconciles against the developer's reference output (PIR), and delivers results back to ABSA.

See [`docs/architecture.md`](docs/architecture.md) for the full architecture and [`CLAUDE_CODE_BRIEF.md`](CLAUDE_CODE_BRIEF.md) for the engagement brief.

## Phase plan (5 months)

| Phase | Months | Scope |
| --- | --- | --- |
| 1 — Foundation | 1 | Landing zone, KMS hierarchy, IAM federation, S3 replication, CI/CD scaffolding |
| 2 — Pipeline Factory + Registry | 2-3 | Templates, generator CLI, code intake, registry API, signed handoff |
| 3 — Scoring Engine | 3-4 | Standard + scalable batch tiers, EventBridge orchestration, delivery adapters |
| 4 — PIR + Hardening | 4-5 | Variance gates, DR runbooks, SR 11-7 evidence pack, audit hub |

## Repository layout

```
docs/                        Architecture, ADRs, runbooks, compliance matrix
terraform/                   Infrastructure as code
├── modules/                 Reusable modules (landing-zone, s3-replication-*, etc.)
├── envs/{dev,stg,prod}/     Per-env stacks calling the modules
├── account-bootstrap/       Account-singleton resources (CloudTrail, GuardDuty)
└── shared/                  Cross-stack contracts and shared variables
platform-contracts/          Shared JSON-Schema contracts + generated Pydantic models (Phase 2)
pipeline-factory/            Pipeline generator: validate / generate / register CLI (Phase 2)
pipelines/                   Per-version generated pipeline artifacts (Phase 2)
code-intake/                 Validators and signing for the productized handoff (Phase 2)
pir-engine/                  Post-implementation review reconciliation (Phase 4)
scoring-engine/              Step Functions / Spark scorers (Phase 3)
registry/                    Model & Pipeline Registry API (Phase 2)
ci/                          GitHub Actions workflows and policy bundles
```

## Compliance mappings

POPIA · SARB GOI 3/5 · SR 11-7 · ISO 27001 · SOC 2 Type II · ABSA GMRMG.
Control matrix: [`docs/compliance/control-matrix.md`](docs/compliance/control-matrix.md).

## Status

Phase 1 foundation complete. Phase 2 Sprint 1 (Registry & shared contracts) complete. **Phase 2 Sprint 2 (Pipeline Factory) in progress.** See [`docs/superpowers/plans/2026-05-26-absa-exl-phase-2-sprint-2-pipeline-factory.md`](docs/superpowers/plans/2026-05-26-absa-exl-phase-2-sprint-2-pipeline-factory.md).
