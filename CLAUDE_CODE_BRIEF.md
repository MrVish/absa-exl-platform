# ABSA × EXL — Model Hosting & Delivery Operations
## Implementation Brief for Claude Code

You are scaffolding the technical implementation of the ABSA × EXL Model Hosting & Delivery Operations platform. Read this brief end-to-end before writing any code. Plan in phases. Ask before making decisions that lock in expensive choices.

---

## 1. Goal

Build a production-grade, audit-ready ML hosting platform on AWS that lets ABSA Group productionise developer-authored SAS / Python models, score them on cadence, and reconcile every run against developer evidence — without raw PII ever leaving the ABSA trust boundary.

10 models in the initial cohort. 5-month build. 10-FTE delivery pod (8 offshore + 2 onsite at ABSA).

---

## 2. Operating model — two tracks

The platform supports two distinct flows. Build them as separate but registry-linked pipelines.

### Track A — Model Onboarding & Pipeline Factory (one-time per model)
1. Developer authors SAS + inference code in ABSA
2. Model Industrialization Team (EXL onsite at ABSA) standardises and packages the code — no core-logic changes, only structure / I/O contract / naming
3. Productized package handed off via Controlled Handoff (signed, manifested)
4. Code intake pipeline in EXL validates: static scans, schema, tests, PIR mapping
5. **Pipeline Factory** generates a scoring pipeline from a template — schedule, DQ rules, PIR hooks, I/O paths, monitoring config
6. Model & Pipeline Registry records: model version, SAS code version, inference code version, schedule, expected schemas, PIR doc reference, owner, SLA, scoring volume tier, approval status

### Track B — Scheduled Scoring Execution (recurring)
1. ABSA SAS scheduler triggers on registered cadence (daily / weekly / monthly)
2. ABSA writes model-ready data to ABSA-owned S3 bucket
3. **S3 cross-account replication** pushes the object to the EXL landing bucket (see §4)
4. EventBridge fires on object arrival → DQ pipeline (Great Expectations)
5. Validated data lands in the per-model data zone
6. Scoring trigger fires, registry lookup picks the right pipeline
7. Scoring engine runs (tiered — see §5)
8. Score output written, snapshot + lineage tag captured
9. PIR Engine compares scores vs developer evidence; variance gate
10. Secure delivery back to ABSA via SFTP, API Gateway, or SNS

---

## 3. Repo layout — scaffold this first

```
absa-exl-platform/
├── README.md
├── docs/
│   ├── architecture.md
│   ├── runbooks/
│   └── adr/                    # Architecture Decision Records
├── terraform/
│   ├── modules/
│   │   ├── landing-zone/
│   │   ├── kms-hierarchy/
│   │   ├── s3-replication/     # ★ critical — see §4
│   │   ├── iam-federation/
│   │   ├── sagemaker-domain/
│   │   ├── eks-scoring/
│   │   ├── pipeline-registry/  # DynamoDB + API
│   │   ├── pir-engine/
│   │   └── observability/
│   ├── envs/
│   │   ├── dev/
│   │   ├── stg/
│   │   └── prod/
│   └── shared/
├── pipeline-factory/
│   ├── templates/              # Jinja2 pipeline templates per model class
│   ├── config-schema/          # JSON Schema for model config
│   ├── generator/              # Python CLI: generate_pipeline.py
│   └── tests/
├── code-intake/
│   ├── github-actions/         # workflows for SAS / Python validation
│   ├── validators/
│   └── manifest-signer/
├── pir-engine/
│   ├── reconciliation/
│   ├── variance-rules/
│   └── reports/
├── scoring-engine/
│   ├── tiers/                  # standard-batch + scalable-batch
│   ├── orchestrator/           # Step Functions / Airflow DAGs
│   └── delivery/               # SFTP, API GW, SNS adapters
├── registry/
│   ├── api/                    # REST API in front of DynamoDB
│   └── schema/
└── ci/
    ├── pipelines/
    └── policies/               # OPA / Sentinel
```

