# Release 3 - the whole list, on any device

**This file is the ONLY record of what is done.** Read it first, update it last, every run.

Release 3 covers: filters, sorting, a working "All", exports everywhere, a whole-school
download for the owner and principal, and phone/tablet responsiveness across all 35 tables.

**Release 3 SHIPPED on 2026-08-12 and is LIVE.** All thirteen items went out together, as
Abhimanyu decided. Commit `810fe43`; backend `eduflow-release3-20260812-810fe43` (Green,
health all ok); frontend Amplify job 143 SUCCEED. Proof the new server code is really
running: `POST /api/export/table` answers 401 rather than 404, so it is live and still
guarded. Gates at ship: backend 3453 passed / 0 failed / 15 credentialed deselected;
frontend 439 passed at that point; production build and lint clean.

**Rollback target if ever needed: `eduflow-release2-20260812-accfc64`.**

*(These three lines read "CODE-COMPLETE and NOT deployed, main is at 0b74b6e" until the
moment it shipped. A deploy state written down without a date beside it goes stale within
hours and is then read as current. Always date it.)*

**`main` has moved past Release 3.** Four owner reports came in once it was live and were
fixed and deployed the same day: the staff-messaging send failing on every message, no
inactivity sign-out existing anywhere, the flat tool list on every profile except the
owner's and the principal's, and a duplicate group icon. **None of that is Release 3
scope.** It is written up in `CLAUDE.md` under "After Release 3", along with the three
things still open. Current `main`: `e6f82fb`.

---

## The one idea behind this release

Every serious fault found on 11 and 12 August was the same shape: **a query that quietly
returned less than it should.** A lookup matching nobody looks like a lookup with nothing
to do. A colleague missing to a 50-row cap looks like a colleague who left. "All" showing
one row looks like a school with one student.

So wherever this release adds an "all" view or an export, the count is visible and
truncation is impossible to mistake for completeness.

---

## Done

### 1. "All" actually shows all of it (SHIPPED 2026-08-12, green)

**This was live and wrong.** The rows-per-page menu has offered "All" on every table since
2026-08-06, but only the student list ever implemented it. Every other screen passed the
sentinel value (-1) straight through as the page size, and every server route clamped it
with `max(1, limit)`. `max(1, -1)` is 1. **Picking "All" showed exactly ONE ROW**, with no
error, on the School Directory (both tabs), the staff list and the notification list.

- New shared helper `frontend/src/lib/fetchAllRows.js`. Walks the pages, never sends the
  sentinel, **fails on a mid-walk error instead of returning a short list**, cannot loop on
  a server that over-reports its total, and sets `truncated` with the real total at a
  25,000-row safety ceiling so a partial answer is never dressed up as a complete one.
- Wired into StudentDatabase, SchoolDirectory (students and staff), StaffTracker and
  AllNotifications. Notifications also counts its unread badge from the rows in hand.
- New test `frontend/src/lib/__tests__/fetchAllRows.test.js`, 9 tests.

### 2. One page-size rule for every list (SHIPPED 2026-08-12, green)

The server used to carry **eight different ceilings** and a screen had no way to know which
one applied to it:

| Was | Routes |
|---|---|
| 500 | students, staff, message logs |
| 100 | chats, facility requests, maintenance schedule, vendors, thread messages, audit, file list |
| 50 | notifications, tech requests, incidents, announcements |
| 20 | leave requests |

Two faults lived in that table. The disagreement itself, and the shared `max(limit, 1)`
pattern that turned "show me everything" into one row without a word.

- New `backend/pagination.py`: one ceiling (`MAX_PAGE_SIZE = 500`), `clamp_page_size()` and
  `clamp_page()`. Over-asking is still capped, which two existing tests already relied on.
  **A page size below 1 is now refused with a 400 that says how to fetch every row
  instead** - never quietly turned into 1.
- Applied at all 16 clamp sites across 10 route files. Notifications went from 50 to 500,
  so a person's own history no longer takes ten times as many round trips as the roll.
- `page = 0` and negative pages are refused the same way. Some routes silently treated
  them as page 1; others produced a negative skip that surfaced as a 500.
- Frontend mirror: `PAGE_MAX` in `lib/api.js`, with the three per-list names kept as
  aliases of it. A per-list figure here is what let them drift.
- The leftover bespoke fetch-everything loop in `api.js` (`getAllStudents`) now uses the
  shared helper.
