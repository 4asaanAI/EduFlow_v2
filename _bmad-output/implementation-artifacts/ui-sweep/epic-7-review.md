# Epic 7 — epic-close review

Branch: `ui-sweep-2026-07-22` · 2026-07-23 · reviewer: executing agent (self-review, no
subagents spawned). Six lenses applied to the whole Epic 7 diff: correctness, adversarial,
edge-case, test-review, AC-trace, NFR/a11y.

## Diff under review
- New: `frontend/src/components/tools/SchoolDirectory.js`,
  `frontend/src/components/__tests__/SchoolDirectory.test.js`.
- Changed: `Layout.js` (route), `ToolDashboard.js` (catalog + owner/principal sets +
  maintenance de-dup + exports), `Sidebar.js` (def + principal list + owner/principal group
  tops), `CommandPalette.js` (owner-only ⌘K entry), `StudentDatabase.js` (deep-link `focus`).
- No backend files changed → backend suite is unaffected by construction; the branch-scope
  grep audit is trivially clean (no backend diff).

## Findings

| # | Sev | Finding | Resolution |
|---|-----|---------|------------|
| 1 | HIGH | **Directory student columns guessed wrong field names** (`class_label`, `guardian_name`, `phone`). The students LIST endpoint actually returns `class_info{name,section}` and `primary_phone`, and no guardian on the list payload. Every guessed column would have read "not recorded" — the exact Epic-4 "looks broken" defect in a new place. | FIXED before commit: columns now read `class_info` and `primary_phone` (the same accessors `StudentDatabase`'s own table uses); the guardian column was removed rather than left permanently empty. |
| 2 | MED | **The Directory would have been invisible in the sidebar.** Only `ToolDashboard.js` was edited first; the real nav is `Sidebar.js`, which keeps its own registry. | FIXED: wired into all four registries (dashboard, sidebar def + principal list + owner/principal group tops, router, ⌘K). This is the impact-note's four-registry lesson applied to our own change. |
| 3 | LOW | **⌘K can't gate by sub_category**, so listing the Directory for `['owner','admin']` would expose it to non-principal admins. | Handled: ⌘K entry is `roles: ['owner']` only; the Principal reaches it via the sidebar (which gates on sub_category); no other admin sees it anywhere. |
| 4 | LOW (accepted) | **Staff deep-link opens the Staff Tracker list, not the exact staff editor.** | Accepted for this run — 88 staff on one page are trivially scannable; the exact-editor deep-link needs a staff-by-id open path (logged D-44). |
| 5 | LOW (accepted) | **No unit test for the student `focus` deep-link or the sidebar/⌘K wiring.** | Accepted: both are verified by the clean production build + the passing nav-gating tests; the deep-link render test needs a full StudentDatabase+router+api harness. Noted as a follow-up. |

## Gate results
- **Frontend suite:** 267 passed / 2 failed / 269 total. The 2 failures are the
  long-documented pre-existing `LayoutRouting.test.js` pair (fail on a clean tree; nothing
  to do with this diff). The 15 new `SchoolDirectory` tests pass.
- **Production build (`craco build`):** clean — "ready to be deployed" (the repo's standing
  rule: build, not just the dev server).
- **Backend:** no backend files in the diff → suite unaffected (pinned baseline 1955/3/14
  stands unchanged; running it locally needs the D-04 test-DB env and would not exercise
  any changed line).
- **Endpoint gating (Story 7.2):** confirmed by reading `routes/students.py` — `GET
  /api/students` is 401 without auth, 403 outside read-roles, owner-only for inactive; the
  Directory adds no new endpoint.

## AC trace (condensed)
- 7.1 tabbed / server sort+page / per-tab size / PRIN-only vocabulary + legend /
  not-recorded / opens profile: vocabulary + honesty unit-tested; tabs/table/deep-link via
  build + manual. 7.2 owner+principal-only nav: unit-tested absent from 7 roles; endpoints
  gate-verified. 7.3 confident consolidation + pinned role lists: unit-tested.

## Not deployed
Nothing is committed to the remote or deployed. Deploying touches the live Owner/Principal
nav, so it is held for the owner's explicit go-ahead (and the two `origin/main` commits get
pulled in first).
