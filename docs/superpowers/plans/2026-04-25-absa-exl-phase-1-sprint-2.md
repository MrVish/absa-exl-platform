# ABSA × EXL Phase 1 Sprint 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close out Phase 1 by adding the two remaining foundation modules (`kms-hierarchy`, `iam-federation`), refactoring account-singleton resources out of `landing-zone` into `account-bootstrap`, upgrading CloudTrail buckets to SSE-KMS, wiring CloudTrail to CloudWatch Logs with six CIS-Benchmark metric filters and alarms, structurally fixing the `s3-replication-destination` chicken-and-egg KMS principal problem, and correcting a VPC flow-logs IAM scoping bug.

**Architecture:** Sprint 2 builds on `phase-1/foundation-kickoff`. New `kms-hierarchy` module owns audit-evidence-grade CMKs (CloudTrail bucket key, flow-logs CW key) shared across stacks; per-data-class keys remain in their owning modules. New `iam-federation` module provisions 4 SAML workload roles + GitHub OIDC ci-deploy role with strict `sub` condition. Account-singleton resources move from per-env `landing-zone` to once-per-account `account-bootstrap`. Destination module's KMS / bucket policy statements become conditional on a nullable `source_replication_role_arn` to support the documented two-phase bootstrap. Spec at [`docs/superpowers/specs/2026-04-25-absa-exl-phase-1-sprint-2-design.md`](../specs/2026-04-25-absa-exl-phase-1-sprint-2-design.md) is authoritative if this plan disagrees.

**Tech Stack:** Same as sprint 1 — Terraform 1.9+, AWS provider 5.x, `terraform test` HCL-native test framework, GitHub Actions, tflint, tfsec, checkov, gitleaks, MADR 3.0 ADRs.

---

## File Structure

| Task | Files (substantive) |
| --- | --- |
| 1 | `terraform/modules/kms-hierarchy/{versions,variables,main,keys,outputs}.tf` + README + `tests/kms_hierarchy.tftest.hcl` |
| 2 | `terraform/modules/iam-federation/{versions,variables,main,roles,oidc,outputs}.tf` + README + `tests/iam_federation.tftest.hcl` |
| 3 | `docs/adr/0005-kms-hierarchy-audit-evidence-only.md` |
| 4 | Account-singleton refactor: delete from `terraform/modules/landing-zone/{iam,security}.tf` + `variables.tf` + `outputs.tf` + tests + README; add to `terraform/account-bootstrap/exl-{dev,stg,prod}/main.tf` |
| 5 | CloudTrail SSE-KMS upgrade + CloudWatch Logs + 6 metric filters + alarms + SNS topic + iam-federation call: heavy edits to `terraform/account-bootstrap/exl-{dev,stg,prod}/main.tf` |
| 6 | Destination KMS chicken-and-egg fix: `terraform/modules/s3-replication-destination/{variables,kms,policy}.tf` + tests + README; `terraform/envs/{dev,stg,prod}/destination/main.tf` |
| 7 | VPC flow-logs IAM scoping fix: `terraform/modules/landing-zone/security.tf` |
| 8 | CI matrix update: `.github/workflows/terraform-validate.yml`; final integration check + PR archive |

**Branch:** all work happens on `phase-1/sprint-2`. The branch is already created off `phase-1/foundation-kickoff`. Latest commit is `0f84ee5` (the design spec).

---

## Task 1: `terraform/modules/kms-hierarchy/` module + ADR-0005

**Files:**
- Create: `terraform/modules/kms-hierarchy/versions.tf`
- Create: `terraform/modules/kms-hierarchy/variables.tf`
- Create: `terraform/modules/kms-hierarchy/main.tf`
- Create: `terraform/modules/kms-hierarchy/keys.tf`
- Create: `terraform/modules/kms-hierarchy/outputs.tf`
- Create: `terraform/modules/kms-hierarchy/README.md`
- Create: `terraform/modules/kms-hierarchy/tests/kms_hierarchy.tftest.hcl`
- Create: `docs/adr/0005-kms-hierarchy-audit-evidence-only.md`

- [ ] **Step 1: Write the failing test first**

Save to `terraform/modules/kms-hierarchy/tests/kms_hierarchy.tftest.hcl`:

```hcl
variables {
  env = "dev"
  tags = {
    cost_center = "ml-platform"
  }
}

run "cloudtrail_bucket_key_rotation_enabled" {
  command = plan

  assert {
    condition     = aws_kms_key.cloudtrail_bucket.enable_key_rotation == true
    error_message = "CloudTrail bucket key must have rotation enabled"
  }
}

run "flow_logs_cw_key_rotation_enabled" {
  command = plan

  assert {
    condition     = aws_kms_key.flow_logs_cw.enable_key_rotation == true
    error_message = "Flow-logs CW key must have rotation enabled"
  }
}

run "cloudtrail_bucket_key_alias_uses_env_prefix" {
  command = plan

  assert {
    condition     = aws_kms_alias.cloudtrail_bucket.name == "alias/dev-cloudtrail-bucket"
    error_message = "CloudTrail bucket key alias must be alias/{env}-cloudtrail-bucket"
  }
}

run "flow_logs_cw_key_alias_uses_env_prefix" {
  command = plan

  assert {
    condition     = aws_kms_alias.flow_logs_cw.name == "alias/dev-flow-logs-cw"
    error_message = "Flow-logs CW key alias must be alias/{env}-flow-logs-cw"
  }
}

run "cloudtrail_key_grants_cloudtrail_service" {
  command = plan

  assert {
    condition = strcontains(
      aws_kms_key.cloudtrail_bucket.policy,
      "cloudtrail.amazonaws.com",
    )
    error_message = "CloudTrail bucket key policy must grant the cloudtrail.amazonaws.com service principal"
  }
}

run "flow_logs_key_grants_cwlogs_service" {
  command = plan

  assert {
    condition = strcontains(
      aws_kms_key.flow_logs_cw.policy,
      "logs.",
    )
    error_message = "Flow-logs CW key policy must grant the logs.{region}.amazonaws.com service principal"
  }
}

run "env_validation_rejects_unknown_value" {
  command = plan

  variables {
    env = "uat"
  }

  expect_failures = [
    var.env,
  ]
}
```

- [ ] **Step 2: Verify test fails (or skip if no terraform CLI)**

If `terraform` is on PATH:

```bash
cd terraform/modules/kms-hierarchy
terraform init -backend=false
terraform test
```

Expected: failure (no resources defined yet). If `terraform` is not on PATH, skip and rely on CI.

- [ ] **Step 3: Write `versions.tf`**

```hcl
terraform {
  required_version = ">= 1.9.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.50.0, < 6.0.0"
    }
  }
}
```

- [ ] **Step 4: Write `variables.tf`**

```hcl
variable "env" {
  description = "Deployment environment. Used in alias names and as a tag value."
  type        = string

  validation {
    condition     = contains(["dev", "stg", "prod"], var.env)
    error_message = "env must be one of dev, stg, prod."
  }
}

variable "tags" {
  description = "Tags applied to every CMK. Must include cost_center."
  type        = map(string)

  validation {
    condition     = contains(keys(var.tags), "cost_center")
    error_message = "tags must include cost_center."
  }
}
```

- [ ] **Step 5: Write `main.tf`**

```hcl
locals {
  common_tags = merge(var.tags, {
    env    = var.env
    module = "kms-hierarchy"
  })
}

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}
```

- [ ] **Step 6: Write `keys.tf`**

```hcl
resource "aws_kms_key" "cloudtrail_bucket" {
  description             = "Audit-evidence CMK for the ${var.env} CloudTrail S3 bucket. Rotation enabled."
  deletion_window_in_days = 30
  enable_key_rotation     = true
  key_usage               = "ENCRYPT_DECRYPT"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowAccountRoot"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" }
        Action    = "kms:*"
        Resource  = "*"
      },
      {
        Sid       = "AllowCloudTrailEncryptDecrypt"
        Effect    = "Allow"
        Principal = { Service = "cloudtrail.amazonaws.com" }
        Action = [
          "kms:GenerateDataKey",
          "kms:Decrypt",
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "aws:SourceArn" = "arn:aws:cloudtrail:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:trail/exl-${var.env}-trail"
          }
        }
      },
    ]
  })

  tags = local.common_tags
}

resource "aws_kms_alias" "cloudtrail_bucket" {
  name          = "alias/${var.env}-cloudtrail-bucket"
  target_key_id = aws_kms_key.cloudtrail_bucket.key_id
}

resource "aws_kms_key" "flow_logs_cw" {
  description             = "Audit-evidence CMK for the ${var.env} CloudWatch Log groups holding VPC flow logs and CloudTrail event stream. Rotation enabled."
  deletion_window_in_days = 30
  enable_key_rotation     = true
  key_usage               = "ENCRYPT_DECRYPT"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowAccountRoot"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" }
        Action    = "kms:*"
        Resource  = "*"
      },
      {
        Sid       = "AllowCloudWatchLogsEncryptDecrypt"
        Effect    = "Allow"
        Principal = { Service = "logs.${data.aws_region.current.name}.amazonaws.com" }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey",
          "kms:Describe*",
        ]
        Resource = "*"
        Condition = {
          ArnLike = {
            "kms:EncryptionContext:aws:logs:arn" = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:*"
          }
        }
      },
    ]
  })

  tags = local.common_tags
}

resource "aws_kms_alias" "flow_logs_cw" {
  name          = "alias/${var.env}-flow-logs-cw"
  target_key_id = aws_kms_key.flow_logs_cw.key_id
}

# Phase 2 placeholder. The manifest-signing CMK will be created here when ADR-0003
# is implemented (Code Intake + Pipeline Factory). Asymmetric RSA-3072, key_usage =
# "SIGN_VERIFY". Until then, the manifest_signing_key_arn output returns null and
# downstream consumers must guard for null.
#
# resource "aws_kms_key" "manifest_signing" {
#   description              = "Asymmetric signing key for Code Intake and Pipeline Factory manifests. Phase 2."
#   deletion_window_in_days  = 30
#   enable_key_rotation      = false
#   customer_master_key_spec = "RSA_3072"
#   key_usage                = "SIGN_VERIFY"
#   policy                   = jsonencode({...})
#   tags                     = local.common_tags
# }
```

