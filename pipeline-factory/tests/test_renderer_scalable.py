import json

import pytest
from pipeline_factory.renderer import render_statemachine


@pytest.fixture
def context() -> dict:
    return {
        "model": {
            "name": "fraud-screen",
            "version": "2.1.0",
            "schedule_cadence": "cron(0 6 ? * 2 *)",
            "input_schema_ref": "s3://absa-exl/in.json",
            "output_schema_ref": "s3://absa-exl/out.json",
            "pir_doc_ref": "s3://absa-exl/pir.json",
        }
    }


def test_scalable_batch_renders_valid_json(context: dict) -> None:
    parsed = json.loads(render_statemachine("scalable", context))
    assert parsed["StartAt"] == "ValidateInput"
    assert "Score" in parsed["States"]
    assert parsed["States"]["Score"]["Resource"] == "arn:aws:states:::eks:runJob.sync"


def test_scalable_batch_states_match_standard(context: dict) -> None:
    parsed = json.loads(render_statemachine("scalable", context))
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


def test_scalable_batch_is_byte_stable(context: dict) -> None:
    a = render_statemachine("scalable", context)
    b = render_statemachine("scalable", context)
    assert a == b
