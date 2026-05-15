"""Part 4 Story 4.1: /api/health/ready — school_id_configured field tests."""

from __future__ import annotations


def test_health_ready_includes_school_id_configured_true(client, monkeypatch):
    """When SCHOOL_ID is set, health/ready must report school_id_configured: true."""
    monkeypatch.setenv("SCHOOL_ID", "my-school")
    resp = client.get("/api/health/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["school_id_configured"] is True


def test_health_ready_includes_school_id_configured_false(client, monkeypatch):
    """When SCHOOL_ID is unset, health/ready must report school_id_configured: false."""
    monkeypatch.delenv("SCHOOL_ID", raising=False)
    resp = client.get("/api/health/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["school_id_configured"] is False


def test_health_ready_includes_db_and_ai_fields(client, monkeypatch):
    """health/ready must always include the db and ai status fields."""
    resp = client.get("/api/health/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert "db" in data
    assert "ai" in data
    assert "school_id_configured" in data
