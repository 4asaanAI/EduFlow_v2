from __future__ import annotations

import logging

import pytest

from services import audit_service
from services.audit_service import write_audit


class BrokenAuditLogs:
    async def insert_one(self, _doc):
        raise RuntimeError("audit db down")


class BrokenDb:
    audit_logs = BrokenAuditLogs()


@pytest.mark.asyncio
async def test_write_audit_writes_consistent_document(fake_db):
    fake_db.audit_logs.docs[:] = []

    result = await write_audit(
        fake_db,
        action="thing_update",
        entity_id="thing-1",
        collection="things",
        changed_by="admin-1",
        changed_by_role="owner",
        school_id="aaryans-joya",
        branch_id="branch-1",
        changes={"name": "New"},
        reason="test",
    )

    assert result is True
    doc = fake_db.audit_logs.docs[-1]
    assert doc["action"] == "thing_update"
    assert doc["entity_id"] == "thing-1"
    assert doc["collection"] == "things"
    assert doc["entity_type"] == "things"
    assert doc["changed_by"] == "admin-1"
    assert doc["changed_by_role"] == "owner"
    assert doc["schoolId"] == "aaryans-joya"
    assert doc["branch_id"] == "branch-1"
    assert doc["changes"] == {"name": "New"}
    assert doc["reason"] == "test"
    assert "created_at" in doc


@pytest.mark.asyncio
async def test_write_audit_defaults_branch_id(fake_db):
    fake_db.audit_logs.docs[:] = []

    await write_audit(
        fake_db,
        action="thing_create",
        entity_id="thing-2",
        collection="things",
        changed_by="admin-1",
        changed_by_role="owner",
        school_id="aaryans-joya",
    )

    assert fake_db.audit_logs.docs[-1]["branch_id"] == ""


@pytest.mark.asyncio
async def test_write_audit_failure_is_fail_open_and_logs_warning(caplog):
    audit_service._audit_failure_count = 0
    caplog.set_level(logging.WARNING, logger=audit_service.logger.name)

    result = await write_audit(
        BrokenDb(),
        action="thing_update",
        entity_id="thing-1",
        collection="things",
        changed_by="admin-1",
        changed_by_role="owner",
        school_id="aaryans-joya",
    )

    assert result is False
    assert "audit_write_failed" in caplog.text


@pytest.mark.asyncio
async def test_write_audit_persistent_failure_escalates_to_error(caplog):
    audit_service._audit_failure_count = audit_service.AUDIT_FAILURE_ALERT_THRESHOLD
    caplog.set_level(logging.ERROR, logger=audit_service.logger.name)

    result = await write_audit(
        BrokenDb(),
        action="thing_update",
        entity_id="thing-1",
        collection="things",
        changed_by="admin-1",
        changed_by_role="owner",
        school_id="aaryans-joya",
    )

    assert result is False
    assert "audit_write_failed" in caplog.text
    assert any(getattr(record, "persistent_audit_failure", False) for record in caplog.records)
