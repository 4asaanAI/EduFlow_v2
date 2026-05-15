"""Unit tests for the canonical notification writer."""

from __future__ import annotations

import logging

import pytest

from services import notification_service
from services.notification_service import create_notification


class Notifications:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.docs = []
        self.insert_attempted = False

    async def insert_one(self, doc):
        self.insert_attempted = True
        if self.fail:
            raise RuntimeError("db unavailable")
        self.docs.append(doc)


class Db:
    def __init__(self, *, fail: bool = False):
        self.notifications = Notifications(fail=fail)


@pytest.mark.asyncio
async def test_create_notification_inserts_standard_shape():
    db = Db()

    result = await create_notification(
        db,
        user_id="user-1",
        notification_type="leave_decision",
        title="Leave request updated",
        message="Leave request approved",
        source_id="leave-1",
        source_type="leave_request",
        school_id="school-1",
    )

    assert result is True
    doc = db.notifications.docs[0]
    assert doc["schoolId"] == "school-1"
    assert doc["user_id"] == "user-1"
    assert doc["type"] == "leave_decision"
    assert doc["title"] == "Leave request updated"
    assert doc["message"] == "Leave request approved"
    assert doc["source_record_id"] == "leave-1"
    assert doc["source_record_type"] == "leave_request"
    assert doc["read"] is False
    assert doc["created_at"]


@pytest.mark.asyncio
async def test_create_notification_defaults_title_to_message():
    db = Db()

    result = await create_notification(
        db,
        user_id="user-1",
        notification_type="info",
        message="Message-only notification",
        school_id="school-1",
    )

    assert result is True
    assert db.notifications.docs[0]["title"] == "Message-only notification"


@pytest.mark.asyncio
async def test_create_notification_skips_empty_user_id(caplog):
    db = Db()

    with caplog.at_level(logging.WARNING):
        result = await create_notification(
            db,
            user_id="",
            notification_type="info",
            title="Missing user",
            message="No target",
        )

    assert result is False
    assert db.notifications.insert_attempted is False
    assert any(getattr(record, "notification_delivery_failed", False) for record in caplog.records)


@pytest.mark.asyncio
async def test_create_notification_skips_none_user_id():
    db = Db()

    result = await create_notification(
        db,
        user_id=None,
        notification_type="info",
        title="Missing user",
        message="No target",
    )

    assert result is False
    assert db.notifications.insert_attempted is False


@pytest.mark.asyncio
async def test_create_notification_db_error_logs_and_returns_false(caplog):
    db = Db(fail=True)

    with caplog.at_level(logging.WARNING):
        result = await create_notification(
            db,
            user_id="user-1",
            notification_type="info",
            title="Write failure",
            message="This should fail open",
        )

    assert result is False
    assert any(record.message == "notification_write_failed" for record in caplog.records)
    assert any(getattr(record, "notification_delivery_failed", False) for record in caplog.records)


@pytest.mark.asyncio
async def test_fan_out_notifications_attempts_all_targets():
    db = Db()

    result = await notification_service.fan_out_notifications(
        db,
        [f"user-{idx}" for idx in range(20)],
        notification_type="info",
        title="Bulk",
        message="Bulk message",
        school_id="school-1",
    )

    assert result == {"sent": 20, "failed": 0}
    assert len(db.notifications.docs) == 20


@pytest.mark.asyncio
async def test_fan_out_notifications_counts_false_failures(monkeypatch):
    async def fake_create_notification(db, **kwargs):
        return kwargs["user_id"] not in {"user-2", "user-4"}

    monkeypatch.setattr(notification_service, "create_notification", fake_create_notification)

    result = await notification_service.fan_out_notifications(
        Db(),
        ["user-1", "user-2", "user-3", "user-4"],
        notification_type="info",
        title="Bulk",
        message="Bulk message",
    )

    assert result == {"sent": 2, "failed": 2}


@pytest.mark.asyncio
async def test_fan_out_notifications_counts_exceptions(monkeypatch):
    async def fake_create_notification(db, **kwargs):
        if kwargs["user_id"] == "user-2":
            raise RuntimeError("boom")
        return True

    monkeypatch.setattr(notification_service, "create_notification", fake_create_notification)

    result = await notification_service.fan_out_notifications(
        Db(),
        ["user-1", "user-2", "user-3"],
        notification_type="info",
        title="Bulk",
        message="Bulk message",
    )

    assert result == {"sent": 2, "failed": 1}