- [ ] **Step 7: Write `outputs.tf`**

```hcl
output "cloudtrail_bucket_key_arn" {
  description = "ARN of the CloudTrail bucket CMK. Pass to aws_s3_bucket_server_side_encryption_configuration on the trail bucket."
  value       = aws_kms_key.cloudtrail_bucket.arn
}

output "cloudtrail_bucket_key_alias" {
  description = "Alias of the CloudTrail bucket CMK."
  value       = aws_kms_alias.cloudtrail_bucket.name
}

output "flow_logs_cw_key_arn" {
  description = "ARN of the flow-logs / CloudWatch Logs CMK. Pass as kms_key_id on aws_cloudwatch_log_group resources."
  value       = aws_kms_key.flow_logs_cw.arn
}

output "flow_logs_cw_key_alias" {
  description = "Alias of the flow-logs / CW Logs CMK."
  value       = aws_kms_alias.flow_logs_cw.name
}

output "manifest_signing_key_arn" {
  description = "ARN of the manifest-signing CMK. Returns null until Phase 2 implements ADR-0003."
  value       = null
}
```

- [ ] **Step 8: Write `README.md`**

````markdown
# `kms-hierarchy` Terraform module

Audit-evidence-grade KMS keys shared across stacks within a single EXL account. Owns the CMKs for the CloudTrail S3 bucket and the CloudWatch Log groups that hold VPC flow logs and CloudTrail event streams. Per-data-class keys (S3 source / destination buckets) remain in their owning modules and are NOT centralised here. Rationale: [ADR-0005](../../../docs/adr/0005-kms-hierarchy-audit-evidence-only.md).

## What this module does NOT own

- S3 source bucket key — owned by `s3-replication-source`
- S3 destination bucket key — owned by `s3-replication-destination`
- VPC data subnet KMS keys — owned by their consuming modules (Phase 2+)

## Usage

```hcl
module "kms_hierarchy" {
  source = "../../modules/kms-hierarchy"

  env = "dev"

  tags = {
    cost_center = "ml-platform"
  }
}

# Use outputs:
resource "aws_s3_bucket_server_side_encryption_configuration" "trail" {
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

## Inputs

See `variables.tf`. Required: `env`, `tags`.

## Outputs

See `outputs.tf`. Notable: `cloudtrail_bucket_key_arn`, `flow_logs_cw_key_arn`, `manifest_signing_key_arn` (Phase 2 placeholder, returns null today).

## Tests

`terraform test` from this directory. Plan-validate only. CI runs the same.

## Compliance mapping

| Control | Where |
| --- | --- |
| ISO 27001 A.10.1 — cryptographic controls | Both keys with rotation enabled, audit-friendly key policies |
| POPIA s19 — security safeguards | Audit-evidence at rest under customer-managed keys |
| SOC 2 CC6.1 — logical access | Service-principal-scoped key policies with aws:SourceArn (CloudTrail) and EncryptionContext (CW Logs) conditions |
| SR 11-7 III.4 — model implementation evidence | CloudTrail and flow logs encrypted under separate CMKs for blast-radius separation |
````

- [ ] **Step 9: Write ADR-0005**

Save to `docs/adr/0005-kms-hierarchy-audit-evidence-only.md`:

```markdown
# ADR-0005: kms-hierarchy module — audit-evidence keys only

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-04-25 |
| Deciders | Engagement lead, EXL Platform Engineering |
| Consulted | EXL InfoSec |

## Context

Phase 1 sprint 2 introduces a `kms-hierarchy` Terraform module to own KMS Customer Master Keys that span multiple stacks. The architectural question: should this module own ALL CMKs across the platform (full centralisation), or only audit-evidence-grade keys that genuinely cross stack boundaries?

Three options were considered:

1. **Full centralisation.** Every CMK in the platform — including the S3 source bucket key, S3 destination bucket key, KMS asymmetric signing key, future per-service keys — flows through this module. Modules consume key ARNs as inputs.
2. **Audit-evidence keys only.** Module owns the CMKs that several stacks consume: CloudTrail bucket key, flow-logs / CW Logs key, and a Phase 2 placeholder for the manifest-signing key. Per-data-class keys (S3 source / destination) remain in their owning modules.
3. **Single account "trunk" key.** One CMK per account named `audit-evidence-{env}` that covers CloudTrail + flow logs + future Config snapshots. Cheaper, but every consumer shares the same key.

## Decision

Option 2 — audit-evidence keys only.

The module owns:
- `${env}-cloudtrail-bucket` — used by the CloudTrail S3 bucket SSE configuration
- `${env}-flow-logs-cw` — used by VPC flow-logs CW Log group AND the CloudTrail event stream CW Log group (both are CW Logs encryption use cases at the same compliance grade)
- `manifest_signing_key_arn` — placeholder output returning `null` until Phase 2 implements ADR-0003

The module does NOT own:
- S3 source bucket key (in `s3-replication-source`)
- S3 destination bucket key (in `s3-replication-destination`)
- Per-data-class keys for stateful workloads added in later phases

## Consequences

### Positive

- Clean separation of concerns. Auditors can point to a single module for audit-evidence-grade encryption.
- Per-data-class key lifecycle (rotation, key policy changes) is owned by the module that consumes the key — no PR-back bottleneck through the central kms module.
- Module surface stays small. Two active resources today, one placeholder. Future audit-evidence keys (e.g. AWS Config snapshot key in Phase 4) extend this module.

### Negative

- Two patterns for KMS in the codebase: centralised (this module) and module-owned (s3-replication-*). Convention drift is possible if future modules don't follow the convention.
- Mitigation: code review enforces the split. The convention is documented in this ADR and referenced from `kms-hierarchy/README.md`.

## Alternatives considered

1. **Full centralisation (Option 1).** Rejected. Centralisation creates a PR-back bottleneck for every key-policy change downstream modules need. The audit benefit ("all keys live here") doesn't outweigh the operational cost. Different consumer modules legitimately have different key-policy needs (e.g. the S3 destination key needs to grant a cross-account replication role; that's not a generic concern).
2. **Single account "trunk" key (Option 3).** Rejected. SR 11-7 reviewers expect blast-radius separation between trail logs and flow logs at the key level — a single trunk key violates that expectation. Cost difference (~$2/mo per account) does not justify the audit risk.

## Compliance mapping

| Control | Reference |
| --- | --- |
| ISO 27001 A.10.1 — cryptographic controls | Both CMKs have rotation enabled and tightly scoped key policies |
| POPIA s19 — security safeguards | Audit-evidence at rest under customer-managed keys |
| SOC 2 CC6.1 — logical access | Service-principal scoped grants with aws:SourceArn / EncryptionContext conditions |
| SR 11-7 III.4 — model implementation evidence | Per-purpose CMKs with separation between trail logs and CW Logs encryption |
```

- [ ] **Step 10: Re-run the test (skip if no terraform CLI)**

If `terraform` is on PATH:

```bash
cd terraform/modules/kms-hierarchy
terraform init -backend=false
terraform validate
terraform test
```

Expected: all 7 `run` blocks pass.

- [ ] **Step 11: Format and commit**

```bash
cd C:/Vishnu/Claude/absa-exl-platform
terraform fmt -recursive 2>/dev/null || true   # only if terraform is on PATH
git add terraform/modules/kms-hierarchy/ docs/adr/0005-kms-hierarchy-audit-evidence-only.md
git commit -m "feat(kms-hierarchy): audit-evidence CMKs + ADR-0005

Two active CMKs per env: cloudtrail-bucket-key and flow-logs-cw-key,
both with rotation enabled and tightly scoped key policies (CloudTrail
service principal with aws:SourceArn condition; CW Logs service
principal with EncryptionContext:aws:logs:arn condition).

manifest_signing_key_arn placeholder output returns null until Phase 2
implements ADR-0003.

ADR-0005 captures the audit-evidence-only architectural choice and
documents why per-data-class keys (S3 source/destination) remain in
their owning modules.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: `terraform/modules/iam-federation/` module

**Files:**
- Create: `terraform/modules/iam-federation/versions.tf`
- Create: `terraform/modules/iam-federation/variables.tf`
- Create: `terraform/modules/iam-federation/main.tf`
- Create: `terraform/modules/iam-federation/roles.tf`
- Create: `terraform/modules/iam-federation/oidc.tf`
- Create: `terraform/modules/iam-federation/outputs.tf`
- Create: `terraform/modules/iam-federation/README.md`
- Create: `terraform/modules/iam-federation/tests/iam_federation.tftest.hcl`

- [ ] **Step 1: Write the failing test first**

Save to `terraform/modules/iam-federation/tests/iam_federation.tftest.hcl`:

