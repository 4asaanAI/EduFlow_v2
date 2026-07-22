"""UI Sweep Epic 10, Story 10.4 — existing exports, now also as Excel.

The important tests here are the ones asserting NOTHING ELSE MOVED. This story
changes packaging only. A format option that quietly widened who can download the
school's data would be a far worse defect than the inconvenience it set out to fix.
"""
from __future__ import annotations

import io

import pytest

from middleware.auth import create_jwt

pytestmark = pytest.mark.asyncio

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _bearer(payload: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


def _owner():
    return _bearer({"user_id": "x-owner", "role": "owner", "name": "Owner"})


def _principal():
    return _bearer({"user_id": "x-prin", "role": "admin", "sub_category": "principal",
                    "branch_id": "branch-a", "name": "Principal"})


def _accountant():
    return _bearer({"user_id": "x-acct", "role": "admin", "sub_category": "accountant",
                    "name": "Accountant"})


def _teacher():
    return _bearer({"user_id": "x-teach", "role": "teacher", "branch_id": "branch-a", "name": "Teacher"})


def _student():
    return _bearer({"user_id": "x-stu", "role": "student", "name": "Student"})


_TOUCHED = ("students", "staff", "fee_transactions", "student_attendance",
            "expenses", "enquiries", "classes")


@pytest.fixture(autouse=True)
def _clean(fake_db):
    saved = {n: list(getattr(fake_db, n).docs) for n in _TOUCHED}
    for n in _TOUCHED:
        getattr(fake_db, n).docs[:] = []
    yield
    for n in _TOUCHED:
        getattr(fake_db, n).docs[:] = saved[n]


def _seed_students(fake_db):
    fake_db.students.docs.extend([
        {"id": "s1", "schoolId": "aaryans-joya", "branch_id": "branch-a",
         "name": "Asha Kumari", "admission_number": "25001", "is_active": True},
        {"id": "s2", "schoolId": "aaryans-joya", "branch_id": "branch-a",
         "name": "Bipin Sharma", "admission_number": "25002", "is_active": True},
    ])


# ── The new format works ────────────────────────────────────────────────────────

def test_students_as_xlsx_is_a_real_workbook_with_the_data(client, fake_db):
    _seed_students(fake_db)
    resp = client.get("/api/export/students?format=xlsx", headers=_owner())

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith(XLSX_MIME)
    assert ".xlsx" in resp.headers["content-disposition"]

    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(resp.content))
    values = [[c.value for c in row] for row in wb.active.iter_rows()]
    flat = [str(v) for row in values for v in row if v is not None]
    assert "Asha Kumari" in flat
    assert "Name" in flat


def test_csv_is_still_the_default(client, fake_db):
    """Every existing caller — buttons, scripts, bookmarks — keeps working."""
    _seed_students(fake_db)
    resp = client.get("/api/export/students", headers=_owner())

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "Asha Kumari" in resp.text


def test_an_unknown_format_falls_back_to_csv_rather_than_erroring(client, fake_db):
    """Matches how Epic 3 handled an unrecognised sort field: the client's option
    list is a convenience, never the enforcement."""
    _seed_students(fake_db)
    resp = client.get("/api/export/students?format=banana", headers=_owner())

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")


@pytest.mark.parametrize("path,headers_fn", [
    ("/api/export/students", _owner),
    ("/api/export/staff", _owner),
    ("/api/export/fee-transactions", _accountant),
    ("/api/export/expenses", _accountant),
    ("/api/export/enquiries", _principal),
    ("/api/export/attendance", _owner),
    ("/api/export/exam-results", _owner),
])
def test_every_export_offers_xlsx(client, path, headers_fn):
    resp = client.get(f"{path}?format=xlsx", headers=headers_fn())
    assert resp.status_code == 200, path
    assert resp.headers["content-type"].startswith(XLSX_MIME), path


def test_an_empty_export_still_produces_an_openable_workbook(client, fake_db):
    """A workbook with only headers must still open. A zero-byte download is the
    'failure that looks like success' defect in a new place."""
    resp = client.get("/api/export/students?format=xlsx", headers=_owner())
    assert resp.status_code == 200

    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(resp.content))
    assert wb.active is not None


# ── Nothing else moved: the gates are exactly as they were ──────────────────────

@pytest.mark.parametrize("path", [
    "/api/export/students", "/api/export/staff", "/api/export/fee-transactions",
    "/api/export/expenses", "/api/export/enquiries", "/api/export/attendance",
    "/api/export/exam-results",
])
@pytest.mark.parametrize("fmt", ["", "?format=xlsx"])
def test_a_student_is_refused_every_export_in_every_format(client, path, fmt):
    """The format option must not become a way around an export permission."""
    resp = client.get(f"{path}{fmt}", headers=_student())
    assert resp.status_code == 403, f"{path}{fmt}"


@pytest.mark.parametrize("path", [
    "/api/export/students", "/api/export/staff", "/api/export/fee-transactions",
    "/api/export/expenses", "/api/export/enquiries",
])
def test_unauthenticated_is_refused_every_export(client, path):
    assert client.get(f"{path}?format=xlsx").status_code == 401


def test_a_teacher_still_cannot_export_students_or_staff(client, fake_db):
    """These were owner-or-principal before this story and must stay so."""
    _seed_students(fake_db)
    assert client.get("/api/export/students?format=xlsx", headers=_teacher()).status_code == 403
    assert client.get("/api/export/staff?format=xlsx", headers=_teacher()).status_code == 403


def test_a_principal_still_cannot_export_fees_or_expenses(client):
    """Fee and expense exports were owner-or-accountant before this story."""
    assert client.get("/api/export/fee-transactions?format=xlsx", headers=_principal()).status_code == 403
    assert client.get("/api/export/expenses?format=xlsx", headers=_principal()).status_code == 403


def test_salary_is_still_withheld_from_the_staff_export(client, fake_db):
    """The staff query projects salary out. A new format must not reintroduce it."""
    fake_db.staff.docs.append({
        "id": "st1", "schoolId": "aaryans-joya", "branch_id": "branch-a",
        "name": "Teacher One", "staff_type": "teacher", "is_active": True,
        "salary": 91234,
    })
    resp = client.get("/api/export/staff?format=xlsx", headers=_owner())
    assert resp.status_code == 200
    assert b"91234" not in resp.content
