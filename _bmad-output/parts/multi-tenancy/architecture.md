---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8, 9]
workflowType: 'architecture'
project_name: 'EduFlow Quality Sweep — Part 4: Multi-tenancy + Data Layer'
user_name: 'Abhimanyusingh'
date: '2026-05-15'
status: 'complete'
part: 4
part_name: 'Multi-tenancy + Data Layer'
parent_architecture: '_bmad-output/planning-artifacts/architecture.md'
inputDocuments:
  - '_bmad-output/planning-artifacts/architecture.md'
  - '_bmad-output/project-context.md'
  - '_bmad-output/planning-artifacts/epic-part4-multitenancy.md'
  - 'backend/database.py'
  - 'backend/tenant.py'
  - 'backend/middleware/auth.py'
  - 'backend/routes/exports.py'
  - 'backend/ai/tool_functions_v2.py'
  - 'backend/migrations/run_all.py'
adrs:
  - 'adr-001-school-id-strategy.md'
  - 'adr-002-audit-gate-strategy.md'
---

# Architecture — Part 4: Multi-tenancy + Data Layer

**Author:** Abhimanyusingh
**Date:** 2026-05-15
**Scope:** Focused architectural hardening of the multi-tenancy model. Supplements (does not replace) the product architecture at `_bmad-output/planning-artifacts/architecture.md`.

---

## 1. Context

EduFlow's dual-axis tenancy model was established in Part 1 (schoolId) and Part 1.5 (scoped_query for branch_id). Parts 2 and 3 deferred several structural issues that are now blockers for multi-branch correctness and future multi-school SaaS. This document records the architectural decisions for Part 4.

### Existing Tenancy Model (entering Part 4)

```
schoolId (env-var SCHOOL_ID)  ←→  ScopedDatabase / ScopedCollection
                                      auto-injects on writes
                                      auto-filters on reads
                                      (scoped_filter)

branch_id (JWT claim)         ←→  scoped_query(query, branch_id=user["branch_id"])
                                      caller must pass explicitly
                                      NOT auto-injected
```

**Known gaps entering Part 4:**
1. `exports.py` enrichment lookups bypass ScopedCollection (bare `find_one`)
2. `require_role()` can't express `sub_category` — inline checks accumulating
3. Migration 014 missing from `run_all.py`
4. `db.otps` collection has indexes but zero code — dead weight
5. ~30 AI tool callsites use `scoped_filter` not `scoped_query` — branch leak risk
6. `schoolId` comes from env only (not JWT) — architectural blocker for SaaS
7. Audit write-ahead gate is synchronous — availability bottleneck at scale

---

## 2. Architectural Decisions

### ADR-001: schoolId Strategy — env-var per instance vs JWT claim

**Status:** DECIDED — Option A (env-var per instance) for current phase

**Context:**
- Current: `SCHOOL_ID` env var, one deployment per school
- Future SaaS: single deployment, multiple schools, schoolId must come from JWT

**Options considered:**

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A: env-var (current)** | One EB instance per school | Simple, zero JWT change, zero scoped_filter change | Doesn't scale beyond ~10 schools without ops overhead |
| **B: JWT claim** | schoolId in JWT, single instance | True SaaS, one deployment | Requires auth_users schema change, all scoped_filter → JWT-aware, cross-school admin impossible without multi-claim JWT |

**Decision:** **Option A for Part 4.** EduFlow is at 1 school (The Aaryans) and the growth roadmap is to onboard 5–10 more schools before rebuilding the auth layer. Option B is documented as a future migration path.

**Part 4 hardening under Option A:**
- `SCHOOL_ID` missing at startup → `ValueError` in non-dev environments (fail fast, no silent default)
- `SCHOOL_ID` added to `.env.example` with documentation
- `/api/health/ready` response includes `school_id_configured: true/false`
- ADR migration path to Option B documented below

**Option B migration path (when needed):**
1. Add `schoolId` claim to JWT payload in `create_jwt()` and `decode_jwt()`
2. Change `get_school_id()` in `tenant.py` to read from request context (via `contextvars`) instead of env
3. Change `auth_users` to be cross-school (remove from SYSTEM_COLLECTIONS isolation)
4. Update all `scoped_filter` callsites to use JWT schoolId instead of env
5. Migrate all per-school data to include `schoolId` (already done via Story 1-3 backfill)

---

### ADR-002: Audit Write-ahead Gate — synchronous vs fail-open

**Status:** DECIDED — Fail-open with warning log

**Context:**
AI dispatch path currently does a synchronous pre-write audit record before calling the LLM. If MongoDB is slow or unavailable, ALL AI requests fail even if the LLM is healthy. At scale, this is an availability risk.

**Options considered:**

| Option | Description | Availability | Audit Completeness |
|--------|-------------|-------------|-------------------|
| **A: Synchronous fail-closed (current)** | Audit write required; AI fails if write fails | Low — DB unavailability = AI unavailability | 100% — no action without record |
| **B: Fail-open with error log** | Audit write attempted; warning if fails; AI proceeds | High — DB unavailability ≠ AI unavailability | ~99% — rare failures logged |
| **C: Async queue** | Write audit to queue; worker drains to DB | Very high | 100% — eventual consistency | Complex infra |

