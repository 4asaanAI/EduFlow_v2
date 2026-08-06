# Owner requests, 2026-08-06 night — investigation and execution plan

Source: Abhimanyu relaying 20 items, most of them Aman's (the school's owner) own
observations, with screenshots. Branch: `main` (one unpushed docs commit already sits
there). **No commit, no push until Abhimanyu says so** — every push to `main` starts a
paid Amplify build, and he is still adding to the list.

Rule for the whole batch: **frontend changes are safe** (Amplify ships them on push and
they are easy to reverse). **Backend changes need a separate Elastic Beanstalk deploy** and
are therefore built, tested and flagged, not deployed, tonight.

---

## What is actually broken, per item

Findings are from reading the code, not from guessing.

| # | Root cause found | Where | Deploy |
|---|---|---|---|
| 1 | `hubItemsForUser()` short-circuits on `audience === 'owner'`, so the owner is shown **every** item in a hub including the ones tagged `principal`. Principal Daily is one of thirteen. | `lib/managementHubs.js:118-123` | frontend |
| 2 | Hard-coded sentence rendered by the one shared hub component, so it appears on all nine. | `tools/ManagementHub.js:31` | frontend |
| 3 | Refresh cookie is `samesite="strict"`. Site is `main.ddxpej151tf13.amplifyapp.com`, API is `dapbq24rsje5g.cloudfront.net` — **different sites**, so the browser never sends the cookie. Silent renewal always fails, so the 60-minute access token simply expires. Nothing to do with inactivity. | `services/auth_tokens.py:53-62`, `middleware/auth.py:75` | **backend** |
| 4 | No notes/remarks field exists anywhere on students or staff. Confirmed by Flo's own answer in the screenshot. | new | **backend** + frontend + AI |
| 5 | Token badge is rendered directly in the sidebar body. | `Sidebar.js:840` | frontend |
| 6 | `TOOL_GROUPS.owner.bottom` and `.principal.bottom` are `[]` after the enterprise regrouping, and Help & Support renders exactly that list. The two tools (Audit Log, Query & Support) still exist and still work — only the menu link was dropped. | `Sidebar.js:202-211, 889` | frontend |
| 7 | 28px avatar + 14px gutter drawn on every assistant message. | `MessageRenderer.js:512-521` | frontend |
| 8 | Markdown tables are emitted as bare `<table>` inside `dangerouslySetInnerHTML` with no scroll container, so the whole message row overflows. (The *rich* table block at line 232 already scrolls correctly — only the markdown path is wrong.) | `MessageRenderer.js:158-172, 524-532` | frontend |
| 9 | **The student is not deleted.** `DELETE /api/students/{id}` only sets `is_active: False, status: "withdrawn"` and writes an audit row. The count of 1801 excludes them. But there is currently **no way to reverse it**: `is_active` is not in `UPDATABLE_FIELDS`. Row buttons do carry icons; they are 12px and inherit a low-contrast colour. | `routes/students.py:503-527`, `services/student_service.py:29-33`, `tools/StudentDatabase.js:708-710` | **backend** + frontend |
| 10 | Two tiers already exist in code (soft deactivate, and owner-only `POST /{id}/erase` which takes a reason) but neither is surfaced as a list, the reason is optional, and there is no NSO-vs-TC distinction. Audit log is already complete and searchable but is visible to `it_tech` and `management` admins too. | `routes/students.py:695`, `routes/audit.py:34-45` | **backend** + frontend |
| 11 | No `address` on the student schema or in `UPDATABLE_FIELDS`; no address on staff `PROFILE_FIELDS`. A generic upload endpoint with `entity_type`/`entity_id` already exists and is the right foundation for ID documents. | `models/schemas.py:252`, `services/student_service.py:29`, `routes/staff.py:50`, `routes/upload.py:90` | **backend** + frontend |
| 12 | `house` is stored, editable and already colour-coded in the detail panel — it was simply never added as a table column. | `tools/StudentDatabase.js` | frontend |
| 13 | `PAGE_SIZES` stops at 30 by an owner decision taken 2026-07-22, before the list had 1,802 rows. Server caps one request at 500. | `hooks/useTablePrefs.js:17` | frontend |
| 14 | Sidebar always renders a 52px logo; the header renders a second one on phones only. | `Sidebar.js:616` | frontend |
| 15 | Account block lives at the bottom of the sidebar. | `Sidebar.js:849-940` | frontend |
| 16 | **Real bug.** The picture pipeline falls back to the paid vision service only when the free reader *ran and found no text*. When the free reader is **not installed** (which is the case on the live server) the code returns "not available" and never tries the fallback. | `routes/chat_upload.py:310-315` | **backend** |
| 17 | Already shipped: `/stop-slop` is a built-in habit rendered into every Flo system prompt. Needs verifying live and extending to the document-generation prompts. | `ai/builtin_skills.py`, `ai/prompts.py:1622,1878` | verify |
| 18 | Each remembered note is `whiteSpace: nowrap` + ellipsis, one line, no scroll. | `MessageRenderer.js:414-419` | frontend |
| 19 | Back calls `setActiveToolParam(null)`, which drops the tool entirely. There is no screen history. Back is also hidden on phones by design. | `Layout.js:361`, `Header.js:502` | frontend |
| 20 | Table borders and scrollbar treatment in the shared table components. | `tools/ToolPage.js:298+` | frontend |

