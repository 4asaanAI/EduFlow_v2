"""R2-9 — an official document cannot be printed until somebody has approved it.

Decision 6 of 2026-08-10: the school's owner (Aman Litt) and the principal (Adesh
Singh) issue a certificate or an ID card directly. The admin office (Lalit Thomas)
creates a request and waits for one of those two.

The record flow already did that. The PRINTER did not, and the two did not even use the
same words for the same document, so the first test below is the one that matters: a
Transfer Certificate was stored as `transfer`, which the approval list had never heard
of, and was therefore auto-issued to anybody who asked. The most sensitive document the
school produces was the one the mismatch let through.
"""

from __future__ import annotations

import pytest

from services.certificate_types import (
    canonical_type,
    document_label,
    requires_approval,
)
from middleware.auth import create_jwt


def _bearer(payload: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


def _owner():
    return _bearer({"user_id": "r29-owner", "role": "owner", "name": "Aman Litt"})


def _principal():
    return _bearer({"user_id": "r29-principal", "role": "admin",
                    "sub_category": "principal", "name": "Adesh Singh"})


def _management():
    return _bearer({"user_id": "r29-management", "role": "admin",
                    "sub_category": "management", "name": "Lalit Thomas"})


@pytest.fixture(autouse=True)
def _a_student(fake_db):
    fake_db.students.docs.append({
        "id": "r29-student", "schoolId": "aaryans-joya", "name": "Test Child",
        "admission_number": "R29-1", "is_active": True,
    })
    yield
    fake_db.students.docs[:] = [d for d in fake_db.students.docs if d.get("id") != "r29-student"]
    fake_db.certificates.docs[:] = [
        d for d in fake_db.certificates.docs if d.get("student_id") != "r29-student"
    ]


# ── The vocabulary, reconciled ───────────────────────────────────────────────

def test_transfer_and_tc_are_the_same_document_as_transfer_certificate():
    assert canonical_type("transfer") == "transfer_certificate"
    assert canonical_type("tc") == "transfer_certificate"
    assert canonical_type("Transfer Certificate") == "transfer_certificate"


def test_every_word_for_a_transfer_certificate_needs_approval():
    # This is the defect. Before R2-9 only `tc` and `transfer_certificate` were on the
    # approval list, and the SCREEN sent `transfer`.
    for spelling in ("transfer", "tc", "transfer_certificate"):
        assert requires_approval(spelling), f"{spelling!r} slipped past the approval rule"


def test_awards_do_not_need_approval_but_claims_about_a_child_do():
    for needs in ("transfer_certificate", "bonafide", "character", "migration", "merit", "id_card"):
        assert requires_approval(needs), f"{needs} must be approved"
    for award in ("sports", "participation"):
        assert not requires_approval(award), f"{award} is an award and needs nobody's permission"


def test_a_document_nobody_has_classified_needs_approval():
    # Fails closed. A type added carelessly must ask a human, not print itself.
    assert requires_approval("some_new_thing_2027")
    assert requires_approval("")
    assert requires_approval(None)


def test_the_printer_and_the_approval_rule_share_one_table():
    # The printer's template tables must be keyed by canonical names, or the two drift
    # apart again and the whole class of bug comes back.
    from routes.image_gen import CERT_BODIES, CERT_LABELS, CERT_STYLES

    for table in (CERT_LABELS, CERT_STYLES, CERT_BODIES):
        for key in table:
            assert canonical_type(key) == key, f"{key!r} is not the canonical name"


# ── The record flow stores one word ──────────────────────────────────────────

def test_the_screens_word_for_a_transfer_certificate_is_stored_canonically(client, fake_db):
    resp = client.post("/api/ops/certificates",
                       json={"student_id": "r29-student", "cert_type": "transfer"},
                       headers=_management())
    assert resp.status_code == 200
    cert = resp.json()["data"]
    assert cert["cert_type"] == "transfer_certificate"
    # And, the point of the whole exercise, it did NOT auto-issue.
    assert cert["status"] == "pending_approval"


def test_the_owner_still_issues_a_transfer_certificate_directly(client, fake_db):
    resp = client.post("/api/ops/certificates",
                       json={"student_id": "r29-student", "cert_type": "transfer"},
                       headers=_owner())
    assert resp.json()["data"]["status"] == "generated"


def test_an_award_is_issued_without_approval_even_for_the_office(client, fake_db):
    resp = client.post("/api/ops/certificates",
                       json={"student_id": "r29-student", "cert_type": "sports"},
                       headers=_management())
    assert resp.json()["data"]["status"] == "generated"


# ── The printer refuses what nobody approved ─────────────────────────────────

def test_the_office_cannot_print_a_transfer_certificate_with_no_approval(client, fake_db):
    resp = client.post("/api/image-gen/certificate",
                       json={"student_id": "r29-student", "cert_type": "transfer"},
                       headers=_management())
    assert resp.status_code == 403
    assert "approved" in resp.json()["detail"].lower()


def test_the_office_cannot_print_while_the_request_is_still_waiting(client, fake_db):
    created = client.post("/api/ops/certificates",
                          json={"student_id": "r29-student", "cert_type": "transfer"},
                          headers=_management()).json()["data"]
    assert created["status"] == "pending_approval"

    resp = client.post("/api/image-gen/certificate",
                       json={"student_id": "r29-student", "cert_type": "transfer",
                             "cert_id": created["id"]},
                       headers=_management())
    assert resp.status_code == 403
    assert "waiting" in resp.json()["detail"].lower()


def test_the_office_can_print_once_the_principal_has_approved(client, fake_db):
    created = client.post("/api/ops/certificates",
                          json={"student_id": "r29-student", "cert_type": "transfer"},
                          headers=_management()).json()["data"]
    approved = client.patch(f"/api/ops/certificates/{created['id']}/approve",
                            headers=_principal())
    assert approved.status_code == 200

    resp = client.post("/api/image-gen/certificate",
                       json={"student_id": "r29-student", "cert_type": "transfer",
                             "cert_id": created["id"]},
                       headers=_management())
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"


def test_a_rejected_request_still_cannot_be_printed(client, fake_db):
    created = client.post("/api/ops/certificates",
                          json={"student_id": "r29-student", "cert_type": "bonafide"},
                          headers=_management()).json()["data"]
    client.patch(f"/api/ops/certificates/{created['id']}/reject",
                 json={"reason": "wrong child"}, headers=_principal())

    resp = client.post("/api/image-gen/certificate",
                       json={"student_id": "r29-student", "cert_type": "bonafide",
                             "cert_id": created["id"]},
                       headers=_management())
    assert resp.status_code == 403


def test_an_approval_cannot_be_reused_for_a_different_document(client, fake_db):
    # A Sports Certificate needs nobody's approval, so the office can always get one
    # issued. Without this check that harmless approval could be handed to the printer
    # to produce a Transfer Certificate.
    sports = client.post("/api/ops/certificates",
                         json={"student_id": "r29-student", "cert_type": "sports"},
                         headers=_management()).json()["data"]

    resp = client.post("/api/image-gen/certificate",
                       json={"student_id": "r29-student", "cert_type": "transfer",
                             "cert_id": sports["id"]},
                       headers=_management())
    assert resp.status_code == 403
    assert "not a" in resp.json()["detail"].lower()


def test_an_approval_cannot_be_reused_for_a_different_student(client, fake_db):
    fake_db.students.docs.append({
        "id": "r29-other", "schoolId": "aaryans-joya", "name": "Another Child",
        "admission_number": "R29-2", "is_active": True,
    })
    created = client.post("/api/ops/certificates",
                          json={"student_id": "r29-student", "cert_type": "bonafide"},
                          headers=_management()).json()["data"]
    client.patch(f"/api/ops/certificates/{created['id']}/approve", headers=_owner())

    resp = client.post("/api/image-gen/certificate",
                       json={"student_id": "r29-other", "cert_type": "bonafide",
                             "cert_id": created["id"]},
                       headers=_management())
    assert resp.status_code == 403
    assert "different student" in resp.json()["detail"].lower()
    fake_db.students.docs[:] = [d for d in fake_db.students.docs if d.get("id") != "r29-other"]


def test_leadership_prints_without_any_approval_request(client, fake_db):
    for headers, who in ((_owner(), "owner"), (_principal(), "principal")):
        resp = client.post("/api/image-gen/certificate",
                           json={"student_id": "r29-student", "cert_type": "transfer"},
                           headers=headers)
        assert resp.status_code == 200, f"the {who} was made to ask permission of themselves"


def test_an_award_still_prints_straight_away_for_the_office(client, fake_db):
    resp = client.post("/api/image-gen/certificate",
                       json={"student_id": "r29-student", "cert_type": "sports"},
                       headers=_management())
    assert resp.status_code == 200


def test_a_refused_print_does_not_spend_the_daily_cap(client, fake_db):
    fake_db.image_gen_quota.docs.clear()
    client.post("/api/image-gen/certificate",
                json={"student_id": "r29-student", "cert_type": "transfer"},
                headers=_management())
    assert not fake_db.image_gen_quota.docs, (
        "a document the school refused to print still counted against its daily limit"
    )


# ── ID cards, under the same rule ────────────────────────────────────────────

def test_the_office_cannot_print_id_cards_with_no_approval(client, fake_db):
    resp = client.post("/api/image-gen/id-cards",
                       json={"students": [{"student_id": "r29-student"}]},
                       headers=_management())
    assert resp.status_code == 403
    assert "approved" in resp.json()["detail"].lower()


def test_leadership_prints_id_cards_directly(client, fake_db):
    for headers in (_owner(), _principal()):
        resp = client.post("/api/image-gen/id-cards",
                           json={"students": [{"student_id": "r29-student"}]},
                           headers=headers)
        assert resp.status_code == 200


def test_one_request_covers_a_whole_batch(client, fake_db):
    resp = client.post("/api/ops/certificates/id-card-request",
                       json={"student_ids": ["r29-student", "r29-student", "s-2", "s-3"]},
                       headers=_management())
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["cert_type"] == "id_card"
    assert data["status"] == "pending_approval"
    # Duplicates collapse; a class of forty is one row for the principal, not forty.
    assert data["student_ids"] == ["r29-student", "s-2", "s-3"]


def test_the_office_can_print_id_cards_once_approved(client, fake_db):
    req = client.post("/api/ops/certificates/id-card-request",
                      json={"student_ids": ["r29-student"]},
                      headers=_management()).json()["data"]
    client.patch(f"/api/ops/certificates/{req['id']}/approve", headers=_principal())

    resp = client.post("/api/image-gen/id-cards",
                       json={"students": [{"student_id": "r29-student"}],
                             "request_id": req["id"]},
                       headers=_management())
    assert resp.status_code == 200


def test_an_id_card_approval_cannot_be_stretched_to_cover_more_children(client, fake_db):
    # The replay attack this guards: approval for one child, print for the whole roll.
    fake_db.students.docs.append({
        "id": "r29-other", "schoolId": "aaryans-joya", "name": "Another Child",
        "admission_number": "R29-2", "is_active": True,
    })
    req = client.post("/api/ops/certificates/id-card-request",
                      json={"student_ids": ["r29-student"]},
                      headers=_management()).json()["data"]
    client.patch(f"/api/ops/certificates/{req['id']}/approve", headers=_principal())

    resp = client.post("/api/image-gen/id-cards",
                       json={"students": [{"student_id": "r29-student"},
                                          {"student_id": "r29-other"}],
                             "request_id": req["id"]},
                       headers=_management())
    assert resp.status_code == 403
    assert "not covered" in resp.json()["detail"].lower()
    fake_db.students.docs[:] = [d for d in fake_db.students.docs if d.get("id") != "r29-other"]


# ── The two security tests every new endpoint needs ──────────────────────────

def test_id_card_request_unauthenticated_returns_401(client):
    resp = client.post("/api/ops/certificates/id-card-request", json={"student_ids": ["x"]})
    assert resp.status_code == 401


def test_id_card_request_wrong_role_returns_403(client):
    headers = _bearer({"user_id": "r29-t", "role": "teacher", "name": "T"})
    resp = client.post("/api/ops/certificates/id-card-request",
                       json={"student_ids": ["x"]}, headers=headers)
    assert resp.status_code == 403


def test_id_card_request_is_refused_to_the_desks_that_cannot_print(client):
    # Deliberately NOT require_role("admin", "owner"): that is every admin desk in the
    # school and would hand a write route to the five dormant profiles, which have none.
    # The accountant head was on this list until 2026-08-11 and is now on the other side
    # of it — see the accountant tests below.
    for sub_category in ("receptionist", "it_tech", "maintenance", "support_staff",
                         "transport_head"):
        headers = _bearer({"user_id": "r29-x", "role": "admin",
                           "sub_category": sub_category, "name": "X"})
        resp = client.post("/api/ops/certificates/id-card-request",
                           json={"student_ids": ["r29-student"]}, headers=headers)
        assert resp.status_code == 403, f"{sub_category} could raise an ID-card request"


# ── The accountant head, added 2026-08-11 ────────────────────────────────────
#
# Abhimanyu, 2026-08-11: Sonu hands parents printed documents too, so he gets the same
# two screens Lalit has. On exactly the same terms — he creates a request and waits.
# The pair of tests below is the whole instruction: he can reach the routes, and he
# cannot issue anything on his own.

def _accountant():
    return _bearer({"user_id": "r29-accountant", "role": "admin",
                    "sub_category": "accountant", "name": "Sonu Ruhal"})


def test_the_accountant_head_can_raise_a_certificate_request(client, fake_db):
    resp = client.post("/api/ops/certificates",
                       json={"student_id": "r29-student", "cert_type": "bonafide"},
                       headers=_accountant())
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "pending_approval"


def test_the_accountant_head_cannot_print_without_approval(client, fake_db):
    resp = client.post("/api/image-gen/certificate",
                       json={"student_id": "r29-student", "cert_type": "bonafide"},
                       headers=_accountant())
    assert resp.status_code == 403
    assert "approved" in resp.json()["detail"].lower()


def test_the_accountant_head_prints_once_either_of_the_two_has_approved(client, fake_db):
    # Both Aman and Adesh may approve. Either one is enough; the school did not ask for
    # two separate sign-offs on one document.
    for approver, who in ((_owner(), "the school's owner"), (_principal(), "the principal")):
        created = client.post("/api/ops/certificates",
                              json={"student_id": "r29-student", "cert_type": "bonafide"},
                              headers=_accountant()).json()["data"]
        assert client.patch(f"/api/ops/certificates/{created['id']}/approve",
                            headers=approver).status_code == 200

        resp = client.post("/api/image-gen/certificate",
                           json={"student_id": "r29-student", "cert_type": "bonafide",
                                 "cert_id": created["id"]},
                           headers=_accountant())
        assert resp.status_code == 200, f"approval by {who} did not let the print through"


def test_the_accountant_head_asks_for_id_cards_and_prints_once_approved(client, fake_db):
    req = client.post("/api/ops/certificates/id-card-request",
                      json={"student_ids": ["r29-student"]},
                      headers=_accountant()).json()["data"]
    assert req["status"] == "pending_approval"

    assert client.post("/api/image-gen/id-cards",
                       json={"students": [{"student_id": "r29-student"}]},
                       headers=_accountant()).status_code == 403

    client.patch(f"/api/ops/certificates/{req['id']}/approve", headers=_owner())
    resp = client.post("/api/image-gen/id-cards",
                       json={"students": [{"student_id": "r29-student"}],
                             "request_id": req["id"]},
                       headers=_accountant())
    assert resp.status_code == 200


def test_the_accountant_head_cannot_approve_his_own_request(client, fake_db):
    # The whole point of the rule. Reaching the screen must never become issuing.
    created = client.post("/api/ops/certificates",
                          json={"student_id": "r29-student", "cert_type": "transfer"},
                          headers=_accountant()).json()["data"]
    resp = client.patch(f"/api/ops/certificates/{created['id']}/approve",
                        headers=_accountant())
    assert resp.status_code == 403


def test_both_aman_and_adesh_are_told_a_document_is_waiting(client, fake_db):
    fake_db.users.docs.append({"id": "u-aman", "schoolId": "aaryans-joya",
                               "role": "owner", "name": "Aman Litt"})
    fake_db.users.docs.append({"id": "u-adesh", "schoolId": "aaryans-joya",
                               "role": "admin", "sub_category": "principal",
                               "name": "Adesh Singh"})
    before = len(fake_db.notifications.docs)

    client.post("/api/ops/certificates",
                json={"student_id": "r29-student", "cert_type": "transfer"},
                headers=_accountant())

    told = {n.get("user_id") for n in fake_db.notifications.docs[before:]}
    assert {"u-aman", "u-adesh"} <= told, (
        "an approval request has to reach BOTH of the people who may approve it"
    )
    fake_db.users.docs[:] = [
        d for d in fake_db.users.docs if d.get("id") not in ("u-aman", "u-adesh")
    ]


# ── The name shown to a person ───────────────────────────────────────────────

def test_the_document_is_called_the_same_thing_everywhere():
    assert document_label("transfer") == "Transfer Certificate"
    assert document_label("tc") == "Transfer Certificate"
    assert document_label("transfer_certificate") == "Transfer Certificate"
    assert document_label("id_card") == "Student ID Cards"
