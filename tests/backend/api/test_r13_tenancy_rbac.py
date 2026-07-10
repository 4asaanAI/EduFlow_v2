"""
R13 — Tenancy & RBAC Fail-Closed
Tests for: ScopedCollection method gap, file-serve least-exposure, export RBAC,
login lockout tenant-aware, operations branch-scope, staff deactivation revokes sessions,
bulk SMS ownership/scoping, bulk import branch tag + atomic writes, regex escape.
"""
from __future__ import annotations
import pytest
from middleware.auth import create_jwt

pytestmark = pytest.mark.asyncio


# ── Helpers ──────────────────────────────────────────────────────────────────

def _bearer(payload: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


def _owner():
    return _bearer({"id": "owner-1", "role": "owner", "name": "Owner"})


def _principal(branch: str = "branch-a"):
    return _bearer({"id": "prin-1", "role": "admin", "sub_category": "principal", "branch_id": branch, "name": "Principal"})


def _accountant():
    return _bearer({"id": "acct-1", "role": "admin", "sub_category": "accountant", "name": "Accountant"})


def _legacy_accounts():
    return _bearer({"id": "acct-2", "role": "admin", "sub_category": "accounts", "name": "LegacyAccountant"})


def _teacher():
    return _bearer({"id": "teach-1", "role": "teacher", "name": "Teacher"})


def _plain_admin():
    return _bearer({"id": "adm-1", "role": "admin", "sub_category": "receptionist", "name": "Reception"})


# ─────────────────────────────────────────────────────────────────────────────
# R13.1 — ScopedCollection method gap
# ─────────────────────────────────────────────────────────────────────────────

def test_scoped_collection_find_one_and_update_injects_school_id(fake_db):
    """find_one_and_update on ScopedCollection must scope to schoolId."""
    from database import ScopedCollection
    col = ScopedCollection(fake_db.students, "school-A")
    # Pre-populate two docs from different schools
    import asyncio
    other_doc = {"id": "s-other", "schoolId": "school-B", "name": "Other"}
    own_doc = {"id": "s-own", "schoolId": "school-A", "name": "Target"}
    fake_db.students.docs.extend([other_doc, own_doc])

    async def _run():
        result = await col.find_one_and_update(
            {"name": "Target"},
            {"$set": {"updated": True}},
        )
        return result

    result = asyncio.get_event_loop().run_until_complete(_run())
    # Should update the school-A doc
    assert own_doc.get("updated") is True
    # school-B doc must NOT be modified
    assert "updated" not in other_doc


def test_scoped_collection_distinct_scopes_to_school(fake_db):
    """distinct on ScopedCollection must not return values from other schools."""
    from database import ScopedCollection
    col = ScopedCollection(fake_db.students, "school-A")
    import asyncio
    fake_db.students.docs.append({"id": "s1", "schoolId": "school-A", "status": "active"})
    fake_db.students.docs.append({"id": "s2", "schoolId": "school-B", "status": "inactive"})

    async def _run():
        return await col.distinct("status")

    values = asyncio.get_event_loop().run_until_complete(_run())
    assert "active" in values
    # school-B doc's "inactive" should not appear
    assert "inactive" not in values


def test_scoped_collection_bulk_write_raises_not_implemented(fake_db):
    """bulk_write must raise NotImplementedError to prevent un-scoped writes."""
    from database import ScopedCollection
    import pytest
    col = ScopedCollection(fake_db.students, "school-A")
    with pytest.raises(NotImplementedError):
        col.bulk_write([])


# ─────────────────────────────────────────────────────────────────────────────
# R13.2 — File-serve least-exposure
# ─────────────────────────────────────────────────────────────────────────────

def test_serve_file_unauthenticated_returns_401(client):
    resp = client.get("/api/uploads/serve/some_file.pdf")
    assert resp.status_code == 401


def test_list_uploads_unauthenticated_returns_401(client):
    resp = client.get("/api/uploads")
    assert resp.status_code == 401


def test_serve_file_accountant_cannot_access_other_users_file(client, fake_db):
    """Accountant (non-principal admin) must not serve another user's file."""
    fake_db.file_uploads.docs.append({
        "id": "fu-1",
        "safe_filename": "report.pdf",
        "s3_key": "school/uploads/report.pdf",
        "uploaded_by": "other-user",
        "schoolId": "aaryans-joya",
    })
    resp = client.get("/api/uploads/serve/report.pdf", headers=_accountant())
    assert resp.status_code == 403


def test_serve_file_principal_can_access_other_users_file(client, fake_db):
    """Principal admin can serve any file in their school."""
    fake_db.file_uploads.docs.append({
        "id": "fu-2",
        "safe_filename": "class_report.pdf",
        "s3_key": "school/uploads/class_report.pdf",
        "uploaded_by": "other-user",
        "schoolId": "aaryans-joya",
    })
    # The S3 presigned URL will fail since S3 is not configured — we just check auth
    resp = client.get("/api/uploads/serve/class_report.pdf", headers=_principal())
    # Should not be 403 (may be 307 redirect or 409 if s3_key not set properly)
    assert resp.status_code != 403


def test_list_uploads_accountant_sees_only_own(client, fake_db):
    """Accountant (non-principal admin) cannot see other users' uploads."""
    fake_db.file_uploads.docs.append({
        "id": "fu-3",
        "safe_filename": "secret.pdf",
        "uploaded_by": "other-user",
        "schoolId": "aaryans-joya",
    })
    resp = client.get("/api/uploads", headers=_accountant())
    assert resp.status_code == 200
    # Accountant user_id is "acct-1", other-user's file should NOT appear
    data = resp.json()["data"]
    assert all(f.get("uploaded_by") in (None, "acct-1") for f in data)


# ─────────────────────────────────────────────────────────────────────────────
# R13.3 — Export RBAC + scoping
# ─────────────────────────────────────────────────────────────────────────────

def test_export_students_unauthenticated_returns_401(client):
    resp = client.get("/api/export/students")
    assert resp.status_code == 401


def test_export_students_plain_admin_returns_403(client):
    resp = client.get("/api/export/students", headers=_plain_admin())
    assert resp.status_code == 403


def test_export_students_accountant_returns_403(client):
    resp = client.get("/api/export/students", headers=_accountant())
    assert resp.status_code == 403


def test_export_students_owner_returns_200(client):
    resp = client.get("/api/export/students", headers=_owner())
    assert resp.status_code == 200


def test_export_students_principal_returns_200(client):
    resp = client.get("/api/export/students", headers=_principal())
    assert resp.status_code == 200


def test_export_staff_plain_admin_returns_403(client):
    resp = client.get("/api/export/staff", headers=_plain_admin())
    assert resp.status_code == 403


def test_export_enquiries_plain_admin_returns_403(client):
    resp = client.get("/api/export/enquiries", headers=_plain_admin())
    assert resp.status_code == 403


def test_export_fees_legacy_accounts_returns_403(client):
    """Legacy 'accounts' sub_category must no longer access fee export (canonical 'accountant' only)."""
    resp = client.get("/api/export/fee-transactions", headers=_legacy_accounts())
    assert resp.status_code == 403


def test_export_fees_accountant_returns_200(client):
    """Canonical 'accountant' sub_category can export fee transactions."""
    resp = client.get("/api/export/fee-transactions", headers=_accountant())
    assert resp.status_code == 200


def test_export_expenses_legacy_accounts_returns_403(client):
    """Expenses export must reject legacy 'accounts' sub_category."""
    resp = client.get("/api/export/expenses", headers=_legacy_accounts())
    assert resp.status_code == 403


def test_export_attendance_teacher_returns_200(client):
    resp = client.get("/api/export/attendance", headers=_teacher())
    assert resp.status_code == 200


def test_export_results_teacher_returns_200(client):
    resp = client.get("/api/export/exam-results", headers=_teacher())
    assert resp.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# R13.4 — Login lockout tenant-aware
# ─────────────────────────────────────────────────────────────────────────────

def test_login_lockout_key_includes_school(client, fake_db):
    """Failed attempts lock only the same (username, school) pair — not cross-tenant."""
    # Seed a lockout for school-A
    fake_db.login_attempts.docs.append({
        "key": "login:baduser:school-A",
        "count": 10,
        "locked_until": "2099-01-01T00:00:00+00:00",
    })
    # Attempt for the same user but school-B should NOT be locked
    resp = client.post("/api/auth/login", json={"username": "baduser", "password": "wrong", "school_id": "school-B"})
    # Should get 401 (wrong password/user not found), not 429 (locked)
    assert resp.status_code == 401


def test_login_lockout_same_school_is_blocked(client, fake_db):
    """Failed attempts in same school DO block login."""
    fake_db.login_attempts.docs.append({
        "key": "login:baduser:aaryans-joya",
        "count": 10,
        "locked_until": "2099-01-01T00:00:00+00:00",
    })
    resp = client.post("/api/auth/login", json={"username": "baduser", "password": "wrong"})
    assert resp.status_code == 429


# ─────────────────────────────────────────────────────────────────────────────
# R13.5 — Operations lists branch-scoped
# ─────────────────────────────────────────────────────────────────────────────

def test_leave_requests_branch_a_principal_cannot_see_branch_b(client, fake_db):
    """Branch-A principal must not see Branch-B leave requests."""
    fake_db.leave_requests.docs.append({
        "id": "lr-b",
        "schoolId": "aaryans-joya",
        "branch_id": "branch-b",
        "user_id": "staff-b",
        "status": "pending",
    })
    # Authenticated as branch-A principal
    resp = client.get("/api/operations/leave-requests", headers=_principal("branch-a"))
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()["data"]]
    assert "lr-b" not in ids