Start with `docs/architecture.md`, then `terraform/modules/landing-zone/`, then `terraform/modules/s3-replication/`. Don't write the scoring engine before the foundation lands.

---

## 4. ★ Data movement — use S3 replication, NOT PrivateLink ★

This is the most important architectural correction in this brief. Earlier drafts of the proposal showed bulk data crossing the boundary via PrivateLink. **That will not work** in ABSA's environment. Use S3 cross-account replication instead.

### The pattern

- ABSA owns a bucket: `s3://absa-model-handoff-<env>` (in ABSA's AWS account)
- EXL owns a landing bucket: `s3://exl-model-landing-<env>` (in EXL's AWS account)
- Replication rule on the ABSA bucket replicates new objects to the EXL bucket
- Cross-account replication role on the EXL side accepts replicated objects
- Both buckets: KMS-encrypted (separate keys per side, both keys grant the replication role kms:Decrypt / kms:Encrypt as needed), versioning enabled, object-lock in compliance mode

### Required Terraform module: `terraform/modules/s3-replication/`

Inputs:
- `source_bucket_name` (in ABSA account)
- `destination_bucket_name` (in EXL account)
- `source_kms_key_arn`
- `destination_kms_key_arn`
- `replication_role_arn`
- `replication_time_control_enabled` (default true — gives 15-min SLA)
- `delete_marker_replication` (default false)
- `prefix_filter` (e.g. `"model-ready/"`)

Outputs:
- `replication_metric_alarm_arn` (for SLA breaches)
- `replication_lag_metric` (CloudWatch metric)

### Triggering downstream work

When a replicated object lands in `exl-model-landing-<env>`:
1. S3 emits `s3:ObjectCreated:Replication`
2. EventBridge rule routes by prefix → invokes the right Step Functions state machine
3. State machine: DQ → load to model data zone → scoring trigger → output → PIR

Do NOT poll. Do NOT use Lambda directly off S3 events for orchestration — keep Lambda thin (parse event, hand off to Step Functions).

### Where PrivateLink IS still used

- API calls between ABSA apps and EXL services (scoring API, registry API, status endpoints)
- Score delivery from EXL → ABSA (API Gateway behind PrivateLink, or signed-URL SFTP)
- NOT for bulk data movement either way

Document this distinction in `docs/adr/0001-data-movement-s3-replication.md`.

---

## 5. Execution tiering

Two execution patterns based on model class. Tier is stored per-model in the registry.

| Tier | Model class | Frequency | Volume | Pattern |
|---|---|---|---|---|
| Standard batch | Application models | Daily | ~20k rows | SageMaker Batch Transform |
| Scalable batch | Scoring models | Weekly / Monthly | 2M – 6M rows | EKS + Spark / SageMaker with multi-instance |

Pipeline Factory should select the right tier from a single config field (`execution_tier: standard | scalable`). Don't hand-roll per model.

---

## 6. Pipeline Factory — what to build

Inputs:
- `model_config.yaml` per model: name, version, tier, schedule, input schema, output schema, PIR doc ref, owner, SLA, registry lookup key

Outputs:
- A complete, deployable scoring pipeline (Step Functions definition + Terraform module instance + monitoring config)

Templates needed (in `pipeline-factory/templates/`):
- `standard-batch.j2` — for application models
- `scalable-batch.j2` — for scoring models
- `realtime.j2` — placeholder for future real-time inference (do not implement now)

Generator (`pipeline-factory/generator/`):
- CLI: `generate_pipeline.py --config model_config.yaml --out pipelines/<model_name>/`
- Validates config against JSON schema
- Renders Step Functions definition
- Writes Terraform stub that registers the pipeline in the registry
- Emits a manifest with content hashes for the Code Intake pipeline to sign

---

## 7. Model & Pipeline Registry

Backing store: DynamoDB table `model_pipeline_registry` with composite key `(model_name, version)`.

Required attributes:
- `model_name`, `version`, `sas_code_version`, `inference_code_version`
- `schedule_cadence` (cron)
- `execution_tier`
- `input_schema_ref`, `output_schema_ref` (S3 URI)
- `pir_doc_ref` (S3 URI)
- `owner_email`, `accountable_executive`
- `approval_status` (pending | approved | retired)
- `sla_seconds`
- `cab_record_id`
- `created_at`, `updated_at`, `last_scored_at`

Front the table with a small REST API (FastAPI on Lambda + API Gateway). All writes require IAM auth + audit logging to CloudTrail.

---

## 8. PIR Engine

Compare the scoring run output to the developer's reference output (a snapshot supplied during onboarding).

Variance gate logic:
- Per-column statistical comparison (KS test, PSI for distributions, exact-match thresholds for categoricals)
- Configurable per-model thresholds
- On breach: block delivery, alert ABSA + EXL ops, write incident record

Reports:
- Per-run variance report (HTML + JSON, written to `s3://exl-pir-reports/`)
- Daily roll-up to ABSA Risk

---

## 9. Constraints (do not violate)

- Raw PII never leaves the ABSA AWS account
- Only model-ready data (already curated, no raw identifiers) crosses to EXL via S3 replication
- All cross-account access is logged in CloudTrail in both accounts
- Model deployments require CAB approval recorded in the registry before the registry's `approval_status` flips to `approved`
- IVU evidence pack must be attached to the registry record before first production run
- Industrialization Team operates onsite at ABSA — design for restricted developer access patterns from inside the ABSA network
- 5-month build; do not propose anything that requires more than 5 months of foundation work before first model can score

---

## 10. Compliance mappings (for the audit pack)

Every component you write must be traceable to:
- POPIA — data sovereignty + processing controls
- SARB GOI 3/5 — model risk management
- SR 11-7 — model development, implementation, use
- ISO 27001 — security management
- SOC 2 Type II — operational controls
- ABSA GMRMG — group model risk management guidance

Maintain `docs/compliance/control-matrix.md` mapping each Terraform module / service / process to the relevant control.

---

## 11. Phase plan (5 months)

### Phase 1 — Foundation (Month 1)
Landing zone · KMS hierarchy · IAM federation · S3 replication module · CI/CD scaffolding · repo structure · ADR-0001 (S3 replication decision)

### Phase 2 — Pipeline Factory + Registry (Months 2-3)
Pipeline Factory templates + generator · Registry API · Code Intake validation · sign-and-handoff flow · first end-to-end Track A run for one test model

### Phase 3 — Scoring Engine (Months 3-4)
Standard-batch tier · scalable-batch tier · EventBridge orchestration · output writer · delivery adapters · first end-to-end Track B run

### Phase 4 — PIR + Hardening (Month 4-5)
PIR Engine · variance gates · DR runbooks · SR 11-7 evidence pack · audit hub · documentation · KT to ABSA

Cohort plan within Phases 2-4:
- Cohort 1: 1 initial model (Month 2)
- Cohort 2: 1 new-type + 2 subsequent models (Month 3-4)
- Cohort 3: 1 new-type + 5 subsequent models (Month 4-5)

---

## 12. How to start

Today's task list:

1. Read this brief end-to-end. Ask clarifying questions on §4 (S3 replication) and §6 (Pipeline Factory) before writing code.
2. Create the repo scaffold from §3.
3. Write `docs/architecture.md` summarising the two-track model + S3 replication choice.
4. Write `docs/adr/0001-data-movement-s3-replication.md` capturing why S3 replication beats PrivateLink for our constraints.
5. Build `terraform/modules/s3-replication/` end-to-end with tests.
6. Build `terraform/modules/landing-zone/` (multi-account org structure, transit gateway, VPCs).
7. Stop and review with the engagement lead before starting Pipeline Factory.

---

## 13. Reference materials

In the same folder as this brief:
- `ABSA_EXL_Model_Hosting_Proposal_v3.0.pptx` — the proposal deck (slide 7 = two-track overview, slide 10 = technical reference architecture)
- `ABSA_EXL_Investment_Model_v5.xlsx` — the cost model and service catalog

Read both before starting.
