from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def run(db):
    name = "school_user_read_created_at"
    await db.notifications.create_index(
        [("schoolId", 1), ("user_id", 1), ("read", 1), ("created_at", -1)],
        name=name,
    )
    logger.info("migration_019: notifications compound index ensured", extra={"index": name})
    return {"index": name}


async def migrate(db):
    await run(db)
