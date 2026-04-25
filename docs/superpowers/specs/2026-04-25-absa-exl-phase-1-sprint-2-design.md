# ABSA × EXL Model Hosting & Delivery Operations — Phase 1 Sprint 2 Design

| Field | Value |
| --- | --- |
| Date | 2026-04-25 |
| Engagement | ABSA × EXL Model Hosting & Delivery Operations (5-month build, 10-FTE pod) |
| Phase | 1 — Foundation, sprint 2 (close-out) |
| Predecessor | Sprint 1 design at [`2026-04-25-absa-exl-phase-1-foundation-design.md`](2026-04-25-absa-exl-phase-1-foundation-design.md) |
| Branch | `phase-1/sprint-2` (off `phase-1/foundation-kickoff`) |
| Status | Design approved; awaiting written-spec review before implementation plan |

## TL;DR

Sprint 2 closes Phase 1 by adding the two remaining foundation modules (`kms-hierarchy` and `iam-federation`), refactoring account-singleton resources out of `landing-zone` into `account-bootstrap`, upgrading CloudTrail buckets from interim AES256 to SSE-KMS via the new key hierarchy, wiring CloudTrail to CloudWatch Logs with six CIS-Benchmark-aligned metric filters and alarms, structurally fixing the `s3-replication-destination` chicken-and-egg KMS principal problem, and correcting a VPC flow-logs IAM scoping bug. One new ADR (0005) captures the kms-hierarchy "audit-evidence keys only" architectural choice. ~7 task commits expected; CI matrix grows by two modules.

## 1. Context

Sprint 1 of Phase 1 (committed on the parent branch `phase-1/foundation-kickoff` and awaiting engagement-lead PR review) landed the repo scaffold, the architecture document and four ADRs, three Terraform modules (`landing-zone`, `s3-replication-source`, `s3-replication-destination`), six env stacks, three account-bootstrap stacks, and a GitHub Actions validate workflow. Several items were knowingly deferred to "Phase 1 sprint 2" with TODOs and known-gap notes in the relevant module READMEs. This sprint resolves all of them.

The deliverable shape mirrors sprint 1: per-task commits, plan-validate `terraform test` per module, no real `terraform apply` (Phase 1 has no AWS credentials yet), engagement-lead checkpoint at sprint end.

## 2. Decisions locked this brainstorm

Six clarifying questions were asked and answered. Most are tactical and live in code; one (Q2) warrants ADR-0005.

| # | Topic | Choice | Rationale | Captured by |
| - | --- | --- | --- | --- |
| 1 | Sprint scope | A — full Phase 1 close-out (all 7 deferred items) | Phase 1 is a one-month engagement-lead checkpoint; splitting it across two more sprints adds review overhead without value | This document, §3 |
| 2 | `kms-hierarchy` module shape | B — audit-evidence keys only (CloudTrail bucket key, flow-logs CW key, placeholder for Phase 2 manifest signing key) | Per-data-class keys belong in their owning modules; this module owns infra-baseline shared keys | ADR-0005 |
| 3 | `iam-federation` module scope | C — workload roles (engineer / operator / readonly / break-glass) plus GitHub Actions OIDC provider with strict `sub` condition | ABSA's central platform team owns Identity Center per ADR-0004; EXL's surface is bounded to in-account roles. OIDC must land before Phase 2's first apply | This document, §4 |
| 4 | Account-singleton refactor approach | A — clean break (remove from `landing-zone`, add to `account-bootstrap`) | No live state to migrate (Phase 1 plan-validate only); no external callers; simplest shape | This document, §3 |
| 5 | Destination KMS chicken-and-egg fix pattern | A — nullable `source_replication_role_arn`, conditional KMS / bucket policy statements via `concat()` of `local` lists | Minimal API surface, ergonomically clean, exactly matches the documented two-phase bootstrap | This document, §6 |
| 6 | CloudTrail → CW Logs scope | B — delivery + 6 CIS-Benchmark metric filters + alarms + `${env}-security-alerts` SNS topic | Standard bank security operations baseline, audit-pack friendly, ~$5/mo per account | This document, §5 |

## 3. Repo deltas

### New files

