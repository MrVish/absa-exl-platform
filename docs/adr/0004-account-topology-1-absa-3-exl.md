# ADR-0004: Account topology — 1 ABSA + 3 EXL with Pattern Z replication

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-04-25 |
| Deciders | Engagement lead, EXL Platform Engineering |
| Consulted | ABSA Cloud Platform team |

## Context

Two facts shaped the topology decision:

1. ABSA allocates **one AWS account** for the engagement on its side. Multiple ABSA accounts were not on offer.
2. EXL's internal standard is **three AWS accounts** (dev, stg, prod) for any production workload. Single-account variants are only used for proof-of-concept work.

Given the asymmetry, three replication patterns were considered:

- **Pattern X**: ABSA single account → `exl-prod` only. Dev / stg use synthetic data generated inside EXL.
- **Pattern Y**: ABSA single account, single source bucket → all three EXL envs.
- **Pattern Z**: ABSA single account, three env-suffixed source buckets → matching EXL env each.

Pattern Z was chosen.

## Decision

The platform runs across **four AWS accounts** total:

| Account | Owner | Purpose |
| --- | --- | --- |
| `absa-handoff` (single account) | ABSA | Hosts three env-suffixed source buckets: `absa-model-handoff-dev`, `absa-model-handoff-stg`, `absa-model-handoff-prod`. Each has its own per-env KMS CMK and replication role. |
| `exl-dev` | EXL | Dev landing-zone + destination bucket. Receives replicas from `absa-model-handoff-dev` only. |
| `exl-stg` | EXL | Stg landing-zone + destination bucket. Receives replicas from `absa-model-handoff-stg` only. |
| `exl-prod` | EXL | Prod landing-zone + destination bucket. Receives replicas from `absa-model-handoff-prod` only. |

Replication is **strictly env-symmetric**: each ABSA source bucket has exactly one replication rule, pointing to its matching EXL env account. There is no cross-env replication.

ABSA's account-level controls (Organisation, SCPs, CloudTrail organisation trail, GuardDuty master detector) are owned by ABSA's central platform team. EXL's footprint inside the ABSA account is bounded to: the three source buckets, three KMS CMKs, three replication roles, and the replication configurations on each bucket. Anything else in the ABSA account is out of scope for this engagement.

## Consequences

### Positive

- Strong env isolation on the EXL side, courtesy of three separate AWS accounts. SR 11-7 and ABSA GMRMG audit narratives are simple.
- Env isolation on the ABSA side is preserved by per-env KMS CMKs and per-env replication roles, even though all three buckets share an account. A misrouted replication rule on `absa-model-handoff-dev` cannot decrypt prod data because the prod CMK key policy explicitly excludes the dev replication role.
- Symmetric env naming end-to-end. An object in `absa-model-handoff-stg/...` lands in `exl-stg`'s `exl-model-landing-stg/...` — the env never changes. Audit lineage is straightforward.
- Pattern Z preserves the option of using real (de-identified) data in dev or stg if ABSA ever wants to enable that. Pattern X would foreclose this without re-architecting.

### Negative

- Three replication rules and three KMS CMKs to maintain on the ABSA side. Operationally cheap; cognitively a small overhead.
- ABSA must commit to providing three buckets even if they intend to use only the prod bucket for live data. The other two would receive synthetic data populated by an EXL Phase 2 generator. This is a small ABSA-side ask but must be confirmed before Phase 2 begins.
- Cost: three KMS CMKs ($3/month combined) and three replication rules. Trivial.

## Alternatives considered

1. **Pattern X — ABSA → exl-prod only.** Rejected: dev and stg lose realistic replication-path testing. Replication-rule misconfigurations would only surface in prod, defeating the purpose of having dev / stg envs.
2. **Pattern Y — single ABSA bucket → all 3 EXL envs.** Rejected: a single source bucket means real (de-identified) data lands in dev and stg by default. POPIA's data-minimisation principle becomes harder to argue. Also, per-env replication metrics and alarms are less natural to attribute when one source feeds three sinks.
3. **Six EXL accounts (dev / stg / prod × source / destination).** Rejected: the source side is owned by ABSA, not EXL. Provisioning EXL-owned accounts on the source side would conflict with the account-allocation reality.
