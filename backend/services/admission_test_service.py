"""B1: an entrance test is a record, not a word.

WHY THIS EXISTS
---------------
Before this, `assessment_scheduled` was a status on an application and nothing else. No
date, no place, no list of who was sitting it. The only test data the platform held was
the score, entered afterwards, one child at a time. **The school could not pull a list for
Sunday**, so the list lived on paper or in somebody's head, and the platform's word
"scheduled" described something it knew nothing about.

TWO RULES THIS MODULE EXISTS TO HOLD
------------------------------------
1. **"Nobody has marked this yet" is not "absent".** Attendance starts as `None` and stays
   there until a person says otherwise. If it defaulted to absent, a test where nobody had
   got round to marking the register would be indistinguishable from a test where no child
   turned up, and the second is a reason to call twelve families. Every list returns how
   many are still unmarked, for the same reason A5's worklist returns how many families
   have no follow-up date.

2. **The seat and the application can never disagree about a mark.** A score is not stored
   on the seat and then copied to the application later. It goes through
   `admissions_service.record_assessment`, the same function the application screen has
   always used, in the same call. If that refuses, the whole thing is refused and NOTHING
   is written, so a mark can never exist on a test list while the application shows none.
   There is one assessment per application and this does not become a second one.

A CORRECTNESS WIN THAT CAME FREE
--------------------------------
The paper's total lives on the TEST, not on each entry. `record_assessment` takes a
`maximum` per call, so before this two children sitting the same paper could be recorded
out of different totals and their percentages would disagree with nobody noticing. Here
they cannot: everyone on one test is marked out of one number, and that number is frozen
the moment the first mark is recorded.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from services.actor_context import ActorContext
from services.admissions_service import (
    AdmissionConflictError,
    AdmissionNotFoundError,
    AdmissionValidationError,
    record_assessment,
)
from services.audit_service import write_audit_doc
from services.txn_context import session_kwargs
from tenant import scoped_query


#: A test that has been called off. Nothing may be added to it and no mark may be taken.
TEST_STATUSES = ("planned", "held", "cancelled")

#: An application in one of these is finished with, so it cannot be given a seat.
#: Scheduling a test for a withdrawn applicant is a list that wastes somebody's Sunday.
APPLICATION_TERMINAL = {"enrolled", "rejected", "withdrawn"}

#: What a person may say about whether somebody turned up. `None` is the third state and
#: it is the important one: it means nobody has said yet.
ATTENDANCE = ("present", "absent")


def _now() -> str:
    return datetime.now().isoformat()


def _public(doc: dict) -> dict:
    return {key: value for key, value in doc.items() if key != "_id"}


def _text(params: dict, key: str, *, required: bool = False) -> Optional[str]:
    value = str(params.get(key) or "").strip()
    if not value:
        if required:
            raise AdmissionValidationError(f"{key} is required")
        return None
    return value


def _a_date(value, key: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise AdmissionValidationError(f"{key} is required")
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        raise AdmissionValidationError(f"{key} must be a date in YYYY-MM-DD form")


def _a_time(value) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:5], "%H:%M").strftime("%H:%M")
    except ValueError:
        raise AdmissionValidationError("start_time must be a time in HH:MM form")


def _maximum(value) -> float:
    try:
        maximum = float(value)
    except (TypeError, ValueError):
        raise AdmissionValidationError("maximum_marks must be a number")
    if maximum <= 0:
        raise AdmissionValidationError("maximum_marks must be more than zero")
    return maximum


async def _audit(db, actor: ActorContext, action: str, entity_id: str, changes: dict,
                 *, entity_type: str = "admission_test", session=None) -> None:
    audit_id = str(uuid.uuid4())
    await write_audit_doc(db, {
        "_id": audit_id, "id": audit_id,
        "schoolId": actor.school_id, "branch_id": actor.branch_id,
        "entity_type": entity_type, "entity_id": entity_id, "action": action,
        "changed_by": actor.user_id, "changed_by_role": actor.role,
        "changes": changes, "created_at": actor.now().isoformat(),
    }, school_id=actor.school_id, branch_id=actor.branch_id)


async def _get_test(db, actor: ActorContext, test_id: str, *, session=None) -> dict:
    row = await db.admission_tests.find_one(
        scoped_query({"id": test_id}, branch_id=actor.branch_id), {"_id": 0},
        **session_kwargs(session),
    )
    if not row:
        raise AdmissionNotFoundError("Entrance test not found")
    return row


def _assert_open(test: dict) -> None:
    if test.get("status") == "cancelled":
        raise AdmissionConflictError(
            "This entrance test was cancelled. Nothing can be added to it and no marks can "
            "be taken on it."
        )


# ───────────────────────────── the test itself ─────────────────────────────

async def create_test(db, actor: ActorContext, params: dict, *, session=None) -> dict:
    test_id = str(uuid.uuid4())
    doc = {
        "_id": test_id, "id": test_id,
        "schoolId": actor.school_id, "branch_id": actor.branch_id,
        "title": _text(params, "title", required=True),
        "scheduled_for": _a_date(params.get("scheduled_for"), "scheduled_for"),
        "start_time": _a_time(params.get("start_time")),
        # Required, deliberately. A list of children with a date and no place on it is not
        # something the office can hand to a parent, and half a summons reads as a whole one.
        "place": _text(params, "place", required=True),
        "class_applying": _text(params, "class_applying"),
        "maximum_marks": _maximum(params.get("maximum_marks")),
        "notes": _text(params, "notes"),
        "status": "planned",
        "created_by": actor.user_id, "created_at": _now(), "updated_at": _now(),
    }
    await db.admission_tests.insert_one(doc, **session_kwargs(session))
    await _audit(db, actor, "admission_test_created", test_id, {"created": _public(doc)})
    return _public(doc)


async def update_test(db, actor: ActorContext, test_id: str, params: dict,
                      *, session=None) -> dict:
    test = await _get_test(db, actor, test_id, session=session)
    update: dict = {}
    if "title" in params:
        update["title"] = _text(params, "title", required=True)
    if "scheduled_for" in params:
        update["scheduled_for"] = _a_date(params.get("scheduled_for"), "scheduled_for")
    if "start_time" in params:
        update["start_time"] = _a_time(params.get("start_time"))
    if "place" in params:
        update["place"] = _text(params, "place", required=True)
    if "class_applying" in params:
        update["class_applying"] = _text(params, "class_applying")
    if "notes" in params:
        update["notes"] = _text(params, "notes")

    marked = await db.admission_test_seats.count_documents(scoped_query(
        {"test_id": test_id, "score": {"$ne": None}}, branch_id=actor.branch_id,
    ))

    if "maximum_marks" in params:
        maximum = _maximum(params.get("maximum_marks"))
        # Changing the total after marks exist silently rewrites every percentage already
        # recorded against every application. The marks are out of the old number and
        # nothing on screen would say so.
        if marked and maximum != test.get("maximum_marks"):
            raise AdmissionConflictError(
                f"{marked} applicant(s) have already been marked out of "
                f"{test.get('maximum_marks'):g}. Changing the total now would quietly change "
                f"every percentage already recorded. Correct the marks, or hold a new test."
            )
        update["maximum_marks"] = maximum

    if "status" in params:
        status = _text(params, "status", required=True)
        if status not in TEST_STATUSES:
            raise AdmissionValidationError(
                f"status must be one of: {', '.join(TEST_STATUSES)}"
            )
        # Cancelling after marks are in would call off a test that has already fed real
        # assessments onto real applications. Those marks do not disappear because a
        # status changed, so the record must not claim the test never happened.
        if status == "cancelled" and marked:
            raise AdmissionConflictError(
                f"This test cannot be cancelled: {marked} applicant(s) have been marked and "
                f"those marks are already on their applications."
            )
        update["status"] = status

    if not update:
        return test
    update["updated_at"] = _now()
    await db.admission_tests.update_one(
        scoped_query({"id": test_id}, branch_id=actor.branch_id), {"$set": update},
        **session_kwargs(session),
    )
    await _audit(db, actor, "admission_test_updated", test_id, update)
    return {**test, **update}


# ───────────────────────────── who is sitting it ─────────────────────────────

async def seat_applicants(db, actor: ActorContext, test_id: str, params: dict,
                          *, session=None) -> dict:
    """Put one or more applicants on a test. Reports every refusal by name."""
    test = await _get_test(db, actor, test_id, session=session)
    _assert_open(test)
    ids = params.get("application_ids")
    if isinstance(ids, str):
        ids = [ids]
    ids = [str(one).strip() for one in (ids or []) if str(one or "").strip()]
    if not ids:
        raise AdmissionValidationError("application_ids is required")

    applications = {row["id"]: row for row in await db.admission_applications.find(
        scoped_query({"id": {"$in": ids}}, branch_id=actor.branch_id),
        {"_id": 0, "id": 1, "applicant_name": 1, "status": 1}, **session_kwargs(session),
    ).to_list(len(ids))}
    already = {row["application_id"] for row in await db.admission_test_seats.find(
        scoped_query({"test_id": test_id}, branch_id=actor.branch_id),
        {"_id": 0, "application_id": 1}, **session_kwargs(session),
    ).to_list(len(ids) + 500)}

    seated, refused = [], []
    for application_id in ids:
        application = applications.get(application_id)
        if not application:
            refused.append({"application_id": application_id,
                            "reason": "No such application for this school."})
            continue
        name = application.get("applicant_name")
        if application_id in already:
            refused.append({"application_id": application_id, "applicant_name": name,
                            "reason": "Already on this test."})
            continue
        if application.get("status") in APPLICATION_TERMINAL:
            refused.append({"application_id": application_id, "applicant_name": name,
                            "reason": f"This application is {application.get('status')}."})
            continue
        seat_id = str(uuid.uuid4())
        doc = {
            "_id": seat_id, "id": seat_id,
            "schoolId": actor.school_id, "branch_id": actor.branch_id,
            "test_id": test_id, "application_id": application_id,
            # The name is NOT copied here on purpose. It is read from the application when
            # the list is drawn, so a corrected spelling shows up rather than the list
            # keeping the old one forever.
            "attendance": None, "score": None,
            "attendance_marked_by": None, "attendance_marked_at": None,
            "scored_by": None, "scored_at": None,
            "created_by": actor.user_id, "created_at": _now(),
        }
        await db.admission_test_seats.insert_one(doc, **session_kwargs(session))
        seated.append({**_public(doc), "applicant_name": name})
        already.add(application_id)

    if seated:
        await _audit(db, actor, "admission_test_seats_added", test_id,
                     {"seated": [row["application_id"] for row in seated]})
    # Both halves are always returned. A partly refused request that reported only its
    # successes would read as a complete one, which is the fault this whole initiative
    # exists to remove.
    return {"test": test, "seated": seated, "refused": refused,
            "counts": {"seated": len(seated), "refused": len(refused), "asked_for": len(ids)}}


async def remove_seat(db, actor: ActorContext, test_id: str, seat_id: str,
                      *, session=None) -> dict:
    seat = await db.admission_test_seats.find_one(
        scoped_query({"id": seat_id, "test_id": test_id}, branch_id=actor.branch_id),
        {"_id": 0}, **session_kwargs(session),
    )
    if not seat:
        raise AdmissionNotFoundError("That applicant is not on this test")
    if seat.get("score") is not None:
        # The mark is already on their application. Removing the seat would leave a mark
        # with nothing explaining where it came from.
        raise AdmissionConflictError(
            "This applicant has already been marked, and the mark is on their application. "
            "Correct the mark instead of removing them from the list."
        )
    await db.admission_test_seats.delete_one(
        scoped_query({"id": seat_id, "test_id": test_id}, branch_id=actor.branch_id),
        **session_kwargs(session),
    )
    await _audit(db, actor, "admission_test_seat_removed", test_id, {"removed": seat})
    return {"removed": seat}


async def mark_seat(db, actor: ActorContext, test_id: str, seat_id: str, params: dict,
                    *, session=None) -> dict:
    """Record whether somebody turned up, and what they scored.

    The score goes through `record_assessment`, which is the SAME function the application
    screen calls. If that refuses, this refuses and writes nothing.
    """
    test = await _get_test(db, actor, test_id, session=session)
    _assert_open(test)
    seat = await db.admission_test_seats.find_one(
        scoped_query({"id": seat_id, "test_id": test_id}, branch_id=actor.branch_id),
        {"_id": 0}, **session_kwargs(session),
    )
    if not seat:
        raise AdmissionNotFoundError("That applicant is not on this test")

    update: dict = {}
    attendance = seat.get("attendance")
    if "attendance" in params:
        value = params.get("attendance")
        if value is not None:
            attendance = str(value).strip().lower()
            if attendance not in ATTENDANCE:
                raise AdmissionValidationError(
                    f"attendance must be one of: {', '.join(ATTENDANCE)}"
                )
            update["attendance"] = attendance
            update["attendance_marked_by"] = actor.user_id
            update["attendance_marked_at"] = _now()

    if "score" in params and params.get("score") is not None:
        # A mark for somebody nobody said turned up is a mark from an empty chair.
        if attendance != "present":
            raise AdmissionValidationError(
                "Mark this applicant present before entering a score. A score for somebody "
                "recorded absent, or for somebody nobody has marked either way, is a mark "
                "with nothing behind it."
            )
        try:
            score = float(params.get("score"))
        except (TypeError, ValueError):
            raise AdmissionValidationError("score must be a number")
        maximum = float(test.get("maximum_marks") or 0)
        if score < 0 or score > maximum:
            raise AdmissionValidationError(
                f"score must be between 0 and {maximum:g}, the total for this test"
            )
        # ONE assessment per application, written by the one function that has always
        # written it. Everyone on this test is marked out of the test's own total, so two
        # children sitting the same paper cannot end up with percentages that disagree.
        # If the application is at a stage that cannot take an assessment, this raises and
        # nothing at all is stored, including the attendance above.
        await record_assessment(db, actor, seat["application_id"], {
            "score": score, "maximum": maximum,
            "assessed_on": test.get("scheduled_for"),
            "notes": f"Entrance test: {test.get('title')}",
        })
        update["score"] = score
        update["scored_by"] = actor.user_id
        update["scored_at"] = _now()

    if not update:
        return {"seat": seat, "changed": False}
    await db.admission_test_seats.update_one(
        scoped_query({"id": seat_id, "test_id": test_id}, branch_id=actor.branch_id),
        {"$set": update}, **session_kwargs(session),
    )
    await _audit(db, actor, "admission_test_seat_marked", seat_id,
                 {"test_id": test_id, **update}, entity_type="admission_test_seat")
    return {"seat": {**seat, **update}, "changed": True}


# ───────────────────────────── reading it back ─────────────────────────────

def _counts(seats: list) -> dict:
    present = [row for row in seats if row.get("attendance") == "present"]
    return {
        "seated": len(seats),
        "present": len(present),
        "absent": len([row for row in seats if row.get("attendance") == "absent"]),
        # The one that matters. Without it, a register nobody has filled in looks
        # exactly like a test nobody came to.
        "not_yet_marked": len([row for row in seats if row.get("attendance") is None]),
        "scored": len([row for row in seats if row.get("score") is not None]),
        "present_but_not_yet_scored": len([row for row in present if row.get("score") is None]),
    }


async def list_tests(db, actor: ActorContext, params: dict | None = None) -> dict:
    params = params or {}
    query: dict = {}
    if params.get("status"):
        query["status"] = str(params["status"]).strip().lower()
    tests = await db.admission_tests.find(
        scoped_query(query, branch_id=actor.branch_id), {"_id": 0},
    ).sort("scheduled_for", -1).to_list(500)
    seats = await db.admission_test_seats.find(
        scoped_query({"test_id": {"$in": [row["id"] for row in tests]}} if tests else {"test_id": "-"},
                     branch_id=actor.branch_id),
        {"_id": 0},
    ).to_list(20000) if tests else []
    by_test: dict = {}
    for seat in seats:
        by_test.setdefault(seat.get("test_id"), []).append(seat)
    for test in tests:
        test["counts"] = _counts(by_test.get(test["id"], []))
    return {"tests": tests, "count": len(tests)}


async def get_test(db, actor: ActorContext, test_id: str) -> dict:
    test = await _get_test(db, actor, test_id)
    seats = await db.admission_test_seats.find(
        scoped_query({"test_id": test_id}, branch_id=actor.branch_id), {"_id": 0},
    ).sort("created_at", 1).to_list(5000)
    # One batched lookup for the names, never one query per applicant.
    applications = {}
    if seats:
        rows = await db.admission_applications.find(
            scoped_query({"id": {"$in": [row["application_id"] for row in seats]}},
                         branch_id=actor.branch_id),
            {"_id": 0, "id": 1, "applicant_name": 1, "status": 1, "class_applying": 1,
             "guardian_name": 1, "guardian_phone": 1},
        ).to_list(len(seats))
        applications = {row["id"]: row for row in rows}
    for seat in seats:
        application = applications.get(seat.get("application_id")) or {}
        seat["applicant_name"] = application.get("applicant_name")
        seat["application_status"] = application.get("status")
        seat["class_applying"] = application.get("class_applying")
        seat["guardian_name"] = application.get("guardian_name")
        seat["guardian_phone"] = application.get("guardian_phone")
        # An applicant whose application has since gone is still shown, marked, rather
        # than vanishing from a list somebody printed on Friday.
        seat["application_found"] = bool(application)
    seats.sort(key=lambda row: str(row.get("applicant_name") or "~"))
    return {"test": test, "seats": seats, "counts": _counts(seats)}
