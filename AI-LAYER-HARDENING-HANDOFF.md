# EduFlow AI Layer Hardening — Handoff & Next Steps

> **If you are a Claude session and the user just said something like "hey I am Shubham, what's the next step?" — read this whole file and present it in plain language, leading with the "TL;DR" and "THE NEXT STEP" sections below. Do not skip the "Important — don't miss" section.**

**Status as of 2026-06-07:** All planning is COMPLETE and was adversarially audited. **Implementation has NOT started — it is intentionally paused here, waiting for Shubham's review.** Shubham will review the epics/stories on his own machine/Claude account and make changes as he sees fit.

---

## TL;DR (read this first)

We hardened the **planning** for a big upgrade to EduFlow's **AI chat layer** (the main chat — `ChatInterface.js` → `/api/chat` → `backend/routes/chat.py`; **NOT** the little floating bottom-right bubble, which is out of scope). The goal: let the assistant **actually perform actions** for a user (mark attendance, record fees, approve leave, publish announcements, etc.) — completing whole multi-step jobs from one instruction — with those actions landing in MongoDB **identically to clicking the UI**, gated by a single confirmation, fully safe and DPDP-compliant. We also added an **AI self-learning/memory** capability (cloned from the open-source Odysseus repo) for Owner & Principal.

Nothing has been coded yet. Four planning documents exist (PRD, readiness report, architecture, epics/stories), plus this handoff. The next step is Shubham's review, then a fresh readiness check, then build Epic A.

---

## THE NEXT STEP (what to actually do next)

1. **Review the plan** (this file + the 4 artifacts in `_bmad-output/planning-artifacts/`, listed below). Decide on any changes.
2. When ready to build, **re-run the BMAD implementation-readiness check** — now *with* the epics present (the first run was before epics existed): it validates epic coverage + quality for real.
3. **Start implementation at Epic A, Story A.0** (per-domain cutover feature flag + `actor_ctx` contract), then **A.1** (attendance service as the reference shared-write-path). Use the per-story loop the rest of the platform uses: create-story → dev-story → tests → code-review.
4. **Sequence is fixed:** A → B → C → D → E → I → F → G (Phase 1), then H (Phase 2). Each epic only depends on earlier ones.
5. **Roll out behind the kill-switch + shadow/dry-run mode**, prove parity, enable live writes, get **Owner + Principal sign-off** on the 7 pilot jobs, then Phase 2 (all other roles).

---

## What this initiative is (the "why")

EduFlow is a chat-first, multi-role school-management SaaS for Indian CBSE schools. Today the AI chat reads data well but **rarely acts** — only ~14 of ~163 backend write-capabilities are reachable by the AI, it does one tool per turn, and (critically) **the AI's write tools re-implement database writes separately from the REST/UI routes**, so they have silently drifted apart.

This initiative **hardens the existing AI layer** (no new user-facing tools or UI) so that:
- **Action ↔ data parity:** an AI write produces the *exact* same database change as the UI (same validation, multi-tenancy scoping, idempotency, audit) — achieved by making the AI tool and the REST route both call **one shared service layer**.
- **Agentic multi-step chaining:** the assistant plans a whole compound task and executes it after **one** confirmation ("plan-then-confirm-once"), all-or-nothing.
- **AI self-learning:** the assistant remembers and adapts per Owner/Principal, and can recall/synthesize history on demand (e.g., "brief me on this family before the meeting").
- **Compliance:** full DPDP Act 2023 posture for children's data.

**Acceptance gate:** Owner + Principal pilot it live for 1–2 months; only if they're satisfied does it roll out to the whole school. So **Owner & Principal are built and verified first.**

---

## The plan documents (all in `_bmad-output/planning-artifacts/`)

| File | What it is |
|---|---|
| `prd-ai-layer-hardening.md` | Product requirements — 36 functional + 25 non-functional requirements, the 7 "pilot jobs" Owner/Principal sign off on, DPDP requirements, phased scope. |
| `implementation-readiness-report-ai-layer-hardening-2026-06-07.md` | Pre-architecture readiness check — verdict **READY**, 0 critical issues. (Re-run this *with epics* before building.) |
| `architecture-ai-layer-hardening.md` | The technical design — 14 architecture decisions (AD1–AD14) + 8 implementation patterns + project structure + validation. This is the source of truth for *how*. |
| `epics-ai-layer-hardening.md` | **The build plan** — 9 epics (A–I), 48 stories with Given/When/Then acceptance criteria, FR coverage map, and a "Resolved Audit Findings" table. |
| `AI-LAYER-HARDENING-HANDOFF.md` | This file. |

Tracker row for this initiative: `_bmad-output/platform-quality-sweep.md` (row 17).

---

## The epics, in plain language (build order)

