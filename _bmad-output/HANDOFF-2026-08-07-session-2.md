# Handoff — 2026-08-07, second working session

Read `HANDOFF-2026-08-07-owner-requests.md` first for everything before this session.
This note covers only what changed today.

**The three hard constraints still apply.** Never start a stopped EC2 instance (one vCPU
in the account, the backend is on the only slot). Never run `backend/migrations/run_all.py`
against production. No agent writes to the live school database.

**Everything in this note is committed, pushed and deployed** as `66a9b5b`, which also
carried the older unpushed `642347f`. See "SHIPPED AND DEPLOYED" below.

---

## What Abhimanyu decided today

Two new decisions, both settled. Build to them, do not re-ask.

1. **A corrected document is downloaded only.** Nothing is saved back to the server.
   No new version, no author, no timestamp. The school's stored copy stays as it is.
2. **Flo's documents get the school's letterhead and proper styling.** He also asked
   whether Flo could be given a document-making skill like mine; the honest answer is
   that the gap was a template gap, not an intelligence gap, and closing it was option 1
   of the three offered.

---

## The four pieces of work

### 1. The platform-wide layout sweep — DONE

Aman's two named defects were already fixed. The sweep found the **same two defects in
three more shapes**, all of which the existing rules could not reach, because both rules
key off `:has(> table)` and that only matches a wrapper whose direct child is the table.

- **The card is the grandparent.** `tools/ToolPage.js` renders
  `<card border+radius><scroll div><table>`, so the rule matched the inner scroll div,
  which draws no border, and never reached the card that draws the side borders. That
  component is the table on roughly **twenty screens across every role**, so this was
  the single widest miss. Same shape in ExamManager, FeeCollection, PrincipalDailyOps,
  TimetableBuilder and AdmissionsWorkflow.
- **The border is on the table itself** (TransportOptimisation), so removing a wrapper's
  border did nothing.
- **Scroll regions that are not tables** kept the chunky default scrollbar. That is the
  thing Aman actually described, and it looked identical on the audit log wrapper, the
  attendance registers and every other sideways-scrolling panel.

All three fixed centrally in `index.css` section 3e, plus one class on ToolPage's
DataTable. Two small phone-width fixes in `ui/EnrolmentControls.js`.

**The browser check now covers every role, and before today it could not.** The E2E
double (`tests/support/e2e_backend.py`) only knew one user, hard-coded as the owner, so
the responsive check was structurally incapable of seeing a teacher's or a parent's
screens, which are different screens. It now signs in eight roles. The spec walks every
screen each role is actually offered and checks two things per screen: the page does not
scroll sideways, and no element overhangs the screen edge. The second check matters
because the shell sets `overflow-x: hidden`, so an overhanging card is silently clipped
and the old document-level check stayed clean while the person lost the right-hand edge.

One production change fell out of it: sidebar group headers had no test handle, so a
teacher's and a student's menus read as empty (all their screens live inside collapsed
groups). `data-testid="tool-group-<id>"` added in `Sidebar.js`.

Result: **11 responsive browser tests pass**, covering all eight roles.

### 2. Hindi in PDFs — DONE

Devanagari was silently replaced with `?`. Now fixed with two Noto fonts under
`backend/assets/fonts/`.

**Two things worth knowing.**

- **Text shaping is not optional.** Hindi is not drawn in the order it is stored: vowel
  signs move in front of their consonant and clusters join into single glyphs. Without
  a shaper the characters are all present but sit in visibly wrong shapes. `uharfbuzz`
  is now a backend dependency for this reason.
- **A test caught a regression that reasoning did not.** The first version registered
  Noto Sans Devanagari alone, assuming it covered Latin. It does not. English came out
  **completely blank** — the subsetter kept only the space and the full stop out of
  "Holiday on Monday." That would have replaced a small Hindi defect with a total
  English one. Fixed by making Noto Sans (Latin) the document font with the Devanagari
  font as its per-character fallback, so a mixed sentence like "कक्षा III की उपस्थिति"
  works. `test_english_documents_are_unaffected` exists to hold that down; do not weaken it.

Three tiers, degrading and never failing: font plus shaper gives correct Hindi; font
without shaper gives unshaped Hindi; no font falls back to exactly the old behaviour.
Which tier was used is written to the log, because a silent drop to the last one is how
this defect stayed invisible.

**Licence checked, not assumed.** SIL OFL 1.1, read from the licence text shipped beside
the font. It permits embedding and redistribution on condition the licence travels with
the font. `.ebignore` excluded every `*.txt`, which would have stripped it out of the
deploy, so there is now an explicit exception for `backend/assets/fonts/OFL.txt`.

### 3. An edit panel for generated documents — DONE

`ui/DocumentEditor.js`, lifted from the Question Paper Creator's pattern rather than
copied, so a fix to the sanitising or the PDF export cannot land in one and miss the
other. Opened from the file card in chat.

New endpoint `GET /api/uploads/content/{file_id}` returns the document's text. Its
permission is the **same check the download uses** — a looser rule there would be a way
round the download gate. Documents made before this shipped answer 409 with a sentence
explaining they can only be downloaded, rather than opening an empty editor.

