# Epic 6 — Nothing Gets Lost — COMPLETED

**Date:** 2026-07-23 · **Branch:** `ui-sweep-2026-07-22`
**Owner items:** 14 (View all + mark all read), 16 (All Chats page)

> **NOT YET VISIBLE TO THE OWNER.** Every change in this epic is frontend or API
> behaviour on a branch. None of it reaches his screen until a deploy. Stated first,
> per the D-15b rule, so nothing below is read as "done for him".

---

## The three decisions taken before any code was written

Put to Abhimanyu on 2026-07-23, because all three change what a person is allowed
to do (the D-18 rule). Two of the three are refusals, and those matter most — a
later reader finding the feature absent would otherwise build it.

| Question | Decision | Where it lands |
|---|---|---|
| May several chats be deleted together? | **Yes, behind a typed confirmation** | Story 6.4 (route), 6.5 (the gate) |
| Does "clearing" a notification delete it? | **No — mark-as-read only, nothing is ever destroyed** | Story 6.3 has no delete control, and no delete endpoint was written |
| May the Owner read other people's chats here? | **No — everyone sees only their own** | Story 6.4, asserted by a test |

---

## Story 6.1 — The bell tells the truth about what is waiting

**The defect, which had been there since the feature shipped.** `Header.refreshUnread`
counted `list.filter(n => n && !n.is_digest && !n.is_read)`. **`is_read` does not
exist anywhere in the product** — `services/notification_service.py:44` writes the
field as `read`. So `!n.is_read` was true for every notification, read or not: the
red dot appeared whenever the signed-in person had *any* notification at all and
never cleared. The comment directly above it described the opposite intent. It also
only ever looked at page 1, while `GET /api/notifications/unread-count` — written
for exactly this question, counting across every page — was called by nothing.

**What changed**

| Before | After |
|---|---|
| Counted a field that does not exist, over page 1 only | Reads `/notifications/unread-count`, scoped to the caller, across every page |
| A 7px dot: "something exists" | The number, capped at `9+`, with an accessible label carrying the real figure |
| Dot painted whenever any notification existed | No badge at all when nothing is unread — not a zero, not a grey dot |
| A failed request would have shown nothing | A failed re-count leaves the previous figure standing |
| Panel said "20 unread" with 60 unread | Panel reports the server's `unread_total` |
| "Mark all read" set local state and never re-read | Re-reads, and **says why** a count survives (`N arrived just now`) |
| Footer: a dead label, "N notifications total" | The way through to the All Notifications page |

**Files:** `frontend/src/components/Header.js`, `frontend/src/lib/api.js`.

**Also closed here — D-22's last component.** `NotificationsPanel` still computed
nine `isDark ? '#hex' : '#hex'` pairs, the one part of the shell Epic 9 missed. All
replaced with tokens; a committed test greps `Header.js` and fails if one returns.
Two new tokens (`--color-unread-tint`, `--color-accent-blue-subtle`) are defined in
both themes, lighter in light — the same alpha over white reads far stronger than
over near-black, so a straight copy would have made an unread row look selected.

## Story 6.2 — The notification list can be asked for more than its first page

`GET /api/notifications` now accepts `sort` (`newest`|`oldest`), `unread_only` and
`include_digest`, all whitelisted server-side with an unrecognised value falling
back to the default rather than reaching a query.

- **`meta.unread_total`** — the count across all pages. **One shared helper**
  (`count_unread`) serves both this and the `/unread-count` endpoint, so the badge,
  the panel and the page cannot drift. A test seeds data where two separate queries
  would diverge — read and unread mixed, a digest row present, several pages, a
  second user's rows — and asserts the two responses agree.
- **`include_digest=false`** keeps the synthesised digest rows and the fabricated
  "All Good" row out of a table that has a row count and a page indicator.
- **The panel's bare call is unchanged and pinned by three tests** written and shown
  green against the old endpoint first: digest on page 1, the "All Good" fallback,
  newest first.
- **`limit` still clamps to 50** server-side; the client's menu tops out at 30.

**Rewritten, not deleted (D-14):** `test_get_notifications_all_good_fallback_meta`
asserted the whole `meta` dict by equality, which made *adding* a key a failure. It
now asserts the contract it was really guarding.

**Files:** `backend/routes/notifications.py`.

## Story 6.3 — A page that shows every notification, not the newest twenty

New page, `?tool=all-notifications`, reached from the bell panel's footer — which
is in the header, on every screen (FR81), so no per-role nav list needed editing.

- Shared `DataTable`, table id **`notifications`**, its own remembered page size.
- The **server** pages and orders; changing the size returns to page 1.
- A real sortable column heading on **When** (FR82) — a `<button>` in the `<th>`
  with `aria-sort`, asking the server to re-order the whole set.
- **All / Unread** filter. **No delete control**, per the Owner's decision.
- "Mark all read" states its real scope: **"Mark all 312 as read"**, not a bare
  label above fifteen visible rows.
- Three distinct empty states: nothing ever arrived · nothing unread right now ·
  failed to load (with a retry, `role="alert"`, never an empty table).
- **It says what it does not hold.** The bell shows stored notifications *and*
  live summaries computed per request (pending approvals, overdue fees,
  announcements). This page holds only the stored ones and will legitimately show
  fewer. One line near the list says so — otherwise this is the screen on which
  Tuesday's leave request appears to have been lost, on a page called Nothing Gets
  Lost.
- Opening a row uses the **same** `getToolForNotification` and the same detail
  modal as the panel. Two screens deciding independently where a notification leads
  is how they drift.

**Files:** `frontend/src/components/tools/AllNotifications.js`, `Layout.js`.

