# Tool-merge impact note — read before consolidating any tools (Epic 7, D-44)

Abhimanyu approved the bolder tool merges (2026-07-23) **on condition we first list
everything that would have to change**. This is that list. The headline: a tool id is
**not** defined in one place — it lives in **four parallel registries plus several
consumers**, none of which import from each other. Miss one and the tool half-disappears
(shows in the sidebar, dead in ⌘K; or routes to nothing; or a notification opens a tool
that no longer exists).

## The four parallel registries (all must be edited for any merge)

| # | File | What it holds | Risk if missed |
|---|------|---------------|----------------|
| 1 | `frontend/src/components/ToolDashboard.js` | The `T` catalog (id → name/icon/colour) **and** the role sets `OWNER_TOOLS` / `TOOL_SETS` (admin_*, teacher, student) | Tool vanishes from the dashboard grid, or a role keeps/loses it wrongly |
| 2 | `frontend/src/components/Sidebar.js` | A **second, independent** catalog (lines ~36–78) **and** its own role lists + grouped sections (lines ~124–174) | Sidebar and dashboard disagree about what exists |
| 3 | `frontend/src/components/Layout.js` | `loadTool()` routing (id → which component file) **and** the `OWNERS` / `ADMINS` / `TEACHERS` / `STUDENTS` id arrays that decide which component bundle a role's id resolves from | A live id routes to `null` → "Loading tool…" forever |
| 4 | `frontend/src/components/CommandPalette.js` | A **third** independent catalog for ⌘K (id/name/roles) | ⌘K offers a tool that's gone, or hides one that exists |

**Root cause worth fixing separately:** these three catalogs (1, 2, 4) are hand-kept copies
of the same data. The right long-term fix is one shared source of truth all three import —
but that is its own refactor and should NOT be bundled into a product merge (it would hide
the merge inside a big mechanical diff). Logged for its own pass.

## The consumers that also name tool ids (check per merge)

- **`frontend/src/lib/notifRouting.js`** — notifications deep-link to a tool id (a fee
  notification opens `fee-tracker`; a circular opens `circular-sender`). If a target id is
  merged away, the notification lands nowhere. Also holds a display-name map (lines ~81–89).
- **Cross-tool `open-tool` dispatches** — e.g. `OwnerTools.js:312` fires
  `CustomEvent('open-tool', 'attendance-alerts')`; a "School Pulse" card jumps to another
  tool by id. Grep `open-tool` and `eduflow-navigate` before removing any id.
- **URL deep-links** — anything of the form `?tool=<id>` (bookmarks, the Directory's own
  row-open, help docs). A removed id must redirect, not 404 into a blank pane.
- **Backend capability endpoints** — the messaging tools sit on real routes:
  `POST /api/sms/send-parent-message` (parent-message) and
  `/api/sms/whatsapp-attendance-alerts` (attendance-alerts). Merging the *UI* entry points
  does NOT touch these — but if a merge means "these are now one screen", confirm the
  screen still calls both endpoints, or a capability silently drops.
- **Tests** — `SchoolDirectory.test.js` and any tool-list test pin role→id lists; update
  them in the same commit so a merge can't silently regress.

## The candidate clusters, with the specific edit each needs

### A. Fee cluster — `fee-tracker` · `smart-fee-defaulter` · `fee-receipts` (+ owner `fee-collection`, `financial-reports`, `expense-tracker`)
- **Verdict:** probably one "Fees" area with tabs, NOT a delete. They do different jobs
  (track dues / chase defaulters / issue receipts), so a merge is a *navigation* change.
- **Edit:** registries 1, 2, 4 (three catalogs), Layout routing (fee-receipts →
  `FeeCollection`, smart-fee-defaulter → OwnerTools/AdminTools), the Sidebar's "Fees"
  group (Sidebar.js:146), and `notifRouting.js` (two `fee-tracker` targets, lines 23/39).
- **Watch:** owner and admin resolve fee tools from *different* component files
  (OwnerTools vs AdminTools) — a merged screen must work for both or be role-split.

### B. Messaging cluster — `circular-sender` · `parent-message` · `attendance-alerts`
- **Verdict:** candidate for one "Messages" area. But each hits a *different* backend send
  path (circulars vs parent SMS vs attendance-threshold SMS), so it's a UI merge only.
- **Edit:** registries 1, 2, 4; Layout `ADMINS`/`OWNERS` arrays; Sidebar "Communication"
  group (Sidebar.js:170); `notifRouting.js` circular targets (lines 30/51/54); the
  `open-tool → attendance-alerts` dispatch in OwnerTools.js:312; backend sends stay.

### C. Document cluster — `certificate-generator` · `id-card-generator`
- **Verdict:** plausibly one "Documents you can print" screen (both render + print a doc
  per student). Closest to a true merge.
- **Edit:** registries 1, 2, 4; Layout routing; Sidebar "Records" group (Sidebar.js:164);
  confirm both still gate to owner/principal per the Epic R9.5 lockdown (certificates were
  tightened there — do not loosen).

### D. Directory vs `student-database`
- **Verdict:** do NOT merge yet. The Directory is read/find only; Student Database also
  creates/edits/erases students and shows class strength. Making the Directory the single
  entry means porting those management features first, or trimming Student Database to
  management-only and pointing "find a student" at the Directory. Either is real work and
  needs its own story.

## Recommended sequence when we do it
1. Land the shared-catalog refactor (one source for registries 1/2/4) FIRST, as its own
   change, so each subsequent merge is a one-place edit, not a four-place edit.
2. Then merge C (documents) — smallest, cleanest.
3. Then A and B as tabbed areas, each with the backend-capability check above.
4. D last, as its own story with the management-feature port.
Each step: update the pinned role→id tests in the same commit; run `craco build` (not just
the dev server); verify ⌘K, the sidebar, the dashboard and notification deep-links all
agree.
