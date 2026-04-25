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
