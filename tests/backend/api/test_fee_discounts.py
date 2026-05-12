"""
API Tests: Fee discount policy engine - EduFlow Backend.
"""


def _discount_type_payload(name="Sibling discount", value=10, value_type="percentage"):
    return {
        "name": name,
        "value": value,
        "value_type": value_type,
        "recurrence": "per-term",
        "reason_note": "Approved school policy",
    }


class TestFeeDiscountPolicy:
    def test_discount_type_catalog_create_update_and_audit(self, client, auth_headers, fake_db):
        created = client.post("/api/fees/discount-types", json=_discount_type_payload(), headers=auth_headers)
        discount_id = created.json()["data"]["id"]
        updated = client.patch(
            f"/api/fees/discount-types/{discount_id}",
            json={"name": "Sibling concession", "is_active": False, "reason_note": "Renamed for clarity"},
            headers=auth_headers,
        )
        active = client.get("/api/fees/discount-types", headers=auth_headers)
        all_items = client.get("/api/fees/discount-types?include_inactive=true", headers=auth_headers)

        assert created.status_code == 200
        assert updated.json()["data"]["name"] == "Sibling concession"
        assert active.json()["data"] == []
        assert len(all_items.json()["data"]) == 1
        assert fake_db.audit_logs.docs[-1]["action"] == "discount_type_update"

    def test_apply_multiple_discounts_returns_line_by_line_breakdown(self, client, auth_headers):
        sibling = client.post("/api/fees/discount-types", json=_discount_type_payload(), headers=auth_headers).json()["data"]
        hardship = client.post("/api/fees/discount-types", json=_discount_type_payload("Hardship grant", 500, "flat"), headers=auth_headers).json()["data"]

        for dtype in (sibling, hardship):
            response = client.post("/api/fees/discounts/apply", json={
                "student_id": "student-1",
                "discount_type_id": dtype["id"],
                "original_amount": 5000,
                "effective_from": "2026-05-01",
                "note": "Owner approved",
            }, headers=auth_headers)
            assert response.status_code == 200

        breakdown = client.get("/api/fees/discounts/student-1", headers=auth_headers).json()["data"]

        assert breakdown["original_amount"] == 5000
        assert len(breakdown["discounts"]) == 2
        assert breakdown["total_discount"] == 1000
        assert breakdown["payable_amount"] == 4000

    def test_owner_discount_impact_summary(self, client, auth_headers, fake_db):
        fake_db.fee_discount_types.docs.clear()
        fake_db.fee_discounts.docs.clear()
        dtype = client.post("/api/fees/discount-types", json=_discount_type_payload("Staff ward", 20, "percentage"), headers=auth_headers).json()["data"]
        client.post("/api/fees/discounts/apply", json={
            "student_id": "student-1",
            "discount_type_id": dtype["id"],
            "original_amount": 10000,
            "effective_from": "2026-05-01",
        }, headers=auth_headers)

        summary = client.get("/api/fees/discount-summary", headers=auth_headers)

        assert summary.status_code == 200
        assert summary.json()["data"]["total_expected_revenue"] == 10000
        assert summary.json()["data"]["total_discount_value"] == 2000
        assert summary.json()["data"]["discount_types"]["Staff ward"]["count"] == 1
