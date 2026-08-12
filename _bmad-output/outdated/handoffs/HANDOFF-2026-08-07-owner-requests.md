# Handoff — owner requests of 2026-08-06, second session

Read `_bmad-output/planning-artifacts/owner-requests-2026-08-06.md` first: it has the root
cause and the exact file for all twenty items. This note is about where the work stands now.

**The two hard constraints still apply and both still bite:** never start a stopped EC2
instance (one vCPU in the account, the backend is on the only slot), and never run
`backend/migrations/run_all.py` against production. A third: no agent writes to the live
school database. Anything that changes a real record is done by a person pressing a button.

---

## Rules for this batch, from Abhimanyu

- **Nothing is committed and nothing is pushed.** He is still testing and adding to the list.
  There is also one older unpushed commit on `main` (`642347f`, the migration docs).
  Everything goes out as **one push at the end**, because each push to `main` starts a paid
  Amplify build.
- Website changes reach the school automatically. **Backend changes need a separate deploy**,
  and are to be flagged, not deployed by an agent.
- Plain human language in everything written to him. No em dashes in prose.

---

## Where it stands: 19 of 20 done, plus the extra notes of 2026-08-07

Both suites green at the point of writing: backend **2,289 passed / 0 failed / 15 deselected**,
frontend **483 passed / 0 failed**, production build clean, live health check `ready`.
Those counts record this moment; they are not a target. **The bar is the FAILURE count and
it is zero.** Never pin a pass count (D-51/D-56).

Items 1, 2, 3, 5, 6, 7, 8, 9, 12, 13, 14, 15, 16, 17, 18, 19 were finished in the previous
session and are unchanged. What this session added:

### The half-applied audit rule — CLOSED

`routes/audit.py` let `it_tech` and `management` admins read the action log while the menu
already restricted it to owner and principal. Both endpoints now use one named list,
`AUDIT_READER_SUB_CATEGORIES`, and the offer side was closed too: `toolPermissions.js`
grew a per-tool allow-list (it only knew about certificates before), and `audit-log` came
out of the `management` list in `Sidebar.js`. Tests:
`tests/backend/unit/test_audit_routes.py` and `frontend/.../AuditLogVisibility.test.js`.

### Item 10 — DONE

- **`services/enrolment_status.py` grew `LIST_VIEWS` and `view_filter()`** — the named
  lists both the student and staff screens ask for: on the roll, on the daily register,
  NSO, left, recycle bin, everyone. One helper, so the two screens cannot drift.
- **Students:** `GET /api/students?enrolment_state=…`, a new
  `GET /api/students/enrolment-summary`, and every row now carries `enrolment_state` and a
  readable label so a screen never re-derives it.
- **Staff and teachers get the same three states** (decision 2). New
  `set_enrolment_state()` in `staff_service.py` — one writer of `is_active`, always writes
  `status` with it, and **the login follows the state**: someone off the roll cannot sign in
  and their sessions end; putting them back turns the login on. New
  `POST /api/staff/{id}/enrolment` and `POST /api/staff/{id}/erase` (owner only, reason
  compulsory, whole record copied into the log first).
- **The recycle bin replaced "Include inactive"** on both screens, with the three counts
  across the top. Shared controls in `components/ui/EnrolmentControls.js` and the shared
  vocabulary in `lib/enrolmentStates.js`.
- **The compulsory reason is now on the SCREEN**, not only on the server: the erase box
  states the ten-character rule, counts what has been typed, and keeps the button out of
  reach until it is met.
- **The free "Status" dropdown came off the student edit form.** It wrote the `status` word
  alone and left `is_active` behind, which is exactly the bug that made a student
  unrecoverable. The form now points at the Status button, which is the one writer.
- **Flo was taught the difference.** New `get_enrolment_summary` tool plus a standing rule
  in every system prompt: give BOTH numbers, never call an NSO student "deleted".
  Tests: `test_flo_knows_the_nso_list.py`, `test_staff_enrolment_state.py`,
  `test_enrolment_list_views.py`.

### Item 4 — DONE

