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
| **ISO 27001 A.13.2.1 — information transfer** | S3 replication with RTC, KMS encryption, IAM least-privilege replication role | `terraform/modules/s3-replication-source/iam.tf`, `replication.tf` | EXL Platform Engineering |
| **ISO 27001 A.12.4.1 — event logging** | VPC flow logs, GuardDuty, Security Hub enabled in every EXL account | `terraform/modules/landing-zone/security.tf` | EXL Platform Engineering |
| **SOC 2 CC6.1 — logical access** | IAM permissions boundaries on EXL workload roles enforce env-tag-based deny conditions | `terraform/modules/landing-zone/iam.tf` | EXL Platform Engineering |
| **ABSA GMRMG — model lifecycle traceability** | Per-env source buckets give per-env scoring-run lineage from the moment data leaves ABSA | `terraform/modules/s3-replication-source/main.tf` (called per env) | ABSA Model Risk |

## Out-of-matrix items (deferred)

The following control rows belong to later phases and will be added to this matrix when the corresponding modules land:

- **POPIA s8 — quality of personal information**: Phase 2 (Code Intake validators).
- **SARB GOI 3 — model risk governance**: Phase 2 (Registry approval gate + CAB record linkage).
- **SR 11-7 III.6 — independent review**: Phase 4 (PIR Engine variance gates).
- **SOC 2 CC7.2 — system monitoring**: Phase 4 (Observability module + dashboards).
- **ABSA GMRMG — IVU evidence pack**: Phase 4 (Audit hub + DR runbooks).