- New test `tests/backend/unit/test_pagination.py`, 24 tests.

**Three existing tests were updated on purpose, not worked around:**

| Test | Was pinning | Why it changed |
|---|---|---|
| `test_epic6_conversations.py::test_limit_is_clamped_server_side` | chats cap 100 | the cap is the shared one now |
| `test_epic6_notifications_paging.py::test_limit_is_clamped_server_side` | notifications cap 50 | the cap being evened out is the point of the item |
| `test_audit_routes.py::test_audit_log_rejects_invalid_pagination` | exact 400 wording | still a 400; the check moved into the shared module |

**One test was deliberately REVERSED**, and it deserves reading:
`FindingPeopleInLongLists.test.js` asserted that a mid-walk failure should return the rows
collected so far as a **success** carrying `meta.partial = true`, on the reasoning that half
a list clearly marked beats an error. The premise was false: **nothing in the codebase ever
read `meta.partial`.** Every caller was `if (r.success) setStudents(r.data)`. So it marked
nothing, and a picker showed 500 of 900 children while reporting a genuinely enrolled child
as not there. It fails loudly now.

**Gates after items 1 and 2:** backend **3,366 passed / 0 failed** / 15 deselected;
frontend **613 passed / 0 failed**; production build clean including lint.

### 3. The seven server exports: honest, and gated by the permission table (SHIPPED 2026-08-12, green)

Backend half of item 4. The screen buttons followed in items 4 to 6 below.

**Every export silently cut rows off.** Each ended in a fixed row limit with no count,
no total and no warning: children 2,000, fees 5,000, staff 2,000, expenses 1,000,
enquiries 1,000, attendance and results 10,000. The roll is 1,876 children, so 124 rows of
headroom, and the next intake would have started dropping children out of the downloaded
file with nothing to show it. Expenses and enquiries at 1,000 may already have been cutting.

An export is now **complete or refused**. `_read_all` asks for one row more than it will
accept, so it can tell the difference between "that is all of them" and "there were more".
Past 100,000 rows the request fails with a 413 saying to narrow it by date, and saying
plainly that no file was produced. Nothing is ever silently dropped.

**The permission gates did not match the Release 2 table.** They were hand-written role
checks that predated it and disagreed with it in both directions. `require_export` in
`backend/routes/exports.py` now derives the gate from `services/profile_matrix.py` by asking
whether the caller may open a screen that shows the data. There is no second list of role
names to forget to update. The four old helpers it replaced are gone from the imports.

| Who | Change |
|---|---|
| Sonu (accountant) | can now export the student list. He holds the School Directory, a fee belongs to a child, and he reconciles the two; the old gate refused him the list he works in daily. |
| Lalit (management) | can now export children, staff and enquiries. Still **refused fees and expenses**, and that is the wall Abhimanyu asked for by name. |
| Adesh (principal) | can now export fees and expenses. He holds every screen and the finance domain in the table, the fee-reminder screens were widened to him on 2026-08-08 for this exact reason, and the Release 3 whole-school download already includes fees for him. |
| Teachers | unchanged. Still their own classes' attendance and results only. |
| Dormant profiles | **refused, even where the table grants them the screen.** The front desk holds `student-database`, so mirroring screens alone would hand it a download of all 1,876 children the day it is switched on. Switching a profile on must include deciding what it may export. |

`scripts/audit_profile_reach.py` was taught the new gate, so the reach report stays complete
rather than listing seven routes as not understood.

**Four tests changed on purpose, each carrying its reasoning:** the principal on fees and
expenses (403 to 200), the accountant on students (403 to 200), `/api/export/expenses`
removed from the owner-only list in `test_owner_part3_qa.py`, and two stale headings in
`test_exports_xlsx.py` that claimed no gate had ever moved. Six new tests were added,
including the two that pin the truncation fix and one that pins the dormant-profile refusal.

**Gates:** backend **3,369 passed / 0 failed** / 15 deselected. Frontend untouched since
item 2, so still 613 / 0 with a clean build.

### 4. The download control, and the first five tables wired to it (SHIPPED 2026-08-12, green)

Item 4, part one. The machinery and five screens. **The remaining 30 tables are not
wired yet** - see the list below.