```
terraform/modules/kms-hierarchy/
├── versions.tf                                    # Terraform 1.9+, AWS 5.50+
├── variables.tf
├── main.tf                                        # locals + data sources
├── keys.tf                                        # 2 active CMKs + 1 commented Phase 2 placeholder
├── outputs.tf
├── README.md
└── tests/kms_hierarchy.tftest.hcl

terraform/modules/iam-federation/
├── versions.tf
├── variables.tf
├── main.tf                                        # locals + data sources
├── roles.tf                                       # 4 SAML-trust workload roles
├── oidc.tf                                        # GitHub OIDC provider + ci-deploy role
├── outputs.tf
├── README.md
└── tests/iam_federation.tftest.hcl

docs/adr/0005-kms-hierarchy-audit-evidence-only.md
docs/superpowers/specs/2026-04-25-absa-exl-phase-1-sprint-2-design.md   # this document
```

### Modified files

| Path | Change |
| --- | --- |
| `terraform/modules/landing-zone/iam.tf` | Delete `aws_iam_account_password_policy.this` |
| `terraform/modules/landing-zone/security.tf` | Delete `aws_securityhub_account.this`, `aws_securityhub_standards_subscription.foundational`, `aws_guardduty_detector.this`. Refactor `aws_iam_role_policy.flow_logs` policy to fix scoping (split into two statements) |
| `terraform/modules/landing-zone/variables.tf` | Drop `var.enable_guardduty`, `var.enable_security_hub` |
| `terraform/modules/landing-zone/outputs.tf` | Drop `guardduty_detector_id` |
| `terraform/modules/landing-zone/tests/landing_zone.tftest.hcl` | Drop `guardduty_detector_exists_when_enabled` and `security_hub_uses_foundational_standard` runs |
| `terraform/modules/landing-zone/README.md` | Delete the "Known gap — account-singleton resources" section |
| `terraform/modules/s3-replication-destination/variables.tf` | `source_replication_role_arn` becomes nullable, `default = null` |
| `terraform/modules/s3-replication-destination/kms.tf` | Refactor key policy via `concat()` of `local` lists with conditional source-role grant |
| `terraform/modules/s3-replication-destination/policy.tf` | Same conditional pattern for source-role bucket policy statement |
| `terraform/modules/s3-replication-destination/README.md` | Rewrite "Apply order" section |
| `terraform/modules/s3-replication-destination/tests/destination.tftest.hcl` | Add 2 runs for null and non-null source role paths |
| `terraform/account-bootstrap/exl-{dev,stg,prod}/main.tf` | Heaviest change — see §5 |
| `terraform/envs/{dev,stg,prod}/destination/main.tf` | Pass `source_replication_role_arn = null` until source side has applied; comment block explains |
| `.github/workflows/terraform-validate.yml` | Add `kms-hierarchy` and `iam-federation` to `validate-modules` matrix |

### Files NOT touched

- The 4 sprint-1 ADRs (0001-0004)
- `docs/architecture.md` — no structural change to the platform
- `terraform/modules/s3-replication-source/` — no changes
- `terraform/envs/*/source/` — no changes
- `terraform/shared/replication-contract.md` — apply-order narrative remains accurate; the destination module now actually supports it
- `docs/compliance/control-matrix.md` — sprint 2 doesn't introduce new control-row categories; the new metric-filter alarms cleanly fall under existing rows ("SR 11-7 III.4 — model implementation evidence" and "SOC 2 CC7.2 — system monitoring" once Phase 4 adds it)

## 4. Module contracts

### 4.1 `terraform/modules/kms-hierarchy/`

Inputs:
- `env` — `dev` / `stg` / `prod`, validated via `contains([...], var.env)`
- `tags` — `map(string)`, validated to include `cost_center`

Resources:
- `aws_kms_key.cloudtrail_bucket` — symmetric, rotation enabled, 30-day deletion window. Key policy: account root `kms:*`, plus `cloudtrail.amazonaws.com` granted `kms:GenerateDataKey` and `kms:Decrypt` with `aws:SourceArn` condition matching `arn:aws:cloudtrail:${region}:${account}:trail/exl-${env}-trail`.
- `aws_kms_alias.cloudtrail_bucket` — `alias/${var.env}-cloudtrail-bucket`.
- `aws_kms_key.flow_logs_cw` — symmetric, rotation enabled. Key policy: account root, plus `logs.${region}.amazonaws.com` granted `kms:Encrypt*`, `kms:Decrypt*`, `kms:ReEncrypt*`, `kms:GenerateDataKey*`, `kms:Describe*`, with `kms:EncryptionContext:aws:logs:arn` condition limiting use to log groups in this account.
- `aws_kms_alias.flow_logs_cw` — `alias/${var.env}-flow-logs-cw`.
- Phase 2 placeholder block, commented out, for `aws_kms_key.manifest_signing` — RSA-3072, `key_usage = "SIGN_VERIFY"`. Comment references ADR-0003.

