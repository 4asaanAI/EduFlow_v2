"""
Migration 023: Add sparse indexes for transport route centroids and student coordinates.
Run: python backend/migrations/023_transport_coordinates.py

Note: plain dict {"lat": float, "lng": float} is not GeoJSON/legacy-pair format required
by 2dsphere indexes, so we use regular sparse indexes instead of 2dsphere. Haversine
distance is computed in Python — no $near/$geoWithin queries are used.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

logger = logging.getLogger(__name__)

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


async def migrate(db=None):
    client = None
    if db is None:
        client = AsyncIOMotorClient(MONGO_URL, tlsInsecure=True, retryWrites=True)
        db = client[DB_NAME]

    try:
        print("=" * 60)
        print("Migration 023: Transport coordinates indexes")
        print("=" * 60)

        # Sparse regular index on transport_routes.centroid.lat (for existence queries)
        # Plain dict {"lat": float, "lng": float} is not GeoJSON — 2dsphere not applicable.
        try:
            await db.transport_routes.create_index(
                [("centroid.lat", 1)],
                sparse=True,
                name="transport_routes_centroid_lat",
            )
            print("  Created sparse index on transport_routes.centroid.lat")
        except Exception as exc:
            print(f"  transport_routes.centroid.lat index already exists or failed: {exc}")

        # Sparse regular index on students.coordinates.lat (for existence queries)
        try:
            await db.students.create_index(
                [("coordinates.lat", 1)],
                sparse=True,
                name="students_coordinates_lat",
            )
            print("  Created sparse index on students.coordinates.lat")
        except Exception as exc:
            print(f"  students.coordinates.lat index already exists or failed: {exc}")

        print("\nMigration 023 complete.")

    finally:
        if client:
            client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
