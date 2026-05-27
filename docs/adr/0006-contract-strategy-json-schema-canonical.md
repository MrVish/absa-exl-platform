# ADR-0006: Contract strategy — JSON Schema canonical, Pydantic generated

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-05-26 |
| Deciders | Engagement lead, EXL Platform Engineering |

## Context

Phase 2 introduces shared contracts (model-config, registry-record,
manifest-envelope) consumed by the Registry, the Pipeline Factory, and Code Intake —
two of which are not Python. The contract must be language-neutral, versioned, and
citable in the audit pack, while the Registry API needs typed Python models. This is
also the repo's first Python, so the tooling baseline is decided here.

## Decision

JSON Schema (Draft 2020-12) is the hand-authored canonical contract, stored in the
shared `platform-contracts` package. Pydantic v2 models are generated from the
schemas with `datamodel-code-generator` and committed; CI regenerates and fails on
any diff, enforcing the "Pydantic equals JSON Schema" invariant.

Python tooling baseline (platform-wide): uv (with committed `uv.lock`) for
environment and dependencies, ruff for lint + format, mypy (strict) for types,
pytest for tests.

## Consequences

### Positive
- Language-neutral contract auditors and non-Python subsystems can consume.
- No hand-sync drift between schema and models — CI proves equivalence.
- Reproducible builds via the lockfile.

### Negative
- A code-generation step in the toolchain; contributors must run
  `regenerate-models.sh` after editing a schema.
- Generated `models.py` is committed (a generated artifact in source control), which
  is the deliberate trade for the CI drift gate.

## Alternatives considered
1. Pydantic canonical, JSON Schema generated. Rejected: the audit contract would be
   a generated file living in Python code.
2. Two hand-maintained definitions. Rejected: they drift.
