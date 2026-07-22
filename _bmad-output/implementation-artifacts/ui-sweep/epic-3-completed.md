# Epics 3 + 9 — Completed

**Date:** 2026-07-22 · **Branch:** `ui-sweep-2026-07-22`

Two epics shipped together, because Abhimanyu asked mid-run for the product to
look like the marketing site (`eduflow.layaa.ai`). Epic 9 was created for that
and sequenced first, so Epic 3's new table could be built once, in the new
language, rather than built and then restyled.

---

## Epic 9 — Looks Like The Brochure

### 9.1 One place that decides what the platform looks like

| | |
|---|---|
| Files | `index.css`, `theme.css`, `App.css` |
| Tests | `designTokens.contrast.test.js` — 40 |

- Baloo 2 (display) + Nunito (body); JetBrains Mono retained for code and data.
  **UX-DR3, which pinned the fonts to Inter, is formally superseded** — recorded
  rather than silently broken.
- Rounder radii, chunky solid-offset shadows, brand blue and orange, a full
  motion scale, and the platform's **first `prefers-reduced-motion` support**.
- A single `:focus-visible` ring for the whole app, with an explicit opt-out
  (`data-focus-ring="none"`) for fields whose container owns the indication.
- **A committed contrast test that computes WCAG ratios and fails the build.**
  It is not decoration: it rejected four real colour choices during this run.

**The palette deliberately diverges from the brochure.** Measured: white on
`#F2811D` = 2.65:1; white on `#2B8FF0` = 3.34:1. NFR-A1 needs 4.5:1. So orange
fills carry navy text (6.09:1) and the blue fill deepens to `#1A6FCE` (4.99:1).

**Dark theme was reverted to neutral grey** after Abhimanyu saw the navy version
("way too much blue"). Kept from the brochure in dark: the type, the shapes, the
accents. Not the background.

### 9.2 Controls that feel good to press

| | |
|---|---|
| Files | `components/ui/primitives.js` (new) |
| Tests | `primitives.test.js` — 19 |

`Button`, `Card`, `Pill`, `EmptyState`, `Field`, shared `inputStyle`. The press
moves `transform` only — asserted by test, because animating a layout property
is the family of fault behind D-01. `EmptyState` distinguishes "no data yet"
from "not recorded" from "failed to load"; the school's data needs all three.

### 9.3 The shell, and readable text on a phone

| | |
|---|---|
| Files | `Layout.js`, `Sidebar.js`, `Header.js`, `Login.js`, `InputBar.js`, `ChatInterface.js`, + 11 modals |

- **UX-DR7 mobile type scale delivered** (deferred out of Epic 2). Keyed to
  viewport width, not `pointer: coarse` — that was D-01's mistake. Controls and
  labels rise together, and the 16px iOS-zoom floor falls out of the scale.
- **139 hard-coded `isDark ? '#hex' : '#hex'` pairs replaced with tokens.**
  This was *why* the retheme initially did not reach the shell: switching theme
  recoloured the text (CSS variables) and left surfaces behind (JS literals).
- "Flo" copied verbatim from `Eduflow-Landing-Page` (markup + animations) —
  the same robot, not a lookalike. Appears on the sign-in screen and the chat
  greeting only; never on a working screen.
- The Aaryans crest + repeating wordmark behind the chat, modelled on the
  school's own enquiry form. Confined to the chat pane, non-interactive,
  hidden in dark (the JPEG's white background showed as a slab) and in
  high-contrast mode.
- **D-05 closed:** `project-context.md` said the sidebar was "120px fixed"; it
  is 260px, and 280px as a mobile drawer.

---

## Epic 3 — Finding One Record Among Two Thousand

### 3.1 A table that sorts, once, for the whole platform

| | |
|---|---|
| Files | `components/ui/DataTable.js` (new) |
| Tests | `DataTable.test.js` — 24 |

- **Sorting is server-side.** The component never sorts `rows`; it asks the
  caller to refetch. On a 20-row page the two are indistinguishable, and on a
  1,802-row table only one is honest. Asserted by test.
- `aria-sort` on each `<th>`; every sortable heading is a real `<button>`.
- A column is only offered as sortable if the **server** accepts that key.
- Empty values render "not recorded" — `dob`, `gender`, `house` and
  `admission_date` are blank for all 1,802 students because they were never
  collected, and a bare dash reads as a fault.
- One `<table>`, wrapper scrolls. Asserted, so D-01 cannot return.

### 3.2 Choosing how much you want to see

| | |
|---|---|
| Files | `hooks/useTablePrefs.js` (new) |
| Tests | `useTablePrefs.test.js` — 19 |

5/10/15/20/25/30, default **15**, **keyed per table**, sent to the API so the
**server** paginates. Every unusable stored value (absent, `'abc'`, `'50'` from
an older build, a float, a negative, blocked storage) falls back rather than
throwing — reading `localStorage` is parsing untrusted input, and a throw would
white-screen the list.

### 3.3 The lists people actually use

| | |
|---|---|
| Files | `routes/students.py`, `routes/staff.py`, `utils/class_order.py` (new), `StudentDatabase.js`, `StaffTracker.js` |
| Tests | `test_class_order.py` — 25 |

- Server sort whitelists widened to match what the table offers.
- **Class sort uses the school's real order** (NUR → LKG → UKG → 1st … 12th,
  then sections A–E) via a Mongo aggregation, not the random `class_id` UUID it
  sorted by before. `utils/class_order.py` is the server-side twin of
  `lib/classOrder.js`; the same cases are pinned on both sides.
- Student Database and Staff Tracker converted.

**NOT converted, and not claimed as done:** audit log, notifications, fee
transactions, attendance. Listed here so partial coverage is never reported as
complete.

---

## Live-data corrections (each separately approved)

| Field | Before | After |
|---|---|---|
| `school_settings.city` | `Lucknow` | `Joya, Amroha` |
| `school_settings.address` | `Sector 12, Jankipuram, Lucknow…` | the school's real address |
| `school_settings.phone` | `0522-4567890` | `+91-8126965555, +91-8126968888` |
| `school_settings.email` | `info@theararyans.edu.in` | `theaaryansjoya@gmail.com` |
| `school_settings.website` | `www.theararyans.edu.in` | `www.theaaryans.in` |
| `school_settings.principal` | `Adesh` | `ADESH SINGH` (read from the staff records) |
| `branches.branch-joya.location` | `Joya, Lucknow` | `Joya, Amroha` |
| `ai_memories` | "The Aaryans (CBSE, **Lucknow**)" | corrected |
| `branches.branch-ald` | "Aliganj Branch" | **deleted** (verified 0 references) |

Every change was read-before / write / read-after with a diff proving which
fields moved. Scripts refuse to run unless exactly one record matches.

**The AI memory mattered most** — the assistant had *memorised* the wrong city
and was answering from it.

**Caveat:** done directly rather than through the owner's School Settings
screen, so these are **not in the audit log**. Future corrections should use the
in-app route.

---

## Numbers

| | |
|---|---|
| Backend suite | **1745 passed / 2 failed (pinned) / 14 deselected** (baseline 1720/2/14) |
| New backend tests | 25 |
| New frontend tests | 102 (`designTokens` 40, `DataTable` 24, `useTablePrefs` 19, `primitives` 19) |
| Production build | compiles; warnings pre-existing |
| New `scoped_filter` hits | 1, annotated `# branch-scope: intentional` |
| Live-data fields changed | 8 + 1 record deleted |
