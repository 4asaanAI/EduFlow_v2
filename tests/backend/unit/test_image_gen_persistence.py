from __future__ import annotations

from types import SimpleNamespace

import pytest

from middleware.auth import create_jwt, SUB_CATEGORIES_BY_ROLE
import routes.image_gen as image_gen_routes


def _headers(role="owner", sub_category=None) -> dict:
    claims = {"user_id": "u-1", "role": role, "name": "Admin"}
    if sub_category:
        claims["sub_category"] = sub_category
    token = create_jwt(claims)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _clean_image_gen_state(fake_db, monkeypatch):
    fake_db.file_uploads.docs[:] = []
    fake_db.audit_logs.docs[:] = []
    fake_db.image_gen_quota.docs[:] = []
    # `fake_db` is a shared module singleton that other test files mutate; ensure
    # the student/class our DB-resolved cert & ID-card tests need are present
    # (non-destructive — R9.5 resolves identity from the DB, not the payload).
    if not any(s.get("id") == "student-1" for s in fake_db.students.docs):
        fake_db.students.docs.append({
            "id": "student-1", "schoolId": "aaryans-joya", "name": "Demo Student",
            "class_id": "class-1", "admission_number": "ADM1", "roll_number": "1",
            "is_active": True, "status": "active",
        })
    if not any(c.get("id") == "class-1" for c in fake_db.classes.docs):
        fake_db.classes.docs.append({
            "id": "class-1", "schoolId": "aaryans-joya", "name": "Class 5", "section": "A",
        })

    # R9.5 AC2: the Gemini/Imagen leg was removed — backgrounds are drawn locally.
    monkeypatch.setattr(
        image_gen_routes,
        "upload_bytes",
        lambda **kwargs: SimpleNamespace(
            bucket="eduflow-test",
            key=kwargs["key"],
            etag="etag",
            sha256="sha",
            size_bytes=len(kwargs["content"]),
        ),
    )
    monkeypatch.setattr(image_gen_routes, "create_presigned_get_url", lambda key: f"https://signed.test/{key}")


def _certificate_payload(**overrides):
    # R9.5 AC1: identity comes from the DB by student_id; client name/class are
    # ignored (kept here to prove they DON'T drive the output).
    payload = {"cert_type": "bonafide", "student_id": "student-1",
               "student_name": "IGNORED", "class": "IGNORED"}
    payload.update(overrides)
    return payload


def test_certificate_persist_false_returns_binary_without_db_write(client, fake_db):
    response = client.post("/api/image-gen/certificate", json=_certificate_payload(), headers=_headers())
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert fake_db.file_uploads.docs == []


