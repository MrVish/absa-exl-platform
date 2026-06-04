from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def sample_config(tmp_path: Path) -> Path:
    config = tmp_path / "model_config.yaml"
    config.write_text(
        """
model_name: credit-risk-pd
version: 1.0.0
execution_tier: standard
schedule_cadence: "cron(0 6 * * ? *)"
input_schema_ref: s3://absa-exl/in.json
output_schema_ref: s3://absa-exl/out.json
pir_doc_ref: s3://absa-exl/pir.json
owner_email: owner@absa.africa
accountable_executive: Jane Exec
sla_seconds: 3600
sas_code_version: sas-2026.04.1
inference_code_version: py-2026.04.1
""".strip(),
        encoding="utf-8",
    )
    return config
