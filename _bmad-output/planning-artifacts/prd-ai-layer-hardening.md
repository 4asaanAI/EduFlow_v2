---
stepsCompleted: ['step-01-init', 'step-02-discovery', 'step-02b-vision', 'step-02c-executive-summary', 'step-03-success', 'step-04-journeys', 'step-05-domain', 'step-06-innovation', 'step-07-project-type', 'step-08-scoping', 'step-09-functional', 'step-10-nonfunctional', 'step-11-polish', 'step-12-complete']
releaseMode: phased
classification:
  projectType: 'agentic AI layer of a multi-role school-management SaaS (React SPA / FastAPI / MongoDB / Azure OpenAI)'
  domain: 'EdTech / School Management — children PII + financial (fees/payroll) data, multi-tenant (school+branch)'
  complexity: 'high'
  projectContext: 'brownfield'
  compliance: ['DPDP Act 2023 (children data special category)']
inputDocuments:
  - '_bmad-output/project-context.md'
  - '_bmad-output/parts/ai-layer/scope.md'
  - '_bmad-output/parts/ai-layer/review-findings-and-fix-plan.md'
  - '_bmad-output/planning-artifacts/ai-layer-bmad-end-to-end-2026-05-13.md'
  - '_bmad-output/planning-artifacts/ai-layer-frontend-bmad-pass-2026-05-13.md'
  - 'backend/ai/tool_functions_v2.py'
  - 'backend/routes/chat.py'
workflowType: 'prd'
initiative: 'ai-layer-hardening'
---

# Product Requirements Document - EduFlow AI Layer Hardening

**Author:** Abhimanyusingh
**Date:** 2026-06-07

## Executive Summary

EduFlow's AI chat is the primary interface for staff and students at multi-branch Indian CBSE schools. Today it reliably *reads* school data but rarely *acts*: only ~15 of the backend's ~163 mutating capabilities are reachable through the assistant, it executes one tool per turn, and its write tools re-implement database mutations independently of the REST routes the UI uses. This initiative hardens the **existing** AI tool surface — adding **no new UI features** (the platform already has the panels) — so that staff and students can complete their real jobs by instruction and have those actions land in MongoDB *identically* to clicking through the UI.

The hardening rests on two pillars:

1. **Action reliability via a single shared write path.** AI tools and REST routes are collapsed onto one extracted service layer per domain (following the existing `notification_service` / `audit_service` "one writer" precedent), so an AI-initiated write is, by construction, the same mutation as the UI's — same validation, multi-tenancy scoping (`schoolId` + `branch_id`), idempotency, notifications, and audit trail. Parity is *proven*, not asserted, by differential state-diff tests that compare the full database blast radius of the AI path against the REST path.

2. **Agentic multi-step chaining under plan-then-confirm-once.** The assistant plans a complete compound task from existing tools, the user approves the **plan once**, and the backend executes the steps as an atomic, all-or-nothing batch. This deliberately evolves Part 2's per-call confirm-token contract into a plan-scoped one — preserving "nothing mutates without explicit confirmation" while eliminating torn-state risk on a child's or financial record and replacing N confirmation cards with one.

### What Makes This Special

The differentiator is **autonomous, whole-task execution that never leaves the school's safety rails.** The assistant finishes a multi-step job in one turn, but every step stays inside the user's exact role and branch scope, the plan-confirm gate, and the audit trail — and because AI-action and UI-action traverse the same write path, a school can let the assistant operate on a minor's record knowing it behaves identically to a human doing it by hand. The core insight: the capability, data model, and confirm/audit rails already exist; the work is making existing power **reliable, chainable, and provably safe on children's data under India's DPDP Act 2023** — which here means concrete, testable controls: PII minimization into LLM prompts, redacted traces and audit logs, per-step re-scoping to prevent cross-child leakage, audited *access* (not just mutation) of minors' records, and a named Azure OpenAI sub-processor/data-residency precondition.

### Rollout & Acceptance Priority

The **Owner** and **Principal** profiles (Principal = role `admin` + sub-category `principal`) are the **acceptance gate**. After go-live they pilot the assistant for one to two months; full-school rollout to all other profiles is contingent on their approval. Accordingly, their write tools (fees, attendance, leave, discounts, approvals, announcements) are hardened and verified **first**, behind a shadow/dry-run phase that accumulates parity evidence at zero write-risk before live writes are enabled, with a kill-switch to disable AI writes on demand. Acceptance is a falsifiable contract — a defined set of compound Owner/Principal jobs, each completed by instruction with zero parity-diff, zero torn-state, and zero cross-tenant/branch leakage across a stated minimum volume of real actions — not an adjective.

## Project Classification

