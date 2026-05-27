import pytest
from registry_api.transitions import (
    ApprovalPreconditionError,
    IllegalTransitionError,
    assert_approval_preconditions,
    assert_transition_allowed,
)


def test_pending_to_approved_allowed() -> None:
    assert_transition_allowed("pending", "approved")


def test_approved_to_retired_allowed() -> None:
    assert_transition_allowed("approved", "retired")


def test_pending_to_retired_illegal() -> None:
    with pytest.raises(IllegalTransitionError):
        assert_transition_allowed("pending", "retired")


def test_approved_to_pending_illegal() -> None:
    with pytest.raises(IllegalTransitionError):
        assert_transition_allowed("approved", "pending")


def test_preconditions_ok_when_cab_and_ivu_present() -> None:
    assert_approval_preconditions({"cab_record_id": "CAB-1", "ivu_evidence_ref": "s3://x/ivu.pdf"})


def test_preconditions_list_missing_fields() -> None:
    with pytest.raises(ApprovalPreconditionError) as exc:
        assert_approval_preconditions({"cab_record_id": None, "ivu_evidence_ref": None})
    assert exc.value.missing == ["cab_record_id", "ivu_evidence_ref"]
