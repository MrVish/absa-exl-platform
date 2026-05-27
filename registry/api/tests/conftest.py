from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws

TABLE_NAME = "model_pipeline_registry"
REGION = "eu-west-1"


@pytest.fixture
def dynamo_table() -> Iterator[str]:
    with mock_aws():
        resource = boto3.resource("dynamodb", region_name=REGION)
        resource.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "model_name", "KeyType": "HASH"},
                {"AttributeName": "version", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "model_name", "AttributeType": "S"},
                {"AttributeName": "version", "AttributeType": "S"},
                {"AttributeName": "approval_status", "AttributeType": "S"},
                {"AttributeName": "updated_at", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "by_status",
                    "KeySchema": [
                        {"AttributeName": "approval_status", "KeyType": "HASH"},
                        {"AttributeName": "updated_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield TABLE_NAME


def make_record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "model_name": "credit-risk-pd",
        "version": "1.0.0",
        "sas_code_version": "sas-2026.04.1",
        "inference_code_version": "py-2026.04.1",
        "schedule_cadence": "cron(0 6 * * ? *)",
        "execution_tier": "standard",
        "input_schema_ref": "s3://absa-exl/in.json",
        "output_schema_ref": "s3://absa-exl/out.json",
        "pir_doc_ref": "s3://absa-exl/pir.json",
        "owner_email": "owner@absa.africa",
        "accountable_executive": "Jane Exec",
        "approval_status": "pending",
        "sla_seconds": 3600,
        "cab_record_id": None,
        "ivu_evidence_ref": None,
        "created_at": "2026-05-26T06:00:00+00:00",
        "updated_at": "2026-05-26T06:00:00+00:00",
        "last_scored_at": None,
        "rev": 0,
    }
    record.update(overrides)
    return record
