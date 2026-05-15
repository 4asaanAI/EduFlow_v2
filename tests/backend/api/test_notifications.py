from __future__ import annotations

from middleware.auth import create_jwt


SCHOOL_ID = "aaryans-joya"


def _reset_notification_state(fake_db):
    fake_db.notifications.docs[:] = []
    fake_db.leave_requests.docs[:] = []
    fake_db.fee_transactions.docs[:] = []
    fake_db.facility_requests.docs[:] = []
    fake_db.announcements.docs[:] = []


def _auth_headers(user: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(user)}"}


def _notification(idx: int, *, user_id: str = "admin-1", read: bool = False, created_at: str | None = None) -> dict:
    return {
        "_id": f"n-{idx}",
        "id": f"n-{idx}",
        "schoolId": SCHOOL_ID,
        "user_id": user_id,
        "type": "info",
        "title": f"Notification {idx}",
        "message": f"Message {idx}",
        "read": read,
        "created_at": created_at or f"2026-05-15T10:{idx:02d}:00",
    }


def test_get_notifications_total_excludes_digest_items(client, auth_headers, fake_db):
    _reset_notification_state(fake_db)
    fake_db.notifications.docs.extend([_notification(i) for i in range(5)])
    fake_db.leave_requests.docs.append({"id": "leave-1", "schoolId": SCHOOL_ID, "status": "pending"})
    fake_db.fee_transactions.docs.append({"id": "fee-1", "schoolId": SCHOOL_ID, "status": "overdue"})
    fake_db.facility_requests.docs.append({"id": "fac-1", "schoolId": SCHOOL_ID, "status": "open"})

    resp = client.get("/api/notifications", headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["total"] == 5
    assert body["meta"]["digest_count"] == 3
    assert body["meta"]["has_fallback"] is False
    assert len(body["data"]) == 8
    assert sum(1 for item in body["data"] if item.get("is_digest")) == 3


def test_get_notifications_page_two_has_no_digest(client, auth_headers, fake_db):
    _reset_notification_state(fake_db)
    fake_db.notifications.docs.extend([_notification(i) for i in range(30)])
    fake_db.leave_requests.docs.append({"id": "leave-1", "schoolId": SCHOOL_ID, "status": "pending"})

    resp = client.get("/api/notifications?page=2&limit=10", headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["total"] == 30
    assert body["meta"]["digest_count"] == 0
    assert all(not item.get("is_digest") for item in body["data"])


def test_get_notifications_all_good_fallback_meta(client, auth_headers, fake_db):
    _reset_notification_state(fake_db)

    resp = client.get("/api/notifications", headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"] == {
        "page": 1,
        "limit": 20,
        "total": 0,
        "digest_count": 0,
        "has_fallback": True,
    }
    assert body["data"][0]["title"] == "All Good"


def test_get_notifications_digest_is_school_scoped(client, auth_headers, fake_db):
    _reset_notification_state(fake_db)
    fake_db.leave_requests.docs.append({"id": "foreign-leave", "schoolId": "other-school", "status": "pending"})
    fake_db.fee_transactions.docs.append({"id": "foreign-fee", "schoolId": "other-school", "status": "overdue"})
    fake_db.facility_requests.docs.append({"id": "foreign-facility", "schoolId": "other-school", "status": "open"})
    fake_db.announcements.docs.append({
        "id": "foreign-ann",
        "schoolId": "other-school",
        "title": "Foreign announcement",
        "audience_roles": ["owner"],
        "created_at": "2026-05-15T08:00:00",
    })

    resp = client.get("/api/notifications", headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["digest_count"] == 0
    assert body["meta"]["has_fallback"] is True
    assert body["data"][0]["title"] == "All Good"


def test_unread_count_only_counts_current_user(client, auth_headers, fake_db):
    _reset_notification_state(fake_db)
    fake_db.notifications.docs.extend([
        _notification(1, read=False),
        _notification(2, read=True),
        _notification(3, user_id="other-user", read=False),
    ])

    resp = client.get("/api/notifications/unread-count", headers=auth_headers)

    assert resp.status_code == 200
    assert resp.json()["data"]["unread_count"] == 1


def test_mark_notification_read_requires_current_user(client, auth_headers, fake_db):
    _reset_notification_state(fake_db)
    fake_db.notifications.docs.append(_notification(1, user_id="other-user", read=False))

    resp = client.patch("/api/notifications/n-1/read", headers=auth_headers)

    assert resp.status_code == 404
    assert fake_db.notifications.docs[0]["read"] is False


def test_mark_all_read_is_idempotent(client, auth_headers, fake_db):
    _reset_notification_state(fake_db)
    fake_db.notifications.docs.extend([
        _notification(1, read=False, created_at="2026-05-15T09:00:00"),
        _notification(2, read=False, created_at="2026-05-15T09:01:00"),
    ])

    first = client.patch("/api/notifications/mark-all-read", headers=auth_headers)
    second = client.patch("/api/notifications/mark-all-read", headers=auth_headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert all(doc["read"] is True for doc in fake_db.notifications.docs)


def test_mark_all_read_does_not_mark_boundary_notification(client, auth_headers, fake_db, monkeypatch):
    import routes.notifications as notifications_route

    class FixedDateTime:
        @classmethod
        def now(cls):
            return cls()

        def isoformat(self):
            return "2026-05-15T10:00:00"

    _reset_notification_state(fake_db)
    fake_db.notifications.docs.extend([
        _notification(1, read=False, created_at="2026-05-15T09:59:59"),
        _notification(2, read=False, created_at="2026-05-15T10:00:00"),
    ])
    monkeypatch.setattr(notifications_route, "datetime", FixedDateTime)

    resp = client.patch("/api/notifications/mark-all-read", headers=auth_headers)

    assert resp.status_code == 200
    assert fake_db.notifications.docs[0]["read"] is True
    assert fake_db.notifications.docs[1]["read"] is False


def test_create_notification_requires_owner_or_admin(client, fake_db):
    _reset_notification_state(fake_db)
    headers = _auth_headers({"id": "teacher-1", "role": "teacher", "name": "Teacher"})

    resp = client.post(
        "/api/notifications",
        headers=headers,
        json={"user_id": "admin-1", "title": "Title", "message": "Message"},
    )

    assert resp.status_code == 403
    assert fake_db.notifications.docs == []


def test_create_notification_requires_title(client, auth_headers, fake_db):
    _reset_notification_state(fake_db)

    resp = client.post(
        "/api/notifications",
        headers=auth_headers,
        json={"user_id": "admin-1", "message": "Message"},
    )

    assert resp.status_code == 400
    assert fake_db.notifications.docs == []


def test_create_notification_persists_standard_shape(client, auth_headers, fake_db):
    _reset_notification_state(fake_db)

    resp = client.post(
        "/api/notifications",
        headers=auth_headers,
        json={
            "user_id": "admin-1",
            "type": "info",
            "title": "Title",
            "message": "Message",
            "source_record_id": "record-1",
            "source_record_type": "test",
        },
    )

    assert resp.status_code == 200
    doc = fake_db.notifications.docs[0]
    assert doc["schoolId"] == SCHOOL_ID
    assert doc["user_id"] == "admin-1"
    assert doc["title"] == "Title"
    assert doc["message"] == "Message"
    assert doc["source_record_id"] == "record-1"
    assert doc["source_record_type"] == "test"