Outputs:
- `cloudtrail_bucket_key_arn`, `cloudtrail_bucket_key_alias`
- `flow_logs_cw_key_arn`, `flow_logs_cw_key_alias`
- `manifest_signing_key_arn` — literal `null` in sprint 2; downstream consumers must guard for null

Tests (`tests/kms_hierarchy.tftest.hcl`, ~6 runs):
- Both keys have rotation enabled
- Aliases use `${var.env}-` prefix
- CloudTrail key policy grants the cloudtrail service principal
- Flow-logs key policy grants the CW Logs service principal in the configured region
- `env` validation rejects unknown value
- `manifest_signing_key_arn` is null

### 4.2 `terraform/modules/iam-federation/`

Inputs:
- `env`
- `absa_identity_center_saml_provider_arn` — string, opaque
- `permissions_boundary_arn` — string, output of `landing-zone`
- `github_org_slash_repo` — e.g. `"absa-group/absa-exl-platform"`
- `allowed_github_branches_for_apply` — list, default `["main"]`
- `tags`

Resources:
- `aws_iam_role.platform_engineer` — SAML federation trust to ABSA Identity Center, `permissions_boundary` attached, attached managed policy `arn:aws:iam::aws:policy/job-function/SystemAdministrator`. 8h session.
- `aws_iam_role.platform_operator` — SAML trust + permissions boundary, inline policy: read-everything plus narrow operational write (excluding IAM, KMS key deletion, CloudTrail modifications). 4h session.
- `aws_iam_role.platform_readonly` — SAML trust + permissions boundary, attached managed policy `arn:aws:iam::aws:policy/ReadOnlyAccess`. 8h session.
- `aws_iam_role.break_glass` — SAML trust with `aws:MultiFactorAuthPresent = true` condition, permissions boundary, attached managed policy `arn:aws:iam::aws:policy/AdministratorAccess`. 1h session. AssumeRole of this role triggers a CloudTrail metric-filter alarm in account-bootstrap.
- `aws_iam_openid_connect_provider.github` — `url = "https://token.actions.githubusercontent.com"`, `client_id_list = ["sts.amazonaws.com"]`, thumbprint exposed as a `local.github_oidc_thumbprint = "1c58a3a8518e8759bf075b76b750d4f2df264fcd"` for ease of update.
- `aws_iam_role.ci_deploy` — OIDC trust with `sub` condition built from `var.allowed_github_branches_for_apply`. For each branch, the condition emits `repo:${var.github_org_slash_repo}:ref:refs/heads/${branch}`. Permissions boundary attached. 1h session. Inline policy is two statements: an `Allow * on *` paired with an explicit `Deny` covering the actions a CI deploy role must never perform — `iam:CreateUser`, `iam:DeleteUser`, `iam:CreateAccessKey`, `iam:DeleteAccessKey`, `iam:UpdateLoginProfile`, `iam:CreateLoginProfile`, `iam:DeleteLoginProfile`, `iam:DeactivateMFADevice`, `iam:DeleteVirtualMFADevice`, `kms:ScheduleKeyDeletion`, `kms:DisableKey`, `kms:DisableKeyRotation`, `s3:DeleteBucket`, `cloudtrail:StopLogging`, `cloudtrail:DeleteTrail`. The Deny is evaluated against the role's permissions boundary which already restricts cross-env reach, so the combined effect is "ci-deploy can apply Terraform within this env, except for credential / key-destruction / audit-evasion actions."

Outputs:
- `platform_engineer_role_arn`, `platform_operator_role_arn`, `platform_readonly_role_arn`, `break_glass_role_arn`, `ci_deploy_role_arn`, `github_oidc_provider_arn`

Tests (~7 runs):
- Break-glass role's trust policy contains the MFA condition
- ci-deploy role's `sub` condition includes the configured branch
- ci-deploy role's allowed actions exclude `iam:*` and `kms:ScheduleKeyDeletion`
- OIDC provider has `client_id_list = ["sts.amazonaws.com"]`
- All five roles attach `var.permissions_boundary_arn`
- `env` validation rejects unknown value
- `allowed_github_branches_for_apply` accepts a list of N entries and produces N `sub` condition values

