"""Feasibility + consistency audit of the agile plan.

Imports the plan data from build_agile_plan.py and checks the things that
make a plan actually DOABLE (not just capacity-balanced):

  1. Dependency existence    - every `deps` id refers to a real task
  2. Dependency ordering     - no task depends on work in a LATER sprint
  3. Capacity                - per (role, sprint) load <= capacity
  4. Sprint-1 unblocked      - no ABSA-blocked task lands in S1
  5. Story/epic integrity    - every task's story exists; no empty stories
  6. Model coverage          - all 10 models have full onboarding stage coverage
  7. ABSA-dependency timing  - when each ABSA blocker first bites

Exit 0 = plan is internally consistent and feasible; non-zero = issues found.
"""

from __future__ import annotations

import build_agile_plan as plan

ERRORS: list[str] = []
WARNINGS: list[str] = []

TASKS = plan.TASKS
STORIES = {s[0] for s in plan.STORIES}
EPICS = {e[0] for e in plan.EPICS}
TASK_IDS = {t[0] for t in TASKS}
SPRINT_OF = {t[0]: t[4] for t in TASKS}


def check_dep_existence():
    for t in TASKS:
        deps = [d.strip() for d in t[6].split(",") if d.strip()]
        for d in deps:
            if d not in TASK_IDS:
                ERRORS.append(f"{t[0]}: dependency {d!r} does not exist")


def check_dep_ordering():
    for t in TASKS:
        tid, tsprint = t[0], t[4]
        deps = [d.strip() for d in t[6].split(",") if d.strip()]
        for d in deps:
            if d in SPRINT_OF and SPRINT_OF[d] > tsprint:
                ERRORS.append(
                    f"{tid} (S{tsprint}) depends on {d} (S{SPRINT_OF[d]}) - "
                    f"dependency is in a LATER sprint (impossible ordering)"
                )


def check_capacity():
    load: dict[tuple[str, int], float] = {}
    for t in TASKS:
        load[(t[3], t[4])] = load.get((t[3], t[4]), 0.0) + t[5]
    for (role, sprint), days in load.items():
        cap = plan.capacity(role, sprint)
        if days > cap + 1e-9:
            ERRORS.append(f"OVERLOAD {role} S{sprint}: {days:.1f}d > {cap:.1f}d")
        elif cap > 0 and days >= cap - 0.5 and days > 0:
            WARNINGS.append(f"TIGHT {role} S{sprint}: {days:.1f}d of {cap:.1f}d ({days/cap*100:.0f}%)")


def check_sprint1_unblocked():
    for t in TASKS:
        if t[4] == 1 and t[7].strip():
            ERRORS.append(f"{t[0]} is in S1 but blocked on '{t[7]}' - S1 must be fully unblocked")


def check_story_epic_integrity():
    tasks_per_story: dict[str, int] = {}
    for t in TASKS:
        if t[1] not in STORIES:
            ERRORS.append(f"{t[0]}: story {t[1]!r} not defined")
        tasks_per_story[t[1]] = tasks_per_story.get(t[1], 0) + 1
    for s in plan.STORIES:
        if s[0] not in tasks_per_story:
            ERRORS.append(f"Story {s[0]} has no tasks")
        if s[1] not in EPICS:
            ERRORS.append(f"Story {s[0]}: epic {s[1]!r} not defined")


def check_model_coverage():
    # Group 1 = models 1-2 (bespoke tasks), Group 2 = 3-10 (generated, 10 tasks each)
    for m in range(3, 11):
        suffixes = {tid.split("-")[-1] for tid in TASK_IDS if tid.startswith(f"T-M{m:02d}-")}
        expected = {s[0] for s in plan.G2_TEMPLATE}
        missing = expected - suffixes
        if missing:
            ERRORS.append(f"Model {m}: missing stages {sorted(missing)}")
    # All 10 models present in tracker
    tracked = {row[0] for row in plan.MODELS}
    for m in range(1, 11):
        if f"Model {m}" not in tracked:
            ERRORS.append(f"Model {m} missing from Per-Model Tracker")


def report_absa_timing():
    first: dict[str, int] = {}
    for t in sorted(TASKS, key=lambda x: x[4]):
        b = t[7].strip()
        if b and b not in first:
            first[b] = t[4]
    print("\nABSA dependency - first sprint it bites:")
    for dep, sprint in sorted(first.items(), key=lambda x: x[1]):
        print(f"  S{sprint:<2} {dep}")


def print_load_grid():
    load: dict[tuple[str, int], float] = {}
    for t in TASKS:
        load[(t[3], t[4])] = load.get((t[3], t[4]), 0.0) + t[5]
    print("\nPer-role load (d/sprint), util%% of cap in parens for the peak:")
    hdr = "role    " + "".join(f"S{n:<5}" for n in range(1, plan.N_SPRINTS + 1))
    print(hdr)
    for role in plan.ROLES:
        cells = []
        peak_util = 0.0
        for n in range(1, plan.N_SPRINTS + 1):
            d = load.get((role, n), 0.0)
            cap = plan.capacity(role, n)
            if cap:
                peak_util = max(peak_util, d / cap)
            cells.append(f"{d:<5.1f}" if d else "  -  ")
        print(f"{role:<7} " + "".join(cells) + f"  peak {peak_util*100:.0f}%")


def main():
    check_dep_existence()
    check_dep_ordering()
    check_capacity()
    check_sprint1_unblocked()
    check_story_epic_integrity()
    check_model_coverage()

    print(f"Audit of {len(TASKS)} tasks / {len(plan.STORIES)} stories / {len(plan.EPICS)} epics")
    print_load_grid()
    report_absa_timing()

    print("\n" + "=" * 60)
    if ERRORS:
        print(f"FAIL - {len(ERRORS)} error(s):")
        for e in ERRORS:
            print("  [ERROR]", e)
    else:
        print("PASS - no consistency/feasibility errors")
    if WARNINGS:
        print(f"\n{len(WARNINGS)} tightness warning(s) (acceptable, but watch):")
        for w in sorted(WARNINGS):
            print("  [tight]", w)

    raise SystemExit(1 if ERRORS else 0)


if __name__ == "__main__":
    main()
