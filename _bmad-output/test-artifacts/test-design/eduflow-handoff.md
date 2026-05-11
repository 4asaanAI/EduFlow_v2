---
project: EduFlow Enterprise Upgrade
document: tea-bmad-handoff
author: Master Test Architect (BMAD TEA)
date: 2026-05-12
mode: System-Level
sourceWorkflow: bmad-testarch-test-design
targetWorkflow: create-epics-and-stories / atdd / automate
status: complete
---

# TEA → BMAD Handoff Document — EduFlow Enterprise Upgrade

**Purpose:** This document is designed for consumption by BMAD's `create-epics-and-stories`, `atdd`, and `automate` workflows. It provides a structured bridge between the system-level test design and epic/story-level implementation, mapping risks to stories and identifying where P0 tests must be written.

---

## TEA Artifacts Inventory

| Artifact | Path | Contents |
|---|---|---|
| Architecture & Risk Document | `_bmad-output/test-artifacts/test-design-architecture.md` | Architectural concerns, testability gaps, risk assessment, mitigation plans, pre-implementation blockers |
| QA Execution Recipe | `_bmad-output/test-artifacts/test-design-qa.md` | Test coverage plan (P0–P3), execution strategy, dependencies, effort estimates |
| This Handoff Document | `_bmad-output/test-artifacts/test-design/eduflow-handoff.md` | TEA → BMAD integration guidance |
| Stories | `_bmad-output/implementation-artifacts/stories.md` | 28 stories across 5 phases |
| PRD | `_bmad-output/planning-artifacts/prd.md` | 95 functional requirements, NFRs, user journeys |
| Architecture | `_bmad-output/planning-artifacts/architecture.md` | Tech decisions, ADRs, open gaps |

---

## Pre-Implementation Blockers (Must Resolve Before Implementation Starts)

These blockers from `test-design-architecture.md` must be resolved before the stories that depend on them begin. BMAD story scheduling must account for them.

| Blocker ID | Blocker | Blocks Story | Owner | Action |
|---|---|---|---|---|
| B1 | Confirmation token store: MongoDB TTL or Redis? | Story 18 (Phase 4) | Backend/Arch | Decide before Phase 4 starts |
| B2 | MongoDB Atlas replica-set tier confirmation | Story 28 (Phase 5) + go-live | DevOps | Confirm Atlas tier before Phase 5 |
| B3 | Azure OpenAI India DPA signed | Go-live (all phases) | Abhimanyu/Legal | Must be resolved before student records load |
| B4 | AWS CloudFront SSE timeout override | Story 28 (Phase 5) | DevOps | Configure before Story 28 implementation |

---

## Epic-Level Integration Guidance

When creating epics for BMAD story decomposition, apply the following P0/P1 risk guidance to epic acceptance criteria.

### P0 Risks — Must Be Epics With Mandatory Test Gates

| Risk ID | Risk | Linked Stories | Epic-Level AC Requirement |
|---|---|---|---|
| R-001 | RBAC enforcement unverified | Story 21 (auth matrix), Story 24 (scope resolver) | Authorization matrix test suite MUST pass in CI before any story in Phase 3+ is marked complete |
| R-002 | Confirm-action gate bypassable | Story 18 (AI dispatch), Story 19 (token hardening) | No AI write dispatch ships without token TTL, session binding, and `used: true` atomic flag |
| R-003 | S3 migration data loss | Story 1 | S3 migration MUST be tested on a prod data copy before running on live; rollback plan documented |
| R-004 | PII in LLM context | Story 4 (log schema CI), pre-go-live audit | `build_school_context()` must be audited for PII before student records load |

### P1 Risks — Epics Should Track as High Priority

| Risk ID | Risk | Linked Stories | Guidance |
|---|---|---|---|
| R-005 | SSE CloudFront timeout | Story 28 | Infrastructure setup is a dependency before Story 28 begins |
| R-006 | Fee idempotency | Story 8, Story 19 | `Idempotency-Key` header must be enforced in Story 8; Story 19 hardens all endpoints |
| R-007 | `.to_list(None)` unbounded | All DB-heavy stories | Add grep check in CI; flag in code review |
| H2 | Scope resolver not unit-tested | Story 24 before Story 21 | Story 24 must be completed before Story 21 authorization matrix tests are valid |

---

## Story-Level Integration Guidance

Critical test scenarios (from `test-design-qa.md`) that must be written as part of the story's definition of done.

### Phase 1 Stories — Test Requirements

