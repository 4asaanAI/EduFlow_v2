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
