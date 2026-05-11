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
