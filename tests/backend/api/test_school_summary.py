"""The whole school on one page, for the two people who run it.

Abhimanyu, 2026-08-12: build the scheduled reports, at least for Aman and Adesh, so they
have a summary of everything in one place.

The two things worth pinning are what "scheduled" honestly means here, and who may read
it. There is no scheduler on this platform, so the day's page is produced the first time
one of them opens it and then KEPT. Yesterday's is never rebuilt from today's figures,
which would quietly rewrite history.
"""

from __future__ import annotations

import pytest

from middleware.auth import create_jwt


def _headers(claims):
    return {"Authorization": "Bearer " + create_jwt({**claims, "schoolId": "aaryans-joya"})}


OWNER = {"user_id": "aman", "role": "owner", "name": "Aman"}
PRINCIPAL = {"user_id": "adesh", "role": "admin", "sub_category": "principal", "name": "Adesh"}
REFUSED = {
    "accountant": {"user_id": "sonu", "role": "admin", "sub_category": "accountant"},
    "management": {"user_id": "lalit", "role": "admin", "sub_category": "management"},
    "teacher": {"user_id": "t", "role": "teacher"},
    "receptionist": {"user_id": "r", "role": "admin", "sub_category": "receptionist"},
}


@pytest.fixture(autouse=True)
def _clean(fake_db):
    names = ("students", "staff", "student_attendance", "fee_transactions", "audit_logs",
             "school_summaries", "certificates", "leave_requests", "approval_requests",
             "pending_discount_approvals")
    originals = {name: list(getattr(fake_db, name).docs) for name in names}
    for name in names:
        getattr(fake_db, name).docs[:] = []
    yield
    for name, docs in originals.items():
        getattr(fake_db, name).docs[:] = docs


def _seed(fake_db, day):
    fake_db.students.docs.extend([
        {"_id": f"s{i}", "id": f"s{i}", "schoolId": "aaryans-joya", "is_active": True,
         "name": f"Child {i}"} for i in range(3)
    ])
    fake_db.staff.docs.append({"_id": "st1", "id": "st1", "schoolId": "aaryans-joya"})
    fake_db.student_attendance.docs.extend([
        {"_id": "a1", "id": "a1", "schoolId": "aaryans-joya", "date": day, "status": "present"},
        {"_id": "a2", "id": "a2", "schoolId": "aaryans-joya", "date": day, "status": "present"},
        {"_id": "a3", "id": "a3", "schoolId": "aaryans-joya", "date": day, "status": "absent"},
    ])
    fake_db.fee_transactions.docs.extend([
        {"_id": "f1", "id": "f1", "schoolId": "aaryans-joya", "student_id": "s0",
         "payment_date": day, "paid_amount": 9750, "status": "paid", "amount": 9750},
        {"_id": "f2", "id": "f2", "schoolId": "aaryans-joya", "student_id": "s1",
         "status": "pending", "amount": 9750, "paid_amount": 0, "due_date": "2020-04-15"},
    ])
    fake_db.certificates.docs.append(
        {"_id": "c1", "id": "c1", "schoolId": "aaryans-joya", "status": "pending_approval"})


def _today(client):
    return client.get("/api/audit-log/school-summary", headers=_headers(OWNER))


def test_the_two_who_run_the_school_get_the_whole_page(client, fake_db):
    from services.school_summary_service import _today_iso
    from services.actor_context import actor_ctx_from_user

    day = _today_iso(actor_ctx_from_user(OWNER | {"id": "aman"}, school_id="aaryans-joya"))
    _seed(fake_db, day)

    data = _today(client).json()["data"]
    assert data["school"]["students_on_the_roll"] == 3
    assert data["attendance"]["present"] == 2
    assert data["attendance"]["absent"] == 1
    assert data["money"]["collected_today"] == 9750
    assert data["money"]["outstanding_in_total"] == 9750
    assert data["money"]["bills_past_their_due_date"] == 1
    assert data["waiting_for_you"]["documents_awaiting_approval"] == 1
    assert data["waiting_for_you"]["total"] == 1

    # The same page in plain words, so it can be read, printed, or sent the day a sender
    # the school can actually use exists.
    assert "The Aaryans, Joya" in data["text"]
    assert "Waiting for you" in data["text"]


def test_the_principal_gets_it_too(client, fake_db):
    assert client.get("/api/audit-log/school-summary",
                      headers=_headers(PRINCIPAL)).status_code == 200


@pytest.mark.parametrize("who", sorted(REFUSED))
def test_nobody_else_gets_it_including_the_accountant_head(client, fake_db, who):
    # The accountant head runs the school's money and still does not get this page: it
    # carries the roll and everyone's changes as well. Each of them has the half that is
    # theirs; this is the whole.
    out = client.get("/api/audit-log/school-summary", headers=_headers(REFUSED[who]))
    assert out.status_code == 403


def test_no_authorization_header_is_refused(client, fake_db):
    assert client.get("/api/audit-log/school-summary").status_code == 401


def test_the_day_is_produced_once_and_then_kept(client, fake_db):
    # THIS is what "scheduled" means here: no cron exists, so the page is produced the
    # first time one of them opens it and kept exactly as produced.
    first = _today(client).json()["data"]
    assert first["freshly_produced"] is True
    assert len(fake_db.school_summaries.docs) == 1

    # Something changes after the summary was produced.
    fake_db.students.docs.append(
        {"_id": "late", "id": "late", "schoolId": "aaryans-joya", "is_active": True})

    second = _today(client).json()["data"]
    assert second["freshly_produced"] is False
    assert second["school"] == first["school"]
    assert len(fake_db.school_summaries.docs) == 1


def test_a_day_with_no_summary_kept_is_not_rebuilt_from_todays_figures(client, fake_db):
    out = client.get("/api/audit-log/school-summary?day=2020-01-01", headers=_headers(OWNER))
    data = out.json()["data"]
    assert data["not_kept"] is True
    assert "wrong day" in data["note"]
    assert fake_db.school_summaries.docs == []


def test_the_history_lists_the_days_that_were_kept(client, fake_db):
    _today(client)
    out = client.get("/api/audit-log/school-summary/history", headers=_headers(OWNER))
    assert out.status_code == 200
    assert out.json()["meta"]["count"] == 1


def test_a_day_with_no_attendance_says_so_rather_than_showing_zero_percent(client, fake_db):
    # Zero percent present reads as a catastrophe. Not marked yet reads as the truth.
    data = _today(client).json()["data"]
    assert data["attendance"]["marked"] is False
    assert "not marked yet" in data["text"]
