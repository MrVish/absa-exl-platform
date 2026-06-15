"""Generate role-grouped kickoff briefs from the agile plan data.

One brief per role group (AWS/MLOps, SAS, Data, DevOps, Tech Lead). Each brief's
task tables, load grid, and sprint-by-sprint focus are GENERATED from
build_agile_plan.py so the briefs can never drift from the Excel. The mission /
framing prose is hand-authored per group.

Run: `uv run --with openpyxl python scripts/build_kickoff_briefs.py`
Output: docs/onboarding/role-brief-<group>.md + README.md
"""

from __future__ import annotations

from pathlib import Path

import build_agile_plan as plan

STORY_ACC = {s[0]: s[5] for s in plan.STORIES}
STORY_TITLE = {s[0]: s[2] for s in plan.STORIES}


def s1_dates() -> str:
    s, e = plan.sprint_dates(1)
    return f"{s:%a %b %d} -> {e:%a %b %d, %Y}"


def seat_tasks(seats, sprint=None):
    out = []
    for t in plan.TASKS:
        if t[3] in seats and (sprint is None or t[4] == sprint):
            out.append(t)
    return sorted(out, key=lambda x: (x[4], x[0]))


def load_grid(seats) -> dict:
    load = {}
    for t in plan.TASKS:
        if t[3] in seats:
            load[(t[3], t[4])] = load.get((t[3], t[4]), 0.0) + t[5]
    return load


# ---- Hand-authored framing per role group ----

