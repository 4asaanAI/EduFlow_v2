"""Whether a person is on the school's roll, and whether they are on the register.

Owner request 10, 2026-08-06. Aman described what the school actually does, and the
platform had no word for the middle of it:

    "There are students who stop reporting to the school without any contact — they get
    transferred to another region and do not come to take the TC. The school puts those
    students into a list called NSO. Their names STILL APPEAR in everyday attendance.
    After the TC, the name is removed from attendance."

So there are three states before a record is destroyed, not two:

    ACTIVE      on the roll, on the register.
    NSO         off the roll, STILL ON THE REGISTER. Stopped attending, no TC issued.
                A teacher keeps marking them absent every day, which is exactly how the
                school notices when one of them walks back in.
    TC_ISSUED   off the roll, off the register. The leaving certificate is out; they are
                finished with the school but their record is kept.

and then permanent erasure, which is a different thing entirely and lives in the erase
route: it destroys the record and demands a written reason.

WHY BOTH `is_active` AND `status` ARE WRITTEN TOGETHER. `is_active` was already the
field every count, dropdown and report filters on, and `status` was already a loose
label ("withdrawn"). Before this, `set_student_status` wrote `status` alone — so
setting a student back to "active" left `is_active` False and the student stayed
invisible. That is the bug behind owner request 9: a student marked inactive during a
demo could not be brought back by any endpoint or any AI tool, because nothing in the
product could write `is_active` at all. One writer, both fields, no drift.

LEGACY ROWS. Records deactivated before this existed carry `status: "withdrawn"` with
no NSO concept. They are read as TC_ISSUED — off the register — which is exactly how
they behaved yesterday, so nothing about the school's existing data changes meaning.
Restoring one sets it cleanly to ACTIVE.
"""

from __future__ import annotations

ACTIVE = "active"
NSO = "nso"
TC_ISSUED = "tc_issued"

# What `status` held before this module existed. Read as TC_ISSUED, never written.
LEGACY_WITHDRAWN = "withdrawn"

#: The states a caller may ask for. Erasure is deliberately NOT here — it destroys the
#: record rather than moving it, and it has its own owner-only route.
SETTABLE_STATES = (ACTIVE, NSO, TC_ISSUED)

#: Human wording, for confirmations and audit rows that people read.
STATE_LABELS = {
    ACTIVE: "on the roll",
    NSO: "NSO — not attending, still on the daily register",
    TC_ISSUED: "TC issued — left the school",
}


def is_on_roll(state: str) -> bool:
    """Counted in "how many students does the school have"."""
    return state == ACTIVE


def normalise(doc: dict | None) -> str:
    """Read the enrolment state off a stored student or staff record.

    Tolerant on purpose: this reads rows written by three different versions of the
    product. `is_active` wins when it says the person is on the roll, because that is
    the field everything else has always filtered on.
    """
    doc = doc or {}
    status = str(doc.get("status") or "").strip().lower()
    if status in SETTABLE_STATES:
        return status
    if doc.get("is_active"):
        return ACTIVE
    # Anything else that is switched off — including the legacy "withdrawn" — is a
    # record that has left the register.
    if doc.get("is_active") is False:
        return TC_ISSUED
    return ACTIVE


def fields_for(state: str) -> dict:
    """The exact fields to write for a state. The ONLY place these pair up."""
    if state not in SETTABLE_STATES:
        raise ValueError(f"unknown enrolment state: {state!r}")
    return {"is_active": state == ACTIVE, "status": state}


def on_register_filter() -> dict:
    """Mongo filter for "should be in today's attendance register".

    ACTIVE **and NSO**. This is the whole point of NSO and the reason it could not be
    expressed by `is_active` alone: an NSO student is off the roll but must still be
    marked every day.

    Use this instead of `{"is_active": True}` anywhere a register, a mark-attendance
    screen or a class list is being built. Do NOT use it for headcounts — a school with
    three NSO students has 1,801 students and 1,804 names to mark.
    """
    return {"$or": [{"is_active": True}, {"status": NSO}]}


def in_recycle_bin_filter() -> dict:
    """Mongo filter for the restore-or-delete list: everything off the roll.

    Covers NSO, TC issued, and legacy `withdrawn` rows, which is what makes the student
    deactivated during the 2026-08-05 demo findable and restorable.
    """
    return {"is_active": {"$ne": True}}


# ---------------------------------------------------------------------------
# What a screen may ask a list endpoint for
# ---------------------------------------------------------------------------
#
# Owner request 10, 2026-08-06. The recycle bin, the NSO list and the TC-issued
# list are three views of the same collection, and the staff and teacher versions
# want exactly the same five choices. Keeping the wording and the filters here is
# what stops `routes/students.py` and `routes/staff.py` drifting apart.

ON_ROLL_VIEW = "active"
NSO_VIEW = NSO
TC_ISSUED_VIEW = TC_ISSUED
#: Everything off the roll: NSO, TC issued and legacy withdrawn rows. The recycle bin.
OFF_ROLL_VIEW = "off_roll"
#: On the roll plus NSO. What a daily register or a marking screen should ask for.
ON_REGISTER_VIEW = "on_register"
#: No filter at all.
ALL_VIEW = "all"

LIST_VIEWS = (
    ON_ROLL_VIEW,
    NSO_VIEW,
    TC_ISSUED_VIEW,
    OFF_ROLL_VIEW,
    ON_REGISTER_VIEW,
    ALL_VIEW,
)


def view_filter(view: str) -> dict:
    """Mongo filter for one of `LIST_VIEWS`. Raises ValueError on anything else.

    TC_ISSUED deliberately catches legacy `withdrawn` rows as well: a record
    switched off before this existed behaves exactly as a TC-issued one, and the
    school should not have to know which version of the product retired it.
    """
    if view == ON_ROLL_VIEW:
        return {"is_active": True}
    if view == NSO_VIEW:
        return {"status": NSO}
    if view == TC_ISSUED_VIEW:
        return {"is_active": {"$ne": True}, "status": {"$ne": NSO}}
    if view == OFF_ROLL_VIEW:
        return in_recycle_bin_filter()
    if view == ON_REGISTER_VIEW:
        return on_register_filter()
    if view == ALL_VIEW:
        return {}
    raise ValueError(f"unknown list view: {view!r}")
