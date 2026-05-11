---
project: EduFlow Enterprise Upgrade
document: test-design-qa
author: Master Test Architect (BMAD TEA)
date: 2026-05-12
mode: System-Level
status: complete
crossRef: test-design-architecture.md
---

# Test Design — QA Execution Recipe

**Purpose:** This document is the test execution recipe for QA. It defines what to test, at what level, in what priority order, and how to set up the test environment. Architectural concerns and risk rationale are in `test-design-architecture.md`.

> **Note:** P0/P1/P2/P3 = priority and risk severity, NOT execution timing. All Playwright tests run on every PR regardless of priority; nightly/weekly cadence applies only to expensive or long-running suites. See Execution Strategy.

---

## Executive Summary

**Risk summary (from Architecture doc):**
- 4 high-priority risks (score ≥ 6): RBAC unverified (R-001), confirm-action bypassable (R-002), S3 data loss (R-003), PII in LLM context (R-004)
- All 4 must be mitigated before go-live

**Coverage summary:**
- 28 stories across 5 phases
- 95 functional requirements
- 9 AI write dispatches + 8 read-only query dispatches
- 9 roles in RBAC matrix
- Test baseline starting from zero — full build-out required

**Stack:** FastAPI backend (pytest + httpx), React 19 frontend (React Testing Library + Jest via `craco test`), Playwright for E2E

---

## Not in Scope

| Item | Reason |
|---|---|
| Teacher and Student login flows | Phase 2 — not go-live scope |
| WhatsApp/Twilio integration testing | Phase 2 Growth feature |
| Parent portal | Phase 3 Vision |
| Multi-tenancy isolation tests | Phase 2 — `schoolId` groundwork is in scope; enforcement testing is Phase 2 |
| Performance load testing beyond p95 targets | Phase 1 is single-school ≤100 concurrent users; full load suite is Phase 2 |
| WCAG 2.1 AA full compliance | Deferred to Phase 2 per PRD |
| Razorpay billing integration | Phase 2 |

---

## Dependencies & Test Blockers

### Backend/Architecture Dependencies (QA Needs These)

| Dependency | Story | Status | Blocker? |
|---|---|---|---|
| `confirm_tokens` MongoDB collection with TTL index | Story 18 | Not implemented | YES — blocks Story 22 tests |
| `mongomock` or `motor-mock` selection and setup | Pre-Story 21 | Not decided | YES — blocks all backend tests |
| `resolve_scope()` decoupled from HTTP context for unit testing | Story 24 | Not done | YES — blocks Story 24 |
| `Idempotency-Key` header handling on mutating endpoints | Story 19 | Not implemented | YES — blocks idempotency tests |
| MongoDB TTL collection for idempotency keys | Story 19 | Not implemented | Soft blocker |
| LLM mock/stub for `LLMClient` | Pre-Story 22 | Not implemented | YES — blocks AI dispatch tests |
| Log schema validation CI step | Story 4 | Not implemented | Soft blocker (go-live gate) |

### QA Infrastructure Setup

Before any tests can run:

```
# Backend test environment
pip install pytest httpx[asyncio] mongomock pytest-asyncio

# Frontend test environment  
cd frontend && yarn test  # uses craco test, not react-scripts test
```

**Motor mock pattern** (required for all backend tests):

```python
# tests/conftest.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.fixture
def mock_db():
    """Mock get_db() for all backend route tests."""
    db = MagicMock()
    db.students = AsyncMock()
    db.fee_transactions = AsyncMock()
    db.staff = AsyncMock()
    db.confirm_tokens = AsyncMock()
    # ... extend as needed per test module
    return db

@pytest.fixture
def auth_headers():
    """Pre-signed JWTs per role for route tests."""
    from backend.middleware.auth import create_access_token
    return {
        "owner": {"Authorization": f"Bearer {create_access_token({'role': 'owner', 'branch_id': 'aaryans-joya'})}"},
        "principal": {"Authorization": f"Bearer {create_access_token({'role': 'admin', 'sub_category': 'principal', 'branch_id': 'aaryans-joya'})}"},
        "accountant": {"Authorization": f"Bearer {create_access_token({'role': 'admin', 'sub_category': 'accountant', 'branch_id': 'aaryans-joya'})}"},
        "maintenance": {"Authorization": f"Bearer {create_access_token({'role': 'admin', 'sub_category': 'maintenance', 'branch_id': 'aaryans-joya'})}"},
        "it_tech": {"Authorization": f"Bearer {create_access_token({'role': 'admin', 'sub_category': 'it_tech', 'branch_id': 'aaryans-joya'})}"},
    }
```

