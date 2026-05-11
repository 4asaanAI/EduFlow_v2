---
project: EduFlow Enterprise Upgrade
document: test-design-architecture
author: Master Test Architect (BMAD TEA)
date: 2026-05-12
mode: System-Level
status: complete
crossRef: test-design-qa.md
---

# Test Design — Architecture & Risk Document

**Purpose:** This document is the contract with the Architecture and Backend teams. It identifies architectural concerns, testability blockers, and risks that must be resolved before or during implementation. QA execution recipe is in `test-design-qa.md`.

---

## Executive Summary

EduFlow is a brownfield, chat-first school management SaaS with a React 19 frontend, FastAPI backend, Motor/MongoDB, Azure OpenAI, and AWS S3. The upgrade scope is an enterprise quality hardening: full CRUD, S3 migration, auth hardening, a new Maintenance Admin profile, AI dispatch table, fee idempotency, and a test baseline starting from zero.

**Architecture decision highlights:**
- SSE (not WebSocket) for AI streaming — unidirectional, ALB-compatible
- Scope resolver as a separate policy layer — correct but currently untested
- Confirm-action gate for all AI write operations — correct pattern, currently unenforceable without token hardening
- UUID4 string IDs throughout — clean, but no ObjectId exposure risk

**Risk summary:** 4 high-priority risks (score ≥ 6). Two are security-critical (RBAC enforcement unverified, confirm-action bypass). One is data-integrity-critical (S3 migration). One is compliance-critical (DPDP PII in LLM context).

---

## Quick Guide

### 🚨 BLOCKERS — Team Must Decide (Pre-Implementation Critical Path)

| # | Blocker | Owner | Decision Needed By |
|---|---|---|---|
| B1 | Confirmation token store: MongoDB TTL collection or Redis? TTL-capable backend is an explicit NFR — must be chosen before Story 18 begins | Backend/Arch | Before Phase 4 |
| B2 | MongoDB replica-set topology: Atlas free tier is a single node. The 99.5% availability NFR cannot be met without replica-set. Must confirm Atlas tier before go-live | DevOps/Infra | Before Phase 1 go-live |
| B3 | Azure OpenAI DPA for India data residency: Student PII records loaded from Day 1. Legal gate — must be signed before go-live | Legal/Ops (Abhimanyu) | Before go-live |
| B4 | SSE timeout on AWS Amplify CloudFront: Default CloudFront timeout terminates SSE connections. PRD explicitly flags this. Must configure CloudFront behaviour-level override or ALB placement before go-live | DevOps/Infra | Before Phase 5 (Story 28) |

### ⚠️ HIGH PRIORITY — Team Should Validate

| # | Concern | Owner | Timeline |
|---|---|---|---|
| H1 | `branch_id` filter missing from scope resolver tests — queries without it pass on single-tenant data but are a RBAC hole in multi-tenant mode | Backend | Phase 5 (Story 24) |
| H2 | No test coverage on `resolve_scope()` means RBAC policy correctness is unverifiable — authorization matrix cannot be valid until scope resolver is unit-tested first | Backend/QA | Phase 5 (Stories 24 → 21) |
| H3 | `tool_functions.py` + `tool_functions_v2.py` split: tools may be double-registered or silently skipped. Consolidation gap creates test surface ambiguity | Backend | Phase 4 (Story 18) |
| H4 | `JWT_SECRET` weak fallback allows accidental production deployment with dev key if env check fails | Backend/DevOps | Phase 1 (Story 2) |

### 📋 INFO ONLY — Solutions Provided

| # | Item | Solution |
|---|---|---|
| I1 | Ephemeral disk for uploads — data loss on redeploy | Story 1 migrates to S3; boto3 already installed |
| I2 | No refresh token currently | Story 2 adds refresh tokens with `httpOnly` cookie storage |
| I3 | `schoolId` missing from existing records | Story 3 migration backfills all collections idempotently |
| I4 | 7-day JWT expiry is too long for the security NFR | Story 2 reduces to 1-hour access token |

---

## Risk Assessment

