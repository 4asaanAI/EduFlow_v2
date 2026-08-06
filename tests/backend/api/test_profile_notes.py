from __future__ import annotations

"""Notes and remarks on a profile, and the privacy rule that defines them.

Owner request 4, 2026-08-06, decision 3: notes are PRIVATE TO EACH AUTHOR. The owner
and the principal may both keep notes about the same child and neither can read the
other's. Abhimanyu was shown that consequence in plain words and chose it deliberately.

These tests exist to stop a future change quietly turning this into a shared feed —
which would hand each of them everything the other had written about a child, without
anyone noticing that a rule had been reversed.
"""

from middleware.auth import create_jwt


def _bearer(payload: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


OWNER = {"user_id": "own-1", "role": "owner", "sub_category": "owner", "name": "Aman Litt"}
PRINCIPAL = {"user_id": "prn-1", "role": "admin", "sub_category": "principal", "name": "Principal"}
ACCOUNTANT = {"user_id": "acc-1", "role": "admin", "sub_category": "accountant", "name": "A"}
TEACHER = {"user_id": "tch-1", "role": "teacher", "name": "T"}


def _add(client, headers, body="A note about this child.", **extra):
    payload = {"subject_type": "student", "subject_id": "student-1", "body": body, **extra}
    return client.post("/api/profile-notes", json=payload, headers=headers)


def _list(client, headers, subject_id="student-1", subject_type="student"):
    return client.get(
        f"/api/profile-notes?subject_type={subject_type}&subject_id={subject_id}",
        headers=headers,
    )


# ─── Security pair, required for every new endpoint ─────────────────────────────

def test_notes_unauthenticated_returns_401(client):
    assert client.get("/api/profile-notes?subject_type=student&subject_id=s1").status_code == 401


def test_notes_wrong_role_returns_403(client):
    assert _list(client, _bearer(TEACHER)).status_code == 403


def test_writing_a_note_unauthenticated_returns_401(client):
    assert client.post("/api/profile-notes", json={}).status_code == 401


def test_an_accountant_may_not_read_or_write_notes(client):
    assert _list(client, _bearer(ACCOUNTANT)).status_code == 403
    assert _add(client, _bearer(ACCOUNTANT)).status_code == 403


# ─── Writing and reading your own ───────────────────────────────────────────────

def test_a_note_is_saved_with_who_wrote_it_and_when(client, fake_db):
    fake_db.profile_notes.docs[:] = []
    resp = _add(client, _bearer(OWNER), "Spoke to the family about attendance.")

    assert resp.status_code == 200, resp.text
    note = resp.json()["data"]
    assert note["body"] == "Spoke to the family about attendance."
    assert note["author_id"] == OWNER["user_id"]
    assert note["author_name"] == "Aman Litt"
    assert note["created_at"]


def test_notes_come_back_newest_first(client, fake_db):
    fake_db.profile_notes.docs[:] = []
    _add(client, _bearer(OWNER), "The older one")
    _add(client, _bearer(OWNER), "The newer one")

    rows = _list(client, _bearer(OWNER)).json()["data"]

    assert [r["body"] for r in rows][0] == "The newer one"
    assert len(rows) == 2


def test_a_note_can_carry_pictures(client, fake_db):
    fake_db.profile_notes.docs[:] = []
    resp = _add(
        client, _bearer(OWNER), "See the attached report card.",
        attachments=[{"file_id": "file-1", "file_url": "/api/uploads/serve/file-1.jpg", "file_name": "card.jpg"}],
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["attachments"][0]["file_id"] == "file-1"


def test_an_empty_note_is_refused(client):
    assert _add(client, _bearer(OWNER), "   ").status_code == 400


def test_an_attachment_without_a_file_id_is_refused(client):
    # A picture has to point at a file that actually went through the upload route.
    resp = _add(client, _bearer(OWNER), "A note", attachments=[{"file_url": "http://example.com/x.jpg"}])
    assert resp.status_code == 400


def test_an_unknown_subject_type_is_refused(client):
    resp = client.post(
        "/api/profile-notes",
        json={"subject_type": "guardian", "subject_id": "g1", "body": "Something"},
        headers=_bearer(OWNER),
    )
    assert resp.status_code == 400


# ─── THE privacy rule ───────────────────────────────────────────────────────────

def test_the_principal_cannot_read_a_note_the_owner_wrote(client, fake_db):
    """Decision 3. If this ever passes by returning the owner's note, the feature has
    silently become a shared feed and everything either of them wrote about a child is
    visible to the other."""
    fake_db.profile_notes.docs[:] = []
    _add(client, _bearer(OWNER), "The owner's private note")

    rows = _list(client, _bearer(PRINCIPAL)).json()["data"]

    assert rows == []


def test_the_owner_cannot_read_a_note_the_principal_wrote(client, fake_db):
    fake_db.profile_notes.docs[:] = []
    _add(client, _bearer(PRINCIPAL), "The principal's private note")

    rows = _list(client, _bearer(OWNER)).json()["data"]

    assert rows == []


def test_each_of_them_sees_exactly_their_own(client, fake_db):
    fake_db.profile_notes.docs[:] = []
    _add(client, _bearer(OWNER), "Owner note")
    _add(client, _bearer(PRINCIPAL), "Principal note")

    assert [r["body"] for r in _list(client, _bearer(OWNER)).json()["data"]] == ["Owner note"]
    assert [r["body"] for r in _list(client, _bearer(PRINCIPAL)).json()["data"]] == ["Principal note"]


def test_the_body_of_a_note_never_reaches_the_action_log(client, fake_db):
    """The action log is readable by both of them, so copying a private note into it
    would hand each the other's notes through the back door."""
    fake_db.profile_notes.docs[:] = []
    fake_db.audit_logs.docs[:] = []
    secret = "Something the principal must never read"
    _add(client, _bearer(OWNER), secret)

    rows = [a for a in fake_db.audit_logs.docs if a["action"] == "profile_note_added"]
    assert len(rows) == 1
    assert secret not in str(rows[0])
    # What it DOES record: that a note was written, about whom, and by whom.
    assert rows[0]["changed_by"] == OWNER["user_id"]
    assert rows[0]["changes"]["subject_id"] == "student-1"


# ─── Correcting and removing your own ───────────────────────────────────────────

def test_you_can_correct_your_own_note(client, fake_db):
    fake_db.profile_notes.docs[:] = []
    note_id = _add(client, _bearer(OWNER), "First draft").json()["data"]["id"]

    resp = client.patch(
        f"/api/profile-notes/{note_id}", json={"body": "Corrected wording"}, headers=_bearer(OWNER)
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["body"] == "Corrected wording"


def test_you_cannot_edit_somebody_elses_note(client, fake_db):
    fake_db.profile_notes.docs[:] = []
    note_id = _add(client, _bearer(OWNER), "The owner's note").json()["data"]["id"]

    resp = client.patch(
        f"/api/profile-notes/{note_id}", json={"body": "Tampered"}, headers=_bearer(PRINCIPAL)
    )

    # A 404 rather than a 403, deliberately: saying "that exists but is not yours"
    # would confirm the other person had written one.
    assert resp.status_code == 404


def test_you_can_delete_your_own_note(client, fake_db):
    fake_db.profile_notes.docs[:] = []
    note_id = _add(client, _bearer(OWNER), "To be removed").json()["data"]["id"]

    assert client.delete(f"/api/profile-notes/{note_id}", headers=_bearer(OWNER)).status_code == 200
    assert _list(client, _bearer(OWNER)).json()["data"] == []


def test_you_cannot_delete_somebody_elses_note(client, fake_db):
    fake_db.profile_notes.docs[:] = []
    note_id = _add(client, _bearer(PRINCIPAL), "The principal's note").json()["data"]["id"]

    assert client.delete(f"/api/profile-notes/{note_id}", headers=_bearer(OWNER)).status_code == 404
    assert len(fake_db.profile_notes.docs) == 1


# ─── The directory column ───────────────────────────────────────────────────────

def test_the_counts_are_batched_and_are_your_own(client, fake_db):
    fake_db.profile_notes.docs[:] = []
    _add(client, _bearer(OWNER), "One")
    _add(client, _bearer(OWNER), "Two")
    _add(client, _bearer(PRINCIPAL), "The principal's")

    counts = client.get(
        "/api/profile-notes/counts?subject_type=student&subject_ids=student-1,student-2",
        headers=_bearer(OWNER),
    ).json()["data"]

    assert counts == {"student-1": 2}


def test_the_counts_are_refused_to_a_teacher(client):
    resp = client.get(
        "/api/profile-notes/counts?subject_type=student&subject_ids=student-1",
        headers=_bearer(TEACHER),
    )
    assert resp.status_code == 403


# ─── Erasure takes the notes with it ────────────────────────────────────────────

def test_erasing_a_student_removes_every_note_about_them(client, fake_db, auth_headers, student_data):
    """A written account of a child must not survive the child's record being
    destroyed, whoever wrote it."""
    created = client.post("/api/students", json=student_data, headers=auth_headers)
    student_id = created.json()["data"]["id"]
    fake_db.profile_notes.docs[:] = []
    client.post(
        "/api/profile-notes",
        json={"subject_type": "student", "subject_id": student_id, "body": "The owner's note"},
        headers=_bearer(OWNER),
    )
    client.post(
        "/api/profile-notes",
        json={"subject_type": "student", "subject_id": student_id, "body": "The principal's note"},
        headers=_bearer(PRINCIPAL),
    )
    assert len(fake_db.profile_notes.docs) == 2

    resp = client.post(
        f"/api/students/{student_id}/erase",
        data={"reason": "Requested by the family under the data protection rules"},
        headers=_bearer(OWNER),
    )

    assert resp.status_code == 200, resp.text
    assert fake_db.profile_notes.docs == []