GROUPS = {
    "aws-mlops": {
        "file": "role-brief-aws-mlops.md",
        "title": "AWS / MLOps Engineering",
        "seats": ["AWS", "AWS2", "AWS3"],
        "mission": (
            "You are three engineers running three parallel streams so the AWS foundation - the tightest "
            "track in any single-engineer version of this plan - never becomes the bottleneck. The platform's "
            "Terraform already exists (modules + per-env stacks) but has only ever run against LocalStack; your "
            "job is to take it to real EXL accounts and operate it.\n\n"
            "- **AWS #1 - Foundation/Infra:** account bootstrap, state backends, landing zone, networking to ABSA, "
            "S3 replication, retention. The base everything else sits on.\n"
            "- **AWS #2 - Platform Services:** signing foundation (KMS), registry-on-Lambda, cross-account verify, "
            "plus the IAM least-privilege + encryption-validation security work.\n"
            "- **AWS #3 - Compute/MLOps:** the D04 compute decision, real Step Functions execution, the compute "
            "layer, EventBridge schedules, production scoring, performance, and DR.\n\n"
            "**Front-loading is deliberate:** all three of you are busy S1-S7 building the foundation, then load "
            "drops sharply. After S7, AWS #2 and AWS #3 can ramp down or redeploy to model-optimization / MLOps "
            "support - that plan is made at the S5 capacity review. The late-program slack you'll see in your grid "
            "is the buffer that absorbs a late-ABSA-account-IDs slip without moving any gate date."
        ),
        "reading": [
            "[docs/technical-overview.md](../technical-overview.md) - the system end-to-end",
            "[ADR-0004](../adr/0004-account-topology-1-absa-3-exl.md) - account topology",
            "[ADR-0009](../adr/0009-signing-foundation-topology.md) + [ADR-0003](../adr/0003-manifest-signing-kms-asymmetric.md) - signing trust model (AWS #2)",
            "[ADR-0011](../adr/0011-ci-platform-jenkins.md) - the Jenkins identity decision shapes your signing-foundation trust policy",
            "[docs/phase-3-closeout.md](../phase-3-closeout.md) - the 'Blocked on ABSA' + 'Not blocked' tables are your backlog rationale",
        ],
    },
    "sas": {
        "file": "role-brief-sas.md",
        "title": "SAS Development",
        "seats": ["SAS", "SAS2", "SAS3"],
        "mission": (
            "You own the model code - the heart of the program. Ten ABSA SAS models must be reviewed, optimized, "
            "packaged, and reconciled against ABSA's benchmark outputs, and the program's hardest gate (Group 1 "
            "sign-off, end of Sprint 8) sits on your reconciliation work.\n\n"
            "- **SAS #1 + SAS #2 (from S1):** run Group 1 models 1 and 2 **in parallel** from Sprint 2. Two people "
            "on the proof removes the bus-factor-of-one risk and means two trained reviewers before scale-out. "
            "SAS #2 also upgrades the `static_sas` checker from structural to real SAS linting (once ABSA's runtime "
            "lands).\n"
            "- **SAS #3 (from S8):** onboards in Sprint 8 (shadowing a Group 1 reconciliation) and joins the "
            "Group 2 scale-out.\n\n"
            "**Group 2 is compressed:** three of you onboard 3 models/sprint in S9-S10 and the last 2 in S11, so "
            "**all 10 models are live by the end of Sprint 11.** Sprint 12 has no new models - it's reconciliation "
            "sweep, defect closure, and knowledge transfer. The single most important quality activity across the "
            "whole program is benchmark reconciliation within agreed tolerance bands; everything else serves that."
        ),
        "reading": [
            "[ADR-0010](../adr/0010-productized-package-contract.md) - the package contract; your bible",
            "[`code-intake/README.md`](../../code-intake/README.md) - checkers, finding codes, deferred checks",
            "[`packages/credit-risk-pd/1.0.0/`](../../packages/credit-risk-pd/1.0.0/) - the worked example you clone the shape of ten times",
            "`code-intake/src/code_intake/checkers/static_sas.py` + `pir.py` - enforced vs deferred",
            "[docs/program-flow.md](../program-flow.md) - where your work sits in the 6-month arc",
        ],
    },
    "data-engineer": {
        "file": "role-brief-data-engineer.md",
        "title": "Data Engineering",
        "seats": ["DE"],
        "mission": (
            "You own the data plane solo, and you're the one role continuously engaged start to finish (~4-5 "
            "effort-days every sprint). You build the contracts that define each model's inputs, the ingestion "
            "path that validates files the moment ABSA lands them, the data-quality framework (volume bands + PSI "
            "drift), source-vs-landing reconciliation, lineage capture, retention, and the PIR integration. In "
            "steady state your DQ checks are the first thing that catches a bad scoring run - before the model "
            "ever executes.\n\n"
            "Your load is deliberately even rather than spiky: you absorb the unpredictable work (real data never "
            "behaves) and provide the data evidence for both Group 1 and Group 2 sign-off."
        ),
        "reading": [
            "[ADR-0006](../adr/0006-contract-strategy-json-schema-canonical.md) - JSON Schema + canonical JSON contract backbone",
            "`platform-contracts/src/platform_contracts/schemas/` - all three schemas, esp. `pir-mapping.schema.json`",
            "[`packages/credit-risk-pd/1.0.0/pir.yaml`](../../packages/credit-risk-pd/1.0.0/) - a real PIR file",
            "[`code-intake/README.md`](../../code-intake/README.md) - the PIR checker section (PIR00x codes)",
            "[ADR-0001](../adr/0001-data-movement-s3-replication.md) - how data moves cross-account",
        ],
    },
    "devops": {
        "file": "role-brief-devops.md",
        "title": "DevOps Engineering",
        "seats": ["DevOps"],
        "mission": (
            "You own the CI/CD layer and, later, observability and operations. EXL's standard is Jenkins, not "
            "GitHub Actions, and a standalone Jenkins is already running - your first job (S1-S3) is migrating all "
            "six CI gates onto it per ADR-0011 and retiring GHA without breaking the platform's signing guarantees. "
            "Then you own dashboards + alerting (S4-S9), and runbooks + hypercare (S11-S12).\n\n"
            "**You are the only un-doubled role,** so two sprints are deliberately your peak: **S2 (~88%, the "
            "Jenkins shared-library + no-AWS jobs crunch)** and **S6 (dashboards + dress-rehearsal ops)**. The Tech "
            "Lead pairs with you at those peaks. If those weeks slip, flag in standup early - they're the only "
            "single-person pinch points in the plan."
        ),
        "reading": [
            "[ADR-0011](../adr/0011-ci-platform-jenkins.md) - the whole migration; the Open Questions are your S1 homework",
            "[`ci/jenkins/README.md`](../../ci/jenkins/README.md) - library wiring, credentials, migration map",
            "the 5 Jenkinsfiles in [`ci/jenkins/examples/`](../../ci/jenkins/examples/) - you'll run all of them by S3",
            "[`.github/workflows/`](../../.github/workflows/) - what you're replacing; note the localstack-demo exit-code gate",
            "[docs/runbooks/localstack-demo.md](../runbooks/localstack-demo.md) - troubleshooting for the S2 port",
        ],
    },
    "tech-lead": {
        "file": "role-brief-tech-lead.md",
        "title": "Tech Lead (Vishnu)",
        "seats": ["TL"],
        "mission": (
            "You built the platform; now you scale yourself through eight people. Your job is three things: "
            "**transfer context fast** (the team's week-1 productivity is a direct function of your walkthrough), "
            "**make and record decisions** (ADR amendments, the D01-D09 register, the S5 capacity review), and "
            "**chase ABSA relentlessly** (every top program risk is an ABSA dependency). You stay the platform-code "
            "owner via PR review to keep the chain-of-custody invariants intact.\n\n"
            "Two sprints are your peak by design and should be protected: **S8 (Group 1 sign-off + audit evidence "
            "pack, ~92%)** and **S12 (Group 2 sign-off + handover + go-live, ~92%)**. Keep the sprints around them "
            "light so you can absorb slippage into the gates."
        ),
        "reading": [
            "[docs/absa-exl-agile-plan.xlsx](../absa-exl-agile-plan.xlsx) - the backlog you own and import to Jira",
            "[docs/program-flow.md](../program-flow.md) - the techno-functional narrative for ABSA",
            "all ADRs in [docs/adr/](../adr/) - you're the decision-record owner",
            "[docs/compliance/control-matrix.md](../compliance/control-matrix.md) - POPIA/SARB control mapping",
        ],
    },
}

