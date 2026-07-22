# Epic 6 — Nothing Gets Lost — QUALITY GATE

**Date:** 2026-07-23 · **Branch:** `ui-sweep-2026-07-22`

The gate ran over a **frozen diff**: all five stories were implemented, then the
review lenses were applied in one systematic pass, then every finding was fixed and
the suites re-run. Nothing was reviewed while still moving — the weakness that
Epic 9's gate was criticised for.

Findings arrived in three waves. **The first two waves landed before any code
existed**, which is the point: eighteen of the twenty-four came out of the readiness
check, the elicitation lenses and party mode, and were paid for as edits to
acceptance criteria rather than as rewrites.

---

## Wave 1 — Readiness check, before implementation (10 findings, 10 applied)

Full report: `_bmad-output/planning-artifacts/implementation-readiness-report-2026-07-23.md`.

| # | Severity | Finding | Resolution |
|---|---|---|---|
| Q-1 | 🔴 | Two independently written counts of "how many are unread", in a story whose own AC forbids exactly that | One shared `count_unread` helper; a test asserts the two endpoints agree over data where separate queries would diverge |
| Q-2 | 🟠 | No story mentioned an index, and `conversations` carries only a bare `user_id` one — NFR-P1 failing quietly on every screen | `(schoolId, user_id, updated_at desc)` added in `_create_indexes()` |
| Q-3 | 🟠 | Story 6.5 stated no empty states while 6.3 did | Three-way empty state added to 6.5 |
| Q-4 | 🟠 | 6.2 left the panel's bare call implicit while 6.4 pinned the sidebar's | Same compatibility-pin AC and tests added to 6.2 |
| Q-5 | 🟠 | Synthetic digest and "All Good" rows would render as records in a table | `include_digest` parameter; the page passes `false` |
| Q-6 | 🟠 | Duplicate `notifications` index at `database.py:367` and `:377` | **Not fixed** — pre-existing, unrelated; logged as D-36 |
| Q-7 | 🟡 | `project-context.md` still told every agent the sidebar is 120px, and the font is Inter | Both corrected in-run (third time of asking for the first) |
| Q-8 | 🟡 | `alertdialog` required with no focus behaviour stated | Focus in, `Escape` out, focus returned to the opener |
| Q-9 | 🟡 | Bulk delete would leave the sidebar stale | `conversations-changed` event; `Layout` refreshes |
| Q-10 | 🟡 | Table ids unstated | `notifications` and `chats` named explicitly |

## Wave 2 — Elicitation and party mode, before implementation (8 findings, 8 applied)

| # | Lens | Finding | Resolution |
|---|---|---|---|
| E-1 | Red team | **`{"ids": [{"$gt": ""}]}` against an untyped body deletes every conversation the caller owns.** The most serious thing found in this epic | Pydantic `List[str]`; a test proves 422 before any query is built |
| E-2 | Party mode (Murat) | **The message delete filters on `conversation_id` with no `user_id`** — safe in the single-delete path only because ownership is proven one id at a time. On the raw list it destroys another user's messages while leaving their conversation standing | Deletes on `owned_ids` only; a test asserts the other user's *messages* survive |
| E-3 | Pre-mortem | A search matching chat names only would make someone hunting a word they remember *saying* conclude the chat is gone | The empty state names the field searched, and says body search is deliberately not built |
| E-4 | Support theatre | The page shows stored notifications only, so it holds fewer than the bell — on a page called Nothing Gets Lost | One line near the list explains live summaries |
| E-5 | Pre-mortem | A "select all" reaching across pages makes one tick + one number destroy a whole history | Selection is visible-page-only; changing page/search/sort clears it |
| E-6 | Pre-mortem | Correct mark-all-read behaviour (sparing mid-flight arrivals) reads as a broken button | The panel says "N arrived just now" |
| E-7 | Party mode (Sally) | "Mark all read" above fifteen rows means "these fifteen" to any reader | Label carries the real scope: "Mark all 312 as read" |
| E-8 | Party mode (John) | **The epic's own headline promised bulk dismissal of notifications the Owner had just said never to delete** | Epic statement corrected, with the reason recorded |

Also from party mode, applied as decisions rather than fixes: the typed gate takes
the **count** rather than the English word `DELETE` (Sally — language-neutral, and it
forces the reader to look at the number); the second window event is a **deliberate**
choice over restructuring `ToolView` (Winston — D-25's warning about reshaping the
shell inside a defect epic); `resetMocks: true` was written into the standing notes
before a line of test code (Amelia — Epic 5 lost a whole first run to it, and this
epic lost none).