## 5. Account-bootstrap upgrades (sprint tasks 3-5)

The heaviest single file in sprint 2. `terraform/account-bootstrap/exl-{dev,stg,prod}/main.tf` grows from ~60 lines to ~150 lines per file. The same structural change is applied identically to all three (with env tokens substituted).

### 5.1 kms-hierarchy module call

At the top of `main.tf`, after the provider block:

```hcl
module "kms_hierarchy" {
  source = "../../modules/kms-hierarchy"

  env = "dev"  # or stg / prod

  tags = {
    cost_center = "ml-platform"
  }
}
```

### 5.2 CloudTrail bucket SSE upgrade

Replace the existing AES256 block:

```hcl
resource "aws_s3_bucket_server_side_encryption_configuration" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = module.kms_hierarchy.cloudtrail_bucket_key_arn
    }
    bucket_key_enabled = true
  }
}
```

Replace the sprint-1 `# TODO(Phase 1 sprint 2): switch to SSE-KMS...` comment with `# Phase 1 sprint 2: SSE-KMS via kms-hierarchy.cloudtrail_bucket_key_arn`.

### 5.3 Account-singleton resources (moved from landing-zone)

Add these blocks (with their dependencies on `data.aws_caller_identity.current` already present in account-bootstrap):

```hcl
resource "aws_iam_account_password_policy" "this" {
  minimum_password_length        = 14
  require_lowercase_characters   = true
  require_uppercase_characters   = true
  require_numbers                = true
  require_symbols                = true
  allow_users_to_change_password = true
  max_password_age               = 90
  password_reuse_prevention      = 24
  hard_expiry                    = false
}

resource "aws_guardduty_detector" "this" {
  enable                       = true
  finding_publishing_frequency = "FIFTEEN_MINUTES"

  tags = local.common_tags
}

resource "aws_securityhub_account" "this" {}

resource "aws_securityhub_standards_subscription" "foundational" {
  standards_arn = "arn:aws:securityhub:${var.region}::standards/aws-foundational-security-best-practices/v/1.0.0"
  depends_on    = [aws_securityhub_account.this]
}
```

### 5.4 CloudWatch Log group + delivery role + CloudTrail wiring

```hcl
resource "aws_cloudwatch_log_group" "cloudtrail" {
  name              = "/aws/cloudtrail/exl-${var.env}"
  retention_in_days = 365
  kms_key_id        = module.kms_hierarchy.flow_logs_cw_key_arn

  tags = local.common_tags
}

resource "aws_iam_role" "cloudtrail_to_cwlogs" {
  name = "exl-${var.env}-cloudtrail-to-cwlogs"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "cloudtrail.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "cloudtrail_to_cwlogs" {
  role = aws_iam_role.cloudtrail_to_cwlogs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogStream",
        "logs:PutLogEvents",
      ]
      Resource = "${aws_cloudwatch_log_group.cloudtrail.arn}:*"
    }]
  })
}
```

Then on the existing `aws_cloudtrail.this`, add:

```hcl
cloud_watch_logs_group_arn = "${aws_cloudwatch_log_group.cloudtrail.arn}:*"
cloud_watch_logs_role_arn  = aws_iam_role.cloudtrail_to_cwlogs.arn
```

### 5.5 SNS topic + 6 metric filters + 6 alarms

```hcl
resource "aws_sns_topic" "security_alerts" {
  name              = "${var.env}-security-alerts"
  kms_master_key_id = "alias/aws/sns"

  tags = local.common_tags
}
```

Six metric filters (CIS AWS Benchmark v3 detective control set), each on `aws_cloudwatch_log_group.cloudtrail`. Filter patterns reproduced in full so the spec is self-contained:

**1 — Root account usage** (`aws_cloudwatch_log_metric_filter.root_usage`, metric `RootUsage`):
```
{ $.userIdentity.type = "Root" && $.userIdentity.invokedBy NOT EXISTS && $.eventType != "AwsServiceEvent" }
```

