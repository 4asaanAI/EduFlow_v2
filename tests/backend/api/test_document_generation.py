"""UI Sweep Epic 10, Stories 10.1 (storage) and 10.2 (Flo's tool).

The tests that matter most here are the ones asserting the tool cannot become a way
around an export permission. "Give me a spreadsheet of every student" and
`GET /api/export/students` return the same 1,802 children by different routes.
"""
from __future__ import annotations

import io

import pytest

from middleware.auth import create_jwt

pytestmark = pytest.mark.asyncio

TOOL_URL = "/api/tools/draft_document/execute"


def _bearer(payload: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


def _owner():
    return _bearer({"user_id": "d-owner", "role": "owner", "name": "Owner"})


def _teacher():
    return _bearer({"user_id": "d-teach", "role": "teacher", "branch_id": "branch-a", "name": "Teacher"})


def _student():
    return _bearer({"user_id": "d-stu", "role": "student", "name": "Student"})


_TOUCHED = ("file_uploads", "audit_logs", "image_gen_quota")


@pytest.fixture(autouse=True)
def _clean(fake_db):
    for n in _TOUCHED:
        if not hasattr(fake_db, n):
            continue
    saved = {n: list(getattr(fake_db, n).docs) for n in _TOUCHED if hasattr(fake_db, n)}
    for n in saved:
        getattr(fake_db, n).docs[:] = []
    yield
    for n, docs in saved.items():
        getattr(fake_db, n).docs[:] = docs


@pytest.fixture(autouse=True)
def _fake_s3(monkeypatch):
    """S3 is not reachable from a test run. Storage is faked at the boundary so the
    record-keeping and audit behaviour either side of it is still exercised."""
    from services import document_export

    class _Stored:
        bucket = "test-bucket"
        key = "aaryans-joya/uploads/x/x.docx"
        etag = "etag"
        sha256 = "sha"

    monkeypatch.setattr(document_export, "upload_bytes", lambda **kw: _Stored())
    monkeypatch.setattr(
        document_export, "create_presigned_get_url",
        lambda key, **kw: f"https://s3.example/{key}?signed=1",
    )


# ── The tool produces a real file and a link ────────────────────────────────────

def test_owner_gets_a_download_link_and_a_stored_record(client, fake_db):
    resp = client.post(TOOL_URL, headers=_owner(), json={"params": {
        "doc_type": "docx",
        "title": "Principal's Circular",
        "paragraphs": ["School reopens on 1 April."],
    }})

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]

    assert data["doc_type"] == "docx"
    assert data["file_name"].endswith(".docx")
    assert data["download_url"].startswith("https://")
    assert data["expires_in_seconds"] > 0

    stored = [d for d in fake_db.file_uploads.docs if d["id"] == data["file_id"]]
    assert len(stored) == 1
    assert stored[0]["generated"] is True
    assert stored[0]["schoolId"] == "aaryans-joya"


def test_the_link_is_signed_and_expires_rather_than_being_public(client):
    """A generated document must never sit on an unauthenticated public URL — that
    was the defect hotfix-1 was raised for."""
    resp = client.post(TOOL_URL, headers=_owner(), json={"params": {
        "doc_type": "pdf", "title": "Notice", "paragraphs": ["Holiday Monday."],
    }})
    data = resp.json()["data"]
    assert "signed=1" in data["download_url"]
    assert data["expires_in_seconds"] > 0


def test_the_stored_key_is_namespaced_to_the_school(client, fake_db):
    resp = client.post(TOOL_URL, headers=_owner(), json={"params": {
        "doc_type": "csv", "headers": ["A"], "rows": [["1"]],
    }})
    file_id = resp.json()["data"]["file_id"]
    record = next(d for d in fake_db.file_uploads.docs if d["id"] == file_id)
    assert record["s3_key"].startswith("aaryans-joya/")


def test_generating_a_document_is_audited(client, fake_db):
    """Every generated document is a copy of school data leaving the platform."""
    resp = client.post(TOOL_URL, headers=_owner(), json={"params": {
        "doc_type": "xlsx", "headers": ["Student"], "rows": [["Asha"]],
    }})
    file_id = resp.json()["data"]["file_id"]

    rows = [a for a in fake_db.audit_logs.docs if a.get("action") == "document_generated"]
    assert len(rows) == 1
    assert rows[0]["changes"]["file_id"] == file_id


