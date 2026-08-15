"""Approvals: one workflow for every approval. 2026-08-15.

**What these tests are for.** Six working approval systems were put behind one screen.
The danger in that is not a broken button; it is that somebody quietly gains the ability
to approve something that was never theirs. So most of what is below asserts a REFUSAL.

**If one of these starts failing, the question is who decided that, not how to make it
pass.** That rule has held through R3-0, R3-1a and R3-2 and it holds here.
"""

from __future__ import annotations

import pytest

from middleware.auth import create_jwt
from services import approval_registry as registry


def _h(**claims):
    return {"Authorization": f"Bearer {create_jwt({'name': 'T', **claims})}"}


OWNER = {"id": "aman", "role": "owner", "name": "Aman"}
PRINCIPAL = {"id": "adesh", "role": "admin", "sub_category": "principal", "name": "Adesh"}
ACCOUNTANT = {"id": "sonu", "role": "admin", "sub_category": "accountant", "name": "Sonu"}
MANAGEMENT = {"id": "lalit", "role": "admin", "sub_category": "management", "name": "Lalit"}
TRANSPORT = {"id": "chaman", "role": "admin", "sub_category": "transport_head", "name": "Chaman"}
TEACHER = {"id": "teach1", "role": "teacher", "name": "A Teacher"}
OTHER_TEACHER = {"id": "teach2", "role": "teacher", "name": "Another Teacher"}
STUDENT = {"id": "kid", "role": "student", "name": "A Child"}

SCHOOL = "aaryans-joya"


def _bearer(person):
    return _h(user_id=person["id"], role=person["role"],
              sub_category=person.get("sub_category"))


# ── 1. The registry itself ───────────────────────────────────────────────────
#
# The whole promise of this work is that a SEVENTH kind of approval joins by declaring
# itself. A kind that is half-declared would appear on the screen and then fail when
# somebody pressed a button, which is worse than not appearing at all.


REQUIRED_KEYS = {
    "label", "collection", "pending_statuses", "raised_by_field", "raised_at_field",
    "who_decides", "steps", "may_decide", "decide", "title", "detail",
}


def test_every_kind_declares_everything_the_screen_needs():
    assert registry.APPROVAL_KINDS, "the registry must not be empty"
    for name, entry in registry.APPROVAL_KINDS.items():
        missing = REQUIRED_KEYS - set(entry)
        assert not missing, f"the '{name}' kind is missing {sorted(missing)}"


def test_all_six_of_the_platforms_approval_systems_are_on_the_one_workflow():
    """The scope was deliberately all six, not the general one first.

    Named individually rather than counted, because a count stays green while somebody
    swaps one kind for another.
    """
    assert set(registry.APPROVAL_KINDS) == {
        "general", "certificate", "staff_leave", "announcement",
        "staff_profile_change", "student_leave",
    }


def test_student_leave_is_the_only_two_step_kind():
    two_step = {n for n, e in registry.APPROVAL_KINDS.items() if e["steps"] > 1}
    assert two_step == {"student_leave"}


# ── 2. Nobody may decide anything they could not decide yesterday ────────────


@pytest.mark.parametrize("person,expected", [
    (OWNER, True),
    (PRINCIPAL, True),
    (ACCOUNTANT, False),
    (MANAGEMENT, False),
    (TRANSPORT, False),
    (TEACHER, False),
    (STUDENT, False),
])
async def test_who_may_decide_a_request_routed_to_both(fake_db, person, expected):
    doc = {"id": "a1", "schoolId": SCHOOL, "routing": "owner_and_principal",
           "status": "pending", "submitted_by": TRANSPORT["id"]}
    assert await registry.may_decide(fake_db, "general", person, doc) is expected


async def test_the_principal_may_not_decide_a_request_meant_for_the_owner_alone(fake_db):
    """This is the hole the shared decision service was written to close in the first
    place, and a shared SCREEN is exactly the kind of change that would reopen it."""
    doc = {"id": "a2", "schoolId": SCHOOL, "routing": "owner_only", "status": "pending",
           "submitted_by": ACCOUNTANT["id"]}
    assert await registry.may_decide(fake_db, "general", PRINCIPAL, doc) is False
    assert await registry.may_decide(fake_db, "general", OWNER, doc) is True


