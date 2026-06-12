# Sprint 1 Brief — Tech Lead

**Sprint 1: Mon Jun 15 → Fri Jun 26, 2026 · Your load: 4.5 effort-days (cap 6 — you split with program management)**

## Your mission on this program

You built the platform; now you scale yourself through four engineers. Your
job shifts from writing code to three things: (1) **transfer context fast** —
the team's week-1 productivity is a direct function of your walkthrough and
the docs trail; (2) **make/record decisions** — ADR amendments, design
reviews, the D01-D09 open-decision register; (3) **chase ABSA relentlessly**
— every top program risk is an ABSA dependency, and you own the ask-list.
You also stay the platform-code owner: PR reviews keep the chain-of-custody
invariants intact.

The two spikes where you're the bottleneck: S8 (Group 1 sign-off meeting)
and S12 (Group 2 sign-off + handover). Protect those sprints.

## Sprint 1 outcome (your slice of the sprint goal)

> Team fully onboarded and self-sufficient on the repo. Board live. ABSA
> ask-list sent with a weekly chase cadence. Jenkins identity decision made
> and recorded in ADR-0011.

## Your tasks

| ID | Task | Est | Acceptance |
|---|---|---|---|
| T-0109 | Host architecture walkthrough | 1.0 | All 4 engineers attended; recorded for future joiners; covers chain-of-custody, repo tour, ADR index |
| T-0110 | Stand up Jira/ADO board; import the backlog | 1.0 | EPIC/Story/Task tree from `docs/absa-exl-agile-plan.xlsx` live; sprint 1 populated |
| T-0111 | Publish Definition of Done + PR workflow | 0.5 | One page; in repo; team acknowledged |
| T-0112 | Ceremony calendar | 0.5 | Standup/planning/review/retro invites sent |
| T-0113 | Send 7-item ABSA ask-list | 0.5 | Sent to named SPOC; items: account IDs, IAM ARNs, SAS runtime, PIR API, data movement, CAB/IVU, network choice (+model docs DEP-08) |
| T-0114 | Weekly dependency-chase cadence | 0.5 | Recurring slot + escalation path agreed with ABSA SPOC |
| T-0203 | Amend ADR-0011 with Jenkins identity decision | 0.5 | The standalone-Jenkins auth path (from DevOps' T-0202) recorded; status updated |

## Suggested day-by-day

| Day | Plan |
|---|---|
| Mon 15 | Run sprint planning (AM). T-0110 board import (PM). |
| Tue 16 | T-0109 walkthrough (AM — record it). T-0111 DoD doc (PM). |
| Wed 17 | T-0112 ceremony calendar. T-0113 ABSA ask-list out the door. **Do not let this slip past Wednesday** — DEP-01 (account IDs) gates the AWS engineer from S2 Monday. |
| Thu 18 | T-0202 support: Jenkins auth-path decision session with DevOps + AWS engineer. T-0203 draft the ADR amendment. |
| Fri 19 | T-0114 dependency cadence agreed. Review week-1 PRs (gap notes, topology doc). |
| Mon 22 | PR reviews: data dictionary template, SAS checker gap notes. Merge T-0203. |
| Tue 23 | Dictionary template review session (with DE + SAS). Unblock anything from standup. |
| Wed 24 | Review tfvars + state-backend design (AWS engineer). First ABSA chase call if ask-list unanswered. |
| Thu 25 | Slack for whatever the week surfaced. S2 planning prep: confirm account-ID status determines S2 scope variant (with/without bootstrap apply). |
| Fri 26 | Facilitate sprint review (each engineer demos) + retro. |

## The ask-list (send Wednesday, verbatim items)

1. AWS account IDs — 3 EXL accounts + ABSA receiving account *(gates S2)*
2. IAM principal ARNs needing `kms:Verify` / `s3:GetObject` *(gates S4)*
3. SAS runtime Docker image + license terms *(gates S3 real linting)*
4. PIR system API/feed contract *(gates S5)*
5. Data-movement decision: S3 replication vs SFTP *(gates S4)*
6. CAB / IVU API contract *(gates S5 change workflow)*
7. Network connectivity choice: peering / TGW / PrivateLink *(gates S3)*
8. Approved model docs + code + benchmarks, models 1-2 first *(gates S2 SAS/DE work)*

## Who depends on you

Everyone, structurally: reviews, decisions, ABSA. Specifically this sprint —
DevOps needs T-0203 review same-day after their T-0202; the team needs the
board (T-0110) before planning ends Monday.

## What's next for you (S2+ preview)

- **S2:** light by design (0d planned) — absorb review load, chase ABSA, support Jenkins debugging.
- **S3:** docs sweep at cutover (ADR-0003/0009 finals, control-matrix → Live).
- **S4:** SigV4 registry smoke test (T-0316).
- **S5:** CAB/IVU → registry approve-route mapping (D02, 2d).
- **S6:** dress-rehearsal orchestration (2d).
- **S8:** PIR sign-off meeting — THE program gate.
- **S12:** Group 2 sign-off + handover sessions + go-live checklist (6d — at cap).
