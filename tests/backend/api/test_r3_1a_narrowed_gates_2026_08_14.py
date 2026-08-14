from __future__ import annotations

"""R3-1a: the five gates narrowed after the R3-1 survey, 2026-08-14.

Sonu (accountant head) and Lalit (management head) were given their passwords on
2026-08-14, so two of the eight office desks stopped being theoretical. These five were
the only items that were both wrong against `profile_matrix.py` AND reachable by somebody
who now holds a credential.

Every test here asserts a NARROWING. Nothing in this file may ever be relaxed to make a
suite green: each line is a decision about what a named person at a real school may do.

The five:
  1. The message log stops handing the management head fee amounts.
  2. Transport is refused to the management head, reading the refusal off the table.
  3. The year-end promotion is the school owner's alone again.
  4. Marking a register is the owner, principal, accountant head and management head only.
  5. The branch records are the school owner's alone again.
"""

import pytest

from middleware.auth import create_jwt

OFFICE_DESKS = (
    "principal", "accountant", "management", "transport_head",
    "receptionist", "it_tech", "maintenance", "support_staff",
)
DORMANT_DESKS = ("transport_head", "receptionist", "it_tech", "maintenance", "support_staff")


def _bearer(role: str, sub_category: str | None = None) -> dict:
    payload = {
        "user_id": f"u-{sub_category or role}", "id": f"u-{sub_category or role}",
        "role": role, "name": "Test", "branch_id": "branch-joya",
    }
    if sub_category:
        payload["sub_category"] = sub_category
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


def _admin(sub_category: str) -> dict:
    return _bearer("admin", sub_category)


# ── 1. The message log ───────────────────────────────────────────────────────
#
# This was the money leak. A fee-reminder row stores an `amount` field AND the full
# message text naming a child and what their family owes, and every office desk could
# read it. Decision 1 of 2026-08-10: the management head never sees a rupee figure.

def test_message_log_refuses_the_management_head(client):
    assert client.get("/api/sms/logs", headers=_admin("management")).status_code == 403


@pytest.mark.parametrize("desk", DORMANT_DESKS)
def test_message_log_refuses_every_dormant_desk(client, desk):
    assert client.get("/api/sms/logs", headers=_admin(desk)).status_code == 403


@pytest.mark.parametrize("headers_desk", ["principal", "accountant"])
def test_message_log_still_open_to_principal_and_accountant_head(client, headers_desk):
    assert client.get("/api/sms/logs", headers=_admin(headers_desk)).status_code == 200


def test_message_log_still_open_to_the_schools_owner(client):
    assert client.get("/api/sms/logs", headers=_bearer("owner")).status_code == 200


# ── 2. Transport ─────────────────────────────────────────────────────────────
#
# The only case the survey found where the table says an explicit NO and the server said
# yes: decision 2 named five transport tools and DENIED them to the management head so the
# accountant head could run transport until the transport head's release.

TRANSPORT_READS = ("/api/ops/transport", "/api/ops/transport/vehicles", "/api/ops/transport/roster")


@pytest.mark.parametrize("path", TRANSPORT_READS)
def test_transport_refuses_the_management_head(client, path):
    assert client.get(path, headers=_admin("management")).status_code == 403


def test_transport_write_refuses_the_management_head(client):
    resp = client.post("/api/ops/transport", headers=_admin("management"), json={"route_name": "R1"})
    assert resp.status_code == 403


def test_transport_delete_refuses_the_management_head(client):
    resp = client.delete("/api/ops/transport/any-id", headers=_admin("management"))
    assert resp.status_code == 403


@pytest.mark.parametrize("path", TRANSPORT_READS)
def test_transport_still_open_to_the_accountant_head(client, path):
    # Decision 2 gives him transport in full until the transport head's release.
    assert client.get(path, headers=_admin("accountant")).status_code == 200


@pytest.mark.parametrize("path", TRANSPORT_READS)
def test_transport_still_open_to_owner_and_principal(client, path):
    assert client.get(path, headers=_bearer("owner")).status_code == 200
    assert client.get(path, headers=_admin("principal")).status_code == 200


def test_transport_refusal_is_read_from_the_table_not_hardcoded(monkeypatch, client):
    """Move the denial and the routes move with it.

    The point of R3-1a's transport fix is that the route asks `profile_matrix.py` rather
    than naming a profile. If somebody later hands transport back to the management head
    by editing the table, these routes must follow without anybody remembering this file.
    """
    from services.profile_matrix import PROFILE_MATRIX

    entry = dict(PROFILE_MATRIX["management"])
    entry["denied_tools"] = frozenset()
    monkeypatch.setitem(PROFILE_MATRIX, "management", entry)
    assert client.get("/api/ops/transport", headers=_admin("management")).status_code == 200


