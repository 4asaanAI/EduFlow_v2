# Handoff — 2026-08-08 — parent messaging, tool search, spreadsheet import

Paste the prompt at the bottom into a fresh session. Everything above it is the
evidence behind that prompt.

---

## Where things stand

**`origin/main` is at `9455920`.** Three commits shipped today, working tree clean:

```
9455920  Flo can import a spreadsheet into the live records, reading every row
1e0a617  Deferred tool loading: 73% fewer tokens per turn, nothing hidden
1c9ec77  Flo can send WhatsApp/SMS to families, behind a confirm card
```

**Test baseline is ZERO failures. Do not pin a pass count** (this repo has been burned
by stale counts being read as targets — D-51/D-56). As of this handoff:
backend 2,615 passed / 0 failed / 15 credentialed deselected; frontend 521 passed / 0
failed; production build passes including the lint gate.

| Thing | State |
|---|---|
| Code on `origin/main` | ✅ pushed |
| Frontend (Amplify) | ✅ LIVE — build 134, commit 9455920, HTTP 200 |
| Backend (Elastic Beanstalk) | ❌ **NOT deployed** — blocked on an IAM permission |
| Live data load (7,322 fields) | ✅ done and verified in production |

### The half-deployed state, and what a user sees today

Frontend is new, backend is old. Nothing is broken, but until the backend deploys:

- Parent messaging, tool search and spreadsheet import **do nothing** — all backend.
- A principal opening WhatsApp fee reminders is **still refused** (the widened gate is
  backend-only). They now at least see an honest "You don't have permission…" instead
  of a misleading empty list.
- The class column still shows a raw UUID instead of `5-A`.

---

## What shipped (so the next session doesn't rebuild it)

### 1. Parent messaging — Flo can message families for real
- `backend/services/messaging_service.py` — the ONE write path.
- REST: `/api/parent-messaging/*` (`backend/routes/parent_messaging.py`).
- Flo tools: `send_parent_message`, `get_messaging_status`, `get_message_templates`,
  `create/update/delete_message_template`, `submit_whatsapp_template`,
  `get_whatsapp_template_status`.
- Parity pinned by `tests/backend/parity/messaging_parity_test.py`.
- Confirm card states how many families it reaches; the resolved recipient list is
  frozen into the confirm token so the approved set is the sent set.
- **SMS wording is free. WhatsApp wording is NOT** — Meta requires pre-approved
  templates. `update_message_template` on a WhatsApp template changes only the local
  preview and says so. Real new wording goes via `submit_whatsapp_template` (Twilio
  Content API → Meta approval, minutes to a day, can be refused). A pending template
  cannot send. **Do not let any doc, prompt or reply imply otherwise.**
- An unconfigured channel now fails loudly (503 naming the missing env var) instead of
  recording "not_configured" for every recipient and returning success.

### 2. Deferred tool loading — 73% fewer tokens per turn
- `backend/ai/tool_search.py`. Owner/principal turn went ~36,400 → ~9,700 tokens.
- Small CORE set described in full; everything else listed BY NAME, schema fetched on
  demand via `search_tools`, callable for the rest of the turn.
- Replaced `EXCLUDE_FOR_ROLE` (now empty). That old trim HID tools, and a hidden tool
  is indistinguishable to the model from one that doesn't exist — which is how the
  school's owner was told an operation was "not available to me" about something they
  could do (2026-08-07). **Nothing is hidden now.**
- Cost only. `is_tool_authorized` is still the sole authorization gate, unchanged.
  `tests/backend/unit/test_tool_search.py` proves, for all 10 role profiles, that every
  authorized tool is either loaded or named AND retrievable by search.
- Kill switch: `EDUFLOW_TOOL_SEARCH=0`.
- **Adding a tool?** Put it in CORE only if genuinely everyday — every CORE name is paid
  for on every turn by every user of that role.

### 3. Spreadsheet import — Flo reads EVERY row
- `backend/services/data_import_service.py`; REST `/api/data-import/{preview,apply}`;
  Flo tools `preview_data_import` (read) and `import_data_file` (confirm-gated write).
