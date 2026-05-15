# ADR-001: schoolId — env-var per instance vs JWT claim

**Date:** 2026-05-15
**Status:** Accepted
**Part:** 4 — Multi-tenancy + Data Layer

## Decision

**Use env-var per instance (Option A) for current phase.** Document Option B (JWT claim) migration path for future SaaS expansion.

## Context

EduFlow currently reads `schoolId` from `os.environ.get("SCHOOL_ID", "aaryans-joya")`. This means one Elastic Beanstalk environment per school. As of 2026-05-15, EduFlow serves exactly one school (The Aaryans). The growth roadmap targets 5–10 additional schools before a SaaS rearchitecture.

## Consequences

**Positive (Option A):**
- Zero impact to JWT structure, scoped_filter callsites, auth_users schema
- Each school has full deployment isolation — no cross-school data risk at DB level
- Simple ops model — add a school → spin up new EB environment + Atlas tenant

**Negative (Option A):**
- Does not scale to 100+ schools without significant ops overhead
- Each school requires a separate deployment pipeline

## Hardening required (Part 4)

1. `SCHOOL_ID` unset in non-dev → `ValueError` at startup
2. `SCHOOL_ID` documented in `.env.example`
3. `/api/health/ready` includes `school_id_configured: true/false`

## Option B migration path (future)

When needed (>10 schools or ops cost dominates):

1. Add `school_id` to JWT payload in `create_jwt()` / `decode_jwt()`
2. Set `school_id` via `contextvars` in auth middleware (per-request context)
3. Change `tenant.get_school_id()` to read from contextvar instead of env
4. Move `auth_users` out of `SYSTEM_COLLECTIONS` — add `school_id` field
5. Remove default `"aaryans-joya"` fallback
6. Test: single-instance serving two schools returns isolated data