**A hole in item 3 above, found while building this and closed.** Item 3 promised
every export is complete or refused. It was not true for **Excel**. The route stopped
truncating, then handed the rows to the shared document builder, whose OWN ceiling is
5,000 rows and which trims to it and drops a note near the bottom of the sheet. The
payment ledger is about 10,700 rows, so an Excel download of it was quietly losing
more than half while the route above believed it had shipped the lot. The builder now
takes the caller's ceiling; the exports pass their own, which refuses rather than
trims. The builder's default is unchanged for Flo's generated documents, where a
reader is looking at a summary and trimming is the right trade.

**Two paths, one rule.**

- Seven data sets have a real export route. `downloadServerExport` uses it and passes
  the screen's live filters.
- The other 28 tables have none, and writing 28 more route handlers would be 28 more
  places for a row ceiling and a permission check to drift - which is most of what
  this release has been spent undoing. So `POST /api/export/table` packages rows the
  screen has ALREADY fetched through its own list endpoint. **This is not a way past
  the permission table:** the route reads nothing. It formats what the caller sent
  back to the caller, and the caller could only have obtained those rows by passing
  the gate on the endpoint they came from.

The rule both share: **the file is complete or there is no file.** Every failure path
throws with something a person can read, and none of them can save a half file.

- `frontend/src/lib/exportTable.js` - the two download paths, `collectAllRows` (walks
  every row matching the filters in force, turning each way a walk can come back short
  into a sentence), and `tableToRows`.
- `frontend/src/components/ui/ExportButton.js` - Excel and CSV as two plain buttons,
  not a menu: phone and tablet are the primary devices and a menu is one more tap to
  mis-hit. It **reports the row count it saved**, and reports failures out loud, in an
  `aria-live` region. A browser that silently saves nothing looks exactly like one
  that saved an empty file.
- `DataTable` takes an `exportTable` prop, so a screen already on the shared table
  gets the control in one line.
- Columns gained `exportValue` and `exportSkip`. A cell drawn from a nested object
  (`class_info`) or a badge would otherwise read correctly on screen and come out
  **blank in the file**, which nobody would think to check. Action-button columns are
  left out rather than exported as a column of empty cells.
- Spreadsheet formula guard: a cell opening with `=` or `@` is prefixed so Excel shows
  it rather than runs it. `+` and `-` are deliberately NOT guarded - the school's data
  is full of `+91` numbers and negative amounts, and prefixing those would turn real
  numbers into text and break the office's arithmetic.

**Wired so far (5):** the student list, the School Directory's two tabs, the staff
list, notifications. Each passes the filters that are in force, so a download of
"class 5 A, searched for Sharma" is those children and not the whole roll.

**The student list uses the generic path even though `/api/export/students` exists.**
Deliberate. That route takes no filters, so it would return the whole roll whatever
the screen was showing, and teaching it the filters would mean restating the filtering,
the branch scoping and the teacher narrowing in a second place. Walking the person's
own list endpoint makes the file and the screen agree by construction rather than by
assertion. The server export stays, for the whole-school zip and for Flo.

New tests: `exportTable.test.js` (9), `ExportButton.test.js` (7), six on the new route
and one pinning the Excel truncation fix.

**One regression was caused and caught here, worth remembering.** The builder's new
row ceiling was first written as `max_rows: int = MAX_ROWS`. A default argument is
evaluated once at import, so the constant stopped being live: every test and caller
that changes `MAX_ROWS` was silently ignored, and one existing test failed. It now
defaults to `None` and resolves at call time. The same trap made the new Excel test
pass for the wrong reason before the fix.

### 5. The download on every table that renders through a shared component (SHIPPED 2026-08-12, green)

**The real count is not 35.** Counted rather than estimated: **91 tables**, because a
tool screen often carries several. 81 of them now have a download.

**A central safety net, put in before the wiring rather than after.** Wiring seventy
tables by hand invites exactly one mistake: handing over the rows on screen instead of
every row that matches. That mistake produces a file that looks perfectly normal,
holds fifteen rows, and says nothing about the other 1,861. So the control now
compares what came back against the count the table is already showing beside its
rows-per-page menu, and **refuses to save a short file**, for every screen at once,
rather than depending on whoever wires each one having thought about it.

**74 tables in one change.** Those 13 tool screens do not use the shared paginated
table; they use `ToolPage.DataTable`, which takes rows as arrays of cells. The button
went there, exactly as column sorting did in July for the same reason. These screens
hand over their complete result set, so the file holds the whole table.

