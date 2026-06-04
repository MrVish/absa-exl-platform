"""static_sas checker: structural checks on .sas files.

Sprint 4 ships structural-only validation: file existence, non-emptiness,
balanced PROC/RUN blocks. Real SAS linting (parsing PROC contents, type
checking variable references, etc.) is deferred to Phase 3 when ABSA's
SAS runtime is in scope.
"""

from __future__ import annotations

import re
from pathlib import Path

from .base import CheckResult, Finding

# Match `PROC <NAME>` (case-insensitive). The DATA step doesn't take a RUN
# in some SAS conventions but standardly does; we treat both DATA and PROC
# as needing a matching RUN.
_OPEN_RE = re.compile(r"^\s*(DATA|PROC)\b", re.IGNORECASE | re.MULTILINE)
_RUN_RE = re.compile(r"^\s*RUN\s*;", re.IGNORECASE | re.MULTILINE)


class StaticSasChecker:
    name = "static_sas"

    def run(self, package_path: Path) -> CheckResult:
        sas_dir = package_path / "sas"
        if not sas_dir.is_dir():
            return CheckResult(checker=self.name, passed=True)

        findings: list[Finding] = []

        for sas_file in sorted(sas_dir.rglob("*.sas")):
            content = sas_file.read_text(encoding="utf-8")
            rel = str(sas_file.relative_to(package_path))

            if not content.strip():
                findings.append(
                    Finding(
                        severity="error",
                        code="SAS002",
                        message=f"empty SAS file: {rel}",
                        file=rel,
                    )
                )
                continue

            opens = len(_OPEN_RE.findall(content))
            runs = len(_RUN_RE.findall(content))
            if opens != runs:
                findings.append(
                    Finding(
                        severity="error",
                        code="SAS003",
                        message=(
                            f"unbalanced PROC/RUN in {rel}: "
                            f"{opens} DATA/PROC blocks vs {runs} RUN statements"
                        ),
                        file=rel,
                    )
                )

        # SAS001 (missing required file) is intentionally not checked here —
        # the schema checker validates the declared file_refs against on-disk
        # presence. static_sas only sees what's actually in sas/.

        passed = not any(f.severity == "error" for f in findings)
        return CheckResult(checker=self.name, passed=passed, findings=findings)
