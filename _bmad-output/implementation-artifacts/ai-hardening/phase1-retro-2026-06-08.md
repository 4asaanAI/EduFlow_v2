# Retrospective — AI Layer Hardening, PHASE 1 (Epics A–G)

**Date:** 2026-06-08
**Facilitator:** Amelia (Developer) · Party-mode team retrospective
**Project Lead:** Abhimanyusingh
**Scope:** Whole Phase-1 initiative — 10 epics (A, B, C, D, E, I, F, J, K, G), 54 stories.
Tracked in `_bmad-output/platform-quality-sweep.md` row 17 + `_bmad-output/EPIC-EXECUTION-PROTOCOL.md` (not numbered in `sprint-status.yaml`).
**Status at retro:** Merged to `main` (commit `fe33910`). Owner+Principal pilot **not yet started**.

---

## 1. Delivery Summary

| Metric | Result |
|--------|--------|
| Epics delivered | 10/10 (A B C D E I F J K G) in strict dependency order |
| Stories delivered | 54/54 |
| Test suite | 699 → **1148 passing**, 0 skipped, 0 new failures vs pinned 25-failure baseline |
| Tests added | ~+449 (parity, regression, `mongo_real` tier, guardrails) |
| Pre-existing AI defects fixed | 3 (Epic B) + dozens via STEP-4 epic-close reviews |
| New UI surfaces | 0 (parity-enforced) |
| Production incidents | 0 (merged, not yet piloted) |

**Architecture bet that paid off:** AD7 single-writer — every AI action and every UI action now
flows through one shared service. Held across all 16 new CRUD tools (Epics J/K) and the
hardened write tools (A–C).

---

## 2. What Went Well (keep doing)

1. **Layering discipline.** Service extraction (A–C) → atomic executor + real-Mongo tier (D) →
   planner (E) → frontend plan card (I) → compliance/ops (F) → CRUD (J/K) → self-learning (G).
   No epic ever depended on a later one — the reason one-epic-per-window held instead of collapsing.
2. **Dual-entrypoint parity tests + CI drift gate.** Proving the AI path byte-identical to REST
   is what makes "no new UI surface" a guarantee, not a hope. 14/14 write tools mapped to corpus.
3. **STEP-4 mandatory epic-close review** (added after Epic D). Highest-leverage process change —
   caught the J/K duplicate write-path helpers that would have re-introduced AD7 drift.
4. **Real-Mongo `mongo_real` tier (D.1).** A true replica set is what let us *prove* transaction
   rollback + idempotency; FakeCollection alone would have green-washed those.
5. **One-epic-per-window protocol + fixed handoff template.** Kept context lean and prevented
   prompt drift across 10 windows.

---

## 3. Challenges & Recurring Patterns (lessons)

**Theme #1 — AI-path drift from the REST path (the dominant bug class).**
B.1 (no idempotency → double-charge), B.2 (discount bypassed owner approval), B.3 (un-audited
house-points), A.3 (approval routing-authz hole), A.4 (announcement gate mismatch). Each was "the
AI tool did *almost* what the route did." → **Single-writer extraction kills this class permanently;
every new write tool must ship with a parity test + corpus entry.**

**Theme #2 — over-aggressive intent/NLP detection.**
Epic G HIGH findings: bare mid-sentence "actually" silently *deleted* a memory; "ok &lt;request&gt;"
swallowed as a confirmation. Mirror of F.1's deliberate choice to keep redaction *surgical*.
→ **Err conservative/anchored on anything that mutates state or hides user intent.**

**Theme #3 — test-isolation leaks from shared singletons.**
K's review: parity fixtures wiped seeded `classes`/`academic_years` and broke Epic J student-create
FK. → **Shared real-ish corpus state needs save/restore fixtures; assume order-independence.**

---

## 4. Previous-Retro Follow-Through

No prior retrospective exists for this initiative (first retro for AI Layer Hardening). The
in-initiative analogue — the STEP-4 epic-close review — served the accountability function between
epics: each epic's `story-{ID}-review.md` recorded findings fixed/dismissed-with-reason, and the
next epic inherited a clean baseline. This worked; keep it.

---

## 5. Next Epic Preview — Epic H (Phase 2, role extension)

**Status: PARKED — GATED on Owner+Principal pilot sign-off. Pilot has not started.**

- **What H is:** widen the F.11 `services/ai_action_policy.py` `LOCKDOWN_ENABLED` switch from
  Owner+Principal to other **staff** roles, broken into per-role stories reusing Epics A–K's engine —
  **no engine changes**. Students remain permanently out of scope (read-only, content-filtered).
- **Readiness:** engine is ready; the gate is a *product/process* gate, not a code gate. The honest
  state is **the pilot hasn't run yet**, so the gate is genuinely open.
- **Do NOT auto-start H.** Per protocol, no H handoff prompt is emitted until sign-off.

---

## 6. Action Items

| # | Action | Owner | Category | Done-when |
|---|--------|-------|----------|-----------|
| 1 | Run the Owner+Principal Phase-1 pilot against the 7-job pilot inventory (PRD) | Abhimanyusingh | Process/Gate | Sign-off captured on the 7 jobs |
| 2 | During pilot, watch the carried risks via F.7 `ai_metrics` counters (per-turn LLM extraction cost; vector-memory ON/OFF decision; plan/confirm/torn-state rates) rather than pre-solving | Abhimanyusingh / Ops | Observability | Pilot data reviewed before H planning |
| 3 | Lock in **one-epic-per-window protocol** + **STEP-4 epic-close review** as standing practice for Epic H and future initiatives | Team | Process | Referenced verbatim in the H handoff prompt |
| 4 | Carry the 3 recurring-pattern guards into H's definition-of-done: parity test+corpus per write tool; conservative/anchored intent matching; save/restore fixtures for shared corpus state | Team | Technical | Added to H story acceptance criteria |

No SMART deadlines attached — sequencing is gated on the pilot, not the calendar.

---

## 7. Readiness Assessment (Phase 1)

| Dimension | Status |
|-----------|--------|
| Testing & quality | ✅ 1148 passing / 0 skipped / 0 new failures; mongo_real tier green |
| Code merged | ✅ `main` @ `fe33910` |
| Deployment to prod | ⏳ not covered by this retro (separate Phase-6 go-live track) |
| Stakeholder (Owner+Principal) acceptance | ⏳ **pilot not started — this is the open gate** |
| Technical health | ✅ AD7 single-writer; scoped_filter audits clean; kill-switch + shadow mode + revert runbook in place |
| Carried risks | 🟡 LLM extraction cost, vector default-OFF — accepted, to be watched via ai_metrics during pilot |

---

## 8. Key Takeaways

1. **Single-writer (AD7) + parity drift gate is the structural fix** for the dominant bug class
   (AI-path divergence). Protect it on every future write tool.
2. **The STEP-4 epic-close review is the process win** — bugs never leaked across epic boundaries.
3. **Phase 1 is structurally complete; the only thing between here and Epic H is the pilot.**
   Don't start H until Owner+Principal sign-off lands.

---

*Meeting adjourned. Next checkpoint: post-pilot review → then emit the Epic H handoff prompt.*
