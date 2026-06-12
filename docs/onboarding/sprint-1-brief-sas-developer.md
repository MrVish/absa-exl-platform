# Sprint 1 Brief — SAS Developer

**Sprint 1: Mon Jun 15 → Fri Jun 26, 2026 · Your load: 5.0 effort-days**

## Your mission on this program

You are the **critical resource of this program**. Ten ABSA SAS models need
to be reviewed, optimized, packaged, and reconciled against ABSA's benchmark
outputs — and the schedule's biggest gate (Group 1 ABSA sign-off, end of
Sprint 8) sits directly on your reconciliation work. Models 1–2 are yours in
Sprints 2–6; from Sprint 9 you run two models per sprint until all ten are
live. If your work slips, the program gate slips — which is also why your
sprints are deliberately loaded at ~6.5/8 days, never 8/8.

Sprint 1 is about fluency: understand exactly what a "productized package"
is in this platform, what the SAS checker enforces today, and write the
standards doc that every one of the ten models will be held to.

## Sprint 1 outcome (your slice of the sprint goal)

> You can take a SAS model from "ABSA sent us a zip" to "code-intake
> validate passes" on the worked example, and the SAS prod-readiness
> standards doc is published for TL review.

## Your tasks

| ID | Task | Est | Acceptance |
|---|---|---|---|
| T-0103 | Clone repo, `uv sync`, full test suite green locally | 0.5 | 278 tests pass |
| T-0107 | `make demo` green locally | 0.5 | LocalStack chain exits 0 — see where your packaged model travels |
| T-0501 | Study credit-risk-pd package + static_sas checker | 2.0 | You can explain the package layout (sas/, python/, pir.yaml, model_config.yaml, manifest.json), every SAS00x finding code, and what the checker does NOT catch today |
| T-0502 | SAS prod-readiness standards doc | 2.0 | Standards doc PR'd: naming, macro discipline, error handling, logging, dataset I/O conventions, what "optimized" means (the bar models 1-10 must clear) |

## Suggested day-by-day

| Day | Plan |
|---|---|
| Mon 15 | Sprint planning (AM). T-0103 env setup. |
| Tue 16 | Architecture walkthrough (AM, TL hosts). T-0107 `make demo` — your package's manifest gets signed, shipped, and re-verified cross-account; watch it happen. |
| Wed 17 | T-0501 part 1: walk `packages/credit-risk-pd/1.0.0/` end to end. Run `uv run code-intake validate --package packages/credit-risk-pd/1.0.0/ --strict` yourself; break something; see the finding codes. |
| Thu 18 | T-0501 part 2: read `code-intake/src/code_intake/checkers/static_sas.py` — it's structural-only today (files exist, balanced PROC/RUN). List what real SAS linting must add (S3's T-0504 needs this list). |
| Fri 19 | T-0501 wrap: gap notes PR. Start T-0502 outline. |
| Mon 22 | T-0502: draft — naming, macros, error handling. |
| Tue 23 | T-0502: draft — logging, I/O conventions, performance ("optimized" defined measurably). |
| Wed 24 | T-0502 review session with TL; revise; merge. |
| Thu 25 | Pre-S2: chase the SAS runtime image/license status (TL's ask-list item DEP-03); if ABSA's model-1 docs arrived, start pre-reading; if not, deepen the checker gap notes. |
| Fri 26 | Sprint review: demo a failing→passing code-intake run + present the standards doc. Retro. |

## Day-1 access checklist

- [ ] GitHub repo write access
- [ ] SAS desktop/dev license for local work (interim until ABSA's runtime lands — PRE-07)
- [ ] Docker Desktop (for `make demo`)
- [ ] Request access to ABSA model documentation share (via TL's ask-list)

## Who depends on you / who you depend on

- **The whole program's gate (S8 sign-off) depends on your reconciliation
  chain**: optimize → package → benchmark-reconcile. It starts S2 with the
  model-1 review.
- **You depend on ABSA** for: model docs + code + benchmarks (DEP-08, needed
  S2) and the SAS runtime image (DEP-03, needed S3 for real linting). Both
  are on the ask-list TL sends Wednesday — raise at standup if silent.
- **Data engineer pairs with you** on pir.yaml ↔ input-schema linkage (their
  T-0402 dictionary template references your package's PIR file).

## Reading list (in order)

1. [ADR-0010](../adr/0010-productized-package-contract.md) — the package contract; this is your bible
2. [`code-intake/README.md`](../../code-intake/README.md) — checkers, finding codes, deferred checks
3. [`packages/credit-risk-pd/1.0.0/`](../../packages/credit-risk-pd/1.0.0/) — the worked example you'll clone the shape of ten times
4. `code-intake/src/code_intake/checkers/static_sas.py` + `pir.py` — what's enforced vs deferred
5. [docs/program-flow.md](../program-flow.md) — where your work sits in the 6-month arc

## What's next for you (S2–S6 preview)

- **S2:** model-1 dev-code review vs benchmark spec (2d) + benchmark gap notes with ABSA's model owner (1d); chase SAS runtime (0.5d).
- **S3 (7.0d):** model-1 optimization (4d) + upgrade static_sas to real lint using the runtime (3d).
- **S4:** model-1 regression harness + package; model-2 review; reconciliation diff tool design with DE.
- **S5–S6:** model-2 optimize/package; reconciliation report template; dress-rehearsal runs.
- **S9–S12:** two models per sprint, each: review → optimize → package → reconcile → PIR.