- **Epic A — Trustworthy single-writer foundation (aligned domains).** Make the AI's existing writes for the easy domains (attendance, leave, approvals, announcements, contact-log, substitution, attendance-correction) go through the *same* code as the UI. Starts with A.0 (a per-domain on/off flag so each domain switches over only after its parity is proven) and A.1 (attendance, the reference implementation). *Zero change to the UI path; the AI path is corrected to match.*
- **Epic B — Parity + fix 3 real defects (fees, discounts, house-points).** While extracting these services, fix three **pre-existing bugs we found** (see below).
- **Epic C — Parity for the incident/complaint tools** (they pick their target collection at runtime; make it explicit).
- **Epic D — Safe execution.** Wrap AI writes in a MongoDB transaction so they're all-or-nothing and never double-applied; add the saga fallback for non-DB side-effects; stand up a **real-Mongo (replica-set) test tier** because the in-memory test fake can't test transactions.
- **Epic E — Whole-job-by-instruction.** The headline: the planner turns one instruction into an ordered plan; the user approves one card; the backend executes it atomically. Includes the plan-hash confirmation token, disambiguation, and the can't-do-it fallback.
- **Epic I — Frontend.** Evolve the existing confirm card to show the multi-step plan + clear status/error messages. (No new pages.)
- **Epic F — Compliant & operable.** DPDP redaction (don't send children's PII to the LLM), audited reads of minors' records, the **kill-switch**, **shadow/dry-run** mode, the **parity test harness + CI gate**, pilot **metrics**, a **closeout** doc-update, and an AI-write **remediation runbook**.
- **Epic G — AI self-learning (cloned from Odysseus).** Memory + skills for Owner/Principal, **no UI** (the AI auto-saves important info, asks in chat only when unsure), on-demand recall/synthesis, plus erasure/retention and correction. **Starts with an infra spike (G.1)** to prove the vector-DB dependencies run on our stack before building.
- **Epic H — Phase 2 (deferred).** Extend everything to the other roles after Owner/Principal sign off.

---

## Important — don't miss these

### 3 pre-existing AI-layer defects we found (fixed in Epic B)
1. **`apply_discount` bypasses owner approval.** The UI routes large discounts to owner approval; the AI tool currently applies them directly — a live authority hole on children's fees. → Epic B.2.
2. **`award_house_points` writes a wrong, un-audited data model.** It writes a different collection than the UI and never updates the house totals or audit log — so AI-awarded points may not even show in standings. → Epic B.3.
3. **`record_fee_payment` has no idempotency.** A confirm retry can double-charge. → Epic B.1.
Each gets a permanent regression test (B.4).

### Key decisions already made (don't re-litigate unless you disagree)
- **Confirm model = plan-then-confirm-once** (approve the whole plan once; execute atomically) — this intentionally evolves the old per-action confirm token.
- **Parity = case-by-case** when AI and REST diverge (decide which is correct per tool; don't assume REST is always right).
- **"No new tools/UI"** means no new user-facing surface — but we DO add a shared service layer, and self-learning is a conscious *addition* the owner approved.
- **Azure OpenAI runs in East-US 2** (startup credits, no India-region model). **DPDP data-residency is deliberately deferred**; PII-minimization to the LLM is a hard control instead. Do not treat residency as a blocker for now.
- **Clone-from-Odysseus directive:** Odysseus (open-source, `github.com/pewdiepie-archdaemon/odysseus`) is mature and bug-free for memory/skills and agent patterns. For anything our epics need that Odysseus already has, **clone and customize rather than rebuild.** Specifically: Epic G clones its Memory/Skills (`src/memory.py`, `memory_vector.py`, `services/memory/skills.py`, `skill_format.py`, `skill_extractor.py`, `routes/memory_routes.py`, `skills_routes.py`); Epic E borrows its planner/`ask_user`/plan-mode patterns. Epics A–D/F are EduFlow-custom (Odysseus lacks shared-service/transaction/saga/redaction/parity).

### Hard constraints (from the platform — see `CLAUDE.md` + `_bmad-output/project-context.md`)
- Python 3.9 — `from __future__ import annotations` as the first import in any file using `str | None`.
- Frontend is plain JS (no TypeScript).
- Multi-tenancy: every query scoped by `schoolId` (+ `branch_id` for non-owners via `scoped_query`).
- Notifications via `notification_service`, audit via `audit_service` — never write those collections directly.
- The existing **699 backend tests must stay green**; preserve the Part 2 AI-layer invariants.

### Open items intentionally left for pilot planning (not gaps)
- The exact **minimum number of AI mutations (N)** needed to call the pilot "proven."
- The **sign-off capture mechanism** (how Owner/Principal record approval).
- **Per-domain transaction-vs-saga boundary** finalized during architecture-into-code.

---

## How to resume (concrete)

```
# 1. Re-validate with epics present
Invoke skill: bmad-check-implementation-readiness
  (point it at prd-, architecture-, epics-ai-layer-hardening.md)

# 2. Build, story by story, starting at Epic A
Invoke skill: bmad-create-story   (for Story A.0, then A.1, …)
Invoke skill: bmad-dev-story      (implement)
Run tests; then:
Invoke skill: bmad-code-review

# 3. Keep the tracker updated
Edit _bmad-output/platform-quality-sweep.md (row 17) as epics complete.
```

The full, current scope/decision history (including everything above) also lives in the project memory of the machine where this was planned; this file is the portable copy — **treat it as the source of truth for the handoff.**
