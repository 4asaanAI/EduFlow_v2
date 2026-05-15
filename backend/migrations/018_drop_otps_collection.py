from __future__ import annotations
# Migration 018: Drop the otps collection — zero code references, dead indexes.

import os
import logging

logger = logging.getLogger(__name__)


async def run(db):
    collections = await db.list_collection_names()
    dropped = "otps" in collections
    if dropped:
        await db.drop_collection("otps")
        logger.info("migration_018: otps collection dropped")
    else:
        logger.info("migration_018: otps collection not present, nothing to drop")
    return {"dropped": dropped}


async def migrate(db):
    # db is always provided by run_all.py; if called directly, pass a real DB instance.
    await run(db)
