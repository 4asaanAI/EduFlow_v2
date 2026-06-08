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
    """True iff self-learning applies to this user (Phase-1: Owner + Principal only).

    Reuses the exact Phase-1 pilot predicate so memory/skills can never widen the
    locked-down surface independently of the action policy.
    """
    from services.ai_action_policy import is_owner_or_principal

    return is_owner_or_principal(user or {})