**LLM mock pattern** (required for Story 22):

```python
# tests/mocks/llm_mock.py
from unittest.mock import AsyncMock

class MockLLMClient:
    async def chat(self, system_prompt, history, tools=None):
        # Simulate tool call response
        return {"tool_calls": [{"name": "assign_followup", "parameters": {...}}]}
    
    async def stream_chat(self, ...):
        yield {"type": "text", "text": "Mock response"}
        yield {"type": "done"}
```

---

## Risk Assessment

*Brief reference — full mitigation plans in Architecture doc (`test-design-architecture.md`).*

### High-Priority Risks (QA Test Coverage)

| Risk ID | Description | QA Test Coverage |
|---|---|---|
| R-001 | RBAC enforcement unverified | `tests/test_auth_matrix.py` — full role × endpoint matrix |
| R-002 | Confirm-action gate bypassable | `tests/test_ai_dispatch.py` — token expiry, replay, session binding |
| R-003 | S3 migration data loss | S3 integration test — write, read via pre-signed URL, checksum |
| R-004 | Student PII in LLM context | Code audit + log schema CI check; no automated test needed |
| R-005 | SSE timeout on CloudFront | Infrastructure verification, not automated test |
| R-006 | Fee idempotency not enforced | `tests/test_routes.py` — duplicate submission returns original |

### Medium/Low Priority Risks (QA Coverage)

| Risk ID | Description | QA Approach |
|---|---|---|
| R-007 | `.to_list(None)` unbounded queries | Static analysis / grep in CI |
| R-009 | Tool registry split (v1/v2) | Story 22 mocks verify dispatch reaches correct handler |
| R-010 | Vendor API unavailability | Graceful degradation test (Story 20 AC) |

---

## Test Coverage Plan

### P0 — Blocks Core Functionality, High Risk, No Workaround

**Criteria:** Fails → system is unsafe or inoperable; high-risk (score ≥ 6); no manual workaround exists.

| Test ID | Requirement | Test Level | Risk Link | Notes |
|---|---|---|---|---|
| T-001 | RBAC: All 9 roles denied on non-permitted endpoints | API | R-001 | `test_auth_matrix.py`; pre-signed JWT per role |
| T-002 | RBAC: Maintenance Admin cannot read `tech_request` records | API | R-001 | 403 on `GET /api/issues/tech` |
| T-003 | RBAC: IT/Tech cannot read `facility_request` records | API | R-001 | 403 on `GET /api/issues/facility` |
| T-004 | RBAC: Principal cannot read fee financial aggregates | API | R-001 | 403 on `GET /api/fees/summary` for principal role |
| T-005 | Confirm-action: AI write mutation does NOT execute without confirmation token | API | R-002 | `test_ai_dispatch.py`; assert no DB write before token confirmed |
| T-006 | Confirm-action: Expired token (>5 min) is rejected | API | R-002 | Force-expire token; confirm rejection |
| T-007 | Confirm-action: Cross-session token replay rejected (401) | API | R-002 | Issue token in session A; replay in session B |
| T-008 | Confirm-action: Token atomic `used: true` prevents double-execution | API | R-002 | Submit same valid token twice; second returns original |
| T-009 | Fee idempotency: Duplicate `Idempotency-Key` returns original record | API | R-006 | POST same fee twice; assert single DB record |
| T-010 | Fee record: Hard delete attempt returns 405 | API | DATA | Verify `DELETE /api/fees/transactions/:id` is rejected |
| T-011 | Auth: Unauthenticated request to any protected route returns 401 | API | SEC | No `Authorization` header → 401 |
| T-012 | AI graceful degradation: Tool panels respond when LLM is unavailable | API | R-010 | Mock LLM timeout; assert tool endpoints return correctly |
| T-013 | S3: File upload writes to S3 and not local disk | Integration | R-003 | Mock S3; assert `boto3.put_object` called, no local file write |
| T-014 | S3: Pre-signed URL is returned for file reads, not raw S3 key | API | SEC | Assert response URL contains `X-Amz-Signature` |
| T-015 | Scope resolver: Owner → no filter applied | Unit | R-001 | `resolve_scope({'role': 'owner'})` returns empty filter |
| T-016 | Scope resolver: Student → `{user_id: X}` filter only | Unit | R-001 | Deny-by-default verified |
| T-017 | Scope resolver: Unknown role → self-only scope (deny-by-default) | Unit | R-001 | Unrecognised sub_category falls to self |

