"""
API Tests: Fee CRUD and idempotency - EduFlow Backend.
"""

from datetime import datetime, timedelta


def _payment_payload():
    return {
        "student_id": "student-1",
        "fee_period": "2026-05",
        "fee_head": "tuition",
        "fee_type": "tuition",
        "amount": 2500,
        "payment_mode": "upi",
        "status": "paid",
        "due_date": "2026-05-10",
    }


class TestFeeCrud:
    def test_payment_create_is_idempotent_for_twenty_four_hours(self, client, auth_headers, fake_db):
        fake_db.fee_transactions.docs.clear()
        fake_db.fee_idempotency_keys.docs.clear()
        headers = {**auth_headers, "Idempotency-Key": "student-1|2026-05|tuition"}

        first = client.post("/api/fees/transactions", json=_payment_payload(), headers=headers)
        second = client.post("/api/fees/transactions", json=_payment_payload(), headers=headers)

        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["idempotent"] is True
        assert first.json()["data"]["id"] == second.json()["data"]["id"]
        assert len(fake_db.fee_transactions.docs) == 1

    def test_payment_rejects_bad_idempotency_key(self, client, auth_headers):
        response = client.post(
            "/api/fees/transactions",
            json=_payment_payload(),
            headers={**auth_headers, "Idempotency-Key": "wrong"},
        )

        assert response.status_code == 400

    def test_fee_correction_preserves_original_and_requires_reason(self, client, auth_headers, fake_db):
        headers = {**auth_headers, "Idempotency-Key": "student-1|2026-05|tuition"}
        created = client.post("/api/fees/transactions", json=_payment_payload(), headers=headers).json()["data"]

        missing_reason = client.patch(f"/api/fees/transactions/{created['id']}/correct", json={"amount": 2600}, headers=auth_headers)
        corrected = client.patch(
            f"/api/fees/transactions/{created['id']}/correct",
            json={"amount": 2600, "reason": "Bank settlement corrected the amount"},
            headers=auth_headers,
        )

        assert missing_reason.status_code == 400
        assert corrected.status_code == 200
        assert corrected.json()["data"]["amount"] == 2600
        assert fake_db.fee_transaction_corrections.docs[0]["original_record"]["amount"] == 2500
        assert fake_db.audit_logs.docs[-1]["action"] == "correct"

    def test_overdue_query_summary_status_and_contact_log(self, client, auth_headers, fake_db):
        old_due = (datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d")
        fake_db.fee_transactions.docs.append({
            "_id": "fee-overdue-1",
            "id": "fee-overdue-1",
            "schoolId": "aaryans-joya",
            "student_id": "student-1",
            "fee_type": "tuition",
            "fee_head": "tuition",
            "fee_period": "2026-04",
            "amount": 3000,
            "status": "overdue",
            "due_date": old_due,
            "created_at": datetime.now().isoformat(),
        })

        overdue = client.get("/api/fees/transactions?overdue_days=30", headers=auth_headers)
        summary = client.get("/api/fees/summary?fee_period=2026-04", headers=auth_headers)
        status = client.get("/api/fees/status/student-1", headers=auth_headers)
        contact = client.post("/api/fees/contact-log", json={
            "student_id": "student-1",
            "fee_transaction_id": "fee-overdue-1",
            "date": "2026-05-12",
            "contact_type": "call",
            "outcome": "Parent promised payment by Friday",
            "notes": "Called primary guardian",
        }, headers=auth_headers)

        assert overdue.status_code == 200
        assert len(overdue.json()["data"]) == 1
        assert summary.json()["data"]["total_outstanding"] == 3000
        assert summary.json()["data"]["defaulters"] == 1
        assert status.json()["data"]["status"] == "overdue"
        assert contact.status_code == 200
        assert fake_db.fee_contact_logs.docs[0]["contact_type"] == "call"

    def test_fee_transaction_hard_delete_rejected(self, client, auth_headers):
        response = client.delete("/api/fees/transactions/fee-1", headers=auth_headers)

        assert response.status_code == 405
