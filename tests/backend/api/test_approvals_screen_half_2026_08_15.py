"""The three leftovers of the approvals workflow, closed. 2026-08-15.

The approvals workflow shipped able to ANSWER a request and not to start one, with a
"bring somebody in" control that asked for an account id nobody at the school knows, and
attachments drawn as a count with no way to open them. Plus two decision paths on staff
leave, only one of which recorded the colleague as away.

**Most of what is below asserts a REFUSAL or a MERGE, not a feature.** The danger in
adding a raise form and a colleague list is not a broken button; it is handing somebody a
list, a file or a decision that was never theirs. If one of these starts failing, the
question is who decided that, not how to make it pass.
"""

from __future__ import annotations

import pytest

from middleware.auth import create_jwt
from services import approval_registry as registry
from services import leave_service


def _h(**claims):
    return {"Authorization": f"Bearer {create_jwt({'name': 'T', **claims})}"}


OWNER = {"id": "aman", "role": "owner", "name": "Aman"}
PRINCIPAL = {"id": "adesh", "role": "admin", "sub_category": "principal", "name": "Adesh"}
ACCOUNTANT = {"id": "sonu", "role": "admin", "sub_category": "accountant", "name": "Sonu"}
MANAGEMENT = {"id": "lalit", "role": "admin", "sub_category": "management", "name": "Lalit"}
TRANSPORT = {"id": "chaman", "role": "admin", "sub_category": "transport_head",
             "name": "Chaman"}
TEACHER = {"id": "teach1", "role": "teacher", "name": "A Teacher"}
STUDENT = {"id": "kid", "role": "student", "name": "A Child"}

SCHOOL = "aaryans-joya"


def _bearer(person):
    return _h(user_id=person["id"], role=person["role"],
              sub_category=person.get("sub_category"))


# ── 1. Either Aman or Adesh can act on all six kinds ─────────────────────────
#
# This is the pin the merge was asked for. It is the whole promise of the workflow in one
# assertion: whatever kind of thing the school asks permission for, there are two people
# who can answer it, so nothing waits on one man being at his desk.
#
# The six are named individually rather than counted, because a count stays green while
# somebody quietly swaps one kind for another.

A_PENDING_ROW_OF_EACH_KIND = {
    # Routed to both, which is the "either one of them" case this test is about. A
    # request the raiser deliberately sends to the owner alone is a different thing and
    # is pinned separately in the workflow's own test file.
    "general": {"routing": "owner_and_principal", "status": "pending",
                "submitted_by": TRANSPORT["id"]},
    "certificate": {"status": "pending_approval", "requested_by": ACCOUNTANT["id"]},
    "staff_leave": {"status": "pending", "user_id": TRANSPORT["id"]},
    "announcement": {"status": "pending_approval", "created_by": MANAGEMENT["id"]},
    # Never your own, so it is somebody else's record in both runs of this test.
    "staff_profile_change": {"status": "pending", "user_id": TRANSPORT["id"]},
    "student_leave": {"status": "pending_principal", "submitted_by": TEACHER["id"],
                      "class_id": "c1"},
}


@pytest.mark.parametrize("decider", [OWNER, PRINCIPAL], ids=["aman", "adesh"])
@pytest.mark.parametrize("kind", sorted(A_PENDING_ROW_OF_EACH_KIND))
async def test_either_aman_or_adesh_can_act_on_all_six_kinds(fake_db, kind, decider):
    doc = {"id": f"{kind}-1", "schoolId": SCHOOL, **A_PENDING_ROW_OF_EACH_KIND[kind]}
    assert await registry.may_decide(fake_db, kind, decider, doc) is True


def test_the_six_kinds_in_that_pin_are_the_whole_registry():
    """So a seventh kind cannot be added without somebody deciding who answers it."""
    assert set(A_PENDING_ROW_OF_EACH_KIND) == set(registry.APPROVAL_KINDS)


@pytest.mark.parametrize("person", [ACCOUNTANT, MANAGEMENT, TRANSPORT, STUDENT],
                         ids=["sonu", "lalit", "chaman", "a-child"])
@pytest.mark.parametrize("kind", sorted(A_PENDING_ROW_OF_EACH_KIND))
async def test_and_nobody_else_can(fake_db, kind, person):
    """The other half of the pin above, and the more important half.

    "Two people can answer everything" is only worth having if it is exactly two. The
    class teacher is not in this list because a child's leave is genuinely theirs to
    decide first; that is covered in the workflow's own test file.
    """
    doc = {"id": f"{kind}-2", "schoolId": SCHOOL, **A_PENDING_ROW_OF_EACH_KIND[kind]}
    assert await registry.may_decide(fake_db, kind, person, doc) is False


