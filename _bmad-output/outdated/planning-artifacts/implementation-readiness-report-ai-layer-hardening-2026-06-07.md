---
stepsCompleted: ['step-01-document-discovery', 'step-02-prd-analysis', 'step-03-epic-coverage-validation', 'step-04-ux-alignment', 'step-05-epic-quality-review', 'step-06-final-assessment']
initiative: 'ai-layer-hardening'
documentsAssessed:
  - '_bmad-output/planning-artifacts/prd-ai-layer-hardening.md'
---

# Implementation Readiness Assessment Report

**Date:** 2026-06-07
**Project:** eduflow — AI Layer Hardening initiative

## Document Inventory

### PRD Documents
**Whole Documents:**
- `prd-ai-layer-hardening.md` (40 KB, 2026-06-07) — IN SCOPE for this assessment

_Other PRD files in planning-artifacts (`prd.md`, `prd-validation-report*.md`) belong to the completed platform-wide sweep and are NOT part of this initiative._

### Architecture Documents
- None for this initiative (the existing `architecture.md` is platform-wide). **Expected** — architecture has not been created yet; this readiness check runs deliberately pre-architecture.

### Epics & Stories Documents
- None for this initiative (existing `epic-part*.md` belong to the completed sweep). **Expected** — epics/stories not yet created.

### UX Design Documents
- None initiative-specific (existing `ux-design-specification.md` is platform-wide). The PRD specifies only a minimal frontend change (plan-confirm card); a dedicated UX spec is likely not required.

## PRD Analysis

### Functional Requirements (30)

**Agentic Planning & Multi-Step Execution**
- FR1: Interpret a single NL instruction implying multiple actions → ordered plan of existing, authorized tools.
- FR2: Resolve entities server-side; disambiguate on ambiguity instead of guessing.
- FR3: Execute read-only steps to inform a plan before proposing writes.
- FR4: Present the complete proposed plan in human-readable form before any write.
- FR5: Bound planning/read rounds per turn without confirmed-write execution consuming the budget.
- FR6: Complete a multi-write compound task from one instruction + one approval.

**Confirmation & Atomic Write Safety**
- FR7: Require explicit user confirmation of a plan before any contained write.
- FR8: Bind a single confirmation to the entire plan (steps + resolved params + tenant scope).
- FR9: Execute a confirmed plan all-or-nothing (failure ⇒ no committed changes).
- FR10: Report partial-failure clearly (nothing applied + why).
- FR11: Reject/no-op replayed confirmation (no double-apply).
- FR12: Decline unauthorized actions before token issue or rate-slot consumption.

**Action–UI Data Parity**
- FR13: Assistant action produces the same DB state change (all collections, notifications, derived counters, audit) as the REST/UI action.
- FR14: Same mandatory-field/validation/business rules as the REST/UI action.
- FR15: Demonstrate parity via differential state-comparison.

**Authorization & Multi-Tenant Scoping**
- FR16: Assistant performs only role+sub-category-permitted actions.
- FR17: Enforce schoolId+branch_id scoping on every step.
- FR18: Refuse out-of-scope requests with an in-scope alternative.

**Data Protection & DPDP**
- FR19: Restrict LLM-bound personal data to minimum necessary (IDs not special-category fields).
- FR20: Redact PII from traces, audit logs, model-facing tool output.
- FR21: Audit assistant reads of minor records (who/what/purpose).
- FR22: Assistant-written records correctable/erasable via the same mechanisms as UI (no shadow PII).
- FR23: Content filter on student input and assistant/tool output.

**Safety Operations & Observability**
- FR24: Operator kill-switch disabling all assistant writes within a defined RTO.
- FR25: Shadow/dry-run mode computes plan + would-be diff, commits nothing.
- FR26: End-to-end write-ahead audit (pending→finalized) for every assistant write.
- FR30: When the assistant cannot complete/plan a job, return a deep-link to the UI panel — no silent failure, no partial write.

**Role Coverage & Phased Rollout**
- FR27: Owner/Principal write capabilities hardened first; independently shippable.
- FR28: Same contract extensible to remaining roles without changing the engine.
- FR29: No new user-facing tool or UI surface.

Total FRs: 30.

### Non-Functional Requirements (25)

