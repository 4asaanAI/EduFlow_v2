---
workflowStatus: 'completed'
totalSteps: 5
stepsCompleted:
  - step-01-detect-mode
  - step-02-load-context
  - step-03-risk-and-testability
  - step-04-coverage-plan
  - step-05-generate-output
lastStep: 'step-05-generate-output'
nextStep: ''
lastSaved: '2026-05-12'
inputDocuments:
  - '_bmad-output/planning-artifacts/prd.md'
  - '_bmad-output/planning-artifacts/architecture.md'
  - '_bmad-output/implementation-artifacts/stories.md'
  - '_bmad-output/project-context.md'
  - '_bmad/tea/workflows/testarch/bmad-testarch-test-design/checklist.md'
outputDocuments:
  - '_bmad-output/test-artifacts/test-design-architecture.md'
  - '_bmad-output/test-artifacts/test-design-qa.md'
  - '_bmad-output/test-artifacts/test-design/eduflow-handoff.md'
mode: 'system-level'
---

# Test Design Workflow Progress — EduFlow Enterprise Upgrade

## Step 1: Mode Detection

**Mode selected:** System-Level  
**Reason:** PRD + Architecture documents available. No `sprint-status.yaml` exists in implementation-artifacts. PRD + ADR pattern confirms System-Level Mode.

**Prerequisites verified:**
- PRD (`prd.md`): present — 95 FRs, NFRs, user journeys
- Architecture (`architecture.md`): present — ADRs, tech decisions, open gaps
- Stories (`stories.md`): present — 28 stories, 5 phases (used for scope)
- Project context (`project-context.md`): present

---

## Step 2: Context Loaded

**Stack detected:** Fullstack (React 19 frontend + FastAPI backend)

**Config flags loaded:**
- `tea_use_playwright_utils`: true → Full UI+API profile loaded
- `tea_browser_automation`: auto → No live app; code/doc analysis only
- `test_stack_type`: auto → resolved to fullstack
- `test_artifacts`: `_bmad-output/test-artifacts/`

**Key artifacts extracted:**
- 9 roles in RBAC matrix (Owner, Principal, Accountant, Receptionist, Transport Head, IT/Tech, Maintenance, Teacher[P2], Student[P2])
- 9 AI write dispatches + 8 read dispatches (Appendix A dispatch table)
- 4 open architecture gaps identified (S3, test suite, JWT refresh, tool registry split)
- Tech stack: React 19 / FastAPI / Motor/MongoDB Atlas / Azure OpenAI / AWS S3 / Twilio

**Knowledge fragments consulted:**
- `adr-quality-readiness-checklist.md`
- `test-levels-framework.md`
- `risk-governance.md`
- `test-quality.md`
- `probability-impact.md`
- `test-priorities-matrix.md`

**Browser exploration:** Skipped — no live app running. Code/doc analysis used.

---

## Step 3: Testability & Risk Assessment

**Testability summary:**
- 4 actionable concerns (TC-01 through TC-04): no test infrastructure, no LLM mock, scope resolver not independently testable, `branch_id` filter gap
- 4 architectural improvements needed (AI-01 through AI-04): confirm token model, idempotency enforcement, log PII CI check, tool rounds test
- 4 pre-implementation blockers (B1 through B4): token store choice, Atlas tier, Azure DPA, CloudFront SSE timeout

**Risk register:**
- 4 high-priority risks (score ≥ 6): R-001 (SEC, 9), R-002 (SEC, 9), R-003 (DATA, 6), R-004 (SEC, 6)
- 6 medium risks (score 3–5)
- 3 low risks (score 1–2)

---

## Step 4: Coverage Plan

**Total test scenarios defined:** 78 (T-001 to T-078)
- P0: 17 tests — RBAC matrix, confirm-action gate, scope resolver, S3, idempotency
- P1: 32 tests — CRUD flows, AI dispatch, SSE, business domain flows
- P2: 19 tests — edge cases, audit trails, health endpoints
- P3: 10 items — benchmarks, manual checks, static analysis

**Execution strategy:** PR / Nightly / Weekly model
- Every PR: all pytest + craco test (10–15 min)
- Nightly: k6 benchmarks + static analysis
- Weekly/pre-release: manual mobile + theme + accessibility checks

**QA effort estimate:** ~11–20 weeks (range; one part-time QA contributor)

**Quality gates defined:** 5 phase-transition gates + go-live gate

---

## Step 5: Output Generated

**Documents written:**
1. `_bmad-output/test-artifacts/test-design-architecture.md` — Architecture & Risk document
2. `_bmad-output/test-artifacts/test-design-qa.md` — QA Execution Recipe
3. `_bmad-output/test-artifacts/test-design/eduflow-handoff.md` — TEA → BMAD Handoff

**Checklist validation:**
- Both documents validated against `checklist.md` criteria
- Architecture doc: actionable-first structure; no recipe sections; no test code; FYI at bottom
- QA doc: test coverage plan with P0–P3; execution strategy by tool type; QA effort only; code examples with assertions
- Handoff doc: TEA artifacts inventory, risk-to-story mapping, phase gates, open assumptions
- Cross-document: consistent risk IDs (R-001 to R-013), consistent priorities (P0–P3), no duplicate content
- Anti-bloat: no repeated notes, no AI slop markers, professional tone

**Workflow complete.** Next recommended action: Run `/atdd` workflow targeting P0 scenarios T-001 through T-017.