**One extractor, not two.** These cells are often drawn rather than written: a
coloured span holding an amount, a `Badge` reading "Draft". `sortableCellText` already
existed for sorting, so it was extended rather than duplicated. It gained a fallback
to the prop that carries a component's label, which fixed a real existing fault as a
side effect: a Badge keeps its only word in a prop, so **every Badge column had been
sorting as blank**, and would have gone into every file as an empty column.

**Also wired:** the class-strength summary and the chat list, which are on the shared
paginated table.

**Known and deliberate:** where a tool screen shows a summary on purpose - "Top 10
defaulters", the ten most recent expenses - the file holds that same summary, and the
table's own title travels into the filename so the file says which it is. A screen
that should offer the full list instead can pass `exportRows`.

**One test was changed on purpose.** `ToolTableSorting.test.js` found its sort button
by the accessible name `/x/i`, which now also matches the new "Excel" button. It
targets the sort button by test id instead. The behaviour under test did not move.

### 6. The hand-rolled tables, done one at a time (SHIPPED 2026-08-12, green)

**Item 4 is now COMPLETE.** Every table on the platform has a download. A sweep over
every file holding a `<table>` or a `DataTable` finds none without one.

Eight tables render their own `<table>` and cannot move onto a shared component
(D-24), so each got the control by hand, with its rows mapped to plain values. The
count was 8, not the 10 estimated last run: two of those "tables" were comments
mentioning the word.

| Screen | What its file holds, and the judgement in it |
|---|---|
| Payroll this month | **Money goes out as a NUMBER**, without the "Rs" the screen prints. The office downloads these in order to add them up, and "Rs 12,400" is text to a spreadsheet: it will not add. |
| Overdue records | Same rule for the amount. The threshold in days goes in the FILENAME, because a file called "overdue records" that used a different number of days than the screen did is a record nobody can reconcile later. Siblings are included, as on screen since Release 2. |
| Exam datesheet | What is ON SCREEN, unsaved edits included. Somebody who has typed the dates in and downloads before pressing Save must get what they are looking at. |
| Marks grid | One column per subject, built from the subjects **this person may see**, so a subject teacher's file holds their two columns exactly as the grid shows them. The download must not be the way around the privacy rule the grid enforces. A child with nothing entered gets a **blank** total, not a zero: a zero is a mark somebody scored, and a report confusing the two accuses a child of failing. |
| Substitution plan | The date is in the filename. A substitution plan with no date on it is not a record of anything. |
| Transport zone review | Distances as numbers, without " km". The saving is the **server's** figure, the one the screen prints, not this side's own subtraction of the two distances - a second opinion about the same number is how a file becomes the copy nobody can check. |
| Admission applications | Guardian name and phone included, though the screen shows the name only as a small line: an enquiry list somebody works through is useless without them. The class name is looked up as the screen looks it up, so the file does not hold a column of identifiers. |
| Attendance register | THIS DAY, and it says so in the filename, because the icon button in the header downloads the whole MONTH. Both now say which they are. The saved state is carried as a column, so a change that has not been saved yet is not presented as recorded. |
| Timetable | Keeps its GRID shape: one row per period, one column per day. Flattening it into a list would be a different document from the one on the wall, and printing the one on the wall is the point. |
| Flo's answer tables | A table Flo drew in a chat reply can be downloaded like any other. This is where somebody ends up when they asked a question rather than opened a screen, and retyping it into Excel is what they were doing before. |

**Known gap, small and deliberate.** A table Flo writes as plain markdown (rather than
as a structured answer) still has no download button on it. That path builds sanitised
HTML rather than a component, so a button cannot simply be placed in it. Those tables
are short by nature, and asking Flo for the same records "in Excel" now gives a
complete file (item 7). Worth doing if anyone asks; not worth restructuring the chat
renderer for now.

### 7. Asking Flo for a spreadsheet gives a COMPLETE one (SHIPPED 2026-08-12, green)

**This was the same fault, hiding in the one place it does most damage.** Flo could
already build an Excel workbook, through `draft_document`. But that tool formats rows
Flo is HOLDING: it fetches a page of students with a read tool and hands those rows
over. Ask it for "all 1,876 children in Excel" and you would get a sheet containing
whatever it happened to have seen, with nothing on the sheet to say so. A short screen
is an annoyance. A short file leaves the building and is filed as a record.

