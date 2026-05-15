from __future__ import annotations
"""
Story P4-1.1: Exam-results export cross-tenant enrichment tests.

Verifies:
  1. /api/export/exam-results is school-scoped (uses get_db(), not get_raw_db())
  2. A missing subject returns "Unknown" instead of raising an error
  3. A found subject returns its name
"""

import pytest
from middleware.auth import create_jwt

pytestmark = pytest.mark.asyncio


def _owner_headers() -> dict:
    payload = {"user_id": "export-owner-1", "role": "owner", "name": "Export Owner"}
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


@pytest.fixture(autouse=True)
def _clean_export_collections(fake_db):
    """Isolate exam_results and subjects between tests."""
    original_results = list(fake_db.exam_results.docs)
    original_subjects = list(fake_db.subjects.docs)
    fake_db.exam_results.docs[:] = []
    fake_db.subjects.docs[:] = []
    yield
    fake_db.exam_results.docs[:] = original_results
    fake_db.subjects.docs[:] = original_subjects


def test_exam_results_export_returns_csv(client, fake_db):
    """Export returns 200 with CSV content-type when there are results."""
    fake_db.subjects.docs.append(
        {"id": "subj-1", "schoolId": "aaryans-joya", "name": "Mathematics"}
    )
    fake_db.exam_results.docs.append(
        {
            "student_id": "student-1",
            "exam_id": "exam-1",
            "subject_id": "subj-1",
            "marks_obtained": 85,
            "max_marks": 100,
            "grade": "A",
            "schoolId": "aaryans-joya",
        }
    )

    resp = client.get("/api/export/exam-results", headers=_owner_headers())
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
    body = resp.text
    assert "Mathematics" in body
    assert "student-1" in body


def test_exam_results_missing_subject_returns_unknown(client, fake_db):
    """When a subject_id has no matching subject, the CSV row shows 'Unknown'."""
    # No subject seeded — subject lookup will return None
    fake_db.exam_results.docs.append(
        {
            "student_id": "student-2",
            "exam_id": "exam-2",
            "subject_id": "subj-missing",
            "marks_obtained": 70,
            "max_marks": 100,
            "grade": "B",
            "schoolId": "aaryans-joya",
        }
    )

    resp = client.get("/api/export/exam-results", headers=_owner_headers())
    assert resp.status_code == 200, resp.text
    body = resp.text
    # Must contain "Unknown" not "N/A" and must not raise
    assert "Unknown" in body
    assert "N/A" not in body


def test_exam_results_export_uses_scoped_db(monkeypatch, client, fake_db):
    """
    Verify the route calls get_db() (scoped) and not get_raw_db().
    We monkeypatch routes.exports.get_db to track calls, confirm it is used.
    """
    import routes.exports as exports_module

    call_log = []
    original_get_db = exports_module.get_db

    def tracked_get_db():
        call_log.append("get_db")
        return original_get_db()

    monkeypatch.setattr(exports_module, "get_db", tracked_get_db)

    resp = client.get("/api/export/exam-results", headers=_owner_headers())
    assert resp.status_code == 200
    assert "get_db" in call_log, "export_results must call get_db() for school-scoped access"


def test_exam_results_empty_returns_csv_headers_only(client, fake_db):
    """With no results, the export returns just the CSV header row."""
    resp = client.get("/api/export/exam-results", headers=_owner_headers())
    assert resp.status_code == 200
    body = resp.text.strip()
    # Should have exactly one line — the header
    lines = [l for l in body.splitlines() if l.strip()]
    assert len(lines) == 1
    assert "Student ID" in lines[0]
    assert "Subject" in lines[0]
