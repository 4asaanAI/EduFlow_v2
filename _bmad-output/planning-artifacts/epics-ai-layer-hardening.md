---
stepsCompleted: ['step-01-validate-prerequisites', 'step-02-design-epics', 'step-03-create-stories', 'step-04-final-validation']
status: 'complete — awaiting Shubham review before implementation'
storyCount: 53
epicCount: 11
inputDocuments:
  - '_bmad-output/planning-artifacts/prd-ai-layer-hardening.md'
  - '_bmad-output/planning-artifacts/architecture-ai-layer-hardening.md'
  - '_bmad-output/planning-artifacts/implementation-readiness-report-ai-layer-hardening-2026-06-07.md'
  - '_bmad-output/project-context.md'
initiative: 'ai-layer-hardening'
---

# EduFlow AI Layer Hardening - Epic Breakdown

## Overview

This document decomposes the PRD (30 FRs / 25 NFRs) and Architecture (13 ADs / 8 patterns) for the AI Layer Hardening initiative into implementable, vertical-slice stories. Brownfield discipline: no new tools/UI, plan-then-confirm-once, Owner/Principal-first, preserve Part 2 invariants + the existing 699 backend tests. Epic sequence follows AD13: A → B → C → D.

## Requirements Inventory

### Functional Requirements

FR1–FR6 (Agentic Planning & Multi-Step Execution); FR7–FR12 (Confirmation & Atomic Write Safety); FR13–FR15 (Action–UI Data Parity); FR16–FR18 (Authorization & Multi-Tenant Scoping); FR19–FR23 (Data Protection & DPDP); FR24–FR26, FR30 (Safety Operations & Observability); FR27–FR29 (Role Coverage & Phased Rollout); FR31–FR36 (AI Self-Learning); **FR37–FR42 (CRUD Coverage — student/fee/academic/org/staff + destructive-action policy)**. _Full text in `prd-ai-layer-hardening.md`._

### NonFunctional Requirements

NFR1–NFR4 (Performance); NFR5–NFR9 (Security & Privacy); NFR10–NFR14, NFR21–NFR22 (Reliability & Data Integrity); NFR15–NFR17 (Compliance/DPDP; NFR17 residency DEFERRED); NFR18–NFR20, NFR23–NFR25 (Maintainability & Testability). _Full text in `prd-ai-layer-hardening.md`._

### Additional Requirements (from Architecture)

- AD7 shared service-layer write path `services/<domain>_service.py` (P1 signature); AD4 Motor txn + saga via `get_txn_session()` + `ScopedCollection` session forwarding; AD6 unique idempotency index in `_create_indexes()` + migration; AD3 plan+plan_hash+schema_version on `confirm_tokens.py`; AD12 real-Mongo replica-set test tier (`@pytest.mark.mongo_real`); AD9 kill-switch `db.system_flags.ai_writes_enabled` + dry-run; AD13 epic sequencing A→B→C→D.
- No starter template (brownfield); first story is characterization tests, not project init.

### UX Design Requirements

- UX-DR1: Multi-step plan confirm card — render N ordered steps under one Confirm/Cancel (`ConfirmActionCard.js`).
- UX-DR2: Partial-failure & `needs_manual_reconciliation` user messaging.
- UX-DR3: Disambiguation prompt UX within the chat flow.
- UX-DR4: UI deep-link fallback when the assistant can't complete a job (FR30).
- UX-DR5: 409 taxonomy messaging — `plan_tampered` ("re-confirm") vs `plan_stale` ("data changed — re-plan").

### FR Coverage Map

- **Epic A:** FR13, FR14, FR16, FR17, FR18, FR22, FR27, FR29 (parity for aligned domains)
- **Epic B:** FR13, FR14 (fees/discount/house-points parity) + found-defect fixes
- **Epic C:** FR13, FR14 (incident/complaint tools parity)
- **Epic D:** FR9, FR10, FR11, FR26
- **Epic E:** FR1, FR2, FR3, FR4, FR5, FR6, FR7, FR8, FR12, FR30
- **Epic F:** FR15, FR19, FR20, FR21, FR23, FR24, FR25
- **Epic F (also):** FR42 (destructive-action two-step + deletion audit — Story F.10)
- **Epic G:** FR31, FR32, FR33, FR34, FR35, FR36 (self-learning addendum)
- **Epic J:** FR37 (student create/update), FR41 (staff create/edit)
- **Epic K:** FR38 (fee config), FR39 (academic structure), FR40 (org config)
- **Epic H (Phase 2):** FR28 (+ all of A–K extended to other roles)

_Every FR1–FR42 mapped. NFRs are covered within the epic whose ADs they quantify (e.g., NFR10/11/21/22 in Epic D; NFR5–9 in Epic F; NFR18–19/23–25 across D/F). CRUD epics (J/K) reuse the same engine + DPDP + parity + audit; no new UI (they wrap existing REST capabilities)._

## Epic List

### Epic A: Trustworthy single-writer foundation — aligned domains
**Goal:** Every AI write for the low-divergence Owner/Principal domains (attendance, leave, approvals, announcement, contact-log, substitution, attendance-correction) goes through the **same service-layer code path as the UI**, so an AI action is identical to a panel action. Establishes the `services/<domain>_service.py` pattern, the `actor_ctx` contract, and the dual-entrypoint parity-test approach at low risk. Zero change to the REST/UI path; AI path corrected to match (case-by-case where a minor divergence exists).
**FRs covered:** FR13, FR14, FR16, FR17, FR18, FR22, FR27, FR29.

### Epic B: Parity + defect resolution — fees, discounts, house-points
**Goal:** Extract shared services for the three domains with **known divergences/defects**, deciding canonical behavior case-by-case and fixing the three found defects as part of extraction: (1) `record_fee_payment` idempotency + partial-payment + SSE parity; (2) `apply_discount` owner-approval-threshold (close the AI bypass); (3) `award_house_points` correct data model (`houses.points` + `house_points_log`) + audit. Includes a documented "Found Defects" resolution.
**FRs covered:** FR13, FR14 (for these domains) + defect fixes feeding NFR11, NFR15.

