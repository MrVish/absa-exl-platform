"""orchestrator: runs every checker; collects all findings; never crashes."""

from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path

from .checkers.base import Checker, CheckResult, Finding


def _build_checkers() -> list[Checker]:
    """Build the checker list at call-time so monkey-patching in tests
    affects future invocations."""
    from .checkers import pir, schema, static_python, static_sas
    from .checkers import tests as tests_mod

    return [
        static_python.StaticPythonChecker(),
        static_sas.StaticSasChecker(),
        schema.SchemaChecker(),
        tests_mod.TestsChecker(),
        pir.PirChecker(),
    ]


def validate(package_path: Path, *, strict: bool = False) -> list[CheckResult]:
    """Run every checker; never short-circuit; never raise.

    `strict` flips warning-severity findings into errors. Default False.

    Returns the list of all CheckResults in execution order.

    A checker that raises is converted to a single error-severity Finding
    with code `<CHECKER>999` so the orchestrator never propagates a crash.
    """
    results: list[CheckResult] = []
    for checker in _build_checkers():
        start = time.monotonic()
        try:
            result = checker.run(package_path)
        except Exception as e:
            result = CheckResult(
                checker=checker.name,
                passed=False,
                findings=[
                    Finding(
                        severity="error",
                        code=f"{checker.name.upper()}999",
                        message=f"checker crashed: {e!r}",
                    )
                ],
            )

        if strict:
            # Flip warning-severity findings into errors.
            elevated = [
                replace(f, severity="error") if f.severity == "warning" else f
                for f in result.findings
            ]
            still_passed = not any(f.severity == "error" for f in elevated)
            result = replace(result, findings=elevated, passed=still_passed)

        result = replace(result, duration_seconds=time.monotonic() - start)
        results.append(result)

    return results