@pytest.mark.parametrize("kind", ["certificate", "staff_leave", "announcement"])
@pytest.mark.parametrize("person,expected", [
    (OWNER, True), (PRINCIPAL, True), (ACCOUNTANT, False),
    (MANAGEMENT, False), (TRANSPORT, False), (TEACHER, False), (STUDENT, False),
])
async def test_the_one_step_kinds_keep_owner_and_principal(fake_db, kind, person, expected):
    doc = {"id": "x", "schoolId": SCHOOL,
           "status": list(registry.APPROVAL_KINDS[kind]["pending_statuses"])[0]}
    assert await registry.may_decide(fake_db, kind, person, doc) is expected


async def test_announcements_keep_the_owner_as_well_as_the_principal(fake_db):
    """The plan's table said announcements were the principal's alone.

    The code has always let the owner or the principal decide one, and decision 22 says
    every kind keeps the approvers it has today. Confirmed by Abhimanyu on 2026-08-15
    after the difference was pointed out: the plan's table is what was wrong. Narrowing
    it here would have taken a power away from the school's owner as a side effect of
    building a screen.
    """
    doc = {"id": "ann1", "schoolId": SCHOOL, "status": "pending_approval"}
    assert await registry.may_decide(fake_db, "announcement", OWNER, doc) is True
    assert await registry.may_decide(fake_db, "announcement", PRINCIPAL, doc) is True


async def test_nobody_may_wave_through_a_correction_to_their_own_details(fake_db):
    """A principal is an administrator. Without this they could ask for a change to
    their own record and approve it in one click, which is the exact self-editing the
    feature exists to prevent."""
    mine = {"id": "pc1", "schoolId": SCHOOL, "status": "pending",
            "user_id": PRINCIPAL["id"], "staff_id": "s1"}
    theirs = {**mine, "id": "pc2", "user_id": "somebody-else"}
    assert await registry.may_decide(fake_db, "staff_profile_change", PRINCIPAL, mine) is False
    assert await registry.may_decide(fake_db, "staff_profile_change", PRINCIPAL, theirs) is True
    assert await registry.may_decide(fake_db, "staff_profile_change", OWNER, mine) is True


# ── 3. Student leave: the two-step one, and the only one a teacher decides ───


@pytest.fixture
def _class_teacher(fake_db):
    """Put back exactly what was there.

    The stand-in database is shared across the whole session, so a fixture that clears a
    collection wholesale breaks a test in another file that happened to run later. That
    is what a first version of this did.
    """
    staff_before = list(fake_db.staff.docs)
    classes_before = list(fake_db.classes.docs)
    fake_db.staff.docs.append(
        {"id": "staff-t1", "schoolId": SCHOOL, "user_id": TEACHER["id"]})
    fake_db.classes.docs.append(
        {"id": "cls-9", "schoolId": SCHOOL, "class_teacher_id": "staff-t1"})
    yield
    fake_db.staff.docs[:] = staff_before
    fake_db.classes.docs[:] = classes_before


async def test_the_class_teacher_decides_the_first_step_for_their_own_class(
        fake_db, _class_teacher):
    doc = {"id": "sl1", "schoolId": SCHOOL, "status": "pending_teacher",
           "class_id": "cls-9", "submitted_by": STUDENT["id"]}
    assert await registry.may_decide(fake_db, "student_leave", TEACHER, doc) is True


async def test_a_teacher_decides_nothing_for_a_class_that_is_not_theirs(
        fake_db, _class_teacher):
    doc = {"id": "sl2", "schoolId": SCHOOL, "status": "pending_teacher",
           "class_id": "cls-9", "submitted_by": STUDENT["id"]}
    assert await registry.may_decide(fake_db, "student_leave", OTHER_TEACHER, doc) is False


