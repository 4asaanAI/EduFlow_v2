# Epic 7 — A Directory Shaped Like The School — BUILT, gate green, NOT yet deployed

Branch: `ui-sweep-2026-07-22` · 2026-07-23

> **Status: implementation complete, frontend gate green, production build clean —
> but NOT committed-to-remote or deployed.** Per the D-15b rule, this is **"not yet
> visible to you"** until it is merged and Amplify rebuilds; the owner's in-app
> check is the last step.

## The design pass the epic was waiting on (owner decisions, 2026-07-23)

The plan deliberately left Epic 7 un-storied, flagged as new product scope needing a
design pass first. Abhimanyu was asked and chose:
1. **Shape** — a **tabbed Directory** (Students / Staff), each on Epic 3's shared
   server-sorted table. Not one merged list; not just a global search.
2. **Scope** — build the Directory **and** consolidate near-duplicate tools this run.
3. **Staff naming** — the school's own register vocabulary (PRIN/NTT/PRT/TGT/PGT),
   expanded on hover, not the machine `role / sub_category`.

Stories 7.1–7.3 were written into
`_bmad-output/planning-artifacts/epics-ui-sweep-2026-07-22.md` from these decisions.

## What is built and unit-verified

- **`frontend/src/components/tools/SchoolDirectory.js`** — tabbed Directory. Students and
  Staff tabs, each on the shared `DataTable` (server sort + rows-per-page, keyed per tab
  `directory-students` / `directory-staff`). Active tab lives in the URL. Reuses the
  existing `getStudents` / `getStaff` endpoints — **no new server surface**. "not
  recorded" for empty fields. Each row opens the owning tool (Student Database / Staff
  Tracker) rather than forking a second editing path.
- **Staff vocabulary, honestly.** `registerCode()` returns a register code ONLY where
  confidently derivable (Principal → PRIN). The teacher tier (NTT/PRT/TGT/PGT) is **not
  in the platform's data** — only `designation`/`staff_type`/`role`/`sub_category` are —
  so it is never invented; those rows fall back to the readable designation, and a legend
  states the gap. Waits on the Track 2 data load (D-09).
- **Wiring.** `Layout.js` loads `school-directory`; `ToolDashboard.js` registers it in the
  catalog and adds it to **Owner** and **Principal** sets only.
- **Consolidation (confident only).** The maintenance admin carried both `facility-requests`
  (the queue it manages) and `raise-maintenance` ("Report an Issue") — two doors to the
  same queue for the one role that owns it. Dropped the duplicate; `raise-maintenance`
  stays for the other roles where it is their only way in.
- **Tests.** `frontend/src/components/__tests__/SchoolDirectory.test.js` — 15 tests, all
  green: the PRIN-only vocabulary rule (and the never-invent-the-tier rule), the
  Owner+Principal-only nav gating (asserted ABSENT from 7 other roles), and the
  consolidation (no silent re-introduction of the duplicate).

## Deep-link (owner-approved 2026-07-23) — done for students

- A **Students** row now opens straight into that student's profile. `SchoolDirectory`
  navigates to `?tool=student-database&focus=<id>`; `StudentDatabase` reads `focus` once
  (guarded by a ref, StrictMode-safe), opens the detail panel (which fetches by id, so the
  student need not be on that screen's current page), then strips the param so a reload or
  a close does not reopen it.
- A **Staff** row lands on the Staff Tracker list (88 rows, one page — trivially scannable).
  Opening the exact staff editor by deep-link needs a staff-by-id open path the Staff
  Tracker does not have yet; deferred (D-44), not half-built.

## All four tool registries wired (the impact-note lesson, applied to our own change)

A tool id must be added in four hand-kept places or it half-appears. For `school-directory`:
- `ToolDashboard.js` — catalog `T` + `OWNER_TOOLS` + `admin_principal` set.
- `Sidebar.js` — the owner tool pool (one definition, reused for principal), the principal
  allowed-list, and the owner **and** principal group `top` strips.
- `Layout.js` — `loadTool` route to `SchoolDirectory`.
- `CommandPalette.js` — ⌘K entry, `roles: ['owner']` only (⌘K can't gate by sub_category,
  so the Principal reaches it via the sidebar, and no other admin sees it anywhere).

## Deliberately NOT done this run (owner's call needed / honesty)

- **Aggressive tool consolidation.** The Directory does NOT replace Student Database for
  Owner/Principal — Student Database also creates/edits/erases students and shows class
  strength, which the read-only Directory does not. Removing it would be a capability
  loss, not a consolidation. Left in place; deeper consolidation of the fee / messaging /
  document clusters needs the owner's per-cluster decision (the Epic 9 "a wrong merge is
  worse than no merge" rule). See DEFERRED D-44.

## Remaining before this epic can be called done / shipped

- Full backend suite vs pinned baseline (1955/3/14) — unaffected (no backend files
  changed) but must be RUN to confirm.
- Full frontend suite + production `craco build` clean.
- Confirm 401/403 coverage exists on `GET /api/students` and `GET /api/staff` (endpoints
  are gated in code — line 224/226 students.py; test presence to be confirmed in the gate).
- Six review passes (code, adversarial, edge-case, test-review, trace, NFR).
- Logs finalised, tracker updated, commit to branch, deploy decision, owner in-app check.
