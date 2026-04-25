## Summary

Phase 1 foundation artifact for the engagement-lead checkpoint at
`CLAUDE_CODE_BRIEF.md` §12 step 7.

- Repo scaffold + 12 stub READMEs for unbuilt modules / dirs
- Architecture document, four ADRs (data movement, dual-module split, KMS
  signing, account topology), compliance control matrix
- Three Terraform modules: `landing-zone`, `s3-replication-source`,
  `s3-replication-destination` — each with plan-validate `terraform test`
- Six env stacks (dev/stg/prod × source/destination) and three
  account-bootstrap stacks
- GitHub Actions workflow: fmt, validate per module, validate per stack,
  tflint, tfsec, checkov, gitleaks

## Architecture

- Pattern Z topology: 1 ABSA account (3 env-suffixed source buckets) +
  3 EXL accounts (one destination each).
- S3 cross-account replication for bulk data; PrivateLink reserved for
  control-plane APIs.
- Object-lock compliance mode on both sides; per-env tiered retention.
- KMS asymmetric for manifest signing (Phase 2).

## Decisions captured in ADRs

- ADR-0001 — Data movement via S3 replication, not PrivateLink
- ADR-0002 — Cross-account IaC dual-module split
- ADR-0003 — Manifest signing via AWS KMS asymmetric keys
- ADR-0004 — Account topology — 1 ABSA + 3 EXL with Pattern Z

## Test plan

- [ ] CI matrix green: fmt, validate-modules, validate-stacks, tflint, tfsec, checkov, gitleaks
- [ ] Engagement lead reviews architecture.md + 4 ADRs
- [ ] Compliance reviewer signs off on control-matrix.md Phase 1 rows
- [ ] ABSA Cloud Platform team reviews replication-contract.md
- [ ] Engagement lead confirms: Terraform vs OpenTofu, prod retention years, paging vendor

## Out of scope (intentional)

- Real `terraform apply` — Phase 2 with account credentials
- KMS hierarchy + IAM federation modules — Phase 1 next sprint
- Pipeline Factory, Code Intake, Registry, Scoring Engine, PIR Engine —
  Phases 2-4

🤖 Generated with [Claude Code](https://claude.com/claude-code)