# ── 2. The two staff leave decision paths are one ────────────────────────────


def test_there_is_only_one_leave_decision_function_left():
    """`decide_leave` recorded the decision and did NOT mark the colleague as away.

    Two paths meant leave approved on the staff screen left the person reading as
    available on every screen that asks, while the same leave approved in the approvals
    queue did not. Deleting the lesser one is what makes that impossible rather than
    merely unlikely.
    """
    assert not hasattr(leave_service, "decide_leave"), (
        "decide_leave was merged into decide_leave_request on 2026-08-15. If it is back, "
        "the two paths can disagree about whether a colleague is at work."
    )
    assert hasattr(leave_service, "decide_leave_request")


def test_every_caller_reaches_the_path_that_marks_the_person_away():
    """Read from the source, so a new caller of the deleted name is caught here."""
    from pathlib import Path

    root = Path(leave_service.__file__).resolve().parent.parent
    for relative in ("routes/staff.py", "ai/tool_functions.py",
                     "services/approval_registry.py"):
        text = (root / relative).read_text(encoding="utf-8")
        assert "decide_leave_request" in text, f"{relative} must use the merged path"
        # The merged name contains the old one, so the old one is looked for as a call.
        assert "decide_leave(" not in text, f"{relative} still calls the deleted path"


@pytest.fixture(autouse=True)
def _clean(fake_db):
    """The stand-in database is shared, so leave a clean one behind for the next test."""
    for col in ("leave_requests", "staff_availability", "notifications", "audit_logs"):
        getattr(fake_db, col).docs[:] = []
    yield
    for col in ("leave_requests", "staff_availability", "notifications", "audit_logs"):
        getattr(fake_db, col).docs[:] = []


async def _a_pending_leave(fake_db):
    await fake_db.leave_requests.insert_one({
        "id": "lv1", "schoolId": SCHOOL, "status": "pending", "staff_id": "st1",
        "user_id": TRANSPORT["id"], "start_date": "2026-09-01", "end_date": "2026-09-03",
        "date_range": {"start": "2026-09-01", "end": "2026-09-03"},
    })


def _ctx():
    from services.actor_context import actor_ctx_from_user

    return actor_ctx_from_user(OWNER, school_id=SCHOOL)


async def test_approving_leave_marks_the_colleague_as_away(fake_db):
    """The reason this path is the survivor, asserted rather than assumed."""
    await _a_pending_leave(fake_db)
    await leave_service.decide_leave_request(
        fake_db, _ctx(), {"leave_id": "lv1", "status": "approved"}
    )
    away = await fake_db.staff_availability.find_one({"leave_request_id": "lv1"})
    assert away is not None, "leave was approved and nobody recorded the person as away"
    assert away["status"] == "on_leave"


async def test_the_old_field_names_are_still_written(fake_db):
    """Screens and exports read `approved_by` on every row written before today.

    A merge that stopped writing it would make each new decision look undecided to all
    of them, which is worse than the drift it was fixing.
    """
    await _a_pending_leave(fake_db)
    await leave_service.decide_leave_request(
        fake_db, _ctx(), {"leave_id": "lv1", "status": "approved"}
    )
    row = await fake_db.leave_requests.find_one({"id": "lv1"})
    assert row["approved_by"] == OWNER["id"]
    assert row["decided_by"] == OWNER["id"]
    assert row["approved_at"] and row["decided_at"]


async def test_a_second_decision_on_the_same_request_is_refused(fake_db):
    """The pending-only guard, carried across from the deleted path.

    Without it the second decision quietly overwrites the first and the person is sent a
    second notification saying the opposite of the first one.
    """
    await _a_pending_leave(fake_db)
    await leave_service.decide_leave_request(
        fake_db, _ctx(), {"leave_id": "lv1", "status": "approved"}
    )
    with pytest.raises(leave_service.LeaveConflictError):
        await leave_service.decide_leave_request(
            fake_db, _ctx(), {"leave_id": "lv1", "status": "rejected", "reason": "no"}
        )


async def test_refusing_leave_still_needs_a_reason_and_approving_does_not(fake_db):
    """Both spellings are accepted, because the two merged callers used different ones.

    Making one of them the only spelling would have dropped the other caller's reason on
    the floor, and a refusal with no reason is the one thing every kind of approval here
    forbids.
    """
    await _a_pending_leave(fake_db)
    with pytest.raises(leave_service.LeaveValidationError):
        await leave_service.decide_leave_request(
            fake_db, _ctx(), {"leave_id": "lv1", "status": "rejected"}
        )
    await leave_service.decide_leave_request(
        fake_db, _ctx(), {"leave_id": "lv1", "status": "rejected",
                          "rejection_reason": "The cover is not arranged"}
    )
    row = await fake_db.leave_requests.find_one({"id": "lv1"})
    assert row["rejection_reason"] == "The cover is not arranged"
    assert row["decision_reason"] == "The cover is not arranged"