**Performance** — NFR1 (per-call timeout=45 + graceful degrade), NFR2 (90s per-turn budget), NFR3 (≤1 confirmation round-trip per compound task), NFR4 (shadow mode adds no committed writes/latency).
**Security & Privacy** — NFR5 (zero privilege beyond role/sub-cat), NFR6 (0 special-category PII outbound, snapshot-tested), NFR7 (0 unredacted PII in traces/audit/output), NFR8 (no internal errors leak; {error, correlation_id}), NFR9 (prompt-injection cannot cause out-of-scope mutation).
**Reliability & Data Integrity** — NFR21 (token binds plan-hash, single-use, TTL; reject mismatch/reuse/expiry), NFR22 (compensation failure ⇒ flagged needs-manual-reconciliation + audit + message; 0 silent partial success), NFR10 (0 torn states under fault-injection), NFR11 (0 double-apply under concurrent confirm), NFR12 (exactly one `done` event on all paths), NFR13 (kill-switch effective ≤60s, tested), NFR14 (write-ahead audit row for every write attempt incl. failures).
**Compliance (DPDP)** — NFR15 (100% audit coverage of minor-record access), NFR16 (erasable/correctable via same mechanisms), NFR17 (Azure sub-processor region/terms documented; data abroad limited per NFR6).
**Maintainability & Testability** — NFR18 (one shared service write-path; 0 duplicate mutation impls), NFR19 (100% in-scope tools have passing differential parity test), NFR20 (≥699 tests green, 0 skipped; Part 2 invariants regression-covered), NFR23 (deterministic planner harness — pinned plan fixtures, separate non-blocking eval suite), NFR24 (versioned per-tool parity corpus + CI drift gate), NFR25 (shadow-vs-live canonical normalizer, ruleset unit-tested).

Total NFRs: 25.

### Additional Requirements / Constraints
- **Assumptions:** existing tool set covers pilot jobs (else surfaced as scope decision); Part 2 hardening live; students treated as minors.
- **Dependencies:** atomicity needs MongoDB transactions (replica-set/Atlas) + saga fallback first-class; Azure OpenAI sole LLM; canonical notification/audit services extended not bypassed.
- **Open questions:** minimum mutation volume N; Azure region/residency for special-category data; kill-switch RTO confirmation; per-domain transaction-vs-saga boundary; sign-off capture mechanism; pilot-job-inventory finalization.
- **Out of scope:** new tools/UI; floating bubble (`FloatingAssistant.js`/`/api/assistant`); conversation memory/retrieval.
- **Pilot Job Inventory:** 7 enumerated Owner/Principal compound jobs (acceptance gate).

### PRD Completeness Assessment (initial)
The PRD is unusually complete for a brownfield hardening effort: requirements are testable and measurable, FRs trace cleanly to the six user journeys and the Pilot Job Inventory, NFRs quantify the success-criteria targets, and DPDP is decomposed into testable controls. Deferred items are consolidated and explicitly flagged as architecture/pilot-planning decisions (not silent gaps). No FR/NFR is vague or untestable. Primary residual risk is execution-layer design depth (transaction-vs-saga boundaries, plan-hash token schema, deterministic planner harness) — correctly deferred to architecture.

## Epic Coverage Validation

**Status: N/A at this stage — epics/stories not yet created (expected, pre-architecture).** Coverage is therefore 0% by definition. This section records the FR set that the upcoming epics ceremony MUST fully cover. No FR may be dropped.

### Coverage Statistics
- Total PRD FRs: **30** (FR1–FR30)
- FRs covered in epics: **0** (no epics yet)
- Coverage percentage: **0% — expected pre-epics**

### FRs awaiting epic coverage (the epic-creation checklist)
- **Planning/Execution engine:** FR1–FR6 — likely one "Agentic Planner & Plan-Then-Confirm Execution" epic.
- **Confirm/atomicity:** FR7–FR12 — same engine epic or a "Confirm-Token & Atomic Execution" epic.
- **Parity:** FR13–FR15 + FR27 — per-domain "Shared Write-Path Extraction + Parity Tests" epics (fees, attendance, leave, discounts, approvals, announcements, correction).
- **AuthZ/tenancy:** FR16–FR18 — cross-cutting; verified within each domain epic + engine epic.
- **DPDP:** FR19–FR23 — a "DPDP Controls" epic (PII minimization, redaction, minor-read audit, erasure parity, content filter).
- **Safety ops:** FR24–FR26 + FR30 — a "Safety Operations" epic (kill-switch, shadow mode, audit, UI deep-link fallback).
- **Rollout:** FR27–FR29 — phasing/sequencing constraints applied across epics; FR29 is a guardrail on every epic.

### Suggested epic shape (for the epics ceremony, not binding)
1. Agentic Planner + Plan-Then-Confirm-Once Execution Engine (FR1–FR12, FR16–FR18 cross-cutting)
2. Shared Write-Path & Parity — per Owner/Principal domain (FR13–FR15, FR27): fees, attendance, leave, discounts, approvals, announcements, correction
3. DPDP Controls (FR19–FR23)
4. Safety Operations & Observability (FR24–FR26, FR30)
5. (Phase 2) Role Extension (FR28)

## UX Alignment Assessment

### UX Document Status
**Not found (initiative-specific) — and a full UX spec is assessed as NOT required.** The initiative adds no new UI surface (FR29). The only frontend change is evolving the existing single-action confirm card (`frontend/src/components/ConfirmActionCard.js`, rendered by `ChatInterface.js`) into a **plan card that lists multiple steps** for one approval. The platform-wide `ux-design-specification.md` already governs the chat UI conventions.

