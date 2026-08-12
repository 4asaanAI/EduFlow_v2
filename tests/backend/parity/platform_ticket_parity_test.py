"""R4-5 - telling Layaa AI, from the screen and from Flo, must leave the same record.

Why this file earns its keep
--------------------------------------------------------------------------------

This is the only path in the platform that sends anything OUT of the school. If the
button and Flo record a report differently, the difference is invisible from inside the
school: both say "reported", and the divergence only shows up at our end, weeks later,
as tickets that are missing the very field we needed.

The parity gate caught a real bug in R4-2 when payroll's two entrances wrote a different
number of audit rows. The same class of mistake is easy here, because Flo's tool adds
`tried` and `expected` into the context and the screen does not.

What is pinned, and why each one:

* **Same ticket, same audit row.** The screen and Flo differ ONLY in `source`, which is
  the one field that is supposed to differ, and in the extra context Flo gathers.
* **A ticket survives a delivery failure.** The report exists whether or not Layaa AI
  could be reached. This is the whole store-first design and it is the thing that would
  quietly stop being true.
* **The person is told the truth either way.** A failed send says so in words, rather
  than reporting success for a report nobody received.
* **A student may raise one.** Not an accident of the missing role gate; a decision.
"""

from __future__ import annotations

import copy

import pytest
from middleware.auth import create_jwt

from ai import tool_functions_v2
from services import platform_ticket_service

pytestmark = pytest.mark.asyncio

_VOLATILE = {"id", "_id", "created_at", "updated_at", "last_attempt_at", "timestamp",
             "entity_id", "record_id", "external_ref", "layaastat_reference"}

OWNER_USER = {"id": "own-1", "role": "owner", "name": "Owner", "branch_id": ""}


def _headers(user_id="own-1", role="owner", name="Owner", sub_category=None):
    claims = {"user_id": user_id, "role": role, "name": name, "schoolId": "aaryans-joya"}
    if sub_category:
        claims["sub_category"] = sub_category
    return {"Authorization": "Bearer " + create_jwt(claims)}


@pytest.fixture(autouse=True)
def _no_real_network(monkeypatch, fake_db):
    """Nothing leaves this process, and delivery is made to succeed by default.

    The stand-in stands in for the SEND, never for the recording. Everything this file
    asserts about is written by our own code against the fake database.
    """
    async def _ok(payload):
        return {
            "delivered": True, "reason": "Sent to Layaa AI.",
            "reference": "layaa-1", "ticket_number": 41,
            "screenshot_stored": False, "screenshot_rejected": False,
            "people_notified": 1,
        }
    monkeypatch.setattr(platform_ticket_service.layaastat_tickets, "send_ticket", _ok)
    _clear(fake_db)
    yield
    _clear(fake_db)


def _clear(fake_db):
    for col in ("platform_tickets", "audit_logs"):
        getattr(fake_db, col).docs[:] = []


def _mask(docs):
    out = [{k: v for k, v in d.items() if k not in _VOLATILE} for d in docs]
    out.sort(key=lambda d: (str(d.get("title", "")), str(d.get("action", ""))))
    return out


def _snapshot(fake_db):
    return {
        "platform_tickets": _mask(copy.deepcopy(fake_db.platform_tickets.docs)),
        "audit_logs": _mask([
            a for a in copy.deepcopy(fake_db.audit_logs.docs)
            if a.get("entity_type") == "platform_tickets"
        ]),
    }


_REPORT = {
    "title": "The fee collection screen will not open",
    "detail": "It spins and then goes blank. Started this morning.",
    "kind": "bug",
    "priority": "high",
}


async def test_screen_and_flo_record_the_same_ticket(client, fake_db):
    resp = client.post("/api/issues/platform", json=dict(_REPORT), headers=_headers())
    assert resp.status_code == 200, resp.text
    rest_state = _snapshot(fake_db)
    _clear(fake_db)

    result = await tool_functions_v2.TOOL_REGISTRY["report_platform_problem"]["fn"](
        dict(_REPORT), OWNER_USER, None
    )
    assert result["success"] is True
    ai_state = _snapshot(fake_db)

    # Exactly two differences are allowed, and both are deliberate: Flo marks the ticket
    # as raised by the assistant, and Flo's context carries the school id it was given.
    # Everything else, including the audit row, must be identical.
    assert len(ai_state["platform_tickets"]) == len(rest_state["platform_tickets"]) == 1
    assert len(ai_state["audit_logs"]) == len(rest_state["audit_logs"]) == 1

    ai_ticket = dict(ai_state["platform_tickets"][0])
    rest_ticket = dict(rest_state["platform_tickets"][0])
    assert rest_ticket.pop("source") == "person"
    assert ai_ticket.pop("source") == "assistant"
    assert ai_ticket == rest_ticket

    ai_audit = dict(ai_state["audit_logs"][0])
    rest_audit = dict(rest_state["audit_logs"][0])
    # The audit row records the source too, so the two rows differ there and only there.
    assert ai_audit["changes"]["snapshot"].pop("source") == "assistant"
    assert rest_audit["changes"]["snapshot"].pop("source") == "person"
    assert ai_audit == rest_audit


async def test_the_audit_row_is_in_the_r4_1_shape(client, fake_db):
    """A created record, not an edit. There was no previous value and none is claimed."""
    from services import audit_changes

    client.post("/api/issues/platform", json=dict(_REPORT), headers=_headers())
    rows = [a for a in fake_db.audit_logs.docs if a.get("entity_type") == "platform_tickets"]
    assert len(rows) == 1
    assert rows[0]["action"] == "platform_ticket_raise"
    assert audit_changes.is_canonical(rows[0]["changes"])
    assert rows[0]["changes"]["kind"] == "create"