def test_the_audit_row_carries_no_document_content(client, fake_db):
    """NFR-S2: ids and counts only. The body may be a child's medical note."""
    client.post(TOOL_URL, headers=_owner(), json={"params": {
        "doc_type": "docx",
        "title": "Medical note for Asha Kumari",
        "paragraphs": ["Asha Kumari has asthma. Guardian phone 9876543210."],
    }})
    audit = next(a for a in fake_db.audit_logs.docs if a.get("action") == "document_generated")
    blob = str(audit)
    assert "Asha Kumari" not in blob
    assert "9876543210" not in blob
    assert "asthma" not in blob


# ── It must not become a way around an export permission ────────────────────────

def test_a_student_cannot_generate_a_document(client):
    """No export in routes/exports.py is open to a student, so neither is this."""
    resp = client.post(TOOL_URL, headers=_student(), json={"params": {
        "doc_type": "xlsx", "headers": ["Name"], "rows": [["Asha"]],
    }})
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Forbidden"


def test_unauthenticated_cannot_generate_a_document(client):
    resp = client.post(TOOL_URL, json={"params": {"doc_type": "csv", "rows": [["x"]]}})
    assert resp.status_code == 401


def test_the_tool_never_queries_the_database_itself(client):
    """The gate's whole justification is that this tool formats content the caller
    already has, rather than fetching data of its own. If it ever starts querying,
    that reasoning collapses and the gate must be narrowed — so this is pinned."""
    import inspect

    from ai.tool_functions_v2 import tool_draft_document

    src = inspect.getsource(tool_draft_document)
    for forbidden in ("get_db(", "db.students", "db.staff", "db.fee_transactions", "find("):
        assert forbidden not in src, (
            f"tool_draft_document now contains {forbidden!r}. It fetches data, so "
            "its role gate can no longer be justified by upstream tools' gates."
        )


def test_a_teacher_may_generate_a_document(client):
    """Teachers legitimately produce worksheets and notices."""
    resp = client.post(TOOL_URL, headers=_teacher(), json={"params": {
        "doc_type": "docx", "title": "Worksheet", "paragraphs": ["Solve for x."],
    }})
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_it_is_a_read_class_tool_and_needs_no_confirmation(client):
    """Deliberate: it changes no school record, so there is nothing to undo.
    Recorded as a test so a later reviewer does not 'fix' it into a confirm flow."""
    from ai.tool_access import is_read_only_tool
    from ai.tool_functions_v2 import TOOL_REGISTRY, WRITE_TOOL_NAMES

    tool = TOOL_REGISTRY["draft_document"]
    assert is_read_only_tool(tool) is True
    assert "draft_document" not in WRITE_TOOL_NAMES
    assert not tool.get("requires_confirmation")


# ── Failures are honest ─────────────────────────────────────────────────────────

def test_an_unsupported_format_is_refused_without_storing_anything(client, fake_db):
    resp = client.post(TOOL_URL, headers=_owner(), json={"params": {
        "doc_type": "exe", "title": "x",
    }})
    body = resp.json()
    assert body["success"] is False
    assert "Unsupported" in body["message"]
    assert fake_db.file_uploads.docs == [], "nothing may be stored when the build fails"


def test_a_missing_format_asks_rather_than_guessing(client):
    resp = client.post(TOOL_URL, headers=_owner(), json={"params": {"title": "x"}})
    body = resp.json()
    assert body["success"] is False
    assert "docx" in body["message"]


def test_the_daily_cap_refuses_plainly_once_reached(client, fake_db, monkeypatch):
    from services import document_export

    monkeypatch.setattr(document_export, "DAILY_DOCUMENT_CAP", 2)
    for _ in range(2):
        ok = client.post(TOOL_URL, headers=_owner(), json={"params": {
            "doc_type": "csv", "rows": [["x"]],
        }})
        assert ok.json()["success"] is True

    blocked = client.post(TOOL_URL, headers=_owner(), json={"params": {
        "doc_type": "csv", "rows": [["x"]],
    }})
    body = blocked.json()
    assert body["success"] is False
    assert "allowance resets tomorrow" in body["message"]


def test_the_cap_shares_its_counter_with_certificate_generation(client, fake_db):
    """A second counter would mean a second allowance."""
    client.post(TOOL_URL, headers=_owner(), json={"params": {"doc_type": "csv", "rows": [["x"]]}})
    quota = fake_db.image_gen_quota.docs
    assert len(quota) == 1
    assert quota[0]["kind"] == "document"


def test_a_truncated_document_says_so_in_the_reply(client, monkeypatch):
    from services import document_builder

    monkeypatch.setattr(document_builder, "MAX_ROWS", 3)
    resp = client.post(TOOL_URL, headers=_owner(), json={"params": {
        "doc_type": "csv", "headers": ["N"], "rows": [[str(i)] for i in range(10)],
    }})
    body = resp.json()
    assert body["data"]["truncated"] is True
    assert "only the first" in body["message"]