Per Abhimanyu's decision there is **no save endpoint**, and a test asserts that PUT,
POST, PATCH and DELETE all fail. If that test ever starts failing, the decision has been
reversed by accident and the school is storing an unaudited second version of a document
its action log still describes as the original.

### 4. School letterhead and styling, on every format — DONE

Letterhead on every page of PDFs and in the Word page furniture: logo, name, CBSE line,
rules, address footer, page numbers. Tables got a navy heading row that repeats after a
page break, banded rows and lighter gridlines.

**Corrected after Abhimanyu compared it against the real form.** The first version said
"The Aaryans" where the paper says "THE AARYANS", reworded the footer out of the identity
fields instead of transcribing it, and had no watermark. The printed wording now lives in
`school_identity.LETTERHEAD`, transcribed character for character from the school's own
enquiry form, with the pale tiled wordmark and the chariot behind the text.

That is **not** a second source of truth for the address. The identity fields stay as the
values the product shows on screen; `LETTERHEAD` is how those same details are printed on
the school's paper. Both live in one file.

**Every format a person reads, but NOT spreadsheets.** Abhimanyu first asked for "each
and every type of document", then, having seen it: "remove the branding from excel/csv
file type". So PDF, Word, PowerPoint, Markdown and plain text carry it; **xlsx and csv
never do**, and that is enforced by `UNBRANDED_TYPES` rather than by a default, so a
caller passing `letterhead=True` still gets a clean sheet.

The reason is worth keeping: a spreadsheet is data. Branding rows above the column
headings shift every row down, so a formula, a filter or an import into another system
starts on the wrong line. The gain was cosmetic and the cost was real.

The branded test is derived from `SUPPORTED_TYPES` minus `UNBRANDED_TYPES` rather than a
hand-written list, so a format added later fails until it is branded as well.

**Four bugs found and fixed while building this**, all worth remembering because each was
invisible until something was actually looked at:

1. The tiled watermark started at a negative x, which fpdf2 refuses, so the entire
   watermark was silently lost.
2. With automatic page breaks left on, the tiling loop tripped a page break, which called
   the header again, which drew another watermark, until Python ran out of stack.
3. The watermark was drawn from `header()`, which puts it UNDERNEATH. The table's banded
   rows are opaque fills, so the crest vanished behind every table. It is now drawn from
   `footer()`, which fpdf2 calls after the body, so it overlays. Nothing could have fixed
   that from underneath short of giving up the row banding.
4. The wordmark tiled straight across the crest and turned it into a smudge. Tiles that
   would overlap the crest are now skipped, so the wording breaks around it and picks up
   on the other side, like the printed form. Two tests check this by measuring where
   things were drawn rather than by eye.

The background crest is a **separate desaturated file** (`aaryans-crest-watermark.png`)
rather than the full-colour logo, because full colour behind a fee table reads as a
mistake. The letterhead crest at the top stays full colour. If the pale file is ever
missing the watermark falls back to the ordinary logo rather than disappearing.

The four numbers that control the watermark are named constants at the top of
`document_builder.py` (`WATERMARK_ROWS`, `WATERMARK_STEP_X`, `WATERMARK_OPACITY`,
`CHARIOT_OPACITY`), because this is the part most likely to need nudging by eye.

---

## 5. What Flo was told, and one real gap it uncovered (2026-08-07)

Abhimanyu asked for Flo's knowledge to be brought up to date too, not just the vault.

