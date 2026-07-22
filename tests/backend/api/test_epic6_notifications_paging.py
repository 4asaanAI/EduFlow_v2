from __future__ import annotations
"""Epic 6, Story 6.2 — the notification list can be asked for more than page 1.

The compatibility pins here (test_panel_call_*) were written and shown green
against the OLD endpoint before the parameters existed, then again after. A pin
written only afterwards records what the change happened to do, not what the
panel needs.
"""

import pytest

from middleware.auth import create_jwt

SCHOOL_ID = "aaryans-joya"


@pytest.fixture(autouse=True)
def _clean(fake_db):
    for coll in ("notifications", "leave_requests", "fee_transactions", "facility_requests", "announcements"):
        getattr(fake_db, coll).docs[:] = []
    yield
    for coll in ("notifications", "leave_requests", "fee_transactions", "facility_requests", "announcements"):
        getattr(fake_db, coll).docs[:] = []


def _headers(user: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(user)}"}


def _notif(idx: int, *, user_id: str = "admin-1", read: bool = False, school_id: str = SCHOOL_ID) -> dict:
    return {
        "_id": f"e6-{user_id}-{idx}",
        "id": f"e6-{user_id}-{idx}",
        "schoolId": school_id,
        "user_id": user_id,
        "type": "info",
        "title": f"Notification {idx}",
        "message": f"Message {idx}",
        "read": read,
        "created_at": f"2026-05-15T10:{idx:02d}:00",
    }


# ── The panel's bare call must not change (readiness Q-4) ────────────────────

def test_panel_call_still_gets_digest_and_defaults(client, auth_headers, fake_db):
    """NotificationsPanel calls this with NO arguments, from the header, on every
    screen. It must still receive digest rows on page 1."""
    fake_db.notifications.docs.extend([_notif(i) for i in range(3)])
    fake_db.leave_requests.docs.append({"id": "lr-1", "schoolId": SCHOOL_ID, "status": "pending"})

    body = client.get("/api/notifications", headers=auth_headers).json()

    assert body["meta"]["page"] == 1
    assert body["meta"]["limit"] == 20
    assert body["meta"]["total"] == 3
    assert body["meta"]["digest_count"] == 1
    assert sum(1 for n in body["data"] if n.get("is_digest")) == 1


def test_panel_call_still_gets_the_all_good_fallback(client, auth_headers, fake_db):
    body = client.get("/api/notifications", headers=auth_headers).json()

    assert body["meta"]["has_fallback"] is True
    assert body["data"][0]["title"] == "All Good"


def test_panel_call_is_still_newest_first(client, auth_headers, fake_db):
    fake_db.notifications.docs.extend([_notif(i) for i in range(5)])

    data = client.get("/api/notifications", headers=auth_headers).json()["data"]

    assert [n["id"] for n in data] == [f"e6-admin-1-{i}" for i in (4, 3, 2, 1, 0)]


# ── One number, one helper (readiness Q-1) ───────────────────────────────────

def test_unread_total_and_unread_count_endpoint_agree(client, auth_headers, fake_db):
    """Seeded so the two COULD differ if they were written as separate queries:
    read and unread mixed, a digest row present, more rows than one page, and a
    second user's notifications alongside."""
    fake_db.notifications.docs.extend([_notif(i, read=(i % 3 == 0)) for i in range(25)])
    fake_db.notifications.docs.append(_notif(99, user_id="someone-else", read=False))
    fake_db.leave_requests.docs.append({"id": "lr-1", "schoolId": SCHOOL_ID, "status": "pending"})

    listed = client.get("/api/notifications?limit=5", headers=auth_headers).json()
    counted = client.get("/api/notifications/unread-count", headers=auth_headers).json()

    expected_unread = sum(1 for i in range(25) if i % 3 != 0)
    assert listed["meta"]["unread_total"] == expected_unread
    assert counted["data"]["unread_count"] == expected_unread


def test_unread_total_ignores_the_current_page(client, auth_headers, fake_db):
    fake_db.notifications.docs.extend([_notif(i) for i in range(30)])

    page_three = client.get("/api/notifications?page=3&limit=5", headers=auth_headers).json()

    assert len(page_three["data"]) == 5
    assert page_three["meta"]["unread_total"] == 30


# ── Sorting ──────────────────────────────────────────────────────────────────

def test_sort_oldest_reverses_the_order(client, auth_headers, fake_db):
    fake_db.notifications.docs.extend([_notif(i) for i in range(4)])

    data = client.get("/api/notifications?sort=oldest", headers=auth_headers).json()["data"]

    assert [n["id"] for n in data if not n.get("is_digest")] == [f"e6-admin-1-{i}" for i in (0, 1, 2, 3)]


def test_unrecognised_sort_falls_back_and_never_reaches_the_query(client, auth_headers, fake_db):
    fake_db.notifications.docs.extend([_notif(i) for i in range(3)])

    body = client.get("/api/notifications?sort=created_at;drop", headers=auth_headers).json()

    assert body["meta"]["sort"] == "newest"
    assert [n["id"] for n in body["data"] if not n.get("is_digest")] == [f"e6-admin-1-{i}" for i in (2, 1, 0)]


