/**
 * GENERATED FILE - DO NOT EDIT BY HAND.
 *
 * Mirror of `backend/services/admissions_journey.py`, which is the source of truth for
 * how the enquiry and application vocabularies line up. Regenerate with:
 *
 *     backend/.venv/Scripts/python.exe scripts/generate_admissions_journey.py
 *
 * `tests/backend/unit/test_admissions_journey_drift.py` fails if this file stops
 * matching the Python. Editing this file by hand changes nothing about what the server
 * answers; it only breaks that test, which is the intended outcome.
 *
 * Read the Python file for the reasoning behind every line below.
 */

export const JOURNEY_STEPS = [
  {
    "step": "enquired",
    "label": "Enquired"
  },
  {
    "step": "in_touch",
    "label": "In touch"
  },
  {
    "step": "visiting",
    "label": "Visiting"
  },
  {
    "step": "applied",
    "label": "Applied"
  },
  {
    "step": "assessed",
    "label": "Assessed"
  },
  {
    "step": "offered",
    "label": "Offered a place"
  },
  {
    "step": "accepted",
    "label": "Place accepted"
  },
  {
    "step": "enrolled",
    "label": "On the roll"
  },
  {
    "step": "closed",
    "label": "Closed"
  }
];

export const STEP_LABELS = {
  "accepted": "Place accepted",
  "applied": "Applied",
  "assessed": "Assessed",
  "closed": "Closed",
  "enquired": "Enquired",
  "enrolled": "On the roll",
  "in_touch": "In touch",
  "offered": "Offered a place",
  "visiting": "Visiting"
};

export const ENQUIRY_STAGE_TO_STEP = {
  "admitted": "accepted",
  "applied": "applied",
  "closed": "closed",
  "contacted": "in_touch",
  "documents_submitted": "applied",
  "enrolled": "enrolled",
  "fee_paid": "accepted",
  "lost": "closed",
  "new": "enquired",
  "visit_scheduled": "visiting",
  "visited": "visiting"
};

export const APPLICATION_STAGE_TO_STEP = {
  "accepted": "accepted",
  "assessed": "assessed",
  "assessment_scheduled": "assessed",
  "draft": "applied",
  "enrolled": "enrolled",
  "offered": "offered",
  "rejected": "closed",
  "submitted": "applied",
  "under_review": "applied",
  "withdrawn": "closed"
};