- **Project Type:** Agentic AI layer of a multi-role school-management SaaS (React 19 SPA ↔ FastAPI/Python 3.9 ↔ MongoDB Atlas ↔ Azure OpenAI `gpt-5.3-chat`)
- **Domain:** EdTech / School Management — children's PII and financial (fees/payroll) data; multi-tenant across school and branch
- **Complexity:** High — agentic execution mutating live operational data, plan-confirm write safety, RBAC + sub-category gating, multi-tenancy isolation, content filtering for minors, audit/compliance
- **Project Context:** Brownfield — hardening a shipped AI dispatch pipeline (Part 2 closed correctness/security gaps; this adds write-execution parity and agentic chaining)
- **Compliance:** DPDP Act 2023 (children's personal data as a special category)

> **Scope boundary — which AI surface:** This initiative targets ONLY the main chat interface (`frontend/src/components/ChatInterface.js` → `/api/chat/*` → `backend/routes/chat.py`, with the full `TOOL_REGISTRY`, SSE streaming, and confirm-token dispatch). The bottom-right floating bubble (`FloatingAssistant.js` → `/api/assistant` → `backend/routes/assistant.py`) is **explicitly out of scope** despite its "assistant" naming.

## Success Criteria

### User Success

- **Whole-job-by-instruction:** An Owner or Principal can issue a compound instruction in natural language (e.g., "mark 9A present except Rahul, mark him absent, and notify his parent") and the assistant completes the *entire* task after **one** plan confirmation — no panel navigation, no per-step taps.
- **Trust moment:** The user sees the proposed plan, approves once, and the result is immediately reflected in dashboards/other roles exactly as if they had done it manually — they never have to re-check whether it "actually saved."
- **No surprises:** If any step of an approved plan cannot complete, the user is told clearly and the database is left in a clean state (fully applied or fully not applied) — never half-done on a fee or attendance record.
- **Time-to-task:** A target compound Owner/Principal job completes in ≤ 1 instruction + 1 confirmation, versus the current ≥ 5–7 UI interactions.

### Business Success

- **Acceptance-gate pass:** Owner *and* Principal each sign off, per defined pilot job, after the 1–2 month live pilot. Sign-off is the trigger for full-school rollout — the single business metric that matters for this initiative.
- **Pilot adoption:** ≥ 80% of the defined Owner/Principal compound jobs are performed via the assistant (rather than the panels) by the end of the pilot window.
- **Zero trust-breaking incidents:** No incident during the pilot where the AI mutated data incorrectly, leaked one child's data into another context, or charged/marked twice.

### Technical Success

- **Parity (the core promise):** For every hardened write tool, a differential state-diff test proves the AI path and the REST/UI path produce byte-identical database blast radius (mutated doc + audit + notifications + derived counters + scoping), except an explicit timestamp/request-id allowlist. **Target: 100% of hardened tools have a passing parity test; zero parity-diff defects in the pilot.**
- **Atomicity:** Plan execution is all-or-nothing. Fault-injection tests at every step boundary leave the DB fully-applied or fully-unapplied — never torn. **Zero torn-state events in the pilot.**
- **Idempotency:** A retried/replayed plan confirmation never double-applies (no double fee charge, no double attendance mark).
- **DPDP controls (each a test, all in MVP):**
  - LLM prompts/tool-args carry student **IDs/references, not** raw names/DOB/contact/health/fee detail (special-category fields) — verified by outbound-payload snapshot.
  - Audit logs and any LLM traces are PII-redacted — verified by writing known PII through a flow and grepping persisted stores for zero hits.
  - Every chain step re-asserts `schoolId` + `branch_id` — cross-child/cross-tenant leakage test passes on multi-step chains, not just single calls.
  - AI **reads** of a minor's record are audited (who/what/why) for purpose limitation, not just writes.
  - Azure OpenAI sub-processor/data-residency disclosure documented as a named precondition.
- **Safety operations:** Shadow/dry-run mode exists and is exercised before any live write; a kill-switch disables all AI writes with a stated RTO (target: effective within 1 minute, tested).
- **No regression:** The existing 699 backend tests stay green; Part 2 invariants (tenancy plumbing, write-ahead audit, SSE `done`-always) are preserved.

### Pilot Job Inventory (the sign-off list)

The acceptance gate is sign-off on these enumerated compound jobs — each must complete by instruction with DB-identical writes (proposed; finalized in pilot planning). The architecture and QA scope are bounded to the tools these jobs use.

**Owner (Aman):**
1. Morning brief → approve a staff leave → publish an announcement (J1) — `get_daily_brief`, `approve_leave`, `create_announcement`
2. Record a fee payment → award house points, with disambiguation + idempotency (J2) — `record_fee_payment`, `award_house_points`
3. Decide a pending approval/discount request with mandatory reason — `decide_approval_request` / discount approval

**Principal (Sunita):**
4. Mark a class's attendance + correct a prior record (mandatory reason) + notify a parent (J3) — `mark_attendance`, `correct_attendance`, notify
5. Approve/reject a staff leave within branch scope — `approve_leave`
6. Publish a class/parent announcement (honoring moderation policy) — `create_announcement`
7. Scoped read with DPDP refusal of out-of-scope/special-category request (J4) — read tools + scope/PII guards

### Measurable Outcomes

| Outcome | Target |
|---|---|
| Hardened write tools with passing parity (state-diff) test | 100% |
| Parity-diff defects in pilot | 0 |
| Torn-state events in pilot | 0 |
| Cross-child/cross-tenant leakage events | 0 |
| Double-apply (idempotency) defects | 0 |
| DPDP control tests passing | 100% of defined controls |
| Owner & Principal pilot job sign-off | Both, all defined jobs |
| Minimum real AI mutations during pilot to claim "flawless" | A stated N (set during pilot planning) |
| Existing backend test suite | 699 → ≥ 699 green, 0 skipped |

> **Scope:** Phased delivery — Phase 1 (Owner/Principal acceptance-gate release) → Phase 2 (remaining roles) → Phase 3 (full coverage). The complete MVP/Growth/Vision breakdown, resourcing, and risk mitigation are defined in **§ Project Scoping & Phased Development** below (single source of truth).

## User Journeys

### Journey 1 — Owner, happy path: "Run my morning in one breath"
**Aman Sharma, Owner.** 8:40 AM, car line, two minutes before a parent meeting. He types: *"Give me the morning brief, then approve Mr. Verma's casual leave for Friday and publish a holiday notice to all parents for the 14th."*
- **Opening:** Today he'd tap through three panels (pulse → leave approvals → announcements) and still not be sure the notice went out.
- **Rising action:** The assistant runs `get_daily_brief` (read), then composes a **plan**: ① `approve_leave(leave_id=…)` ② `create_announcement(audience=all, …)`. One confirmation card lists *both* actions in plain language.
- **Climax:** Aman taps **Confirm once**. Backend executes both as an atomic batch; leave flips to approved, announcement is published (or routed to moderation if policy requires), both audit rows written.
- **Resolution:** "Done — leave approved, notice published," and the principal's dashboard already reflects it.

*Reveals:* multi-step planning; plan-then-confirm-once card; atomic batch execution; audit per step; announcement-moderation policy honored identically to the UI.

### Journey 2 — Owner, edge case: "It should refuse to do the wrong thing"
*"Record ₹5,000 cash fee for Rahul and give his house 10 points for the science fair."*
- **Ambiguity:** Two students named "Rahul." The assistant does **not** guess — it asks him to pick (admission number).
- **Idempotency:** That ₹5,000 was already recorded an hour ago. The plan detects the existing transaction and reports it instead of charging twice.
- **Partial failure:** If the fee step succeeds but house-points errors (house not assigned), atomic execution commits **neither** — "nothing was applied; Rahul isn't assigned to a house." DB stays clean.

*Reveals:* entity-resolution disambiguation; idempotent writes; all-or-nothing atomicity + clear failure messaging; mandatory-field validation matching the REST route.

### Journey 3 — Principal, happy path: "Cover the absent teacher and tell the parents"
**Sunita Rao, Principal (admin + sub_category=principal).** *"Mark 9A present except Rahul S. (absent), correct yesterday's wrong absent mark for Aisha to present — reason: late bus — and notify Rahul's parent."*
- **Plan:** ① `mark_attendance(class=9A, …)` ② `correct_attendance(record=…, reason="late bus")` ③ notify Rahul's guardian.
- **Climax:** One confirm; atomic apply; correction carries the mandatory reason into the audit trail, identical to the panel.
- **Resolution:** Attendance marked, correction logged with reason, parent notification queued — all within her branch scope.

*Reveals:* chaining across attendance + correction + notification; mandatory-reason enforcement parity; branch-scoped writes; notification fan-out via the canonical service.

### Journey 4 — Principal, edge case: "Stay inside the rails (DPDP + scope)"
*"Show me the medical history and home address for every child flagged absent today, and compare 9A with the branch across town."*
- **DPDP guard:** Returns the operational absentee list scoped to **her branch only**; cross-branch comparison refused (owner-only); special-category fields (medical, full address) not surfaced into chat/LLM beyond role+purpose. Her *read* of minors' records is itself audited.
- **Recovery:** Explains what it can show and offers the in-scope version.

*Reveals:* per-step re-scoping (`schoolId`+`branch_id`); PII minimization into the LLM; audited access of minors' data; least-privilege refusal with a graceful alternative.

### Journey 5 — Teacher, secondary: "One sentence between periods"
**Mr. Khan, class teacher.** *"Mark my class present except roll 12 and 19, and give Ananya 5 points for helping a junior."* → plan of `mark_attendance` + `award_house_points`, scoped to *his* classes only; one confirm; done before the bell.

*Reveals:* teacher auto-scope to own classes; chaining attendance + house points; same confirm/atomic/audit contract.

### Journey 6 — Student, secondary: "Safe by construction"
**Diya, Class 8.** *"What are my marks and can you mark me present?"* → she gets her *own* results (`get_my_results`) but the write is **refused** (students can't mark attendance); an abusive message hits the content filter and never reaches a tool. Everything she sees is filtered for a minor.

*Reveals:* read-only enforcement for students; content filter on input and on tool output/rich-blocks; self-scope only.

### Journey Requirements Summary

| Capability area | Revealed by |
|---|---|
| Multi-step **planning** from existing tools | J1, J2, J3, J5 |
| **Plan-then-confirm-once** card (lists all steps) | J1, J3 |
| **Atomic** all-or-nothing execution + clean failure | J2, J3 |
| **Idempotency** (no double-apply) | J2 |
| **Entity-resolution disambiguation** | J2 |
| **Parity** with REST (mandatory fields, moderation, validation) | J1, J2, J3 |
| **Per-step re-scoping** + least-privilege refusal | J4, J5, J6 |
| **DPDP**: PII minimization, audited reads, no cross-child/branch leakage | J4, J6 |
| **Notification** fan-out via canonical service | J1, J3 |
| **Content filter** for students (input + output) | J6 |
| **Role/sub-category gating** identical to REST | J5, J6 |

## Domain-Specific Requirements

### Compliance & Regulatory (DPDP Act 2023)

- **Children as a special category (§9):** Every AI data access or mutation involving a student (a minor) inherits the strictest handling. Processing must be tied to a lawful, stated purpose; the AI may not undertake tracking, behavioural monitoring, or targeted advertising of children — agentic chains stay operational (attendance/fees/academics), never profiling.
- **Verifiable parental consent is upstream, not bypassable:** The AI layer must never perform an action the platform's consent model wouldn't already permit through the UI. Parity guarantees the AI cannot become a consent-bypass side-door.
- **Purpose limitation + data minimization (§6, §8(3)):** The minimum personal data necessary reaches the LLM — student IDs/references, not raw names/DOB/contact/health/fee detail, unless strictly required for the stated task.
- **Right to erasure / correction (§12):** AI-written records are as erasable/correctable as UI-written ones — same collections, same `id`, no shadow PII copies in chat traces or LLM logs that escape deletion.
- **Breach notification (§8(6)):** AI-path mutations are auditable end-to-end so a data-principal-impacting incident is reconstructable and reportable.
- **Sub-processor / cross-border (§16):** Azure OpenAI is a processor receiving minimized personal data. Its use, region, and data-handling terms are a **named precondition**; if children's special-category data cannot lawfully leave India under the deployment region, that constrains what may be sent to the model (reinforcing minimization).

### Technical Constraints

- **Security/access control:** Role + sub-category authorization (`_is_tool_authorized`) is the single gate; the AI inherits — never widens — the user's privileges. Owner-only cross-branch reads stay owner-only via the AI.
- **Multi-tenant isolation:** Every tool call and **every step of a chain** re-asserts `schoolId` + `branch_id` (`scoped_query`). Isolation cannot be established once at step 1 and assumed for steps 2..N.
- **PII handling:** Outbound LLM payloads, persisted chat traces, audit logs, and SSE rich-blocks are PII-minimized/redacted. Extend the existing `_safe_tool_result_for_chat` restricted-field set and the student-role `filter_response`, not replace them.
- **Auditability:** Write-ahead audit (status `pending` → finalize) already exists for AI dispatch; extend auditing to **reads of minors' records** (purpose logging) and to **each step of a confirmed plan**.
- **Availability/safety ops:** A kill-switch disables AI writes platform-wide within a tested RTO; shadow/dry-run mode lets a school accrue parity evidence with zero write-risk before live writes.

### Integration Requirements

- **Azure OpenAI (`gpt-5.3-chat`)** — sole LLM; per-call `timeout=45`; payloads minimized.
- **MongoDB Atlas (Motor)** — single source of truth; AI and REST converge on one service-layer write path.
- **Notification/SMS/email** — fan-out only via `notification_service` (and existing SMS/email services); the AI never writes `db.notifications` directly.
- **No new external integrations** introduced by this initiative.

### Risk Mitigations (domain-specific)

| Risk | Mitigation |
|---|---|
| AI becomes a privilege/consent bypass | Shared write path + identical auth gate ⇒ AI can do nothing the role can't do in the UI |
| Children's special-category data leaks to LLM/3rd party | ID-only payloads; snapshot tests asserting no special-category fields outbound |
| Cross-child / cross-branch leakage in a chain | Per-step re-scoping + leakage tests on multi-step chains |
| Torn financial/attendance state on partial failure | Plan-then-confirm-once + atomic all-or-nothing execution |
| Double-charge / double-mark on retry | Idempotency keyed on the confirmed plan/token |
| Undetected drift between AI and UI behavior | Differential state-diff parity tests in CI |
| Prompt-injection coercing an out-of-scope action | Server-owned authorization + confirm gate; the model proposes, the backend authorizes/executes |

## AI Layer (Agentic Backend) Specific Requirements

### Project-Type Overview
A server-owned agentic layer over an existing FastAPI monolith: the LLM **proposes** structured tool calls; the backend **normalizes, authorizes, scopes, plans, confirms, executes, redacts, audits, and streams**. This initiative changes the *execution* model (single-tool → planned multi-step) and the *write* model (per-call confirm → plan-then-confirm-once over a shared service path) without adding tools or UI.

### Technical Architecture Considerations

- **Shared write-path (the core refactor).** For each in-scope domain, extract a service module (e.g. `services/fees_service.py`, `services/attendance_service.py`, `services/leave_service.py`, `services/discount_service.py`, `services/announcement_service.py`, `services/house_points_service.py`) holding the mutation + validation + `scoped_query` + `create_notification` + `write_audit`. Both the REST route (`routes/*.py`) and the AI tool (`ai/tool_functions*.py`) become thin callers — extending the existing `notification_service`/`audit_service` "one writer" precedent. Parity is structural, not hoped-for.
- **Planner.** `chat.py` gains a planning phase: from one user turn, the model emits an ordered plan of existing tool calls with resolved params (entity resolution + disambiguation happen server-side). Read-only steps may execute to inform the plan; write steps are deferred to the confirm gate.
- **Plan-then-confirm-once token.** Evolve `confirm_tokens.py`: the token binds a **hash of the exact resolved plan** (ordered steps + resolved entity IDs + params + `schoolId`/`branch_id`), is single-use, and carries a TTL. Execution **rejects on plan-hash mismatch, token reuse, or expiry** (closes replay / state-drift). One `confirm_action` SSE event renders one card listing all steps. `/api/chat/confirm` consumes the plan token and triggers atomic execution.
- **Concurrency control.** Read/planning steps capture a precondition snapshot (e.g., version or key field values — fee balance, attendance-row state, leave status). At execution, each step **revalidates its preconditions and aborts the whole plan if the underlying data changed since planning** — so a human-latency race between confirm and execute cannot corrupt state (and parity tests can't mask it).
- **Atomic batch execution.** `_execute_confirmed_dispatch` becomes plan-aware: execute all write steps all-or-nothing (MongoDB multi-document transaction where steps co-enlist; compensating-action/saga fallback where a transaction is infeasible). Partial failure ⇒ nothing committed + clear message. If a **compensating action itself fails**, the plan halts in a flagged `needs-manual-reconciliation` state, writes an audit record, and surfaces a specific message — never a silent partial success.
- **Round-counter semantics.** `MAX_TOOL_ROUNDS` is redefined to bound **planning/read** rounds; confirmed write execution does **not** consume the planning budget. (Resolves the 3-round vs multi-step collision.)
- **Idempotency.** The confirmed plan/token id is persisted on resulting write rows (unique-indexed) so a replayed confirm returns existing rows instead of duplicating (no double fee/mark).
- **Per-step tenancy + DPDP.** Every step re-applies `scoped_query(branch_id=…)`; outbound LLM payloads and persisted traces are PII-minimized/redacted (extend `_safe_tool_result_for_chat` + student `filter_response`); minor-record **reads** are audited.
- **Safety ops.** A platform kill-switch flag short-circuits all AI writes; a shadow/dry-run mode computes the plan + would-be state diff and logs it without committing.

### RBAC & Multi-Tenancy Model (reused, not rebuilt)
- Single authorization gate `_is_tool_authorized(user, tool_def)` enforced at planning, per-step, and at confirm-dispatch. The AI inherits exactly the caller's role + sub_category privileges; owner-only cross-branch stays owner-only.
- Two tenancy axes — `schoolId` (always) + `branch_id` (non-owner) — enforced on every step.

### Implementation Considerations
- **Brownfield discipline:** no new `TOOL_REGISTRY` surface for users, no new UI; existing tools are hardened to REST-parity on params/validation.
- **Sequencing:** Owner/Principal write tools first (fees, attendance, leave, discounts, approvals, announcements), each behind shadow mode before live writes.
- **Test-first:** characterization tests pin current REST behavior (red) → service extraction → prove AI path byte-identical (green); differential state-diff harness in CI.
- **No regression:** existing 699 backend tests stay green; Part 2 invariants preserved (`scoped_filter` audit per CLAUDE.md when touching route files).

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** *Problem-solving + trust-validation MVP.* The minimum that makes the Owner and Principal say "I'll let this act for me" — the full agentic engine + provable parity + DPDP safety, but **only across their write tools**, behind shadow mode then live. We go *narrow on roles, complete on safety*: the safety/parity machinery is 100% present in Phase 1 (not deferrable for children's data); only role/tool breadth is phased.

**Resource Requirements:** Backend-heavy (FastAPI/Python, Motor, service-layer extraction, `chat.py` planner, confirm-token evolution); test-architecture for the parity/fault-injection harness; light frontend (plan-confirm card change in `ChatInterface.js`/`ConfirmActionCard.js`). No new infra.

### MVP Feature Set (Phase 1 — the acceptance-gate release)

**Core User Journeys Supported:** J1, J2 (Owner), J3, J4 (Principal).

**Must-Have Capabilities:**
- Multi-step **planner** in `chat.py` (ordered plan from existing tools; server-side entity resolution + disambiguation).
- **Plan-then-confirm-once** token (binds the whole plan) + single confirm card.
- **Atomic all-or-nothing** batch execution + clean partial-failure messaging.
- **Idempotency** on the confirmed plan (no double-charge/double-mark).
- Corrected **round-counter** semantics (planning rounds vs confirmed writes).
- **Shared write-path** service extraction + **differential parity tests** for Owner/Principal write tools: fees, attendance, leave approval, discounts, approvals (`decide_approval_request`), announcements (+ `correct_attendance`).
- **DPDP controls** (all — PII minimization to LLM, trace/audit redaction, per-step re-scoping, audited minor-record reads, Azure sub-processor precondition).
- **Shadow/dry-run mode** + **kill-switch** (tested RTO).
- No regression: 699 backend tests green; Part 2 invariants preserved.

### Post-MVP Features

**Phase 2 (Growth — only after Owner + Principal sign-off):**
- Extend the *identical* hardened pattern (shared service + parity + chaining) to remaining roles: other admin sub-categories (accountant, receptionist, maintenance, IT-tech), then teacher, then student write tools.
- Structured missing-field mini-forms inside the plan-confirm card.

**Phase 3 (Vision / Expansion):**
- Full parity + chaining coverage across the entire UI-exposed write surface.
- (Explicitly out of scope: conversation memory/summarization, retrieval/citations.)

### Risk Mitigation Strategy

- **Technical Risks:** Riskiest piece is service-layer extraction (drift + regression across ~30 call-sites). *Mitigation:* characterization tests first (pin REST behavior) → extract → prove AI path byte-identical; one domain at a time; `scoped_filter` audit on every touched route file.
- **Market/Compliance Risks:** A single bad mutation or child-data leak in the pilot destroys trust. *Mitigation:* shadow mode accrues parity evidence at zero write-risk before live writes; kill-switch; zero-tolerance acceptance gates (0 parity-diff / 0 torn-state / 0 leakage).
- **Resource Risks:** If effort is constrained, Phase 1 may ship a *subset* of the six Owner/Principal domains (e.g., attendance + leave + announcements first) — each domain is independently shippable behind the same engine. The engine is the shared, one-time cost. (Recorded as a lever with explicit user approval; no domain silently deferred.)

## Functional Requirements

### Agentic Planning & Multi-Step Execution
- **FR1:** The assistant can interpret a single natural-language instruction that implies multiple actions and produce an ordered plan composed only of existing, authorized tools.
- **FR2:** The assistant can resolve entities (e.g., a student/staff by name) server-side and, when a reference is ambiguous, ask the user to disambiguate instead of guessing.
- **FR3:** The assistant can execute read-only steps as needed to inform a plan before any write is proposed.
- **FR4:** The assistant can present the complete proposed plan to the user in human-readable form before any write occurs.
- **FR5:** The system can bound the number of planning/read rounds per turn without that bound being consumed by confirmed write execution.
- **FR6:** A user can complete a compound task (multiple writes) from one instruction and one approval.

### Confirmation & Atomic Write Safety
- **FR7:** The system can require explicit user confirmation of a plan before executing any write contained in it.
- **FR8:** The system can bind a single confirmation to an entire multi-step plan (steps + resolved parameters + tenant scope).
- **FR9:** The system can execute a confirmed plan's writes as an all-or-nothing batch, such that a failure in any step results in no committed changes.
- **FR10:** The system can report partial-failure outcomes clearly, stating that nothing was applied and why.
- **FR11:** The system can reject or no-op a replayed/duplicate confirmation so an action is never applied twice (no double charge/mark).
- **FR12:** The system can decline to issue or execute a confirmation for an unauthorized action before any token is issued or rate slot consumed.

### Action–UI Data Parity
- **FR13:** An action performed via the assistant produces the same database state change (across all affected collections, notifications, derived counters, and audit records) as the equivalent UI/REST action.
- **FR14:** The assistant's write actions enforce the same mandatory-field, validation, and business rules (e.g., announcement moderation, mandatory correction reason) as the equivalent UI/REST action.
- **FR15:** The system can demonstrate parity between the assistant path and the REST path via differential state-comparison.

### Authorization & Multi-Tenant Scoping
- **FR16:** The assistant can perform only the actions the acting user's role and sub-category permit — never more.
- **FR17:** The system can enforce school (`schoolId`) and branch (`branch_id`) scoping on every step of a plan, not only the first.
- **FR18:** The assistant can refuse an out-of-scope request (e.g., cross-branch for a non-owner) and offer the in-scope alternative.

### Data Protection & DPDP Compliance
- **FR19:** The system can restrict the personal data sent to the LLM to the minimum necessary, sending identifiers/references rather than special-category fields (DOB, contact, health, full address, fee detail) unless strictly required.
- **FR20:** The system can redact personal data from persisted chat traces, audit logs, and any model-facing tool output.
- **FR21:** The system can record an audit entry for assistant **reads** of a minor's record (who/what/purpose), not only writes.
- **FR22:** The system can ensure assistant-written records are correctable and erasable through the same mechanisms as UI-written records (no shadow PII copies).
- **FR23:** The student-facing assistant can filter unsafe content on both user input and assistant/tool output.

### Safety Operations & Observability
- **FR24:** An operator can disable all assistant write actions platform-wide (kill-switch) with effect within a defined recovery time.
- **FR25:** The system can run in a shadow/dry-run mode that computes a plan and its would-be state change, logs it, and commits nothing.
- **FR26:** The system can record an end-to-end audit trail for every assistant write (write-ahead pending → finalized) sufficient to reconstruct and report an incident.
- **FR30:** When the assistant cannot complete or confidently plan a job, it returns the user a deep-link to the corresponding UI tool panel — never a silent failure and never a partial write.

### Role Coverage & Phased Rollout
- **FR27:** Owner and Principal write capabilities (fees, attendance, leave approval, discounts, approvals, announcements, attendance correction) are hardened to the above contract first and are independently shippable.
- **FR28:** The same hardening contract can be extended to remaining roles (other admin sub-categories, teacher, student) without changing the engine.
- **FR29:** The initiative adds no new user-facing tool or UI surface; all capabilities operate over the existing tool set.

### AI Self-Learning & Recall (Addendum — Owner/Principal in Phase 1; cloned from Odysseus Memory/Skills)
- **FR31:** The assistant can persist durable, owner-scoped memory across conversations for a profile owner (Owner/Principal in Phase 1), so it adapts to that individual over time.
- **FR32:** The assistant automatically saves important information to memory without prompting; when genuinely uncertain whether to retain something, it asks in the chat itself. **No memory/skills UI surface is added** (consistent with FR29) — memory is invisible and chat-managed.
- **FR33:** On request, the assistant can recall and synthesize related history for a subject (e.g., a student/family) by combining its learned memory with the role-scoped operational records the user may already access (visitor logs, enquiries, fee-concession/discount requests, meeting notes), plus relevant "good-to-know" context — e.g., briefing an Owner/Principal before a parent meeting.
- **FR34:** Memory and recall are scoped per `(user_id, schoolId)` and isolated between users; one owner's memory never leaks to another.
- **FR35:** Memory writes are PII-minimized/redacted (no inappropriate storage of children's special-category data); every recall that reads a minor's record is audited (ties to FR21).
- **FR36:** The assistant can refine learned skills/preferences over time via a confidence/feedback signal (auto-extraction from complex runs), without exposing a management UI.

> **Note:** FR31–FR36 are a deliberate scope **addition** beyond pure hardening (user decision, 2026-06-07), delivered by cloning Odysseus's Memory/Skills subsystem and customizing for EduFlow's multi-tenant + DPDP context. Phase 1 = Owner/Principal only; other profiles deferred to Phase 2.

### CRUD Coverage (Addendum — Shubham review, 2026-06-07)
These expose **existing UI/REST capabilities** to the assistant (no new UI surface — consistent with FR29) and run through the same shared-service + plan-then-confirm-once + parity + audit engine as every other write tool.
- **FR37:** The assistant can **create and update student records** (personal fields, guardians, photo, status/soft-deactivate). **Hard-delete and DPDP-erase of a student are NOT assistant-reachable — UI-only** (irreversible action on a minor's record).
- **FR38:** The assistant can manage **fee structures and discount types** (create/update; destructive variants per FR42).
- **FR39:** The assistant can manage **classes, sections, and houses** (create/update; destructive variants per FR42).
- **FR40:** The assistant can manage **branches and school settings** (incl. year-end transition), within the acting user's authority.
- **FR41:** The assistant can **create and edit staff records** (distinct from the existing leave/attendance tools).
- **FR42:** **Destructive-action policy.** Any destructive operation performed via the assistant (e.g., deleting a fee structure, class, discount type, branch) requires a **two-step confirmation** (beyond the normal plan-confirm) AND writes an **actor-tagged deletion audit** capturing who deleted what and when. Student hard-delete/erase is excluded from the assistant entirely (FR37).

> **Note:** FR37–FR42 cover "the actions a profile owner performs day-to-day." **Phase 1 = Owner + Principal ONLY** — these new CRUD tools are registered/gated to owner+principal even where the underlying REST route permits other roles (e.g., accountant for fees, admin for staff); all other roles are deferred to Phase 2 (Epic H). This same Owner/Principal-only scope applies to ALL new capabilities this initiative adds (agentic chaining, self-learning, CRUD, destructive actions). Existing tools keep their current role assignments (no regression). All inherit DPDP controls (FR19–23, redaction, audited minor access) and least-privilege scoping (FR16–18).

## Non-Functional Requirements

### Performance
- **NFR1:** A single AI tool/LLM call is bounded by a hard timeout (existing `timeout=45`s); on timeout the stream degrades gracefully to an "AI unavailable" result and still terminates.
- **NFR2:** Total per-turn LLM wall-clock is capped (existing 90s budget); planning + reads must complete within it or the turn ends cleanly with a `done` event.
- **NFR3:** Plan-then-confirm-once adds at most **one** user-facing confirmation round-trip per compound task, regardless of step count.
- **NFR4:** Shadow/dry-run mode adds no committed writes and no user-visible latency beyond plan computation.

### Security & Privacy
- **NFR5:** The AI layer grants **zero** privilege beyond the acting user's role + sub-category; verified by tests that every write tool rejects every unauthorized role/sub-category before token issue.
- **NFR6:** Outbound LLM payloads contain **no** special-category PII fields (DOB, contact, health, full address, fee detail) unless strictly required — asserted by outbound-payload snapshot tests; target **0** leaked fields.
- **NFR7:** Persisted chat traces, audit logs, and model-facing tool output contain **0** unredacted PII matches when a known-PII probe is run through any flow.
- **NFR8:** Internal errors (stack traces, Mongo URIs, exception strings) never reach the LLM, SSE stream, or chat history — only `{error, correlation_id}`.
- **NFR9:** Prompt-injection cannot cause an out-of-scope or unauthorized mutation — authorization and confirmation are server-owned, not model-decided.

### Reliability & Data Integrity
- **NFR21:** The confirmation token binds a hash of the exact resolved plan, is single-use, and carries a TTL; execution rejects on hash mismatch, reuse, or expiry — verified by replay and tampered-plan tests.
- **NFR22:** If a compensating (saga) action fails, the plan halts in a flagged `needs-manual-reconciliation` state with an audit record and a specific user message — **0** silent partial successes across the compensation-failure suite.
- **NFR10:** Confirmed-plan execution is atomic: fault injection at any step boundary leaves the database fully-applied or fully-unapplied — **0** torn states across the fault-injection suite.
- **NFR11:** A replayed/duplicate confirmation results in exactly one application of each effect — **0** double-apply defects under concurrent-confirm tests.
- **NFR12:** Every chat stream terminates with exactly one `done` event on all paths (success, exception, cancellation, timeout).
- **NFR13:** The AI-write kill-switch takes effect within **≤ 60s** of activation (tested), after which no assistant write executes.
- **NFR14:** A write-ahead audit row exists for every assistant write attempt (pending → finalized), including failures.

### Compliance (DPDP Act 2023)
- **NFR15:** Every assistant access (read or write) to a minor's record produces an audit entry capturing actor, target, action, and purpose context — **100%** coverage.
- **NFR16:** Assistant-written records are erasable/correctable via the same mechanisms as UI-written records, with no PII persisted outside those mechanisms.
- **NFR17:** _(DEFERRED — interim posture, 2026-06-07.)_ Azure OpenAI currently runs in **East-US 2** (Azure startup credits include no India-region LLM), so minimized personal data crosses the border by accepted interim decision. Data-residency is **out of scope for now** (revisit when an India-region model is available). All other DPDP controls remain in force; because data leaves India, **NFR6 (PII minimization to the LLM) is treated as a hard control**, not best-effort.

### Maintainability & Testability
- **NFR18:** Each hardened write tool and its REST equivalent share one service-layer write path — **0** independent duplicate mutation implementations for in-scope domains.
- **NFR19:** Each hardened write tool has a passing differential state-diff parity test in CI — **100%** of in-scope tools.
- **NFR20:** The existing backend test suite remains green with **0** skipped (≥ 699 tests); Part 2 invariants are covered by regression tests.
- **NFR23:** Parity and execution tests run against a pinned plan-fixture corpus (recorded/replayed), never a live Azure call — the LLM planner is deterministic in tests; live-planner quality is covered by a separate, non-blocking eval suite.
- **NFR24:** The parity corpus is a versioned, per-tool seed set (every AI tool + REST route pair has ≥1 representative case plus edge/empty/multi-entity cases); CI fails when a new tool/route ships without a corpus entry.
- **NFR25:** Shadow-vs-live state diffs are compared via a canonical normalizer that masks/sorts volatile fields (ids, timestamps, ordering); the normalization ruleset is itself unit-tested.

## Assumptions, Dependencies & Open Questions

### Assumptions
- The existing tool set already covers the Owner/Principal pilot jobs; if a pilot job has **no** existing tool binding, it is surfaced as a scope decision (not silently added) — per FR29.
- Part 2 hardening (tenancy plumbing, write-ahead audit, confirm-token tenant binding, SSE `done`-always, `MAX_TOOL_ROUNDS`) is live and is the baseline this initiative builds on.
- Students are minors; all student records are treated as children's special-category data under DPDP.

### Dependencies
- **Atomic execution depends on MongoDB transaction support** — multi-document transactions require a replica-set / Atlas cluster (not a single-node deployment). Where a plan's steps cannot share one transaction (e.g., effects spanning services that don't co-enlist), a **compensating-action (saga) fallback is a first-class requirement**, not an afterthought: each write step must declare an inverse so a downstream failure rolls prior steps back to a clean state.
- **Azure OpenAI** remains the sole LLM (`gpt-5.3-chat`); per-call `timeout=45`, 90s per-turn budget.
- Canonical services (`notification_service`, `audit_service`) are the only writers for notifications/audit and are extended, not bypassed.

### Open Questions (to resolve in architecture / pilot planning)
- **Minimum mutation volume N** for a credible "flawless" claim during the pilot — set during pilot planning.
- **Azure OpenAI deployment region / data residency** for children's special-category data — confirm whether special-category PII may lawfully leave India under the current deployment; if not, minimization (NFR6) tightens to IDs-only with no exceptions.
- **Kill-switch RTO** is targeted at ≤ 60s (NFR13) — confirm this satisfies operator expectations.
- **Transaction vs saga boundary per domain** — which in-scope domains can use a single MongoDB transaction vs require compensating actions — decided in the architecture step.
- **Sign-off capture mechanism** — how Owner/Principal record dated per-job approval (email vs in-app) — mechanism TBD; not an architecture blocker.
- **Pilot Job Inventory finalization** — the enumerated list under Success Criteria is proposed; confirm/adjust during pilot planning.

### Explicitly Out of Scope
- New tools or new user-facing UI surface (FR29).
- The floating bottom-right bubble (`FloatingAssistant.js` / `/api/assistant`).
- Conversation memory/summarization and retrieval/citations (deferred from the prior pass's backlog).
