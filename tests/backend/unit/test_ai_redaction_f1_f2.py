"""Story F.1 / F.2 — PII minimization to the LLM + trace PII scan.

F.1: `redact_for_llm` ships the model the minimum personal data — special-category
fields (DOB/contact/health/full-address/Aadhaar) are masked; identifiers/names pass.
F.2: `contains_unredacted_pii` finds zero unredacted PII in a redacted payload.
"""

from __future__ import annotations

import json

import pytest

from ai.redaction import redact_for_llm, contains_unredacted_pii, REDACTED

pytestmark = pytest.mark.asyncio


_STUDENT = {
    "id": "stu-1",
    "name": "Aarav Sharma",
    "admission_number": "ADM-100",
    "class_name": "5A",
    "date_of_birth": "2015-03-02",
    "dob": "2015-03-02",
    "home_address": "12 MG Road, Joya",
    "guardian_phone": "9876543210",
    "contact": "9876543210",
    "aadhaar_number": "1234 5678 9012",
    "blood_group": "O+",
    "medical_conditions": "asthma",
    "father_medical_history": "none",
    "fee_balance": 4500,
    "attendance_pct": 92,
}


def test_special_category_fields_are_masked():
    out = redact_for_llm(_STUDENT)
    for masked_key in (
        "date_of_birth", "dob", "home_address", "aadhaar_number",
        "blood_group", "medical_conditions", "father_medical_history",
    ):
        assert out[masked_key] == REDACTED, masked_key
    # phone/contact masked but not fully dropped (keeps last 3 for human reference)
    assert out["guardian_phone"] != "9876543210"
    assert "210" in out["guardian_phone"]


def test_identifiers_and_task_fields_pass_through():
    # Calibration: redaction must NOT over-block — names/ids/counts/amounts remain
    # so the assistant can still answer normally.
    out = redact_for_llm(_STUDENT)
    assert out["id"] == "stu-1"
    assert out["name"] == "Aarav Sharma"
    assert out["admission_number"] == "ADM-100"
    assert out["class_name"] == "5A"
    assert out["fee_balance"] == 4500
    assert out["attendance_pct"] == 92


def test_nested_and_list_redaction():
    payload = {"data": [{"name": "X", "dob": "2016-01-01", "phone": "9000000001"}]}
    out = redact_for_llm(payload)
    row = out["data"][0]
    assert row["name"] == "X"
    assert row["dob"] == REDACTED
    assert row["phone"] != "9000000001"


def test_redacted_payload_has_no_unredacted_pii():
    out = redact_for_llm(_STUDENT)
    blob = json.dumps(out)
    assert contains_unredacted_pii(blob) == []


def test_scanner_flags_raw_pii():
    raw = json.dumps(_STUDENT)
    found = contains_unredacted_pii(raw)
    assert found  # raw Aadhaar + raw phone present
