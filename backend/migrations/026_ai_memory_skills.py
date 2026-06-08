from __future__ import annotations


async def migrate(db) -> None:
    """AI Layer Hardening Epic G: indexes for AI self-learning (memory + skills).

    Mirrors the declarations in ``database._create_indexes()`` so already-running
    clusters get them too. Scoped by ``(schoolId, user_id)`` for tenant + per-owner
    isolation (FR34); the ``expire_at`` TTL enforces retention (G.7). Idempotent +
    best-effort, like the other migrations.
    """
    try:
        await db.ai_memories.create_index([("schoolId", 1), ("user_id", 1), ("updated_at_ts", -1)])
    except Exception:
        pass
    try:
        await db.ai_memories.create_index([("schoolId", 1), ("student_refs", 1)])
    except Exception:
        pass
    try:
        # TTL retention anchor — Mongo deletes a memory once its `expire_at` Date passes.
        await db.ai_memories.create_index("expire_at", expireAfterSeconds=0)
    except Exception:
        pass
    try:
        await db.ai_skills.create_index([("schoolId", 1), ("user_id", 1), ("updated_at_ts", -1)])
    except Exception:
        pass
