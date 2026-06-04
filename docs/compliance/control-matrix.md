# Compliance Control Matrix — Phase 1 Foundation

> **Scope:** Phase 1 controls only. Each phase extends this matrix with the rows it owns. Reviewed quarterly by the engagement lead and ABSA Compliance.

## Reading the matrix

| Column | Meaning |
| --- | --- |
| Control | The compliance requirement (POPIA section, SARB GOI clause, SR 11-7 sub-requirement, etc.) |
| Implementation | The Terraform module / repo file / process that satisfies it |
| Evidence artifact | What an auditor would inspect to confirm the control is in place |
| Owner | Who is accountable for the control's continued operation |

## Phase 1 controls

| Control | Implementation | Evidence artifact | Owner |
| --- | --- | --- | --- |
| **POPIA s19 — security safeguards** | KMS-encrypted S3 buckets on both sides of the replication boundary | `terraform/modules/s3-replication-source/kms.tf`, `terraform/modules/s3-replication-destination/kms.tf` | EXL Platform Engineering |
| **POPIA s14 — retention** | Object-lock compliance mode with per-env tiered retention (default 7 years prod) | `terraform/modules/s3-replication-source/main.tf` (object_lock_configuration block) | EXL Platform Engineering |
| **SARB GOI 5 — model documentation immutability** | Object-lock compliance mode prevents deletion / modification before retention expires | Same as above | EXL Platform Engineering |
| **SR 11-7 III.4 — model implementation evidence** | CloudTrail in both accounts logs every S3 object operation, KMS Sign / Decrypt call, and IAM AssumeRole | `terraform/account-bootstrap/exl-{env}/main.tf` (CloudTrail), assumed for ABSA side | EXL Platform Engineering, ABSA Cloud Platform |
| **ISO 27001 A.13.2.1 — information transfer** | S3 replication with RTC, KMS encryption, IAM least-privilege replication role | `terraform/modules/s3-replication-source/iam.tf`, `terraform/modules/s3-replication-source/replication.tf` | EXL Platform Engineering |
| **ISO 27001 A.12.4.1 — event logging** | VPC flow logs in landing-zone (KMS-encrypted via kms-hierarchy); GuardDuty + Security Hub + foundational standard in account-bootstrap; CloudTrail event stream to CW Logs in account-bootstrap | `terraform/modules/landing-zone/security.tf`, `terraform/account-bootstrap/exl-{env}/main.tf` | EXL Platform Engineering |
| **SOC 2 CC6.6 — privileged access** | Break-glass IAM role requires MFA via SAML assertion; assumption alarmed via CloudTrail metric filter | `terraform/modules/iam-federation/roles.tf`, `terraform/account-bootstrap/exl-{env}/main.tf` (sts_assume_role_fail filter, but break-glass-specific alerting is Phase 4) | EXL Platform Engineering |
| **SOC 2 CC7.2 — system monitoring** | 6 CIS Benchmark v3 metric filters + alarms on CloudTrail event stream (root usage, IAM policy change incl. PolicyVersion mutations, KMS CMK change, S3 policy change, STS AssumeRole burst, CloudTrail config change). All alarms route to per-env security_alerts SNS topic | `terraform/account-bootstrap/exl-{env}/main.tf` | EXL Platform Engineering |
| **SOC 2 CC6.1 — logical access** | IAM permissions boundaries on EXL workload roles enforce env-tag-based deny conditions | `terraform/modules/landing-zone/iam.tf` | EXL Platform Engineering |
| **ABSA GMRMG — model lifecycle traceability** | Per-env source buckets give per-env scoring-run lineage from the moment data leaves ABSA | `terraform/modules/s3-replication-source/main.tf` (called per env) | ABSA Model Risk |

## Phase 2 controls (sprint 1 — Registry)

| Control | Implementation | Evidence artifact | Owner |
| --- | --- | --- | --- |
| **SARB GOI 3 — model risk governance** | Registry approval gate: `approval_status` cannot reach `approved` without `cab_record_id` + `ivu_evidence_ref` | `registry/api/src/registry_api/transitions.py`, `docs/adr/0007-registry-data-model-and-api.md` | ABSA Model Risk |
| **SR 11-7 III.4 — model implementation evidence** | Structured audit log (principal / action / old->new / rev) per mutation + CloudTrail on API GW, Lambda, DynamoDB | `registry/api/src/registry_api/audit.py`, `terraform/modules/pipeline-registry/main.tf` | EXL Platform Engineering |
| **ISO 27001 A.10.1 — cryptographic controls** | Module-owned CMK (rotation enabled) for DynamoDB SSE + log groups | `terraform/modules/pipeline-registry/main.tf` (aws_kms_key.this) | EXL Platform Engineering |
| **ISO 27001 A.9 / SOC 2 CC6.1 — logical access** | API Gateway `AWS_IAM` (SigV4) auth; reader/writer caller policies scope `execute-api:Invoke` by HTTP method | `terraform/modules/pipeline-registry/main.tf` (route auth + reader/writer policies) | EXL Platform Engineering |
| **SOC 2 CC6.1 — recoverability of evidence** | DynamoDB PITR on the registry table | `terraform/modules/pipeline-registry/main.tf` (point_in_time_recovery) | EXL Platform Engineering |
| **ABSA GMRMG — model inventory + ownership** | Authoritative registry record with owner, accountable executive, SLA per model version | `platform-contracts/src/platform_contracts/schemas/registry-record.schema.json` | ABSA Model Risk |

## Phase 2 controls (sprint 2 — Pipeline Factory)

| Control | Implementation | Evidence artifact | Owner |
| --- | --- | --- | --- |
| **SR 11-7 III.1 — model documentation** | Per-version immutable artifact directories committed in git (model_config + state machine + registration + manifest + terraform) | `pipelines/<name>/<version>/`, `pipeline-factory/configs/<name>/<version>/model_config.yaml` | EXL Platform Engineering |
| **SR 11-7 III.4 — model implementation evidence** | API-routed registration preserves the audit log + approval gate from 2.1; CI is the only POST path (per ADR-0008) | `.github/workflows/pipeline-factory.yml` (`register` job), `pipeline-factory/src/pipeline_factory/registration.py` | EXL Platform Engineering |
| **SARB GOI 3 — model risk governance** | The generator can only create `pending` records; CAB + IVU still required to flip to `approved` (gate is server-side in the Registry API) | `registry/api/src/registry_api/transitions.py`, `pipeline-factory/src/pipeline_factory/registration.py` | ABSA Model Risk |
| **ISO 27001 A.14.2 — secure development** | Drift gate (CI re-render + `git diff --exit-code`) + golden-file tests ensure generated artifacts are reproducible bit-for-bit | `.github/workflows/pipeline-factory.yml`, `pipeline-factory/tests/test_golden_fixture.py` | EXL Platform Engineering |

## Out-of-matrix items (deferred)

The following control rows belong to later phases and will be added to this matrix when the corresponding modules land:

- **POPIA s8 — quality of personal information**: Phase 2 (Code Intake validators).
- **SR 11-7 III.6 — independent review**: Phase 4 (PIR Engine variance gates).
- **SOC 2 CC7.2 — system monitoring**: Phase 4 (Observability module + dashboards).
- **ABSA GMRMG — IVU evidence pack**: Phase 4 (Audit hub + DR runbooks).
