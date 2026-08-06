"""
Give guardian records the S3 key for their own photograph (2026-08-06).

WHY THIS IS NEEDED
------------------
When the parent photographs were copied into the school's own bucket, the key was
written onto the STUDENT record (`mother_photo_s3_key`, `father_photo_s3_key`,
`guardian_photo_s3_key`) because the `guardians` collection had no photo field at the
time. The guardian rows later got a `photo_url` — but it still points at the previous
vendor's public CDN, and they carry no key.

That matters now that photographs are served as signed links from our own bucket
(`services/photo_url_service.py`): a guardian row with no key and a vendor URL resolves
to NO photograph, because handing the browser the public link is exactly the exposure
being closed. So the 255 parent photographs that currently work would have stopped
working.

The image is the same file in both places, so the key is simply copied across, matched
on RELATION (Father -> father_photo, Mother -> mother_photo). Nothing is invented: a
guardian only gets a key when the child's record actually holds one for that relation.

RULES OBSERVED: fill blanks only; never overwrite; never delete; dry-run by default.

Usage:
    python scripts/backfill_guardian_photo_keys_2026_08_06.py           # dry run
    python scripts/backfill_guardian_photo_keys_2026_08_06.py --apply
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import certifi
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / "backend" / ".env")
SCHOOL_ID = os.environ.get("SCHOOL_ID", "aaryans-joya")

# guardian.relation (lowercased) -> the field on the student record holding the key
RELATION_TO_FIELD = {
    "father": "father_photo",
    "mother": "mother_photo",
}
FALLBACK_FIELD = "guardian_photo"


async def main(apply: bool) -> int:
    client = AsyncIOMotorClient(os.environ["MONGO_URL"], tlsCAFile=certifi.where(), retryWrites=True)
    db = client[os.environ["DB_NAME"]]
    try:
        guardians = [g async for g in db.guardians.find(
            {"schoolId": SCHOOL_ID, "photo_url": {"$nin": [None, ""]}},
            {"_id": 0, "id": 1, "student_id": 1, "relation": 1,
             "photo_url": 1, "photo_url_s3_key": 1})]
        print("=" * 68)
        print("GUARDIAN PHOTO KEY BACKFILL")
        print("=" * 68)
        print(f"guardians holding a photo   : {len(guardians)}")
        already = sum(1 for g in guardians if g.get("photo_url_s3_key"))
        print(f"  already have an S3 key    : {already}")

        sids = list({g["student_id"] for g in guardians})
        students = {}
        for i in range(0, len(sids), 400):
            async for s in db.students.find(
                    {"schoolId": SCHOOL_ID, "id": {"$in": sids[i:i + 400]}},
                    {"_id": 0, "id": 1, "mother_photo_s3_key": 1, "father_photo_s3_key": 1,
                     "guardian_photo_s3_key": 1}):
                students[s["id"]] = s

        to_write, no_key = [], 0
        for g in guardians:
            if g.get("photo_url_s3_key"):
                continue
            st = students.get(g["student_id"])
            if not st:
                no_key += 1
                continue
            field = RELATION_TO_FIELD.get((g.get("relation") or "").strip().lower(), FALLBACK_FIELD)
            key = st.get(f"{field}_s3_key") or st.get(f"{FALLBACK_FIELD}_s3_key")
            if not key:
                no_key += 1
                continue
            to_write.append((g["id"], key))

        print(f"  WOULD BACKFILL            : {len(to_write)}")
        print(f"  no matching key on the child's record : {no_key}")

        if not apply:
            print("\nDRY RUN — nothing written. Re-run with --apply to write.")
            return 0

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        manifest = ROOT / "aaryans_database" / f"_rollback_guardian_keys_{stamp}.json"
        manifest.write_text(json.dumps({
            "script": Path(__file__).name, "written_at": stamp,
            "note": "To roll back, unset photo_url_s3_key on exactly these guardian ids.",
            "guardian_ids": [gid for gid, _ in to_write],
        }, indent=1))
        print(f"\nrollback manifest -> {manifest.name}")

        n = 0
        for gid, key in to_write:
            res = await db.guardians.update_one(
                {"id": gid, "schoolId": SCHOOL_ID,
                 "$or": [{"photo_url_s3_key": None}, {"photo_url_s3_key": {"$exists": False}}]},
                {"$set": {"photo_url_s3_key": key}})
            n += res.modified_count
        print(f"guardians updated           : {n}")
        verify = await db.guardians.count_documents(
            {"schoolId": SCHOOL_ID, "photo_url_s3_key": {"$nin": [None, ""]}})
        print(f"verified: guardians with a key : {verify}")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    sys.exit(asyncio.run(main(ap.parse_args().apply)))