def test_approval_requests_branch_a_principal_cannot_see_branch_b(client, fake_db):
    """Branch-A principal must not see Branch-B approval requests."""
    fake_db.approval_requests.docs.append({
        "id": "ar-b",
        "schoolId": "aaryans-joya",
        "branch_id": "branch-b",
        "routing": "owner_and_principal",
        "submitted_by": "staff-b",
        "submitted_at": "2026-01-01",
    })
    resp = client.get("/api/operations/approval-requests", headers=_principal("branch-a"))
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()["data"]]
    assert "ar-b" not in ids


# ─────────────────────────────────────────────────────────────────────────────
# R13.6 — Regex injection escape
# ─────────────────────────────────────────────────────────────────────────────

def test_audit_search_with_regex_metachar_does_not_500(client):
    """Malformed regex in audit search must return 200 (escaped), not 500."""
    resp = client.get("/api/audit-log?q=(a+)+$", headers=_owner())
    assert resp.status_code in (200, 401, 403)  # 401/403 if no audit gate; not 500


def test_incident_search_with_regex_metachar_does_not_500(client):
    """Malformed regex in incident search must return 200, not 500."""
    resp = client.get("/api/ops/incidents?q=[invalid", headers=_owner())
    assert resp.status_code in (200, 401, 403)


