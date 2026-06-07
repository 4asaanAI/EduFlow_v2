---
stepsCompleted: ['step-01-init', 'step-02-context', 'step-03-starter', 'step-04-decisions', 'step-05-patterns', 'step-06-structure', 'step-07-validation', 'step-08-complete']
lastStep: 8
status: 'complete'
completedAt: '2026-06-07'
inputDocuments:
  - '_bmad-output/planning-artifacts/prd-ai-layer-hardening.md'
  - '_bmad-output/planning-artifacts/implementation-readiness-report-ai-layer-hardening-2026-06-07.md'
  - '_bmad-output/project-context.md'
  - 'backend/routes/chat.py'
  - 'backend/ai/tool_functions_v2.py'
  - 'backend/services/confirm_tokens.py'
workflowType: 'architecture'
initiative: 'ai-layer-hardening'
project_name: 'eduflow'
user_name: 'Abhimanyusingh'
date: '2026-06-07'
---

# Architecture Decision Document — EduFlow AI Layer Hardening

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements (30):** Seven capability areas. The architecturally load-bearing clusters:
- *Planning & Execution (FR1–FR6):* a server-side planner turns one instruction into an ordered plan of EXISTING tools; reads may run during planning; planning rounds are bounded separately from confirmed-write execution.
- *Confirmation & Atomicity (FR7–FR12):* one confirmation binds the whole plan; execution is all-or-nothing; replays never double-apply; unauthorized actions are rejected pre-token.
- *Parity (FR13–FR15, FR27):* AI write == REST write on full DB blast radius — achievable only via a shared write path, proven by differential state-diff.
- *AuthZ/Tenancy (FR16–FR18):* role+sub_category gate and schoolId+branch_id scoping re-applied per step.
- *DPDP (FR19–FR23):* PII minimization to LLM, redaction, per-step re-scoping, audited minor reads, erasure parity, content filter.
- *Safety-Ops (FR24–FR26, FR30):* kill-switch, shadow/dry-run, write-ahead audit, UI deep-link fallback.
- *Rollout (FR27–FR29):* Owner/Principal first; no new tools/UI.

**Non-Functional Requirements (25):** Integrity-and-compliance-dominated. Drivers of design:
- *Data integrity:* atomicity (NFR10), idempotency (NFR11), plan-hash token (NFR21), saga-failure reconciliation (NFR22).
- *Privacy/security:* zero-privilege-escalation (NFR5), no special-category PII outbound (NFR6), redacted stores (NFR7), no error leakage (NFR8), injection-safe (NFR9).
- *Compliance:* minor-access audit (NFR15), erasure parity (NFR16), Azure residency precondition (NFR17).
- *Maintainability/test:* one shared write path (NFR18), parity tests (NFR19), deterministic planner harness (NFR23), parity-corpus CI gate (NFR24), shadow normalizer (NFR25), no regression (NFR20).
- *Performance:* existing timeout/budget (NFR1–2), ≤1 confirmation per task (NFR3).

### Scale & Complexity
- Primary domain: **backend** (FastAPI 3.9 / Motor / MongoDB Atlas / Azure OpenAI), thin SSE + React confirm-card touch.
- Complexity: **High** — agentic execution mutating live regulated data with atomicity + compliance guarantees.
- Estimated architectural components: planner, plan/confirm-token store, atomic-executor (txn + saga), per-domain service layer (~6), DPDP redaction/scoping middleware, safety-ops (kill-switch/shadow), test harness (fixtures/corpus/normalizer).

### Technical Constraints & Dependencies
- Brownfield: preserve Part 2 invariants + 699 green tests; no new tools/UI; Python 3.9 (`from __future__ import annotations`).
- MongoDB multi-document transactions require a replica-set/Atlas cluster; saga fallback where steps can't co-enlist.
- Single LLM (Azure OpenAI `gpt-5.3-chat`); **open dependency:** deployment region/data-residency for children's special-category data.
- Canonical services (`notification_service`, `audit_service`) are the only writers — extend, not bypass.

### Cross-Cutting Concerns
Tenancy scoping (schoolId+branch_id) per step · PII minimization + redaction · write-ahead + access auditing · idempotency · plan-scoped confirm-gating · kill-switch/shadow toggles · zero-regression on existing suite.

