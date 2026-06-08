"""orchestrator: runs every checker; collects all findings; never crashes.

Per Phase 3 spec section 5.1, static_python and tests run INSIDE an
ephemeral per-package venv. The venv is created from the package's
python/pyproject.toml; if the venv setup fails, VenvCreationError is
caught and surfaced as a 'venv' CheckResult so the 'orchestrator never
propagates exceptions' invariant holds.

Non-venv checkers (static_sas, schema, pir) still run in the workspace
toolchain — they only read static files, not runtime imports.
"""

from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path

from .checkers.base import Checker, CheckResult, Finding


def validate(package_path: Path, *, strict: bool = False) -> list[CheckResult]:
    """Run every checker; never short-circuit; never raise.

    `strict` flips warning-severity findings into errors. Default False.

    Returns the list of all CheckResults in execution order.

    A checker that raises is converted to a single error-severity Finding
    with code `<CHECKER>999` so the orchestrator never propagates a crash.
    """
    from .checkers import pir, schema, static_python, static_sas
    from .checkers import tests as tests_mod
    from .errors import VenvCreationError
    from .venv import create_ephemeral_venv

    results: list[CheckResult] = []

    # 1. Non-venv checkers (static_sas, schema, pir) run in the workspace
    #    toolchain. They only read static files.
    non_venv_checkers: list[Checker] = [
        static_sas.StaticSasChecker(),
        schema.SchemaChecker(),
        pir.PirChecker(),
    ]
    for checker in non_venv_checkers:
        results.append(_run_one(checker, package_path, strict=strict))

    # 2. Venv-dependent checkers (static_python, tests) run inside an
    #    ephemeral venv created from python/pyproject.toml.
    #    If the package has no python files at all (pure-SAS, or empty
    #    python/), skip the venv entirely — both checkers no-op themselves
    #    in that case, so spinning up a venv just to discard it would
    #    waste 25-40s per validate call.
    python_dir = package_path / "python"
    has_python_code = python_dir.is_dir() and any(python_dir.rglob("*.py"))

    if not has_python_code:
        # No Python -> no venv -> let the checkers run their own no-op
        # short-circuit paths against the workspace toolchain.
        no_venv_python_checkers: list[Checker] = [
            static_python.StaticPythonChecker(),
            tests_mod.TestsChecker(),
        ]
        for checker in no_venv_python_checkers:
            results.append(_run_one(checker, package_path, strict=strict))
        return results

    try:
        with create_ephemeral_venv(package_path) as venv_ctx:
            venv_checkers: list[Checker] = [
                static_python.StaticPythonChecker(env_vars=venv_ctx.env_vars),
                tests_mod.TestsChecker(env_vars=venv_ctx.env_vars),
            ]
            for checker in venv_checkers:
                results.append(_run_one(checker, package_path, strict=strict))
    except VenvCreationError as e:
        # Surface as a Finding rather than propagating. The 'venv' check
        # is synthetic — there's no Checker class for it — but it stands
        # in the result list as the place where venv setup failed.
        finding = Finding(
            severity="error",
            code=e.code,
            message=e.message,
            hint=e.hint,
            location=str(package_path / "python"),
        )
        if strict and finding.severity == "warning":
            finding = replace(finding, severity="error")
        results.append(
            CheckResult(
                checker="venv",
                passed=False,
                findings=[finding],
                duration_seconds=0.0,
            )
        )
        # The downstream venv-dependent checkers are now unreachable;
        # don't pretend they ran. Caller sees one "venv" failure and
        # the absence of static_python/tests results in the list, which
        # is the honest representation: we never got far enough to run them.

    return results


def _run_one(
    checker: Checker,
    package_path: Path,
    *,
    strict: bool,
) -> CheckResult:
    """Run a single checker, catching exceptions and timing the call.

    A checker that raises is converted to a single error-severity Finding
    with code `<CHECKER>999` so the orchestrator never propagates a crash.
    """
    name = checker.name
    start = time.monotonic()
    try:
        result: CheckResult = checker.run(package_path)
    except Exception as e:
        result = CheckResult(
            checker=name,
            passed=False,
            findings=[
                Finding(
                    severity="error",
                    code=f"{name.upper()}999",
                    message=f"checker crashed: {e!r}",
                )
            ],
        )

    if strict:
        elevated = [
            replace(f, severity="error") if f.severity == "warning" else f
            for f in result.findings
        ]
        still_passed = not any(f.severity == "error" for f in elevated)
        result = replace(result, findings=elevated, passed=still_passed)

    return replace(result, duration_seconds=time.monotonic() - start)