Notes and remarks on every student and staff profile, with picture attachments.
**PRIVATE TO EACH AUTHOR** per decision 3, and that rule is the feature: every read filters
on `author_id`, a note the other person wrote returns 404 rather than 403 (saying "that
exists but is not yours" would confirm they wrote one), and **the body never reaches the
action log**, because both of them can read that log.

`services/profile_notes_service.py`, `routes/profile_notes.py`, `components/ui/ProfileNotes.js`.
Two Flo tools (`get_profile_notes`, `add_profile_note`) with the mandatory parity-corpus
entry (`tests/backend/parity/profile_note_parity_test.py`). Erasing a person now deletes
every note about them, whoever wrote it.

### Item 11 — DONE

`address` added to the student and staff schemas, both field whitelists, both create paths,
both forms and the student profile panel. One free-text box on purpose: Indian addresses do
not fit line1/line2/postcode. Identity documents ride on the existing upload endpoint with
`entity_type=profile-document` (`components/ui/ProfileDocuments.js`). Unlike notes these are
**not** private to the uploader: a birth certificate is a school record.

### The extra notes Abhimanyu sent on 2026-08-07 — DONE

- **Lists were truncated AND unsearchable.** The cause of "the whole list of students is not
  appearing": several screens called `getStudents()` with no arguments and the server
  answered with its default of twenty rows. On 1,802 students that is a list that looks
  complete. Fixed with `getAllStudents()` in `lib/api.js`, which walks the pages, and used
  in the ID card generator, certificate generator, transport assignment, the performance
  viewer and TeacherTools.
- **Search added** where a person has to find somebody: a new shared
  `components/ui/SearchablePicker.js` (text box plus a native select, so keyboard and screen
  readers keep working) on the certificate and transport pickers; a plain search box on the
  ID card table, the Staff Tracker and both Directory tabs. "Select all" now follows what is
  on screen, so a search cannot leave 1,802 cards selected behind a list of one.
  Server-side search was added to `GET /api/staff/`.
- **The three directories became one.** `student-database` and `staff-tracker` came out of
  the School Database hub; the Directory carries the fuller information (roll, house,
  status, email), search on both tabs, and a button through to each full screen so adding,
  restoring and erasing are not stranded. The hub guard test was updated to record the new
  rule by name rather than being loosened.

---

## What is left

**Item 20 remainder — the wider layout sweep with the `ui-ux-pro-max` skill.** Aman asked
for a proper pass over the same class of layout misses across the whole platform, not just
the two he pointed at (table side borders on phones and scrollbar treatment, both already
done). Not started.

That is the only open item from the original twenty. Anything new Abhimanyu adds goes on
top of it.

---

## Backend changes waiting for a deploy — FLAG THESE, DO NOT DEPLOY

Four now, not two. An agent must not run the Elastic Beanstalk deploy.

1. **The one-hour sign-out.** Refresh cookie SameSite is `none` in production
   (`services/auth_tokens.py`). Cannot be tested on the local dev server, because the proxy
   makes the browser and the API same-origin.
2. **Flo reading photos.** Falls through to the paid picture-reading service when the free
   reader is absent, not only when it ran and found nothing. The absent case is the live
   server, which is why Flo has never read a photo in production.
3. **Everything in items 10, 4 and 11 above.** New endpoints, new collection
   (`profile_notes`), the `address` field, the audit-log restriction. Until this is
   deployed the new screens will call endpoints that return 404 on the live site, so **the
   frontend and backend should go out together** rather than the website landing first.
4. **One new index** in `database.py` for `profile_notes`. `_create_indexes()` does not run
   in production by design, so this reaches the school through a migration written later or
   is simply absent — the collection is small enough that the absence is not urgent, but it
   should not be forgotten.

---

## The local server

`npx craco start` in `frontend/` runs on **http://localhost:3000**.

⚠️ **It proxies to the LIVE backend** (`DEV_API_TARGET` in `frontend/.env` points at
`https://dapbq24rsje5g.cloudfront.net`). Anything typed into it changes the school's real
data. It shows the new website against real records, which is the point, but it is not a
sandbox. **The new screens will not work there until the backend is deployed.**

---

## Commands

```bash
# Backend suite — pin the DB or a fail-closed guard stops the run
MONGO_URL=mongodb://127.0.0.1:27099/eduflow_test DB_NAME=eduflow_test python -m pytest tests/backend/ -q

# Frontend
cd frontend && CI=true npx craco test --watchAll=false
cd frontend && CI=true npx craco build

# Live health
curl https://dapbq24rsje5g.cloudfront.net/api/health/ready
```

The bar is **0 failures**. Never pin a pass count.

---

## The prompt to start the next session with

```text
Resume EduFlow. Read _bmad-output/HANDOFF-2026-08-07-owner-requests.md IN FULL first,
then _bmad-output/planning-artifacts/owner-requests-2026-08-06.md. Do not touch
anything before you have read both.

Three constraints that cause real damage if missed:
1. AWS allows exactly ONE small server in this account (vCPU quota is 1). The backend
   runs on a single t2.small in ap-south-1b. Do NOT start any stopped EC2 instance; it
   takes the only slot and puts the school offline.
2. NEVER run backend/migrations/run_all.py against production.
3. Do NOT write to the live school database directly. Anything that changes real
   records is done by a person pressing a button in the product.

State: 19 of the owner's 20 requests are built, plus the extra list-search and
directory-merge notes he sent on 2026-08-07. Backend 2289 passed / 0 failed / 15
deselected, frontend 483 passed / 0 failed, production build clean. NOTHING is
committed and NOTHING is pushed; there is also one older unpushed commit (642347f)
that goes out with everything else. Keep making all edits and hold for ONE push at
the very end, because every push to main starts a paid Amplify build.

The only open item from the original twenty is item 20's remainder: the wider layout
sweep across the whole platform with the ui-ux-pro-max skill. Start there unless
Abhimanyu has sent something new.

Abhimanyu's four decisions are settled. Build to them, do not re-ask. In particular:
notes on profiles are PRIVATE TO EACH AUTHOR, and the NSO list applies to students,
staff AND teachers.

Read backend/services/enrolment_status.py before touching anything to do with NSO,
attendance registers or student status, and backend/services/profile_notes_service.py
before touching notes.

Verify against the running system, not status pages. Health check:
https://dapbq24rsje5g.cloudfront.net/api/health/ready

FOUR backend changes are now waiting on a deploy and must be flagged to Abhimanyu,
not deployed by an agent: the SameSite refresh cookie fix, the photo-reading
fallback, and everything new in items 10, 4 and 11 (new endpoints, the profile_notes
collection, the address field, the audit-log restriction). The website and the
backend should go out TOGETHER, or the new screens will call endpoints that 404.

Test commands, and the bar is 0 FAILURES with no pass count ever pinned:
  MONGO_URL=mongodb://127.0.0.1:27099/eduflow_test DB_NAME=eduflow_test python -m pytest tests/backend/ -q
  cd frontend && CI=true npx craco test --watchAll=false
  cd frontend && CI=true npx craco build

A local dev server may still be running on http://localhost:3000. It proxies to the
LIVE backend, so it is a preview, not a sandbox, and the new screens will not work
there until the backend is deployed. Restart it with
`cd frontend && BROWSER=none npx craco start` if it is gone.

Keep a live to-do list. Write in plain human language with no em dashes. Prepare a
handoff before context runs low rather than compacting.
```
