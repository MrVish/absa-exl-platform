# Sprint 1 Brief — Data Engineer

**Sprint 1: Mon Jun 15 → Fri Jun 26, 2026 · Your load: 4.0 effort-days**

## Your mission on this program

You own the data plane: the contracts that say what each model's input looks
like, the ingestion path that validates files the moment ABSA lands them,
the data-quality framework (volume bands + drift metrics), and the PIR
integration that anchors every input column to ABSA's Production Input
Register. In steady state, your DQ checks are the first thing that catches a
bad scoring run — before the model ever executes.

Your load is deliberately lighter than the others mid-program: you absorb
the unpredictable work (real data never behaves) and the per-model contract
work as Group 2 scales.

## Sprint 1 outcome (your slice of the sprint goal)

> The data dictionary template exists and is agreed — so that the moment
> ABSA's model-1/2 docs arrive (S2), filling in real schemas is mechanical,
> not a design exercise.

## Your tasks

| ID | Task | Est | Acceptance |
|---|---|---|---|
| T-0102 | Clone repo, `uv sync`, full test suite green locally | 0.5 | 278 tests pass |
| T-0106 | `make demo` green locally | 0.5 | LocalStack chain exits 0 |
| T-0401 | Study platform-contracts schemas + PIR mapping + demo data flow | 1.0 | You can explain: model-config schema, package-manifest payload, pir-mapping schema, and how data flows source→scoring in the demo |
| T-0402 | Data dictionary template | 2.0 | Template PR'd: per-model input schema sheet (column, type, nullability, valid ranges, PIR reference, source dataset) — reviewed by TL + SAS dev |

## Suggested day-by-day

| Day | Plan |
|---|---|
| Mon 15 | Sprint planning (AM). T-0102 env setup. |
| Tue 16 | Architecture walkthrough (AM, TL hosts). T-0106 `make demo`. |
| Wed 17 | T-0401: read the three schemas in `platform-contracts/src/platform_contracts/schemas/`; trace `pir.yaml` in the worked example; map the demo's data flow. |
| Thu 18 | T-0402: draft the dictionary template. Use `packages/credit-risk-pd/1.0.0/` as the prototype — fill the template against it as a worked example. |
| Fri 19 | T-0402: finish the worked-example fill; PR the template. |
| Mon 22 | T-0402 review session with TL + SAS dev (the PIR-linkage column is the contentious bit — agree it). Merge. |
| Tue 23 | Pre-S2: sketch the volume/cadence matrix structure (T-0404) — rows ready for ABSA's per-model answers. |
| Wed 24 | Pre-S2: bucket layout / partitioning options note (feeds T-0405) — date-partitioned vs run-id-keyed, lifecycle implications. |
| Thu 25 | If ABSA model docs arrived: start model-1 schema. If not: prototype an arrival-validation check against the demo fixture (de-risks S3's T-0406). |
| Fri 26 | Sprint review: present the template + filled worked example. Retro. |

## Day-1 access checklist

- [ ] GitHub repo write access
- [ ] Docker Desktop (for `make demo`)
- [ ] Request access to ABSA data dictionaries / source-dataset docs (via TL's ask-list)

## Who depends on you / who you depend on

- **SAS dev consumes your contracts**: their per-model packaging needs your
  input schemas (S2 onward) and pairs with you on the reconciliation diff
  tool (S4).
- **You depend on ABSA** for model docs (DEP-08, S2) and later the PIR
  API contract (DEP-04, S5). Insulated this sprint by design.
- **Your DQ framework (S4-S5) feeds decision D01** (drift metrics) — you
  write the proposal ABSA's risk owner approves.

## Reading list (in order)

1. [ADR-0006](../adr/0006-contract-strategy-json-schema-canonical.md) — why JSON Schema + canonical JSON is the contract backbone
2. `platform-contracts/src/platform_contracts/schemas/` — all three schemas, especially `pir-mapping.schema.json`
3. [`packages/credit-risk-pd/1.0.0/pir.yaml`](../../packages/credit-risk-pd/1.0.0/) — a real PIR file
4. [`code-intake/README.md`](../../code-intake/README.md) — the PIR checker section (PIR00x codes)
5. [ADR-0001](../adr/0001-data-movement-s3-replication.md) — how data moves cross-account

## What's next for you (S2–S7 preview)

- **S2:** input schemas for models 1-2 (2d), volume/cadence matrix for all 10 (1d), bucket layout convention (1d).
- **S3:** arrival validation job (3d) + reject/return-to-ABSA workflow (1d).
- **S4:** volume band checks + PSI drift design → the D01 proposal.
- **S5:** DQ report artifact per run; PIR contract session + pir.yaml sync build.
- **S6-S7:** dress-rehearsal data prep; DQ tuning on first production runs.
- **S9-S12:** contracts + DQ verification for each Group 2 wave (2 models/sprint).