| Story | Story Title | P0 Tests Required | P1 Tests Required |
|---|---|---|---|
| Story 1 | S3-Backed File Storage Migration | T-013 (S3 write), T-014 (pre-signed URL) | T-061 (10MB limit), T-062 (checksum) |
| Story 2 | Auth Hardening | T-011 (unauthenticated → 401), T-037 (refresh flow), T-038 (deactivated user → 401) | — |
| Story 3 | `schoolId` Backfill | — | T-064 (all docs have `schoolId`) |
| Story 4 | Health Endpoint + Logging | — | T-059, T-060 (health endpoint), T-068 (log PII check) |

### Phase 2 Stories — Test Requirements

| Story | Story Title | P0 Tests Required | P1 Tests Required |
|---|---|---|---|
| Story 5 | Student Profile CRUD | T-001 (RBAC), T-020 (DPDP erasure) | T-018, T-019 (CRUD + pagination) |
| Story 6 | Staff Profile CRUD | T-001 (RBAC) | T-021 (CRUD + session invalidation) |
| Story 7 | Attendance Correction | T-027 (hard delete → 405) | T-026 (correction + reason) |
| Story 8 | Fee Management CRUD | T-009 (idempotency), T-010 (hard delete → 405) | T-022, T-023 (CRUD + correction) |
| Story 9 | Discount Policy Engine | — | T-024, T-025 (discount stacking + breakdown) |
| Story 10 | Leave + Approvals | — | T-028, T-029, T-030 (leave/approval workflows) |

### Phase 3 Stories — Test Requirements

| Story | Story Title | P0 Tests Required | P1 Tests Required |
|---|---|---|---|
| Story 11 | Maintenance Admin Profile | T-002 (Maintenance cannot read tech), T-032 (only Owner closes) | T-031 (request lifecycle) |
| Story 12 | IT/Tech Issue Tracker | T-003 (IT/Tech cannot read facility) | T-042 (category routing) |
| Story 13 | Incident & Visitor Management | — | T-033 (high-severity notification), T-045 (thread order) |
| Story 14 | Announcements | — | T-034 (role-targeted filtering) |
| Story 15 | Transport Management | — | T-041 (zone assignment + roster) |
| Story 16 | In-App Notifications | — | T-033 (incident), T-066 (unread count) |
| Story 17 | Timetable Management | — | T-043 (referential integrity), T-044 (period conflict), T-065 (availability query) |

### Phase 4 Stories — Test Requirements

| Story | Story Title | P0 Tests Required | P1 Tests Required |
|---|---|---|---|
| Story 18 | AI Dispatch Table | T-005 (no mutation without token), T-006 (expired token), T-007 (cross-session replay), T-008 (atomic used flag) | T-046 (confirm SSE), T-047 (read dispatches), T-048 (audit log), T-049 (3-round cap) |
| Story 19 | Fee Idempotency + Token Hardening | T-009 (duplicate submission) | — |
| Story 20 | AI Graceful Degradation | T-012 (tool panels work without LLM) | T-040 (ai_unavailable SSE event) |

### Phase 5 Stories — Test Requirements

| Story | Story Title | Tests Written Here |
|---|---|---|
| Story 21 | Authorization Matrix Tests | T-001 through T-004 (full matrix) |
| Story 22 | AI Dispatch Tests | T-005 through T-008 + T-046 through T-049 |
| Story 23 | Core Route Tests | T-011, T-009, T-027, T-010 (core routes) |
| Story 24 | Scope Resolver Unit Tests | T-015, T-016, T-017 |
| Story 25 | UX States | Manual verification in Definition of Done |
| Story 26 | Theme Coherence | T-075 (static analysis), T-076 (manual) |
| Story 27 | Mobile Responsiveness | T-071, T-072, T-073 (manual) |
| Story 28 | SSE Real-Time | T-039 (done event), T-074 (keepalive), T-078 (graceful degradation) |

---

## Risk-to-Story Mapping Table

Full mapping of test-design risks to implementation stories.

| Risk ID | Category | Score | Stories | Phase | Status |
|---|---|---|---|---|---|
| R-001 | SEC | 9 | Story 21, Story 24 | Phase 5 | Not started |
| R-002 | SEC | 9 | Story 18, Story 19 | Phase 4 | Not started |
| R-003 | DATA | 6 | Story 1 | Phase 1 | Not started |
| R-004 | SEC | 6 | Story 4 (CI gate) | Phase 1 | Not started |
| R-005 | TECH | 6* | Story 28 (infra dep) | Phase 5 | Infra pending |
| R-006 | DATA | 6* | Story 8, Story 19 | Phase 2+4 | Not started |
| R-007 | PERF | 4 | All DB stories | All phases | Ongoing |
| R-008 | OPS | 4 | N/A (non-technical) | — | Monitor |
| R-009 | TECH | 4 | Story 18 | Phase 4 | Not started |
| R-010 | BUS | 4 | Story 20 | Phase 4 | Not started |
| R-011 | TECH | 1 | Story 2 | Phase 1 | Not started |
| R-012 | OPS | 2 | Growth Phase | Phase 2 | Documented gap |
| R-013 | OPS | 1 | Growth Phase | Phase 2 | Documented gap |

