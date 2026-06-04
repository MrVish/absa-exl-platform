import json

import pytest
from pipeline_factory.renderer import render_statemachine


@pytest.fixture
def context() -> dict:
    return {
        "model": {
            "name": "credit-risk-pd",
            "version": "1.0.0",
            "schedule_cadence": "cron(0 6 * * ? *)",
            "input_schema_ref": "s3://absa-exl/in.json",
            "output_schema_ref": "s3://absa-exl/out.json",
            "pir_doc_ref": "s3://absa-exl/pir.json",
        }
    }


def test_standard_batch_renders_valid_json(context: dict) -> None:
    out = render_statemachine("standard", context)
    parsed = json.loads(out)
    assert parsed["StartAt"] == "ValidateInput"
    expected_states = {
        "ValidateInput",
        "DataQuality",
        "Score",
        "WriteOutput",
        "PIRVariance",
        "VarianceDecision",
        "Notify",
        "BlockDelivery",
        "NotifyFailure",
        "Fail",
    }
    assert set(parsed["States"]) == expected_states


def test_standard_batch_score_uses_sagemaker_integration(context: dict) -> None:
    parsed = json.loads(render_statemachine("standard", context))
    expected_resource = "arn:aws:states:::sagemaker:createTransformJob.sync"
    assert parsed["States"]["Score"]["Resource"] == expected_resource


def test_standard_batch_is_byte_stable(context: dict) -> None:
    a = render_statemachine("standard", context)
    b = render_statemachine("standard", context)
    assert a == b


def test_realtime_tier_refused(context: dict) -> None:
    with pytest.raises(ValueError, match="realtime"):
        render_statemachine("realtime", context)
