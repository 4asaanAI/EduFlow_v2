"""School tenant helpers."""

from __future__ import annotations

import contextvars
import logging
import os

logger = logging.getLogger(__name__)

DEFAULT_SCHOOL_ID = "aaryans-joya"

# Per-request school context — set by SchoolContextMiddleware for authenticated requests
_school_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("school_id", default=None)


def validate_school_id() -> None:
    """Called at startup. Raises ValueError if SCHOOL_ID is not configured in non-dev."""
    env = os.environ.get("ENVIRONMENT", "development").lower()
    school_id = os.environ.get("SCHOOL_ID", "")
    if not school_id and env not in ("development", "test", "testing"):
        raise ValueError(
            "SCHOOL_ID environment variable is required. "
            "Set it to your school's identifier (e.g. SCHOOL_ID=my-school). "
            "Missing SCHOOL_ID in a non-development environment would silently "
            "route all requests to the wrong tenant."
        )
    if not school_id:
        logger.warning(
            "SCHOOL_ID not set — using dev default 'aaryans-joya'. "
            "Set SCHOOL_ID in .env for a consistent dev environment."
        )


def get_school_id() -> str:
    ctx_val = _school_id_var.get()
    if ctx_val:
        return ctx_val
    return os.environ.get("SCHOOL_ID") or DEFAULT_SCHOOL_ID


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
    # Strict filter — no $exists:False fallback (Story 1-3 backfilled all docs)
    school_clause = {"schoolId": current_school_id}
    if not base:
        return school_clause
    return {"$and": [base, school_clause]}


def _find_branch_id_values(node) -> list:
    """Walk a Mongo query tree collecting any literal `branch_id` clauses.

    Recurses into `$and` / `$or` / `$nor`. Returns the raw values (anything
    nested inside another operator like `{"$ne": ...}` is returned as-is so
    the caller can decide whether it conflicts).
    """
    found = []

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "branch_id":
                    found.append(v)
                elif k in ("$and", "$or", "$nor") and isinstance(v, list):
                    for child in v:
                        walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(node)
    return found


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

    The schoolId clause is strict (no $exists:False fallback) — Story 1-3
    backfilled all documents. branch_id is matched exactly with the same
    strict guarantee.

    Part 1.5 Patch M (defense in depth):
        * Treat empty-string branch_id the same as None (no clause applied).
        * If the caller's query already pins branch_id (anywhere, including
          inside `$and`/`$or`) AND that value differs from the parameter,
          raise ValueError instead of silently letting the caller punch
          through tenant boundaries.
        * If the caller's query already pins the same branch_id, return the
          query unchanged (no double-clause).
    """
    # Empty string is just as wrong as None — fail closed instead of injecting
    # `{"branch_id": ""}` which matches no documents but pretends to scope.
    if branch_id == "":
        branch_id = None

    base = scoped_filter(query, school_id=school_id)
    if branch_id is None:
        return base

    existing = _find_branch_id_values(query or {})
    if existing:
        # Any caller-supplied branch_id MUST match the requested branch.
        for value in existing:
            if value != branch_id:
                raise ValueError(
                    "scoped_query branch_id conflict: query has %r, parameter has %r"
                    % (value, branch_id)
                )
        # All occurrences match — caller already scoped correctly.
        return base

    # Compose: existing $and with branch_id, or wrap a fresh $and.
    if "$and" in base:
        return {"$and": [*base["$and"], {"branch_id": branch_id}]}
    return {"$and": [base, {"branch_id": branch_id}]}