```hcl
variables {
  env                                    = "dev"
  absa_identity_center_saml_provider_arn = "arn:aws:iam::000000000000:saml-provider/AWSSSO_test_DO_NOT_DELETE"
  permissions_boundary_arn               = "arn:aws:iam::111111111111:policy/dev-env-scoped-boundary"
  github_org_slash_repo                  = "absa-group/absa-exl-platform"
  allowed_github_branches_for_apply      = ["main"]
  tags = {
    cost_center = "ml-platform"
  }
}

run "all_workload_roles_attach_permissions_boundary" {
  command = plan

  assert {
    condition = (
      aws_iam_role.platform_engineer.permissions_boundary == "arn:aws:iam::111111111111:policy/dev-env-scoped-boundary" &&
      aws_iam_role.platform_operator.permissions_boundary == "arn:aws:iam::111111111111:policy/dev-env-scoped-boundary" &&
      aws_iam_role.platform_readonly.permissions_boundary == "arn:aws:iam::111111111111:policy/dev-env-scoped-boundary" &&
      aws_iam_role.break_glass.permissions_boundary == "arn:aws:iam::111111111111:policy/dev-env-scoped-boundary" &&
      aws_iam_role.ci_deploy.permissions_boundary == "arn:aws:iam::111111111111:policy/dev-env-scoped-boundary"
    )
    error_message = "All five roles must attach the env-scoped permissions boundary"
  }
}

run "break_glass_trust_policy_requires_mfa" {
  command = plan

  assert {
    condition     = strcontains(aws_iam_role.break_glass.assume_role_policy, "MultiFactorAuthPresent")
    error_message = "Break-glass trust policy must require MFA"
  }
}

run "ci_deploy_sub_condition_includes_branch" {
  command = plan

  assert {
    condition = strcontains(
      aws_iam_role.ci_deploy.assume_role_policy,
      "repo:absa-group/absa-exl-platform:ref:refs/heads/main",
    )
    error_message = "ci-deploy trust policy sub condition must include the configured branch"
  }
}

run "ci_deploy_inline_policy_denies_credential_mutation" {
  command = plan

  assert {
    condition = (
      strcontains(aws_iam_role_policy.ci_deploy.policy, "iam:CreateUser") &&
      strcontains(aws_iam_role_policy.ci_deploy.policy, "iam:CreateAccessKey") &&
      strcontains(aws_iam_role_policy.ci_deploy.policy, "kms:ScheduleKeyDeletion") &&
      strcontains(aws_iam_role_policy.ci_deploy.policy, "cloudtrail:StopLogging")
    )
    error_message = "ci-deploy inline policy must explicitly deny credential mutation, key deletion, and audit-evasion actions"
  }
}

run "oidc_provider_uses_sts_client_id" {
  command = plan

  assert {
    condition     = aws_iam_openid_connect_provider.github.client_id_list[0] == "sts.amazonaws.com"
    error_message = "GitHub OIDC provider client_id_list must include sts.amazonaws.com"
  }
}

run "session_durations_match_role_purpose" {
  command = plan

  assert {
    condition = (
      aws_iam_role.platform_engineer.max_session_duration == 28800 &&
      aws_iam_role.platform_operator.max_session_duration == 14400 &&
      aws_iam_role.platform_readonly.max_session_duration == 28800 &&
      aws_iam_role.break_glass.max_session_duration == 3600 &&
      aws_iam_role.ci_deploy.max_session_duration == 3600
    )
    error_message = "Session durations: engineer/readonly 8h, operator 4h, break-glass/ci-deploy 1h"
  }
}

run "env_validation_rejects_unknown_value" {
  command = plan

  variables {
    env = "qa"
  }

  expect_failures = [
    var.env,
  ]
}
```

- [ ] **Step 2: Verify test fails (or skip)**

Same skip rule as Task 1. If `terraform` is on PATH, run `terraform init -backend=false && terraform test` and expect failures.

- [ ] **Step 3: Write `versions.tf`**

```hcl
terraform {
  required_version = ">= 1.9.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.50.0, < 6.0.0"
    }
  }
}
```

- [ ] **Step 4: Write `variables.tf`**

```hcl
variable "env" {
  description = "Deployment environment."
  type        = string

  validation {
    condition     = contains(["dev", "stg", "prod"], var.env)
    error_message = "env must be one of dev, stg, prod."
  }
}

variable "absa_identity_center_saml_provider_arn" {
  description = "ARN of the ABSA-managed AWS IAM Identity Center SAML provider. Provided by ABSA's central platform team. Treated as opaque by this module."
  type        = string
}

variable "permissions_boundary_arn" {
  description = "ARN of the env-scoped permissions boundary policy created by the landing-zone module. Attached to all 5 roles in this module."
  type        = string
}

variable "github_org_slash_repo" {
  description = "GitHub repository in 'org/repo' form. Used to scope the OIDC trust policy sub condition."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$", var.github_org_slash_repo))
    error_message = "github_org_slash_repo must be in 'org/repo' form."
  }
}

variable "allowed_github_branches_for_apply" {
  description = "List of branch names from which the ci-deploy role may be assumed. Each entry produces a sub condition."
  type        = list(string)
  default     = ["main"]
}

variable "tags" {
  description = "Tags applied to every resource. Must include cost_center."
  type        = map(string)

  validation {
    condition     = contains(keys(var.tags), "cost_center")
    error_message = "tags must include cost_center."
  }
}
```

- [ ] **Step 5: Write `main.tf`**

```hcl
locals {
  common_tags = merge(var.tags, {
    env    = var.env
    module = "iam-federation"
  })

  # GitHub Actions root CA thumbprint. Update if GitHub rotates the CA.
  # Confirmed at https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services
  github_oidc_thumbprint = "1c58a3a8518e8759bf075b76b750d4f2df264fcd"

  # Build the list of OIDC sub conditions, one per allowed branch.
  ci_deploy_sub_conditions = [
    for branch in var.allowed_github_branches_for_apply :
    "repo:${var.github_org_slash_repo}:ref:refs/heads/${branch}"
  ]
}

data "aws_caller_identity" "current" {}
```

- [ ] **Step 6: Write `roles.tf`**

```hcl
# SAML federation trust shared by 4 workload roles
locals {
  saml_assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = var.absa_identity_center_saml_provider_arn }
      Action    = "sts:AssumeRoleWithSAML"
      Condition = {
        StringEquals = {
          "SAML:aud" = "https://signin.aws.amazon.com/saml"
        }
      }
    }]
  })

  break_glass_assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = var.absa_identity_center_saml_provider_arn }
      Action    = "sts:AssumeRoleWithSAML"
      Condition = {
        StringEquals = {
          "SAML:aud" = "https://signin.aws.amazon.com/saml"
        }
        Bool = {
          "aws:MultiFactorAuthPresent" = "true"
        }
      }
    }]
  })
}

resource "aws_iam_role" "platform_engineer" {
  name                 = "${var.env}-platform-engineer"
  assume_role_policy   = local.saml_assume_role_policy
  permissions_boundary = var.permissions_boundary_arn
  max_session_duration = 28800

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "platform_engineer_admin" {
  role       = aws_iam_role.platform_engineer.name
  policy_arn = "arn:aws:iam::aws:policy/job-function/SystemAdministrator"
}

resource "aws_iam_role" "platform_operator" {
  name                 = "${var.env}-platform-operator"
  assume_role_policy   = local.saml_assume_role_policy
  permissions_boundary = var.permissions_boundary_arn
  max_session_duration = 14400

  tags = local.common_tags
}

resource "aws_iam_role_policy" "platform_operator" {
  name = "${var.env}-platform-operator-policy"
  role = aws_iam_role.platform_operator.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "AllowReadEverything"
        Effect   = "Allow"
        Action   = ["*:Get*", "*:List*", "*:Describe*", "logs:FilterLogEvents"]
        Resource = "*"
      },
      {
        Sid      = "AllowOperationalWrite"
        Effect   = "Allow"
        Action = [
          "ec2:RebootInstances",
          "ec2:StartInstances",
          "ec2:StopInstances",
          "ecs:UpdateService",
          "lambda:InvokeFunction",
          "states:StartExecution",
          "states:StopExecution",
        ]
        Resource = "*"
      },
      {
        Sid    = "DenyDangerousActions"
        Effect = "Deny"
        Action = [
          "iam:*",
          "kms:ScheduleKeyDeletion",
          "kms:DisableKey",
          "cloudtrail:StopLogging",
          "cloudtrail:DeleteTrail",
          "cloudtrail:UpdateTrail",
        ]
        Resource = "*"
      },
    ]
  })
}

resource "aws_iam_role" "platform_readonly" {
  name                 = "${var.env}-platform-readonly"
  assume_role_policy   = local.saml_assume_role_policy
  permissions_boundary = var.permissions_boundary_arn
  max_session_duration = 28800

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "platform_readonly" {
  role       = aws_iam_role.platform_readonly.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

resource "aws_iam_role" "break_glass" {
  name                 = "${var.env}-break-glass"
  assume_role_policy   = local.break_glass_assume_role_policy
  permissions_boundary = var.permissions_boundary_arn
  max_session_duration = 3600

  tags = merge(local.common_tags, {
    purpose = "incident-response"
    audit   = "high"
  })
}

resource "aws_iam_role_policy_attachment" "break_glass_admin" {
  role       = aws_iam_role.break_glass.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}
```

- [ ] **Step 7: Write `oidc.tf`**

```hcl
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [local.github_oidc_thumbprint]

  tags = local.common_tags
}

resource "aws_iam_role" "ci_deploy" {
  name = "${var.env}-ci-deploy"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.github.arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        StringLike = {
          "token.actions.githubusercontent.com:sub" = local.ci_deploy_sub_conditions
        }
      }
    }]
  })

  permissions_boundary = var.permissions_boundary_arn
  max_session_duration = 3600

  tags = local.common_tags
}

resource "aws_iam_role_policy" "ci_deploy" {
  name = "${var.env}-ci-deploy-policy"
  role = aws_iam_role.ci_deploy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "AllowAllByDefault"
        Effect   = "Allow"
        Action   = "*"
        Resource = "*"
      },
      {
        Sid    = "DenyCredentialMutation"
        Effect = "Deny"
        Action = [
          "iam:CreateUser",
          "iam:DeleteUser",
          "iam:CreateAccessKey",
          "iam:DeleteAccessKey",
          "iam:UpdateLoginProfile",
          "iam:CreateLoginProfile",
          "iam:DeleteLoginProfile",
          "iam:DeactivateMFADevice",
          "iam:DeleteVirtualMFADevice",
        ]
        Resource = "*"
      },
      {
        Sid    = "DenyKeyAndAuditDestruction"
        Effect = "Deny"
        Action = [
          "kms:ScheduleKeyDeletion",
          "kms:DisableKey",
          "kms:DisableKeyRotation",
          "s3:DeleteBucket",
          "cloudtrail:StopLogging",
          "cloudtrail:DeleteTrail",
        ]
        Resource = "*"
      },
    ]
  })
}
```