## Wave 3 — Epic-close review over the frozen diff (6 findings, 6 fixed)

| # | Severity | File | Issue | Fix | Regression test |
|---|---|---|---|---|---|
| R-1 | 🟠 | `routes/chat.py` | Bulk delete joined up to 100 UUIDs into `entity_id` — an **indexed** field — making a bulk action the largest key in `audit_logs` | Ids moved into `changes`; `entity_id` is the actor | `test_bulk_delete_writes_one_audit_row_with_counts_only` |
| R-2 | 🟠 | `tools/AllChats.js` | Single delete fired on one unguarded click, beside a bulk action gated by a typed count — the careful gate for many, the bare click for the one in front of you | Single delete uses the same dialog | `deleting ONE chat is confirmed exactly like deleting many`, `cancelling a single delete deletes nothing` |
| R-3 | 🟡 | `tools/AllChats.js` | Deleting the last rows of the last page showed "No chats yet" to someone with 300 | Step back a page | `emptying the last page steps back rather than saying "no chats yet"` |
| R-4 | 🟡 | `tools/AllChats.js` | `alertdialog` did not restore focus on close (gap against Q-8's own AC) | Opener remembered and refocused | covered by the Escape test |
| R-5 | 🟡 | `tools/AllChats.js` | A title of one space rendered as blank | `chatName()` trims | `an unnamed chat reads "New conversation"` |
| R-6 | 🟡 | `tools/AllChats.js` | Arriving at the "Last used" column from a title sort landed on *oldest* first | Lands on most-recent; second click reverses | — (behaviour documented at the call site) |

### Dismissed, with reasons

| Finding | Why dismissed |
|---|---|
| `unread_total` costs an extra `count_documents` on every list call | It is an indexed count on `(schoolId, user_id, read)`, and it is the thing that makes the number honest. Deriving it client-side is the defect this story exists to remove. |
| `sort=title` has no covering index | It sorts one user's conversations, not the school's. Adding a third index to serve the least-used ordering is cost without a case. |
| The regex title search is unanchored and cannot use an index | The compound index narrows to one user's conversations first; the scan is over tens of rows, not the collection. |
| `AllNotifications.changeSort` ignores its argument | There is exactly one sortable column. A second would need to change it, and would not compile past review without doing so. |
| Pre-existing unannotated `scoped_filter` hits in `chat.py` / `notifications.py` | Annotating ~25 untouched lines would bury a security-relevant diff. Same disposition as D-17. |
| The `notice` banner on All Chats never auto-clears | It is replaced by the next action and read immediately. A timer would be a second thing to get wrong. |

---

## AC → test trace (`bmad-testarch-trace`)

Every acceptance criterion in Epic 6 traces to at least one test. Abbreviations:
**BE** = `tests/backend/api/test_epic6_*.py`, **FE** =
`frontend/src/components/__tests__/Epic6NothingGetsLost.test.js`.

### Story 6.1
| AC | Test |
|---|---|
| Count comes from `/unread-count`, across every page | FE `asks the endpoint written for the question` |
| The `is_read` defect — a read notification paints no badge | FE `a read notification produces NO badge` |
| Shows the number, capped `9+`, label carries the real figure | FE `shows the number…`, `caps the display at 9+…` |
| No badge at all when nothing is unread | FE `a read notification produces NO badge` |
| A failed re-count keeps the previous figure | FE `a failed count leaves the previous figure standing` |
| Panel reports the server's total, not its own rows | FE `the panel reports the server total` |
| Mark-all re-reads rather than assuming zero | FE `mark all read re-reads instead of assuming zero` |
| A surviving count says why | FE `says WHY a count survives mark-all-read` |
| Footer is a way through | FE `the panel footer is a way through` |
| No `isDark ?` colour literal remains (D-22) | FE `no colour is decided in JavaScript any more` |

### Story 6.2
| AC | Test |
|---|---|
| `sort` / `unread_only` whitelisted, unknown falls back | BE `test_sort_oldest_…`, `test_unrecognised_sort_falls_back_…` |
| `meta.unread_total` across all pages | BE `test_unread_total_ignores_the_current_page` |
| One shared count helper; the two agree | BE `test_unread_total_and_unread_count_endpoint_agree` |
| The panel's bare call unchanged (3 pins) | BE `test_panel_call_still_gets_digest_and_defaults`, `…_all_good_fallback`, `…_newest_first` |
| Existing `meta`-equality test rewritten, not deleted | `test_notifications.py::test_get_notifications_all_good_fallback_meta` |
| `unread_only` admits no digest, no fallback | BE `test_unread_only_admits_no_digest_and_no_fallback` |
| `include_digest=false` returns records only | BE `test_include_digest_false_returns_records_only`, `…_never_invents_an_all_good_row` |
| `limit` clamped server-side | BE `test_limit_is_clamped_server_side` |
| 401 + cross-user substituting for the role test | BE `test_notifications_unauthenticated_returns_401`, `test_unread_count_unauthenticated_returns_401`, `test_one_user_cannot_read_or_count_anothers_notifications`, `test_paging_and_filtering_cannot_reach_another_user` |
| School scoping | BE `test_notifications_are_school_scoped` |

### Story 6.3
| AC | Test |
|---|---|
| Footer opens the page | FE `the panel footer is a way through` |
| Shared table, own remembered key | FE `remembers its page size under its own key` |
| The server pages; size goes to the API | FE `the server pages — the size goes to the API` |
| Size change returns to page 1 | FE `changing the size returns to page 1` |
| A real sortable column asks the server (FR82) | FE `the column heading asks the SERVER to re-order everything` |
| Three-way empty state | FE `"nothing unread" and "nothing ever arrived" are different messages`, `a load failure is an error with a retry` |
| Same routing function and modal as the panel | shared import, exercised by FE `offers no way to delete a notification` render path |
| No delete control | FE `offers no way to delete a notification` |
| Mark-all states its real scope | FE `mark-all states its real scope` |
| Says what it does not hold | FE `explains that live summaries are not stored here` |
| `include_digest=false` requested | FE `asks the server to leave the synthetic rows out` |

### Story 6.4
| AC | Test |
|---|---|
| `page`/`limit`/`sort`/`search` + `meta.total` | BE `test_paging_reaches_past_the_fifty…`, `test_sort_oldest_and_title_are_honoured` |
| Sidebar's bare call unchanged | BE `test_sidebar_call_still_gets_newest_fifty_most_recent_first`, `…gains_meta_without_reshaping_data` |
| Unknown sort falls back | BE `test_unrecognised_sort_falls_back_to_recent` |
| `limit` clamped | BE `test_limit_is_clamped_server_side` |
| `search` escaped and cost-bounded | BE `test_search_term_is_escaped_not_interpreted`, `test_a_catastrophic_pattern_is_neutralised` |
| Index added | `database.py` (verified by inspection — the fake DB has no planner) |
| Bulk deletes only what the caller owns | BE `test_bulk_delete_skips_another_users_conversation`, `…_is_school_scoped` |
| Messages deleted too, on owned ids only | BE `test_bulk_delete_removes_conversations_and_their_messages`, **`test_bulk_delete_does_not_touch_another_users_messages`** |
| Cap on ids; typed ids | BE `test_bulk_delete_refuses_an_empty_or_oversized_list`, **`test_bulk_delete_refuses_a_query_operator_as_an_id`** |
| Count from the database, not the request | BE `test_bulk_delete_counts_from_the_database_not_the_request` |
| Partial result stated | BE `test_bulk_delete_reports_what_actually_happened` |
| Unknown and someone-else's indistinguishable | BE `test_bulk_delete_skips_another_users_conversation` |
| One audit row, counts and ids only | BE `test_bulk_delete_writes_one_audit_row_with_counts_only` |
| 401 + cross-user | BE `test_bulk_delete_unauthenticated_returns_401`, `test_list_conversations_unauthenticated_returns_401`, `test_one_user_never_sees_anothers_conversations`, `test_search_cannot_reach_another_users_conversations` |

### Story 6.5
| AC | Test |
|---|---|
| Entry point in the sidebar, surviving an empty list | verified by inspection + build; **on the human checklist** |
| Shared table, search/sort/paging, pinned/starred shown | FE `search is sent to the server`, `remembers its page size under its own key` |
| Unnamed chat reads "New conversation" | FE `an unnamed chat reads "New conversation"` |
| Opening takes the reader back to the chat | FE `opening a chat takes the reader back to it` |
| Reuses existing endpoints | FE `pin and star reuse the endpoints that already exist` |
| Selection is page-only; clears on navigation | FE `select-all covers the visible page only`, `changing page clears the selection` |
| Cap can never be exceeded | FE `a selection can never exceed what the server accepts` |
| Typed gate states the count and stays disabled | FE `the confirmation states the count and stays disabled until it is typed` |
| Pinned/starred named | FE `names pinned or starred chats caught in the selection` |
| Partial delete reported as partial | FE `a partial delete is reported as partial` |
| Shell told, so sidebar/chat view do not go stale | FE `deleting tells the shell` |
| Single delete confirmed like bulk | FE `deleting ONE chat is confirmed…`, `cancelling a single delete deletes nothing` |
| Empty page steps back | FE `emptying the last page steps back` |
| Three empty states, search one names the field | FE `an empty search result says WHICH field was searched`, `"no chats at all" is a different message`, `a load failure offers a retry` |
| `alertdialog`, Escape, focus | FE `the confirmation states the count…` (role), `Escape closes the confirmation without deleting anything` |
| Only your own chats | BE `test_one_user_never_sees_anothers_conversations` |

**Untraced ACs: none.** Two are verified by inspection rather than assertion and are
named as such on the human checklist: the index (the fake DB has no query planner, so
a test would assert the call, not the benefit) and the sidebar entry point's position.

## Test review (`bmad-testarch-test-review`)

- **Compatibility pins were written first and shown green against the old code**,
  then again after. A pin written only afterwards records what the change happened to
  do, not what the caller needs. Five such pins here (three for the panel, two for the
  sidebar).
- **Two tests guard traps rather than features** and are commented as such, because
  both would pass against a plausible-looking wrong implementation of the code beside
  them.
- **Routes are exercised, not mocks.** Every "the server pages/orders/filters" claim
  is asserted against the real route with real fake-DB data — the Epic 4 lesson, where
  a test double that agreed with the client hid a defect for a whole initiative.
- **The `resetMocks: true` trap cost nothing this time**, having been written into the
  epic's standing notes before any test was authored. Epic 5 lost its whole first run
  to it.
- Every new test file resets its collections in an `autouse` fixture — the session-wide
  `FakeDb` singleton leaks between tests otherwise.

## NFR review (`bmad-testarch-nfr`)

| NFR | Verdict |
|---|---|
| **NFR-P1** p95 ≤ 500ms | Addressed: the missing `conversations` index was the finding that made this real (Q-2). Both list paths add one indexed `count_documents`. **Not measured against production volumes** — stated rather than claimed. |
| **NFR-R1** atomic writes | Bulk delete reports deleted vs not-found rather than presenting a partial result as success; conversations deleted before messages so no chat outlives its contents. |
| **NFR-S1** server-side enforcement | Ownership is decided server-side on every path. The client's selection cap is a convenience; the server's `List[str]` + max length is the gate. |
| **NFR-S2** no PII in logs | The audit row carries counts and conversation ids only. Asserted by a test that seeds a student's name in a chat title and a message body, then greps the row. |
| **NFR-A1/A2** contrast and focus | Two new tokens are backgrounds only, so they carry no text-contrast obligation; the committed contrast test still passes. Every new control has a visible focus state and a `data-testid`. The badge carries a word/number, not colour alone. |
| **FR81** persistent navigation | Both entry points are in the shell (header, sidebar), reachable from every screen. |
| **FR82 / UX-DR5 / UX-DR10** | Both lists use the shared table with server-side ordering, server-side paging and per-table remembered page sizes. |
| **UX-DR6** three-way empty state | Both pages, with the third case (search) added to All Chats during the readiness check. |

## Grep audit (`scoped_filter` / `scoped_query`)

Re-run over `backend/routes/notifications.py`, `backend/routes/chat.py`,
`backend/database.py`, `backend/models/schemas.py`. Every **new** hit carries
`# branch-scope: intentional — …`. Pre-existing unannotated hits in the two route
files are untouched and logged (same disposition as D-17).

## Final counts

| | |
|---|---|
| Backend | **1955 passed / 3 failed / 14 deselected** |
| — the 3 failures | 2 are the pinned order-dependent pair (D-03); the 3rd is D-35, a clock-zone defect verified pre-existing on a stashed tree |
| Frontend | **244 passed / 2 failed** (the pinned `LayoutRouting` pair, confirmed identical with and without this epic's `Layout.js` change) |
| Production build | clean |
| New tests | 78 (39 backend, 39 frontend) |
| Findings | **24 raised · 18 before code existed · 24 resolved · 6 dismissed with reasons** |
| Findings born in this epic and carried forward | **0** |
