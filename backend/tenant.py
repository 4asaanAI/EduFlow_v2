"""School tenant helpers."""

from __future__ import annotations

import os

DEFAULT_SCHOOL_ID = "aaryans-joya"


def get_school_id() -> str:
    return os.environ.get("SCHOOL_ID", DEFAULT_SCHOOL_ID)


def add_school_id(document: dict, school_id: str | None = None) -> dict:
    if not isinstance(document, dict):
        return document
    if "schoolId" in document:
        return document
    return {**document, "schoolId": school_id or get_school_id()}


def scoped_filter(query: dict | None, school_id: str | None = None) -> dict:
    base = query or {}
    current_school_id = school_id or get_school_id()
    if "schoolId" in base:
        return base
    school_clause = {
        "$or": [
            {"schoolId": current_school_id},
            {"schoolId": {"$exists": False}},
        ]
    }
    if not base:
        return school_clause
    return {"$and": [base, school_clause]}


def scoped_query(
    query: dict | None = None,
    *,
    branch_id: str | None = None,
    school_id: str | None = None,
) -> dict:
    """Single helper enforcing BOTH tenancy axes (schoolId + branch_id).

    Part 1 (Auth + RBAC) — replaces ad-hoc branch_id additions to MongoDB
    queries that historically forgot one or the other. Pass the caller's
    branch_id explicitly (typically from `user["branch_id"]`); the school_id
    defaults to the env-canonical tenant.

    The schoolId clause tolerates documents that predate the schoolId field
    via `$exists: False` (backward compatible with pre-Story-1-3 rows).
    branch_id is matched exactly — no exists-false fallback because every
    operational doc has been backfilled.
    """
    base = scoped_filter(query, school_id=school_id)
    if branch_id is None:
        return base
    # Compose: existing $and with branch_id, or wrap a fresh $and.
    if "$and" in base:
        return {"$and": [*base["$and"], {"branch_id": branch_id}]}
    if "branch_id" in base:
        return base
    return {"$and": [base, {"branch_id": branch_id}]}