**Documents.** Flo now knows the letterhead is applied automatically (so it must NOT write
the school's name and address into the body, or they print twice), that spreadsheets are
plain on purpose, that **Hindi works in PDFs now** where it used to become question marks,
and that a person can read and correct a document but the correction is not saved back.
Pinned by `tests/backend/unit/test_flo_knows_about_documents.py`. These are prompt-content
tests and they are worth it: the defect class they guard is the prompt and the code
disagreeing, which is what the R3 epic and D-13 were both about.

**One hard-coded word caused a real failure.** The first version of that guidance wrote
"THE AARYANS" and "The Aaryans" literally into a shared prompt, which broke
`test_assistant_identity_follows_the_stored_record` — a multi-tenancy guard checking that a
second school deploying this code never sees The Aaryans' name in its own assistant. The
test was right; the wording is now generic.

### The action-log rule was half-applied, and Flo was the missing door

Found while checking what else Flo might be wrong about. The 2026-08-06 request cut the
action log down to owner and principal. That reached `routes/audit.py`, `Sidebar.js` and
`toolPermissions.js` — but not the assistant. **The drift ran in both directions**, which is
why it survived a review:

- `it_tech` was still offered the log by Flo, and Flo's own role rules told them they could
  read it, when the screen had been taken away.
- The **principal**, who is allowed the log and has it on screen, was never offered it by
  Flo at all.
- The registry authorised `teacher` and `student` too.
- A fourth door opened while fixing it: `management` has no tool list of its own and falls
  back to the principal's, so it inherited the log the moment it was added there. The
  fallback list now excludes principal-only tools.

Flo's tool imports the route's own `AUDIT_READER_SUB_CATEGORIES` rather than restating it,
so there is one list and two callers. A refusal returns `_denied`, not an empty result: "you
do not have access" rather than "there is nothing there", which would be a confident wrong
answer about the school's own records. Pinned by
`tests/backend/unit/test_flo_audit_log_access.py`, including a test that fails if anyone
re-states the sub-categories instead of importing them.

The eval corpus case `ittech-audit` expected an answer and now expects a denial. It was
encoding the old rule.

**A rule enforced on three of four doors is not enforced.** Worth remembering next time a
permission is narrowed: the screens, the web address, the menu allow-list and Flo are four
separate doors, and Flo is the one nobody checks.

## The memory vault

Updated and pushed (`claude-memory-vault@9705f59`). Three stale claims corrected, each
checked against the running system rather than the repo:

- It said **production runs `origin/local_testing`**. It does not, and has not for some
  time: the last four EB versions are all `eduflow-main-*` built from `main`. That line
  would have sent a future deploy at the wrong branch.
- The **certificate and ID-card permission gap is now closed**. The fix had existed since
  2026-08-04 and had simply never been deployed. It went out today, and both endpoints
  answer 401 unauthenticated on the live front door. The lesson in that entry stands: a fix
  that is merged and undeployed protects nobody.
- The `run_all.py` root cause is closed (`CLAUDE.md` no longer tells anyone to run it), and
  the pending list is two migrations now, not one.

---

## SHIPPED AND DEPLOYED — 2026-08-06

Abhimanyu gave an explicit go-ahead to push and deploy, so the standing "flag, do not
deploy" rule was lifted for this one release by his instruction.

- **Commit:** `66a9b5b` on `main`, which also carried the older unpushed `642347f`.
- **Website:** Amplify job **121**, SUCCEED, for this exact commit.
- **Backend:** EB version `eduflow-main-20260806-66a9b5b` on `Eduflow-env-1`, Ready and
  **Green**.
- **Rollback target:** `eduflow-main-20260806-3a02b20`.
- **Verified against the running system**, not status pages: health reads `ready` with db,
  ai, s3 and sms all ok, and the new endpoints answer **401** rather than 404, which proves
  the new code is live and still properly guarded.

### The one thing that went wrong, so it does not cost anyone an hour again

The first deploy attempt **failed instantly** with an S3 `DeleteObject` denial. Cause: it
ran as the `Claude` IAM user. **EB deploys must run as `claude-hosting`** (keys in `.env`
as `AWS_ACCESS_KEY_ID_HOSTING` / `AWS_SECRET_ACCESS_KEY_HOSTING`), which holds
`AdministratorAccess-AWSElasticBeanstalk`. Re-running with that identity worked first time
and took about 70 seconds.

Worth knowing: the failure happened **before the running app was touched**, so the school
stayed up throughout, which was confirmed by hitting the health endpoint while the
environment still showed Red.

---

## The backend changes that were waiting, now all live

All six went out in the deploy above. Listed here as the record of what changed on the
server, not as outstanding work.

1. The one-hour sign-out (refresh cookie SameSite, `services/auth_tokens.py`).
2. Flo reading photos (the fallback when the free reader is absent).
3. Everything in items 10, 4 and 11 from the previous session: new endpoints, the
   `profile_notes` collection, the `address` field, the audit-log restriction.
4. One new index in `database.py` for `profile_notes`.
5. **New: Hindi in PDFs and the school branding.** Ships four font files and a licence
   under `backend/assets/fonts/`, and two images under `backend/assets/` (the full-colour
   crest and the pale watermark copy). Adds **`uharfbuzz` to `requirements.txt`** — the
   first new Python dependency in a while, so the deploy will build it. All of these were
   checked against `.gitignore` and `.ebignore`: nothing is excluded, and `.ebignore`
   carries an explicit exception for the font licence because it excludes every `*.txt`.
6. **New: the document content endpoint** (`GET /api/uploads/content/{file_id}`). Until
   it is deployed, the "Read and edit" button on the website will fail on the live site.

The website and the backend went out together, so no screen was ever calling an endpoint
that did not exist yet.

---

## Test results at the end of this session

The bar is **0 failures**. Never pin a pass count.

- Backend: 0 failed
- Frontend: 0 failed
- Responsive browser check: 11 passed, all eight roles
- Production build: clean

---

## The local dev server

Abhimanyu killed it during this session and asked for the leftover process to be ended,
which was done. Port 3000 is free. Restart with
`cd frontend && BROWSER=none npx craco start`.

It proxies to the **LIVE backend**, so it is a preview and not a sandbox, and the new
screens will not work there until the backend is deployed. The Playwright suite is
different: it starts its own local double on port 8000 and is safe.

---

## What is left

- **Nothing outstanding from the owner's twenty items.** All shipped and deployed.
- The one new index for `profile_notes` still has no migration. `_create_indexes()` does
  not run in production by design, so it reaches the school only through a migration
  written later. The collection is small, so this is not urgent, but do not forget it.
- Optional, offered and not taken today: letting Flo write its own document layout
  rather than filling a fixed template. That is the next step up in document quality
  and now sits on top of working fonts and a working letterhead.
