# UI Sweep — Deferred Work & Discoveries

Running log for the EduFlow UI Sweep initiative (owner-reported defects, 2026-07-22).
Rule 6: anything discovered mid-run is either fixed in that run or logged here with a
reason and a pointer. Never silently skipped.

Branch: `ui-sweep-2026-07-22`

---

## Timeline — what has actually happened

| Date | Run | Outcome |
|---|---|---|
| 2026-07-22 | Pre-epic | Responsive audit; found the earlier "fully screen-responsive" commit (807fd8f) was a CSS-only layer that missed ~25 dialogs, everything outside `.app-main-content`, and mobile viewport height. Fixed. |
| 2026-07-22 | Pre-epic | **Two regressions introduced and then fixed the same day** — see D-01. |
| 2026-07-22 | Pre-epic | Local dev unblocked: production CORS + AWS WAF were rejecting `localhost`. Solved with a dev-server proxy and a cookie allow-list (`frontend/src/setupProxy.js`). Root cause: PostHog's cookie is URL-encoded JSON, which WAF reads as an injection attempt; in production the analytics cookies never reach the API because page and API are different origins. |
| 2026-07-22 | Pre-epic | Read-only reconciliation of the school's source documents vs the live database → `_bmad-output/planning-artifacts/aaryans-source-of-truth-2026-07-22.md`. |
| 2026-07-22 | Pre-epic | Shipped: staff role/sub-category lockdown (frontend), staff `designation` display, mobile header + sidebar behaviour, class ordering, notification dot. Commits `401a4ac`, `ab206cb`, and the mobile-shell commit. |
| 2026-07-22 | Planning | `bmad-check-implementation-readiness` run → paused at step 1: **no epic document existed** for this work. `bmad-create-epics-and-stories` run → requirements inventory, 7 epics, coverage map, Epic 1 stories written. |

---

## Open items

### D-01 — Regressions introduced 2026-07-22 (FIXED same day)
Two defects were shipped by this initiative and corrected within hours:
1. Setting `display:block` on tables with `display:table` on thead/tbody split each table
   into two independently-sized tables, so headings stopped aligning with their cells.
   Fixed with a `:has()` rule that scrolls the table's wrapper instead.
2. Forcing all form controls to 16px under `pointer: coarse` also fired in Chrome's
   device simulator, so dropdowns rendered at 16px beside 12px labels.
   Reverted; the correct fix is a mobile type scale (UX-DR7, Epic 2).
**Status:** closed. Recorded because the owner reported both, and because they are the
reason the epic-close adversarial review gate exists.

### D-02 (was RISK-1) — Owner-role restriction is frontend-only — **OPEN, Epic 1 Story 1.1**
"Owner" was removed from the staff role dropdown and reported to the owner as closing
the privilege-escalation hole. It does not: FR4 and NFR-S1 require server-side denial,
and the API still accepts `role: "owner"`. **This was mis-reported as complete.**
**Reason deferred:** none — it is Epic 1 Story 1.1 and must be fixed there.

### D-03 (was RISK-2) — Two order-dependent backend test failures — **DEFERRED**
`tests/backend/api/test_r13_tenancy_rbac.py::test_scoped_collection_find_one_and_update_injects_school_id`
and `::test_scoped_collection_distinct_scopes_to_school` fail in a full-suite run but
pass in isolation (38 passed alone). Verified pre-existing by running the full suite
against a clean `main` worktree — identical two failures.
**Baseline for this initiative: 1636 passed, 2 failed, 14 deselected.**
**Reason deferred:** pre-existing, unrelated to this initiative, caused by shared state
left behind by an earlier test. Do not attribute to your own changes; do confirm the
count is still exactly 2 at each epic close.

### D-04 (was RISK-3) — Test runs can reach the production database — **DEFERRED, owner decision pending**
`backend/.env` now holds the live `MONGO_URL`, pulled from the Elastic Beanstalk
environment. Before this file existed, tests had nowhere to connect. There is no guard
preventing a test run from writing to production.
**Workaround in force:** always override before running pytest —
`$env:MONGO_URL="mongodb://127.0.0.1:27099/eduflow_test"; $env:DB_NAME="eduflow_test"`.
**Proposed fix:** a conftest guard that refuses to run against the production cluster.
Awaiting the owner's go-ahead.

### D-05 (was RISK-4) — `project-context.md` carries a stale fact — **DEFERRED**
It states "Sidebar width is 120px fixed". Actual: 260px, and 280px as a mobile drawer.
It is loaded as authoritative context by every BMAD workflow, so it misinforms agents.
**Reason deferred:** documentation-only; fix alongside Epic 2 (the sidebar epic).

### D-06 — Two students in the school's export are absent from the platform — **DEFERRED to Track 2**
Admission numbers `19968` and `211309` appear in `Students-22-06-2026.xlsx` (1,804 rows)
but not in the database (1,802). Possibly withdrawals, possibly a missed import.
**Action:** the school should confirm. Not a UI defect.

### D-07 — Six login accounts have no matching user record — **DEFERRED to Track 2**
`users` = 1,892 vs `auth_users` = 1,898. Cause unknown.

### D-08 — Leave types do not match the school's register — **DEFERRED, product decision**
The school's staff attendance register tracks Casual, Medical, **Special** and
**Without Pay**. The platform tracks Casual, Medical and **Earned**. So two of the
school's leave types cannot be recorded, and one platform type is unused.

### D-09 — The school's real staff vocabulary is unused — **DEFERRED, feeds Epic 7**
The register uses **PRIN / NTT / PRT / TGT / PGT / Other** (Principal, Nursery Teacher
Training, Primary, Trained Graduate, Post Graduate, Other). The platform uses
`class_teacher` / `subject_teacher`. Relevant to the roles redesign the owner asked to
see mocked both ways before building.

### D-10 — Nine admission-form fields have nowhere to be stored — **DEFERRED to Track 2**
From the printed enquiry form: student/father/mother Aadhar numbers, PEN (UDISE) number,
APAAR ID and consent, previous school attended, registration number, declaration/T.C.
undertaking. See §2 of the source-of-truth document.

---

## Track 2 (data load) — explicitly OUT OF SCOPE for these epics

Requires separate owner approval; involves writes to live data.
1. Student date of birth, gender, house, admission date — from the **FY2025-26**
   detainees workbook, joined on admission number only, ~1,551 of 1,802 matchable (88%).
   **The class column in that file must never be used** — it is last year's class and
   would demote every continuing student.
2. Transport routes and rates (~250 pick-up points).
3. Fee structure 2026-27.
4. Class-teacher assignments for all 48 sections.
5. Correcting the school's own details (address, phone, email, principal, affiliation) —
   currently placeholder data for a real school.
