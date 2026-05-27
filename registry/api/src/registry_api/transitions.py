from __future__ import annotations

from typing import Any

VALID_STATUSES = ("pending", "approved", "retired")
_ALLOWED_EDGES = {("pending", "approved"), ("approved", "retired")}
_APPROVAL_REQUIRED_FIELDS = ("cab_record_id", "ivu_evidence_ref")


class IllegalTransitionError(Exception):
    """Raised for a transition that is not on the allowed edge set."""


class ApprovalPreconditionError(Exception):
    """Raised when approval is attempted without CAB + IVU evidence."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__("missing approval preconditions: " + ", ".join(missing))


def assert_transition_allowed(current: str, target: str) -> None:
    if (current, target) not in _ALLOWED_EDGES:
        raise IllegalTransitionError(f"cannot transition {current} -> {target}")


def assert_approval_preconditions(record: dict[str, Any]) -> None:
    missing = [field for field in _APPROVAL_REQUIRED_FIELDS if not record.get(field)]
    if missing:
        raise ApprovalPreconditionError(missing)
