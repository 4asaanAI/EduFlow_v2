"""Part 4 Story 4.1: /api/health/ready — school_id_configured field tests."""

from __future__ import annotations

import pytest
import server


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
    assert "s3" in data
    assert "sms" in data
    assert "school_id_configured" in data


def test_health_ready_degrades_when_s3_degraded(client, monkeypatch):
    async def degraded():
        return "degraded"

    async def ok():
        return "ok"

    monkeypatch.setattr(server, "_check_s3", degraded)
    monkeypatch.setattr(server, "_check_sms", ok)
    monkeypatch.setattr(server, "_check_ai", ok)

    resp = client.get("/api/health/ready")

    assert resp.status_code == 200
    data = resp.json()
    assert data["s3"] == "degraded"
    assert data["overall"] == "degraded"


@pytest.mark.asyncio
async def test_check_s3_not_configured(monkeypatch):
    monkeypatch.delenv("S3_BUCKET_NAME", raising=False)
    monkeypatch.delenv("S3_BUCKET", raising=False)

    assert await server._check_s3() == "not_configured"


@pytest.mark.asyncio
async def test_check_s3_ok(monkeypatch):
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket")

    class FakeS3:
        def list_objects_v2(self, **_kwargs):
            return {}

    monkeypatch.setattr("services.s3_storage.get_s3_client", lambda: FakeS3())

    assert await server._check_s3() == "ok"


@pytest.mark.asyncio
async def test_check_s3_degraded(monkeypatch):
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket")

    class BrokenS3:
        def list_objects_v2(self, **_kwargs):
            raise RuntimeError("down")

    monkeypatch.setattr("services.s3_storage.get_s3_client", lambda: BrokenS3())

    assert await server._check_s3() == "degraded"