- [ ] **Step 8: Write `outputs.tf`**

```hcl
output "platform_engineer_role_arn" {
  description = "ARN of the SAML-trust platform engineer role (8h session, SystemAdministrator-class permissions within boundary)."
  value       = aws_iam_role.platform_engineer.arn
}

output "platform_operator_role_arn" {
  description = "ARN of the SAML-trust platform operator role (4h session, read everything plus narrow operational write)."
  value       = aws_iam_role.platform_operator.arn
}

output "platform_readonly_role_arn" {
  description = "ARN of the SAML-trust readonly role (8h session, ReadOnlyAccess managed policy)."
  value       = aws_iam_role.platform_readonly.arn
}

output "break_glass_role_arn" {
  description = "ARN of the SAML-trust break-glass role (1h session, AdministratorAccess, MFA required). AssumeRole triggers a CloudTrail metric-filter alarm."
  value       = aws_iam_role.break_glass.arn
}

output "ci_deploy_role_arn" {
  description = "ARN of the OIDC-trust CI deploy role (1h session, * minus credential / key / audit destruction)."
  value       = aws_iam_role.ci_deploy.arn
}

output "github_oidc_provider_arn" {
  description = "ARN of the GitHub Actions OIDC provider for this account."
  value       = aws_iam_openid_connect_provider.github.arn
}
```

- [ ] **Step 9: Write `README.md`**

````markdown
# `iam-federation` Terraform module

Workload IAM roles + GitHub Actions OIDC provider for an EXL env account. Provisions five roles (4 SAML-trust, 1 OIDC-trust) and one OIDC provider.

ABSA's central platform team owns IAM Identity Center / SSO federation per [ADR-0004](../../../docs/adr/0004-account-topology-1-absa-3-exl.md). This module accepts the SAML provider ARN as an opaque input and uses it to build the trust policy of the four workload roles.

## Five roles

| Role | Trust | Session | Permissions |
| --- | --- | --- | --- |
| `${env}-platform-engineer` | SAML | 8h | `SystemAdministrator` managed policy within boundary |
| `${env}-platform-operator` | SAML | 4h | Read everything + narrow operational write; explicit deny on IAM, KMS deletion, CloudTrail mods |
| `${env}-platform-readonly` | SAML | 8h | `ReadOnlyAccess` managed policy |
| `${env}-break-glass` | SAML + MFA required | 1h | `AdministratorAccess` managed policy. AssumeRole triggers a CloudTrail metric-filter alarm. Use only for incident response. |
| `${env}-ci-deploy` | OIDC (GitHub Actions) | 1h | `*` minus explicit deny list (credential mutation, key deletion, audit evasion). `sub` condition restricts to configured GitHub branches. |

All five roles attach `var.permissions_boundary_arn` (the env-scoped boundary from `landing-zone`).

## GitHub OIDC trust policy

The ci-deploy role's trust policy uses both:
- `StringEquals` on `aud = sts.amazonaws.com` — every OIDC token must be intended for STS
- `StringLike` on `sub` matching the configured `repo:${org}/${repo}:ref:refs/heads/${branch}` patterns — restricts which branches' workflows can assume the role

This combination prevents the "any-repo can assume" vulnerability that has caused real incidents in the wild. Forks of the repository, pull-request workflows, and tag pushes will all fail to match the `sub` condition.

## GitHub OIDC root CA thumbprint

