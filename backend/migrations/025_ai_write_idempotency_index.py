from __future__ import annotations


async def migrate(db) -> None:
    """AI Layer Hardening D.4 (AD6): unique index for AI plan-execution idempotency.

    The atomic plan executor (`ai/plan_executor.py`) claims a per-step key
    ``idempotency_key = f"{plan_token}:{step_idx}"`` inside the confirmed-write
    transaction. The UNIQUE index below is what guarantees exactly-once execution:
    two concurrent confirms of the same plan race to insert the same key — the loser
    hits DuplicateKey and its transaction aborts, so the action applies exactly once.

    Mirrors the declaration in ``database._create_indexes()`` (this migration makes it
    exist on already-running clusters). Idempotent + best-effort, like the others.
    """
    try:
        await db.ai_write_idempotency.create_index("idempotency_key", unique=True)
    except Exception:
        # Index may already exist (created by _create_indexes on app boot) — fine.
        pass