async def test_a_teacher_may_not_touch_a_request_that_has_gone_up_to_the_principal(
        fake_db, _class_teacher):
    """A longer absence moves to the principal. If the class teacher could still decide
    it, the second step would be a formality anybody could skip."""
    doc = {"id": "sl3", "schoolId": SCHOOL, "status": "pending_principal",
           "class_id": "cls-9", "submitted_by": STUDENT["id"]}
    assert await registry.may_decide(fake_db, "student_leave", TEACHER, doc) is False
    assert await registry.may_decide(fake_db, "student_leave", PRINCIPAL, doc) is True


# ── 4. The card everybody reads ──────────────────────────────────────────────


def test_a_request_that_carries_an_action_says_so_on_its_card():
    """R3-2's rule survives the move onto the shared shape: a person has to be able to
    tell "I agree with this" from "do this now"."""
    doc = {
        "id": "a3", "schoolId": SCHOOL, "status": "pending", "routing": "owner_and_principal",
        "title": "Delete the bus route Joya Town", "description": "No longer used",
        "submitted_by": TRANSPORT["id"], "submitted_at": "2026-08-15T09:00:00+00:00",
        "approval_carries_out_the_action": True,
        "what_approving_does": "Agreeing to this DELETES the bus route straight away.",
        "pending_action": {"kind": "delete_transport_route", "route_id": "r1"},
    }
    card = registry.to_card("general", doc)
    assert card["carries_out_the_action"] is True
    assert "DELETES" in card["what_approving_does"]


def test_approving_a_correction_says_that_it_changes_the_record():
    doc = {"id": "pc3", "schoolId": SCHOOL, "status": "pending", "user_id": "u9",
           "staff_id": "s9", "requested": {"phone": "99999"},
           "created_at": "2026-08-15T09:00:00+00:00"}
    card = registry.to_card("staff_profile_change", doc)
    assert card["carries_out_the_action"] is True


