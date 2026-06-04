# `prod/signing` Terraform stack

Composes [`modules/signing-foundation`](../../../modules/signing-foundation) for the `prod` environment in the `exl-prod` AWS account.

## Prerequisites

This stack consumes outputs from two upstream Terraform stacks:

1. **`account-bootstrap/exl-prod`** — provides `github_oidc_provider_arn` (the GitHub Actions OIDC IdP in the exl-prod account) and `platform_engineer_role_arn` (typically the `key_admin_principals` value).
2. **`envs/prod/registry`** — provides `writer_policy_arn` (the IAM policy granting `execute-api:Invoke` on the registry API).

Both prerequisite stacks must be applied before this stack. The values flow through this stack via `terraform.tfvars`; copy `terraform.tfvars.example` to `terraform.tfvars` and populate by running `terraform output` against each producer.

## Apply

```bash
cd terraform/envs/prod/signing
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with the real ARNs from the prerequisite stacks.
terraform init
terraform plan
terraform apply
```

## Outputs

This stack does not currently expose outputs (the module's outputs are accessed via `terraform output -module=signing` if needed). If a future stack needs to consume the CMK ARN or signer/registrar role ARNs, add an `outputs.tf` here that re-exposes them.

## Related

- [`modules/signing-foundation/README.md`](../../../modules/signing-foundation/README.md) — full input/output reference.
- [ADR-0009](../../../../docs/adr/0009-signing-foundation-topology.md) — design rationale (lands in T12).