**2 — IAM policy change** (`iam_policy_change`, metric `IAMPolicyChange`):
```
{ ($.eventName = DeleteGroupPolicy) || ($.eventName = DeleteRolePolicy) || ($.eventName = DeleteUserPolicy) || ($.eventName = PutGroupPolicy) || ($.eventName = PutRolePolicy) || ($.eventName = PutUserPolicy) || ($.eventName = CreatePolicy) || ($.eventName = DeletePolicy) || ($.eventName = AttachRolePolicy) || ($.eventName = DetachRolePolicy) || ($.eventName = AttachUserPolicy) || ($.eventName = DetachUserPolicy) || ($.eventName = AttachGroupPolicy) || ($.eventName = DetachGroupPolicy) }
```

**3 — KMS CMK change** (`kms_cmk_change`, metric `KMSCMKChange`):
```
{ ($.eventSource = kms.amazonaws.com) && (($.eventName = DisableKey) || ($.eventName = ScheduleKeyDeletion)) }
```

**4 — S3 bucket policy / config change** (`s3_policy_change`, metric `S3PolicyChange`):
```
{ ($.eventSource = s3.amazonaws.com) && (($.eventName = PutBucketAcl) || ($.eventName = PutBucketPolicy) || ($.eventName = PutBucketCors) || ($.eventName = PutBucketLifecycle) || ($.eventName = PutBucketReplication) || ($.eventName = DeleteBucketPolicy) || ($.eventName = DeleteBucketCors) || ($.eventName = DeleteBucketLifecycle) || ($.eventName = DeleteBucketReplication)) }
```

**5 — STS AssumeRole failure burst** (`sts_assume_role_fail`, metric `STSAssumeRoleFail`):
```
{ ($.eventSource = sts.amazonaws.com) && ($.errorCode EXISTS) }
```

**6 — CloudTrail config change** (`cloudtrail_change`, metric `CloudTrailChange`):
```
{ ($.eventSource = cloudtrail.amazonaws.com) && (($.eventName = StopLogging) || ($.eventName = DeleteTrail) || ($.eventName = UpdateTrail)) }
```

Alarm thresholds and periods:

| # | Threshold | Period | Evaluation | Datapoints to alarm |
| - | --- | --- | --- | --- |
| 1 RootUsage | ≥ 1 | 60s | 1 | 1 |
| 2 IAMPolicyChange | ≥ 1 | 60s | 1 | 1 |
| 3 KMSCMKChange | ≥ 1 | 60s | 1 | 1 |
| 4 S3PolicyChange | ≥ 1 | 60s | 1 | 1 |
| 5 STSAssumeRoleFail | ≥ 10 | 60s | 5 | 5 |
| 6 CloudTrailChange | ≥ 1 | 60s | 1 | 1 |

All six `aws_cloudwatch_metric_alarm` resources have `alarm_actions = [aws_sns_topic.security_alerts.arn]`, statistic `Sum`, `comparison_operator = "GreaterThanOrEqualToThreshold"`, `treat_missing_data = "notBreaching"`, and tags from `local.common_tags`.

### 5.6 iam-federation module call

At the bottom of `main.tf`:

```hcl
locals {
  # Deterministic ARN for the env-scoped permissions boundary policy created
  # by the landing-zone module in the destination stack. Avoids a
  # terraform_remote_state lookup across stacks.
  permissions_boundary_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/${var.env}-env-scoped-boundary"
}

module "iam_federation" {
  source = "../../modules/iam-federation"

  env                                    = "dev"  # or stg / prod
  # TODO: replace with the real ABSA Identity Center provider ARN before first apply
  absa_identity_center_saml_provider_arn = "arn:aws:iam::000000000000:saml-provider/AWSSSO_PLACEHOLDER_DO_NOT_DELETE"
  permissions_boundary_arn               = local.permissions_boundary_arn
  github_org_slash_repo                  = "absa-group/absa-exl-platform"
  allowed_github_branches_for_apply      = ["main"]

  tags = {
    cost_center = "ml-platform"
  }
}
```

Note on `permissions_boundary_arn`: The landing-zone module (called from `terraform/envs/{env}/destination/main.tf`) creates the policy `${env}-env-scoped-boundary` in the same AWS account. account-bootstrap constructs the ARN deterministically from the known pattern instead of a `terraform_remote_state` lookup — this avoids cross-stack coupling and keeps account-bootstrap independently appliable for `terraform validate`. The caller is responsible for ensuring the destination stack has applied first at real-apply time (Phase 2 sequence: destination stack provisions the policy → account-bootstrap re-applies and the iam-federation roles attach the boundary).