> Risk Score = Probability × Impact. Score ≥ 6 is high-priority.

### High-Priority Risks (Score ≥ 6)

| Risk ID | Category | Description | P | I | Score | Mitigation | Owner | Timeline |
|---|---|---|---|---|---|---|---|---|
| R-001 | SEC | RBAC enforcement at API layer unverified — no test suite exists. A teacher could query fee records or a Maintenance Admin could read tech requests without being caught | 3 | 3 | **9** | Authorization matrix test suite (Story 21) covering all 9 roles × all sensitive endpoints before go-live | Backend/QA | Phase 5 |
| R-002 | SEC | Confirm-action gate can be replayed or bypassed without token hardening — current implementation has no TTL, single-use enforcement, or session binding on confirmation tokens | 3 | 3 | **9** | Story 18 (AI dispatch) + Story 19 (token hardening): UUID4 tokens, 5-min TTL, `used: true` atomic flag, session binding | Backend | Phase 4 |
| R-003 | DATA | S3 migration — existing files on ephemeral disk will be lost if Elastic Beanstalk instance is replaced before migration runs | 3 | 2 | **6** | Story 1: migration script against prod data copy first; idempotent; rollback documented. Run before any deployment | Backend/DevOps | Phase 1 (first) |
| R-004 | SEC | Student PII sent to Azure OpenAI without confirmed DPA for India data residency — student records load from Day 1 | 2 | 3 | **6** | Legal gate B3: DPA must be signed before go-live. AI queries must use anonymised context / ID references, not raw PII. Verify in `build_school_context()` | Backend/Legal | Pre go-live |

### Medium-Priority Risks (Score 3–5)

| Risk ID | Category | Description | P | I | Score | Mitigation |
|---|---|---|---|---|---|---|
| R-005 | TECH | SSE connection termination by CloudFront default timeout breaks live attendance and fee summary streams | 3 | 2 | 6* | Infrastructure fix (B4): CloudFront behaviour override or ALB before Story 28 |
| R-006 | DATA | Fee idempotency not enforced — double-tap or network retry creates duplicate payment records | 2 | 3 | 6* | Story 8 + Story 19: `Idempotency-Key` header enforced server-side with 24h TTL |
| R-007 | PERF | `motor .to_list(None)` on unbounded collections — already flagged in project-context.md anti-patterns. SSE streams + large student datasets could exhaust memory | 2 | 2 | 4 | Code review gate: grep codebase for `.to_list(None)` before Phase 4; enforce explicit limits |
| R-008 | OPS | Single implementer (Abhimanyu) — illness or overload delays go-live with no fallback | 2 | 2 | 4 | Scope is bounded. No scope creep. Growth features explicitly deferred |
| R-009 | TECH | `tool_functions.py` + `tool_functions_v2.py` split — tools registered in both files may produce inconsistent dispatch behaviour | 2 | 2 | 4 | Consolidate into single registry in Story 18; mock-verified in Story 22 |
| R-010 | BUS | Biometric and fee software integrations are vendor-dependent — if APIs are unavailable at go-live, Accountant and Principal journeys are degraded | 2 | 2 | 4 | Platform goes live without them; manual fallbacks defined in PRD |

### Low-Priority Risks (Score 1–2)

| Risk ID | Category | Description | P | I | Score |
|---|---|---|---|---|---|
| R-011 | TECH | No refresh token — re-login every 7 days (currently). Story 2 addresses this | 1 | 1 | 1 |
| R-012 | PERF | AI write rate limiting (no per-session throttle) — Phase 1 known gap, acceptable for controlled single-school pilot | 1 | 2 | 2 |
| R-013 | OPS | Announcement moderation not implemented — unmoderated Receptionist content. Acceptable pre-teacher/student go-live | 1 | 1 | 1 |

*R-005 and R-006 score 6 but are infrastructurally/technically addressable — distinguished from the pure security risks R-001/R-002.

**Risk Category Legend:** TECH = Architecture/Integration | SEC = Security | PERF = Performance/Scalability | DATA = Data Integrity | BUS = Business/Revenue | OPS = Deployment/Operational