- `chat_upload` now STORES the whole file (S3 + `chat_uploaded_files`) and returns a
  `file_id`. Truncation now says loudly that the model is seeing a fragment, must not
  answer about the whole file, and should use the import tools.
- **Why:** the chat attachment gave Flo 40,000 chars = 63 of 1,878 students (3.4%), and
  it answered as if it had read all of it. The fix was NOT a bigger slice — the file
  bypasses the conversation entirely.
- Rules: fills blanks but never overwrites unless `overwrite=true`; matches on admission
  number never on name; rows without an admission number are reported not guessed; fees,
  class and enrolment status cannot be set from a sheet.

---

## Live production data change — ALREADY DONE, do not repeat

Applied 2026-08-08 from `aaryans_database/Students-06-08-2026-12-08-00.xlsx`:
**7,322 fields across 1,848 students, 0 failures**, batch `873c7b0d-c8db-44bf-8bee-862f25b701b8`.

Verified present in production afterwards: whatsapp_phone 1,095 · bus_route 1,376 ·
registration_number 795 · aadhaar_number 146 · alternate_phone 81 · external_sid 1,848 ·
pen_number 3, plus 27 assorted gaps (names/addresses/gender/admission dates).

- Backup of all 1,876 pre-change records:
  `aaryans_database/backups/students-before-import-2026-08-08.json` (gitignored).
- Per-student audit rows exist (`action: data_import_update`), so it is reversible
  student by student.
- **30 rows in the file have no admission number** and were deliberately skipped.
  Someone at the school should identify those children.
- The old vendor's `Username` column was stored as `legacy_username`, NOT `username`,
  so it can never be mistaken for an EduFlow login.

---

## Remaining work, in priority order

### P1 — Backend deploy is BLOCKED on an IAM permission
The deploy failed cleanly; production still runs `eduflow-main-20260806-53` and serves
fine (`/api/health/ready` → 200, all subsystems ok).

```
User: arn:aws:iam::210447603820:user/Claude is not authorized to perform:
s3:DeleteObject on arn:aws:s3:::elasticbeanstalk-ap-south-1-210447603820/...
```

Elastic Beanstalk deletes a staging folder during deploy and could not.

**The bundle is already uploaded and the application version already created:**
`eduflow-main-20260808-9455920`. So this is a one-command retry once unblocked.

Two ways forward — ASK ABHIMANYU WHICH, do not pick silently:
- Grant `s3:DeleteObject` on `elasticbeanstalk-ap-south-1-210447603820` to IAM user
  `Claude`, then:
  `aws elasticbeanstalk update-environment --application-name eduflow --environment-name Eduflow-env-1 --version-label eduflow-main-20260808-9455920 --region ap-south-1`
- Or he deploys from his own credentials: `eb use eduflow-prod && eb deploy`.

**Do NOT attempt to work around the permission boundary.** It is deliberate.

After deploying, verify: `curl -fsS http://13.126.141.241/api/health/ready`, then confirm
the environment reports the new version label and returns to Green.

### P2 — WhatsApp still cannot send
`TWILIO_WHATSAPP_FROM`, `TWILIO_WHATSAPP_FEE_TEMPLATE_SID` and
`TWILIO_WHATSAPP_ATTENDANCE_TEMPLATE_SID` are **not set** on Elastic Beanstalk
(verified 2026-08-08). SMS credentials exist, but `TWILIO_PHONE_NUMBER` is a **US
number (+12286410951)** — worth reviewing for delivery and cost to Indian parents.

The 1,095 WhatsApp numbers are now in the database, so this is the last blocker on fee
reminders actually reaching anyone.

### P3 — Backend health: unexplained 4xx flapping
The environment flaps Ok↔Severe with *"100.0% of the requests are erroring with HTTP
4xx"* — seen at 06:09, 07:03, 07:23, 07:27 UTC on 2026-08-08, i.e. **before** any of
today's deploy activity. Likely a health check hitting an authenticated endpoint, or
clients being rejected. Resolve before school staff start using their accounts.

### P4 — `origin/local_testing` is unmerged and overlaps heavily
One commit (`28d6558`, Shubham, 2026-08-02): "Add AI flow logging; fix Groq TPM
413/throttling; attribute tokens to real model". **1,109 insertions** across
`llm_client.py`, `prompts.py`, `tool_functions_v2.py`, `chat.py`, `ChatInterface.js`,
`api.js` — the same files the tool-search work rewrote.

