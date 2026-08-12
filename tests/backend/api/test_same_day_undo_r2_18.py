"""R2-18 - put back your own mistake, on the same day, or be told why you cannot.

Lalit types the school's data all day and, by decision 4, cannot delete anything. He
will make mistakes. He and Sonu can now reverse their OWN change from TODAY. Anything
older, or anybody else's, goes to Adesh.

**The reason this refuses so much.** The plan said an undo is "a write-back of the
previous value" because audit rows carry `{field: {"previous": …, "new": …}}`, and told
whoever built it to check that shape first. Checking it found at least eight different
shapes across the write paths, most carrying no previous value at all - bulk attendance
records a count, a delete records the whole document, an import records a batch id. An
undo written against the assumed shape would have appeared to work and done nothing on
most paths, which is worse than no undo: the person believes the mistake is fixed and
walks away. So every test below that asserts a refusal is asserting the feature's main
job.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from middleware.auth import create_jwt

SCHOOL = "aaryans-joya"


def _bearer(payload: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


def _lalit():
    return _bearer({"user_id": "u-lalit", "role": "admin",
                    "sub_category": "management", "name": "Lalit Thomas"})


def _sonu():
    return _bearer({"user_id": "u-sonu", "role": "admin",
                    "sub_category": "accountant", "name": "Sonu Ruhal"})


def _now_iso(hours_ago: float = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()


def _audit(fake_db, **overrides) -> str:
    row = {
        "id": overrides.pop("id", "aud-1"),
        "schoolId": SCHOOL,
        # The names the platform's own services actually write: SINGULAR. The first
        # version of this file used the plural, which is exactly why it passed while
        # the feature refused every real edit on the platform.
        "entity_type": "student",
        "entity_id": "stu-1",
        "action": "student_update",
        "changed_by": "u-lalit",
        "changed_by_role": "admin",
        "changes": {"name": {"previous": "Aarav Sharma", "new": "Arav Sharma"}},
        "created_at": _now_iso(),
    }
    row.update(overrides)
    fake_db.audit_logs.docs.append(row)
    return row["id"]


@pytest.fixture(autouse=True)
def _a_student(fake_db):
    before_students = list(fake_db.students.docs)
    before_audit = list(fake_db.audit_logs.docs)
    fake_db.students.docs.append({
        "id": "stu-1", "schoolId": SCHOOL, "name": "Arav Sharma",
        "admission_number": "R18-1", "is_active": True, "phone": "999",
    })
    fake_db.audit_logs.docs[:] = []
    yield
    # The fake_db fixture is shared across the whole session: a file that leaves its
    # rows behind breaks an unrelated test files away.
    fake_db.students.docs[:] = before_students
    fake_db.audit_logs.docs[:] = before_audit


# ── The thing working ────────────────────────────────────────────────────────

def test_lalit_can_put_back_his_own_typo_from_today(client, fake_db):
    audit_id = _audit(fake_db)

    resp = client.post(f"/api/audit-log/my-changes-today/{audit_id}/undo", headers=_lalit())

    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["restored"] == {"name": "Aarav Sharma"}
    student = next(s for s in fake_db.students.docs if s["id"] == "stu-1")
    assert student["name"] == "Aarav Sharma"


def test_sonu_can_do_the_same(client, fake_db):
    audit_id = _audit(fake_db, changed_by="u-sonu")
    resp = client.post(f"/api/audit-log/my-changes-today/{audit_id}/undo", headers=_sonu())
    assert resp.status_code == 200


def test_an_undo_writes_its_own_entry_in_the_action_log(client, fake_db):
    # Reversing a change is itself a change. Without this, Aman's digest would show the
    # mistake and not the correction, which is the more misleading half to be missing.
    audit_id = _audit(fake_db)
    client.post(f"/api/audit-log/my-changes-today/{audit_id}/undo", headers=_lalit())

    undos = [r for r in fake_db.audit_logs.docs if r.get("action") == "undo"]
    assert len(undos) == 1
    assert undos[0]["undo_of"] == audit_id
    assert undos[0]["changed_by"] == "u-lalit"
    assert undos[0]["changes"]["name"] == {"previous": "Arav Sharma", "new": "Aarav Sharma"}


def test_the_list_shows_todays_changes_with_what_each_would_restore(client, fake_db):
    _audit(fake_db, id="aud-a")
    _audit(fake_db, id="aud-b", changes={"phone": {"previous": "888", "new": "999"}})

    resp = client.get("/api/audit-log/my-changes-today", headers=_lalit())

    assert resp.status_code == 200
    rows = {r["audit_id"]: r for r in resp.json()["data"]}
    assert rows["aud-a"]["can_undo"] is True
    assert rows["aud-b"]["would_restore"] == {"phone": "888"}


# ── The refusals, which are the point ────────────────────────────────────────

def test_somebody_elses_change_cannot_be_undone(client, fake_db):
    audit_id = _audit(fake_db, changed_by="u-adesh")
    resp = client.post(f"/api/audit-log/my-changes-today/{audit_id}/undo", headers=_lalit())
    assert resp.status_code == 422
    assert "somebody else" in resp.json()["detail"]


def test_yesterdays_change_cannot_be_undone(client, fake_db):
    audit_id = _audit(fake_db, created_at=_now_iso(hours_ago=72))
    resp = client.post(f"/api/audit-log/my-changes-today/{audit_id}/undo", headers=_lalit())
    assert resp.status_code == 422
    assert "not made today" in resp.json()["detail"]


def test_a_change_with_no_previous_value_recorded_is_refused_out_loud(client, fake_db):
    # Bulk attendance records `{"count_marked": 41, "date": …}`. There is no before-value
    # anywhere in that row. This is the shape that would have silently done nothing.
    audit_id = _audit(fake_db, changes={"count_marked": 41, "date": "2026-08-11"})
    resp = client.post(f"/api/audit-log/my-changes-today/{audit_id}/undo", headers=_lalit())
    assert resp.status_code == 422
    assert "what the value was before" in resp.json()["detail"]
    # And nothing was written.
    assert not [r for r in fake_db.audit_logs.docs if r.get("action") == "undo"]


def test_a_deletion_is_not_undone_this_way(client, fake_db):
    audit_id = _audit(fake_db, action="student_delete", changes={"deleted": {"id": "stu-1"}})
    resp = client.post(f"/api/audit-log/my-changes-today/{audit_id}/undo", headers=_lalit())
    assert resp.status_code == 422
    assert "added or removed a record" in resp.json()["detail"]


def test_money_is_never_put_back_this_way(client, fake_db):
    for field in ("fees", "salary", "amount", "fee_status"):
        audit_id = _audit(fake_db, id=f"aud-{field}",
                          changes={field: {"previous": 5000, "new": 4000}})
        resp = client.post(f"/api/audit-log/my-changes-today/{audit_id}/undo", headers=_lalit())
        assert resp.status_code == 422, f"{field} was restorable"
        assert "cannot be put back this way" in resp.json()["detail"]


def test_whether_a_child_is_on_the_roll_is_never_put_back_this_way(client, fake_db):
    # Decision 4: taking somebody off the roll belongs to the owner and the principal,
    # so putting them back on is theirs too.
    for field in ("status", "is_active", "enrolment_state"):
        audit_id = _audit(fake_db, id=f"aud-{field}",
                          changes={field: {"previous": "active", "new": "left"}})
        resp = client.post(f"/api/audit-log/my-changes-today/{audit_id}/undo", headers=_lalit())
        assert resp.status_code == 422, f"{field} was restorable"


def test_a_login_is_never_put_back_this_way(client, fake_db):
    for field in ("username", "password_hash", "role", "sub_category"):
        audit_id = _audit(fake_db, id=f"aud-{field}",
                          changes={field: {"previous": "a", "new": "b"}})
        resp = client.post(f"/api/audit-log/my-changes-today/{audit_id}/undo", headers=_lalit())
        assert resp.status_code == 422, f"{field} was restorable"


def test_only_a_student_or_staff_record_can_be_put_back(client, fake_db):
    audit_id = _audit(fake_db, collection="fee_transactions", entity_type="fee_transactions",
                      changes={"note": {"previous": "a", "new": "b"}})
    resp = client.post(f"/api/audit-log/my-changes-today/{audit_id}/undo", headers=_lalit())
    assert resp.status_code == 422
    assert "student or staff record" in resp.json()["detail"]


def test_a_protected_field_alongside_an_ordinary_one_does_not_leak_through(client, fake_db):
    # The nastiest case: one audit row touching both a name and a salary. The name may
    # go back; the salary must not, and the undo must not quietly write both.
    audit_id = _audit(fake_db, changes={
        "name": {"previous": "Aarav Sharma", "new": "Arav Sharma"},
        "salary": {"previous": 50000, "new": 90000},
    })
    resp = client.post(f"/api/audit-log/my-changes-today/{audit_id}/undo", headers=_lalit())
    assert resp.status_code == 200
    assert resp.json()["data"]["restored"] == {"name": "Aarav Sharma"}
    student = next(s for s in fake_db.students.docs if s["id"] == "stu-1")
    assert "salary" not in student, "an undo wrote back a salary"


def test_a_change_that_cannot_be_undone_still_appears_in_the_list_with_a_reason(client, fake_db):
    # A person who has just made a mistake goes looking for it. A list that quietly
    # omits it teaches them the platform has forgotten what they did.
    _audit(fake_db, id="aud-bulk", changes={"count_marked": 41})

    resp = client.get("/api/audit-log/my-changes-today", headers=_lalit())

    row = next(r for r in resp.json()["data"] if r["audit_id"] == "aud-bulk")
    assert row["can_undo"] is False
    assert row["reason"]


def test_a_record_deleted_since_the_change_is_refused_rather_than_recreated(client, fake_db):
    audit_id = _audit(fake_db, entity_id="stu-gone")
    resp = client.post(f"/api/audit-log/my-changes-today/{audit_id}/undo", headers=_lalit())
    assert resp.status_code == 422
    assert "no longer exists" in resp.json()["detail"]


# ── The two security tests every new endpoint needs ──────────────────────────

def test_undo_unauthenticated_returns_401(client):
    assert client.post("/api/audit-log/my-changes-today/x/undo").status_code == 401
    assert client.get("/api/audit-log/my-changes-today").status_code == 401


def test_a_student_cannot_reach_another_persons_change(client, fake_db):
    audit_id = _audit(fake_db)
    headers = _bearer({"user_id": "u-stu", "role": "student", "name": "S"})
    resp = client.post(f"/api/audit-log/my-changes-today/{audit_id}/undo", headers=headers)
    # Not their change, so refused. The route is open to any signed-in person on
    # purpose: it only ever shows you your own work.
    assert resp.status_code == 422
    assert "somebody else" in resp.json()["detail"]


def test_the_undo_routes_do_not_open_the_action_log(client, fake_db):
    # The action log itself stays with the owner and the principal (Aman's request 10).
    # These routes must not become a way around that.
    _audit(fake_db, id="aud-someone-else", changed_by="u-adesh")
    resp = client.get("/api/audit-log/my-changes-today", headers=_lalit())
    assert resp.status_code == 200
    assert "aud-someone-else" not in {r["audit_id"] for r in resp.json()["data"]}


# ---------------------------------------------------------------------------
# The tests that matter most: undo against the platform's REAL write paths.
#
# Everything above builds an audit row by hand, which is how the first version of this
# file passed while the feature refused every real edit on the platform: the fixture
# used the plural "students" and the services write the singular "student". A test that
# writes its own evidence proves only that the test and the code agree.
#
# These go through the actual service, then undo what it recorded.
# ---------------------------------------------------------------------------

def _actor(user_id="u-lalit", role="admin", sub_category="management"):
    from services.actor_context import ActorContext
    return ActorContext(
        user_id=user_id, role=role, sub_category=sub_category,
        school_id=SCHOOL, branch_id=None, actor_name="Lalit Thomas",
    )


async def test_a_real_student_edit_can_be_undone(client, fake_db):
    from services.student_service import update_student
    from services.undo_service import list_my_undoable_changes, undo_change

    actor = _actor()
    await update_student(fake_db, actor, {"student_id": "stu-1", "name": "Wrong Name"})

    listed = await list_my_undoable_changes(fake_db, actor)
    reversible = [row for row in listed["changes"] if row["can_undo"]]
    assert reversible, (
        "an ordinary edit made through the platform's own service could not be undone. "
        f"reasons given: {[r['reason'] for r in listed['changes']]}"
    )

    await undo_change(fake_db, actor, {"audit_id": reversible[0]["audit_id"]})
    student = next(s for s in fake_db.students.docs if s["id"] == "stu-1")
    assert student["name"] == "Arav Sharma", "the name was not put back"


async def test_a_real_staff_edit_can_be_undone(client, fake_db):
    from services.staff_service import update_staff
    from services.undo_service import list_my_undoable_changes, undo_change

    fake_db.staff.docs.append({
        "id": "stf-1", "schoolId": SCHOOL, "name": "Ramesh Kumar",
        "staff_type": "teacher", "phone": "111", "is_active": True,
    })
    actor = _actor()
    await update_staff(fake_db, actor, {"staff_id": "stf-1", "phone": "222"})

    listed = await list_my_undoable_changes(fake_db, actor)
    reversible = [r for r in listed["changes"] if r["can_undo"]]
    assert reversible, [r["reason"] for r in listed["changes"]]

    await undo_change(fake_db, actor, {"audit_id": reversible[0]["audit_id"]})
    member = next(s for s in fake_db.staff.docs if s["id"] == "stf-1")
    assert member["phone"] == "111"
    fake_db.staff.docs[:] = [s for s in fake_db.staff.docs if s.get("id") != "stf-1"]


async def test_a_real_spreadsheet_import_can_be_undone(client, fake_db):
    # The one thing Lalit does in bulk, and the most likely to need putting back. Its
    # audit row USED to record only the new values, while its own comment claimed it
    # carried the before values, so an import was the single least reversible thing on
    # the platform and nothing said so.
    from services.undo_service import explain_refusal, undoable_fields
    from datetime import datetime, timezone

    row = {
        "id": "aud-import", "schoolId": SCHOOL,
        "entity_type": "student", "entity_id": "stu-1",
        "action": "data_import_update",
        "changed_by": "u-lalit", "changed_by_role": "admin",
        "changes": {"phone": {"previous": "999", "new": "777"}},
        "import_batch": "batch-1",
        "created_at": _now_iso(),
    }
    reason = explain_refusal(row, _actor(), datetime.now(timezone.utc))
    assert reason == "", f"an import can no longer be undone: {reason}"
    assert undoable_fields(row) == {"phone": "999"}


def test_the_import_service_records_what_each_field_held_before(fake_db):
    # Pinned at the source, so the shape cannot drift back to new-values-only without
    # this failing. The comment in that file claimed this was already true; it was not.
    import inspect
    from services import data_import_service

    source = inspect.getsource(data_import_service)
    assert '"previous": (item.get("previous") or {}).get(field)' in source, (
        "the import no longer records the value each field held before it ran, so an "
        "import cannot be undone"
    )