## Starter Template Evaluation

**Not applicable — brownfield initiative.** This work extends an existing, deployed codebase with a fixed, established stack:
- Frontend: React 19 + CRACO + Tailwind v3 + shadcn/ui (plain JS, no TS)
- Backend: FastAPI 0.110 / Python 3.9 / Motor (MongoDB Atlas) / Pydantic v2 / python-jose
- LLM: Azure OpenAI `gpt-5.3-chat`; Infra: AWS Amplify (FE) + Elastic Beanstalk (BE)

No starter template is introduced; the initiative adds **no new technology, framework, or dependency** (per FR29 and the "harden existing only" constraint). The architectural foundation is the existing repo and the patterns codified in `project-context.md` and `CLAUDE.md`. Project initialization is therefore **not** a first story; the first stories are characterization tests + service-layer extraction (per the readiness report's brownfield guidance).

## Core Architectural Decisions

_Standard categories (DB: MongoDB Atlas + Motor; Auth: JWT + `require_*`; API: REST + SSE; Frontend: React 19 SPA; Infra: Amplify/EB) are **inherited unchanged** from the brownfield stack. The decisions below are the execution-layer changes this initiative introduces. Refined via party-mode review (Winston/Murat/Amelia)._

### Priority
- **Critical (block implementation):** AD1 Planner · AD3 Plan-confirm token · AD4 Atomic executor · AD7 Shared write-path · AD12 Real-Mongo test tier (gates AD4–AD6).
- **Important:** AD2 Round semantics · AD5 Concurrency · AD6 Idempotency · AD8 DPDP · AD9 Safety-ops · AD10 Test architecture · AD13 Epic sequencing.
- **Deferred (accepted interim):** AD11 Azure data-residency.

### AD1 — Agentic Planner (`ai/planner.py`; model proposes, server authorizes)
Invoked from `chat.py`. The LLM emits a structured **Plan**: `steps[] = {tool, params, kind: read|write, precondition?}`. Read steps may execute inline to inform the plan; write steps are collected, never executed here. Entity resolution + disambiguation run server-side via the existing scope-aware `_resolve_params`. Not a new tool. *(FR1–FR4)*

### AD2 — Round-counter semantics
`MAX_TOOL_ROUNDS` bounds **planning/read** iterations only; confirmed write execution (separate request) never consumes it. Add `MAX_PLAN_STEPS` (default 8) to bound plan size. *(FR5)*

### AD3 — Plan-then-confirm-once token (evolve `confirm_tokens.py`)
Token carries `plan` (ordered resolved steps) + `plan_hash` (sha256 over a **canonical, sorted-key serialization** of steps + entity IDs + `school_id`/`branch_id`) + `schema_version`. `issue_confirm_token` gains `plan`; single-use + TTL retained. `consume_confirm_token` adds **plan-hash revalidation** (409 on mismatch) alongside existing tenant binding, and the single-use guard covers the **whole plan**, not per-step. **Back-compat by data, not branching:** a missing `plan` = legacy single-action token; old tokens drain over one TTL window before the planner is enabled. *(FR7, FR8, NFR21)*

### AD4 — Atomic executor (`ai/plan_executor.py`, called by `_execute_confirmed_dispatch`)
`_execute_confirmed_dispatch` **always** builds a Plan (length-1 for a single legacy write) and calls `plan_executor.run()` — one code path, no `len==1` fork. Strategy:
- **Transaction-first:** all Mongo writes in one Motor multi-doc transaction. New `database.get_txn_session()` returns `_client.start_session()`; **`session=` is forwarded through `ScopedCollection`** so tenant (`schoolId`) scoping is preserved inside the txn. **Never** write via `get_raw_db()` in a txn (tenant leak). Atlas replica set required (✓).
- **Saga fallback** only for non-Mongo side effects (S3/SMS/email): sequential with declared compensating actions; on failure compensate in reverse; if a **compensation fails → `needs-manual-reconciliation`** state + audit + specific message (no silent partial success). *(FR9, FR10, NFR10, NFR22)*

### AD5 — Optimistic concurrency (distinct from AD3)
Each write step declares an explicit `precondition` in the Plan schema — prefer a monotonic `version`/`updatedAt` token over field snapshots. The executor re-reads inside the txn and aborts the whole plan if changed. **Division of labor:** `plan_hash` = identity/structure/tamper integrity; `precondition` = data-freshness/lost-update. They raise **distinct 409 variants** so the frontend distinguishes "re-confirm" (tampered) from "data moved — re-plan" (stale).

### AD6 — Idempotency
Per-step `idempotency_key = plan_token + step_index`, **unique-indexed** on the write rows (index added in `database.py → _create_indexes()`). Replay returns the existing row (no duplicate). *(FR11, NFR11)*

### AD7 — Shared write-path service layer (parity spine)
`services/<domain>_service.py` per Owner/Principal domain (fees, attendance, leave, discount, approvals, announcement, house_points, attendance-correction). Service signature: `op(db, actor_ctx, validated_params, *, session=None, idempotency_key=None)` → domain result, **raises domain exceptions (no `HTTPException`/`Depends`/`Request`)**. It owns validation + `scoped_query(branch_id=…)` write + `create_notification` + `write_audit`. The REST route keeps auth gate + parsing + domain-error→HTTP mapping; the AI tool is a thin adapter synthesizing `actor_ctx` from the chat user. **Critical:** `sub_category` authorization is **replicated in `_is_tool_authorized` (chat.py), not moved into the service** — else AI tools skip sub_category checks. Grep `scoped_filter(` in each handler before moving (CLAUDE.md Parts 9–13 rule). *(FR13–FR15, FR27, NFR18)*

### AD8 — DPDP controls
- `redact_for_llm()` on tool results before they re-enter the LLM and before trace persistence (IDs, not special-category fields) — extends `_safe_tool_result_for_chat` + restricted-field set. **Hard control** (data leaves India — see AD11).
- Per-step re-scoping: executor re-applies `scoped_query(branch_id=…)` on every step.
- `audit_read()` on student-record tool reads (via `write_audit`).
- Erasure parity: automatic via shared collections/ids. *(FR19–FR23, NFR6/7/15/16)*

### AD9 — Safety operations
- **Kill-switch:** `db.system_flags.ai_writes_enabled`, short-TTL cached read (≤60s RTO), checked in `_execute_confirmed_dispatch` before execution; off ⇒ reject writes with a clear message.
- **Shadow/dry-run:** explicit `dry_run` flag passed into the executor (not a bare abort). Service fns return intended-mutation descriptors collected into a diff; run inside a txn then abort; **saga/side-effect steps hard-gated to no-op-with-record** in dry-run. Stated scope: dry-run validates Mongo-diff + plan shape, **not** side-effect behavior. *(FR24, FR25, NFR4/NFR13/NFR25)*

### AD10 — Test architecture
- **Deterministic planner:** recorded **plan fixtures** (planner mocked); live planner in a separate **non-blocking eval suite**. *(NFR23)*
- **Parity harness (dual-entrypoint):** `tests/backend/parity/` runs the REST handler via `TestClient` (full middleware/auth) vs the AI tool via its real dispatch path, normalizing out the confirm-token round-trip, then state-diffs via a **canonical normalizer** (masks ids/timestamps/order; ruleset unit-tested). Calling the shared service fn from both is a tautology — the gate must be dual-entrypoint. One cheap direct-fn smoke test allowed. **CI drift gate** fails if a write tool/route lacks a corpus entry; normalizer/corpus pinned, re-baseline is a deliberate reviewed step. *(NFR19/24/25)*
- Atomicity/idempotency/shadow tests live on the real-Mongo tier (AD12).

### AD11 — Azure data-residency (DEFERRED — accepted interim, 2026-06-07)
`gpt-5.3-chat` runs in **East-US 2** (Azure startup credits include no India-region LLM). Cross-border transfer of **minimized** personal data is accepted for now; residency is **out of scope** until an India-region model is available. All other DPDP controls remain in force; AD8 `redact_for_llm()` is treated as a **hard control** because data leaves India. *(NFR17 — deferred)*

### AD12 — Real-Mongo replica-set test tier (gating dependency)
FakeDb (`tests/backend/conftest.py`) has no sessions/transactions/unique-index enforcement, so AD4/AD5/AD6/AD9 cannot be honestly verified on it. Add a **`@pytest.mark.mongo_real` tier** backed by an ephemeral Mongo started as a single-node replica set (testcontainers or CI `--replSet` + `rs.initiate()`), run nightly + on AI-layer paths. FakeDb keeps the 699 + planner-mocked/logic tests; add a `session=`-tolerant shim to `FakeCollection` (asserts nothing about atomicity). Add an index-existence introspection guard. **This tier gates AD4–AD6** and must be built first within Epic B.

### AD13 — Epic sequencing (hard dependency chain)
- **Epic A — Shared write-path extraction (AD7):** pure refactor, REST tests stay green, zero behavior change. Ship first; de-risks everything.
- **Epic B — Transactional executor + idempotency + test substrate (AD4, AD5, AD6, AD12):** the session/scoping work and real-Mongo tier live here.
- **Epic C — Planner + multi-step confirm token (AD1, AD2, AD3):** depends on B.
- **Epic D — DPDP + Safety + Parity harness (AD8, AD9, AD10):** cross-cutting, lands last.

### AD14 — Cross-cutting decisions (from adversarial audit, 2026-06-07)
- **Notifications/side-effects fire AFTER commit.** `create_notification` Mongo writes enlist in the plan transaction (roll back on abort). Non-Mongo side effects (SMS/email/SSE) are **saga steps executed only after the transaction commits** — a rolled-back plan sends nothing. No "fee recorded" SMS for a payment that didn't persist.
- **A confirmed plan = ONE AI rate-limit dispatch.** The existing per-user-per-hour limiter (Story 7-48) counts a whole plan as a single dispatch (one user action), checked once at `/confirm` before execution — not per step.
- **Plan-scoped confirm-token TTL.** Plans accrue planning latency before the card renders; the token TTL clock starts at issue (card render), and "token expired while reading the plan" returns a clear, re-planable message (not a generic 400). Tune TTL for plans if 5 min proves tight.
- **Idempotency parity with REST.** Where a REST route has a content-based idempotency key, the AI path's key derivation must MATCH it (in addition to `plan_token:step_idx`) so AI and REST dedupe against the *same* key — closing the "two separate AI instructions double-charge" gap.
- **Partial-plan authorization = reject whole plan.** If ANY step is outside the user's role/sub_category, the entire plan is rejected with which-step feedback — never silently truncated to the allowed steps.
- **`actor_ctx` contract is pinned** to exactly what services consume: `{user_id, role, sub_category, school_id, branch_id, actor_name}` (+ `now_fn` injection for testability). Services needing more must extend the dataclass, not read `Request`.

### Decision Impact & Cross-Component Contract
The `(db, actor_ctx, validated_params, session=, idempotency_key=)` service signature (AD7) is the contract tying AD4 (session), AD6 (idempotency_key), AD8 (scope in actor_ctx), and parity (AD10) together. Build order A→B→C→D; AD12 inside B is the test gate for the integrity guarantees.

## Implementation Patterns & Consistency Rules

_General platform conventions are inherited from `CLAUDE.md` and `project-context.md` (DB/API/naming/test rules) and are NOT restated. Below are the NEW patterns specific to this initiative — the places multiple AI dev agents could implement inconsistently._

**Critical conflict points identified: 8**

### P1 — Service-layer signature (the one true write path)
```python
async def <verb>_<noun>(db, actor_ctx, params, *, session=None, idempotency_key=None) -> dict:
    # validate → scoped_query(branch_id=actor_ctx.branch_id) write (pass session=) →
    # create_notification → write_audit; raise Domain*Error on failure (NEVER HTTPException)
```
- `actor_ctx` = small dataclass `{user_id, role, sub_category, school_id, branch_id}`, synthesized identically by the REST adapter and the AI-tool adapter.
- Services in `backend/services/<domain>_service.py`; one mutation = one public fn.
- **Anti-pattern:** raising `HTTPException`, importing `fastapi`, or reading `Request` inside a service.

### P2 — Adapter rule (REST + AI tool are thin)
- REST route: `Depends(require_*)` → parse → `try: service(...) except Domain*Error → HTTPException`. No DB mutation in the route.
- AI tool: build `actor_ctx` from chat user → `service(...)`; return `_ok()/_empty_result()` shape. No DB mutation in the tool.
- **Sub_category authorization stays in `_is_tool_authorized` (chat.py) AND `require_*` (route)** — never relocated into the service.

### P3 — Plan & step schema (canonical)
```json
{"plan_id":"<uuid>","steps":[{"idx":0,"tool":"mark_attendance","kind":"write",
  "params":{...},"precondition":{"collection":"...","id":"...","version":"<int|updatedAt>"}}],
 "school_id":"...","branch_id":"..."}
```
- `kind ∈ {read, write}`; `precondition` required on every `write` step (AD5). One canonical builder in `ai/planner.py`.

### P4 — `plan_hash` canonicalization
`sha256(json.dumps(plan, sort_keys=True, separators=(",",":")))` over resolved steps + entity IDs + tenant. The **same** helper computes it at issue and consume (lives in `confirm_tokens.py`, not the planner).

### P5 — Idempotency key format
`idempotency_key = f"{plan_token}:{step_idx}"`, stored on each write row, unique-indexed in `database.py → _create_indexes()`. Duplicate-key ⇒ "already applied → return existing row," never a surfaced error.

### P6 — Transaction & session threading
- Sessions only via `database.get_txn_session()`; thread `session=` through `ScopedCollection` — **never** `get_raw_db()` in a txn.
- `dry_run: bool` is an explicit executor arg; in dry-run, Mongo writes run in an aborted txn and **saga/side-effect steps no-op-with-record**.

### P7 — Error / 409 taxonomy (frontend must distinguish)
- `plan_hash` mismatch → `409 {code:"plan_tampered"}` → FE "re-confirm".
- `precondition` stale → `409 {code:"plan_stale"}` → FE "data changed — re-plan".
- compensation failure → `{code:"needs_manual_reconciliation"}` + audit.
- Internal errors stay opaque: `{error, correlation_id}` (Part 2 P3 invariant — unchanged).

### P8 — Test conventions
- Real-Mongo tests carry `@pytest.mark.mongo_real`; everything else stays on FakeDb.
- Parity tests in `tests/backend/parity/<domain>_parity_test.py`, **dual-entrypoint** (TestClient REST vs AI dispatch), diff via shared normalizer `tests/backend/parity/normalizer.py`.
- Every new test file: `from __future__ import annotations` + `pytestmark = pytest.mark.asyncio`.

### Enforcement
All dev agents MUST: route every in-scope mutation through a P1 service; never duplicate a mutation in both tool and route; add a parity-corpus entry for any touched write tool/route (CI drift gate); preserve `scoped_filter`/`scoped_query` audit on touched route files; keep the 699 suite green.

## Project Structure & Boundaries

### Directory Structure (existing tree; ➕ new, ✏️ modified)

```
backend/
├── server.py
├── database.py                         ✏️  get_txn_session(); ScopedCollection forwards session=; new idempotency index in _create_indexes()
├── tenant.py                           (unchanged — scoped_query reused)
├── routes/
│   ├── chat.py                         ✏️  planner invocation; MAX_TOOL_ROUNDS/MAX_PLAN_STEPS; _execute_confirmed_dispatch → builds Plan, calls plan_executor; kill-switch check; _is_tool_authorized unchanged gate
│   ├── fees.py · attendance.py · staff.py · academics.py · operations.py · issues.py   ✏️  handlers become thin adapters over services/*
│   └── ...
├── ai/
│   ├── planner.py                      ➕  builds the resolved Plan (AD1, P3)
│   ├── plan_executor.py                ➕  txn-first + saga + dry_run + precondition revalidation (AD4/AD5/AD9)
│   ├── redact.py                       ➕  redact_for_llm() (AD8)  [or extend existing _safe_tool_result helpers]
│   ├── tool_functions.py / _v2.py      ✏️  write tools become thin adapters over services/*
│   ├── prompts.py                      ✏️  planner system-prompt addition (no new tools)
│   └── ...
├── services/
│   ├── notification_service.py · audit_service.py   (precedent — unchanged)
│   ├── confirm_tokens.py               ✏️  plan + plan_hash + schema_version; consume revalidates plan_hash; canonical hash helper (AD3/P4)
│   ├── fees_service.py                 ➕  AD7 (P1 signature)
│   ├── attendance_service.py           ➕
│   ├── leave_service.py                ➕
│   ├── discount_service.py             ➕
│   ├── approvals_service.py            ➕
│   ├── announcement_service.py         ➕
│   ├── house_points_service.py         ➕
│   └── actor_context.py                ➕  actor_ctx dataclass (P1)
├── migrations/
│   └── 0NN_ai_idempotency_index.py     ➕  unique idempotency_key index + run_all.py entry (AD6)
└── config/
    └── system_flags (db.system_flags.ai_writes_enabled)   ➕  kill-switch (AD9)

frontend/src/components/
├── ChatInterface.js                    ✏️  render multi-step plan card
└── ConfirmActionCard.js                ✏️  list N steps; plan_tampered/plan_stale/needs_reconciliation messaging (P7, W1–W4)

tests/backend/
├── conftest.py                         ✏️  FakeCollection session= shim (no-op, asserts nothing about atomicity)
├── parity/
│   ├── normalizer.py                   ➕  canonical state-diff normalizer (AD10/P8)
│   ├── <domain>_parity_test.py         ➕  dual-entrypoint REST vs AI tool (per domain)
│   └── corpus/                         ➕  per-tool seed cases + CI drift gate
├── mongo_real/                         ➕  @pytest.mark.mongo_real: atomicity, concurrency, idempotency, shadow (AD12)
└── (existing 699 tests unchanged)
```

### Architectural Boundaries
- **API boundary:** unchanged surface — `/api/chat/*` (SSE + `/confirm`) and existing REST routes. No new endpoints, no new tools.
- **Service boundary (new seam):** `services/<domain>_service.py` is the single writer; routes and AI tools are adapters above it. Services raise domain exceptions, never `HTTPException`.
- **Execution boundary:** planner (decides) → confirm token (gates) → `plan_executor` (commits atomically). The model never writes; the server authorizes + executes.
- **Tenancy boundary:** `scoped_query(branch_id)` inside services + per-step re-scoping in the executor; `session=` flows through `ScopedCollection` (never `get_raw_db()` in a txn).
- **Data boundary:** writes hit existing collections via existing ids (erasure parity); new artifacts are the `idempotency_key` field/index, `confirm_tokens` plan fields, and `system_flags`.

### Epic → Structure Mapping
- **Epic A (service extraction, AD7):** `services/*_service.py`, `actor_context.py`; thin-adapter edits to `routes/*` + `tool_functions*`; characterization parity tests.
- **Epic B (executor + idempotency + test substrate, AD4/5/6/12):** `ai/plan_executor.py`, `database.py` (session + index), `migrations/0NN_*`, `tests/backend/mongo_real/`, `conftest.py` shim.
- **Epic C (planner + token, AD1/2/3):** `ai/planner.py`, `routes/chat.py`, `services/confirm_tokens.py`, `prompts.py`.
- **Epic D (DPDP + safety + parity, AD8/9/10):** `ai/redact.py`, `system_flags` kill-switch + shadow in `plan_executor.py`, `tests/backend/parity/` + `ConfirmActionCard.js`/`ChatInterface.js`.

### Integration Points & Data Flow
User msg → `chat.py` planner (reads run, writes deferred) → resolved Plan + `plan_hash` → `issue_confirm_token` → SSE `confirm_action` (one card) → user confirms → `/confirm` → `_execute_confirmed_dispatch` (kill-switch + rate + token consume + plan-hash + write-ahead audit) → `plan_executor.run()` (txn: per-step re-scope → precondition check → service writes with `session`+`idempotency_key` → notifications/audit) → commit/abort → result streamed.

## Architecture Validation Results

### Coherence Validation ✅
- **Decision compatibility:** No contradictions. The `(db, actor_ctx, params, session=, idempotency_key=)` service contract (AD7) is the single seam tying transactions (AD4), idempotency (AD6), scoping/DPDP (AD8), and parity testing (AD10). Plan-token (AD3) + executor (AD4) + concurrency (AD5) compose cleanly: token = identity integrity, precondition = freshness, executor = atomic commit.
- **Pattern consistency:** P1–P8 implement the ADs without conflict and inherit (don't override) the platform conventions in `CLAUDE.md`. The 409 taxonomy (P7) maps 1:1 to AD3/AD5/AD4.
- **Structure alignment:** Project tree places each AD in a concrete file; new seams (`services/*`, `ai/planner.py`, `ai/plan_executor.py`) respect existing boundaries; no new endpoints/tools (FR29).

### Requirements Coverage Validation ✅

**Functional (FR1–FR30):**
- Planning/Execution FR1–FR6 → AD1, AD2.
- Confirm/Atomicity FR7–FR12 → AD3, AD4; FR12 → existing `_is_tool_authorized` pre-token gate (AD7/P2).
- Parity FR13–FR15 → AD7 + AD10.
- AuthZ/Tenancy FR16–FR18 → AD7/P2 + AD8 per-step re-scoping.
- DPDP FR19–FR23 → AD8.
- Safety-Ops FR24–FR26, FR30 → AD9 (kill-switch/shadow), existing write-ahead audit, P7 fallback.
- Rollout FR27–FR29 → AD13 sequencing; FR29 guardrail across all ADs.

**Non-Functional (NFR1–NFR25):**
- Perf NFR1–NFR4 → inherited timeout/budget + AD2 + AD9 dry-run.
- Security/Privacy NFR5–NFR9 → AD7/P2 (priv), AD8 (PII/redaction), inherited P3 error-opacity.
- Integrity NFR10/11/21/22 → AD4/AD5/AD6/AD3.
- Compliance NFR15–NFR17 → AD8; NFR17 **deferred** (AD11, accepted).
- Maintainability/Test NFR18–NFR20, NFR23–NFR25 → AD7, AD10, AD12.

### Implementation Readiness Validation ✅
Decisions, patterns, and structure are concrete enough for parallel dev agents; the lone deferred item (residency) is explicitly out of scope and non-blocking.

### Gap Analysis Results
- **Critical:** none.
- **Important:** AD12 real-Mongo tier must be stood up early in Epic B (gates AD4–AD6 verification). Domain dataclass `actor_ctx` shape must be finalized in Epic A as the shared contract.
- **Nice-to-have:** consolidated 409 error-code enum shared FE/BE; planner eval-suite metrics dashboard (post-MVP).

### Architecture Completeness Checklist
**Requirements Analysis** — [x] context analyzed · [x] scale/complexity assessed · [x] constraints identified · [x] cross-cutting concerns mapped
**Architectural Decisions** — [x] critical decisions documented · [x] stack specified (inherited) · [x] integration patterns defined · [x] performance addressed
**Implementation Patterns** — [x] naming/signature conventions · [x] structure patterns · [x] communication (plan/SSE/409) patterns · [x] process (txn/saga/dry-run/error) patterns
**Project Structure** — [x] complete directory structure · [x] component boundaries · [x] integration points mapped · [x] requirements→structure (epic) mapping

### Architecture Readiness Assessment
**Overall Status:** READY FOR IMPLEMENTATION (all 16 checklist items `[x]`, no Critical Gaps).
**Confidence Level:** High — grounded in the real codebase (confirm_tokens.py, _execute_confirmed_dispatch, ScopedDatabase) and adversarially reviewed (two party-mode rounds).
**Key Strengths:** parity-by-construction via shared write path; integrity-by-design (plan-hash + precondition + atomic/saga + idempotency); brownfield-respectful (no new tools/UI, Part 2 invariants preserved); test substrate explicitly designed (AD12).
**Areas for Future Enhancement:** Azure India-region residency (AD11); planner quality eval dashboard; extend pattern to all roles (Phase 2/3).

### Implementation Handoff
**AI Agent Guidelines:** follow ADs exactly; use P1–P8 consistently; route every mutation through a service; never write in both tool and route; keep 699 tests green; preserve `scoped_query` audit on touched routes.
**First Implementation Priority:** Epic A, Story 1 — extract the first domain service (attendance) with characterization tests proving zero behavior change (NOT a project-init story; brownfield).
