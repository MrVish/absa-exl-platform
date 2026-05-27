from __future__ import annotations

import json
import logging

logger = logging.getLogger("registry.audit")


def emit_audit(
    *,
    principal: str,
    action: str,
    model_name: str,
    version: str,
    old_status: str | None = None,
    new_status: str | None = None,
    rev: int | None = None,
) -> None:
    logger.info(
        json.dumps(
            {
                "principal": principal,
                "action": action,
                "model": f"{model_name}@{version}",
                "old_status": old_status,
                "new_status": new_status,
                "rev": rev,
            }
        )
    )
