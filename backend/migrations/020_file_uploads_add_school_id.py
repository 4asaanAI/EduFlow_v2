from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


async def run(db):
    school_id = os.environ.get("SCHOOL_ID", "aaryans-joya")
    result = await db.file_uploads.update_many(
        {"schoolId": {"$exists": False}},
        {"$set": {"schoolId": school_id}},
    )
    await db.file_uploads.create_index(
        [("schoolId", 1), ("uploaded_by", 1), ("created_at", -1)],
        name="school_uploaded_by_created_at",
    )
    await db.file_uploads.create_index(
        [("schoolId", 1), ("linked_table", 1), ("linked_id", 1), ("created_at", -1)],
        name="school_linked_created_at",
    )
    logger.info(
        "migration_020: file_uploads schoolId backfill complete",
        extra={
            "matched": result.matched_count,
            "modified": result.modified_count,
            "school_id": school_id,
        },
    )
    return {"matched": result.matched_count, "modified": result.modified_count}


async def migrate(db):
    await run(db)
