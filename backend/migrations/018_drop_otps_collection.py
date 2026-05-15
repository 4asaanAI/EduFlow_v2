from __future__ import annotations
"""Migration 018: Drop the otps collection — zero code references, dead indexes."""


async def run(db):
    collections = await db.list_collection_names()
    if "otps" in collections:
        await db.drop_collection("otps")
    return {"dropped": "otps" in collections}


# Support both calling conventions used by the runner
async def migrate(db=None):
    await run(db)