Stored as `local.github_oidc_thumbprint` in `main.tf`. Currently `1c58a3a8518e8759bf075b76b750d4f2df264fcd`. GitHub rotates this CA periodically — verify the current value against [GitHub's OIDC documentation](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services) before first apply.

## Usage

```hcl
module "iam_federation" {
  source = "../../modules/iam-federation"

  env                                    = "dev"
  absa_identity_center_saml_provider_arn = "arn:aws:iam::123456789012:saml-provider/AWSSSO_xxx_DO_NOT_DELETE"
  permissions_boundary_arn               = "arn:aws:iam::222222222222:policy/dev-env-scoped-boundary"
  github_org_slash_repo                  = "absa-group/absa-exl-platform"
  allowed_github_branches_for_apply      = ["main"]

  tags = {
    cost_center = "ml-platform"
  }
}
```

## Inputs

See `variables.tf`.

## Outputs

See `outputs.tf`.

## Tests

`terraform test` from this directory.

## Compliance mapping

| Control | Where |
| --- | --- |
| ISO 27001 A.9.2 — user access management | SAML federation, role-per-purpose |
| SOC 2 CC6.1 — logical access | Permissions boundary on every role; explicit denies on dangerous actions |
| SOC 2 CC6.6 — privileged access | Break-glass requires MFA, 1h session, alarmed in CloudTrail |
| ABSA GMRMG access governance | Workload-role separation; ci-deploy strictly scoped to configured branches |
````

- [ ] **Step 10: Re-run the test (skip if no terraform CLI)**

If `terraform` is on PATH, run `terraform init -backend=false && terraform validate && terraform test` from the module directory. All 7 test runs should pass.

- [ ] **Step 11: Format and commit**

```bash
cd C:/Vishnu/Claude/absa-exl-platform
terraform fmt -recursive 2>/dev/null || true
git add terraform/modules/iam-federation/
git commit -m "feat(iam-federation): SAML workload roles + GitHub OIDC ci-deploy

Five roles, all attaching the env-scoped permissions boundary from
landing-zone:
- platform-engineer (SAML, 8h, SystemAdministrator within boundary)
- platform-operator (SAML, 4h, read+narrow ops write, explicit denies)
- platform-readonly (SAML, 8h, ReadOnlyAccess)
- break-glass (SAML+MFA required, 1h, AdministratorAccess; alarmed in
  CloudTrail metric filters)
- ci-deploy (OIDC, 1h, * minus credential / key / audit destruction)

GitHub OIDC provider with strict sub condition:
'repo:\${org}/\${repo}:ref:refs/heads/\${branch}' for each branch in
var.allowed_github_branches_for_apply. Default ['main'].

Module accepts the ABSA Identity Center SAML provider ARN as an opaque
input — ABSA central platform team owns the federation side per
ADR-0004.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Account-singleton refactor — remove from `landing-zone`

**Files:**
- Modify: `terraform/modules/landing-zone/iam.tf`
- Modify: `terraform/modules/landing-zone/security.tf`
- Modify: `terraform/modules/landing-zone/variables.tf`
- Modify: `terraform/modules/landing-zone/outputs.tf`
- Modify: `terraform/modules/landing-zone/tests/landing_zone.tftest.hcl`
- Modify: `terraform/modules/landing-zone/README.md`

The corresponding additions to `account-bootstrap` happen in Task 4 (combined with the SSE-KMS upgrade since both touch the same file).

- [ ] **Step 1: Delete `aws_iam_account_password_policy.this` from `landing-zone/iam.tf`**

Open `terraform/modules/landing-zone/iam.tf`. The current file has:

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

resource "aws_iam_policy" "env_scoped_boundary" {
  # ...
}
```

Delete the entire `aws_iam_account_password_policy.this` block. The file now starts with `resource "aws_iam_policy" "env_scoped_boundary"`.

- [ ] **Step 2: Delete GuardDuty + Security Hub from `landing-zone/security.tf`**

Open `terraform/modules/landing-zone/security.tf`. Find and delete these three blocks:

```hcl
resource "aws_guardduty_detector" "this" {
  count = var.enable_guardduty ? 1 : 0

  enable                       = true
  finding_publishing_frequency = "FIFTEEN_MINUTES"

  tags = local.common_tags
}

resource "aws_securityhub_account" "this" {
  count = var.enable_security_hub ? 1 : 0
}

resource "aws_securityhub_standards_subscription" "foundational" {
  count = var.enable_security_hub ? 1 : 0

  standards_arn = "arn:aws:securityhub:${data.aws_region.current.name}::standards/aws-foundational-security-best-practices/v/1.0.0"

  depends_on = [aws_securityhub_account.this]
}
```

The flow-logs resources (CloudWatch log group, IAM role, role policy, flow log) stay in `security.tf`. The `data.aws_region.current` data source stays — it was used by the Security Hub standards ARN, but is no longer needed in this file. If it's only referenced by the deleted block, also delete the data source declaration; otherwise keep it.

After this step, `security.tf` contains only the four flow-logs resources.

- [ ] **Step 3: Drop `enable_guardduty` and `enable_security_hub` from `variables.tf`**

In `terraform/modules/landing-zone/variables.tf`, delete these two variable blocks:

```hcl
variable "enable_guardduty" {
  description = "Whether to enable GuardDuty in this account. Default true; set false only for ephemeral test accounts."
  type        = bool
  default     = true
}

variable "enable_security_hub" {
  description = "Whether to enable Security Hub. Default true."
  type        = bool
  default     = true
}
```

The remaining variables are `env`, `region`, `vpc_cidr`, `availability_zones`, `transit_gateway_id`, `flow_logs_retention_days`, `tags`.

- [ ] **Step 4: Drop `guardduty_detector_id` from `outputs.tf`**

In `terraform/modules/landing-zone/outputs.tf`, delete:

```hcl
output "guardduty_detector_id" {
  description = "GuardDuty detector ID, or null if disabled."
  value       = try(aws_guardduty_detector.this[0].id, null)
}
```

- [ ] **Step 5: Drop the two failing tests from `tests/landing_zone.tftest.hcl`**

Open `terraform/modules/landing-zone/tests/landing_zone.tftest.hcl`. Delete these two `run` blocks:

```hcl
run "guardduty_detector_exists_when_enabled" {
  command = plan

  variables {
    enable_guardduty = true
  }

  assert {
    condition     = length(aws_guardduty_detector.this) == 1
    error_message = "GuardDuty detector must be created when enable_guardduty=true"
  }
}

run "security_hub_uses_foundational_standard" {
  command = plan

  variables {
    enable_security_hub = true
  }

  assert {
    condition     = length(aws_securityhub_standards_subscription.foundational) == 1
    error_message = "Security Hub Foundational standard must be subscribed"
  }
}
```

Also remove `enable_guardduty` and `enable_security_hub` from the file-level `variables {}` block at the top of the file if they were defaulted there.

- [ ] **Step 6: Update the README — delete the "Known gap" section**

Open `terraform/modules/landing-zone/README.md`. Find and delete the entire section that starts with `## Known gap — account-singleton resources` and continues until the next `##` heading.

The README's resource list (in the description paragraph or "What this module does" section) should also be updated: remove mentions of GuardDuty, Security Hub, and password policy. The module now owns: VPC + subnets + NAT + TGW + flow logs + permissions boundary.

- [ ] **Step 7: Commit**

```bash
cd C:/Vishnu/Claude/absa-exl-platform
git add terraform/modules/landing-zone/
git commit -m "refactor(landing-zone): remove account-singleton resources

Removed aws_iam_account_password_policy, aws_securityhub_account +
foundational standard subscription, and aws_guardduty_detector. These
resources are AWS-account singletons and belong in account-bootstrap
where there is exactly one stack per EXL account. Sprint 2 task 4
adds them to account-bootstrap/exl-{env}/main.tf.

Dropped var.enable_guardduty, var.enable_security_hub, output
guardduty_detector_id, and the two corresponding test runs. README's
'Known gap — account-singleton resources' section deleted (the gap is
closed).

The module now owns: VPC + subnets + NAT + TGW + flow logs +
permissions boundary policy. Pure per-env workload landing zone.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Account-singleton add + CloudTrail SSE-KMS upgrade in `account-bootstrap`

**Files:**
- Modify: `terraform/account-bootstrap/exl-dev/main.tf`
- Modify: `terraform/account-bootstrap/exl-stg/main.tf`
- Modify: `terraform/account-bootstrap/exl-prod/main.tf`

This task adds: kms-hierarchy module call, CloudTrail SSE-KMS upgrade replacing AES256, and the three account-singleton resources moved from landing-zone (password policy, GuardDuty, Security Hub + foundational standard).

- [ ] **Step 1: Edit `terraform/account-bootstrap/exl-dev/main.tf`**

The existing file has provider, CloudTrail trail, CloudTrail S3 bucket, bucket lifecycle, versioning, server-side encryption (currently AES256), public access block, bucket policy, and `data.aws_caller_identity.current`. Make these changes:

**1a — Add the kms-hierarchy module call** at the top of the file (after the `terraform { }` block, before any other resources):

```hcl
module "kms_hierarchy" {
  source = "../../modules/kms-hierarchy"

  env = "dev"

  tags = {
    cost_center = "ml-platform"
  }
}
```

**1b — Replace the SSE configuration**. The current block looks like:

```hcl
# TODO(Phase 1 sprint 2): switch to SSE-KMS with a CMK from the
# kms-hierarchy module once that module is built. AES256 is interim.
resource "aws_s3_bucket_server_side_encryption_configuration" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
```

Replace with:

```hcl
# Phase 1 sprint 2: SSE-KMS via kms-hierarchy.cloudtrail_bucket_key_arn.
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

**1c — Add the three account-singleton resources** anywhere in the file (recommend a clearly demarcated section at the bottom):

```hcl
# ---------------------------------------------------------------------
# Account-singleton resources (moved from landing-zone in sprint 2).
# Each EXL account has exactly one of these.
# ---------------------------------------------------------------------

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

  tags = {
    env         = "dev"
    cost_center = "ml-platform"
    managed_by  = "terraform"
    stack       = "account-bootstrap/exl-dev"
  }
}

resource "aws_securityhub_account" "this" {}

resource "aws_securityhub_standards_subscription" "foundational" {
  standards_arn = "arn:aws:securityhub:${var.region}::standards/aws-foundational-security-best-practices/v/1.0.0"

  depends_on = [aws_securityhub_account.this]
}
```

- [ ] **Step 2: Replicate to `exl-stg/main.tf`**

Apply the same three additions (1a, 1b, 1c) to `terraform/account-bootstrap/exl-stg/main.tf`. Substitutions per env:
- `env = "stg"` in the kms_hierarchy module call
- `env = "stg"` in the GuardDuty resource tags
- `stack = "account-bootstrap/exl-stg"` in tags

The SSE block fix (1b) is identical (uses `module.kms_hierarchy.cloudtrail_bucket_key_arn` regardless of env).

- [ ] **Step 3: Replicate to `exl-prod/main.tf`**

Apply the same changes to `terraform/account-bootstrap/exl-prod/main.tf`. Substitutions:
- `env = "prod"` in the kms_hierarchy module call
- `env = "prod"` in the GuardDuty resource tags
- `stack = "account-bootstrap/exl-prod"` in tags

- [ ] **Step 4: Verify all three stacks are syntactically consistent**

```bash
cd C:/Vishnu/Claude/absa-exl-platform
diff terraform/account-bootstrap/exl-dev/main.tf terraform/account-bootstrap/exl-stg/main.tf | head -40
```

Expected: only diffs are env tokens (`dev` vs `stg`, `account-bootstrap/exl-dev` vs `account-bootstrap/exl-stg`).

- [ ] **Step 5: Commit**

```bash
git add terraform/account-bootstrap/
git commit -m "feat(account-bootstrap): add kms-hierarchy + singletons + SSE-KMS

Three changes per account-bootstrap stack (exl-dev/stg/prod):

1. Added module 'kms_hierarchy' call producing the cloudtrail-bucket
   and flow-logs-cw CMKs for this account.

2. CloudTrail S3 bucket SSE upgraded from interim AES256 to SSE-KMS
   using module.kms_hierarchy.cloudtrail_bucket_key_arn. Replaces the
   sprint-1 TODO comment.

3. Account-singleton resources moved from landing-zone:
   aws_iam_account_password_policy, aws_guardduty_detector,
   aws_securityhub_account, aws_securityhub_standards_subscription.
   Closes the 'Known gap' deferral from sprint 1.

Each EXL account has exactly one of each singleton.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: CloudTrail observability — CW Logs + 6 metric filters + alarms + SNS topic + iam-federation

**Files:**
- Modify: `terraform/account-bootstrap/exl-dev/main.tf`
- Modify: `terraform/account-bootstrap/exl-stg/main.tf`
- Modify: `terraform/account-bootstrap/exl-prod/main.tf`

The heaviest content addition. ~120 new lines per file (across CW Log group, CloudTrail-to-CWLogs role, 6 metric filters, 6 alarms, SNS topic, iam-federation module call). Apply identically across all 3 stacks with env-token substitutions.

- [ ] **Step 1: Add the CloudWatch Log group + delivery role to `exl-dev/main.tf`**

Add after the existing CloudTrail resource (after `aws_cloudtrail.this`):

```hcl
# ---------------------------------------------------------------------
# CloudTrail → CloudWatch Logs (sprint 2 task 5)
# Near-real-time event stream for security operations + metric filters.
# ---------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "cloudtrail" {
  name              = "/aws/cloudtrail/exl-dev"
  retention_in_days = 365
  kms_key_id        = module.kms_hierarchy.flow_logs_cw_key_arn

  tags = {
    env         = "dev"
    cost_center = "ml-platform"
    managed_by  = "terraform"
    stack       = "account-bootstrap/exl-dev"
  }
}

resource "aws_iam_role" "cloudtrail_to_cwlogs" {
  name = "exl-dev-cloudtrail-to-cwlogs"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "cloudtrail.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = {
    env         = "dev"
    cost_center = "ml-platform"
    managed_by  = "terraform"
    stack       = "account-bootstrap/exl-dev"
  }
}