**New tool `export_data_file`.** It takes the NAME of a data set, not rows, and reads
them from the database through the same builder the download button on the screen uses.
Nothing passes through the model, so nothing can be dropped on the way.

- The seven export queries in `routes/exports.py` were split into builders returning
  (headers, rows, title). The routes are now three lines each. **One definition of what
  "the student list" is**, reached two ways.
- The gate is `may_export`, which is `require_export`'s own rule asked as a plain
  question, **not a second copy**. Management is refused the ledger and gets the
  children and the staff; the accountant gets both; dormant profiles are refused
  everything. A download is not a way around the permission table, and Flo is not
  either.
- It passes the export's row ceiling, so the Excel path refuses rather than trims.
- **It says how many rows are in the file.** "Here is your file" gives a person no way
  to notice a wrong one.
- "excel", "spreadsheet", "sheet", "xls" all mean xlsx, because nobody asks for "xlsx".
- `draft_document`'s description and Flo's prompt now say plainly which tool is for
  records and which is for something Flo wrote, and why picking wrong gives a file
  quietly missing most of its rows.

**Four guards fired on the new tool and every one was right.** It had to be classified
as a read rather than a write, given a read verb prefix, placed on a permission segment
(`shared`, like the spreadsheet import: the tool is neutral, the data set decides), and
the pinned per-profile reach counts had to be updated by hand. Every profile gained
exactly one read tool and **no write count moved**. Five dormant profiles can now see
the tool exists and are still refused every file by its own gate.

New test `tests/backend/parity/export_data_file_parity_test.py`, 17 tests, including
one pinning that Flo and the download button read the same rows.

**Abhimanyu, 2026-08-12, after seeing this work: a spreadsheet is NEVER trimmed.** A
person who asks Flo for records in Excel gets all of them. Two changes followed.

- `draft_document` used to cut any table at 5,000 rows and add a note. Excel and CSV
  now carry the export ceiling instead, which refuses rather than trims and sits far
  above the school's longest list. **Word, PDF and PowerPoint still trim and still say
  so**, on purpose: a five-thousand-row table in a letter is not a document anybody
  reads, whereas a spreadsheet is opened to be counted and reconciled, so a trimmed one
  is a wrong answer wearing the clothes of a right one.
- `export_data_file` was moved into the CORE tool set. Every other name in that set is
  a token trade; this one is a correctness guard. If Flo has to go and look the tool
  up, the failure when it does not bother is silent and bad: it falls back to
  `draft_document` and builds a sheet from the rows already in the conversation, which
  is short, looks complete, and gets filed.

**One existing test moved from `csv` to `docx`, deliberately.**
`test_a_truncated_document_says_so_in_the_reply` still pins that a trimmed DOCUMENT
says so. Two new tests pin that a spreadsheet is never trimmed and says nothing,
because there is nothing to say.

**Gates after item 7:** backend **3,396 passed / 0 failed** / 15 deselected. Frontend
**635 passed / 0 failed**. Production build clean including lint.

### 8. The timetable generator (SHIPPED 2026-08-12, green)

Added to Release 3 on Abhimanyu instruction, 2026-08-12, from a standalone
"AI Timetable Builder" he supplied as a zip.

**It is not a replacement, and saying so mattered.** That zip is a separate Next.js /
TypeScript / Supabase app with no logins and no permission model. A straight swap
would have thrown away what the platform timetable actually does: hold the school
timetable, obey who may edit, and feed the substitution plan. So the VALUABLE HALF was
ported - the solver - onto the platform own storage and rules, and the existing grid
stays as the thing that holds the result.

- `backend/services/timetable_solver.py`. Backtracking search, then a local-search
  polish pass, then four marks out of 100: spread across the week, teachers' preferred
  periods, morning subjects in the morning, and no subject twice running. Algorithm
  unchanged in substance from the original.
- `POST /api/academics/timetable/generate` and `/apply`, plus a panel on the timetable
  screen, shown only to the two people who may use it.

**THE ONE THING THAT HAD TO CHANGE, and it is not cosmetic.** The original only checks
teacher clashes INSIDE the one timetable it is building; its own comment says so. This
school has 48 classes sharing teachers, so generating 5A without looking at what Mr
Sharma already teaches in 6B produces a week that is impossible in real life - and the
substitution plan reads these rows, so it would then send a cover teacher to a room
where he is already teaching. The solver is now told every period every teacher is
already committed to in other classes. The polish pass re-checks it too, or it would
quietly put back the clash the search avoided.

