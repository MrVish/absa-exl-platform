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

## Break-glass operational caveat

The break-glass role's trust policy requires `aws:MultiFactorAuthPresent = true` via the `Bool` operator. This depends on ABSA's Identity Center SAML attribute mapping releasing the MFA attribute in assertions for MFA-authenticated users. If the attribute is not released, the role will be silently unusable — every AssumeRole attempt is denied with no clear root-cause indication.

**Pre-Phase-2 verification:** confirm with ABSA's central platform team that Identity Center includes the MFA attribute in SAML assertion context. The alternative operator `BoolIfExists` would allow assumption when the attribute is absent (a security regression), so `Bool` is the correct choice — but the SAML attribute release must be verified.

## GitHub OIDC trust policy

The ci-deploy role's trust policy uses both:
- `StringEquals` on `aud = sts.amazonaws.com` — every OIDC token must be intended for STS
- `StringLike` on `sub` matching the configured `repo:${org}/${repo}:ref:refs/heads/${branch}` patterns — restricts which branches' workflows can assume the role

This combination prevents the "any-repo can assume" vulnerability that has caused real incidents in the wild. Forks of the repository, pull-request workflows, and tag pushes will all fail to match the `sub` condition.

## GitHub OIDC root CA thumbprint

Stored as `local.github_oidc_thumbprint` in `main.tf`. Currently `6938fd4d98bab03faadb97b34396831e3780aea1` (updated 2023). GitHub rotates this CA periodically — verify the current value against [GitHub's OIDC documentation](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services) before first apply. AWS provider 5.36+ ignores thumbprint_list at runtime for JWKS-backed providers; the field is required by the resource schema but not load-bearing for security.

## ci-deploy IAM mutation surface — known limitation

The ci-deploy role has `Allow * on *` baseline with explicit Deny on credential mutation, key destruction, and audit evasion (see `oidc.tf`). The deny list does NOT include `iam:PutRolePolicy`, `iam:AttachRolePolicy`, or `iam:PassRole`, because legitimate Terraform role-management operations require them. The permissions boundary attached to ci-deploy does NOT itself prevent cross-role policy mutation within the env.

**Implication:** ci-deploy can mutate the inline / attached policies of any role in this env, including platform_engineer, platform_operator, and break_glass. A compromised CI workflow could grant itself or another role broader effective permissions before re-running.

**Mitigation in Phase 1:** OIDC trust scoping (only specific branches in the configured repo can assume ci-deploy) limits the attack surface to insider compromise of those branches.

**Phase 2 work:** review whether to add a targeted Allow on `iam:PassRole` with service-principal conditions, paired with broader denies on cross-role policy mutation. Tracked as an open item.

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
