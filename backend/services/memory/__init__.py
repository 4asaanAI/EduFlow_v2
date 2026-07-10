"""AI self-learning (Memory + Skills) for Owner & Principal — Epic G.

Cloned and customized from the open-source Odysseus project
(github.com/pewdiepie-archdaemon/odysseus): `src/memory.py`, `src/memory_vector.py`,
`services/memory/skills.py`, `skill_extractor.py`, `routes/memory_routes.py`.

EduFlow adaptations vs Odysseus:
- Storage is **MongoDB scoped by `(user_id, schoolId)`** (Odysseus used flat JSON
  files keyed by a single `owner`). This gives tenant + per-user isolation (FR34).
- Every write is PII-minimized with `ai.redaction.redact_text_for_memory()` (DPDP).
- Phase-1 self-learning is **Owner + Principal only** (Story F.11 / FR43); never
  students. Callers gate via `services.memory.is_memory_subject`.
- No UI surface anywhere (FR32) — the assistant auto-saves and asks in chat only.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def is_memory_subject(user: Optional[Dict[str, Any]]) -> bool:
    """True iff the assistant may CAPTURE (auto-learn) from this user.

    Backward-compatible alias of the R10.5 capture predicate. Default: Owner +
    Principal only (Phase-1). Widening is a config change in
    `services.memory.policy` (`MEMORY_CAPTURE_EXTRA_ROLES`), never an engine change.
    """
    from services.memory.policy import can_capture_memories

    return can_capture_memories(user or {})


def can_recall_memories(user: Optional[Dict[str, Any]]) -> bool:
    """True iff learned memories/skills may be recalled into this user's turns (R10.5)."""
    from services.memory.policy import can_recall_memories as _recall

    return _recall(user or {})


def can_capture_memories(user: Optional[Dict[str, Any]]) -> bool:
    """True iff the assistant may auto-learn from this user (R10.5)."""
    from services.memory.policy import can_capture_memories as _capture

    return _capture(user or {})