### Epic C: Parity — dynamic-collection incident/complaint tools
**Goal:** Extract shared services for `assign_followup`, `update_incident_status`, `add_thread_entry`, `confirm_resolution`, which route to `incidents`/`complaints`/`facility_requests`/`tech_requests` at runtime. Make the target collection explicit/declared so scoping, audit, and (later) transactions are deterministic.
**FRs covered:** FR13, FR14 (for these tools), FR16–FR18 reinforcement.

### Epic D: Safe execution — atomic, idempotent, never torn
**Goal:** A transactional executor wraps the now-shared services so AI writes are **all-or-nothing and never double-applied** (even single actions), with the saga fallback for non-Mongo side effects and the `needs_manual_reconciliation` state. Stands up the real-Mongo replica-set test tier (AD12) that proves it.
**FRs covered:** FR9, FR10, FR11, FR26. **NFRs:** NFR10, NFR11, NFR21, NFR22, NFR20, NFR23, NFR24.

### Epic E: Whole-job-by-instruction — agentic planner + plan-then-confirm-once
**Goal:** The headline value — a user states a compound task; the assistant plans it, shows **one** plan card, and on a single confirmation executes the whole thing atomically. Planner, plan-hash token, round-counter redefinition, server-side disambiguation, and the UI-deep-link fallback. Borrows Odysseus `ask_user`/plan-mode patterns; executor/atomicity remains EduFlow-custom.
**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR6, FR7, FR8, FR12, FR30. **NFRs:** NFR3, NFR9.

### Epic F: Compliant & operable — DPDP + safety-ops + parity harness
**Goal:** Make it safe to run live in a school: PII-minimized to the LLM, redacted traces/audit, audited minor-reads, kill-switch + shadow/dry-run, and the dual-entrypoint parity harness + CI drift gate that proves FR13–15 continuously.
**FRs covered:** FR15, FR19, FR20, FR21, FR23, FR24, FR25. **NFRs:** NFR5–NFR8, NFR13, NFR15, NFR16, NFR19, NFR25, NFR4.

### Epic G: AI self-learning (Memory + Skills) for Owner & Principal — cloned from Odysseus
**Goal:** The assistant adapts per profile owner — auto-saving important info, asking in-chat only when uncertain, with **no memory/skills UI**, and able to **recall & synthesize related history on demand** (memory + role-scoped operational records). Cloned from Odysseus's Memory/Skills subsystem, customized for EduFlow's multi-tenant + DPDP context (MongoDB-backed, `(user_id, schoolId)`-scoped, redacted). **Begins with an infra-feasibility spike** for chromadb/fastembed on Python 3.9 / Elastic Beanstalk.
**FRs covered:** FR31, FR32, FR33, FR34, FR35, FR36.

### Epic I: Frontend — multi-step plan card & status messaging
**Goal:** Give the headline UX an owner — evolve `ConfirmActionCard.js`/`ChatInterface.js` to render the multi-step plan, the 409 taxonomy/reconciliation messaging, disambiguation, and the deep-link fallback. No new pages/tools. Depends on Epic E's backend SSE plan event.
**UX-DRs covered:** UX-DR1–UX-DR5.

### Epic J: Owner/Principal CRUD — student & staff records (hardened AI tools)
**Goal:** Expose existing student & staff CRUD to the assistant as hardened tools (create+update for students — **no AI delete/erase**; staff create/edit). Wraps existing REST via shared services; no new UI.
**FRs covered:** FR37, FR41.

### Epic K: Owner/Principal CRUD — school internals (hardened AI tools)
**Goal:** Expose fee structures/discount types, classes/sections/houses, and branches/school-settings to the assistant as hardened tools. Destructive ops route through F.10. Owner authority for org config.
**FRs covered:** FR38, FR39, FR40.

### Epic H (Phase 2 — deferred, post Owner/Principal sign-off): Role extension
**Goal:** Extend the *identical* hardened pattern (A–K, including self-learning) to remaining roles (accountant, receptionist, maintenance, IT-tech, teacher, student). No engine changes. Gated on the pilot acceptance gate.
**FRs covered:** FR28.

**Execution order:** A → B → C → D → E → I → F → J → K → G (Phase 1) → H (Phase 2). Service extraction (A–C) precedes the executor (D), which precedes the planner (E); the frontend plan card (I) follows E's SSE event; F and G cross-cut/append. Each epic is standalone and requires only prior epics, never a later one. Per-domain cutover safety is provided by the story sequencing + characterization tests + shadow mode (F.5) + kill-switch (F.4).

**Clone-from-Odysseus note:** Epic G clones Odysseus Memory/Skills (`src/memory.py`, `memory_vector.py`, `services/memory/skills.py`, `skill_format.py`, `skill_extractor.py`, `routes/memory_routes.py`, `skills_routes.py`). Epic E borrows Odysseus patterns (`ask_user`, plan-mode, tool dispatcher) but does not clone wholesale. Epics A–D, F are EduFlow-custom (Odysseus lacks shared-service/transaction/saga/redaction/parity).

---

## Epic A: Trustworthy single-writer foundation — aligned domains

Every AI write for low-divergence Owner/Principal domains goes through the same service-layer path as the UI. Zero change to the REST/UI path; the AI path is corrected to match (case-by-case where a minor divergence exists). Establishes the `actor_ctx` contract and the service + characterization-test pattern.

### Story A.1: Attendance service as the reference shared-write-path
As an Owner/Principal,
I want my AI-marked attendance to write exactly what the panel writes,
So that the chat and the UI are interchangeable and trustworthy.

**Acceptance Criteria:**
**Given** the existing `POST /api/attendance/student/bulk` behavior is pinned by a characterization test (red baseline),
**When** `services/attendance_service.py` is extracted with signature `mark_attendance(db, actor_ctx, params, *, session=None, idempotency_key=None)` and both the REST route and `tool_functions_v2.mark_attendance` are refactored to call it,
**Then** the REST characterization test still passes unchanged
**And** a dual-entrypoint state-diff test shows the AI tool and REST route produce byte-identical DB blast radius (records + audit + scoping) except the timestamp/request-id allowlist
**And** `actor_ctx` dataclass `{user_id, role, sub_category, school_id, branch_id, actor_name}` (+ injectable `now_fn`) is defined in `services/actor_context.py` and synthesized identically by both adapters (this is the pinned contract — services needing more must extend the dataclass, never read `Request`)
**And** no service reads `Request`/`Depends` or raises `HTTPException`
**And** `scoped_query(branch_id=...)` is preserved (verified by the CLAUDE.md `scoped_filter` grep audit).