## 6. Destination KMS chicken-and-egg fix (sprint task 6)

The `s3-replication-destination` module's KMS key policy currently grants `kms:Encrypt` to `var.source_replication_role_arn`. AWS validates IAM principals in KMS key policies at PUT time, so the first apply (when the source role doesn't yet exist) fails with `MalformedPolicyDocumentException`. The fix is to make the variable nullable and conditionally include the source-role statement.

Changes:

- `variables.tf`: `var.source_replication_role_arn` becomes `type = string`, `default = null`, `nullable = true`. Description is updated to explain the two-phase bootstrap.
- `kms.tf`: introduces a `locals` block defining `account_root_grant` (always present) and `source_role_kms_grant` (a `var.source_replication_role_arn == null ? [] : [{...}]` conditional). The key policy statement list becomes `Statement = concat([local.account_root_grant], local.source_role_kms_grant)`.
- `policy.tf`: mirrors the same pattern for `AllowSourceReplicationRoleWrite` (the `AllowSourceAccountReadBucketVersioning` statement keys on `var.source_account_id`, which is always provided, so it remains unconditional).
- `tests/destination.tftest.hcl`: 2 new runs — `null_source_role_omits_kms_grant_in_policy` (sets the var to null, asserts the policy JSON does NOT contain `"AllowSourceReplicationRoleEncrypt"`) and `non_null_source_role_includes_kms_grant_in_policy` (sets the var to a fixture ARN, asserts the JSON DOES contain it).
- `README.md`: "Apply order" section is rewritten to describe the now-supported two-phase bootstrap (destination apply with null → source apply → destination re-apply with real ARN; no MalformedPolicyDocumentException).

Env-stack consumers (`terraform/envs/{env}/destination/main.tf`) pass `source_replication_role_arn = null` with a comment block explaining the two-phase bootstrap. Once the source side has applied, the operator updates the call to `module.replication_source.replication_role_arn` (or a `terraform_remote_state` lookup) and re-applies.

## 7. VPC flow-logs IAM scoping fix (sprint task 7)

Single-file change in `terraform/modules/landing-zone/security.tf`. Splits `aws_iam_role_policy.flow_logs` from one statement into two:

- `WriteFlowLogs` — `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`, `logs:DescribeLogStreams` scoped to `${aws_cloudwatch_log_group.flow_logs.arn}:*`
- `DescribeLogGroups` — `logs:DescribeLogGroups` only, scoped `Resource: *` (the action requires this)

Two bugs fixed: `logs:CreateLogGroup` was missing entirely; `logs:DescribeLogGroups` was incorrectly given a resource-level scope.

