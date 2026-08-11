"""R2-15 - the day in one page for Aman and Adesh.

Aman asked that everything on the platform be visible to him. Today that means
remembering to open the Audit Log and read it row by row. This is the same rows, told
as a summary: who did what, how much, and the handful of things worth a second look.

Two things these tests hold on to:

* **It is the action log, so it is gated like the action log.** The owner and the
  principal, nobody else (Aman's request 10 of 2026-08-06, reconfirmed 2026-08-10). A
  summary of rows you may not read is still those rows.
* **A cap must never read as "that was everything".** The list of things to look at is
  capped so the digest stays short enough to be read, and it says out loud how many it
  did not show.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from middleware.auth import create_jwt

SCHOOL = "aaryans-joya"


def _bearer(payload: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


def _owner():
    return _bearer({"user_id": "d-owner", "role": "owner", "sub_category": "owner", "name": "Aman"})


def _principal():
    return _bearer({"user_id": "d-prin", "role": "admin", "sub_category": "principal", "name": "Adesh"})


def _iso(hours_ago: float = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()


@pytest.fixture(autouse=True)
def _clean_audit(fake_db):
    before_audit = list(fake_db.audit_logs.docs)
    before_users = list(fake_db.users.docs)
    fake_db.audit_logs.docs[:] = []
    fake_db.users.docs.extend([
        {"id": "u-lalit", "schoolId": SCHOOL, "name": "Lalit Thomas",
         "role": "admin", "sub_category": "management"},
        {"id": "u-sonu", "schoolId": SCHOOL, "name": "Sonu Ruhal",
         "role": "admin", "sub_category": "accountant"},
    ])
    yield
    fake_db.audit_logs.docs[:] = before_audit
    fake_db.users.docs[:] = before_users


def _row(fake_db, **overrides):
    row = {
        "id": f"a-{len(fake_db.audit_logs.docs)}",
        "schoolId": SCHOOL,
        "entity_type": "students",
        "collection": "students",
        "entity_id": "stu-1",
        "action": "student_update",
        "changed_by": "u-lalit",
        "changed_by_role": "admin",
        "changes": {},
        "created_at": _iso(1),
    }
    row.update(overrides)
    fake_db.audit_logs.docs.append(row)
    return row


def test_a_quiet_day_says_so_rather_than_showing_an_empty_page(client, fake_db):
    resp = client.get("/api/audit-log/daily-digest", headers=_owner())
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["quiet_day"] is True
    assert data["text"] == "Nothing was changed on the platform in the last day."


def test_the_digest_counts_by_person_and_names_them(client, fake_db):
    for _ in range(3):
        _row(fake_db)
    _row(fake_db, changed_by="u-sonu", action="fee_payment_recorded",
         entity_type="fee_transactions", collection="fee_transactions")

    data = client.get("/api/audit-log/daily-digest", headers=_owner()).json()["data"]

    assert data["total_changes"] == 4
    by_person = {p["name"]: p["total"] for p in data["by_person"]}
    assert by_person == {"Lalit Thomas": 3, "Sonu Ruhal": 1}
    # Machine names like `student_update` must not reach the school's owner.
    assert "student_update" not in data["text"]
    assert "edited" in data["text"]


def test_money_activity_is_counted_separately(client, fake_db):
    _row(fake_db, changed_by="u-sonu", entity_type="fee_transactions",
         collection="fee_transactions", action="fee_payment_recorded")
    _row(fake_db)
    data = client.get("/api/audit-log/daily-digest", headers=_owner()).json()["data"]
    assert data["money_changes"] == 1


def test_the_things_worth_looking_at_are_picked_out(client, fake_db):
    _row(fake_db, action="student_update")
    _row(fake_db, action="student_delete", reason="left the school")
    _row(fake_db, action="undo")

    data = client.get("/api/audit-log/daily-digest", headers=_owner()).json()["data"]

    what = {item["what"] for item in data["noteworthy"]}
    assert "a record was removed" in what
    assert "somebody put their own change back" in what
    assert len(data["noteworthy"]) == 2, "an ordinary edit was flagged as noteworthy"
    assert "left the school" in data["text"], "the reason somebody gave was not shown"


def test_a_capped_list_says_how_many_it_did_not_show(client, fake_db):
    # A silent cap reads as "that was everything", which is the one thing a summary of
    # oversight must never imply.
    for _ in range(20):
        _row(fake_db, action="student_delete")

    data = client.get("/api/audit-log/daily-digest", headers=_owner()).json()["data"]

    assert len(data["noteworthy"]) == 15
    assert data["noteworthy_total"] == 20
    assert "and 5 more" in data["text"]


def test_yesterdays_activity_is_not_counted_in_todays_digest(client, fake_db):
    _row(fake_db, created_at=_iso(hours_ago=40))
    _row(fake_db, created_at=_iso(hours_ago=2))

    data = client.get("/api/audit-log/daily-digest", headers=_owner()).json()["data"]
    assert data["total_changes"] == 1


def test_the_window_can_be_widened_but_not_without_limit(client, fake_db):
    _row(fake_db, created_at=_iso(hours_ago=40))

    week = client.get("/api/audit-log/daily-digest?hours=168", headers=_owner()).json()["data"]
    assert week["total_changes"] == 1

    # An unbounded window over the highest-volume collection on the platform is a way to
    # ask the database for everything it has ever recorded.
    huge = client.get("/api/audit-log/daily-digest?hours=99999", headers=_owner()).json()["data"]
    assert huge["window_hours"] == 168


def test_somebody_no_longer_on_the_platform_is_still_accounted_for(client, fake_db):
    # Their name is gone; what they did is not, and a digest that dropped the row would
    # be a summary with a hole in it.
    _row(fake_db, changed_by="u-departed")
    data = client.get("/api/audit-log/daily-digest", headers=_owner()).json()["data"]
    assert data["total_changes"] == 1
    assert data["by_person"][0]["name"] == "Somebody no longer on the platform"


# ── It is the action log, so it is gated like the action log ─────────────────

def test_the_principal_gets_the_digest(client, fake_db):
    assert client.get("/api/audit-log/daily-digest", headers=_principal()).status_code == 200


def test_digest_unauthenticated_returns_401(client):
    assert client.get("/api/audit-log/daily-digest").status_code == 401


@pytest.mark.parametrize("sub_category", [
    "accountant", "management", "receptionist", "it_tech",
    "maintenance", "transport_head", "support_staff",
])
def test_nobody_below_the_principal_can_read_the_digest(client, fake_db, sub_category):
    headers = _bearer({"user_id": "d-x", "role": "admin",
                       "sub_category": sub_category, "name": "X"})
    resp = client.get("/api/audit-log/daily-digest", headers=headers)
    assert resp.status_code == 403, (
        f"{sub_category} read a summary of the action log, which is the owner's and the "
        "principal's only"
    )


def test_a_teacher_cannot_read_the_digest(client, fake_db):
    headers = _bearer({"user_id": "d-t", "role": "teacher", "name": "T"})
    assert client.get("/api/audit-log/daily-digest", headers=headers).status_code == 403