### Story A.2: Leave-approval service parity
As an Owner/Principal,
I want AI leave approvals to behave identically to the panel,
So that an AI-approved leave is indistinguishable from a manual one.

**Acceptance Criteria:**
**Given** `PATCH /api/staff/leaves/{id}` behavior is characterized,
**When** `services/leave_service.py` is extracted and both `approve_leave` (AI) and the route call it,
**Then** any divergence is resolved by an explicit case-by-case decision recorded in the story notes
**And** the dual-entrypoint parity test passes
**And** notification/audit fan-out matches the canonical path.

### Story A.3: Approval-request decision service parity
As an Owner/Principal,
I want AI approve/reject of pending requests to match the panel (incl. routing-dependent authority),
So that decisions and their notifications are consistent.

**Acceptance Criteria:**
**Given** `PATCH /api/operations/approvals/{id}` is characterized (incl. the owner-vs-principal routing rule),
**When** `services/approvals_service.py` is extracted and `decide_approval_request` + route call it,
**Then** the routing-dependent authority check remains enforced for both entrypoints
**And** the mandatory-reason rule and `create_notification` fan-out match
**And** the parity test passes.

### Story A.4: Announcement service parity (moderation honored)
As an Owner/Principal,
I want an AI-published announcement to respect the same moderation gate as the panel,
So that the AI can't broadcast unmoderated content.

**Acceptance Criteria:**
**Given** `POST /api/operations/announcements` + `_announcement_requires_approval(...)` is characterized,
**When** `services/announcement_service.py` centralizes the moderation gate and both entrypoints call it,
**Then** an AI announcement to `audience=all/class/teacher/student` becomes `status=pending_approval` exactly as the route does
**And** the dual-entrypoint parity test passes
**And** the duplicated inline gate in `tool_create_announcement` is removed.

### Story A.5: Contact-log service parity
As an accountant/Owner,
I want AI-logged fee contact events to match the panel,
So that contact history is consistent regardless of entrypoint.

**Acceptance Criteria:**
**Given** `POST /api/fees/contact-log` is characterized,
**When** `services/contact_log_service.py` is extracted and `log_contact_event` + route call it,
**Then** the parity test passes and scoping/audit match.

### Story A.6: Substitution service parity
As a Principal,
I want AI-initiated substitutions to match the panel,
So that timetable/coverage data stays correct.

**Acceptance Criteria:**
**Given** `POST /api/academics/substitutions` is characterized,
**When** `services/substitution_service.py` is extracted and `initiate_substitution` + route call it,
**Then** parity test passes and notification fan-out matches.

### Story A.7: Attendance-correction service parity (mandatory reason)
As an Owner/Principal,
I want AI attendance corrections to carry the mandatory reason and dual-write exactly like the panel,
So that corrections are auditable and consistent.

**Acceptance Criteria:**
**Given** `PATCH /api/fees/transactions/{id}/correct`-style correction behavior is characterized (insert `attendance_corrections` + update `student_attendance`),
**When** `services/attendance_correction_service.py` is extracted and `correct_attendance` + route call it,
**Then** both collection writes happen atomically within the service call
**And** the mandatory reason + `original_snapshot` + `correction_count` are written identically
**And** the parity test passes.

---

## Epic B: Parity + defect resolution — fees, discounts, house-points

Resolves the three confirmed pre-existing AI-layer defects while extracting shared services. Parity decided case-by-case.

### Story B.1: Fees service — idempotency + partial-payment + SSE parity
As an accountant/Owner,
I want an AI-recorded fee payment to be idempotent and identical to the panel (partial payments, SSE update),
So that a confirm retry never double-charges and the receipt/feeds match.

**Acceptance Criteria:**
**Given** `POST /api/fees/transactions` (idempotency-key, partial payments, `_publish_fee_update`) is characterized,
**When** `services/fees_service.py` is extracted and both `record_fee_payment` and the route call it,
**Then** an AI fee payment supports partial amounts and emits the SSE update exactly like the route
**And** a repeated confirmation with the same idempotency key produces exactly one transaction (regression test for the double-charge defect)
**And** the parity test passes.

### Story B.2: Discount service — close the AI approval-gate bypass
As an Owner,
I want AI-applied discounts above the threshold to route to my approval just like the panel,
So that the assistant can't bypass owner authority on a child's fees.

**Acceptance Criteria:**
**Given** `POST /api/fees/discounts/apply` routes `> DISCOUNT_APPROVAL_THRESHOLD` to `pending_discount_approvals` (HTTP 202),
**When** `services/discount_service.py` centralizes the threshold logic and both `apply_discount` and the route call it,
**Then** an AI discount above the threshold is created as a pending approval, NOT applied directly (regression test proving the bypass is closed)
**And** a below-threshold AI discount applies directly, matching the route
**And** the parity test passes.

### Story B.3: House-points service — correct data model + audit
As an Owner/Principal/teacher,
I want AI-awarded house points to update the real standings and be audited like the panel,
So that AI awards actually show in leaderboards and are traceable.

**Acceptance Criteria:**
**Given** `POST /api/activities/houses/{id}/points` updates `houses.points` + inserts `house_points_log` + writes audit,
**When** `services/house_points_service.py` is extracted and `award_house_points` is rewritten to call it (resolving the student-name→house_id mapping),
**Then** an AI award updates `houses.points` and `house_points_log` and writes an audit row (regression test proving the old `house_points`-only, un-audited path is gone)
**And** the parity test passes.

### Story B.4: Found-Defects addendum + regression guards
As the team,
I want the three resolved defects documented with permanent regression tests,
So that the bypass/double-charge/wrong-model bugs can never silently return.