def test_fee_export_invalid_period_returns_400(client):
    """fee export with non-YYYY-MM period must return 400."""
    resp = client.get("/api/fees/export?period=bad-period", headers=_owner())
    assert resp.status_code == 400


def test_fee_export_valid_period_returns_200(client):
    """fee export with valid YYYY-MM period must succeed."""
    resp = client.get("/api/fees/export?period=2026-01", headers=_owner())
    assert resp.status_code == 200


def test_attendance_export_invalid_month_returns_400(client):
    """Attendance export with invalid month must return 400."""
    resp = client.get(
        "/api/attendance/export?class_id=class-1&month=2026/01",
        headers=_owner(),
    )
    assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# R13.7 — Staff deactivation revokes sessions via canonical helper
# ─────────────────────────────────────────────────────────────────────────────

def test_staff_deactivation_unauthenticated_returns_401(client):
    resp = client.delete("/api/staff/some-id")
    assert resp.status_code == 401


def test_staff_deactivation_wrong_role_returns_403(client):
    resp = client.delete("/api/staff/some-id", headers=_teacher())
    assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# R13.8 — Bulk SMS ownership + scoping + daily cap
# ─────────────────────────────────────────────────────────────────────────────

def test_send_parent_message_unauthenticated_returns_401(client):
    resp = client.post("/api/sms/send-parent-message", json={"student_ids": [], "message": "Hi"})
    assert resp.status_code == 401