### P1 — Critical Paths, Medium-High Risk, Common Workflows

**Criteria:** Core user journey is broken or degraded; medium-risk (score 3–5); daily workflows affected.

| Test ID | Requirement | Test Level | Risk Link | Notes |
|---|---|---|---|---|
| T-018 | Student CRUD: Create, read, update, deactivate (happy path) | API | — | `test_routes.py` |
| T-019 | Student: Deactivated student absent from default list | API | — | `?include_inactive=true` returns it |
| T-020 | Student: DPDP erasure requires Owner role + reason field | API | SEC | Verify 403 for non-owner; 422 if reason missing |
| T-021 | Staff CRUD: Create, read, update, deactivate | API | — | Deactivation invalidates sessions (Story 2) |
| T-022 | Fee payment: Record with all required fields (happy path) | API | — | `POST /api/fees/transactions` |
| T-023 | Fee payment: Correction requires mandatory reason; original preserved | API | DATA | `PATCH .../correct` without reason → 422 |
| T-024 | Discount: Multiple discounts stack correctly on student profile | Unit | DATA | Full breakdown: original → each discount → payable |
| T-025 | Discount: No black-box total — individual discount lines are in response | API | DATA | Assert `discounts[]` array in response |
| T-026 | Attendance: Correction preserves original; reason required | API | DATA | `PATCH /api/attendance/:id/correct` |
| T-027 | Attendance: Hard delete returns 405 | API | DATA | `DELETE /api/attendance/:id` → 405 |
| T-028 | Leave request: Approved leave reflected in substitution availability | API | — | `GET /api/academics/timetable?teacher_id` excludes approved-leave day |
| T-029 | Approval request: Routed correctly to Owner / Owner+Principal | API | — | `routing: owner_and_principal` appears in both dashboards |
| T-030 | Approval request: Reject requires mandatory reason | API | — | 422 if reason missing |
| T-031 | Maintenance: Request lifecycle open → in_progress → pending_owner_confirmation | API | — | `POST` then two `PATCH` state transitions |
| T-032 | Maintenance: Only Owner can close a facility request | API | R-001 | Maintenance Admin `POST /confirm-resolution` → 403 |
| T-033 | Notifications: High-severity incident triggers notification to Owner + Principal | API | — | Mock notification dispatch; verify recipients |
| T-034 | Announcements: User only sees announcements matching their role group | API | — | Verify `target_roles` filter in `GET /api/operations/announcements` |
| T-035 | Token service: Monthly limit enforced before LLM call | Unit | — | Admin at 100,001 tokens → rejected |
| T-036 | Token service: Graceful fallback when no balance document | Unit | — | Missing doc → unlimited (dev safety net) |
| T-037 | Auth: Refresh token flow — 401 on expired access token → refresh succeeds | API | SEC | Story 2 |
| T-038 | Auth: Deactivated user's refresh token returns 401 | API | SEC | Session invalidation verified |
| T-039 | SSE: `done` event is always last event in stream | API | TECH | Assert `done` type appears and no events follow |
| T-040 | SSE: LLM timeout emits `ai_unavailable` event, not generic error | API | R-010 | Mock LLM timeout; assert SSE event type |
| T-041 | Transport: Student assigned to zone; roster shows correct zone | API | — | Assignment + roster query |
| T-042 | Issue tracker: Category selector routes to correct namespace | API | — | `tech` or `facility` based on intake category |
| T-043 | Timetable: Bulk import validates referential integrity before commit | API | DATA | Invalid class_id in payload → 422, no partial commit |
| T-044 | Timetable: Conflicting teacher period rejected | API | — | Same teacher, same period, same day → 409 |
| T-045 | Incident thread: Entries in reverse-chronological order | API | — | Oldest entry last in response |
| T-046 | AI dispatch: All 9 write dispatches emit `confirm` SSE event before mutation | API | R-002 | Mock LLM; assert `confirm` event type before DB write |
| T-047 | AI dispatch: All 8 query dispatches return data without confirm-action | API | — | Read tools execute directly |
| T-048 | AI dispatch audit log: Every executed mutation is recorded | API | — | Assert `ai_dispatch_audit_log` insert after execution |
| T-049 | Max tool rounds: 3-round cap fires; does not loop indefinitely | Unit | TECH | Mock LLM to always return tool calls; assert stop at 3 |

