from __future__ import annotations

import pytest

from middleware.auth import create_jwt
from tests.backend.factories import make_class, make_student

pytestmark = pytest.mark.asyncio


def _owner_h():
    token = create_jwt({"user_id": "owner-fees", "role": "owner", "name": "School Owner", "branch_id": "branch-a"})
    return {"Authorization": f"Bearer {token}"}


def _accountant_h():
    token = create_jwt({"user_id": "acct-fees", "role": "admin", "sub_category": "accountant", "name": "Accountant", "branch_id": "branch-a"})
    return {"Authorization": f"Bearer {token}"}


def _student_h():
    token = create_jwt({"user_id": "student-user", "role": "student", "name": "Student", "branch_id": "branch-a"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _clean(fake_db):
    names = (
        "fee_structures", "fee_structure_revisions", "fee_transactions",
        "school_fee_checkouts", "students", "classes", "audit_logs",
    )
    originals = {name: list(getattr(fake_db, name).docs) for name in names}
    for name in names:
        getattr(fake_db, name).docs[:] = []
    yield
    for name, docs in originals.items():
        getattr(fake_db, name).docs[:] = docs


def _seed(fake_db):
    fake_db.classes.docs.append(make_class(id="class-fee", branch_id="branch-a"))
    fake_db.students.docs.extend([
        make_student(id="student-a", user_id="student-user", class_id="class-fee", branch_id="branch-a", name="A"),
        make_student(id="student-b", class_id="class-fee", branch_id="branch-a", name="B"),
    ])
    fake_db.fee_structures.docs.append({
        "id": "structure-1", "schoolId": "aaryans-joya", "name": "Class Fee",
        "class_id": "class-fee", "academic_year": "2026-27", "version": 1,
        "status": "active", "fee_heads": [],
    })


def _installments():
    return [{
        "code": "term-1", "label": "Term 1", "due_date": "2026-07-15",
        "fee_heads": [{"name": "Tuition", "amount": 12000}, {"name": "Exam", "amount": 1000}],
    }]


def test_owner_can_version_installments_and_preview_without_writes(client, fake_db):
    _seed(fake_db)
    saved = client.put(
        "/api/fees/structures/structure-1/installments",
        json={"installments": _installments()}, headers=_owner_h(),
    )
    assert saved.status_code == 200
    assert saved.json()["data"]["version"] == 2
    assert len(fake_db.fee_structure_revisions.docs) == 1

    preview = client.post(
        "/api/fees/structures/structure-1/charges/preview", json={}, headers=_accountant_h(),
    )
    assert preview.status_code == 200
    assert preview.json()["data"]["meta"] == {
        "student_count": 2, "charge_count": 4, "new_charge_count": 4, "total_amount": 26000.0,
    }
    assert fake_db.fee_transactions.docs == []


def test_charge_generation_is_idempotent(client, fake_db):
    _seed(fake_db)
    client.put(
        "/api/fees/structures/structure-1/installments",
        json={"installments": _installments()}, headers=_owner_h(),
    )
    first = client.post(
        "/api/fees/structures/structure-1/charges/generate", json={}, headers=_owner_h(),
    )
    second = client.post(
        "/api/fees/structures/structure-1/charges/generate", json={}, headers=_owner_h(),
    )
    assert first.json()["data"]["created_count"] == 4
    assert second.json()["data"] == {"created_count": 0, "skipped_count": 4, "charges": []}
    assert len(fake_db.fee_transactions.docs) == 4
    assert all(row["status"] == "pending" for row in fake_db.fee_transactions.docs)


def test_invalid_installment_is_rejected_without_mutation(client, fake_db):
    _seed(fake_db)
    response = client.put(
        "/api/fees/structures/structure-1/installments",
        json={"installments": [{"code": "term-1", "due_date": "bad", "fee_heads": []}]},
        headers=_owner_h(),
    )
    assert response.status_code == 400
    assert "installments" not in fake_db.fee_structures.docs[0]
    assert fake_db.fee_structure_revisions.docs == []


def test_student_cannot_generate_charges(client, fake_db):
    _seed(fake_db)
    response = client.post(
        "/api/fees/structures/structure-1/charges/generate", json={}, headers=_student_h(),
    )
    assert response.status_code == 403


def test_generate_charges_unauthenticated_returns_401(client):
    response = client.post("/api/fees/structures/structure-1/charges/generate", json={})
    assert response.status_code == 401


def test_student_checkout_only_accepts_own_charges(client, fake_db, monkeypatch):
    _seed(fake_db)
    fake_db.school_fee_checkouts.docs[:] = []
    fake_db.fee_transactions.docs = [
        {"id": "own-charge", "schoolId": "aaryans-joya", "branch_id": "branch-a", "student_id": "student-a", "amount": 500, "status": "pending"},
        {"id": "other-charge", "schoolId": "aaryans-joya", "branch_id": "branch-a", "student_id": "student-b", "amount": 700, "status": "pending"},
    ]
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret")

    class PaymentLink:
        def create(self, payload):
            assert payload["amount"] == 50000
            return {"id": "plink-school", "short_url": "https://rzp.io/i/school"}

    class Client:
        payment_link = PaymentLink()

    monkeypatch.setattr("services.razorpay_service._razorpay_client", lambda: Client())

    own = client.post(
        "/api/fees/online-checkout",
        json={"transaction_ids": ["own-charge"], "success_url": "https://school.example/fees"},
        headers=_student_h(),
    )
    foreign = client.post(
        "/api/fees/online-checkout", json={"transaction_ids": ["other-charge"]}, headers=_student_h(),
    )
    assert own.status_code == 200
    assert own.json()["data"]["checkout_url"] == "https://rzp.io/i/school"
    assert foreign.status_code == 403
    assert len(fake_db.school_fee_checkouts.docs) == 1
