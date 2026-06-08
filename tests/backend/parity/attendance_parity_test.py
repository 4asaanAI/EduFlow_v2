"""Story A.1 — dual-entrypoint parity for attendance.

Drives the SAME seed through both write entrypoints — the REST route via
TestClient (full middleware/auth) and the AI `tool_mark_attendance` via its
real dispatch fn — and asserts the DB blast radius (records + audit) is
byte-identical except a volatile allowlist (`id`, `_id`, `created_at`,
`timestamp`). This is the AD10 dual-entrypoint gate (a direct service call from
both sides would be a tautology); the full normalizer/corpus harness lands in Epic F.
"""

from __future__ import annotations

import copy

import pytest

from ai import tool_functions_v2

pytestmark = pytest.mark.asyncio

_VOLATILE = {"id", "_id", "created_at", "timestamp"}

OWNER_USER = {"id": "admin-1", "role": "owner", "name": "Admin User"}
SEED = {
    "class_id": "class-1",
    "date": "2026-06-08",
    "records": [
        {"student_id": "student-1", "status": "present"},
        {"student_id": "student-9", "status": "absent"},
    ],
}


def _normalize(docs):
    out = []
    for doc in docs:
        masked = {k: v for k, v in doc.items() if k not in _VOLATILE}
        out.append(masked)
    out.sort(key=lambda d: (d.get("entity_id", ""), d.get("student_id", ""), d.get("status", "")))
    return out


def _snapshot(fake_db):
    return {
        "student_attendance": _normalize(copy.deepcopy(fake_db.student_attendance.docs)),
        "audit_logs": _normalize(
            [d for d in copy.deepcopy(fake_db.audit_logs.docs) if d.get("action") == "attendance_bulk"]
        ),
    }


def _clear(fake_db):
    for col in ("student_attendance", "audit_logs", "attendance_bulk_keys"):
        getattr(fake_db, col).docs[:] = []


@pytest.fixture(autouse=True)
def _clean(fake_db):
    _clear(fake_db)
    yield
    _clear(fake_db)


async def test_ai_and_rest_produce_identical_blast_radius(client, auth_headers, fake_db, monkeypatch):
    # --- REST entrypoint (no Idempotency-Key → no attendance_bulk_keys row) ---
    resp = client.post("/api/attendance/student/bulk", headers=auth_headers, json=SEED)
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db)

    # --- AI entrypoint (same seed, same owner) ---
    _clear(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    ai_result = await tool_functions_v2.tool_mark_attendance(
        {"class_id": SEED["class_id"], "date": SEED["date"],
         "attendance": [dict(r) for r in SEED["records"]]},
        OWNER_USER,
        None,
    )
    assert ai_result["success"] is True
    ai_state = _snapshot(fake_db)

    assert ai_state["student_attendance"] == rest_state["student_attendance"]
    assert ai_state["audit_logs"] == rest_state["audit_logs"]
    # Sanity: parity is non-trivial (records actually written).
    assert len(rest_state["student_attendance"]) == 2
    assert len(rest_state["audit_logs"]) == 1