resource "aws_iam_role_policy" "cloudtrail_to_cwlogs" {
  name = "exl-dev-cloudtrail-to-cwlogs"
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

- [ ] **Step 2: Wire CW Logs into the existing CloudTrail resource**

In `exl-dev/main.tf`, find the existing `resource "aws_cloudtrail" "this"` block. It currently has `name`, `s3_bucket_name`, `include_global_service_events`, `is_multi_region_trail`, `enable_log_file_validation`, and an `event_selector` block. Add two new arguments inside the resource:

```hcl
resource "aws_cloudtrail" "this" {
  name                          = "exl-dev-trail"
  s3_bucket_name                = aws_s3_bucket.cloudtrail.id
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_log_file_validation    = true

  cloud_watch_logs_group_arn = "${aws_cloudwatch_log_group.cloudtrail.arn}:*"
  cloud_watch_logs_role_arn  = aws_iam_role.cloudtrail_to_cwlogs.arn

  event_selector {
    # ...existing content unchanged...
  }
}
```

- [ ] **Step 3: Add the SNS topic for security alerts**

Append to `exl-dev/main.tf`:

```hcl
# ---------------------------------------------------------------------
# Security alerts SNS topic — alarmed by metric filters below.
# Subscriptions live per-env (operator adds via console or a separate
# subscription stack), not in this module.
# ---------------------------------------------------------------------

resource "aws_sns_topic" "security_alerts" {
  name              = "dev-security-alerts"
  kms_master_key_id = "alias/aws/sns"

  tags = {
    env         = "dev"
    cost_center = "ml-platform"
    managed_by  = "terraform"
    stack       = "account-bootstrap/exl-dev"
  }
}
```

- [ ] **Step 4: Add the 6 metric filters**

Append to `exl-dev/main.tf`:

```hcl
# ---------------------------------------------------------------------
# CIS AWS Benchmark v3 detective control metric filters.
# Each filter publishes a custom metric in the AbsaExlSecurity namespace;
# alarms below watch those metrics.
# ---------------------------------------------------------------------

locals {
  metric_namespace = "AbsaExlSecurity"
}

resource "aws_cloudwatch_log_metric_filter" "root_usage" {
  name           = "exl-dev-root-usage"
  log_group_name = aws_cloudwatch_log_group.cloudtrail.name
  pattern        = "{ $.userIdentity.type = \"Root\" && $.userIdentity.invokedBy NOT EXISTS && $.eventType != \"AwsServiceEvent\" }"

  metric_transformation {
    name      = "RootUsage"
    namespace = local.metric_namespace
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "iam_policy_change" {
  name           = "exl-dev-iam-policy-change"
  log_group_name = aws_cloudwatch_log_group.cloudtrail.name
  pattern        = "{ ($.eventName = DeleteGroupPolicy) || ($.eventName = DeleteRolePolicy) || ($.eventName = DeleteUserPolicy) || ($.eventName = PutGroupPolicy) || ($.eventName = PutRolePolicy) || ($.eventName = PutUserPolicy) || ($.eventName = CreatePolicy) || ($.eventName = DeletePolicy) || ($.eventName = AttachRolePolicy) || ($.eventName = DetachRolePolicy) || ($.eventName = AttachUserPolicy) || ($.eventName = DetachUserPolicy) || ($.eventName = AttachGroupPolicy) || ($.eventName = DetachGroupPolicy) }"

  metric_transformation {
    name      = "IAMPolicyChange"
    namespace = local.metric_namespace
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "kms_cmk_change" {
  name           = "exl-dev-kms-cmk-change"
  log_group_name = aws_cloudwatch_log_group.cloudtrail.name
  pattern        = "{ ($.eventSource = kms.amazonaws.com) && (($.eventName = DisableKey) || ($.eventName = ScheduleKeyDeletion)) }"

  metric_transformation {
    name      = "KMSCMKChange"
    namespace = local.metric_namespace
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "s3_policy_change" {
  name           = "exl-dev-s3-policy-change"
  log_group_name = aws_cloudwatch_log_group.cloudtrail.name
  pattern        = "{ ($.eventSource = s3.amazonaws.com) && (($.eventName = PutBucketAcl) || ($.eventName = PutBucketPolicy) || ($.eventName = PutBucketCors) || ($.eventName = PutBucketLifecycle) || ($.eventName = PutBucketReplication) || ($.eventName = DeleteBucketPolicy) || ($.eventName = DeleteBucketCors) || ($.eventName = DeleteBucketLifecycle) || ($.eventName = DeleteBucketReplication)) }"

  metric_transformation {
    name      = "S3PolicyChange"
    namespace = local.metric_namespace
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "sts_assume_role_fail" {
  name           = "exl-dev-sts-assume-role-fail"
  log_group_name = aws_cloudwatch_log_group.cloudtrail.name
  pattern        = "{ ($.eventSource = sts.amazonaws.com) && ($.errorCode EXISTS) }"

  metric_transformation {
    name      = "STSAssumeRoleFail"
    namespace = local.metric_namespace
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "cloudtrail_change" {
  name           = "exl-dev-cloudtrail-change"
  log_group_name = aws_cloudwatch_log_group.cloudtrail.name
  pattern        = "{ ($.eventSource = cloudtrail.amazonaws.com) && (($.eventName = StopLogging) || ($.eventName = DeleteTrail) || ($.eventName = UpdateTrail)) }"

  metric_transformation {
    name      = "CloudTrailChange"
    namespace = local.metric_namespace
    value     = "1"
  }
}
```

- [ ] **Step 5: Add the 6 alarms**

Append to `exl-dev/main.tf`:

```hcl
# ---------------------------------------------------------------------
# CIS AWS Benchmark v3 alarms paired with the metric filters above.
# All alarm actions go to the security_alerts SNS topic.
# ---------------------------------------------------------------------

locals {
  alarm_tags = {
    env         = "dev"
    cost_center = "ml-platform"
    managed_by  = "terraform"
    stack       = "account-bootstrap/exl-dev"
  }
}

resource "aws_cloudwatch_metric_alarm" "root_usage" {
  alarm_name          = "exl-dev-root-usage"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "RootUsage"
  namespace           = local.metric_namespace
  period              = 60
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "Root account usage detected in exl-dev"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.security_alerts.arn]

  tags = local.alarm_tags
}

resource "aws_cloudwatch_metric_alarm" "iam_policy_change" {
  alarm_name          = "exl-dev-iam-policy-change"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "IAMPolicyChange"
  namespace           = local.metric_namespace
  period              = 60
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "IAM policy change detected in exl-dev"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.security_alerts.arn]

  tags = local.alarm_tags
}

resource "aws_cloudwatch_metric_alarm" "kms_cmk_change" {
  alarm_name          = "exl-dev-kms-cmk-change"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "KMSCMKChange"
  namespace           = local.metric_namespace
  period              = 60
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "KMS key disabled or scheduled for deletion in exl-dev"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.security_alerts.arn]

  tags = local.alarm_tags
}

resource "aws_cloudwatch_metric_alarm" "s3_policy_change" {
  alarm_name          = "exl-dev-s3-policy-change"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "S3PolicyChange"
  namespace           = local.metric_namespace
  period              = 60
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "S3 bucket policy change detected in exl-dev"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.security_alerts.arn]

  tags = local.alarm_tags
}

resource "aws_cloudwatch_metric_alarm" "sts_assume_role_fail" {
  alarm_name          = "exl-dev-sts-assume-role-fail-burst"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 5
  datapoints_to_alarm = 5
  metric_name         = "STSAssumeRoleFail"
  namespace           = local.metric_namespace
  period              = 60
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "≥10 failed STS AssumeRole attempts in 5 minutes — possible credential probing"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.security_alerts.arn]

  tags = local.alarm_tags
}

resource "aws_cloudwatch_metric_alarm" "cloudtrail_change" {
  alarm_name          = "exl-dev-cloudtrail-change"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "CloudTrailChange"
  namespace           = local.metric_namespace
  period              = 60
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "CloudTrail config change detected in exl-dev (StopLogging / DeleteTrail / UpdateTrail)"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.security_alerts.arn]

  tags = local.alarm_tags
}
```

- [ ] **Step 6: Add the iam-federation module call**

Append to `exl-dev/main.tf`:

```hcl
# ---------------------------------------------------------------------
# IAM federation — workload roles (SAML) + GitHub Actions OIDC ci-deploy.
# permissions_boundary_arn is constructed deterministically from the
# known pattern of the policy created by the landing-zone module in
# the destination stack.
# ---------------------------------------------------------------------

locals {
  permissions_boundary_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/dev-env-scoped-boundary"
}

module "iam_federation" {
  source = "../../modules/iam-federation"

  env = "dev"
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

- [ ] **Step 7: Replicate steps 1-6 to `exl-stg/main.tf` and `exl-prod/main.tf`**

Apply the same blocks to the other two account-bootstrap stacks. Substitution table:

| Token | exl-dev | exl-stg | exl-prod |
| --- | --- | --- | --- |
| `env = "dev"` (kms_hierarchy + iam_federation) | dev | stg | prod |
| `aws_cloudwatch_log_group.cloudtrail` name `/aws/cloudtrail/exl-dev` | exl-dev | exl-stg | exl-prod |
| `exl-dev-cloudtrail-to-cwlogs` (role + policy) | exl-dev | exl-stg | exl-prod |
| `aws_sns_topic.security_alerts` name `dev-security-alerts` | dev | stg | prod |
| Metric filter names `exl-dev-*` | exl-dev | exl-stg | exl-prod |
| Alarm names `exl-dev-*` | exl-dev | exl-stg | exl-prod |
| Tags `env = "dev"` and `stack = "account-bootstrap/exl-dev"` | dev / exl-dev | stg / exl-stg | prod / exl-prod |
| `local.permissions_boundary_arn` policy name `dev-env-scoped-boundary` | dev | stg | prod |

The `local.metric_namespace = "AbsaExlSecurity"` and `local.alarm_tags` blocks stay identical (only the env field varies via the substitution above).

- [ ] **Step 8: Verify substitutions worked**

```bash
cd C:/Vishnu/Claude/absa-exl-platform
grep -c '"dev"' terraform/account-bootstrap/exl-dev/main.tf
grep -c '"stg"' terraform/account-bootstrap/exl-stg/main.tf
grep -c '"prod"' terraform/account-bootstrap/exl-prod/main.tf
grep '"dev"' terraform/account-bootstrap/exl-stg/main.tf  # should print nothing
grep '"stg"' terraform/account-bootstrap/exl-dev/main.tf  # should print nothing
```

If any cross-env tokens leak, fix before committing.

- [ ] **Step 9: Commit**

```bash
git add terraform/account-bootstrap/
git commit -m "feat(account-bootstrap): CloudTrail observability + iam-federation

Per account-bootstrap stack (exl-dev/stg/prod), adds:

- CloudWatch Log group /aws/cloudtrail/exl-{env} encrypted with the
  flow-logs-cw key from kms-hierarchy. CloudTrail event stream wired
  via cloud_watch_logs_group_arn + cloud_watch_logs_role_arn.

- 6 metric filters in namespace AbsaExlSecurity (CIS AWS Benchmark v3
  detective controls): RootUsage, IAMPolicyChange, KMSCMKChange,
  S3PolicyChange, STSAssumeRoleFail, CloudTrailChange.

- 6 paired CloudWatch alarms: 5 fire at threshold ≥1 over 60s;
  STSAssumeRoleFail fires at ≥10 over 5 min (credential probing).
  All actions route to the new \${env}-security-alerts SNS topic.

- SNS topic \${env}-security-alerts encrypted with alias/aws/sns.
  No subscriptions in module — env stack pattern matches replication
  alerts topic.

- iam-federation module call wires 5 workload roles (4 SAML, 1 OIDC
  ci-deploy) into the account. permissions_boundary_arn is constructed
  deterministically from the known landing-zone policy name to avoid
  cross-stack state coupling.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Destination KMS chicken-and-egg fix

**Files:**
- Modify: `terraform/modules/s3-replication-destination/variables.tf`
- Modify: `terraform/modules/s3-replication-destination/kms.tf`
- Modify: `terraform/modules/s3-replication-destination/policy.tf`
- Modify: `terraform/modules/s3-replication-destination/README.md`
- Modify: `terraform/modules/s3-replication-destination/tests/destination.tftest.hcl`
- Modify: `terraform/envs/dev/destination/main.tf`
- Modify: `terraform/envs/stg/destination/main.tf`
- Modify: `terraform/envs/prod/destination/main.tf`

- [ ] **Step 1: Make `source_replication_role_arn` nullable in `variables.tf`**

Open `terraform/modules/s3-replication-destination/variables.tf`. Find:

```hcl
variable "source_replication_role_arn" {
  description = "ARN of the source-side replication role. Granted permission to write into this bucket and use this KMS key."
  type        = string
}
```

Replace with:

```hcl
variable "source_replication_role_arn" {
  description = "ARN of the source-side replication role. Pass null on first destination apply (before the source side has applied) — KMS key policy and bucket policy will omit source-role grants in that case. Pass the real ARN on the second destination apply once the source role exists."
  type        = string
  default     = null
  nullable    = true
}
```

- [ ] **Step 2: Refactor `kms.tf` with conditional grant**

Open `terraform/modules/s3-replication-destination/kms.tf`. The current `aws_kms_key.this` resource has a key policy with two statements (`AllowAccountRoot` and `AllowSourceReplicationRoleEncrypt`). Replace the entire resource with:

```hcl
resource "aws_kms_key" "this" {
  description             = "Destination-side CMK for ${var.bucket_name}"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  key_usage               = "ENCRYPT_DECRYPT"

  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = concat([local.account_root_kms_grant], local.source_role_kms_grant)
  })

  tags = local.common_tags
}

resource "aws_kms_alias" "this" {
  name          = "alias/model-landing-${var.env}"
  target_key_id = aws_kms_key.this.key_id
}
```

Then add a new `locals` block at the top of `kms.tf` (or in a new `locals.tf` file — pick whichever is consistent with the rest of the module; here add at the top of `kms.tf`):

```hcl
locals {
  account_root_kms_grant = {
    Sid       = "AllowAccountRoot"
    Effect    = "Allow"
    Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" }
    Action    = "kms:*"
    Resource  = "*"
  }

  source_role_kms_grant = var.source_replication_role_arn == null ? [] : [{
    Sid       = "AllowSourceReplicationRoleEncrypt"
    Effect    = "Allow"
    Principal = { AWS = var.source_replication_role_arn }
    Action = [
      "kms:Encrypt",
      "kms:DescribeKey",
    ]
    Resource = "*"
  }]
}
```

- [ ] **Step 3: Refactor `policy.tf` with conditional grant**

Open `terraform/modules/s3-replication-destination/policy.tf`. The current `aws_s3_bucket_policy.this` resource has 2 statements (`AllowSourceReplicationRoleWrite` and `AllowSourceAccountReadBucketVersioning`). Refactor:

```hcl
locals {
  source_role_bucket_grant = var.source_replication_role_arn == null ? [] : [{
    Sid       = "AllowSourceReplicationRoleWrite"
    Effect    = "Allow"
    Principal = { AWS = var.source_replication_role_arn }
    Action = [
      "s3:ReplicateObject",
      "s3:ReplicateDelete",
      "s3:ReplicateTags",
      "s3:ObjectOwnerOverrideToBucketOwner",
    ]
    Resource = "${aws_s3_bucket.this.arn}/*"
  }]

  source_account_bucket_grant = {
    Sid       = "AllowSourceAccountReadBucketVersioning"
    Effect    = "Allow"
    Principal = { AWS = "arn:aws:iam::${var.source_account_id}:root" }
    Action    = "s3:GetBucketVersioning"
    Resource  = aws_s3_bucket.this.arn
  }
}

resource "aws_s3_bucket_policy" "this" {
  bucket = aws_s3_bucket.this.id

  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = concat(local.source_role_bucket_grant, [local.source_account_bucket_grant])
  })
}
```

Note: the `source_account_bucket_grant` is unconditional because `var.source_account_id` is always provided (it's a string, not nullable). Only the role-keyed statement is conditional.

- [ ] **Step 4: Add 2 new tests to `tests/destination.tftest.hcl`**

Open `terraform/modules/s3-replication-destination/tests/destination.tftest.hcl`. Add at the end of the file:

```hcl
run "null_source_role_omits_kms_grant_in_policy" {
  command = plan

  variables {
    source_replication_role_arn = null
  }

  assert {
    condition = !strcontains(
      aws_kms_key.this.policy,
      "AllowSourceReplicationRoleEncrypt",
    )
    error_message = "When source_replication_role_arn is null, KMS key policy must NOT contain the AllowSourceReplicationRoleEncrypt statement"
  }

  assert {
    condition = !strcontains(
      aws_s3_bucket_policy.this.policy,
      "AllowSourceReplicationRoleWrite",
    )
    error_message = "When source_replication_role_arn is null, bucket policy must NOT contain the AllowSourceReplicationRoleWrite statement"
  }
}

run "non_null_source_role_includes_kms_and_bucket_grants" {
  command = plan

  variables {
    source_replication_role_arn = "arn:aws:iam::111111111111:role/dev-s3-replication-role"
  }

  assert {
    condition = strcontains(
      aws_kms_key.this.policy,
      "AllowSourceReplicationRoleEncrypt",
    )
    error_message = "When source_replication_role_arn is set, KMS key policy MUST contain the source-role grant"
  }

  assert {
    condition = strcontains(
      aws_s3_bucket_policy.this.policy,
      "AllowSourceReplicationRoleWrite",
    )
    error_message = "When source_replication_role_arn is set, bucket policy MUST contain the source-role write statement"
  }
}
```

- [ ] **Step 5: Rewrite the README "Apply order" section**

Open `terraform/modules/s3-replication-destination/README.md`. Find the section starting `## Apply order` (or similar). Replace with:

```markdown
## Apply order

This module supports a two-phase bootstrap because AWS validates IAM principals in KMS key policies at PUT time — passing a non-existent source role ARN would fail with `MalformedPolicyDocumentException`. The fix: `var.source_replication_role_arn` is nullable. When null, the module omits the source-role statements from both the KMS key policy and the bucket policy.

**Phase 1 (first destination apply, source role does not exist yet):**
- Caller passes `source_replication_role_arn = null`.
- KMS key, bucket, alarms, SNS topic all provision.
- KMS key policy contains only the `AllowAccountRoot` statement.
- Bucket policy contains only the `AllowSourceAccountReadBucketVersioning` statement.

**Phase 2 (source side applies):**
- Source side provisions the replication role + bucket + KMS key + replication configuration.
- Source side outputs `replication_role_arn`.

**Phase 3 (destination re-apply with the real source role ARN):**
- Caller passes `source_replication_role_arn = module.replication_source.replication_role_arn` (or via terraform_remote_state).
- KMS key policy is updated to add `AllowSourceReplicationRoleEncrypt`.
- Bucket policy is updated to add `AllowSourceReplicationRoleWrite`.

After Phase 3, ongoing changes to either side can apply in any order; the dependency direction is symmetric once both sides exist.
```

- [ ] **Step 6: Update env-stack consumers**

For each of `terraform/envs/{dev,stg,prod}/destination/main.tf`, update the `module "replication_destination"` call. Find the existing call and replace the `source_replication_role_arn` line with:

```hcl
module "replication_destination" {
  source = "../../../modules/s3-replication-destination"

  bucket_name = "exl-model-landing-dev"  # or stg / prod
  env         = "dev"  # or stg / prod
  # ... other args unchanged ...

  # Two-phase bootstrap — see s3-replication-destination README "Apply order".
  # First apply: keep source_replication_role_arn = null; the destination
  # provisions without source-role grants.
  # After the source-side has applied, replace this null with the real
  # role ARN (e.g. data.terraform_remote_state.source.outputs.replication_role_arn)
  # and re-apply.
  source_replication_role_arn = null

  source_account_id = "111111111111"  # ABSA account ID

  # ... other args unchanged ...
}
```

The ABSA account ID stays as the placeholder used in sprint 1 — Phase 2 will replace it with the real value.

- [ ] **Step 7: Commit**

```bash
git add terraform/modules/s3-replication-destination/ \
        terraform/envs/dev/destination/main.tf \
        terraform/envs/stg/destination/main.tf \
        terraform/envs/prod/destination/main.tf
git commit -m "fix(s3-replication-destination): chicken-and-egg KMS bootstrap

var.source_replication_role_arn becomes nullable (default null). When
null, KMS key policy and bucket policy omit the source-role statements
via concat() of local lists. When set, both policies include the source-
role grants.

This resolves the apply-time failure (MalformedPolicyDocumentException
on KMS key policy with non-existent IAM principal) that the sprint-1
known-gap section in README documented.

Two new test runs verify both states: null_source_role_omits_kms_grant_
in_policy and non_null_source_role_includes_kms_and_bucket_grants.

README's 'Apply order' rewritten to describe the now-supported three-
phase bootstrap. Env-stack consumers updated to pass null with a comment
block explaining the post-bootstrap re-apply.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: VPC flow-logs IAM scoping fix

**Files:**
- Modify: `terraform/modules/landing-zone/security.tf`

The flow-logs IAM role policy currently has two bugs: missing `logs:CreateLogGroup` action, and `logs:DescribeLogGroups` scoped to the log group ARN (the action requires `Resource: *`).

- [ ] **Step 1: Edit the flow-logs IAM policy**

Open `terraform/modules/landing-zone/security.tf`. Find the existing `aws_iam_role_policy.flow_logs` resource:

```hcl
resource "aws_iam_role_policy" "flow_logs" {
  name = "${local.name_prefix}-flow-logs-policy"
  role = aws_iam_role.flow_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
      ]
      Resource = "${aws_cloudwatch_log_group.flow_logs.arn}:*"
    }]
  })
}
```

Replace with:

```hcl
resource "aws_iam_role_policy" "flow_logs" {
  name = "${local.name_prefix}-flow-logs-policy"
  role = aws_iam_role.flow_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "WriteFlowLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams",
        ]
        Resource = "${aws_cloudwatch_log_group.flow_logs.arn}:*"
      },
      {
        Sid      = "DescribeLogGroups"
        Effect   = "Allow"
        Action   = "logs:DescribeLogGroups"
        Resource = "*"
      },
    ]
  })
}
```

Two changes:
1. Added `logs:CreateLogGroup` to the action list (some flow log delivery flows require it for log group provisioning).
2. Split `logs:DescribeLogGroups` into a separate statement with `Resource: *` because that action does not accept a resource-level scope. Keeping it in the original statement would silently fail at apply time.

- [ ] **Step 2: Commit**

```bash
git add terraform/modules/landing-zone/security.tf
git commit -m "fix(landing-zone): VPC flow-logs IAM scoping

