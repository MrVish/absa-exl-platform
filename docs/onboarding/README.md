# Kickoff Briefs - 9-Person Team (grouped by role)

**Sprint 1: Mon Jun 15 -> Fri Jun 26, 2026.** One brief per role group. Generated from [`docs/absa-exl-agile-plan.xlsx`](../absa-exl-agile-plan.xlsx) via `scripts/build_kickoff_briefs.py`, so they never drift from the backlog.

| Brief | Seats | S1 load |
|---|---|---|
| [AWS / MLOps Engineering](role-brief-aws-mlops.md) | AWS, AWS2 | 6.0 d |
| [SAS Development](role-brief-sas.md) | SAS, SAS2, SAS3 | 7.5 d |
| [Data Engineering](role-brief-data-engineer.md) | DE | 4.0 d |
| [DevOps Engineering](role-brief-devops.md) | DevOps | 5.5 d |
| [Tech Lead (Vishnu)](role-brief-tech-lead.md) | TL | 4.5 d |

## Team at a glance

| Seat | Role | On team from |
|---|---|---|
| AWS | AWS/MLOps Eng #1 - Foundation & Infra | Sprint 1 |
| AWS2 | AWS/MLOps Eng #2 - Platform, Compute & MLOps | Sprint 1 |
| DE | Data Engineer | Sprint 1 |
| SAS | SAS Developer #1 (Model 1 / Group 2) | Sprint 1 |
| SAS2 | SAS Developer #2 (Model 2 / Group 2) | Sprint 1 |
| SAS3 | SAS Developer #3 (Group 2, from S8) | Sprint 8 |
| DevOps | DevOps Engineer | Sprint 1 |
| TL | Tech Lead (Vishnu) | Sprint 1 |

## Is the plan achievable? (audited)

`scripts/audit_agile_plan.py` checks the plan for feasibility, not just capacity. As of the last run it **passes**:

- **Dependency ordering** - no task depends on work scheduled in a later sprint (no impossible orderings).
- **Capacity** - no role exceeds its cap in any sprint. Peak engineer load is DevOps S2 at 88%; peak overall is TL at 92% in the two sign-off sprints (S8, S12).
- **Sprint 1 is fully unblocked** - zero ABSA-dependent tasks land in S1, so the team is productive from day one regardless of ABSA timing.
- **Model coverage** - all 10 models have complete onboarding-stage coverage; all 10 are live by S11.
- **Integrity** - every task maps to a real story and epic; no empty stories.

Re-run any time after editing the plan: `uv run --with openpyxl python scripts/audit_agile_plan.py`.

## The one sentence that matters

The platform (registry, pipeline factory, signer, code intake, LocalStack demo) is **already built and regression-tested** - your job is to put it on real AWS, swap CI to Jenkins, onboard 10 SAS models through it, and run it in production. Sprint 1 is about getting productive and making the first structural decisions.