No test changes required (this is an internal IAM document; existing tests don't assert on it).

## 8. ADR-0005 outline

`docs/adr/0005-kms-hierarchy-audit-evidence-only.md`. MADR 3.0:

- **Status**: Accepted, 2026-04-25.
- **Context**: Two competing approaches for the kms-hierarchy module — own all platform CMKs centrally (audit-friendly but creates PR-back bottlenecks) versus own only audit-evidence keys (CloudTrail, flow-logs) shared across stacks while per-data-class keys live in their owning modules (s3-replication-source / s3-replication-destination).
- **Decision**: Audit-evidence keys only. Module owns `cloudtrail_bucket_key`, `flow_logs_cw_key`, plus a Phase 2 placeholder for the manifest-signing key. Per-data-class keys remain in their owning modules.
- **Consequences (positive)**: Clean separation of concerns; auditors can point to the single module that owns audit-evidence-grade encryption; teams owning per-data-class keys retain control of rotation / policy lifecycle without PR-back.
- **Consequences (negative)**: Two patterns for KMS in the codebase (centralised vs module-owned); convention drift risk if future modules don't follow the convention. Mitigation: code review enforces the split.
- **Alternatives considered**: A — full centralisation (rejected for centralisation-bottleneck reasons); C — single trunk key per account (rejected for SR 11-7 blast-radius reasons; auditors expect separation between trail logs and flow logs).

Length ~80-100 lines, parallel to ADRs 0001-0004.

## 9. Testing strategy

Unchanged from sprint 1.

- **Static layer** (pre-commit + CI): `terraform fmt -check -recursive`, `terraform init -backend=false && terraform validate`, `tflint --recursive`, `tfsec --minimum-severity MEDIUM`, `checkov --framework terraform`, `gitleaks`.
- **Module unit layer**: `terraform test` HCL-native plan-validate per module. Coverage rule unchanged.
- **Apply-time integration tests**: deferred to Phase 2.
- **CI matrix**: gains `kms-hierarchy` and `iam-federation` to `validate-modules`.

## 10. CI workflow change

Single-line change in `.github/workflows/terraform-validate.yml`:

```yaml
strategy:
  matrix:
    module:
      - landing-zone
      - s3-replication-source
      - s3-replication-destination
      - kms-hierarchy        # NEW
      - iam-federation       # NEW
```

The `validate-stacks` matrix is unchanged. tflint / tfsec / checkov / gitleaks jobs already cover all paths recursively.

## 11. Out-of-scope this sprint

| Item | Phase | Reason |
| --- | --- | --- |
| Phase 2 ADR — generator runtime dual-mode | 2 | Pipeline Factory not yet started |
| Synthetic data generator for ABSA dev/stg buckets | 2 | Dependency on Code Intake |
| Real `terraform apply` against AWS | 2 | No account credentials yet |
| LocalStack / ephemeral-account integration tests | 2 | Same |
| Pipeline Factory, Code Intake, Registry | 2 | Stub READMEs unchanged |
| Scoring engine, SageMaker domain, EKS scoring | 3 | Stub READMEs unchanged |
| PIR engine + Observability + DR runbooks | 4 | Stub READMEs unchanged |
| OpenTofu vs Terraform engagement-lead decision | unblocked | External question, doesn't block sprint 2 |
| `aws_securityhub_account` consolidated control findings | 4 | Phase 4 observability work |

## 12. Open items to flag with engagement lead

These items don't block sprint 2 implementation but warrant resolution before Phase 2 begins.

1. **ABSA Identity Center SAML provider ARN** — `iam-federation` uses a placeholder until the engagement lead provides the real one.
2. **GitHub org slug for the OIDC trust policy** — current placeholder is `absa-group/absa-exl-platform`; verify with the engagement lead.
3. **CloudWatch alarm period and evaluation count** — current spec uses CIS Benchmark defaults; security operations may want to tune these per env.
4. **SNS subscriber addresses for `${env}-security-alerts` topic** — mirrors the per-env-subscription stub pattern from sprint 1 (subscriptions live in env stacks).
5. **GitHub Actions OIDC root CA thumbprint** — exposed as a `local` in `iam-federation`'s `oidc.tf`. Engagement lead should confirm the current thumbprint at the time of first apply (GitHub rotates its CA periodically).

## 13. Sprint 2 today — deliverables manifest

Concrete artifacts produced before the sprint-2 follow-up PR opens:

- [ ] `phase-1/sprint-2` branch created off `phase-1/foundation-kickoff`
- [ ] `terraform/modules/kms-hierarchy/` — full module + tests + README
- [ ] `terraform/modules/iam-federation/` — full module + tests + README
- [ ] `docs/adr/0005-kms-hierarchy-audit-evidence-only.md`
- [ ] `terraform/modules/landing-zone/` — singleton resources removed; flow-logs IAM scoping fix; README cleaned
- [ ] `terraform/modules/s3-replication-destination/` — chicken-and-egg fix (variables / kms.tf / policy.tf / README / tests)
- [ ] `terraform/account-bootstrap/exl-{dev,stg,prod}/main.tf` — kms-hierarchy module call, SSE-KMS upgrade, account singletons moved in, CloudWatch Logs integration, 6 metric filters + alarms, security-alerts SNS topic, iam-federation module call
- [ ] `terraform/envs/{dev,stg,prod}/destination/main.tf` — `source_replication_role_arn = null` with explanatory comment block
- [ ] `.github/workflows/terraform-validate.yml` — 2 new modules in validate-modules matrix
- [ ] `docs/superpowers/specs/2026-04-25-absa-exl-phase-1-sprint-2-design.md` — this document

Branch / commit strategy: 7 task commits (kms-hierarchy module, iam-federation module, account-singleton refactor, CloudTrail SSE-KMS upgrade, CloudTrail observability, destination KMS fix, flow-logs IAM fix) + final integration check / PR-body archive task. Estimated ~12 total commits with fix cycles, parallel to sprint 1's discipline.
