# `absa-handoff` — ABSA-side baseline (NOT EXL-managed)

This directory is intentionally empty of Terraform. ABSA's central
platform team owns account-level resources in their AWS account.
This README documents what EXL expects to be in place there before
the source-side modules can be applied.

## Required ABSA-side baseline

| Resource | Owned by | Purpose |
| --- | --- | --- |
| AWS Organizations master account | ABSA central platform | Org-level governance for the ABSA-handoff account |
| Service Control Policies | ABSA central platform | Restrict workload-account capabilities |
| CloudTrail organisation trail | ABSA central platform | Captures all S3 / KMS / IAM events in the handoff account, including replication-role activity |
| GuardDuty master detector | ABSA central platform | Detects anomalous activity on the handoff buckets |
| IAM Identity Center / SSO federation | ABSA central platform | EXL Industrialization Team access |
| Account-level password policy and root-MFA enforcement | ABSA central platform | Baseline account hygiene |

## EXL footprint inside the ABSA account

EXL Terraform (the `s3-replication-source` module called from
`terraform/envs/{env}/source/`) deploys these resources only:

- 3 source buckets (`absa-model-handoff-{dev,stg,prod}`)
- 3 KMS CMKs (`alias/handoff-{dev,stg,prod}`)
- 3 IAM roles (`{env}-s3-replication-role`)
- 3 S3 bucket replication configurations

EXL does NOT manage Organizations, SCPs, account-level CloudTrail, GuardDuty,
or the account password policy on the ABSA side.

## Verification before first source-side apply

The engagement lead should confirm with ABSA's central platform team that
all six baseline rows above are in place before running `terraform apply`
in `terraform/envs/{env}/source/` for the first time. The `replication-contract.md`
treats this baseline as an assumption.
