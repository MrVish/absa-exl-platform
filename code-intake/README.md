# `code-intake`

Validates productized packages (SAS + Python + PIR + tests + model_config) and
emits a signed package manifest. The third stage of the Phase-2 audit chain.

See [Sprint 4 spec](../docs/superpowers/specs/2026-06-04-absa-exl-phase-2-sprint-4-code-intake-design.md),
[ADR-0003](../docs/adr/0003-manifest-signing-kms-asymmetric.md),
[ADR-0010](../docs/adr/0010-productized-package-contract.md).

## Subcommands

| Command | Use case |
|---|---|
| `code-intake validate --package <path> [--strict] [--json]` | Run all five checkers; print summary; exit 0/1. `--strict` flips warnings into errors. `--json` emits a single JSON object on stdout. |
| `code-intake generate-manifest --package <path> [--strict]` | Run validate first; on success write `<path>/manifest.json` with UNSIGNED sentinels Sprint 3's signer fills in CI. Preserves `generated_at` / `signed_at` from an existing manifest for byte-stable re-renders. |

## Library API

```python
from code_intake.orchestrator import validate
from code_intake.manifest import build_package_payload, build_package_envelope
from code_intake.package_config import load_package_config
```

All functions are pure — no AWS calls, no network. Sprint 3's `manifest-signer`
owns the AWS path.

## The five checkers

| Checker | Validates | Failure codes |
|---|---|---|
| `static_python` | `ruff check` + `mypy --strict` + `pytest --collect-only` against `<package>/python/` | PY001 ruff · PY002 mypy · PY003 pytest discovery · PY998 subprocess timed out (tune `StaticPythonChecker(timeout_seconds=N)`) |
| `static_sas`    | Files in `<package>/sas/` are non-empty and have balanced PROC/RUN (structural only) | SAS002 empty · SAS003 PROC/RUN imbalance |
| `schema`        | `<package>/model_config.yaml` validates against `package-manifest-payload.schema.json` | SCH001 schema validation |
| `tests`         | `pytest <package>/python/tests/` exits 0 | TST001 collection · TST002 ≥1 test failed · TST998 subprocess timed out (tune `TestsChecker(timeout_seconds=N)`) |
| `pir`           | `<package>/pir.yaml` validates against `pir-mapping.schema.json` AND every column referenced by Python is in `pir.inputs[]` | PIR001 schema · PIR002 unmapped column |

The orchestrator runs all five and **never short-circuits**. A checker that
crashes is wrapped as a single `<CHECKER>999` finding rather than propagating
the exception. A checker whose subprocess exceeds its `timeout_seconds`
emits a `<CHECKER>998` finding, distinct from `999` so operators can tell
"checker timed out" apart from "checker threw an exception".

## Don't hand-edit `manifest.json`

The `manifest.json` in each `packages/<name>/<version>/` directory is
**generated** by `code-intake generate-manifest`. CI enforces byte-stability via
`git diff --exit-code packages/`. To change a manifest, edit the upstream source
(`model_config.yaml`, the SAS / Python code, etc.) and regenerate.

## Architecture

| Module | Responsibility |
|---|---|
| `code_intake.checkers.base`     | Shared `Checker` protocol + `Finding` / `CheckResult` dataclasses |
| `code_intake.checkers.*`        | Five concrete checkers (one file each) |
| `code_intake.orchestrator`      | Runs all five; collect-all-findings; never crashes; records timing |
| `code_intake.package_config`    | Loader + schema validation for the package's `model_config.yaml` |
| `code_intake.manifest`          | Build payload + UNSIGNED envelope (Sprint 3's signer fills sentinels) |
| `code_intake.cli`               | Click CLI exposing `validate` and `generate-manifest` |
| `code_intake.errors`            | `CodeIntakeError`, `ValidationError`, `PackageConfigError` |

## Testing

```bash
uv run pytest code-intake/tests
```

The end-to-end test (`test_e2e_track_a.py`) exercises the full Code Intake →
Pipeline Factory → signer → mock registrar chain inside one moto context —
proving the CI flow works without AWS credentials.
