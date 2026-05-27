from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Tier = Literal["standard", "scalable"]
_S3 = r"^s3://"


class CreateModelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_name: str = Field(pattern=r"^[a-z][a-z0-9-]{2,63}$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    sas_code_version: str = Field(min_length=1)
    inference_code_version: str = Field(min_length=1)
    schedule_cadence: str = Field(min_length=1)
    execution_tier: Tier
    input_schema_ref: str = Field(pattern=_S3)
    output_schema_ref: str = Field(pattern=_S3)
    pir_doc_ref: str = Field(pattern=_S3)
    owner_email: EmailStr
    accountable_executive: str = Field(min_length=1)
    sla_seconds: int = Field(gt=0)
    cab_record_id: str | None = None
    ivu_evidence_ref: str | None = Field(default=None, pattern=_S3)


class UpdateModelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    expected_rev: int = Field(ge=0)
    schedule_cadence: str | None = Field(default=None, min_length=1)
    sla_seconds: int | None = Field(default=None, gt=0)
    last_scored_at: str | None = None
    cab_record_id: str | None = None
    ivu_evidence_ref: str | None = Field(default=None, pattern=_S3)