### P2 — Secondary Flows, Low-Medium Risk, Edge Cases

**Criteria:** Individual feature degraded; low-risk (score 1–2); has workaround or is edge case.

| Test ID | Requirement | Test Level | Risk Link | Notes |
|---|---|---|---|---|
| T-050 | Student list: Pagination ≤ 20/page enforced | API | — | `GET /api/students?page=1&limit=21` → only 20 returned |
| T-051 | Student list: Sort by name and class options work | API | — | `?sort=name` returns ascending |
| T-052 | Fee: Overdue filter works correctly | API | — | `?overdue_days=30` returns only qualifying records |
| T-053 | Fee: Contact log created with all required fields | API | — | `POST /api/fees/contact-log` |
| T-054 | Fee summary: Discount impact summary returns aggregate totals | API | — | `GET /api/fees/discount-summary` |
| T-055 | Transport: Vehicle capacity stored correctly | API | — | CRUD on vehicle record |
| T-056 | Announcements: Pagination ≤ 20/page | API | — | |
| T-057 | Visitor log: Entry with all fields (name, purpose, outcome) | API | — | `POST /api/operations/visitors` |
| T-058 | Incident search: Full-text search across description | API | — | `?search=canteen` returns matching records |
| T-059 | Health endpoint: Returns correct per-component status | API | — | `GET /api/health/ready` happy path |
| T-060 | Health endpoint: AI degraded → overall still `ready` | API | — | Mock AI timeout; assert `{ ai: "degraded", overall: "ready" }` |
| T-061 | File upload: Files > 10MB are rejected with clear error | API | — | `413` or `422` response |
| T-062 | File upload: S3 checksum verified on successful upload | Integration | R-003 | Assert ETag comparison |
| T-063 | Audit log: PATCH on student returns previous + new value + changed_by | API | DATA | Compare before/after in log collection |
| T-064 | `schoolId` backfill: All documents contain `schoolId` field | Integration | — | Query each collection; assert field present |
| T-065 | Timetable: `GET ?teacher_id=X&date=Y` returns correct periods | API | — | Substitution availability query |
| T-066 | Notifications: Unread count decrements after mark-as-read | API | — | `PATCH .../read` then `GET .../unread-count` |
| T-067 | Content filter: Student-role AI response does not contain another student's data | Unit | SEC | Phase 2 partial — verify `filter_response()` for student role |
| T-068 | Log schema: Log entries do not contain PII field names | CI check | R-004 | Grep or programmatic field name check |

### P3 — Nice-to-Have, Exploratory, Benchmarks