---

## Testability Concerns and Architectural Gaps

### 🚨 ACTIONABLE CONCERNS

#### Blockers to Fast Feedback

| Concern | WHAT Architecture Must Provide | Owner | Timeline | Impact |
|---|---|---|---|---|
| TC-01: Zero test infrastructure | Tests/ directory exists but is empty. No mocking strategy defined. Motor must be mocked at `get_db()` — no factory pattern exists | Backend | Phase 1 (Story 4 parallel) | Blocks all automated testing |
| TC-02: LLM is live — no mock | `LLMClient` calls Azure OpenAI on every invocation. No mock/stub exists. Tests will be slow, non-deterministic, and costly without a mock layer | Backend | Before Phase 4 (Story 22) | Blocks AI dispatch tests |
| TC-03: Scope resolver not independently testable | `resolve_scope()` is coupled to the FastAPI request context. Unit tests need it decoupled to assert policy correctness without HTTP overhead | Backend | Phase 5 (Story 24) | Blocks RBAC verification |
| TC-04: `branch_id` filter gap | Single-tenant data does not catch missing `branch_id` filters. Tests pass on dev data but RBAC is incorrect in multi-tenant mode | Backend | Phase 5 (before Story 21) | Blocks authorization matrix validity |

#### Architectural Improvements Needed

| Improvement | WHAT Must Change | Owner | Timeline | Impact |
|---|---|---|---|---|
| AI-01: Confirmation token model is incomplete | `confirm_tokens` collection must be created with fields: `token`, `action`, `params`, `user_id`, `session_id`, `expires_at`, `used`. TTL index on `expires_at` is required | Backend | Phase 4 (Story 18) | R-002 |
| AI-02: Idempotency key enforcement is missing | No `Idempotency-Key` header handling on any mutating endpoint currently. All story-8+ endpoints need this pattern | Backend | Phase 4 (Story 19) | R-006 |
| AI-03: Log schema PII validation in CI | No CI step validates structured log output for PII field names. Required by NFR Security and Story 4 AC | DevOps/Backend | Phase 1 (Story 4) | R-004 |
| AI-04: `MAX_TOOL_ROUNDS=3` is not tested | Infinite LLM→tool→LLM loop is prevented only by the cap. Tests must verify the cap fires and does not silently succeed | Backend/QA | Phase 4 (Story 22) | TECH risk |

### Testability Assessment Summary

**What Works Well:**
- UUID4 string IDs throughout — clean JSON serialization, no ObjectId conversion needed in tests
- FastAPI with `httpx.AsyncClient` + `TestClient` is well-supported for async route testing
- `require_role()` FastAPI dependency pattern is consistent — easy to assert 403 paths
- SSE event schema is documented and typed — predictable assertions on `type` field
- `scope.filter()` produces a deterministic MongoDB filter — assertion-friendly
- Scope resolver is a pure function (once decoupled from HTTP context) — ideal for unit testing

**Accepted Trade-offs (No Action Required):**
- `fetch` native + `axios` split is deliberate (multipart handling) — no testability impact
- Pinned `date-fns` v3 — version lock prevents test breakage from upstream changes
- 4 Gunicorn workers are stateless — parallel test execution is safe

---

## Risk Mitigation Plans

### R-001: RBAC Enforcement Unverified (Score 9)

**Strategy:**
1. Implement Story 24 (scope resolver unit tests) first — verify policy before route-level matrix
2. Implement Story 21 (authorization matrix) covering 9 roles × all sensitive endpoints
3. Use `httpx.AsyncClient` with pre-signed JWTs per role — no live auth server needed
4. Mock `get_db()` using `mongomock` — no live MongoDB required
5. Add CI gate: matrix tests must pass before any deployment to production

**Owner:** Backend (implementation) / QA (test authorship)
**Timeline:** Phase 5 (before go-live)
**Status:** Not started
**Verification:** CI pipeline shows 100% pass on `tests/test_auth_matrix.py` before any deploy

---

### R-002: Confirm-Action Gate Bypassable (Score 9)