async def test_a_student_may_report_a_broken_platform(client, fake_db):
    """A decision, not an oversight. The person most likely to see a screen that will
    not load is whoever was using it, and a report we refuse is a fault we hear about
    a week later."""
    resp = client.post(
        "/api/issues/platform",
        json={"title": "I cannot open my timetable"},
        headers=_headers(user_id="stu-1", role="student", name="Aryan"),
    )
    assert resp.status_code == 200, resp.text
    assert len(fake_db.platform_tickets.docs) == 1


async def test_reporting_requires_signing_in(client):
    assert client.post("/api/issues/platform", json={"title": "x"}).status_code == 401


async def test_listing_someone_elses_tickets_is_refused_to_a_student(client, fake_db):
    """Raising is open to everybody. READING other people's is not.

    Without this a student would see every fault the school's owner ever reported,
    which is a list of everything wrong with the school's platform.
    """
    client.post("/api/issues/platform", json=dict(_REPORT), headers=_headers())
    resp = client.get("/api/issues/platform", headers=_headers(user_id="stu-1", role="student", name="Aryan"))
    assert resp.status_code == 200
    # Not a 403: a student has a perfectly good list, it just holds only their own.
    # Refusing the whole screen would teach them the feature is not for them.
    assert resp.json()["data"] == []
    assert resp.json()["meta"]["total"] == 0


async def test_the_ticket_survives_a_failed_delivery_and_says_so(client, fake_db, monkeypatch):
    """The whole reason the ticket is written down before it is sent."""
    async def _down(payload):
        return {"delivered": False, "code": "unreachable",
                "reason": "Layaa AI could not be reached just now. The ticket is saved here and can be sent again."}
    monkeypatch.setattr(platform_ticket_service.layaastat_tickets, "send_ticket", _down)

    resp = client.post("/api/issues/platform", json=dict(_REPORT), headers=_headers())
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    # The report EXISTS.
    assert len(fake_db.platform_tickets.docs) == 1
    assert data["delivered"] is False
    # And the person is told the truth, in words, rather than "reported successfully".
    assert "has not reached Layaa AI yet" in data["message"]
    assert "can be sent again" in data["message"]


async def test_a_delivery_failure_does_not_lose_the_audit_row_either(client, fake_db, monkeypatch):
    async def _down(payload):
        return {"delivered": False, "code": "refused", "reason": "Layaa AI refused this ticket."}
    monkeypatch.setattr(platform_ticket_service.layaastat_tickets, "send_ticket", _down)
    client.post("/api/issues/platform", json=dict(_REPORT), headers=_headers())
    rows = [a for a in fake_db.audit_logs.docs if a.get("entity_type") == "platform_tickets"]
    assert len(rows) == 1, "the change was recorded even though nobody received it"


async def test_a_ticket_with_no_title_is_refused_in_words(client, fake_db):
    resp = client.post("/api/issues/platform", json={"detail": "it broke"}, headers=_headers())
    assert resp.status_code == 400
    assert "one line" in resp.json()["detail"]
    assert fake_db.platform_tickets.docs == []


async def test_resending_a_delivered_ticket_does_not_send_it_twice(client, fake_db):
    resp = client.post("/api/issues/platform", json=dict(_REPORT), headers=_headers())
    ticket_id = resp.json()["data"]["id"]

    again = client.post(f"/api/issues/platform/{ticket_id}/resend", headers=_headers())
    assert again.status_code == 200
    assert "already reached Layaa AI" in again.json()["data"]["message"]


async def test_a_student_cannot_resend_somebody_elses_ticket(client, fake_db):
    resp = client.post("/api/issues/platform", json=dict(_REPORT), headers=_headers())
    ticket_id = resp.json()["data"]["id"]
    again = client.post(
        f"/api/issues/platform/{ticket_id}/resend",
        headers=_headers(user_id="stu-1", role="student", name="Aryan"),
    )
    assert again.status_code == 403


async def test_flo_writes_what_it_already_tried_into_the_ticket(fake_db):
    """The field that stops a ticket for something fixable in ten seconds.

    It is required at the chat gate, and it has to land somewhere we will actually read
    it, or requiring it achieves nothing.
    """
    await tool_functions_v2.TOOL_REGISTRY["report_platform_problem"]["fn"](
        {**_REPORT, "tried": "Signed out and back in, and checked the date filter.",
         "expected": "The list of payments for today."},
        OWNER_USER, None,
    )
    ticket = fake_db.platform_tickets.docs[0]
    assert ticket["context"]["what_flo_already_tried"].startswith("Signed out")
    assert ticket["context"]["what_they_expected"] == "The list of payments for today."


async def test_an_oversized_screenshot_is_dropped_and_the_person_is_told(client, fake_db):
    """Silently dropping it would leave them believing we can see what they saw."""
    huge = "A" * (platform_ticket_service.MAX_SCREENSHOT_CHARS + 1)
    resp = client.post(
        "/api/issues/platform",
        json={**_REPORT, "screenshot_base64": huge},
        headers=_headers(),
    )
    data = resp.json()["data"]
    assert data["screenshot_dropped_too_large"] is True
    assert data["had_screenshot"] is False
    assert "too large" in data["message"]