**Generating never saves.** It returns a proposal with its marks; applying is a
separate deliberate tap. A week that appeared on its own is a week nobody has checked.
Applying REPLACES the class week rather than merging, re-checks every period against
what other classes hold, and refuses with a 409 if somebody booked that teacher in the
meantime.

**Who has it (Abhimanyu, 2026-08-12).** Aman and Adesh. Adesh writes the school
timetables himself, so it is his tool; Aman holds it because the owner is never shut
out of his own school. **Every generate and every apply writes an audit row**,
including failed ones, which is how Aman sees the tool being used on live data - a
tool that only leaves a trace when it works tells the owner half a story. **Lalit
keeps the timetable screen he has today** and can still hand-edit a period: nobody
asked for that to be taken away, so it has not been. Say the word if it should be.

New tests: `tests/backend/unit/test_timetable_solver.py` (16),
`tests/backend/api/test_timetable_generation.py` (20),
`frontend/src/components/__tests__/TimetableGenerator.test.js` (9).

### 9. The nightly CI failure on main, fixed (SHIPPED 2026-08-12, green)

Not Release 3 work, but red is red. The scheduled run of `main` failed on 10, 11 and
12 August with a staff test complaining that a login already belonged to somebody else.

**The product was fine; the test factory was not.** `student_data` and `staff_data`
built their identity fields from a four-digit random number, and the fake database
is shared for the whole session with nothing clearing it between tests. So every staff
record ever created in a run piles up, and two draws landing on the same four digits
produce the same email, phone and employee ID - at which point the create is correctly
refused and a test that was checking something else entirely fails. About forty
creations against nine thousand numbers, so it was a coin toss rather than a constant
failure, which is the worst kind of red build: it passes often enough that people
re-run it instead of reading it. Both factories now use a counter, which cannot
collide.

**Gates:** backend **3,432 passed / 0 failed** / 15 deselected. Frontend **644 passed /
0 failed**. Production build clean including lint.

---

### 10. The whole school in one file, for Aman and Adesh only (item B, SHIPPED 2026-08-12, green)

One Excel workbook, nine sheets: children, staff, fees and payments, attendance, exam
results, classes, transport, expenses, enquiries. On screen at the top of the School
Directory, and through Flo as `export_whole_school_workbook`.

**Built by LOOPING the builders, not by writing nine queries.** `EXPORT_BUILDERS` in
`routes/exports.py` already held seven; classes and transport were added to that same
dictionary rather than written beside the workbook. Nine fresh queries would have been
nine more places for a row ceiling and a scoping rule to drift away from the download
button on the screen, which is most of what this release has been spent undoing. Putting
them in the dictionary also means Flo can now download either on its own, so both needed
a permission entry or they would have read as broken.

**Nothing is ever trimmed, and there are two refusals behind that.** The reading refuses
first (`_read_all`, past 100,000 rows). If a builder is ever added that reads some other
way, `build_workbook` refuses a sheet it would have to shorten. A short sheet inside a
nine-tab workbook is this release's defining fault in the one place nobody would look for
it: nobody scrolls to the bottom of tab five to check.

**Every sheet says its own row count on its first line**, the response carries the counts
on a header so the screen can say what it saved without opening the file, and Flo reads
all nine back in its reply. A person cannot count 1,876 rows by eye.

**Money comes out as a NUMBER.** New `_workbook_cell` keeps numbers numeric instead of
stringifying them as the rest of the builder does. The office downloads the fee sheet in
order to add it up, and "12400" as text will not add. Booleans become Yes/No rather than
1/0, which beside a column of rupees reads as an amount.

**Owner and principal only** (Abhimanyu, 2026-08-12), which is exactly what the existing
`require_owner_or_principal` means, so no new gate was invented. Checked three times on
purpose: the route, Flo's own function, and the tool's leadership-only domain. This is the
largest copy of the school's data the platform can produce, so two of them would have to
fail together for it to reach the wrong desk. Sonu may export the ledger and Lalit may
export the children; neither may have the file holding both plus everything else.

**Storage went through the same guards.** `store_built_document` was added so the workbook
cannot slip past storage-not-configured and the daily cap, which `create_document` was
enforcing only on the build-and-store path.

