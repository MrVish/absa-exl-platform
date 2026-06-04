# ADR-0008: Generator runtime — dual-mode (local dev + CI canonical)

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-05-26 |
| Deciders | Engagement lead, EXL Platform Engineering |

## Context

The Pipeline Factory generator turns a `model_config.yaml` into committed artifacts
and routes a registration to the Registry API. Two questions hung over the runtime:
where does it run, and who has the authority to POST?

ADR-0003 (manifest signing) already said "CI is the only signer". ADR-0006 set the
Python tooling baseline. The remaining gap, owed since Phase 1 (decision #5 in the
foundation spec), was the formal record of the generator runtime mode.

## Decision

The generator runs in two modes from the same binary (`generate-pipeline`):

- **Local dev mode** — an engineer runs `uv run generate-pipeline validate` and
  `... generate` on their workstation. No AWS credentials are required. The
  generator does not POST to the Registry API in this mode (the `register`
  subcommand is allowed but `--dry-run` is the expectation; running it with real
  creds is a per-engineer choice, not the canonical path).
- **CI canonical mode** — GitHub Actions runs `generate` on every PR (a drift
  gate: re-render, `git diff --exit-code pipelines/`, fail on drift). On push
  to `main`, GitHub Actions additionally runs `register` for every committed
  pipeline using an IAM role assumed via the GitHub Actions OIDC provider
  (`pipeline-factory-registrar`, writer-policy from the `pipeline-registry`
  module). **Only CI may POST to the Registry API in this design.**

Mode is a function of the subcommand and the presence of OIDC creds; there is no
mode flag.

## Consequences

### Positive
- Single source of governance for what is registered (the API), guarded by IAM.
- Engineers iterate fast locally without burning CI cycles.
- The drift gate makes generator changes safe — any divergence between the
  committed artifacts and a fresh render fails the PR.

### Negative
- Until the OIDC IdP and the registrar role are provisioned (deferred to 2.3),
  the `register` job is a documented no-op (gated on the secret). Models cannot
  actually be registered against a live API yet — which is consistent with the
  rest of the platform's plan-validate posture.

## Alternatives considered
1. CLI-only on developer workstations, no CI involvement. Rejected — no single
   audit trail; developers could POST inconsistent versions.
2. Lambda-hosted generator triggered by an EventBridge rule. Rejected —
   debugging Jinja rendering inside a Lambda is painful; CI gives clean logs
   and PR-diff review for free.
3. Sign + register inline in the generator. Rejected — couples signing infra to
   generator infra. ADR-0003 already separates signing (Code Intake / 2.3) from
   manifest emission (Pipeline Factory / this sprint).