def test_something_left_too_long_is_flagged_overdue_and_never_decided_for_anybody():
    """Decision 28. Overdue changes how a row is DRAWN and nothing else. There is
    deliberately no code anywhere that decides an approval on its own."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    stale = {"id": "a4", "schoolId": SCHOOL, "status": "pending", "title": "Old",
             "submitted_by": "x",
             "submitted_at": (now - timedelta(hours=100)).isoformat()}
    fresh = {**stale, "id": "a5",
             "submitted_at": (now - timedelta(hours=2)).isoformat()}
    assert registry.to_card("general", stale, now=now)["overdue"] is True
    assert registry.to_card("general", fresh, now=now)["overdue"] is False
    # Still pending. Nothing was decided by the passage of time.
    assert registry.to_card("general", stale, now=now)["status"] == "pending"


def test_a_decided_request_is_never_drawn_as_overdue():
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    done = {"id": "a6", "schoolId": SCHOOL, "status": "approved", "title": "Done",
            "submitted_by": "x",
            "submitted_at": (now - timedelta(days=30)).isoformat()}
    assert registry.to_card("general", done, now=now)["overdue"] is False


# ── 5. The routes refuse a stranger ──────────────────────────────────────────


@pytest.mark.parametrize("method,path", [
    ("get", "/api/approvals/kinds"),
    ("get", "/api/approvals/waiting-on-me"),
    ("get", "/api/approvals/raised-by-me"),
    ("get", "/api/approvals/general/a1"),
    ("post", "/api/approvals/general/a1/decide"),
    ("post", "/api/approvals/general/a1/reply"),
    ("post", "/api/approvals/general/a1/participants"),
    ("post", "/api/approvals/general/a1/reopen"),
    ("patch", "/api/approvals/general/a1"),
])
def test_every_approvals_route_refuses_somebody_who_is_not_signed_in(client, method, path):
    assert getattr(client, method)(path).status_code == 401


def test_a_made_up_kind_of_approval_is_refused_rather_than_guessed(client):
    resp = client.get("/api/approvals/not-a-real-kind/x1", headers=_bearer(OWNER))
    assert resp.status_code == 404


def test_the_transport_head_cannot_decide_the_request_he_raised(client, fake_db):
    """He raises; Aman or Adesh decides. A screen must never turn the person asking into
    the person agreeing."""
    fake_db.approval_requests.docs.append({
        "id": "a7", "schoolId": SCHOOL, "status": "pending",
        "routing": "owner_and_principal", "title": "Delete a route",
        "description": "d", "submitted_by": TRANSPORT["id"],
        "submitted_at": "2026-08-15T09:00:00+00:00",
    })
    resp = client.post("/api/approvals/general/a7/decide",
                       json={"decision": "approve", "reason": "yes"},
                       headers=_bearer(TRANSPORT))
    assert resp.status_code == 403
    assert fake_db.approval_requests.docs[-1]["status"] == "pending"
    fake_db.approval_requests.docs.clear()


def test_refusing_something_without_saying_why_is_refused(client, fake_db):
    """Every one of the six already insisted on a reason for a refusal. This is that
    same rule asked once instead of six times."""
    fake_db.approval_requests.docs.append({
        "id": "a8", "schoolId": SCHOOL, "status": "pending",
        "routing": "owner_and_principal", "title": "T", "description": "d",
        "submitted_by": TRANSPORT["id"], "submitted_at": "2026-08-15T09:00:00+00:00",
    })
    resp = client.post("/api/approvals/general/a8/decide",
                       json={"decision": "reject", "reason": ""},
                       headers=_bearer(OWNER))
    assert resp.status_code == 400
    fake_db.approval_requests.docs.clear()


# ── 6. The two directions of "what is waiting" ───────────────────────────────


async def test_the_queue_answers_across_every_kind_at_once(fake_db):
    """Decision 30: asked "is anything waiting on me", the answer covers every kind.
    Six separate lists is the thing this replaces."""
    fake_db.approval_requests.docs.append({
        "id": "q1", "schoolId": SCHOOL, "status": "pending",
        "routing": "owner_and_principal", "title": "A request", "description": "d",
        "submitted_by": TRANSPORT["id"], "submitted_at": "2026-08-15T09:00:00+00:00"})
    fake_db.certificates.docs.append({
        "id": "q2", "schoolId": SCHOOL, "status": "pending_approval",
        "cert_type": "bonafide", "requested_by": ACCOUNTANT["id"],
        "created_at": "2026-08-15T08:00:00+00:00"})
    try:
        cards = await registry.waiting_on(fake_db, OWNER)
        assert {c["kind"] for c in cards} == {"general", "certificate"}
    finally:
        fake_db.approval_requests.docs.clear()
        fake_db.certificates.docs.clear()


async def test_the_queue_shows_a_person_only_what_they_may_decide(fake_db):
    fake_db.approval_requests.docs.append({
        "id": "q3", "schoolId": SCHOOL, "status": "pending", "routing": "owner_only",
        "title": "Owner only", "description": "d", "submitted_by": ACCOUNTANT["id"],
        "submitted_at": "2026-08-15T09:00:00+00:00"})
    try:
        assert [c["id"] for c in await registry.waiting_on(fake_db, OWNER)] == ["q3"]
        assert await registry.waiting_on(fake_db, PRINCIPAL) == []
        assert await registry.waiting_on(fake_db, TRANSPORT) == []
    finally:
        fake_db.approval_requests.docs.clear()


async def test_a_person_can_see_what_they_asked_for_even_though_they_decide_nothing(fake_db):
    """A department head raises far more than he decides. A screen that showed only
    what he can decide would be empty and would read as broken."""
    fake_db.approval_requests.docs.append({
        "id": "q4", "schoolId": SCHOOL, "status": "pending",
        "routing": "owner_and_principal", "title": "Mine", "description": "d",
        "submitted_by": TRANSPORT["id"], "submitted_at": "2026-08-15T09:00:00+00:00"})
    try:
        mine = await registry.raised_by(fake_db, TRANSPORT)
        assert [c["id"] for c in mine] == ["q4"]
        assert await registry.raised_by(fake_db, OWNER) == []
    finally:
        fake_db.approval_requests.docs.clear()