**Strategy:**
1. Create `confirm_tokens` MongoDB collection with TTL index on `expires_at` (5 min)
2. Implement `POST /api/chat/confirm` with atomic `used: true` flag set before execution
3. Bind token to `session_id` — reject cross-session replay with 401
4. Implement fail-closed: if token store is unreachable, all write operations reject (not fail-open)
5. Story 22 tests: verify mutation does NOT execute without token, verify expired token is rejected, verify cross-session replay is rejected

**Owner:** Backend
**Timeline:** Phase 4 (Story 18 + 19)
**Status:** Partial — confirm-action card exists in frontend; backend token enforcement not implemented
**Verification:** Story 22 test suite passes; `POST /api/chat/confirm` with expired token returns non-200 without side effects

---

### R-003: S3 Migration Data Loss (Score 6)

**Strategy:**
1. Write `backend/migrations/012_migrate_uploads_to_s3.py` as idempotent script
2. Run against a copy of production data — verify all URLs resolve before touching live data
3. After migration: all `routes/upload.py` writes go directly to S3 via `boto3`; no writes to local disk
4. All reads use time-limited pre-signed URLs (expiry ≤ 1 hour); bucket is not publicly readable
5. Rollback plan: keep local disk files until migration is verified on production; document rollback steps

**Owner:** Backend/DevOps
**Timeline:** Phase 1 (Story 1 — first story to implement)
**Status:** `boto3` installed and configured; `upload.py` still writes to disk
**Verification:** After migration, open each previously-uploaded file URL and confirm it resolves via S3 pre-signed URL

---

### R-004: Student PII in Azure OpenAI Context (Score 6)

**Strategy:**
1. Legal gate: Azure OpenAI DPA for India data residency signed before go-live (B3)
2. Audit `build_school_context()` in `backend/ai/`: ensure only IDs and non-PII aggregates are passed to LLM — no student names, contact numbers, fee amounts in LLM system prompt
3. Add structured log PII validation CI step (AI-03) to reject log entries containing PII field names
4. Document which fields are sent to Azure OpenAI in architecture spec

**Owner:** Backend (code audit) / Abhimanyu (legal gate)
**Timeline:** Before go-live (legal gate); Phase 1 (technical audit)
**Status:** Content filter exists for student role; LLM context builder not audited for PII
**Verification:** CI log schema check passes; DPA on record before student records are loaded

---

## Assumptions and Dependencies

**Architectural assumptions:**
1. MongoDB Atlas is on a replica-set tier (M10+) — required for 99.5% availability SLA (B2 must confirm)
2. Azure OpenAI India-region endpoint is available and DPA is obtainable (B3)
3. AWS Amplify CloudFront can have per-behaviour timeout overrides configured (B4)
4. Elastic Beanstalk instance has a stable `S3_BUCKET_NAME` env var before go-live
5. `SCHOOL_ID` env var is set to `"aaryans-joya"` in all environments from Story 3 onward
6. Biometric and fee software APIs will not be available at Phase 1 go-live — manual fallbacks are the deployment assumption

**Dependencies with required dates:**

| Dependency | Required By | Risk if Late |
|---|---|---|
| Azure OpenAI DPA signed (B3) | Before go-live | Student records cannot be loaded; legal exposure |
| Atlas replica-set tier confirmed (B2) | Before Phase 5 | 99.5% SLA unachievable |
| CloudFront SSE timeout override (B4) | Before Story 28 | SSE channels break after default timeout |
| `mongomock` or `motor-mock` selected | Before Story 21 | Authorization matrix tests cannot run without DB mock |

**Risks to plan:**

| Risk | Impact | Contingency |
|---|---|---|
| Azure DPA cannot be obtained in time | Go-live delayed or student records deferred | Load staff/admin records only; student data loaded post-DPA |
| Atlas free tier is not replica-set capable | Story 28 SSE SLA fails | Upgrade Atlas tier; cost ~$57/month for M10 |
| CloudFront override not available on Amplify hosting tier | SSE streams unreliable | Place ALB in front of Amplify origin (adds infrastructure cost) |