def test_certificate_persist_true_stores_pdf_and_returns_json(client, fake_db):
    response = client.post(
        "/api/image-gen/certificate",
        json=_certificate_payload(persist=True),
        headers=_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["file_url"].startswith("https://signed.test/aaryans-joya/uploads/")
    assert body["expires_in"] == 3600
    assert fake_db.file_uploads.docs[-1]["linked_table"] == "certificate"
    assert fake_db.file_uploads.docs[-1]["linked_id"] == "student-1"
    assert fake_db.audit_logs.docs[-1]["action"] == "certificate_generated"


def test_certificate_requires_student_id(client):
    # R9.5 AC1: no client-supplied identity — a missing student_id is a 400.
    resp = client.post("/api/image-gen/certificate",
                       json={"cert_type": "bonafide", "student_name": "Forged Name"},
                       headers=_headers())
    assert resp.status_code == 400


def test_certificate_unknown_student_is_404(client):
    resp = client.post("/api/image-gen/certificate",
                       json={"cert_type": "bonafide", "student_id": "no-such-student"},
                       headers=_headers())
    assert resp.status_code == 404


def test_certificate_denied_for_receptionist_admin(client):
    # A named refusal for one ordinary office role, alongside the derived sweep below.
    # (This test used to name the accountant; owner decision 2026-08-04 moved the
    # accountant to the ALLOWED side, so it now names the receptionist instead — the
    # refusal it was written to protect is still asserted, just for a role that is
    # still refused.)
    resp = client.post("/api/image-gen/certificate", json=_certificate_payload(),
                       headers=_headers(role="admin", sub_category="receptionist"))
    assert resp.status_code == 403


# ── NEW-01 / NEW-02 / D-49 — who may issue an official school document ───────
# Owner decision 2026-08-04: the school's owner, the principal, AND the accountant —
# the third office position Abhimanyu said he would name (decision 2). Commit 1011034
# had widened both routes to every admin sub_category; nothing but a single accountant
# test noticed, and the ID-card route had NO permission test at all — which is why the
# widening survived. These tests encode the decided rule on BOTH routes so the next
# change to either gate has to argue with a red suite.

# Every admin sub_category that is NOT an allowed issuer. Derived from the auth module
# so a newly-added sub_category is covered the day it is added, not the day someone
# remembers to extend this list.
#
# DELIBERATE DEVIATION from CLAUDE.md's "never parametrize across security boundaries".
# That rule exists so an ALLOWED case and a REFUSED case are never averaged into one
# test. These parametrised cases are all on the SAME side of the boundary — every one
# expects 403 — and the allowed profiles (owner, principal) each have their own named
# test below. Deriving the list is the point: NEW-01 happened because a permission
# widened and a hand-maintained list did not notice.
_ISSUER_ADMIN_SUBS = frozenset({"principal", "management"})
_NON_ISSUER_ADMIN_SUBS = sorted(
    SUB_CATEGORIES_BY_ROLE["admin"] - _ISSUER_ADMIN_SUBS
)


@pytest.mark.parametrize("sub_category", _NON_ISSUER_ADMIN_SUBS)
def test_certificate_refused_for_every_non_issuer_admin(client, sub_category):
    resp = client.post("/api/image-gen/certificate", json=_certificate_payload(),
                       headers=_headers(role="admin", sub_category=sub_category))
    assert resp.status_code == 403, f"{sub_category} must not be able to issue a certificate"


@pytest.mark.parametrize("sub_category", _NON_ISSUER_ADMIN_SUBS)
def test_id_cards_refused_for_every_non_issuer_admin(client, sub_category):
    resp = client.post("/api/image-gen/id-cards",
                       json={"class_id": "class-1", "students": [{"student_id": "student-1"}]},
                       headers=_headers(role="admin", sub_category=sub_category))
    assert resp.status_code == 403, f"{sub_category} must not be able to issue an ID card"


def test_certificate_allowed_for_principal(client):
    resp = client.post("/api/image-gen/certificate", json=_certificate_payload(),
                       headers=_headers(role="admin", sub_category="principal"))
    assert resp.status_code == 200


def test_id_cards_allowed_for_principal(client):
    resp = client.post("/api/image-gen/id-cards",
                       json={"class_id": "class-1", "students": [{"student_id": "student-1"}]},
                       headers=_headers(role="admin", sub_category="principal"))
    assert resp.status_code == 200


# R2-9, 2026-08-10 — these two tests used to assert that the admin office could print a
# Bonafide Certificate and a set of ID cards outright, and they were reversed here
# deliberately rather than deleted, because the DOOR they were written to protect is
# still the point: the office must reach these routes, or the screens it owns are dead
# buttons and it would look like the platform was broken.
#
# What changed is decision 6 of 2026-08-10: the office creates the request and the
# school's owner or principal approves it. So the office reaching the route now means
# "may print an award straight away, and may print anything else once it is approved" —
# which is what these two now assert. `test_certificate_approval_r2_9.py` holds the full
# set; these stay so that a future change narrowing the gate back to leadership-only is
# still caught right here.

def test_management_may_print_an_award_without_asking(client):
    # Sports and participation certificates need nobody's permission — they record that
    # a child took part, and assert nothing about their standing.
    resp = client.post("/api/image-gen/certificate",
                       json=_certificate_payload(cert_type="sports"),
                       headers=_headers(role="admin", sub_category="management"))
    assert resp.status_code == 200


def test_management_reaches_the_certificate_route_and_is_told_to_get_approval(client):
    # NOT the gate refusing them: the gate still admits the office. This is the approval
    # step, and the difference matters — the message has to tell them what to do next.
    resp = client.post("/api/image-gen/certificate", json=_certificate_payload(),
                       headers=_headers(role="admin", sub_category="management"))
    assert resp.status_code == 403
    assert "approved" in resp.json()["detail"].lower()


def test_management_reaches_the_id_card_route_and_is_told_to_get_approval(client):
    resp = client.post("/api/image-gen/id-cards",
                       json={"class_id": "class-1", "students": [{"student_id": "student-1"}]},
                       headers=_headers(role="admin", sub_category="management"))
    assert resp.status_code == 403
    assert "approved" in resp.json()["detail"].lower()


# The decided rule is THREE profiles, so every one of them needs a test. Without these,
# a later change that narrowed the gate to principal-only would lock the school's owner
# out of issuing any certificate — with a fully green suite. That is the same shape of
# miss that let NEW-01 through: a permission moved and no test was watching that
# direction. The owner case is the sharpest of the three, because the obvious-looking
# `require_access("owner", "admin", sub_category=(...))` construct passes every other
# test in this file and silently 403s the owner.
def test_certificate_allowed_for_owner(client):
    resp = client.post("/api/image-gen/certificate", json=_certificate_payload(),
                       headers=_headers(role="owner"))
    assert resp.status_code == 200


def test_id_cards_allowed_for_owner(client):
    resp = client.post("/api/image-gen/id-cards",
                       json={"class_id": "class-1", "students": [{"student_id": "student-1"}]},
                       headers=_headers(role="owner"))
    assert resp.status_code == 200


def test_certificate_refused_for_teacher(client):
    resp = client.post("/api/image-gen/certificate", json=_certificate_payload(),
                       headers=_headers(role="teacher", sub_category="class_teacher"))
    assert resp.status_code == 403


def test_id_cards_refused_for_student(client):
    resp = client.post("/api/image-gen/id-cards",
                       json={"class_id": "class-1", "students": [{"student_id": "student-1"}]},
                       headers=_headers(role="student", sub_category="student"))
    assert resp.status_code == 403


def test_certificate_unauthenticated_returns_401(client):
    resp = client.post("/api/image-gen/certificate", json=_certificate_payload())
    assert resp.status_code == 401


def test_id_cards_unauthenticated_returns_401(client):
    resp = client.post("/api/image-gen/id-cards",
                       json={"class_id": "class-1", "students": [{"student_id": "student-1"}]})
    assert resp.status_code == 401


def test_id_cards_persist_true_stores_pdf(client, fake_db):
    response = client.post(
        "/api/image-gen/id-cards",
        json={"persist": True, "class_id": "class-1", "students": [{"student_id": "student-1"}]},
        headers=_headers(),
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert fake_db.file_uploads.docs[-1]["linked_table"] == "id_card"
    assert fake_db.audit_logs.docs[-1]["action"] == "id_card_generated"


def test_id_cards_requires_student_ids(client):
    resp = client.post("/api/image-gen/id-cards",
                       json={"students": [{"name": "Forged", "class": "5"}]},
                       headers=_headers())
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_daily_cap_blocks_over_limit(fake_db, monkeypatch):
    from routes import image_gen
    monkeypatch.setattr(image_gen, "DAILY_GEN_CAP", 2)
    ok1 = await image_gen._enforce_daily_cap(fake_db, "aaryans-joya", "certificate")
    ok2 = await image_gen._enforce_daily_cap(fake_db, "aaryans-joya", "certificate")
    ok3 = await image_gen._enforce_daily_cap(fake_db, "aaryans-joya", "certificate")
    assert ok1 and ok2 and not ok3
    # a different kind has its own counter
    assert await image_gen._enforce_daily_cap(fake_db, "aaryans-joya", "id_card")
