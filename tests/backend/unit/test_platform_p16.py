from __future__ import annotations
import pytest

pytestmark = pytest.mark.asyncio

def test_401_response_has_www_authenticate_header(client):
    """Unauthenticated requests return WWW-Authenticate: Bearer header."""
    resp = client.get("/api/students/")
    assert resp.status_code == 401
    assert "WWW-Authenticate" in resp.headers
    assert resp.headers["WWW-Authenticate"] == "Bearer"
