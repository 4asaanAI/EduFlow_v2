"""R4-4 - the things that hurt the platform, and what Flo says about the rest.

--------------------------------------------------------------------------------
Decision 4, and what it actually means
--------------------------------------------------------------------------------

Abhimanyu, 2026-08-12: **undo only the things that hurt the platform. For everything
else Flo talks the person through undoing it by hand.**

That is two pieces of work, and the second is the larger one. A platform that can reverse
five kinds of change and says "ask the principal" to everything else has solved a fifth of
the problem. The guidance below is the other four fifths.

--------------------------------------------------------------------------------
"Hurts" is about the KIND of change. It is not permission to make it.
--------------------------------------------------------------------------------

There is a trap here worth naming, because falling into it would quietly undo Release 2.

A fee entry hurts when it is wrong, so a fee entry should be undoable. But Lalit, the
management head, may not touch money at all (decision 1, 2026-08-10) - he cannot even see
an amount. If "this kind of change is undoable" were the whole test, undo would become a
back door into fees for a person the permission table deliberately keeps out, and it would
look like a feature rather than a hole.

So eligibility is **both** tests, always:

    1. Is this the kind of change that hurts the platform when it is wrong?
    2. May THIS person make that kind of change in the first place?

The second question is answered by the same permission table the menus and the server
already use. Undo asks it; it never restates it. Grouping never grants, and neither does
undoing.

--------------------------------------------------------------------------------
Guidance is not a consolation prize
--------------------------------------------------------------------------------

When something cannot be reversed automatically, the recorded change usually still knows
what the value was before. That is enough to tell a person exactly what to type and where.
"Ask the principal" throws that away and makes a person who is trying to fix their own
mistake go and interrupt somebody else.

`guidance()` returns steps only when it can be specific. Where the earlier value was never
recorded it says so plainly rather than inventing a step, because a confident instruction
built on a value nobody wrote down is worse than an honest refusal.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from services import audit_changes
from services.profile_matrix import granted_domains, profile_of

FINANCE = "finance"
NON_FINANCE = "non_finance"
LEADERSHIP = "leadership"

#: The kinds of change that hurt the platform when they are wrong, and who may reverse
#: one. `domain` is checked against the SAME permission table the menus and the server
#: read, so this table can never widen anybody's reach.
#:
#: Each entry says why it is here. "It seemed important" is not a reason; the test is
#: whether getting it wrong causes real harm that a person cannot easily see and fix.
HURTS: Dict[str, Dict[str, Any]] = {
    "fee_transactions": {
        "domain": FINANCE,
        "label": "a fee entry",
        "why": "A wrong fee entry sends a family a demand they do not owe, or marks a "
               "bill paid that was never paid. Both reach a parent before anybody at "
               "the school notices.",
    },
    "salary_disbursements": {
        "domain": FINANCE,
        "label": "a salary payment",
        "why": "Somebody is paid the wrong amount, and pay is the one record a member "
               "of staff checks personally and immediately.",
    },
    "salary_structures": {
        "domain": FINANCE,
        "label": "a salary structure",
        "why": "It sets every future payment, so one wrong figure repeats every month "
               "until somebody spots it.",
    },
    "attendance": {
        "domain": NON_FINANCE,
        "label": "a day's attendance",
        "why": "A child marked absent who was present follows them through the term, "
               "into reports, and into conversations with their family.",
    },
    "exam_results": {
        "domain": NON_FINANCE,
        "label": "marks",
        "why": "Marks go onto report cards and out of the building. A wrong mark is "
               "seen by the child and their parents before it is seen by the school.",
    },
    "students": {
        "domain": NON_FINANCE,
        "label": "a child's record",
        "why": "The roll is what every other part of the platform reads. A wrong class "
               "or admission number breaks attendance, fees and reports at once.",
    },
    "staff": {
        "domain": NON_FINANCE,
        "label": "a colleague's record",
        "why": "Staff records decide timetables, leave and pay, so an error spreads "
               "into all three before anybody looks at the record itself.",
    },
}


def hurts(collection: str) -> bool:
    """Is this the kind of change the platform will reverse for somebody?"""
    return str(collection or "").strip().lower() in HURTS


def entry_collection(entry: dict) -> str:
    """The collection an audit row is about, however the row spells it."""
    for key in ("collection", "entity_type"):
        name = str((entry or {}).get(key) or "").strip().lower()
        if name in HURTS:
            return name
    return ""


def may_reverse(user: dict, collection: str) -> bool:
    """May THIS person reverse this kind of change?

    Asks the permission table rather than restating it. A profile that may not see fees
    may not undo a fee entry, whatever the audit row says, because an undo that ignored
    the table would be a way around it rather than a feature.
    """
    key = str(collection or "").strip().lower()
    rule = HURTS.get(key)
    if not rule:
        return False
    if not profile_of(user):
        return False
    return rule["domain"] in granted_domains(user)


def refusal_reason(user: dict, entry: dict) -> str:
    """Why this change is not eligible for automatic undo. "" means it is."""
    collection = entry_collection(entry)
    if not collection:
        named = (entry or {}).get("collection") or (entry or {}).get("entity_type") or "this"
        return (
            f"Putting back a change to {named} is not something the platform does "
            "automatically, because getting it wrong there is easy to see and easy to "
            "correct by hand."
        )
    if not may_reverse(user, collection):
        return (
            f"Putting back {HURTS[collection]['label']} is not something your profile "
            "can do. Ask whoever normally makes that kind of change."
        )
    return ""


# ---------------------------------------------------------------------------
# The larger half: telling a person exactly how to put it back themselves
# ---------------------------------------------------------------------------

def guidance(entry: dict) -> Dict[str, Any]:
    """Plain steps for undoing a change by hand, from what was actually recorded.

    Returns `{"can_guide": bool, "reason": str, "steps": [...]}`.

    `can_guide` is False whenever the recorded change does not carry enough to be
    specific. That is deliberate: a confident-sounding instruction built on a value
    nobody wrote down would send somebody to overwrite a good value with a blank, and
    they would trust it because it came from the platform.
    """
    canonical = audit_changes.normalise((entry or {}).get("changes"))
    kind = canonical.get("kind")
    what = HURTS.get(entry_collection(entry), {}).get("label") or "this record"

    if kind == audit_changes.KIND_CREATE:
        return {
            "can_guide": True,
            "reason": "",
            "steps": [
                f"This change ADDED {what}, so putting it back means removing it again.",
                "Open the record and check nothing else has been added to it since. "
                "Anything added afterwards would go too.",
                "Removing a record is the owner's and the principal's decision, so ask "
                "one of them rather than doing it yourself.",
            ],
        }

    if kind == audit_changes.KIND_DELETE:
        snapshot = canonical.get("snapshot") or {}
        named = ", ".join(sorted(k for k in snapshot if k not in {"id", "schoolId"})[:8])
        return {
            "can_guide": True,
            "reason": "",
            "steps": [
                f"This change REMOVED {what}. A copy of it was kept, so it can be typed "
                "back in full.",
                f"The record held: {named}." if named else "A copy of the record was kept.",
                "Create the record again with those values, then check anything that "
                "pointed at it, such as fees or attendance, still lines up.",
            ],
        }

    if kind == audit_changes.KIND_BULK:
        affected = canonical.get("affected")
        count = f"{affected} records" if isinstance(affected, int) else "many records"
        return {
            "can_guide": False,
            "reason": (
                f"This change touched {count} at once, and the platform did not keep "
                "what each one held beforehand. There is nothing to guide you back to."
            ),
            "steps": [],
        }

    if kind != audit_changes.KIND_EDIT:
        return {
            "can_guide": False,
            "reason": canonical.get("why") or "Nothing was recorded about this change.",
            "steps": [],
        }

    fields = canonical.get("fields") or {}
    known = {n: f for n, f in fields.items() if f.get("previous_known")}
    unknown = sorted(n for n, f in fields.items() if not f.get("previous_known"))

    if not known:
        return {
            "can_guide": False,
            "reason": (
                "The platform recorded what these values became but not what they were "
                f"before ({', '.join(unknown)}), so there is nothing to put back. "
                "Whoever made the change is the only person who knows the old value."
            ),
            "steps": [],
        }

    steps: List[str] = [f"Open {what} and edit it."]
    for name, field in sorted(known.items()):
        previous = field.get("previous")
        shown = "empty" if previous in (None, "") else f'"{previous}"'
        steps.append(f"Set {name} back to {shown}. It is currently \"{field.get('new')}\".")
    steps.append("Save. Your correction is recorded too, beside the original change.")

    if unknown:
        # Said out loud. A list of confident steps that silently omits two fields reads
        # as "that is everything", and the person walks away with the job half done.
        steps.append(
            "One thing this cannot help with: the earlier value was never recorded for "
            + ", ".join(unknown)
            + ". Those have to come from whoever made the change."
        )

    return {"can_guide": True, "reason": "", "steps": steps}