ABSA_BLOCKERS = {
    "ABSA: account IDs": "AWS account IDs (3 EXL + ABSA receiving)",
    "ABSA: network choice": "Network connectivity decision (peering / TGW / PrivateLink)",
    "ABSA: model docs": "Approved model docs + code + benchmarks (models 1-2 first)",
    "ABSA: SAS runtime": "SAS runtime Docker image + license",
    "ABSA: IAM ARNs": "IAM principal ARNs (kms:Verify / s3:GetObject)",
    "ABSA: data movement": "Data movement decision (S3 replication vs SFTP)",
    "ABSA: PIR contract": "PIR system API/feed contract",
    "ABSA: CAB/IVU contract": "CAB / IVU API contract",
}


def fmt_seat(role: str) -> str:
    return f"{role} ({plan.ROLE_NAMES[role]})"


def gen_brief(key: str, g: dict) -> str:
    seats = g["seats"]
    multi = len(seats) > 1
    L = []
    L.append(f"# Role Brief - {g['title']}")
    L.append("")
    L.append(f"**Sprint 1: {s1_dates()}** (10 working days). Source of truth: "
             f"[`docs/absa-exl-agile-plan.xlsx`](../absa-exl-agile-plan.xlsx) Backlog sheet - task IDs match.")
    L.append("")
    L.append("## Mission")
    L.append("")
    L.append(g["mission"])
    L.append("")

    if multi:
        L.append("## The seats in this role")
        L.append("")
        for s in seats:
            L.append(f"- **{s}** - {plan.ROLE_NAMES[s]}")
        L.append("")

    # Sprint 1 plan per seat
    L.append("## Sprint 1 plan")
    L.append("")
    for s in seats:
        tasks = seat_tasks([s], sprint=1)
        total = sum(t[5] for t in tasks)
        if multi:
            L.append(f"### {fmt_seat(s)} - {total:.1f} effort-days")
        else:
            L.append(f"Your Sprint 1 load: **{total:.1f} effort-days** (cap "
                     f"{plan.capacity(s, 1):.0f}).")
        L.append("")
        if not tasks:
            L.append("_Not yet on the team in Sprint 1 (joins later - see load table)._")
            L.append("")
            continue
        L.append("| Task | Est (d) | Acceptance / Notes | Blocked on |")
        L.append("|---|---|---|---|")
        for t in tasks:
            note = t[8] or STORY_ACC.get(t[1], "")
            note = note.replace("|", "/")[:90]
            blk = t[7] or "-"
            L.append(f"| {t[0]} {t[2]} | {t[5]:.1f} | {note} | {blk} |")
        L.append("")

    # Full-program load grid for this group's seats
    L.append("## Your load across the program (effort-days/sprint)")
    L.append("")
    grid = load_grid(seats)
    hdr = "| Seat | " + " | ".join(f"S{n}" for n in range(1, plan.N_SPRINTS + 1)) + " | Cap |"
    sep = "|---|" + "---|" * plan.N_SPRINTS + "---|"
    L.append(hdr)
    L.append(sep)
    for s in seats:
        cells = []
        for n in range(1, plan.N_SPRINTS + 1):
            d = grid.get((s, n), 0.0)
            cells.append(f"{d:.1f}" if d else "-")
        cap = max(plan.capacity(s, n) for n in range(1, plan.N_SPRINTS + 1))
        L.append(f"| {s} | " + " | ".join(cells) + f" | {cap:.0f} |")
    L.append("")
    L.append("_Cap is 8 d/sprint per engineer (6 for TL), i.e. 10 working days x 0.8 focus factor. "
             "Loads sit below cap on purpose - the gap is ceremonies, review, and slack for the unknowns._")
    L.append("")

    # Sprint-by-sprint focus
    L.append("## Sprint-by-sprint focus")
    L.append("")
    for n in range(1, plan.N_SPRINTS + 1):
        tasks = seat_tasks(seats, sprint=n)
        if not tasks:
            continue
        s, e = plan.sprint_dates(n)
        goal = plan.SPRINT_GOALS[n][0]
        L.append(f"**S{n} ({s:%b %d}-{e:%b %d})** - _{goal}_")
        for t in tasks:
            tag = f"[{t[3]}] " if multi else ""
            L.append(f"- {tag}{t[2]} ({t[5]:.1f}d)")
        L.append("")

    # ABSA blockers relevant to this group
    blockers = sorted({t[7] for t in plan.TASKS if t[3] in seats and t[7].strip()})
    if blockers:
        L.append("## ABSA dependencies that block your work")
        L.append("")
        L.append("| Dependency | First bites | What it is |")
        L.append("|---|---|---|")
        for b in blockers:
            first = min(t[4] for t in plan.TASKS if t[3] in seats and t[7] == b)
            L.append(f"| {b} | S{first} | {ABSA_BLOCKERS.get(b, b)} |")
        L.append("")
        L.append("The Tech Lead sends the consolidated ABSA ask-list in Sprint 1 (T-0113) and chases weekly. "
                 "If any of the above is unanswered approaching its sprint, raise it in standup.")
        L.append("")

    L.append("## Reading list (in order)")
    L.append("")
    for i, r in enumerate(g["reading"], 1):
        L.append(f"{i}. {r}")
    L.append("")

    L.append("## Working agreement & Definition of Done")
    L.append("")
    L.append("- Branch-based flow; no direct pushes to `main`; CI green before merge; CODEOWNERS review.")
    L.append("- Daily 15-min standup; a blocker older than a day is escalated, not rediscovered at review.")
    L.append("- **Done** = merged to `main`, tests green, docs updated if behaviour changed, acceptance met, "
             "demoed on the 2nd-Friday review.")
    L.append("- Estimates are effort, not elapsed. If a task is running long, say so at standup - re-planning is "
             "normal; silent slippage is not.")
    L.append("")
    return "\n".join(L)


