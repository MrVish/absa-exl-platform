import pytest
from pipeline_factory.hashing import terraform_fmt
from pipeline_factory.renderer import render_pipeline_tf


@pytest.fixture
def standard_context() -> dict:
    return {
        "tier": "standard",
        "model": {
            "name": "credit-risk-pd",
            "version": "1.0.0",
            "schedule_cadence": "cron(0 6 * * ? *)",
        },
    }


@pytest.fixture
def scalable_context() -> dict:
    return {
        "tier": "scalable",
        "model": {
            "name": "fraud-screen",
            "version": "2.1.0",
            "schedule_cadence": "cron(0 6 ? * 2 *)",
        },
    }


def test_standard_tf_renders_and_fmts(standard_context: dict) -> None:
    raw = render_pipeline_tf(standard_context)
    formatted = terraform_fmt(raw)
    assert "aws_sfn_state_machine" in formatted
    assert "aws_cloudwatch_event_rule" in formatted
    assert "aws_cloudwatch_log_group" in formatted
    assert 'schedule_expression = "cron(0 6 * * ? *)"' in formatted
    # idempotent
    assert terraform_fmt(formatted) == formatted


def test_scalable_tf_includes_eks_variables(scalable_context: dict) -> None:
    formatted = terraform_fmt(render_pipeline_tf(scalable_context))
    assert "eks_cluster_name" in formatted
    assert "eks_scoring_namespace" in formatted
    assert "scoring_image_uri" in formatted


def test_standard_tf_excludes_eks_variables(standard_context: dict) -> None:
    formatted = terraform_fmt(render_pipeline_tf(standard_context))
    assert "eks_cluster_name" not in formatted
    assert "scoring_image_uri" not in formatted
