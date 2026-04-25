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
