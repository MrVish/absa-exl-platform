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

## Phase 2 controls (sprint 3 — Signing Foundation, ADR-0009)

| Control | Implementation | Evidence artifact | Owner |
| --- | --- | --- | --- |
| **ISO 27001 A.10.1.1 — policy on the use of cryptographic controls** | Mandatory KMS-asymmetric signing of every manifest envelope (RSASSA_PKCS1_V1_5_SHA_256) with signer ARN + algorithm captured in the envelope | `docs/adr/0009-signing-foundation-topology.md`, `manifest-signer/src/manifest_signer/signer.py`, `manifest-signer/src/manifest_signer/verifier.py` | EXL Platform Engineering |
| **ISO 27001 A.10.1.2 — key management** | Per-tier KMS CMKs with rotation enabled; key topology + ARN allow-list documented in ADR-0009 | `docs/adr/0009-signing-foundation-topology.md`, `terraform/modules/manifest-signing/main.tf` | EXL Platform Engineering |
| **SOC 2 CC6.1 — logical access (signing keys)** | IAM-scoped `kms:Sign` permission restricted to the pipeline-factory + code-intake CI roles; cross-account verification uses `kms:Verify` only | `terraform/modules/manifest-signing/iam.tf`, `manifest-signer/src/manifest_signer/cli.py` | EXL Platform Engineering |
| **SOC 2 CC6.6 — encryption of evidence** | All committed manifests carry a non-`UNSIGNED` signature post-CI; verifier rejects sentinel-signature envelopes | `manifest-signer/src/manifest_signer/signer.py` (`UNSIGNED_SENTINEL`), `manifest-signer/tests/test_verifier_online.py` | EXL Platform Engineering |
| **SOC 2 CC6.8 — restricted access to crypto material** | Private keys never leave KMS; only the public key is published to `published-keys/` S3 prefix for offline verification | `manifest-signer/src/manifest_signer/cli.py` (`publish-key`), `docs/adr/0009-signing-foundation-topology.md` | EXL Platform Engineering |

## Phase 2 controls (sprint 4 — Productized Package Contract, ADR-0010)

| Control | Implementation | Evidence artifact | Owner |
| --- | --- | --- | --- |
| **ISO 27001 A.12.1.1 — documented operating procedures** | Five-checker pipeline (static_python, static_sas, schema, tests, pir) runs on every package; finding codes (PY00x, SAS00x, SCH00x, TST00x, PIR00x) documented in code-intake/README.md | `code-intake/README.md`, `code-intake/src/code_intake/checkers/`, `docs/adr/0010-productized-package-contract.md` | EXL Platform Engineering |
| **ISO 27001 A.12.1.2 — change management** | `manifest.json` is generated, not hand-edited; CI enforces byte-stability via `git diff --exit-code packages/`; every change must regenerate from upstream sources | `code-intake/src/code_intake/manifest.py`, `code-intake/README.md` ("Don't hand-edit manifest.json") | EXL Platform Engineering |
| **ISO 27001 A.14.2.2 — system change control procedures** | Package manifest digest covers all artifact bytes (SHA-256 per file); upstream-ref chain links package -> pipeline -> registry record so any post-approval change to source code invalidates the chain | `code-intake/src/code_intake/manifest.py` (`_file_ref`, `_build_layout`), `pipeline-factory/src/pipeline_factory/upstream_resolver.py` | EXL Platform Engineering |
| **SOC 2 CC7.1 — system operations (validation evidence)** | Validation summary records each checker's pass/fail + finding codes + ran_at into the signed envelope; CAB can re-execute the same checkers against the same fixture and reproduce results | `code-intake/src/code_intake/manifest.py` (`_build_validation_summary`), `code-intake/tests/test_e2e_track_a.py` | EXL Platform Engineering |
| **SOC 2 CC8.1 — change control framework** | Two deferred checks (SCH002 schema-version drift, SCH003 PIR referential integrity) marked `DEFERRED-CHECK:` in code with manifest-build-time enforcement per ADR-0010 | `code-intake/src/code_intake/manifest.py` (DEFERRED-CHECK markers), `code-intake/README.md` ("Deferred checks") | EXL Platform Engineering |

## Phase 3 controls (CI platform migration — Jenkins, ADR-0011)

> **Status:** Proposed. These rows describe the target state once
> [ADR-0011](../adr/0011-ci-platform-jenkins.md) is `Accepted` and the
> Sprint M3 cutover lands. Until then the ADR-0003 / ADR-0009 rows above
> remain authoritative for the live CI gates.

| Control | Implementation | Evidence artifact | Owner |
| --- | --- | --- | --- |
| **ISO 27001 A.9.4.1 — information access restriction (CI identity)** | Jenkins assumes the signer / registrar role via IRSA on EKS (recommended) — per-job ServiceAccount token; no static AWS credentials on agents | `terraform/modules/signing-foundation/` (`identity_provider = "jenkins_irsa"` variant), `ci/jenkins/vars/awsLogin.groovy` | EXL Platform Engineering |
| **ISO 27001 A.12.1.4 — separation of environments (CI)** | Per-environment Jenkins agent labels (`linux-docker-prod`, `linux-docker-stg`) + per-environment IAM trust-policy `:sub` claims keyed on K8s namespace + ServiceAccount | `ci/jenkins/examples/pipeline-factory.Jenkinsfile`, `docs/adr/0011-ci-platform-jenkins.md` §"Jenkins identity model" | EXL Platform Engineering |
| **SOC 2 CC8.1 — change control (branch protection)** | GitHub branch protection on `main` requires named Jenkins commit-status contexts (`ci/python-validate`, `ci/pipeline-factory/sign`, `ci/pipeline-factory/register`, `ci/localstack-demo`, `ci/code-intake`, `ci/terraform-validate`) before merge | GitHub repo settings → branches → main → required status checks; cross-referenced in `ci/jenkins/README.md` | EXL Platform Engineering |
| **SR 11-7 III.5 — independent verification (drift-gate commit-back)** | Jenkins drift-gate uses a GitHub App identity (preferred) or scoped bot PAT for the regenerated-manifest commit; identity is auditable per-action and revocable without rotating a human account | `ci/jenkins/examples/pipeline-factory.Jenkinsfile` (validate stage), `docs/adr/0011-ci-platform-jenkins.md` §"Drift-gate commit-back" | EXL Platform Engineering |

## Out-of-matrix items (deferred)

The following control rows belong to later phases and will be added to this matrix when the corresponding modules land:

- **POPIA s8 — quality of personal information**: Phase 2 (Code Intake validators).
- **SR 11-7 III.6 — independent review**: Phase 4 (PIR Engine variance gates).
- **SOC 2 CC7.2 — system monitoring**: Phase 4 (Observability module + dashboards).
- **ABSA GMRMG — IVU evidence pack**: Phase 4 (Audit hub + DR runbooks).