**Decision:** **Option B (fail-open with error log) for Part 4.**

Rationale:
- EduFlow is a single-school, single-region deployment. MongoDB Atlas M10 is highly available (99.995% SLA).
- The audit log is an operational tool, not a compliance/legal requirement. Missing one record under DB stress is acceptable.
- Option C (async queue) introduces infra complexity (Redis/SQS) that isn't justified at current scale.
- Fail-open preserves teacher/principal experience (attendance, fee collection) during brief DB hiccups.

**Implementation:**
```python
# Fail-open pattern:
try:
    await db.audit_log.insert_one(pre_write_record)
except Exception:
    logger.warning("audit_pre_write_failed", exc_info=True, extra={"action": action_name})
    # Proceed — do not raise
```

**Re-evaluation trigger:** If audit failure rate exceeds 0.1% in production metrics, escalate to Option C.

---

### ADR-003: Branch-ID Enforcement Convention

**Status:** DECIDED — Convention + CI grep, not structural enforcement

**Context:**
`scoped_filter()` (school-only) and `scoped_query(branch_id=...)` (school + branch) are both available. ~30 AI tool callsites in `tool_functions_v2.py` use `scoped_filter` without branch_id. This is technically correct for school-wide queries, but the lack of consistency creates confusion.

**Decision:** Convention-based enforcement for Part 4:

1. **All AI tool queries** that operate on per-branch data MUST use `scoped_query(branch_id=branch_id)`
2. **Intentional school-wide queries** (cross-branch context) MUST have `# branch-scope: intentional — <reason>` comment
3. **CI rule** (grep): Any new `scoped_filter(` in `tool_functions_v2.py` without a `# branch-scope` comment on the same or adjacent line fails the check

**Structural enforcement (deferred to Option B schoolId migration):**
- When Option B lands, `ScopedDatabase` can be upgraded to also inject `branch_id` from request context, making structural enforcement feasible.

---

### ADR-004: require_access() Helper Design

**Status:** DECIDED

**Context:**
`require_role()` only checks `role`. Sub_category constraints (e.g. `admin + accountant`) are expressed as either ad-hoc inline checks or one-off helpers (`require_owner_or_principal`). As role verticals grow, this proliferates.

**Decision:** Add `require_access(role_or_roles, sub_category=None)` to `middleware/auth.py`:

```python
def require_access(*roles: str, sub_category: str | tuple[str, ...] | None = None):
    """
    FastAPI dependency checking role AND optional sub_category.

    Examples:
      Depends(require_access("owner"))
      Depends(require_access("admin", sub_category="accountant"))
      Depends(require_access("owner", "admin", sub_category=("principal", "accountant")))
    """
    if not roles:
        raise ValueError("require_access() requires at least one role argument")

    def dependency(request: Request):
        user = get_current_user(request)
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        if sub_category is not None:
            allowed = (sub_category,) if isinstance(sub_category, str) else sub_category
            if user.get("sub_category") not in allowed:
                raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return dependency
```

**Migration:** Existing `require_role()` and `require_owner_or_principal()` remain unchanged — no breaking changes. New routes use `require_access()`. Existing inline sub_category checks in routes are migrated to `require_access()` in Story P4.2.

---

## 3. Data Architecture Decisions

### Drop `db.otps` Collection

**Decision:** Remove `otps` from `SYSTEM_COLLECTIONS`, remove its indexes, and drop via migration 018.

**Rationale:** Zero code references. The OTP-based auth flow was never implemented (SMS OTP was planned in the original build plan but replaced by password auth). Keeping dead indexes wastes Atlas capacity and creates false expectations.

**Future note:** If SMS OTP is implemented in Phase 7 (WhatsApp/Twilio integration), a new migration adds the collection back. The name `019_add_otp_auth` makes the intent clear.

### Migration Ordering Fix

**Decision:** Migration 014 (`014_ensure_maintenance_user`) MUST be added to `run_all.py` immediately. It creates the maintenance user role and is required for a working deployment.

**Root cause:** The file was created during Part 3 development but missed the `run_all.py` update (likely a merge oversight).

**Audit rule:** `run_all.py` must always contain an import for every `.py` file in `migrations/` (except `__init__.py` and `run_all.py` itself). This will be enforced by a test in `tests/backend/test_migrations.py`.

---

## 4. AI Scoping Architecture

### branch_id Threading in tool_functions_v2

**Current state:** Tool functions receive a `context` dict that includes the user object. The user object has `branch_id` from the JWT. But not all tool functions pass `branch_id` to `scoped_query()`.

**Required pattern:**
```python
async def tool_get_students(context: dict, params: dict) -> dict:
    user = context["user"]
    branch_id = user.get("branch_id")
    db = get_db()
    students = await db.students.find(
        scoped_query({"class_id": params.get("class_id")}, branch_id=branch_id)
    ).to_list(None)
    return {"students": students}
```

