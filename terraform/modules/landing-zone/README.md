# `landing-zone` Terraform module

Workload-account landing zone for an EXL env account. Provisions a 3-tier VPC, NAT gateways, Transit Gateway attachment, VPC flow logs, GuardDuty, Security Hub, account password policy, and an env-scoped permissions boundary.

This module is **not** an organisation-level landing zone. It does not manage AWS Organizations resources; account creation is owned by ABSA's central platform team via Control Tower / AFT. See [ADR-0004](../../../docs/adr/0004-account-topology-1-absa-3-exl.md) for the topology rationale.

## Usage

```hcl
module "landing_zone" {
  source = "../../modules/landing-zone"

  env                = "dev"
  region             = "af-south-1"
  vpc_cidr           = "10.40.0.0/20"
  availability_zones = 3
  transit_gateway_id = "tgw-0123456789abcdef0"

  enable_guardduty    = true
  enable_security_hub = true
  flow_logs_retention_days = 30

  tags = {
    cost_center = "ml-platform"
  }
}
```

## CIDR allocation convention

| Env | CIDR | Subnet pattern (cidrsubnet 4-bit newbits) |
| --- | --- | --- |
| dev | `10.40.0.0/20` | public 0-2, private 4-6, data 8-10 |
| stg | `10.40.16.0/20` | public 0-2, private 4-6, data 8-10 |
| prod | `10.40.32.0/20` | public 0-2, private 4-6, data 8-10 |

## NAT gateway pattern

Prod uses one NAT gateway per AZ for high availability (3 NATs in 3 AZs). Dev and stg share a single NAT gateway in the first AZ for cost. Verified by the `non_prod_uses_single_nat_gateway` and `prod_uses_one_nat_gateway_per_az` tests.

## Data subnet isolation

The data tier route table is intentionally empty — data-tier resources have no egress route, not even via NAT. This forces stateful workloads (RDS, ElastiCache, S3 access) to use VPC endpoints. If you add a data-tier consumer that needs to reach AWS service APIs, provision the corresponding gateway endpoint (S3, DynamoDB) or interface endpoint (Secrets Manager, KMS, etc.) in the env stack — not in this module.

## Permissions boundary

The module creates an env-scoped permissions boundary policy at `arn:aws:iam::<account>:policy/<env>-env-scoped-boundary`. Attach this to every workload role you create in the env. The boundary denies any action on a resource tagged `env=<other>` and denies IAM-user mutation entirely. See [ADR-0004 §Compensating controls](../../../docs/adr/0004-account-topology-1-absa-3-exl.md) for context.

## Known gap — account-singleton resources

This module currently provisions three resources that are AWS-account singletons: `aws_iam_account_password_policy`, `aws_securityhub_account`, and `aws_guardduty_detector`. Calling this module more than once in the same AWS account will produce conflicting Terraform state on these singletons.

For Phase 1, this module is called exactly once per EXL account (one of `exl-dev` / `exl-stg` / `exl-prod`), so the conflict cannot occur in practice. However, the architectural correctness fix is to move these resources into `terraform/account-bootstrap/exl-{env}/` alongside CloudTrail, where account-singleton ownership is explicit. This refactor is scheduled for Phase 1 sprint 2 alongside the `kms-hierarchy` and `iam-federation` modules.

Until then: do NOT instantiate this module twice in the same AWS account.

## Inputs

See `variables.tf` for the authoritative list and validation rules. Required inputs without defaults: `env`, `region`, `vpc_cidr`, `transit_gateway_id`, `tags`.

## Outputs

See `outputs.tf`. Notable: `vpc_id`, `private_subnet_ids`, `data_subnet_ids`, `permissions_boundary_arn`.

## Tests

Run `terraform test` from the module directory. All tests are plan-validate — no apply, no AWS credentials required.

## Compliance mapping

| Control | Where |
| --- | --- |
| ISO 27001 A.12.4.1 — event logging | VPC flow logs, GuardDuty, Security Hub |
| SOC 2 CC6.1 — logical access | env-scoped permissions boundary |
| ABSA GMRMG — segregation of envs | non-overlapping CIDRs + permissions boundary |
