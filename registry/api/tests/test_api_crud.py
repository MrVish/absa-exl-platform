from .conftest import make_create_body


def test_create_returns_201_and_pending(client) -> None:  # type: ignore[no-untyped-def]
    resp = client.post("/models", json=make_create_body())
    assert resp.status_code == 201
    body = resp.json()
    assert body["approval_status"] == "pending"
    assert body["rev"] == 0


def test_create_duplicate_returns_409(client) -> None:  # type: ignore[no-untyped-def]
    client.post("/models", json=make_create_body())
    resp = client.post("/models", json=make_create_body())
    assert resp.status_code == 409


def test_create_rejects_unknown_field_422(client) -> None:  # type: ignore[no-untyped-def]
    resp = client.post("/models", json=make_create_body(surprise="x"))
    assert resp.status_code == 422


def test_get_missing_returns_404(client) -> None:  # type: ignore[no-untyped-def]
    resp = client.get("/models/missing/versions/1.0.0")
    assert resp.status_code == 404


def test_list_by_status(client) -> None:  # type: ignore[no-untyped-def]
    client.post("/models", json=make_create_body())
    client.post("/models", json=make_create_body(version="1.1.0"))
    resp = client.get("/models", params={"status": "pending"})
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


def test_patch_updates_and_bumps_rev(client) -> None:  # type: ignore[no-untyped-def]
    client.post("/models", json=make_create_body())
    resp = client.patch(
        "/models/credit-risk-pd/versions/1.0.0",
        json={"expected_rev": 0, "sla_seconds": 7200},
    )
    assert resp.status_code == 200
    assert resp.json()["rev"] == 1
    assert resp.json()["sla_seconds"] == 7200