**Audit scope:** Every function in `tool_functions_v2.py` that queries an operational collection must be reviewed. School-wide queries (e.g., fetching all classes for context building) may legitimately omit `branch_id` — these require `# branch-scope: intentional` comment.

---

## 5. Context Builder Scoping

### Decision: School-scoped, intentionally not branch-scoped

`context_builder.py` builds the AI's contextual knowledge (what data exists in the school). This is designed to be school-wide — a teacher in Branch A can reference "Branch B's exam schedule" in conversation even if they can't write to it. **Branch filtering happens at the tool execution layer, not the context layer.**

This decision is correct and should be documented (not changed) in Part 4. Story P4.8 adds unit tests that verify and document this behavior.

```python
# context_builder.py — top of file
# SCOPING NOTE: Context builder deliberately uses school-wide scope (no branch_id filter).
# Context gives the AI "awareness" of the school — teachers may ask about any branch.
# Branch isolation is enforced at the TOOL EXECUTION layer (tool_functions_v2.py),
# not at the context-building layer. Do not add branch_id filters here without
# revisiting this decision in the architecture doc (docs/architecture-backend.md).
```

---

## 6. Security Implications

| Change | Security Impact |
|--------|----------------|
| `require_access()` helper | Positive — reduces inline sub_category check proliferation; centralizes auth logic |
| exports.py fix | Positive — eliminates cross-school data leak in exam results export |
| `scoped_query` enforcement in AI tools | Positive — eliminates cross-branch data leak in AI responses |
| Fail-open audit gate | Slightly negative — rare audit gaps under DB stress; acceptable at current scale |
| SCHOOL_ID startup guard | Positive — eliminates silent default that could route to wrong tenant |
| Drop otps collection | Neutral — removes dead code, no functional change |

---

## 7. Test Strategy for Part 4

| Story | New Tests | Type |
|-------|-----------|------|
| P4.1 | Cross-school isolation in exam-results export | Integration |
| P4.2 | require_access() unit tests (4 cases) | Unit |
| P4.3 | Migration completeness check; fresh DB migration run | Integration |
| P4.4 | `db.otps` zero-reference grep; post-migration drop | Integration |
| P4.5 | Branch isolation in 3 AI tool responses | Integration |
| P4.6 | SCHOOL_ID startup guard; health/ready field | Unit + Integration |
| P4.7 | Fail-open audit gate under simulated DB failure | Integration (mock) |
| P4.8 | 7 context_builder sub-helper tests | Unit |

**Target:** 387 + ~25 new = ~412 backend tests passing at Part 4 close.

---

## 8. Implementation Order (Story Sequencing)

Priority order recommended for implementation:

1. **P4.3** (migration 014 + audit) — lowest risk, highest operational impact, do first
2. **P4.1** (exports.py cross-tenant) — data correctness, Critical priority
3. **P4.4** (drop otps) — cleanup, no risk
4. **P4.2** (require_access helper) — auth improvement, no breaking changes
5. **P4.5** (branch_id AI tools) — most callsites, methodical audit
6. **P4.8** (context_builder tests) — test-only, no production changes
7. **P4.6** (schoolId ADR + startup guard) — low LOC change, high operational value
8. **P4.7** (audit fail-open) — small change, needs careful testing

---

## 9. Files Changed by Part 4

| File | Stories | Change Type |
|------|---------|-------------|
| `backend/routes/exports.py` | P4.1 | Bug fix |
| `backend/middleware/auth.py` | P4.2 | New helper |
| `backend/migrations/run_all.py` | P4.3 | Add missing migration |
| `backend/migrations/018_drop_otps_collection.py` | P4.4 | New migration |
| `backend/database.py` | P4.4 | Remove otps from SYSTEM_COLLECTIONS + indexes |
| `backend/ai/tool_functions_v2.py` | P4.5 | Audit + fix scoped_query |
| `backend/tenant.py` | P4.6 | Add startup guard comment/note |
| `backend/server.py` | P4.6 | Add school_id_configured to /health/ready |
| `backend/.env.example` | P4.6 | Add SCHOOL_ID |
| `backend/routes/audit.py` | P4.7 | Fail-open wrap |
| `backend/ai/context_builder.py` | P4.8 | Add scoping comment |
| `tests/backend/test_exports.py` | P4.1 | New test |
| `tests/backend/test_auth.py` | P4.2 | New tests |
| `tests/backend/test_migrations.py` | P4.3 | New test |
| `tests/backend/test_context_builder.py` | P4.8 | New file |
| `docs/architecture-backend.md` | P4.6 | Option B migration path section |
| `_bmad-output/parts/multi-tenancy/adr-001-school-id-strategy.md` | P4.6 | ADR |
| `_bmad-output/parts/multi-tenancy/adr-002-audit-gate-strategy.md` | P4.7 | ADR |
