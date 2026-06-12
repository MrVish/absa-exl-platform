# Sprint 1 Kickoff Briefs

One brief per person. Hand each engineer their own file on day 1.

**Sprint 1: Mon 2026-06-15 → Fri 2026-06-26** (10 working days).

| Brief | Role | Sprint 1 load |
|---|---|---|
| [sprint-1-brief-devops.md](sprint-1-brief-devops.md) | DevOps Engineer | 5.5 d |
| [sprint-1-brief-aws-mlops.md](sprint-1-brief-aws-mlops.md) | AWS / MLOps Engineer | 5.0 d |
| [sprint-1-brief-sas-developer.md](sprint-1-brief-sas-developer.md) | SAS Developer | 5.0 d |
| [sprint-1-brief-data-engineer.md](sprint-1-brief-data-engineer.md) | Data Engineer | 4.0 d |
| [sprint-1-brief-tech-lead.md](sprint-1-brief-tech-lead.md) | Tech Lead | 4.5 d |

Loads are below the 8 d/sprint capacity (6 d for TL) on purpose: the
remainder is ceremonies, reviews, reading, and slack for the unknowns every
first sprint has.

Source of truth for all task IDs: [`docs/absa-exl-agile-plan.xlsx`](../absa-exl-agile-plan.xlsx)
(Backlog sheet). If a brief and the backlog disagree, the backlog wins.

## Working agreement (applies to everyone)

- **Branch-based flow.** No direct pushes to `main`. Every change is a PR;
  CI must be green before merge. CODEOWNERS review applies.
- **Daily standup, 15 min.** What moved, what's next, what's blocked.
  A blocker older than one day gets escalated in standup, not discovered at review.
- **Definition of Done** (per task): code merged to `main`, tests green,
  docs updated if behaviour changed, acceptance criteria from the backlog met.
- **Demo on the last Friday.** Each person shows their slice of the sprint
  goal working — not slides, the actual thing.
- **Estimates are effort, not elapsed.** If a 1-day task is 3 days in, say so
  at standup — re-planning is normal; silent slippage is not.

## The one sentence that matters

The platform (registry, pipeline factory, signer, code intake, LocalStack
demo) is **already built and regression-tested** — your job in this program
is to put it on real AWS, swap CI to Jenkins, onboard 10 SAS models through
it, and run it in production. Sprint 1 is about getting you productive and
making the first structural decisions.