Two bugs in aws_iam_role_policy.flow_logs:

1. Missing logs:CreateLogGroup action. VPC Flow Logs delivery to
   CloudWatch Logs requires this when the destination log group is
   first created or recreated.

2. logs:DescribeLogGroups was scoped to \${log_group_arn}:* — the
   DescribeLogGroups action does not accept resource-level scoping
   and rejects any resource other than '*'. Split into a separate
   statement with Resource = '*' so the role gets the API permission
   without losing the resource-level scope on the other actions.

Plan-validate doesn't catch this; the bug surfaces at apply time as a
permission failure on flow-log delivery. Found by sprint-1 final code
review (issue I4).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: CI matrix update + final integration check + PR archive

**Files:**
- Modify: `.github/workflows/terraform-validate.yml`
- Create: `docs/superpowers/pull-requests/phase-1-sprint-2.md`

- [ ] **Step 1: Add the 2 new modules to the CI validate-modules matrix**

Open `.github/workflows/terraform-validate.yml`. Find the `validate-modules` job's matrix:

```yaml
matrix:
  module:
    - landing-zone
    - s3-replication-source
    - s3-replication-destination
```

Replace with:

```yaml
matrix:
  module:
    - landing-zone
    - s3-replication-source
    - s3-replication-destination
    - kms-hierarchy
    - iam-federation
```

