"""The school's own identity — ONE place, verified against the school's own sources.

UI Sweep Epic 4, Story 4.3. Before this file the school's identity was written into
ten different places, and five of them said the school was in Lucknow. It is in Joya,
Amroha. Correcting it (D-15) meant editing five files and still missing a stored value
(D-15b), which the owner then had to report twice.

So there is now exactly one definition, and every surface reads from it: the settings
endpoint's fallback, the assistant's briefing, and the tool screens.

**Provenance.** Every value below comes from the school's own published material —
`theaaryans.in` (read 2026-07-22 on Abhimanyu's instruction) reconciled against the
printed prospectus recorded in
`_bmad-output/planning-artifacts/aaryans-source-of-truth-2026-07-22.md`. Nothing here
is inferred, and nothing here is a placeholder. If a value cannot be sourced, it does
not belong in this file — a plausible invention is exactly the defect this closes.

**These are DEFAULTS, not overrides.** A stored school record always wins, including
when the Owner has deliberately cleared a field to "". See `merge_school_identity`.
"""

from __future__ import annotations

import os
from typing import Any, Dict

# Verified 2026-07-22. `principal` confirmed by Abhimanyu the same day.
#
# THIS FILE DESCRIBES THE JOYA BRANCH, and only the Joya branch. Abhimanyu,
# 2026-07-22: "the Joya branch of Aaryans was established in 2015 but the other
# branches might have been established in 2005 ... we are only focusing over the
# Joya branch as we are making the platform for them only."
#
# That is why `established` is 2015 and not 2005 — 2005 belongs to a different
# branch of the same trust, which this platform does not serve. `branches` holds
# exactly one record (`branch-joya`) and all 1,802 students sit on it. If another
# branch is ever onboarded, its founding year is ITS OWN and does not belong here.
SCHOOL_IDENTITY: Dict[str, str] = {
    "school_name": "The Aaryans",
    "board": "CBSE",
    "affiliation_no": "2133014",
    "school_code": "81936",
    "established": "2015",
    "principal": "Adesh Singh",
    "address": "Prem Nagar, P.O. Joya, N.H. 24, Distt. Amroha, Uttar Pradesh 244222",
    "city": "Joya, Amroha",
    "state": "Uttar Pradesh",
    "phone": "+91 81269 65555, +91 81269 68888",
    "email": "theaaryansjoya@gmail.com",
    "website": "www.theaaryans.in",
}

# ── The school's stationery, transcribed word for word ──────────────────────────
#
# Added 2026-08-07 after Abhimanyu compared a generated PDF against the school's own
# printed enquiry form and found the letterhead did not match it: the name was set as
# "The Aaryans" rather than "THE AARYANS", and the footer had been reworded.
#
# THIS IS NOT A SECOND SOURCE OF TRUTH FOR THE ADDRESS, which is the mistake D-15 was
# raised for. `address`, `phone`, `email` and `website` above remain the values the
# product uses and displays. These strings are how those same details are PRINTED on
# the school's stationery, punctuation and all, and they exist so a document that is
# meant to look like the school's own paper actually does.
#
# Transcribed character by character from the printed enquiry form held in
# `aaryans_database/`. If the school reprints its stationery, retranscribe from the
# new form rather than editing these by eye.
LETTERHEAD = {
    "name": "THE AARYANS",
    "tagline": "A Senior Secondary Co-educational School Affiliated to CBSE, New Delhi",
    "affiliation_line": "Affiliation No. 2133014",
    "footer_address": (
        "Prem Nagar, Joya, Delhi-Moradabad Highway, Distt. Amroha-244222 (U.P.), "
        "Contact # +91-8126965555, 8126968888"
    ),
    "footer_contact": "Email ID : theaaryansjoya@gmail.com, Web : www.theaaryans.in",
    # The pale repeated wordmark printed across the whole page of the form.
    "watermark_text": "THE AARYANS",
}


# Environment may still override the four fields that were configurable before this
# file existed, so a second school deploying this code is not stuck with The Aaryans'
# details. The rest are not env-configurable: adding ten more env vars would recreate
# the scattering this file exists to end.
_ENV_OVERRIDABLE = {
    "school_name": "SCHOOL_NAME",
    "board": "SCHOOL_BOARD",
    "city": "SCHOOL_CITY",
    "state": "SCHOOL_STATE",
}

# The one branch this deployment serves. A school-level owner token may carry no
# `branch_id`, but a posting must never persist unscoped, so callers fall back to
# this. It was written as a bare "branch-joya" literal in three places (the
# commercial routes and two AI tool helpers); when a second branch is onboarded
# there must be exactly one line to reconsider, not three to find.
DEFAULT_BRANCH_ID = "branch-joya"


def default_branch_id() -> str:
    """The branch a posting belongs to when the caller's token does not say."""
    return os.environ.get("DEFAULT_BRANCH_ID", DEFAULT_BRANCH_ID)


def default_school_identity() -> Dict[str, str]:
    """The verified identity, with the four historically env-configurable overrides."""
    identity = dict(SCHOOL_IDENTITY)
    for field, env_var in _ENV_OVERRIDABLE.items():
        identity[field] = os.environ.get(env_var, identity[field])
    return identity


def merge_school_identity(stored: Dict[str, Any] | None) -> Dict[str, Any]:
    """Overlay a stored school record on the verified defaults.

    A key that is **absent** from the stored record falls back to the verified value —
    this is what let the city correction reach the product with no database write.

    A key that is **present but empty** stays empty. The Owner clearing a field is a
    decision, and a default that quietly reinstates the value he deleted is a defect
    wearing a good intention: he would have no way to diagnose it.
    """
    merged = default_school_identity()
    for key, value in (stored or {}).items():
        merged[key] = value
    return merged
