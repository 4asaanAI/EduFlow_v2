"""Owner decision 2026-08-04: "Aaryans has only one branch, make EduFlow one-branch
specific." D-29 and D-53.

Two places read school-wide while everything around them read one branch:

- the expense export (D-29), the only export that did not scope
- certificates and ID cards, plus their daily generation cap (D-53)

Neither changes anything visible today, because there is exactly one branch and all
1,802 students sit on it. The tests therefore have to create a SECOND branch to prove
the rule exists at all — the same reason these were invisible for months.

The owner carries no branch and must keep reading across, which is the half of this
that is easy to break: a fix that scopes everyone equally locks the school's owner out
of their own school.
"""

from __future__ import annotations

import pytest

from middleware.auth import create_jwt

def _bearer(payload: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


def _owner():
    return _bearer({"user_id": "ob-owner", "role": "owner", "name": "Owner"})


def _principal(branch: str):
    return _bearer({
        "user_id": f"ob-prin-{branch}", "role": "admin", "sub_category": "principal",
        "branch_id": branch, "name": "Principal",
    })


def _accountant(branch: str):
    return _bearer({
        "user_id": f"ob-acc-{branch}", "role": "admin", "sub_category": "accountant",
        "branch_id": branch, "name": "Accountant",
    })


_TOUCHED = ("students", "expenses", "image_gen_quota", "classes")


@pytest.fixture(autouse=True)
def _clean(fake_db):
    saved = {name: list(getattr(fake_db, name).docs) for name in _TOUCHED}
    for name in _TOUCHED:
        getattr(fake_db, name).docs[:] = []
    yield
    for name in _TOUCHED:
        getattr(fake_db, name).docs[:] = saved[name]


def _two_branches_of_expenses(fake_db):
    fake_db.expenses.docs.extend([
        {"id": "e-a", "schoolId": "aaryans-joya", "branch_id": "branch-joya",
         "date": "2026-08-01", "category": "Repairs", "amount": 500, "description": "Own branch"},
        {"id": "e-b", "schoolId": "aaryans-joya", "branch_id": "branch-other",
         "date": "2026-08-02", "category": "Repairs", "amount": 900, "description": "Other branch"},
    ])


def _two_branches_of_students(fake_db):
    fake_db.students.docs.extend([
        {"id": "s-own", "schoolId": "aaryans-joya", "branch_id": "branch-joya",
         "name": "Own Branch Child", "is_active": True, "admission_number": "A-1"},
        {"id": "s-other", "schoolId": "aaryans-joya", "branch_id": "branch-other",
         "name": "Other Branch Child", "is_active": True, "admission_number": "A-2"},
    ])


# ── D-29 — the expense export ────────────────────────────────────────────────

def test_accountant_export_shows_only_their_own_branch(client, fake_db):
    _two_branches_of_expenses(fake_db)

    resp = client.get("/api/export/expenses?format=csv", headers=_accountant("branch-joya"))
    assert resp.status_code == 200
    body = resp.text
    assert "Own branch" in body
    assert "Other branch" not in body, (
        "a branch-bound accountant exported another branch's spending — this is D-29"
    )


def test_owner_export_still_shows_every_branch(client, fake_db):
    """The half that is easy to break. The owner has no branch and reads across."""
    _two_branches_of_expenses(fake_db)

    resp = client.get("/api/export/expenses?format=csv", headers=_owner())
    assert resp.status_code == 200
    assert "Own branch" in resp.text
    assert "Other branch" in resp.text


# ── D-53 — certificates and ID cards ─────────────────────────────────────────

def test_principal_cannot_issue_a_certificate_for_another_branchs_student(client, fake_db):
    _two_branches_of_students(fake_db)

    resp = client.post(
        "/api/image-gen/certificate",
        json={"student_id": "s-other", "cert_type": "bonafide"},
        headers=_principal("branch-joya"),
    )
    # 404, the same answer as a student who does not exist: telling them the child is
    # enrolled elsewhere is itself information they are not entitled to.
    assert resp.status_code == 404


def test_principal_can_still_issue_for_their_own_students(client, fake_db):
    _two_branches_of_students(fake_db)

    resp = client.post(
        "/api/image-gen/certificate",
        json={"student_id": "s-own", "cert_type": "bonafide"},
        headers=_principal("branch-joya"),
    )
    assert resp.status_code == 200


def test_owner_can_still_issue_for_any_student(client, fake_db):
    _two_branches_of_students(fake_db)

    for student_id in ("s-own", "s-other"):
        resp = client.post(
            "/api/image-gen/certificate",
            json={"student_id": student_id, "cert_type": "bonafide"},
            headers=_owner(),
        )
        assert resp.status_code == 200, f"the owner was refused {student_id}"


def test_id_card_batch_omits_students_from_another_branch(client, fake_db):
    _two_branches_of_students(fake_db)

    resp = client.post(
        "/api/image-gen/id-cards",
        json={"students": [{"student_id": "s-own"}, {"student_id": "s-other"}]},
        headers=_principal("branch-joya"),
    )
    assert resp.status_code == 200
    # The other branch's child must not appear on a printed card.
    assert b"Other Branch Child" not in resp.content


def test_the_daily_cap_is_counted_per_branch(client, fake_db):
    """One school-wide pool meant one branch could exhaust another's allowance."""
    _two_branches_of_students(fake_db)
    fake_db.students.docs.append(
        {"id": "s-other-2", "schoolId": "aaryans-joya", "branch_id": "branch-other",
         "name": "Second Other Child", "is_active": True, "admission_number": "A-3"}
    )

    client.post("/api/image-gen/certificate", json={"student_id": "s-own"},
                headers=_principal("branch-joya"))

    counters = [d for d in fake_db.image_gen_quota.docs if d.get("kind") == "certificate"]
    assert counters, "no daily counter was written"
    assert all("branch_id" in d for d in counters), (
        "the daily cap is not keyed on the branch — one branch can still use up another's"
    )
    assert {d.get("branch_id") for d in counters} == {"branch-joya"}
