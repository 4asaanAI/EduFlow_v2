"""Owner request, 2026-08-07: reading and correcting a document Flo made.

`GET /api/uploads/content/{file_id}` hands back the document's text so the edit panel
has something to open. Until this existed, a generated document could only be
downloaded, so one wrong sentence meant asking Flo again and hoping.

TWO THINGS THESE TESTS EXIST TO HOLD DOWN.

1. **The permission is the SAME one the download uses.** Anyone who may download the
   file may read its text, and nobody else. A looser rule here would be a way round
   the download gate, which is the more obvious door and therefore the better guarded
   one. So the entitlement cases below deliberately mirror
   `test_generated_file_link.py` rather than inventing their own.

2. **Nothing is written back.** Abhimanyu decided on 2026-08-07 that a corrected
   document is downloaded only. There is therefore no save endpoint, and the test at
   the bottom asserts that on purpose: if someone later adds a PUT here without
   revisiting that decision, the school would silently gain a second, unaudited
   version of a document its action log still describes as the original.
"""
from __future__ import annotations

import pytest

from middleware.auth import create_jwt

SCHOOL = "aaryans-joya"


def _bearer(payload: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


def _owner():
    return _bearer({"user_id": "c-owner", "role": "owner", "name": "Owner"})


def _principal():
    return _bearer({"user_id": "c-prin", "role": "admin", "sub_category": "principal", "name": "Principal"})


def _teacher():
    return _bearer({"user_id": "c-teach", "role": "teacher", "branch_id": "branch-a", "name": "Teacher"})


def _student():
    return _bearer({"user_id": "c-stu", "role": "student", "name": "Student"})


def _url(file_id: str) -> str:
    return f"/api/uploads/content/{file_id}"


@pytest.fixture(autouse=True)
def _clean_uploads(fake_db):
    saved = list(fake_db.file_uploads.docs)
    fake_db.file_uploads.docs[:] = []
    yield
    fake_db.file_uploads.docs[:] = saved


def _put(fake_db, *, file_id: str, uploaded_by: str, school: str = SCHOOL, html: str | None = "<h1>Notice</h1><p>Holiday on Monday.</p>"):
    record = {
        "id": file_id,
        "_id": file_id,
        "schoolId": school,
        "uploaded_by": uploaded_by,
        "file_name": f"{file_id}.pdf",
        "safe_filename": f"{file_id}.pdf",
        "file_type": "application/pdf",
        "s3_key": f"{school}/uploads/{file_id}/x.pdf",
        "generated": True,
    }
    if html is not None:
        record["editable_html"] = html
    fake_db.file_uploads.docs.append(record)


# ── Authentication and entitlement — the same gate as the download ───────────────

def test_unauthenticated_cannot_read_a_document(client, fake_db):
    _put(fake_db, file_id="f1", uploaded_by="c-owner")
    assert client.get(_url("f1")).status_code == 401


def test_a_user_cannot_read_a_document_they_do_not_own(client, fake_db):
    _put(fake_db, file_id="f1", uploaded_by="c-owner")
    resp = client.get(_url("f1"), headers=_teacher())
    assert resp.status_code == 403


def test_a_student_cannot_read_someone_elses_document(client, fake_db):
    _put(fake_db, file_id="f1", uploaded_by="c-owner")
    assert client.get(_url("f1"), headers=_student()).status_code == 403


def test_the_person_who_made_it_can_read_it(client, fake_db):
    _put(fake_db, file_id="f1", uploaded_by="c-owner")
    resp = client.get(_url("f1"), headers=_owner())
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "Holiday on Monday." in data["content_html"]
    assert data["file_name"] == "f1.pdf"


def test_owner_and_principal_can_read_any_document_in_the_school(client, fake_db):
    _put(fake_db, file_id="f1", uploaded_by="c-teach")
    assert client.get(_url("f1"), headers=_owner()).status_code == 200
    assert client.get(_url("f1"), headers=_principal()).status_code == 200


def test_a_document_from_another_school_is_not_found(client, fake_db):
    """Tenant isolation: an id belonging to a different school is invisible here."""
    _put(fake_db, file_id="f1", uploaded_by="c-owner", school="other-school")
    assert client.get(_url("f1"), headers=_owner()).status_code == 404


def test_a_missing_document_is_answered_in_our_own_words(client, fake_db):
    resp = client.get(_url("nope"), headers=_owner())
    assert resp.status_code == 404
    assert "ask for it again" in resp.json()["detail"].lower()


# ── Documents that predate editing ───────────────────────────────────────────────

def test_an_older_document_says_it_can_only_be_downloaded(client, fake_db):
    """Anything generated before this shipped holds no editable copy. Saying so is
    better than opening an empty editor, which reads as though the document itself
    were empty."""
    _put(fake_db, file_id="f1", uploaded_by="c-owner", html=None)
    resp = client.get(_url("f1"), headers=_owner())
    assert resp.status_code == 409
    assert "only be downloaded" in resp.json()["detail"].lower()


# ── The decision that a corrected copy is not saved ──────────────────────────────

def test_the_response_states_that_nothing_is_saved_back(client, fake_db):
    _put(fake_db, file_id="f1", uploaded_by="c-owner")
    data = client.get(_url("f1"), headers=_owner()).json()["data"]
    assert data["saves_to_server"] is False


@pytest.mark.parametrize("method", ["put", "post", "patch", "delete"])
def test_there_is_no_way_to_write_a_document_back(client, fake_db, method):
    """Deliberate, not missing. If this ever starts passing, the decision of
    2026-08-07 has been reversed by accident, and a corrected document is being stored
    with no author, no timestamp and no audit row while the existing log entry still
    describes the original."""
    _put(fake_db, file_id="f1", uploaded_by="c-owner")
    # DELETE carries no body in the test client, so the payload is only sent for the
    # methods that accept one.
    kwargs = {} if method == "delete" else {"json": {"content_html": "<p>x</p>"}}
    resp = getattr(client, method)(_url("f1"), headers=_owner(), **kwargs)
    assert resp.status_code in (404, 405), (
        f"{method.upper()} on the content endpoint answered {resp.status_code}; "
        "a corrected document must not be writable here"
    )
