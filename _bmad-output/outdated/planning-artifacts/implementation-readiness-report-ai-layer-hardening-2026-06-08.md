---
stepsCompleted: ['step-01-document-discovery', 'step-02-prd-analysis', 'step-03-epic-coverage-validation', 'step-04-ux-alignment', 'step-05-epic-quality-review', 'step-06-final-assessment']
initiative: 'ai-layer-hardening'
run: 'second (post-epics, post-review)'
supersedes: 'implementation-readiness-report-ai-layer-hardening-2026-06-07.md'
---

# Implementation Readiness Assessment Report (Run 2 — with epics)

**Date:** 2026-06-08
**Project:** eduflow — AI Layer Hardening initiative
**Context:** Re-run AFTER architecture + epics exist and AFTER user/Shubham review feedback was applied. The first run (2026-06-07) was pre-epics and could not validate coverage/quality for real.

## Document Inventory
- PRD: `prd-ai-layer-hardening.md` — FR1–FR43, NFR1–NFR25 ✅
- Architecture: `architecture-ai-layer-hardening.md` — AD1–AD15 + 8 patterns, status complete ✅
- Epics: `epics-ai-layer-hardening.md` — **11 epics (A–K) / 54 stories**, FR coverage map, Resolved-Audit-Findings table ✅
- No initiative-specific UX doc (intentional — only the plan-confirm card; covered by Epic I + UX-DR1–5).
- No duplicates. All initiative-scoped.

## PRD Analysis
- **43 FRs** across 9 capability areas (incl. self-learning FR31–36 and CRUD FR37–43).
- **25 NFRs** (perf, security/privacy, integrity, DPDP, maintainability/test). NFR17 residency DEFERRED (accepted).
- Constraints confirmed: Phase-1 Owner+Principal only across the whole school DB; students unchanged/excluded; plan-then-confirm-once; parity via shared services; 3 found defects fixed in Epic B.

## Epic Coverage Validation (REAL — epics now exist)

**Coverage statistics:** Total FRs **43** · Covered **43** · **Coverage 100%**.

| FR group | Stories |
|---|---|
| FR1–FR6 (planning) | E.2, E.3, E.4, E.5, E.6 |
| FR7–FR8 (plan-confirm token) | E.1, E.5 |
| FR9–FR11 (atomic/idempotent/partial-fail) | D.3, D.4, D.5 |
| FR12 (reject unauthorized pre-token) | E.4, F.11 |
| FR13–FR14 (parity) | A.1–A.7, B.1–B.3, C.2–C.3 |
| FR15 (parity harness) | F.6 |
| FR16–FR18 (authz/scoping) | A.1, E.4, F.3, F.11 |
| FR19 (PII minimization) | F.1 |
| FR20 (trace/audit redaction) | F.2 |
| FR21 (audited minor reads) | F.2, G.5 |
| FR22 (erasure parity) | A.1 (shared path) |
| FR23 (student content filter) | _preserved as regression — students unchanged; full student verification Phase 2/H_ |
| FR24 (kill-switch) | F.4 |
| FR25 (shadow/dry-run) | F.5 |
| FR26 (per-write write-ahead audit) | D.3, D.5 (extends Part-2 audit) |
| FR27 (Owner/Principal first) | A/B/C, F.11 |
| FR28 (extend other roles) | H.1 (Phase 2) |
| FR29 (no new UI) | A.1, G.4, K.3 (cross-cutting) |
| FR30 (UI deep-link fallback) | E.6 |
| FR31–FR36 (self-learning) | G.2–G.8 |
| FR37 (student CRU) | J.1 |
| FR38 (fee config) | K.1 |
| FR39 (academic structure) | K.2 |
| FR40 (org config) | K.3 |
| FR41 (staff) | J.2 |
| FR42 (destructive policy) | F.10 |
| FR43 (Phase-1 lockdown) | F.11 |

**Missing FRs: none.** Two intentional caveats (unchanged from run 1): FR23 preserved-as-regression (students Phase-2); FR26 covered implicitly by the executor (extends existing audit).

## UX Alignment
- No full UX spec required; the only UI change (multi-step plan card + status messaging) is owned by **Epic I (I.1–I.3)** covering UX-DR1–5. ✅
- No UX↔PRD misalignment. ✅

## Epic Quality Review
- **User value:** each epic frames a user outcome (trustworthy writes, defect fixes, safe execution, whole-job-by-instruction, compliant/operable, self-learning, CRUD, frontend) — the "build the planner" technical-milestone trap (flagged in run 1) was avoided. ✅
- **No forward dependencies:** A→B→C→D→E→I→F→J→K→G→H; each epic uses only prior epics. Within epics, ordering is safe (D.1 test tier before D.3+; E.1 token before E.5; F.11 lockdown before live writes). ✅
- **Brownfield story types present:** characterization-first (A.1, B.1, C.1, J/K), migration/index (D.4), regression guards (B.4, F.6, F.11), no project-init story. ✅
- **Sizing:** stories are single-session-scoped with testable Given/When/Then ACs. ✅
- **Story count integrity:** 54 stories, frontmatter and summary consistent. ✅

## Gap Analysis
- **Critical:** none.
- **Carry-forward (resolve in dev/pilot, not blockers):**
  1. Epic G **infra spike G.1** gates the chromadb/fastembed dependency — must pass before the rest of G.
  2. Real-Mongo tier **D.1** gates atomicity/idempotency/shadow verification — build early in Epic D.
  3. **F.11 lockdown** temporarily removes existing non-owner/principal AI write access during the pilot — an operational change to communicate; Phase 2 (H) restores/expands.
  4. **Azure region/data-residency** precondition before live LLM payloads (DPDP; residency deferred but minimization is hard).
  5. **Pilot specifics** — minimum mutation volume N + sign-off capture mechanism (pilot planning).

## Summary & Recommendation

### Overall Readiness Status: **READY FOR IMPLEMENTATION** ✅
100% FR coverage, sound epic quality, no forward dependencies, brownfield discipline present, 0 critical issues. The expanded post-review plan (11 epics / 54 stories) is internally consistent and buildable.

### Recommended start
**Epic A, Story A.1** (attendance service — the reference shared-write-path; also pins the `actor_ctx` contract). Then A.2–A.7 → B → C → D → E → I → F → J → K → G; Phase 2 = H.

### Final go/no-go: **GO** — cleared to begin implementation at A.1, pending the user's explicit greenlight (per their request to control the start).

— Assessed 2026-06-08. Supersedes the 2026-06-07 pre-epics run.