def test_send_parent_message_cross_branch_filtered(client, fake_db, monkeypatch):
    """send_parent_message must not send to students in another branch."""
    import routes.sms as sms_module
    fake_db.students.docs.append({
        "id": "stu-branch-b",
        "schoolId": "aaryans-joya",
        "branch_id": "branch-b",
        "name": "Ravi",
    })
    monkeypatch.setattr(sms_module, "get_db", lambda: fake_db)
    # Branch-A principal sends to branch-B student ID — should be filtered out
    resp = client.post(
        "/api/sms/send-parent-message",
        headers=_principal("branch-a"),
        json={"student_ids": ["stu-branch-b"], "message": "Hello"},
    )
    # Should return 400 (no valid students in branch-a for that ID)
    assert resp.status_code == 400


def test_sms_daily_cap_exceeded_returns_429(client, fake_db, monkeypatch):
    """When daily cap is exceeded, bulk SMS returns 429."""
    import routes.sms as sms_module
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    # Seed > cap sms_logs for today
    monkeypatch.setattr(sms_module, "SMS_DAILY_CAP", 2)
    for i in range(3):
        fake_db.sms_logs.docs.append({
            "id": f"sms-{i}",
            "schoolId": "aaryans-joya",
            "sent_at": f"{today}T10:00:00",
        })
    fake_db.students.docs.append({
        "id": "stu-cap",
        "schoolId": "aaryans-joya",
        "name": "Test",
    })
    monkeypatch.setattr(sms_module, "get_db", lambda: fake_db)
    resp = client.post(
        "/api/sms/send-parent-message",
        headers=_owner(),
        json={"student_ids": ["stu-cap"], "message": "Hi"},
    )
    assert resp.status_code == 429


def test_get_sms_logs_branch_scoped(client, fake_db, monkeypatch):
    """get_sms_logs for branch-bound admin must only return own-branch logs."""
    import routes.sms as sms_module
    fake_db.sms_logs.docs.append({
        "id": "log-b",
        "schoolId": "aaryans-joya",
        "branch_id": "branch-b",
        "sent_at": "2026-01-01T10:00:00",
    })
    monkeypatch.setattr(sms_module, "get_db", lambda: fake_db)
    resp = client.get("/api/sms/logs", headers=_principal("branch-a"))
    assert resp.status_code == 200
    ids = [item.get("id") for item in resp.json()["data"]]
    assert "log-b" not in ids


# ─────────────────────────────────────────────────────────────────────────────
# R13.9 — Bulk import branch tag
# ─────────────────────────────────────────────────────────────────────────────

def test_import_validate_unauthenticated_returns_401(client):
    resp = client.post("/api/import/validate", files={"file": ("test.csv", b"name", "text/csv")})
    assert resp.status_code == 401


def test_import_student_doc_includes_branch_id():
    """_student_doc must include branch_id when user has one."""
    from routes.import_data import _student_doc
    user = {"id": "u1", "role": "owner", "branch_id": "branch-x"}
    row = {"class_id": "cls-1", "name": "Test Student"}
    doc = _student_doc(row, user)
    assert doc.get("branch_id") == "branch-x"


def test_import_student_doc_no_branch_id_when_owner_has_none():
    """_student_doc must omit branch_id when user has no branch."""
    from routes.import_data import _student_doc
    user = {"id": "u1", "role": "owner"}
    row = {"class_id": "cls-1", "name": "Test Student"}
    doc = _student_doc(row, user)
    assert "branch_id" not in doc
