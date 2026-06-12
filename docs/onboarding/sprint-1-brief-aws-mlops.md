# Sprint 1 Brief — AWS / MLOps Engineer

**Sprint 1: Mon Jun 15 → Fri Jun 26, 2026 · Your load: 5.0 effort-days**

## Your mission on this program

You own everything that runs on real AWS. The Terraform for the whole
platform already exists (modules + per-env stacks) but has only ever been
applied against LocalStack. Across Sprints 2–6 you take it to real accounts:
account bootstrap, landing zone, the KMS signing foundation, the registry
API on Lambda, S3 replication to ABSA, and then the ML compute layer (Step
Functions + the D04 compute decision). From Sprint 9 you drop to per-model
pipeline configs as Group 2 scales out.

Sprint 1 is **preparation under uncertainty**: ABSA hasn't delivered account
IDs yet, so you get fluent in the codebase and stage everything so that the
day the IDs arrive, `terraform apply` is a same-day event, not a two-week
discovery.

## Sprint 1 outcome (your slice of the sprint goal)

> You can explain every Terraform module's purpose and inputs. tfvars
> templates exist for all three EXL accounts. The state-backend design is
> written. Nothing waits on you when account IDs land.

## Your tasks

| ID | Task | Est | Acceptance |
|---|---|---|---|
| T-0101 | Clone repo, `uv sync`, full test suite green locally | 0.5 | 278 tests pass |
| T-0105 | `make demo` green locally | 0.5 | LocalStack chain exits 0 — this is the system you'll deploy for real |
| T-0301 | Module/stack review + gap notes | 2.0 | Written gap-notes doc: every module/stack reviewed for real-AWS readiness (hardcodes, missing variables, LocalStack-isms, region assumptions) |
| T-0302 | tfvars templates per env | 1.0 | `exl-dev/stg/prod` tfvars skeletons with TODO markers for the account-ID-shaped holes |
| T-0303 | State backend design | 1.0 | Doc: S3 state bucket + DynamoDB lock table per account, naming, bootstrap ordering (the chicken-and-egg of who creates the state bucket) |

## Suggested day-by-day

| Day | Plan |
|---|---|
| Mon 15 | Sprint planning (AM). T-0101 env setup. |
| Tue 16 | Architecture walkthrough (AM, TL hosts). T-0105 `make demo` — watch what the Terraform in `infra/localstack/` does; that's the shape of the real thing. |
| Wed 17 | T-0301 part 1: `terraform/modules/` — landing-zone, account-bootstrap pattern, s3-replication pair, kms-hierarchy, iam-federation. |
| Thu 18 | T-0301 part 2: signing-foundation (read [ADR-0009](../adr/0009-signing-foundation-topology.md) alongside), pipeline-registry, per-env stacks. Join the Jenkins auth-path session (PM, with DevOps + TL) — the decision shapes your trust-policy work in S2. |
| Fri 19 | T-0301 wrap: write the gap-notes doc, PR it. |
| Mon 22 | T-0302 tfvars templates for the three accounts. |
| Tue 23 | T-0303 state backend design doc. |
| Wed 24 | Review ADR-0011 amendment; sketch the `identity_provider` trust-policy variant you'll build in S2 (T-0309). |
| Thu 25 | Prep S2: dry-run the account-bootstrap apply sequence on the sandbox account; write the runbook-style checklist. |
| Fri 26 | Sprint review: walk the team through the gap notes + apply plan. Retro. |

## Day-1 access checklist

- [ ] AWS sandbox account (admin or PowerUser) for dry-runs
- [ ] GitHub repo write access
- [ ] Terraform 1.9.5 + AWS CLI v2 locally
- [ ] Docker Desktop (for `make demo`)

## Who depends on you / who you depend on

- **You depend on DevOps' T-0202** (Jenkins auth path) before writing the
  signing-foundation trust policy in S2 — attend Thursday's decision session.
- **You depend on ABSA** for account IDs (DEP-01, first impact S2/T-0304).
  You're insulated this sprint by design; flag at standup if the ask-list
  (TL sends it Wed) gets no response by sprint end.
- **Everyone depends on your S2-S4 chain**: bootstrap → signing foundation →
  registry-on-Lambda → replication. Your gap notes de-risk all of it.

## Reading list (in order)

1. [docs/technical-overview.md](../technical-overview.md) — the system end-to-end
2. [ADR-0004](../adr/0004-account-topology-1-absa-3-exl.md) — account topology
3. [ADR-0009](../adr/0009-signing-foundation-topology.md) + [ADR-0003](../adr/0003-manifest-signing-kms-asymmetric.md) — the signing trust model you'll re-anchor for Jenkins
4. [ADR-0001](../adr/0001-data-movement-s3-replication.md) + [ADR-0002](../adr/0002-cross-account-iac-dual-module-split.md) — replication + dual-module pattern
5. [docs/phase-3-closeout.md](../phase-3-closeout.md) — §"Blocked on ABSA" and §"Not blocked" = your S2-S4 backlog rationale

## What's next for you (S2–S4 preview)

- **S2 (8.0d — your heaviest):** account-bootstrap apply (when IDs land), state backends, landing-zone dev, `identity_provider` variable in signing-foundation, IP whitelisting coordination.
- **S3:** network connectivity implementation, signing stack live on exl-prod, publish-key, Lambda packaging for registry-api starts, D04 compute-platform ADR.
- **S4:** registry on APIGW+Lambda+DynamoDB in dev→prod, replication modules applied, cross-account verify with ABSA's principal.