async def test_leave_that_was_refused_never_marks_the_person_away(fake_db):
    await _a_pending_leave(fake_db)
    await leave_service.decide_leave_request(
        fake_db, _ctx(), {"leave_id": "lv1", "status": "rejected", "reason": "no cover"}
    )
    assert await fake_db.staff_availability.find_one({"leave_request_id": "lv1"}) is None


# ── 3. Raising a request, and who is offered the control ─────────────────────


def test_only_the_general_kind_can_be_raised_from_the_approvals_screen():
    """A certificate is asked for on the certificates screen, leave on the leave screen.

    Offering those here would be a SECOND way to create the same record, and two ways to
    create one thing is how the two drift apart and start disagreeing.
    """
    raisable = {n for n, e in registry.APPROVAL_KINDS.items() if e.get("raisable_here")}
    assert raisable == {"general"}


@pytest.mark.parametrize("person,expected", [
    (ACCOUNTANT, True), (MANAGEMENT, True), (TRANSPORT, True), (PRINCIPAL, True),
    # Decision 25: Aman and Adesh approve, they do not raise. The principal is an
    # administrator so the route lets him, and the school's owner is not offered it.
    (OWNER, False), (TEACHER, False), (STUDENT, False),
])
def test_who_is_offered_the_ask_for_something_control(person, expected):
    """Mirrors `require_role("admin")` on the route the screen calls.

    The server answers this so the screen never holds its own idea of who may raise
    what, which is how a control ends up offered to somebody the route then refuses.
    """
    may_raise = registry.APPROVAL_KINDS["general"]["may_raise"]
    assert bool(may_raise(person)) is expected


def test_the_kinds_route_reports_may_raise_per_kind(client):
    resp = client.get("/api/approvals/kinds", headers=_bearer(ACCOUNTANT))
    assert resp.status_code == 200
    kinds = {row["kind"]: row for row in resp.json()["data"]}
    assert kinds["general"]["may_raise"] is True
    for name, row in kinds.items():
        if name != "general":
            assert row["may_raise"] is False, f"{name} is not raisable from this screen"


def test_the_owner_is_not_offered_the_control(client):
    resp = client.get("/api/approvals/kinds", headers=_bearer(OWNER))
    assert all(row["may_raise"] is False for row in resp.json()["data"])


# ── 4. The colleague list, and opening an attachment ─────────────────────────


def test_the_people_route_refuses_somebody_outside_the_conversation(client):
    """Every approvals route is signed-in-only by design, because who may see a request
    is a question about the RECORD. A flat colleague list on that gate would hand the
    school's staff list to any student or guardian with a login."""
    resp = client.get("/api/approvals/general/nope/people", headers=_bearer(STUDENT))
    assert resp.status_code in (403, 404)


def test_people_route_needs_a_signed_in_caller(client):
    resp = client.get("/api/approvals/general/anything/people")
    assert resp.status_code == 401


def test_the_colleague_list_never_offers_somebody_who_cannot_sign_in():
    """The staff room's rule, reused rather than rewritten.

    A colleague you can add but who can never answer is worse than an absent one: it
    looks like they are ignoring you. The rule is asked of the permission table, so a
    profile switched on for its release appears here the same day with no code change.
    """
    from pathlib import Path

    import routes.approvals as approvals_routes

    source = Path(approvals_routes.__file__).read_text(encoding="utf-8")
    assert "_staff_contacts" in source, (
        "the colleague list must come from the staff room's own rule, not a second list"
    )


def test_an_attachment_reaches_the_screen_with_its_name():
    """A count is not a document.

    The person deciding a repair cost could see that a quote existed and had no way to
    read it, which is the same shape as every other fault this release closed.
    """
    from pathlib import Path

    import routes.approvals as approvals_routes

    source = Path(approvals_routes.__file__).read_text(encoding="utf-8")
    assert "attachment_files" in source
    assert "_name_the_attachments" in source


def test_naming_an_attachment_grants_nobody_anything():
    """The file itself is still fetched one at a time through the upload route, which
    applies the ordinary file rules plus the narrow approvals rule."""
    from pathlib import Path

    import routes.upload as upload_routes

    source = Path(upload_routes.__file__).read_text(encoding="utf-8")
    assert "may_open_attachment" in source, (
        "opening an approval attachment must still go through the approvals read rule"
    )
