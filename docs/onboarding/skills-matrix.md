# Skills Matrix — what each role needs to contribute

A hiring + ramp-up reference for the ABSA × EXL Model Hosting platform. Skills
are grounded in **this** codebase, not a generic syllabus — each is tied to the
component the role actually works in.

Tiers:
- **Core** — needed to contribute meaningfully from week 1.
- **Ramp-up** — build in the first month on the project.
- **Bonus** — depth that makes the role stronger / unblocks stretch work.

> If the team shape changes (roles added/split), update this doc — it is
> hand-authored, not generated from the plan.

---

## Shared baseline — every engineer, regardless of role

| Skill | Why it matters here |
|---|---|
| Git + PR-based flow | Branch protection + CODEOWNERS review; CI must be green before merge |
| Python 3.12 + `uv` (`sync`, `run`, workspace) | The repo is a uv monorepo; even SAS devs touch each package's `python/` side |
| Contract-first thinking + JSON Schema (Draft 2020-12) | Every artifact is schema-validated; canonical JSON is what makes signatures deterministic |
| Chain-of-custody mental model | sign → manifest → verify; digests anchor package → pipeline → registry. The soul of the platform |
| Docker basics | Run `make demo` (the LocalStack producer→verifier chain) locally on day 1 |
| pytest / ruff / mypy --strict | The quality gates every change passes |

**Fastest ramp for anyone:** clone → `make demo` green locally → read the ADR
index in `docs/adr/` → trace one model through
`packages/credit-risk-pd/1.0.0/` → `code-intake validate` → `pipeline-factory`
→ `manifest-signer` → verifier. That single trace touches ~80% of the concepts
any role needs.

---

## AWS / MLOps #1 — Foundation & Infra

*Owns accounts, networking, replication, retention. Works in `terraform/`
(landing-zone, account-bootstrap, s3-replication).*

| Tier | Skill | Why it matters here |
|---|---|---|
| Core | IAM in depth — roles, **cross-account trust policies**, `sts:AssumeRole`, permission boundaries, policy conditions | The whole platform is multi-account; trust is the backbone |
| Core | **Terraform** — modules, per-env stacks, remote state (S3 + DynamoDB lock), `init/plan/apply`, `fmt/validate` | All infra is IaC; you apply the existing modules to real accounts |
| Core | **S3 advanced** — cross-account replication + RTC, object-lock (compliance mode), lifecycle/retention, SSE-KMS, bucket policies | The data-movement + retention controls (ADR-0001) |
| Core | AWS multi-account topology (Organizations) | ADR-0004: 1 ABSA + 3 EXL accounts |
| Ramp-up | VPC networking + connectivity choice (**peering / Transit Gateway / PrivateLink**), IP whitelisting, Route 53 | The cross-account data plane to ABSA |
| Ramp-up | CloudTrail / GuardDuty / Security Hub / CIS-benchmark alarms | account-bootstrap security baseline |
| Ramp-up | tflint / tfsec / checkov | The terraform-validate gate |
| Bonus | Hybrid / on-prem connectivity patterns | Real ABSA-side connectivity |
| Bonus | Cost management + right-sizing | The S11 cost-review task |

## AWS / MLOps #2 — Platform, Compute & MLOps

*Owns signing foundation, registry-on-Lambda, Step Functions, security. Works in
`manifest-signer/`, `registry/api/`, `pipeline-factory/renderer.py`.*

| Tier | Skill | Why it matters here |
|---|---|---|
| Core | **KMS asymmetric CMK** — RSA-3072, `SIGN_VERIFY`, `RSASSA_PKCS1_V1_5_SHA_256`, `kms:Sign/Verify/GetPublicKey`, key policies | This *is* the signing foundation (ADR-0003 / 0009) |
| Core | **Lambda** — packaging (container/zip), execution roles, API Gateway integration, env config | registry-api goes to Lambda+APIGW (the biggest demo→prod gap) |
| Core | **API Gateway + DynamoDB** + **SigV4** request signing | The registry data store + authenticated registration |
| Core | **Step Functions / ASL** — state types, retry/catch, EventBridge scheduling | The scoring compute layer + per-model cadence |
| Core | **FastAPI + boto3 + Pydantic v2** | The registry app + all AWS client code |
| Ramp-up | Cryptography fundamentals — digital signatures, SHA-256, PEM/DER, public-key verification | To reason about + extend the chain-of-custody |
| Ramp-up | The **D04 compute decision** — SFN+Lambda vs SageMaker Pipelines/Processing | You own the ADR and the build |
| Ramp-up | IAM least-privilege auditing + encryption-in-transit/at-rest validation | The S7 security-assurance tasks |
| Ramp-up | **moto / LocalStack** | Testing AWS code without real accounts |
| Bonus | SageMaker (if chosen), ECR/container builds | Compute platform alternative |
| Bonus | DR / backup-restore patterns | The S11 DR task |

## SAS Developers (×3)

*Own optimize → package → reconcile for 10 models. Work in
`packages/<model>/`, `code-intake/`.*