**Acceptance Criteria:**
**Given** B.1–B.3 are complete,
**When** a "Found Defects" section is added to this epics doc (and `project-context.md` if a new invariant emerged),
**Then** each defect has a named regression test referenced
**And** the existing 699 tests remain green.

---

## Epic C: Parity — dynamic-collection incident/complaint tools

`assign_followup`, `update_incident_status`, `add_thread_entry`, `confirm_resolution` route to `incidents`/`complaints`/`facility_requests`/`tech_requests` at runtime. Make the target explicit so scoping/audit/transactions are deterministic.

### Story C.1: Explicit record-type resolution for incident tools
As a maintainer,
I want the incident/complaint tools to resolve their target collection explicitly (not implicitly at write time),
So that scoping, audit, and later transactions know the mutation surface up front.

**Acceptance Criteria:**
**Given** `_find_mutable_record`/`_append_record_note` currently search 4 collections at runtime,
**When** a `record_type` is resolved during planning/param-resolution and passed explicitly to the service,
**Then** the service writes only to the resolved collection
**And** an ambiguous/unknown record returns a clear disambiguation/refusal (no blind multi-collection scan at write)
**And** existing behavior is preserved by a characterization test.

### Story C.2: Incident assign + thread services parity
As an Owner/Principal,
I want AI follow-up assignment and thread entries to match the panel,
So that incident workflows are consistent.

**Acceptance Criteria:**
**Given** `PATCH /api/operations/incidents/{id}/assign` and `POST /.../thread` are characterized,
**When** `services/incident_service.py` exposes `assign_followup` + `add_thread_entry` and both entrypoints call them,
**Then** parity tests pass for each, incl. notification fan-out where the route does it.

### Story C.3: Incident status + resolution-confirm services parity
As an Owner/Principal,
I want AI status updates and resolution confirmations to match the panel,
So that incident state transitions are consistent and audited.

**Acceptance Criteria:**
**Given** `PATCH /api/operations/incidents/{id}` and the facility-request confirm path are characterized,
**When** `update_incident_status` + `confirm_resolution` call `services/incident_service.py`,
**Then** status-transition guards and audit match both entrypoints
**And** parity tests pass.

---

## Epic D: Safe execution — atomic, idempotent, never torn

