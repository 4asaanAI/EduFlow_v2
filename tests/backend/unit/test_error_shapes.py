from __future__ import annotations

from fastapi import HTTPException
from fastapi.testclient import TestClient

from server import app


@app.get("/__test__/http-error")
async def _test_http_error():
    raise HTTPException(404, "Not found")


@app.get("/__test__/unhandled-error")
async def _test_unhandled_error():
    raise RuntimeError("boom")


def test_http_exception_shape_has_detail_only(client):
    response = client.get("/__test__/http-error")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not found"}


def test_validation_error_shape_uses_detail_list(client):
    response = client.post("/api/auth/login", json={"username": "admin"})

    assert response.status_code == 422
    body = response.json()
    assert set(body.keys()) == {"detail"}
    assert isinstance(body["detail"], list)


def test_global_exception_shape_has_no_success_field():
    with TestClient(app, raise_server_exceptions=False) as local_client:
        response = local_client.get("/__test__/unhandled-error")

    assert response.status_code == 500
    assert response.json() == {"detail": "An internal error occurred"}
