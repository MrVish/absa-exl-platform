import json
import logging

from registry_api.audit import emit_audit


def test_emit_audit_writes_json_line(caplog) -> None:  # type: ignore[no-untyped-def]
    with caplog.at_level(logging.INFO, logger="registry.audit"):
        emit_audit(
            principal="arn:aws:iam::111122223333:role/writer",
            action="approve",
            model_name="credit-risk-pd",
            version="1.0.0",
            old_status="pending",
            new_status="approved",
            rev=1,
        )
    record = json.loads(caplog.records[-1].getMessage())
    assert record["action"] == "approve"
    assert record["principal"].endswith("role/writer")
    assert record["old_status"] == "pending"
    assert record["new_status"] == "approved"
    assert record["model"] == "credit-risk-pd@1.0.0"
