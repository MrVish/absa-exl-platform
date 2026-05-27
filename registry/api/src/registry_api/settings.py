from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    table_name: str
    region: str
    log_level: str


@lru_cache
def get_settings() -> Settings:
    table_name = os.environ.get("TABLE_NAME")
    if not table_name:
        raise RuntimeError("Required environment variable TABLE_NAME is not set")
    return Settings(
        table_name=table_name,
        region=os.environ.get("AWS_REGION", "eu-west-1"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