The `validate-stacks` matrix is unchanged — the env stacks and bootstrap stacks haven't moved.

- [ ] **Step 2: Verify YAML still parses**

```bash
cd C:/Vishnu/Claude/absa-exl-platform
python -c "import yaml; yaml.safe_load(open('.github/workflows/terraform-validate.yml'))"
```

Expected: no output (valid YAML). If `python` not available, try `python3` or `py`. If none, skip — CI will catch syntax errors on first push.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/terraform-validate.yml
git commit -m "ci: add kms-hierarchy and iam-federation to validate-modules matrix

CI's validate-modules matrix now covers all 5 modules: landing-zone,
s3-replication-source, s3-replication-destination, kms-hierarchy,
iam-federation. Each matrix leg runs terraform init -backend=false +
terraform validate + terraform test against the module.

The validate-stacks matrix is unchanged; env stacks and bootstrap
stacks pick up the module changes automatically since they reference
the modules by relative path.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 4: Run final integration verifications**

```bash
cd C:/Vishnu/Claude/absa-exl-platform

# Pre-commit on the whole tree (terraform-binary-dependent hooks may fail on machines without terraform)
pre-commit run --all-files 2>&1 | tail -30

# Confirm the commit log on this branch
git log --oneline phase-1/foundation-kickoff..HEAD

# Confirm clean working tree
git status
```

Expected outputs:
- pre-commit: trim-trailing-whitespace, end-of-file-fixer, yaml-check, large-file, secret-detect, gitleaks all pass; terraform_validate / tflint / tfsec may fail if the binaries aren't on PATH (acceptable — CI handles)
- `git log` shows ~7-8 task commits since `phase-1/foundation-kickoff`
- `git status` shows clean tree (untracked `CLAUDE_CODE_BRIEF.md` and `.pptx` are pre-existing and intentional)

- [ ] **Step 5: Write the sprint-2 PR body archive**

The repo has no GitHub remote yet (engagement lead will configure one). Archive the PR body so it can be copy-pasted later. Save to `docs/superpowers/pull-requests/phase-1-sprint-2.md`:

```markdown
## Summary

Phase 1 sprint 2 — close-out of the Phase 1 foundation. Builds on the
engagement-lead checkpoint PR (`phase-1/foundation-kickoff`).

- **kms-hierarchy module** (new) — audit-evidence-grade CMKs:
  cloudtrail-bucket-key, flow-logs-cw-key, plus a Phase 2 placeholder
  output for the manifest-signing key. Per-data-class keys (S3 source /
  destination) remain in their owning modules per ADR-0005.
- **iam-federation module** (new) — 4 SAML workload roles
  (engineer / operator / readonly / break-glass with MFA) plus GitHub
  OIDC ci-deploy role with strict `sub` condition restricting to
  configured branches.
- **Account-singleton refactor** — password policy, GuardDuty, Security
  Hub + foundational standard moved from `landing-zone` to
  `account-bootstrap` (closes the sprint-1 known-gap deferral).
- **CloudTrail SSE-KMS upgrade** — replaces interim AES256 with the
  cloudtrail-bucket-key from kms-hierarchy.
- **CloudTrail observability** — events stream to a CW Log group with
  365-day retention, encrypted by flow-logs-cw-key. 6 CIS-Benchmark v3
  metric filters + alarms route to a per-env `${env}-security-alerts`
  SNS topic (no subscriptions in module).
- **Destination KMS chicken-and-egg fix** — `source_replication_role_arn`
  becomes nullable; KMS / bucket policy statements are conditional via
  `concat()` of `local` lists. Resolves apply-time
  MalformedPolicyDocumentException on the first destination apply.
- **VPC flow-logs IAM scoping fix** — adds `logs:CreateLogGroup`, splits
  `logs:DescribeLogGroups` into a separate statement with `Resource = "*"`
  so the action doesn't get rejected at apply time.

## Architecture decisions

- ADR-0005 — kms-hierarchy module owns audit-evidence keys only, not all
  platform CMKs.

## Test plan

- [ ] CI matrix green: fmt, validate-modules (5 modules now), validate-
      stacks (9 stacks), tflint, tfsec, checkov, gitleaks.
- [ ] Engagement lead reviews ADR-0005.
- [ ] EXL InfoSec reviews iam-federation OIDC trust policy strictness.
- [ ] ABSA InfoSec reviews kms-hierarchy key policies (CloudTrail
      `aws:SourceArn` + CW Logs `EncryptionContext`).

## Out of scope (intentional)

- Real `terraform apply` against AWS — Phase 2 with account credentials.
- Phase 2 ADR for generator runtime dual-mode (locked but unwritten).
- Synthetic data generator for ABSA dev/stg buckets — Phase 2.
- Pipeline Factory, Code Intake, Registry — Phase 2.

## Open items for the engagement lead

1. Replace placeholder ABSA Identity Center SAML provider ARN in
   `terraform/account-bootstrap/exl-{env}/main.tf` before first apply.
2. Confirm `github_org_slash_repo = "absa-group/absa-exl-platform"`.
3. Confirm CloudWatch alarm period / evaluation defaults vs security
   ops preferences.
4. Provide subscriber addresses for `${env}-security-alerts` SNS topic.
5. Verify GitHub Actions OIDC root CA thumbprint in
   `terraform/modules/iam-federation/main.tf` is current.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

- [ ] **Step 6: Commit the PR archive**

```bash
mkdir -p docs/superpowers/pull-requests
git add docs/superpowers/pull-requests/phase-1-sprint-2.md
git commit -m "docs: phase 1 sprint 2 PR body archived for engagement-lead use

Repo has no GitHub remote yet. When the engagement lead configures the
remote, the body of the sprint-2 follow-up PR is in this file ready to
paste into:
  gh pr create --title \"Phase 1 sprint 2 — Foundation close-out\" \\
               --base phase-1/foundation-kickoff \\
               --head phase-1/sprint-2 \\
               --body-file docs/superpowers/pull-requests/phase-1-sprint-2.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 7: Hand-off summary**

Final report includes:
- Branch name (`phase-1/sprint-2`)
- HEAD commit SHA
- Total commit count since branch point
- PR archive path
- Engagement-lead next steps (configure remote → push branch → open PR using the archived body)

The plan terminates here. Any further work belongs in Phase 2.

---

## Open follow-up items (out of this plan but tracked)

These items are correctly out of sprint 2's scope and deferred per the spec:

1. **Phase 2 ADR-0006** — generator runtime dual-mode (locked in sprint-1 brainstorm Q5; ADR not written until Pipeline Factory begins).
2. **Synthetic data generator** — needed for ABSA dev/stg source buckets to receive non-real data; Phase 2 dependency.
3. **Real `terraform apply`** — Phase 2 with AWS credentials.
4. **Phase 2 IAM permissions test** — once Phase 2 has account credentials, the apply-time IAM behavior of flow-logs (the Task 7 fix) will be confirmed end-to-end.
5. **Compliance control matrix expansion** — add rows for the new metric-filter alarms when Phase 4 observability work begins.