### Alignment Issues
- None blocking. PRD ↔ UI intent is consistent: one confirmation per compound task (NFR3), human-readable plan (FR4).

### Warnings (low severity — fold into the engine epic, not a separate UX ceremony)
- **W1 — Multi-step plan card spec:** define how N steps render in one card (ordering, per-step summary, the single Confirm/Cancel), so it stays scannable for a busy Owner/Principal.
- **W2 — Partial-failure & reconciliation messaging:** specify the user-facing copy for "nothing was applied + why" (FR10) and the `needs-manual-reconciliation` state (NFR22).
- **W3 — Disambiguation prompt UX:** how the assistant asks the user to pick between ambiguous entities (FR2) within the chat flow.
- **W4 — Deep-link fallback UX:** how the "open the UI panel" fallback (FR30) is presented when the assistant can't complete a job.
- **Recommendation:** capture W1–W4 as a short UX subsection inside the planner/execution engine epic; no standalone UX spec needed.

## Epic Quality Review

**Status: N/A — no epics yet.** Converted to forward guidance so the upcoming `bmad-create-epics-and-stories` ceremony avoids the violations this initiative is structurally prone to:

### 🔴 Highest risk — "technical milestone" epic with no user value
The planner/execution engine (FR1–FR12) is the natural place to write a technical epic ("Build the planner"), which violates the user-value rule. **Remediation:** frame Phase-1 epics as **vertical slices** — e.g., *"Owner completes a two-step attendance-+-notify job by one instruction and one confirmation"* — where the slice includes a thin planner + one real domain end-to-end, delivering standalone value. The engine grows across slices rather than being a value-less upfront epic.

### 🟠 Forward-dependency / sequencing risks to enforce
- Domain parity epics (FR13–FR15) depend on the execution engine. Avoid a forward dependency by either (a) building engine + first domain (attendance or leave) as one value-delivering epic, or (b) explicitly sequencing the engine epic first and marking the dependency.
- DPDP (FR19–FR23) and Safety Ops (FR24–FR26, FR30) are cross-cutting — risk of being written as vague technical epics. **Remediation:** anchor them to user-visible outcomes (e.g., *"A parent's child's data is never exposed in another user's chat,"* *"An Owner can instantly disable AI writes if something looks wrong"*).

### 🟡 Brownfield-specific story types to include (commonly missed)
- **Characterization stories** pinning current REST behavior BEFORE service extraction (red→green parity, per CLAUDE.md test-first discipline).
- **Migration stories** for the idempotency unique-index on write rows and any plan/confirm-token schema change.
- **Integration stories** ensuring `scoped_filter`/`scoped_query` audit on every touched route file (CLAUDE.md mandatory check).
- **Regression guard** story: Part-2 invariants + existing 699 tests stay green.

### Best-practices checklist to apply when epics exist
Epic delivers user value · functions independently · stories right-sized · no forward dependencies · DB/index created when first needed · clear Given/When/Then ACs · full FR1–FR30 traceability.

## Summary and Recommendations

### Overall Readiness Status
**READY to proceed to Architecture.** (The PRD is the only artifact that exists for this initiative by design, and it is complete, internally consistent, and fully testable. "Missing" architecture/epics are the expected next stages, not gaps.)

### Assessment scope note
This check ran deliberately **pre-architecture**, so it validated PRD quality and forward-traceability rather than epic/story coverage. Epic coverage (0%) and epic quality (N/A) reflect that epics don't exist yet — not defects.

### Critical Issues Requiring Immediate Action
- **None.** No blocking issues found in the PRD.

### Findings carried forward (resolve in architecture, not blockers)
1. Execution-layer design depth — transaction-vs-saga boundary per domain, plan-hash confirm-token schema, optimistic-concurrency precondition model (PRD Open Questions).
2. Deterministic planner test harness + parity-corpus CI drift gate + shadow-vs-live canonical normalizer (NFR23–25) need a concrete test-architecture design.
3. DPDP preconditions — Azure OpenAI region/data-residency for special-category data; confirm before live LLM payloads.
4. Pilot-job-inventory finalization + sign-off capture mechanism (pilot planning).
5. UX micro-spec for the multi-step plan card (W1–W4) — fold into the engine epic.

### Recommended Next Steps
1. **Run `bmad-create-architecture`** — resolve the execution-layer Open Questions, design the planner/plan-confirm-token/atomic-saga model, shared service-layer extraction plan, and the test-architecture (parity harness + corpus gate + normalizer).
2. **Then `bmad-create-epics-and-stories`** — apply the forward guidance above (vertical-slice epics, no technical-milestone epic, brownfield characterization/migration/regression stories), with full FR1–FR30 traceability.
3. **Re-run this readiness check** after epics exist to validate coverage and epic quality for real.
4. Confirm the Azure region/residency precondition (3) before any live LLM payload work begins.

### Final Note
This assessment found **0 critical issues** and **5 forward items** (all correctly deferred to architecture/pilot-planning). The PRD is ready to drive architecture. — Assessed 2026-06-07.