### Story D.1: Real-Mongo replica-set test tier + FakeDb session shim
As the team,
I want a real-Mongo (replica-set) test tier and a FakeDb session shim,
So that atomicity/idempotency/transaction guarantees are actually verifiable (FakeDb can't fake them).

**Acceptance Criteria:**
**Given** the existing FakeDb harness has no sessions/transactions/unique-index enforcement,
**When** a `@pytest.mark.mongo_real` tier is added (ephemeral Mongo started as a single-node replica set via testcontainers or CI `--replSet`+`rs.initiate()`) and a no-op `session=` shim is added to `FakeCollection`,
**Then** a sample transaction test commits/rolls back on the real tier
**And** the FakeDb shim accepts `session=` without asserting atomicity
**And** the 699 existing tests stay green
**And** the `@pytest.mark.mongo_real` tier runs nightly + on AI-layer path changes (NOT every PR), with the CI markers/job documented so it isn't disabled for being slow.

### Story D.2: Tenant-safe transaction sessions
As a maintainer,
I want a transaction session that preserves tenant scoping,
So that transactional writes never bypass `schoolId`/`branch_id` injection.

**Acceptance Criteria:**
**Given** `ScopedDatabase` wraps Motor,
**When** `database.get_txn_session()` returns `_client.start_session()` and `ScopedCollection` forwards `session=` through its scoped ops,
**Then** a write inside a transaction still injects `schoolId` (test proves no tenant leak)
**And** `get_raw_db()` is never used inside the executor.

### Story D.3: Single-step atomic executor + length-1 plan path
As an Owner/Principal,
I want even a single AI write to run through the atomic executor,
So that there is one execution path and no behavioral fork.

**Acceptance Criteria:**
**Given** D.2 sessions exist,
**When** `_execute_confirmed_dispatch` builds a length-1 Plan and calls `ai/plan_executor.run()` (transaction-first), unconditionally,
**Then** an existing single write tool still works end-to-end (regression)
**And** a forced mid-write failure leaves zero committed changes (real-Mongo test).

### Story D.4: Idempotency key + unique index + migration
As an Owner/Principal,
I want a replayed confirmation to apply an action exactly once,
So that retries never double-charge/double-mark.

**Acceptance Criteria:**
**Given** the executor writes via services,
**When** `idempotency_key = f"{plan_token}:{step_idx}"` is stored on write rows, a unique index is added in `database._create_indexes()` + a migration in `migrations/` (and `run_all.py`),
**Then** two concurrent confirms of the same plan produce exactly one effect and one DuplicateKey-mapped "already applied" (real-Mongo concurrency test)
**And** an index-existence introspection test guards the index
**And** where a REST route already has a content-based idempotency key, the AI path derives the SAME key (so AI and REST dedupe against one another, not just within a single plan token).

### Story D.5: Saga fallback + needs-manual-reconciliation
As an Owner/Principal,
I want multi-step plans with non-Mongo side effects to either fully complete or cleanly compensate,
So that a partial failure never leaves a torn or silently half-done state.

**Acceptance Criteria:**
**Given** a plan whose steps include a non-Mongo side effect (e.g., SMS),
**When** a later step fails, the executor runs compensating actions in reverse,
**Then** the DB ends fully-applied or fully-compensated (fault-injection test)
**And** if a compensation itself fails, the plan halts in `needs_manual_reconciliation` with an audit row + specific message (no silent partial success).

### Story D.6: Optimistic-concurrency precondition revalidation
As an Owner/Principal,
I want a plan to abort if the underlying data changed between planning and confirmation,
So that a stale plan can't corrupt state.

**Acceptance Criteria:**
**Given** each write step carries a `precondition` (version/updatedAt or key fields),
**When** the executor re-reads inside the transaction and a value changed since planning,
**Then** the whole plan aborts with a `plan_stale` 409 (distinct from `plan_tampered`)
**And** no partial write occurs (real-Mongo test).

---

## Epic E: Whole-job-by-instruction — agentic planner + plan-then-confirm-once

### Story E.1: Plan/step schema + plan-hash confirm token
As a maintainer,
I want the confirm token to bind a hash of the exact resolved plan,
So that what executes is provably what the user approved.

**Acceptance Criteria:**
**Given** `confirm_tokens.py` currently carries single `action`/`params`,
**When** it is evolved to carry `plan` + `plan_hash` (canonical sorted-key sha256 incl. entity IDs + tenant) + `schema_version`, with the same hash helper used at issue and consume,
**Then** `consume_confirm_token` rejects a tampered plan with `plan_tampered` 409
**And** a missing `plan` (legacy token) still consumes as a length-1 plan (back-compat test)
**And** single-use + TTL + tenant-binding tests still pass.

### Story E.2: Structured planner
As an Owner/Principal,
I want the assistant to turn one instruction into an ordered plan of existing tools,
So that it can complete compound tasks.

**Acceptance Criteria:**
**Given** a compound instruction,
**When** `ai/planner.py` produces an ordered `steps[]` of existing, authorized tools (reads runnable inline; writes deferred) with a `precondition` on each write step,
**Then** the plan only references tools the user's role+sub_category permit (unauthorized tools excluded pre-token)
**And** the planner is deterministic in tests via recorded plan fixtures (no live Azure call).

### Story E.3: Round-counter redefinition
As a maintainer,
I want planning/read rounds bounded separately from confirmed writes,
So that multi-step tasks aren't starved by the existing 3-round cap.

**Acceptance Criteria:**
**Given** `MAX_TOOL_ROUNDS=3` currently bounds the whole loop,
**When** it is redefined to bound planning/read iterations only and `MAX_PLAN_STEPS` (default 8) bounds plan size,
**Then** confirmed write execution does not consume the planning budget (test)
**And** a plan exceeding `MAX_PLAN_STEPS` is rejected with a clear message.

### Story E.4: Server-side entity resolution + disambiguation
As an Owner/Principal,
I want the assistant to ask me to clarify when a name is ambiguous instead of guessing,
So that it never acts on the wrong student/staff.

**Acceptance Criteria:**
**Given** an instruction naming an entity that matches >1 record,
**When** the planner resolves entities server-side,
**Then** it returns a disambiguation prompt in chat (UX-DR3) and issues no token
**And** an exact single match resolves to the canonical id used in the plan/hash
**And** if ANY step of the plan is outside the user's role/sub_category, the WHOLE plan is rejected with which-step feedback (never silently truncated).

### Story E.5: Plan-then-confirm-once execution end-to-end
As an Owner/Principal,
I want to approve a compound plan once and have it all execute atomically,
So that I complete a whole job in one instruction + one confirmation.

**Acceptance Criteria:**
**Given** a resolved multi-step write plan,
**When** chat.py emits one `confirm_action` SSE event listing all steps (UX-DR1) and I confirm,
**Then** `/confirm` → executor commits all steps atomically (or none)
**And** the result is streamed and the dashboards reflect every step
**And** `plan_tampered`/`plan_stale`/`needs_manual_reconciliation` map to the P7 user messages (UX-DR5)
**And** the whole plan counts as ONE AI rate-limit dispatch (checked once at /confirm, not per step)
**And** notifications/SMS fire only AFTER the transaction commits (an aborted plan sends nothing)
**And** a token that expired while the user read the plan returns a clear, re-planable message (not a generic 400).

### Story E.6: Graceful fallback when the assistant can't complete a job
As an Owner/Principal,
I want a clear path to the UI panel when the assistant can't plan/complete something,
So that I'm never left at a dead end and nothing is half-written.

**Acceptance Criteria:**
**Given** an instruction the assistant cannot confidently plan or that fails authorization,
**When** the turn ends,
**Then** it returns a deep-link to the corresponding UI panel (UX-DR4), with no partial DB write
**And** the response is logged for later review.

---

## Epic F: Compliant & operable — DPDP + safety-ops + parity harness

### Story F.1: PII minimization to the LLM
As a data-protection-conscious school,
I want the assistant to send the model the minimum personal data necessary,
So that children's special-category data isn't shipped to the LLM unnecessarily.

**Acceptance Criteria:**
**Given** tool results and prompts can contain student fields,
**When** `redact_for_llm()` is applied before LLM calls and trace persistence (extending `_safe_tool_result_for_chat`),
**Then** an outbound-payload snapshot test asserts zero special-category fields (DOB/contact/health/full-address/fee-detail) unless strictly required
**And** identifiers/references are sent instead.

### Story F.2: Redacted traces/audit + audited minor reads
As a school under DPDP,
I want stored traces/audit free of unredacted PII and every minor-record access audited,
So that we can demonstrate purpose-limited, traceable handling.

**Acceptance Criteria:**
**Given** a known-PII probe flowed through a chat turn,
**When** persisted chat traces + audit logs are scanned,
**Then** zero unredacted PII matches are found
**And** every assistant read of a minor's record writes an audit entry (actor/target/purpose) via `write_audit` (FR21).

### Story F.3: Per-step re-scoping in the executor
As a multi-branch school,
I want every step of a plan re-scoped to my school/branch,
So that a chain can't leak across tenants/branches.

**Acceptance Criteria:**
**Given** a multi-step plan,
**When** the executor runs each step,
**Then** `scoped_query(branch_id=...)` is re-applied per step (test proves step 3 can't widen scope vs step 1).

### Story F.4: AI-write kill-switch
As an Owner/operator,
I want to disable all AI writes instantly,
So that I can stop the assistant if something looks wrong during the pilot.

**Acceptance Criteria:**
**Given** `db.system_flags.ai_writes_enabled`,
**When** it is turned off,
**Then** `_execute_confirmed_dispatch` rejects writes with a clear message within ≤60s (short-TTL cache test)
**And** reads still work.

### Story F.5: Shadow / dry-run mode
As an Owner/Principal in the pilot,
I want a mode that shows what the assistant *would* change without committing,
So that we accumulate parity evidence at zero write-risk before enabling live writes.

**Acceptance Criteria:**
**Given** dry-run mode is on for a user/school,
**When** a plan is confirmed,
**Then** the executor runs writes in an aborted transaction and reports the would-be diff, committing nothing
**And** saga/side-effect steps no-op-with-record
**And** the reported diff matches a later real run via the canonical normalizer.

### Story F.6: Dual-entrypoint parity harness + CI drift gate
As the team,
I want continuous proof that AI and UI writes are identical,
So that drift can never silently reappear.

**Acceptance Criteria:**
**Given** `tests/backend/parity/` with `normalizer.py` (masks ids/timestamps/order; ruleset unit-tested) and a per-tool corpus,
**When** the harness runs the REST handler via TestClient and the AI tool via real dispatch on the same seed and diffs state,
**Then** all in-scope tools pass with zero diff outside the allowlist
**And** CI fails if a write tool/route ships without a corpus entry.

### Story F.7: Pilot observability & metrics
As an Owner/Principal (and the team),
I want the success-criteria metrics actually measured,
So that the acceptance gate is evidence-based, not anecdotal.

**Acceptance Criteria:**
**Given** the pilot must show ≥80% adoption, a minimum mutation volume N, and zero parity-diff/torn-state/leakage incidents,
**When** the AI dispatch path emits counters/events for plan executions, confirmations, per-step outcomes, parity-diff incidents (from F.6), torn-state/reconciliation events, kill-switch activations, and AI-vs-UI action counts,
**Then** these are queryable (reusing the existing audit/observability layer from Part 7) for an Owner/Principal pilot review
**And** no PII is captured in metrics (DPDP).

### Story F.8: Part closeout — refresh project-context & CLAUDE.md
As the next developer,
I want the new invariants documented in the canonical context files,
So that the drift this initiative removed can't silently return.

**Acceptance Criteria:**
**Given** the hardening invariants (service-layer one-writer, plan-then-confirm-once token, idempotency key format, per-step re-scoping, kill-switch, redact_for_llm, parity-corpus CI gate),
**When** Phase 1 nears completion,
**Then** `project-context.md` and `CLAUDE.md` are updated with each new invariant + its enforcement point
**And** the platform-quality-sweep tracker row is updated.

### Story F.9: AI-write remediation (revert a dispatch)
As an Owner/operator,
I want to find and revert a specific AI-authored mutation if the pilot writes something wrong,
So that the kill-switch (stops new writes) is paired with a way to undo a bad past write.

**Acceptance Criteria:**
**Given** the write-ahead audit log records every AI dispatch (plan, steps, before/after),
**When** an operator identifies a bad AI dispatch,
**Then** a documented remediation path exists to reverse that dispatch's writes (manual runbook + the audit data needed), scoped and audited
**And** the runbook is captured in the deployment docs.

### Story F.10: Two-step destructive-action confirmation + actor-tagged deletion audit
As an Owner/Principal,
I want any AI deletion to require a second explicit confirmation and to be permanently logged with who did it,
So that destructive changes to the school database are deliberate and fully traceable.

**Acceptance Criteria:**
**Given** a plan contains a destructive step (delete fee structure/class/house/discount-type/branch, etc.),
**When** the plan is confirmed,
**Then** the destructive step requires a SECOND explicit acknowledgment beyond the plan-confirm (the card flags it as destructive; it is never silently auto-batched)
**And** on execution an actor-tagged deletion audit row is written (`actor, actor_name, target, action=delete, timestamp`) queryable as "who deleted what, when"
**And** student hard-delete and DPDP-erase are rejected by the assistant entirely (UI-only).

---

## Epic I: Frontend — multi-step plan card & status messaging

Gives the headline UX a clear owner. Depends on Epic E's backend SSE `confirm_action` plan event. No new tools/pages — evolves the existing `ConfirmActionCard.js` / `ChatInterface.js`.

### Story I.1: Multi-step plan confirmation card
As an Owner/Principal,
I want one card that lists every step of the proposed plan with a single Confirm/Cancel,
So that I approve a whole compound job in one glance (UX-DR1).

**Acceptance Criteria:**
**Given** chat.py emits a `confirm_action` event carrying an ordered plan,
**When** `ConfirmActionCard.js` renders it,
**Then** all N steps display in order, scannable, under one Confirm and one Cancel
**And** double-submit is guarded (existing Part 8 pattern)
**And** Cancel issues no write and reports cancellation.

### Story I.2: Status & error messaging (409 taxonomy + reconciliation)
As an Owner/Principal,
I want clear, distinct messages for the failure modes,
So that I know whether to re-confirm, re-plan, or that something needs manual attention (UX-DR5, UX-DR2).

**Acceptance Criteria:**
**Given** the backend returns `plan_tampered` / `plan_stale` / `needs_manual_reconciliation` / partial-failure,
**When** the chat renders them,
**Then** each maps to a specific, human message ("re-confirm" / "data changed — re-plan" / "needs manual attention" / "nothing was applied because…")
**And** no internal error detail leaks (only `{error, correlation_id}` for opaque failures).

### Story I.3: Disambiguation prompt & UI deep-link fallback
As an Owner/Principal,
I want to pick between ambiguous matches in chat and get a panel link when the assistant can't proceed,
So that I'm never stuck (UX-DR3, UX-DR4).

**Acceptance Criteria:**
**Given** the assistant returns a disambiguation request or a can't-complete fallback,
**When** the chat renders it,
**Then** an ambiguous case shows selectable options (e.g., by admission number) that continue the flow
**And** a can't-complete case shows a deep-link to the corresponding UI panel, with no partial write.

---

## Epic G: AI self-learning (Memory + Skills) for Owner & Principal — cloned from Odysseus

No memory/skills UI (FR32). Begins with an infra spike.

### Story G.1: Infra feasibility spike — chromadb + fastembed on Python 3.9 / EB
As the team,
I want proof that the vector-memory dependencies run on our stack before building the feature,
So that we don't commit to a dependency that can't deploy.

**Acceptance Criteria:**
**Given** the backend is Python 3.9 on Elastic Beanstalk,
**When** `chromadb-client` + `fastembed` are trialed (model size, cold-start, memory footprint, EB packaging),
**Then** a short spike report records feasibility + the chosen embedding model + any constraints
**And** a go/no-go for the rest of Epic G is recorded (fallback: keyword-only retrieval if vectors aren't viable).

### Story G.2: Owner-scoped memory store (MongoDB-backed, DPDP-redacted)
As an Owner/Principal,
I want the assistant to durably remember important things scoped to me,
So that it adapts to how I work over time.

**Acceptance Criteria:**
**Given** the Odysseus memory model (owner/text/category/source/uses/metadata),
**When** it is cloned and adapted to a MongoDB collection scoped by `(user_id, schoolId)` with `redact_for_llm()` applied on write,
**Then** a memory write stores no children's special-category PII (test)
**And** one owner's memory is never returned to another (isolation test, FR34).

### Story G.3: Hybrid recall injected into chat context
As an Owner/Principal,
I want the assistant to recall relevant past context automatically,
So that it stays aware of my prior interactions.

**Acceptance Criteria:**
**Given** stored memories,
**When** a chat turn runs, the assistant retrieves top-K via hybrid (vector + keyword fallback) and injects them into context,
**Then** relevant memories influence the response (test with seeded memory)
**And** retrieval degrades gracefully to keyword-only if vectors are unavailable.

### Story G.4: Auto-save important info + in-chat confirm when uncertain (no UI)
As an Owner/Principal,
I want the assistant to remember important things on its own and only ask me in chat when unsure,
So that learning is effortless and invisible.

**Acceptance Criteria:**
**Given** a chat turn containing durable-worthy info,
**When** the assistant judges importance,
**Then** clearly-important info is saved automatically (no prompt)
**And** genuinely-uncertain items trigger an in-chat yes/no (never a UI control)
**And** no memory/skills panel or UI surface exists anywhere (FR32 verified).

### Story G.5: On-demand recall & synthesis (the pre-meeting briefing)
As an Owner/Principal,
I want to ask for related history on a subject and get a synthesized briefing,
So that I'm prepared before a meeting (e.g., a family's 3 prior fee-concession visits).

**Acceptance Criteria:**
**Given** I ask in chat for the related history of a family/student,
**When** the assistant synthesizes across its memory AND the role-scoped operational records it may access (visitor logs, enquiries, fee-concession/discount requests, notes),
**Then** it returns a concise briefing of related items + good-to-know context, scoped to what my role may see
**And** the synthesis reuses the EXACT same read-authorization/scoping path as the existing read tools (no separate over-sharing path)
**And** every read of a minor's record in that synthesis is audited (FR35)
**And** it never surfaces data outside my role/branch scope.

### Story G.6: Skill auto-extraction + feedback (no UI)
As an Owner/Principal,
I want the assistant to get better at my recurring workflows over time,
So that repeated tasks get smoother.

**Acceptance Criteria:**
**Given** a complex run (≥2 rounds/tools),
**When** the cloned `skill_extractor` distills a confidence-scored skill scoped to me,
**Then** low-confidence skills are dropped (threshold)
**And** a lightweight in-chat feedback signal can mark a recalled skill helpful/not (no skills UI)
**And** skills are `(user_id, schoolId)`-isolated.

### Story G.7: Memory erasure & retention (DPDP)
As a school under DPDP,
I want learned memory to be deletable and retention-bounded,
So that the memory store honors right-to-erasure and doesn't hoard personal data.

**Acceptance Criteria:**
**Given** an Owner/Principal leaves, or a student's records are erased (DPDP §12),
**When** an erasure is triggered,
**Then** that owner's memories are deleted, and memories referencing an erased student are purged or de-referenced
**And** a retention policy (TTL or review) bounds memory age
**And** all memory deletions are audited.

### Story G.8: Memory correction & confidence (anti-poisoning)
As an Owner/Principal,
I want wrong things the assistant "learned" to be correctable,
So that one bad auto-saved fact doesn't silently bias every future answer.

**Acceptance Criteria:**
**Given** an auto-saved memory is wrong,
**When** the owner corrects it in chat ("that's not right…"),
**Then** the memory is updated/removed and won't resurface
**And** memories carry a confidence/recency signal so stale/low-confidence ones decay in retrieval ranking.

---

## Epic J: Owner/Principal CRUD — student & staff records (hardened AI tools)

Exposes existing student/staff CRUD (REST) to the assistant as hardened tools through the engine. Create + update only for students; hard-delete/erase stay UI-only (FR37). Depends on the engine (A-pattern + D + E) and F.10 for any destructive step.

### Story J.1: Student create & update tools
As an Owner/Principal,
I want to create and edit student records by instruction,
So that I can do day-to-day student-database work from chat, identically to the panel.

**Acceptance Criteria:**
**Given** `POST /api/students/`, `PATCH /api/students/{id}`, `PUT /api/students/{id}/guardians`, photo, and status/deactivate are characterized,
**When** `services/student_service.py` is extracted and new AI tools (`create_student`, `update_student`, manage-guardians, set-status) call it,
**Then** an AI-created/edited student is byte-identical to the panel result (dual-entrypoint parity test), DPDP-redacted to the LLM, branch/school-scoped, and audited
**And** there is **no** `delete_student`/`erase_student` AI tool (UI-only; the assistant refuses and offers the panel deep-link)
**And** the tools are gated to the same roles the REST routes require.

### Story J.2: Staff create & edit tools
As an Owner/Principal,
I want to create and edit staff records by instruction,
So that staff onboarding/updates can be done from chat like the panel.

**Acceptance Criteria:**
**Given** the staff create/edit REST routes are characterized,
**When** `services/staff_service.py` is extracted (or extended) and `create_staff`/`update_staff` AI tools call it,
**Then** the dual-entrypoint parity test passes, OWNER_ONLY_FIELDS protections are preserved, scoping/audit match
**And** any destructive staff op routes through F.10 (two-step + deletion audit).

---

## Epic K: Owner/Principal CRUD — school internals (hardened AI tools)

Exposes fee config, academic structure, and org config (REST) to the assistant as hardened tools. Destructive variants go through F.10.

### Story K.1: Fee structures & discount types CRUD tools
As an Owner/Principal,
I want to manage fee structures and discount types by instruction,
So that "all the fee-summary tools" are usable from chat with full parity.

**Acceptance Criteria:**
**Given** `POST/PATCH /api/fees/structures` and `/api/fees/discount-types` are characterized,
**When** `services/fee_config_service.py` is extracted and AI tools call it,
**Then** create/update parity holds (dual-entrypoint), owner-only gating preserved, audited
**And** any delete (e.g., remove a discount type) requires F.10's two-step confirm + deletion audit.

### Story K.2: Classes, sections & houses CRUD tools
As an Owner/Principal,
I want to manage classes, sections, and houses by instruction,
So that academic-structure upkeep is doable from chat.

**Acceptance Criteria:**
**Given** the class/section/house REST routes are characterized,
**When** `services/academic_structure_service.py` is extracted and AI tools call it,
**Then** create/update parity holds, scoping/audit match
**And** deletes route through F.10.

### Story K.3: Branches & school settings tools (owner authority)
As an Owner,
I want to manage branches and school settings (incl. year-end transition) by instruction,
So that high-level org config is doable from chat, safely.

**Acceptance Criteria:**
**Given** `POST/PUT /api/settings/branches`, `PATCH /api/settings/school`, and year-end transition are characterized,
**When** `services/org_config_service.py` is extracted and AI tools call it,
**Then** these tools are gated to **owner** authority (parity with REST), audited, and parity-tested
**And** destructive/high-impact ops (e.g., delete branch, year-end transition) route through F.10's two-step confirm + audit
**And** these are confirmed to add **no new UI** — they wrap existing capabilities.

---

## Epic H (Phase 2 — deferred): Role extension

### Story H.1: Extend the hardened pattern to remaining roles
As a school,
I want every profile (accountant, receptionist, maintenance, IT-tech, teacher, student) to get the same hardened, parity-checked, self-learning assistant,
So that the whole school benefits after the Owner/Principal pilot succeeds.

**Acceptance Criteria:**
**Given** Owner + Principal have signed off on the pilot,
**When** Phase 2 planning breaks this epic into per-role stories reusing Epics A–G's engine (no engine changes),
**Then** each role's write tools get a shared service + parity test, role-scoped self-learning, and DPDP controls
**And** student-facing self-learning gets an explicit DPDP re-review (minors as data principals).

> **Found Defects (resolved in Epic B):** (1) `award_house_points` wrong data model + no audit → B.3; (2) `apply_discount` owner-approval bypass → B.2; (3) `record_fee_payment` no idempotency (double-charge) → B.1. Each has a permanent regression test (B.4).

---

## Final Validation Summary

- **Epics:** 11 (A–G + I/J/K Phase 1, H Phase 2). **Stories:** 53. **Execution order:** A→B→C→D→E→I→F→J→K→G→H.
- **FR coverage:** FR1–FR36 all mapped to ≥1 story (see FR Coverage Map + per-story references).
- **Coverage caveats (intentional):** FR23 (student content-filter) preserved as a regression guard in Phase 1; full student-facing verification in Epic H (students = Phase 2). FR26 (per-write write-ahead audit) covered implicitly by executor stories D.3/D.5 (extends the existing Part-2 audit).
- **Dependencies:** no forward dependencies within or across epics; each epic standalone, requiring only prior epics. Test substrate (D.1) precedes transaction stories; plan-token (E.1) precedes plan execution (E.5).
- **Brownfield discipline:** characterization-test-first on every service extraction; migration + index stories explicit (D.4); regression guards (B.4, F.6 CI gate); `scoped_query` audit per touched route; 699 existing tests stay green; no new UI/tools (FR29, G.4).
- **Clone-from-Odysseus:** Epic G clones Memory/Skills; Epic E borrows planner/ask_user patterns; A–D/F are EduFlow-custom (Odysseus lacks them).
- **Status:** COMPLETE — **awaiting Shubham's review before any implementation begins.**

## Resolved Audit Findings (adversarial review, 2026-06-07)

A cynical gap-audit found 15 issues; all are now addressed in the plan:

| # | Finding | Resolved in |
|---|---|---|
| 1 | No frontend story for the plan card | **Epic I** (I.1–I.3) |
| 2 | Nothing instruments success metrics | **Story F.7** (pilot observability) |
| 3 | No per-domain cutover mechanism | Per-domain story sequencing + characterization tests + shadow mode (F.5) + kill-switch (F.4) — _the A.0 per-domain feature flag was removed per Shubham's review; cutover safety relies on these instead_ |
| 4 | Rate-limit per plan undefined | **AD14** + Story E.5 (one dispatch per plan) |
| 5 | Notification vs transaction ambiguity | **AD14** + Story E.5/D.5 (fire after commit) |
| 6 | No memory erasure/retention (DPDP) | **Story G.7** |
| 7 | No memory correction / poisoning defense | **Story G.8** |
| 8 | Partial-plan authorization undefined | **AD14** + Story E.4 (reject whole plan) |
| 9 | No project-context/CLAUDE.md closeout | **Story F.8** |
| 10 | Confirm-token TTL vs planning latency | **AD14** + Story E.5 (re-planable expiry) |
| 11 | Idempotency only dedupes within a token | **AD14** + Story D.4/B.1 (match REST key) |
| 12 | Recall authorization reuse hand-waved | **Story G.5** (reuse read-tool authz path) |
| 13 | Real-Mongo CI cost/runtime undecided | **Story D.1** (nightly + AI-path, documented) |
| 14 | No data-remediation if pilot writes bad data | **Story F.9** (revert-dispatch runbook) |
| 15 | `actor_ctx` underspecified | **AD14** + Story A.1 (pinned contract) |

**Final totals:** 11 epics (A–K), 53 stories, FR1–FR42 + UX-DR1–5 covered.

> **Shubham review changes (2026-06-07):** Story A.0 removed (its `actor_ctx` contract folded into A.1; cutover safety via sequencing + shadow + kill-switch). Added CRUD coverage per Shubham: **Epic J** (student & staff create/update — NO AI student delete/erase), **Epic K** (fee/academic/org-config CRUD), and **Story F.10** (two-step destructive-action confirm + actor-tagged deletion audit). New requirements FR37–FR42 + architecture AD15.