---

## Recommended Workflow Sequence

After this handoff document, the recommended BMAD workflow sequence is:

1. **Now → `atdd` workflow** — Generate P0 test cases (T-001 to T-017) from the P0 scenarios in `test-design-qa.md`. P0 tests should be written before Phase 4 implementation begins.

2. **Phase 1 parallel → `framework` workflow** — Set up pytest infrastructure (`conftest.py`, mock fixtures, CI integration) in parallel with Phase 1 story implementation.

3. **Phase 4 parallel → `automate` workflow** — Automate P1 test cases for AI dispatch and fee idempotency as those stories complete.

4. **Phase 5 → Story 21, 22, 23, 24** — Run authorization matrix and dispatch tests; these stories ARE the test baseline.

5. **Pre-go-live → `gate` workflow** — Use the quality gate criteria below.

---

## Phase Transition Quality Gates

### Gate: Phase 1 → Phase 2

- [ ] S3 migration tested on prod data copy; rollback plan documented
- [ ] JWT access token expiry ≤ 1 hour; refresh token flow works
- [ ] `schoolId` backfill migration run; all collections have field
- [ ] `/api/health/ready` endpoint returns correct per-component status
- [ ] Log schema CI check rejects PII field names
- [ ] Azure OpenAI DPA review initiated (B3)

### Gate: Phase 2 → Phase 3

- [ ] All CRUD endpoints for Student, Staff, Attendance, Fee, Discount, Leave, Approvals are complete
- [ ] Fee idempotency enforced on `POST /api/fees/transactions`
- [ ] Attendance and fee records return 405 on DELETE attempts
- [ ] `mongomock` / `motor-mock` selected and `conftest.py` written

### Gate: Phase 3 → Phase 4

- [ ] Maintenance Admin profile fully operational (role, data model, tool panel, RBAC)
- [ ] Namespace isolation enforced: IT/Tech cannot read facility records and vice versa
- [ ] In-app notifications working for high-severity incidents and approval decisions
- [ ] LLM mock/stub implemented for AI dispatch tests

### Gate: Phase 4 → Phase 5

- [ ] All 9 AI write dispatches emit `confirm` SSE event before mutation
- [ ] Confirmation tokens: TTL 5 min, single-use, session-bound, fail-closed
- [ ] `Idempotency-Key` accepted and honoured on all mutating endpoints
- [ ] AI graceful degradation: tool panels respond when LLM is unavailable

### Gate: Phase 5 → Go-Live

- [ ] `tests/test_auth_matrix.py` passes 100% in CI
- [ ] `tests/test_ai_dispatch.py` passes 100% in CI
- [ ] `tests/test_routes.py` passes 100% in CI
- [ ] `tests/test_scope_resolver.py` passes 100% in CI
- [ ] P0 tests (T-001 to T-017) all green
- [ ] P1 test pass rate ≥ 95%
- [ ] Azure OpenAI DPA signed and on record (B3)
- [ ] MongoDB Atlas replica-set tier confirmed (B2)
- [ ] CloudFront SSE timeout override configured (B4)
- [ ] All Owner and Principal views tested on iOS Safari + Android Chrome at 375px
- [ ] Manual smoke of all 9 role journeys completed
- [ ] Zero open P0/P1 bugs

---

## Open Assumptions Requiring Confirmation

| # | Assumption | Required From | Action |
|---|---|---|---|
| A1 | UDISE+ reporting is NOT mandatory for The Aaryans in Phase 1 | Aman (client) | Confirm before Phase 2 scope finalised; FR94 is conditional |
| A2 | Biometric and fee software APIs will NOT be available at go-live | Vendor | Confirm before Phase 1 ends; manual fallbacks are the default |
| A3 | MongoDB Atlas tier supports replica-set (M10+) | DevOps/Abhimanyu | Confirm ASAP — affects availability SLA and test infrastructure |
| A4 | Azure OpenAI India endpoint is available and DPA is obtainable | Microsoft/Legal | Confirm before student records load |
| A5 | `mongomock` is compatible with Motor 3.3.1 async operations | Backend | Spike/verify before Story 21 starts; `motor-mock` is the fallback |

---

*Handoff document generated by BMAD TEA workflow `bmad-testarch-test-design` on 2026-05-12.*
*Next action: Run `/atdd` workflow targeting P0 scenarios from `test-design-qa.md` sections T-001 through T-017.*
