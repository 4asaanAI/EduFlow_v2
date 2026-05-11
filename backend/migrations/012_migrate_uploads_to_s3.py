"""
Migration 012: Move legacy file_uploads binary data/local files to S3.

Run against a copy of production first:
    python backend/migrations/012_migrate_uploads_to_s3.py

This migration is idempotent. Records with an existing s3_key are skipped.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.s3_storage import build_upload_key, infer_content_type, upload_bytes


load_dotenv(Path(__file__).parent.parent / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
UPLOADS_DIR = Path(__file__).resolve().parents[1] / "uploads"


def _legacy_content(record: dict) -> bytes | None:
    if record.get("data") is not None:
        return bytes(record["data"])

    safe_filename = record.get("safe_filename")
    if not safe_filename:
        return None

    candidate = UPLOADS_DIR / safe_filename
    if candidate.exists() and candidate.is_file():
        return candidate.read_bytes()
    return None


async def migrate(db=None):
    client = None
    if db is None:
        client = AsyncIOMotorClient(MONGO_URL, tlsInsecure=True, retryWrites=True)
        db = client[DB_NAME]

    try:
        print("=" * 60)
        print("Migration 012: Migrate uploads to S3")
        print("=" * 60)

        total = 0
        migrated = 0
        skipped = 0
        missing = 0

        cursor = db.file_uploads.find({})
        async for record in cursor:
            total += 1
            if record.get("s3_key"):
                skipped += 1
                continue

            content = _legacy_content(record)
            if content is None:
                missing += 1
                print(f"  Missing legacy content for upload {record.get('id') or record.get('_id')}")
                continue

            file_id = str(record.get("id") or record.get("_id"))
            file_name = record.get("file_name") or record.get("safe_filename") or file_id
            key = build_upload_key(file_id, file_name)
            content_type = infer_content_type(file_name, record.get("file_type"))
            stored = upload_bytes(
                content=content,
                key=key,
                content_type=content_type,
                original_filename=file_name,
            )

            await db.file_uploads.update_one(
                {"_id": record["_id"]},
                {
                    "$set": {
                        "storage": "s3",
                        "s3_bucket": stored.bucket,
                        "s3_key": stored.key,
                        "s3_etag": stored.etag,
                        "sha256": stored.sha256,
                        "file_size_bytes": stored.size_bytes,
                        "file_size_kb": int(stored.size_bytes / 1024),
                    },
                    "$unset": {"data": ""},
                },
            )
            migrated += 1
            print(f"  Migrated {file_id} -> s3://{stored.bucket}/{stored.key}")

        indexes = await db.file_uploads.index_information()
        if "s3_key_1" not in indexes:
            await db.file_uploads.create_index("s3_key", sparse=True)
            print("  Created sparse index on file_uploads.s3_key")

        print(f"\n  Total: {total}")
        print(f"  Migrated: {migrated}")
        print(f"  Skipped: {skipped}")
        print(f"  Missing legacy content: {missing}")
        print("\nMigration 012 complete.")

    finally:
        if client:
            client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