## Story 6.4 — The chat history can be asked for more than its newest fifty

`GET /api/chat/conversations` did `.to_list(50)` with no page, no limit, no search
and no total. **The fifty-first-oldest conversation was unreachable by any route in
the product.** It now accepts `page`, `limit` (clamped to 100), `sort`
(`recent`|`oldest`|`title`, whitelisted) and `search`, and returns `meta.total`.

- **The sidebar's bare call is unchanged and pinned by tests** — same newest fifty,
  same order, same shape, `meta` added alongside.
- **`search` is `re.escape`d and length-capped.** Escaping bounds what a term
  *means*; the cap bounds what it *costs*.
- **New index** `(schoolId, user_id, updated_at desc)` in `_create_indexes()`.
  Without it both the sidebar and the new page sort a user's whole history in
  memory on every load. `notifications` already had what it needed.

**`POST /api/chat/conversations/bulk-delete`** — owner-approved, and two things in
it are load-bearing:

1. **The body is a Pydantic `List[str]`, never `await request.json()`.** Against an
   untyped body, `{"ids": [{"$gt": ""}]}` builds a query matching **every
   conversation the caller owns** — a request that reads "delete these three" and
   executes as "delete everything". Now a 422 before any query is built.
2. **The message delete uses `owned_ids`** — what the ownership query actually
   returned — **never the caller's raw list.** The messages filter carries no
   `user_id`; it is safe in the single-delete path only because ownership is proven
   one id at a time first. Passing the raw list would destroy another user's
   messages while leaving their conversation standing: a chat they can open and find
   empty, with nothing in any log to explain it.

Also: ids deduplicated, the count taken from the database rather than `len(ids)`,
conversations deleted before messages (an orphaned message is invisible; a
conversation outliving its messages opens empty), a partial result reported as
partial, an unknown id and someone else's reported identically, and one audit row
carrying counts and ids only — never a title or message text (NFR-S2).

**Files:** `backend/routes/chat.py`, `backend/models/schemas.py`, `backend/database.py`.

## Story 6.5 — A page that shows every chat, and lets you clear out the ones you are done with

New page, `?tool=all-chats`, reached from the sidebar's Recent Chats header.

- Shared `DataTable`, table id **`chats`**, server-side search, sort and paging.
- **The entry point survives an empty list.** The whole Recent Chats zone used to
  be hidden when there were no conversations (`conversations.length > 0`), so
  someone with no recent chats would have had no route to the archive at all.
- Opening a chat dispatches `open-conversation`; `Layout` clears the active tool
  and opens it. Deleting dispatches `conversations-changed`; `Layout` refreshes the
  sidebar and, if the open conversation was one of the deleted, returns to a new chat.
- **Selection covers the visible page only.** A select-all reaching across forty
  pages of search results would let one tick and one typed number destroy an entire
  history. Changing page, search or sort clears the selection.
- **The typed gate takes the count, not the word `DELETE`.** The Owner asked for a
  typed confirmation; the usual English keyword is a spelling test for people who
  work in English and Hindi, and adds friction without adding safety. Typing the
  number forces the one thing the gate exists for — looking at how many you are
  about to destroy. **Flagged on the human checklist so he can overrule it.**
- Pinned and starred chats are **not** protected (his choice) but are **named** in
  the confirmation.
- **Single delete goes through the same gate.** The sidebar deletes on one
  unguarded click; copying that beside a typed-count bulk action would mean the
  careful gate is the one you get for many and the bare click the one you get for
  the chat you are looking at.
- `alertdialog`, focus moves in, `Escape` closes without deleting, focus returns to
  the control that opened it.
- Emptying the last page steps back rather than showing "No chats yet" to someone
  who still has three hundred.
- Three empty states — and the search one **says which field was searched**, because
  someone looking for a word they remember *saying* will otherwise conclude the chat
  is gone. Searching message bodies was deliberately not built: it needs a text index
  over every message in the school.

**Files:** `frontend/src/components/tools/AllChats.js`, `Layout.js`, `Sidebar.js`,
`frontend/src/lib/api.js`.

---

## Numbers

| | |
|---|---|
| Stories | 5 |
| New backend tests | **39** (17 notifications, 22 conversations) |
| New frontend tests | **39** |
| Backend suite | **1955 passed / 3 failed (pre-existing) / 14 deselected** |
| Frontend suite | **244 passed / 2 failed (pre-existing LayoutRouting)** |
| Production build | clean |
| Live-data writes | **0** |

## Baseline correction — the pinned figure was wrong, and here is why

The handoff pinned "1917 passed, 2 failed". This run measured **1916 passed, 3
failed** on a clean tree *before any change*, and the third failure is real:

`test_receptionist_p11.py::test_visitor_duplicate_returns_409_with_duplicate_field`
seeds a visitor with `datetime.now()` (**local**, IST) and the service computes
"today" from `actor_ctx.now()`, which returns **UTC**
(`services/actor_context.py:21`). Between 00:00 and 05:30 IST the two dates differ,
the duplicate lookup searches the wrong day, and the test fails. This run happened
at about 02:00 local, so it failed; the baseline was recorded during the day, so it
passed. **Pre-existing, verified on a stashed tree, not touched.** Logged as D-35.

## Whole-epic grep audit

`scoped_filter`/`scoped_query` re-run over all four touched backend files. Every new
hit carries `# branch-scope: intentional — …`, and the reason is the same in each
case and worth stating: **notifications and conversations belong to one user, and
`user_id` is strictly narrower than `branch_id`.** Neither document type carries a
`branch_id` field at all, so `scoped_query(branch_id=...)` would match nothing and
silently empty every bell and every chat history in the school.