**Criteria:** Non-blocking; benchmarks or coverage enhancement.

| Test ID | Requirement | Test Level | Notes |
|---|---|---|---|
| T-069 | Performance: p95 ≤ 500ms on standard data operations | Benchmark | Manual k6 test against staging |
| T-070 | Performance: Tool panel initial load ≤ 3s on simulated 4G | Benchmark | Lighthouse or manual measurement |
| T-071 | Mobile: 375px viewport renders without horizontal scroll (Owner dashboard) | Manual | iOS Safari + Android Chrome |
| T-072 | Mobile: Touch targets ≥ 44×44px on all Owner/Principal views | Manual | Chrome DevTools device emulation |
| T-073 | Mobile: Chat input stays visible when keyboard is open (iOS Safari) | Manual | Test on real device |
| T-074 | SSE keepalive: Server emits keepalive event every 30s | API | Assert `keepalive` event type in stream |
| T-075 | Theme: No hardcoded hex colours in tool panel `.js` files | Static analysis | Grep for `#[0-9a-fA-F]{3,6}` |
| T-076 | Theme: All panels render correctly in light + dark mode | Manual | Visual spot-check all panels |
| T-077 | Accessibility: Colour contrast ≥ 4.5:1 for body text | Manual | Colour contrast checker |
| T-078 | Biometric API unavailable: Last-updated indicator shown; channel stays open | API | Mock biometric timeout |

---

## Execution Strategy

**Philosophy:** Run everything on every PR. Playwright parallelizes 100s of tests to 10–15 minutes. Only defer suites that are structurally expensive (external services, long-running ops).

### Every PR (~10–15 min)

**Playwright / pytest / craco test:**
- All P0 and P1 backend tests (pytest + httpx, mocked DB + LLM)
- Authorization matrix (`test_auth_matrix.py`)
- AI dispatch tests (`test_ai_dispatch.py`)
- Core route tests (`test_routes.py`)
- Scope resolver unit tests (`test_scope_resolver.py`)
- Token service unit tests (`test_token_service.py`)
- All P2 API tests
- Frontend smoke tests via `craco test`

**CI gate:** All P0 tests must pass at 100%. P1 at ≥ 95%. Any failure blocks merge.

### Nightly (~30–60 min)

**Performance benchmarks (k6):**
- p95 ≤ 500ms on standard data operations (T-069)
- Tool panel load time (T-070)

**Static analysis:**
- Grep for `.to_list(None)` (R-007)
- Grep for hardcoded hex colours (T-075)
- Log schema PII field name check (T-068 / AI-03)

### Weekly / Pre-Release

**Manual test pass:**
- Mobile responsiveness (T-071, T-072, T-073)
- Theme coherence in light + dark mode (T-076)
- Accessibility spot-check (T-077)
- Full manual smoke of all 9 role journeys
- SSE keepalive and reconnect on mobile (T-074, Story 28 AC)

---

## QA Effort Estimate

QA effort only (test authorship + infrastructure setup). Excludes DevOps, backend implementation, and legal.

| Priority | Scope | Estimate |
|---|---|---|
| P0 (17 tests) | Auth matrix, confirm-action, scope resolver, S3, idempotency | ~3–5 weeks |
| P1 (32 tests) | CRUD coverage, AI dispatch, SSE, business flows | ~4–7 weeks |
| P2 (19 tests) | Edge cases, audit trails, health checks | ~2–4 weeks |
| P3 (10 items) | Benchmarks, manual checks, static analysis | ~1–2 weeks |
| Test infrastructure setup | `conftest.py`, mocks, CI integration | ~1–2 weeks |
| **Total QA effort** | | **~11–20 weeks** |

*Range reflects uncertainty in mock library selection, LLM stub complexity, and iteration on authorization matrix coverage.*

*Timeline assumes one part-time QA contributor alongside the solo implementer. Compresses significantly if QA and implementation overlap by phase.*

---

## Implementation Planning Handoff