---

## Knock-on work the 20 items imply

These are not extra scope; they are what each item cannot ship without.

- **Item 4 → Flo.** Two new AI tools (`get_profile_notes`, `add_profile_note`), entries in
  the tool registry, the role gate (owner + principal only), the write-tool parity corpus
  (mandatory per `CLAUDE.md`), and the confirm-card flow so an AI-written note is confirmed
  before it lands.
- **Item 4 → School Directory.** A Notes column and a note panel on both directory tabs.
- **Item 4 + 11 → uploads.** Attachments need a `notes`/`profile-docs` entity type and the
  `{school_id}/uploads/...` key convention (Part 6 rule).
- **Item 10 → attendance.** NSO students must **still appear in daily attendance**;
  TC-issued students must not. Today, deactivating removes them from everything. This means
  the attendance query has to change, not just the student list.
- **Item 10 → Flo.** Flo must know the difference, or she will answer "1,801 students" when
  the honest answer is "1,801 active, 3 on the NSO list".
- **Item 10 → audit visibility.** Remove `audit-log` from the `management` sub-category
  allow-list and from the `it_tech`/`management` branches of the audit route.
- **Item 9 → a live data change.** Restoring the student is a write to the school's real
  database. It will be done by Abhimanyu clicking Restore in the product, not by an agent
  reaching into MongoDB.
- **Every new endpoint** needs its two security tests (unauthenticated 401, wrong role 403)
  per the standing convention.

---

## Order of work

Sequenced so the safe, visible wins land first and the risky data work happens with a clear
head, and so that any stopping point is a coherent one.

**Block A — pure layout, no data (items 2, 5, 6, 7, 14, 18, 12, 13)**
Small, independent, each visible immediately on the local server.

**Block B — navigation and menus (items 1, 15, 19)**
Touch the shell, so they land together and get one round of clicking through every role.

**Block C — chat rendering (items 8, 20, 17-verify)**

**Block D — the data work (items 9, 10, 11, 4)**
Backend first, then screens, then Flo. Item 10 is the spine; 9 falls out of it.

**Block E — backend-only fixes to flag, not deploy (items 3, 16)**
Written and tested tonight, deployed when Abhimanyu says so in daylight.

---

## Decisions needed from Abhimanyu

1. **Item 1.** The owner currently sees thirteen principal-tagged tools. Hiding all of them
   would also take away Timetable, Academic Structure, Attendance marking, Transport, Parent
   Messages and Student Transfer. Default taken: hide **only Principal Daily**, the one named.
2. **Item 10.** Confirm NSO students keep appearing in daily attendance, and that the third
   state is "TC issued" (removed from attendance, still in the recycle bin) before permanent
   erase. Also whether NSO applies to staff and teachers as well as students.
3. **Item 4.** Confirm notes are owner + principal only, and that a note is visible to both
   of them (not private to its author).
4. **Item 15.** Confirm the account block leaves the sidebar entirely rather than appearing
   in both places.

---

## Verification

- Local dev server (backend on 8000, frontend on 3000) rather than driving Abhimanyu's Chrome.
- Backend suite and frontend suite must both finish at **0 failures**. No pass count is pinned.
- Responsive check at phone width for every screen touched.
