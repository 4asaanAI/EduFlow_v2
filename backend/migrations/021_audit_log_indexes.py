from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def run(db):
    await db.audit_logs.create_index(
        [("schoolId", 1), ("created_at", -1)],
        name="school_created_at",
    )
    await db.audit_logs.create_index(
        [("schoolId", 1), ("entity_id", 1), ("created_at", -1)],
        name="school_entity_created_at",
    )
    logger.info("migration_021: audit log indexes ensured")
    return {"indexes": ["school_created_at", "school_entity_created_at"]}


async def migrate(db):
    await run(db)
