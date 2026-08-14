"""A3: the admissions journey, said once.

The platform describes one journey in two vocabularies. The enquiry half counts through
`new, contacted, visit_scheduled, visited, documents_submitted, fee_paid, enrolled, lost`.
The application half counts through `draft, submitted, under_review, assessment_scheduled,
assessed, offered, accepted, enrolled, rejected, withdrawn`. They overlap, they disagree
about wording, and a family part way through has a position in each. Somebody reading two
different words for the same moment cannot tell whether they are looking at one family
twice or at two things that have both happened.

So this module publishes ONE ordered list of steps, and says which stage on either side
means which step. Both halves read it, and the screen shows a family's position once.

It is the source of truth. `frontend/src/lib/admissionsJourney.generated.js` is a
generated mirror of it, checked in so the frontend build never has to run Python.
`tests/backend/unit/test_admissions_journey_drift.py` fails if the mirror goes stale.
Never hand-edit the mirror.

**This module decides nothing and permits nothing.** It is vocabulary. Whether a stage
change is allowed is `enquiry_service.ALLOWED_TRANSITIONS` and
`admissions_service.TRANSITIONS`, and both are unchanged by this file.
"""

from __future__ import annotations

# The one ordered vocabulary. Index 0 is the first contact, the last is a closed record.
JOURNEY_STEPS = [
    ("enquired", "Enquired"),
    ("in_touch", "In touch"),
    ("visiting", "Visiting"),
    ("applied", "Applied"),
    ("assessed", "Assessed"),
    ("offered", "Offered a place"),
    ("accepted", "Place accepted"),
    ("enrolled", "On the roll"),
    ("closed", "Closed"),
]

STEP_KEYS = [key for key, _ in JOURNEY_STEPS]
STEP_LABELS = dict(JOURNEY_STEPS)

# "Closed" is deliberately last in the list but is NOT further along than "on the roll".
# It is an ending, not a rung. Anything that compares two positions must skip it, which
# is what `_rank` below does by giving it no rank at all.
CLOSED = "closed"
ENROLLED = "enrolled"

# Enquiry stage -> journey step. The legacy stages (`applied`, `admitted`, `closed`) are
# here because enquiry records already carry them, not because anything writes them.
ENQUIRY_STAGE_TO_STEP = {
    "new": "enquired",
    "contacted": "in_touch",
    "visit_scheduled": "visiting",
    "visited": "visiting",
    "documents_submitted": "applied",
    "fee_paid": "accepted",
    "enrolled": "enrolled",
    "lost": "closed",
    "applied": "applied",
    "admitted": "accepted",
    "closed": "closed",
}

# Application stage -> journey step.
APPLICATION_STAGE_TO_STEP = {
    "draft": "applied",
    "submitted": "applied",
    "under_review": "applied",
    "assessment_scheduled": "assessed",
    "assessed": "assessed",
    "offered": "offered",
    "accepted": "accepted",
    "enrolled": "enrolled",
    "rejected": "closed",
    "withdrawn": "closed",
}


def _rank(step: str | None) -> int:
    """How far along a step is. `closed` and anything unknown score -1, so they never
    win a comparison against a real position."""
    if not step or step == CLOSED:
        return -1
    try:
        return STEP_KEYS.index(step)
    except ValueError:
        return -1


def step_for_enquiry_stage(stage: str | None) -> str | None:
    return ENQUIRY_STAGE_TO_STEP.get(str(stage or "").strip().lower())


def step_for_application_stage(stage: str | None) -> str | None:
    return APPLICATION_STAGE_TO_STEP.get(str(stage or "").strip().lower())


def describe_position(enquiry: dict | None = None, application: dict | None = None) -> dict:
    """Where one family actually is, as a single answer.

    `source` says which record decided it, because "we have an application for this
    child" and "somebody moved the enquiry along" are different facts and a reader is
    entitled to know which one they are looking at.
    """
    enquiry_step = step_for_enquiry_stage((enquiry or {}).get("status"))
    application_step = step_for_application_stage((application or {}).get("status"))

    if application_step and _rank(application_step) >= _rank(enquiry_step):
        step, source = application_step, "application"
    elif enquiry_step:
        step, source = enquiry_step, "enquiry"
    elif application_step:
        step, source = application_step, "application"
    else:
        return {
            "step": None, "label": "Not known", "index": None,
            "total": len(STEP_KEYS) - 1, "source": None, "closed": False,
        }

    return {
        "step": step,
        "label": STEP_LABELS[step],
        # One-based, and `closed` has no number because it is an ending, not a rung.
        "index": None if step == CLOSED else STEP_KEYS.index(step) + 1,
        "total": len(STEP_KEYS) - 1,
        "source": source,
        "closed": step == CLOSED,
    }