def test_transport_still_reaches_the_dormant_desks(client):
    """Deliberate, and NOT an endorsement.

    The five dormant desks can still reach transport.

    This test's name and reasoning changed on 2026-08-14, and the change matters. It
    originally said the gap closes when R3-0 lands. **R3-0 is now RETIRED, not parked**, so
    nothing is coming to close it centrally: Abhimanyu's decision is that a credential is
    handed out only once a profile is ready, which makes the lock redundant. See
    `implementation-artifacts/release-3-access/R3-0-retired-and-the-twenty-questions-2026-08-14.md`.

    So this now records an ACCEPTED gap rather than a queued one. What holds the line is a
    process rule and the fact that nobody holds a password, not code. Whoever narrows these
    desks in R3-2 or Release 4 (access) deletes this test as part of that decision.
    """
    assert client.get("/api/ops/transport", headers=_admin("support_staff")).status_code == 200


# ── 3. The year-end promotion ────────────────────────────────────────────────

@pytest.mark.parametrize("desk", OFFICE_DESKS)
def test_year_end_transition_refuses_every_office_desk(client, desk):
    resp = client.post("/api/settings/year-end-transition", headers=_admin(desk), json={})
    assert resp.status_code == 403, f"{desk} could promote the whole roll"


def test_year_end_transition_is_not_refused_for_the_schools_owner(client):
    resp = client.post("/api/settings/year-end-transition", headers=_bearer("owner"), json={})
    assert resp.status_code != 403


# ── 4. Marking a register ────────────────────────────────────────────────────
#
# Abhimanyu, 2026-08-14: marking stays with the owner, the principal, the accountant head
# and the management head. That KEEPS the accountant head, whom the table otherwise holds
# to attendance read-only, and it is a widening the school made on purpose.

MARKERS = ("principal", "accountant", "management")


@pytest.mark.parametrize("desk", DORMANT_DESKS)
def test_staff_register_refuses_every_dormant_desk(client, desk):
    resp = client.post("/api/attendance/staff/bulk", headers=_admin(desk), json={})
    assert resp.status_code == 403


@pytest.mark.parametrize("desk", DORMANT_DESKS)
def test_student_register_refuses_every_dormant_desk(client, desk):
    resp = client.post("/api/attendance/student/bulk", headers=_admin(desk), json={})
    assert resp.status_code == 403


@pytest.mark.parametrize("desk", MARKERS)
def test_staff_register_stays_with_all_four(client, desk):
    resp = client.post("/api/attendance/staff/bulk", headers=_admin(desk), json={})
    assert resp.status_code != 403
    resp = client.post("/api/attendance/staff/bulk", headers=_bearer("owner"), json={})
    assert resp.status_code != 403


@pytest.mark.parametrize("desk", MARKERS)
def test_student_register_stays_with_all_four(client, desk):
    resp = client.post("/api/attendance/student/bulk", headers=_admin(desk), json={})
    assert resp.status_code != 403


def test_teachers_still_mark_the_student_register(client):
    resp = client.post("/api/attendance/student/bulk", headers=_bearer("teacher"), json={})
    assert resp.status_code != 403


def test_teachers_still_cannot_mark_the_staff_register(client):
    resp = client.post("/api/attendance/staff/bulk", headers=_bearer("teacher"), json={})
    assert resp.status_code == 403


# ── 5. The branch records ────────────────────────────────────────────────────

@pytest.mark.parametrize("desk", OFFICE_DESKS)
def test_branch_records_refuse_every_office_desk(client, desk):
    assert client.get("/api/settings/branches", headers=_admin(desk)).status_code == 403


def test_branch_records_still_open_to_the_schools_owner(client):
    assert client.get("/api/settings/branches", headers=_bearer("owner")).status_code == 200


# ── The security convention: every one of these still refuses a stranger ─────

@pytest.mark.parametrize("method,path", [
    ("get", "/api/sms/logs"),
    ("get", "/api/ops/transport"),
    ("post", "/api/settings/year-end-transition"),
    ("post", "/api/attendance/staff/bulk"),
    ("post", "/api/attendance/student/bulk"),
    ("get", "/api/settings/branches"),
])
def test_unauthenticated_returns_401(client, method, path):
    assert getattr(client, method)(path).status_code == 401


@pytest.mark.parametrize("method,path", [
    ("get", "/api/sms/logs"),
    ("get", "/api/ops/transport"),
    ("post", "/api/settings/year-end-transition"),
    ("post", "/api/attendance/staff/bulk"),
    ("get", "/api/settings/branches"),
])
def test_student_role_returns_403(client, method, path):
    assert getattr(client, method)(path, headers=_bearer("student")).status_code == 403