# ── Filtering, and keeping fabricated rows out of a table (readiness Q-5) ────

def test_unread_only_excludes_read_rows(client, auth_headers, fake_db):
    fake_db.notifications.docs.extend([_notif(0, read=True), _notif(1, read=False), _notif(2, read=True)])

    body = client.get("/api/notifications?unread_only=true", headers=auth_headers).json()

    assert [n["id"] for n in body["data"]] == ["e6-admin-1-1"]
    assert body["meta"]["total"] == 1


def test_unread_only_admits_no_digest_and_no_fallback(client, auth_headers, fake_db):
    """The digest and the fallback are read by construction, so "unread" can never
    legitimately be satisfied by one."""
    fake_db.leave_requests.docs.append({"id": "lr-1", "schoolId": SCHOOL_ID, "status": "pending"})

    body = client.get("/api/notifications?unread_only=true", headers=auth_headers).json()

    assert body["data"] == []
    assert body["meta"]["digest_count"] == 0
    assert body["meta"]["has_fallback"] is False


def test_include_digest_false_returns_records_only(client, auth_headers, fake_db):
    """What the All Notifications page passes. A synthetic row inside a table with
    a row count and a page indicator is a fabricated record among real ones."""
    fake_db.notifications.docs.extend([_notif(i) for i in range(2)])
    fake_db.leave_requests.docs.append({"id": "lr-1", "schoolId": SCHOOL_ID, "status": "pending"})

    body = client.get("/api/notifications?include_digest=false", headers=auth_headers).json()

    assert len(body["data"]) == 2
    assert all(not n.get("is_digest") for n in body["data"])
    assert body["meta"]["digest_count"] == 0


def test_include_digest_false_never_invents_an_all_good_row(client, auth_headers, fake_db):
    """The worst case: an empty page rendering a fabricated notification that says
    everything is fine."""
    body = client.get("/api/notifications?include_digest=false", headers=auth_headers).json()

    assert body["data"] == []
    assert body["meta"]["has_fallback"] is False


# ── Clamping ─────────────────────────────────────────────────────────────────

def test_limit_is_clamped_server_side(client, auth_headers, fake_db):
    fake_db.notifications.docs.extend([_notif(i) for i in range(60)])

    body = client.get("/api/notifications?limit=5000&include_digest=false", headers=auth_headers).json()

    assert body["meta"]["limit"] == 50
    assert len(body["data"]) == 50


# ── Standing endpoint conventions ────────────────────────────────────────────

def test_notifications_unauthenticated_returns_401(client):
    assert client.get("/api/notifications").status_code == 401


def test_unread_count_unauthenticated_returns_401(client):
    assert client.get("/api/notifications/unread-count").status_code == 401


def test_one_user_cannot_read_or_count_anothers_notifications(client, fake_db):
    """Stands in for the usual 403-wrong-role test. These endpoints are scoped to
    the caller's own user_id rather than gated by role, so there is no wrong role
    to send — the boundary being defended is between users, not between roles."""
    fake_db.notifications.docs.extend([
        _notif(1, user_id="admin-1", read=False),
        _notif(2, user_id="admin-1", read=False),
        _notif(3, user_id="teacher-9", read=False),
    ])
    theirs = _headers({"user_id": "teacher-9", "role": "teacher", "name": "T"})

    listed = client.get("/api/notifications?include_digest=false", headers=theirs).json()
    counted = client.get("/api/notifications/unread-count", headers=theirs).json()

    assert [n["id"] for n in listed["data"]] == ["e6-teacher-9-3"]
    assert listed["meta"]["total"] == 1
    assert listed["meta"]["unread_total"] == 1
    assert counted["data"]["unread_count"] == 1


def test_paging_and_filtering_cannot_reach_another_user(client, fake_db):
    """The new parameters are the obvious way to try to walk out of your own scope."""
    fake_db.notifications.docs.extend([_notif(i, user_id="admin-1") for i in range(10)])
    theirs = _headers({"user_id": "teacher-9", "role": "teacher", "name": "T"})

    for query in ("page=1&limit=50", "sort=oldest", "unread_only=true", "include_digest=false"):
        body = client.get(f"/api/notifications?{query}", headers=theirs).json()
        assert all(n.get("is_digest") or n["user_id"] == "teacher-9" for n in body["data"]), query
        assert body["meta"]["total"] == 0, query


def test_notifications_are_school_scoped(client, auth_headers, fake_db):
    fake_db.notifications.docs.extend([
        _notif(1, user_id="admin-1"),
        _notif(2, user_id="admin-1", school_id="other-school"),
    ])

    body = client.get("/api/notifications?include_digest=false", headers=auth_headers).json()

    assert [n["id"] for n in body["data"]] == ["e6-admin-1-1"]
