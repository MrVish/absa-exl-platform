from .conftest import make_create_body


def _create(client, **o):  # type: ignore[no-untyped-def]
    return client.post("/models", json=make_create_body(**o))


def test_approve_without_cab_ivu_returns_422(client) -> None:  # type: ignore[no-untyped-def]
    _create(client)
    resp = client.post("/models/credit-risk-pd/versions/1.0.0:approve")
    assert resp.status_code == 422
    assert set(resp.json()["error"]["detail"]["missing"]) == {"cab_record_id", "ivu_evidence_ref"}


def test_approve_with_cab_ivu_returns_200(client) -> None:  # type: ignore[no-untyped-def]
    _create(client)
    client.patch(
        "/models/credit-risk-pd/versions/1.0.0",
        json={"expected_rev": 0, "cab_record_id": "CAB-1", "ivu_evidence_ref": "s3://x/ivu.pdf"},
    )
    resp = client.post("/models/credit-risk-pd/versions/1.0.0:approve")
    assert resp.status_code == 200
    assert resp.json()["approval_status"] == "approved"


def test_illegal_pending_to_retire_returns_409(client) -> None:  # type: ignore[no-untyped-def]
    _create(client)
    resp = client.post("/models/credit-risk-pd/versions/1.0.0:retire")
    assert resp.status_code == 409


def test_approve_then_retire(client) -> None:  # type: ignore[no-untyped-def]
    _create(client)
    client.patch(
        "/models/credit-risk-pd/versions/1.0.0",
        json={"expected_rev": 0, "cab_record_id": "CAB-1", "ivu_evidence_ref": "s3://x/ivu.pdf"},
    )
    client.post("/models/credit-risk-pd/versions/1.0.0:approve")
    resp = client.post("/models/credit-risk-pd/versions/1.0.0:retire")
    assert resp.status_code == 200
    assert resp.json()["approval_status"] == "retired"
