from __future__ import annotations


async def migrate(db) -> None:
    """Create only the indexes used by leadership platform messaging.

    This migration writes no school records and is idempotent. Run this file by
    itself after review; never invoke ``run_all.py`` against the live database.
    """
    await db.platform_message_threads.create_index(
        [("schoolId", 1), ("branch_id", 1), ("member_ids", 1), ("updated_at", -1)]
    )
    await db.platform_message_threads.create_index(
        [("schoolId", 1), ("branch_id", 1), ("direct_key", 1)], unique=True, sparse=True
    )
    await db.platform_messages.create_index(
        [("schoolId", 1), ("branch_id", 1), ("thread_id", 1), ("created_at", -1)]
    )
    await db.platform_message_receipts.create_index(
        [("schoolId", 1), ("branch_id", 1), ("message_id", 1), ("user_id", 1)], unique=True
    )
    await db.platform_message_receipts.create_index(
        [("schoolId", 1), ("branch_id", 1), ("user_id", 1), ("read_at", 1), ("thread_id", 1)]
    )
    await db.platform_message_presence.create_index(
        [("schoolId", 1), ("branch_id", 1), ("user_id", 1)], unique=True
    )