| Task | Owner | Target Phase |
|---|---|---|
| Select and configure `mongomock` / `motor-mock` | Backend | Before Phase 5 (Story 21) |
| Write `LLMClient` mock/stub | Backend | Before Phase 4 (Story 22) |
| Decouple `resolve_scope()` from HTTP context | Backend | Phase 5 (Story 24) |
| Write `tests/conftest.py` with auth fixture | QA | Phase 5 (first) |
| Implement `confirm_tokens` collection + TTL | Backend | Phase 4 (Story 18) |
| Add `Idempotency-Key` handling to all mutating endpoints | Backend | Phase 4 (Story 19) |
| Add log schema PII CI check | DevOps/Backend | Phase 1 (Story 4) |
| Authorization matrix test suite | QA | Phase 5 (Story 21) |
| AI dispatch test suite | QA | Phase 5 (Story 22) |
| Core route tests | QA | Phase 5 (Story 23) |
| Scope resolver unit tests | QA | Phase 5 (Story 24) |

---

## Appendix A: Code Examples & Tagging

### `data-testid` Convention

All interactive elements in React components must include `data-testid` attributes (per project-context.md design system rules):

```jsx
// Example: ConfirmActionCard.js
<button data-testid="confirm-action-submit" onClick={handleConfirm}>Confirm</button>
<button data-testid="confirm-action-cancel" onClick={handleCancel}>Cancel</button>

// Example: FeeCollection.js
<input data-testid="fee-amount-input" ... />
<button data-testid="fee-submit-button" ... />
```

### Sample Authorization Matrix Test Shape

```python
# tests/test_auth_matrix.py
import pytest
from httpx import AsyncClient

SENSITIVE_ENDPOINTS = [
    ("/api/fees/summary", "GET"),
    ("/api/fees/transactions", "POST"),
    ("/api/issues/tech", "GET"),
    ("/api/issues/facility", "GET"),
    ("/api/students", "POST"),
]

ROLE_PERMISSIONS = {
    "owner": ["/api/fees/summary", "/api/fees/transactions", "/api/issues/tech", "/api/issues/facility", "/api/students"],
    "accountant": ["/api/fees/summary", "/api/fees/transactions"],
    "maintenance": [],  # cannot read tech
    "it_tech": [],      # cannot read facility
    "principal": ["/api/students"],
}

@pytest.mark.asyncio
async def test_maintenance_cannot_read_tech_requests(test_app, auth_headers):
    async with AsyncClient(app=test_app, base_url="http://test") as client:
        response = await client.get("/api/issues/tech", headers=auth_headers["maintenance"])
    assert response.status_code == 403
```

### Sample AI Dispatch Test Shape

```python
# tests/test_ai_dispatch.py
@pytest.mark.asyncio
async def test_write_dispatch_does_not_execute_without_confirmation(test_app, auth_headers, mock_llm):
    """Verify no DB mutation occurs when confirm-action step is pending."""
    mock_llm.return_value = {"tool_calls": [{"name": "assign_followup", "parameters": {...}}]}
    
    async with AsyncClient(app=test_app, base_url="http://test") as client:
        # Send message that triggers a write dispatch
        response = await client.post("/api/chat/conversations/test-id/messages",
                                     headers=auth_headers["owner"],
                                     json={"message": "Assign follow-up to Adesh"})
    
    # Assert confirm SSE event was emitted
    events = parse_sse_events(response.text)
    assert any(e["type"] == "confirm" for e in events)
    
    # Assert NO DB write occurred
    mock_db.assign_followup.assert_not_called()
```

---

## Appendix B: Knowledge Base References

- `risk-governance.md` — Risk classification framework applied in this document
- `probability-impact.md` — Probability × Impact scoring (1–3 scale)
- `test-levels-framework.md` — E2E / API / Component / Unit selection criteria
- `test-priorities-matrix.md` — P0–P3 priority assignment rules
- `adr-quality-readiness-checklist.md` — Architecture readiness gates
- `test-quality.md` — Anti-bloat and document quality standards