Deliberately NOT merged. It reduces token cost via Groq; tool search reduces it a
different way (73% already). Merging blind risks one silently undoing the other. Needs a
real decision on whether Groq is still the intended path. The other three remote
branches are fully merged into main.

### P5 — Smaller items
- **Dead CORS origin.** `main.d15d0fwwo2dh1j.amplifyapp.com` is in `CORS_ORIGINS` on
  Beanstalk but that Amplify app no longer exists (AWS: "App not found"). Harmless but
  it is clutter in a security setting.
- **No seeded message templates, on purpose.** `message_templates` is empty in
  production. Inventing template wording would be exactly the "convincing fake data"
  this repo warns about. The school writes its own.
- **The 30 admission-number-less rows** (see above).

---

## Gotchas that cost time today — do not relearn them

1. **`npx craco test` does not exist.** The frontend is Vite + plain Jest. Run
   `cd frontend && CI=true npx jest`. Also run `npm run build` before pushing frontend
   changes — **Amplify runs ESLint first and a warning fails the deploy.** CLAUDE.md is
   now corrected.
2. **`backend/routes/messaging.py` is the STAFF-to-staff chat** (threads, groups, read
   receipts, SSE) — 716 lines. Parent messaging is `parent_messaging.py`. These were
   briefly conflated during this build and the staff file was overwritten and restored
   from git. **Check a path exists before writing to it.**
3. **The roll is 1,876 students (1,842 active)**, counted live. Every doc said 1,802 —
   stale since the 6 Aug load and copied forward. CLAUDE.md and AGENTS.md are corrected.
   **Never hardcode a roll; count it.**
4. **`aaryans_database/` is gitignored** — it holds the export and the PII backup.
   Verify before any `git add -A`.
5. Live DB reads from this machine need `tlsCAFile=certifi.where()` (local CA store is
   missing for Python 3.14), and `MONGO_URL` comes from the Beanstalk config. **Delete
   any file you write it to.**

---

## THE PROMPT — paste this into a new session

> Continue the EduFlow work handed off in
> `_bmad-output/HANDOFF-2026-08-08-messaging-toolsearch-import.md`. Read that file
> first; it has the full state, the evidence, and the gotchas.
>
> Context in one line: parent messaging, deferred tool loading and full-file spreadsheet
> import all shipped to `origin/main` at `9455920` and the frontend is live, but **the
> backend deploy is blocked on a missing `s3:DeleteObject` IAM permission**, so none of
> the backend features are in production yet.
>
> Work these in order, checking with me before anything irreversible:
>
> 1. **Unblock and finish the backend deploy.** The bundle is uploaded and application
>    version `eduflow-main-20260808-9455920` already exists, so it is a one-command
>    retry. Ask me whether to grant `s3:DeleteObject` to the `Claude` IAM user or whether
>    I will deploy myself. Do not work around the permission. Verify health afterwards
>    and confirm the new version label is live.
> 2. **Get WhatsApp actually sending.** Three env vars are unset on Beanstalk. Tell me
>    exactly what to set and where. Also advise on the US sender number (+1228…) for
>    Indian parents. Then prove a send works end to end without messaging real families.
> 3. **Diagnose the 4xx flapping** on the backend environment — it predates today's
>    deploys and should be understood before school staff start using their accounts.
> 4. **Decide `origin/local_testing`** (Shubham's Groq commit) with me. It overlaps the
>    tool-search work heavily. Recommend merge / rebase / drop with reasoning; do not
>    merge blind.
> 5. **Tidy-ups:** remove the dead CORS origin, and give me the list of the 30 students
>    whose rows had no admission number so the school can identify them.
>
> Standing rules: the test bar is ZERO failures — run
> `MONGO_URL=mongodb://127.0.0.1:27099/eduflow_test DB_NAME=eduflow_test python -m pytest tests/backend/ -q`
> and `cd frontend && CI=true npx jest` plus `npm run build`; never pin a pass count.
> Do not run `migrations/run_all.py` against the live database. Write to me in plain,
> non-technical language, and be just as direct about failures as successes.