**All four AI guards fired and each got a written decision:** classified read (it stores a
file and an audit row and changes no school record), read verb prefix, leadership segment,
and the pinned reach counts moved 162 to 163 for the two leadership profiles only, with
**no write count moving** and no other profile changing.

New tests: `tests/backend/api/test_whole_school_workbook.py` (20),
`frontend/src/components/__tests__/WholeSchoolExportButton.test.js` (9).

### 11. Filters on every tab, and the silent people-pickers (item C, SHIPPED 2026-08-12, green)

**Filtering, written once for about seventy tables.** It went into `ToolPage.DataTable`,
exactly as column sorting did in July and the download did in item 5, and for the same
reason: a filter written seventy times by hand is seventy chances to filter the screen and
forget the file. Two kinds, because people filter in two ways - a typed search that reads
every cell, and a picker on any column whose values repeat enough to be worth choosing
between. Columns of names get no picker: twenty names in a dropdown is worse than typing.

**The threshold is eight rows, deliberately low.** Abhimanyu asked for filters wherever the
data is OR COULD BECOME too much to go through by hand, so this is not reserved for the
tables that are long today. A list of eight is a list of eighty next term.

**The file follows the filter.** A download that quietly holds the whole list when the
screen was narrowed is the same fault as a short file, in the other direction: it gets
filed under the wrong name. Where a screen hands over a plain-value copy of its rows, it is
followed by position; if the two lists are ever different sizes the positions do not line
up, and the safe answer is the rows on screen, which are the ones the person is looking at.

**The count is always visible** - "Showing 24 of 1,876" - and a filtered-to-nothing table
says how many rows are hidden rather than "No data found", which reads as an empty school.

**A class filter on the School Directory**, going to the server like its search does.
Search finds a child you can already name; a filter is how somebody works THROUGH a group.
The download takes both with it.

**The silent pickers, closed.** Every caller of `getAllStudents` was
`if (r.success) setStudents(r.data || [])` with no `else`, so a failed load left an empty
picker with no message. On a school of 1,876 children an empty picker reads as "there are
no children", "nobody matches" or "this is broken" - three wrong conclusions, none of them
the true one. New `PeopleLoadNotice` says it out loud with a retry, and `loadStudentsInto`
also CLEARS the rows on failure: leaving a stale list behind a failure notice is how
somebody picks a child who is no longer on it. All 8 call sites across `AdminTools.js` and
`TeacherTools.js`.

New test: `ToolTableFiltering.test.js` (11).

### 12. Rows drawn as you scroll (item D, SHIPPED 2026-08-12, green)

"All" means ALL THE DATA, drawn as you scroll (Abhimanyu). Every row is still fetched and
held; what changes is that the browser is not asked to lay out 1,876 table rows at once. In
`ui/DataTable`, so the student list and the School Directory both get it, which are the two
long enough to be felt today.

**Grow-on-scroll rather than a virtual window, and the reason matters.** A windowed list
draws a fixed slice and moves it, which needs every row to be the same known height. These
rows are not: a child's cell carries a name with an admission number under it, and a
wrapped name on a phone is taller again. Guessing the height wrong makes the scrollbar lie
about how much is left, and this release is about not lying about how much there is.

**It never hides anything.** The count says how many are drawn AND how many are loaded,
because a list that has painted its first hundred rows must not look like a list of a
hundred rows. There is a button as well as the scroll: a scroll watcher that never fires
would otherwise strand the rest of the list in silence.

New test: `RowsDrawnAsYouScroll.test.js` (6).

### 13. Real phone and tablet profiles, and the pass over every table (item E, SHIPPED 2026-08-12, green)

**What was missing.** The only "mobile" project was Desktop Chrome with the window made
narrow: no touch, no device pixel ratio, a desktop user agent. That is a small desktop, not
a phone, and it is why the owner's iPhone 15 Pro report of 2026-08-06 was not caught by a
suite that was green at 390px. Two new projects carry the real things: `phone-pixel`
(Pixel 7, touch, 2.625x) and `tablet-ipad` (iPad gen 7, touch, 2x). Both run on Chromium
because WebKit is not installed here, so they prove the LAYOUT and the touch behaviour and
not Safari's engine - stated in the config rather than left to be discovered. The
zoom-on-focus rule is asserted by measuring computed font size, so it is caught either way.