| Tier | Skill | Why it matters here |
|---|---|---|
| Core | **SAS programming** — DATA step, PROC SQL, macros, scoring-code structure + **performance optimization** | The central job: optimize 10 production models |
| Core | **Benchmark reconciliation** — tolerance bands, per-variable deltas, deterministic re-runs | The critical-quality activity that gates ABSA sign-off |
| Core | Reading model dev specs + benchmark outputs | You validate optimized code against ABSA's reference |
| Core | The **package contract** (ADR-0010) — layout, `model_config.yaml`, `pir.yaml`, `manifest.json` | Every model is packaged this way |
| Core | **`code-intake` CLI** — `validate`, `generate-manifest`, finding codes (PY/SAS/SCH/TST/PIR) | The intake gate each package must pass |
| Core | Python basics — the `python/score.py` + pytest side of each package | Every package ships a Python test suite |
| Ramp-up | SAS↔Python interop; how SAS scoring maps onto the platform | The hosting model |
| Ramp-up | PIR (Production Input Register) concept | Input-column lineage + sign-off evidence |
| Ramp-up | Credit-risk / PD domain literacy | The initial model cohort |
| Ramp-up | Git/PR flow + ruff/mypy on the Python side | Quality gates |
| Bonus | Containerized SAS runtime / SAS Viya | Real linting once ABSA provides the runtime |
| Bonus | Model-risk / validation concepts (SR 11-7) | Regulatory context for reconciliation + PIR |

## Data Engineer

*Owns contracts, ingestion validation, DQ, lineage, PIR integration. Works in
`platform-contracts/` and the data-plane Terraform.*

| Tier | Skill | Why it matters here |
|---|---|---|
| Core | **Data contract / schema design** — JSON Schema, data dictionaries, types/nullability | Per-model input contracts |
| Core | **Data quality** — volume bands, **distribution drift (PSI)**, schema-on-arrival validation | The DQ framework that catches bad runs before scoring |
| Core | **S3 data layout** — partitioning, bucket conventions, ingestion patterns | Scoring-input landing + organization |
| Core | Python data stack — pandas / pyarrow, boto3, the platform-contracts schemas | DQ jobs + contract tooling |
| Core | **Lineage** + source-vs-landing reconciliation | Run traceability + sign-off evidence |
| Ramp-up | **PIR mapping** (`pir.yaml`) + integration with ABSA's PIR system | The mapping authority for inputs |
| Ramp-up | Retention / archival (S3 lifecycle), backfill patterns | Steady-state data ops |
| Ramp-up | SQL + columnar formats (parquet) | Data handling |
| Bonus | Glue / Athena (if adopted), great-expectations-style DQ frameworks | Scale-out tooling |

## DevOps Engineer

*Owns the entire Jenkins migration, then observability + runbooks. Works in
`ci/jenkins/`, `.github/workflows/`.*

| Tier | Skill | Why it matters here |
|---|---|---|
| Core | **Jenkins deep** — shared libraries (Groovy `vars/`), multibranch, declarative Jenkinsfile, `publishChecks`/GitHub Branch Source, credentials, agents/executors | The entire CI migration is yours (ADR-0011) |
| Core | **Jenkins↔AWS auth** — IRSA-on-EKS / EC2 instance profile / OIDC-IdP | The identity decision that gates the signing trust policy |
| Core | **Docker** — agents, the localstack-demo job, containerized tools | Several jobs run in Docker |
| Core | GitHub Actions (what's being replaced) + branch-protection / required checks | The cutover source + the merge gate |
| Core | CI/CD concepts — drift gates, byte-stable artifacts, parallel matrices | The platform's CI invariants |
| Ramp-up | **Observability** — CloudWatch (logs/metrics/alarms/dashboards), SNS alerting, Grafana/QuickSight (D08) | The dashboards + alerting epic |
| Ramp-up | Terraform basics (read/run the AWS engineers' stacks) | You run what they author |
| Ramp-up | Incident response, runbooks, DR verification | Hypercare + steady state |
| Ramp-up | Performance / load testing | The SLA-validation tasks |
| Bonus | Secrets Manager-backed Jenkins credentials, EKS/K8s (if Jenkins-on-EKS), cost dashboards | Production-grade CI ops |

## Tech Lead

*Architecture-depth across all the above, plus the program spine. Listed for a
successor / 2-IC.*

| Tier | Skill | Why it matters here |
|---|---|---|
| Core | Everything above at architecture depth | Reviews + unblocks every stream |
| Core | Cryptographic chain-of-custody design | The platform's core guarantee |
| Core | ADR authorship + decision facilitation (the D01–D09 register) | You own the decisions |
| Core | Stakeholder + ABSA dependency management | Every top risk is an ABSA dependency |
| Ramp-up | The full codebase (registry, pipeline-factory, signer, code-intake, contracts) | Platform-code ownership via review |

---

## Cross-cutting — domain context that lifts everyone

This is a **banking / model-risk** program, so shared vocabulary in these areas
makes every role more effective (SAS devs + TL deepest):

- **POPIA** — South African data protection
- **SARB GOI** — Reserve Bank governance/outsourcing guidance
- **SR 11-7** — model risk management
- **CAB / IVU** — change advisory + independent validation governance
- **PIR** — Production Input Register
- **Audit-evidence / chain-of-custody** — why every artifact is signed + reproducible

---

## See also

- [Role briefs](README.md) — per-role mission, Sprint 1 tasks, full-program load
- [docs/program-flow.md](../program-flow.md) — the end-to-end techno-functional narrative
- [docs/adr/](../adr/) — the architecture decision records
- [docs/phase-3-closeout.md](../phase-3-closeout.md) — what's built vs deferred