def gen_readme() -> str:
    L = []
    L.append("# Kickoff Briefs - 9-Person Team (grouped by role)")
    L.append("")
    L.append(f"**Sprint 1: {s1_dates()}.** One brief per role group. Generated from "
             "[`docs/absa-exl-agile-plan.xlsx`](../absa-exl-agile-plan.xlsx) via "
             "`scripts/build_kickoff_briefs.py`, so they never drift from the backlog.")
    L.append("")
    L.append("| Brief | Seats | S1 load |")
    L.append("|---|---|---|")
    for key, g in GROUPS.items():
        seats = g["seats"]
        s1 = sum(t[5] for t in plan.TASKS if t[3] in seats and t[4] == 1)
        seat_label = ", ".join(seats)
        L.append(f"| [{g['title']}]({g['file']}) | {seat_label} | {s1:.1f} d |")
    L.append("")
    L.append("## Team at a glance")
    L.append("")
    L.append("| Seat | Role | On team from |")
    L.append("|---|---|---|")
    for r in plan.ROLES:
        frm = "Sprint 8" if r == "SAS3" else "Sprint 1"
        L.append(f"| {r} | {plan.ROLE_NAMES[r]} | {frm} |")
    L.append("")
    L.append("## Is the plan achievable? (audited)")
    L.append("")
    L.append("`scripts/audit_agile_plan.py` checks the plan for feasibility, not just capacity. As of the last "
             "run it **passes**:")
    L.append("")
    L.append("- **Dependency ordering** - no task depends on work scheduled in a later sprint (no impossible orderings).")
    L.append("- **Capacity** - no role exceeds its cap in any sprint. Peak engineer load is DevOps S2 at 88%; "
             "peak overall is TL at 92% in the two sign-off sprints (S8, S12).")
    L.append("- **Sprint 1 is fully unblocked** - zero ABSA-dependent tasks land in S1, so the team is productive "
             "from day one regardless of ABSA timing.")
    L.append("- **Model coverage** - all 10 models have complete onboarding-stage coverage; all 10 are live by S11.")
    L.append("- **Integrity** - every task maps to a real story and epic; no empty stories.")
    L.append("")
    L.append("Re-run any time after editing the plan: `uv run --with openpyxl python scripts/audit_agile_plan.py`.")
    L.append("")
    L.append("## The one sentence that matters")
    L.append("")
    L.append("The platform (registry, pipeline factory, signer, code intake, LocalStack demo) is **already built "
             "and regression-tested** - your job is to put it on real AWS, swap CI to Jenkins, onboard 10 SAS "
             "models through it, and run it in production. Sprint 1 is about getting productive and making the "
             "first structural decisions.")
    L.append("")
    return "\n".join(L)


def main():
    out_dir = Path(__file__).resolve().parent.parent / "docs" / "onboarding"
    out_dir.mkdir(parents=True, exist_ok=True)
    for key, g in GROUPS.items():
        (out_dir / g["file"]).write_text(gen_brief(key, g), encoding="utf-8")
        print(f"Wrote {g['file']}")
    (out_dir / "README.md").write_text(gen_readme(), encoding="utf-8")
    print("Wrote README.md")


if __name__ == "__main__":
    main()