**The sweep found real faults, and it collects them all rather than stopping at the first.**
New `tests/e2e/tables-on-a-phone.spec.js` walks every screen on the menu for five profiles.

| Device | Found | Fixed by |
|---|---|---|
| Phone | 6 controls under the 40px thumb floor, including back-to-chat on EVERY screen | raising the shared helpers: `ActionBtn`, the ToolPage Refresh button, `Btn`, `ActionButton`, the rows-per-page menu, the attendance P/A/L buttons |
| Tablet | **358 faults on one profile alone** | one CSS block |

**The tablet was being treated as a small desktop, and that is the real finding here.**
Every touch rule in the stylesheet stopped at 768px. An iPad is 810px wide, so it fell off
the end of all of them and inherited desktop sizes: 36px buttons, and 13px form fields that
make Safari magnify the page. Nobody had noticed because there was no tablet in the suite
until this item added one.

Fixed with one block keyed on `pointer: coarse` AND a width. Keying off input modality
alone is what caused D-01 in July: it fired in Chrome's simulator and put 16px dropdowns
beside 12px labels on a desktop. Pairing it with a width means it cannot catch a desktop at
a desktop size, and firing in device emulation is now exactly what is wanted, because that
is how the tablet is tested. The labels move with the controls, which was D-01's other half.

Two controls needed their own answer rather than a height floor. A **tick box** is square
and sized by width and height; stretching one with `min-height` gives an oval rather than a
bigger target, and on the spreadsheet-import screen a mis-hit tick box imports a column
nobody chose. A **slider** is dragged rather than tapped, so 16px tall is worse than a small
button: a finger landing beside the track moves nothing at all.

**One test-harness fault fixed on the way, and it is this release's own lesson.** The E2E
stand-in backend pinned its allowed origin to port 3000, so running the suite against any
other port made the browser silently DROP every reply and the sign-in page just sat there
with no error on it. A dropped response looks exactly like a server that never answered.

**Two checks are deliberately NOT in the E2E file**: "it says how many rows it is showing"
and "a wide table scrolls inside itself". The stand-in backend serves empty lists, so both
would have been passing on the harness rather than on the product, which is a worse answer
than not asking. They are pinned against real rows in the unit suite instead.

**Gates after all four items:** backend **3,453 passed / 0 failed** / 15 deselected.
Frontend **670 passed / 0 failed**. Production build clean including lint. Playwright
**11 passed** on the two new device projects, and **37 passed** across desktop, phone and
tablet on the responsive suite.

---

## Release 3 shipped on 2026-08-12 and is live.

All thirteen items went out together, as Abhimanyu decided. Commit `810fe43`; backend
`eduflow-release3-20260812-810fe43`; frontend Amplify job 143. Rollback target if ever
needed: `eduflow-release2-20260812-accfc64`.

`main` has since moved on to `e6f82fb` with four same-day fixes from owner reports found
once this was live. Those are NOT Release 3 scope; see `CLAUDE.md` under "After Release 3"
for what they were and for the three things still open.

## The one gap left open on purpose

A table Flo writes as plain MARKDOWN (rather than as a structured answer) still has no
download button on it. That path builds sanitised HTML rather than a component. Those
tables are short by nature, and asking Flo for the same records in Excel now gives a
complete file. Left alone on instruction; worth doing if anyone asks.

---

## Decisions from Abhimanyu, 12 August. Settled. Do not reopen.

- Ship Release 3 all together. The "All" fix does not go out on its own.
- "All" is offered on every table.
- **Exports need NO approval or confirm window.** Not on screen, not through Flo.
- **Exports MUST respect who is looking.** A download is not a way around the Release 2
  permission table.
- The whole-school zip is Aman (owner) and Adesh (principal) only, which maps onto the
  existing `require_owner_or_principal` gate.
- Zip contents are Excel sheets, not plain comma files, because the office uses Excel.
- Treat all 35 tables as equally important.
- Audit and undo work is **Release 4, separate.** Do not fold it in.

---

## Noted, not a Release 3 fault

`Epic6NothingGetsLost.test.js` ("1 of 2 deleted") failed once inside a full-suite run and
passed 39/39 three times in a row on its own. It is a timing flake under load, not a
regression. Left alone rather than papered over; if it recurs, it needs a real fix rather
than a longer timeout.
