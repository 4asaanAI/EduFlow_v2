# Handoff — 2026-08-08 evening — everything is deployed; what is left is not code

Supersedes `HANDOFF-2026-08-08-messaging-toolsearch-import.md`, whose central claim
("the backend deploy is blocked on a missing `s3:DeleteObject` IAM permission") was
**wrong**. See below before acting on anything in that file.

Paste the prompt at the bottom into a fresh session on the PC.

---

## State

`origin/main` is at **`9f5e224`**, working tree clean. Today's commits:

```
9f5e224  Data Import screen: an update tab for all four profiles, add-students for two
4ada10f  Accountant and management can import their own segment of a spreadsheet
cdfdf6a  Deploys run as claude-hosting; correct the WhatsApp readiness picture
9455920  Flo can import a spreadsheet into the live records, reading every row
1e0a617  Deferred tool loading: 73% fewer tokens per turn, nothing hidden
1c9ec77  Flo can send WhatsApp/SMS to families, behind a confirm card
```

| Thing | State |
|---|---|
| Backend (Elastic Beanstalk) | ✅ **LIVE** — `eduflow-main-20260808-9f5e224`, Green, all subsystems ok |
| Frontend (Amplify) | ✅ **LIVE** — build 138, commit `9f5e224` |
| Test bar | **ZERO failures.** 2,642 backend · 521 frontend · production build incl. lint |

**Never pin a pass count** (D-51/D-56). The counts above are today's evidence, not a target.

---

## The correction that matters most

**The deploy was never blocked by a missing permission.** Three IAM logins exist on
account `210447603820`; only **`claude-hosting`** can deploy, and its keys were already
in the repo's own `.env` as `AWS_ACCESS_KEY_ID_HOSTING` / `AWS_SECRET_ACCESS_KEY_HOSTING`.
The previous session used the narrower `Claude` login, hit `s3:DeleteObject denied`, and
read that as a gap — costing a day with the backend undeployed, and nearly costing an
unnecessary IAM widening.

**`s3:DeleteObject denied` on an EB deploy means the wrong key. Check
`aws sts get-caller-identity` first; the Arn must end `user/claude-hosting`.**
Full deploy procedure, including how to build and verify the bundle, is in `CLAUDE.md`.

---

## What shipped today, beyond the previous handoff

### Spreadsheet import is now segment-scoped across four profiles
Owner and principal import the whole student record; the **accountant** imports bank
fields plus contact numbers; **management** imports everything except bank fields.
One source of truth: `data_import_service.IMPORT_FIELD_SCOPES`. Columns outside a
profile's segment are **named back to the person**, before confirming and after, never
silently dropped. Details and the gotchas are in `CLAUDE.md`.

### The sidebar "Data Import" panel now has two tabs
"Update existing records" (the scoped import, all four profiles) and "Add new students"
(the OLD enrolment route, owner/principal only). ⚠️ **That button never updated anything
before today — it CREATED students** with invented admission numbers. Read the CLAUDE.md
note before touching it.

### Two defects found and fixed
- `import_data_file` was missing from `BULK_TOOL_NAMES`, so a tool that rewrites fields
  across the entire roll was running with **no confirm card**, despite its own description.
- A dead `"access_domain": "students"` literal on both import tools, silently overwritten
  by the assignment loop while still reading as authoritative.

### Smaller
- Dead Amplify origin `main.d15d0fwwo2dh1j.amplifyapp.com` removed from `CORS_ORIGINS`
  (confirmed the app no longer exists; live frontend still passes preflight).
- The 30 students whose rows had no admission number:
  `aaryans_database/students-without-admission-number-2026-08-08.csv`
  (**gitignored — it is names and parents' phone numbers. It will NOT be on the PC.**
  Regenerate it there from `aaryans_database/Students-06-08-2026-12-08-00.xlsx`, or copy
  it across by hand. Do not commit it.)

---

## Closed questions — do not reopen

**The 4xx health flapping is bot noise, not a defect.** Diagnosed from the instance's
nginx log. Real traffic is an uptime monitor every ~3 min, always 200; every few hours a
bot sweeps for PHP files and collects 404s, and when a burst lands in an otherwise empty
minute EB enhanced health reports "100% of requests erroring" and flips, then clears.
Full log: 81 × 200, 15 × 404, 1 × 400, **zero 5xx**. No school user is being turned away.

**`origin/local_testing` (Shubham's Groq commit `28d6558`) — recommended DROP, awaiting
Abhimanyu's decision.** It targets the same problem as the shipped deferred-tool-loading
work, but gets its saving mainly by **deleting** system-prompt text: most of the
anti-jailbreak rules, the writing-style rules, and the rules requiring Flo to say "you are
not allowed to see this" rather than "there are none". Its other saving — not duplicating
the tool list in the prompt — main already does, properly and with tests, for a 73% cut.
It also forks from 2026-07-25 and rewrites the same files. **Salvage instead:** ask Shubham
to resubmit just the AI flow logging and real-model token attribution against current main.
The branch is untouched.

**Who holds the four authority profiles** (confirmed by Abhimanyu): owner = Aman Litt,
principal = Adesh, **accountant = Sonu**, **management = Lalit**. There is exactly ONE
login per admin profile, so shared use makes the audit trail name the account, not the
person — a decision still open.

---

## What is actually left, and none of it is code

### P1 — WhatsApp cannot send, and it is NOT three unset env vars
This was checked against the Twilio account directly, and the earlier handoff understated it.

- The only WhatsApp sender is `whatsapp:+14155238886` — Twilio's **shared sandbox**
  number, and it is `OFFLINE`. Sandbox only reaches people who first text a join code, so
  it can never reach the school's families. A WhatsApp Business Account exists
  (`waba_id 757370660501818`) but **no real sender is registered to it**.
- All 3 approved content templates are **MARKETING**-category Layaa AI sales outreach.
  Fee and attendance reminders are **UTILITY** and must be written and approved separately.
  Sending school reminders on a marketing template risks the WhatsApp Business Account.

Order: register a real sender → write the fee/attendance wording → submit to Meta
(minutes to a day, can be refused) → only then set `TWILIO_WHATSAPP_FROM`,
`TWILIO_WHATSAPP_FEE_TEMPLATE_SID`, `TWILIO_WHATSAPP_ATTENDANCE_TEMPLATE_SID` on Beanstalk.
**No end-to-end send can be proved before a sender exists.** Do not tell the school
WhatsApp works until it does.

### P2 — SMS sends from a US number
Both numbers on the account are US (`+12286410951`, `+15612508971`). To Indian parents:
higher cost, foreign sender, and routinely carrier-filtered. An **Indian DLT-registered
sender** is the right answer for school messaging.

### P3 — Credentials handover
All four logins exist with working passwords. **Passwords cannot be recovered** — they are
one-way encrypted. Either Abhimanyu knows them or they must be reset (offer: reset all four
to temporary passwords that must be changed at first login). Usernames as they stand:
`Aman Litt` (contains a space), `Adesh`, `accountant`, `management` — the last two are
generic words rather than names, worth tidying. Login URL:
`https://main.ddxpej151tf13.amplifyapp.com` (no custom domain).
**Do not send passwords over WhatsApp/SMS** — they persist on both phones and in backups.
Four staff: hand over by phone or in person.

### P4 — Smaller
- `message_templates` is empty **on purpose**. Inventing school wording would be exactly
  the "convincing fake data" this repo warns about. The school writes its own.
- Production secrets (live Razorpay keys, Mongo password, `JWT_SECRET`, Azure key, Twilio
  token) sit in **plain text** in Beanstalk env vars. Nothing known compromised; should
  move to Secrets Manager.
- `012_migrate_uploads_to_s3` is still the one genuinely pending migration. Rehearse
  against a copy of production first. **Never `run_all.py` against live.**

---

## Gotchas — do not relearn these

1. **`s3:DeleteObject denied` = wrong AWS key**, not a missing permission. See above.
2. **Build the deploy bundle by hand and diff it against the last good one.** A first
   attempt dropped `.ebextensions/` and swept in `backend/uploads/` (possibly real
   people's documents). Command is in `CLAUDE.md`.
3. **`npx craco test` does not exist.** Frontend is Vite + plain Jest:
   `cd frontend && CI=true npx jest`. Run `npm run build` too — **Amplify runs ESLint
   first and a warning fails the deploy.**
4. **`backend/routes/messaging.py` is STAFF-to-staff chat.** Parent messaging is
   `parent_messaging.py`. The staff file was once overwritten by conflating them.
   Check a path exists before writing to it.
5. **The roll is 1,876 students (1,842 active)** — counted live. Never hardcode it.
   Note `auth_users` holds 1,802 student logins, which is where the old stale "1,802"
   figure came from; they are different numbers measuring different things.
6. **`aaryans_database/` is gitignored** and holds the export plus the PII backup.
   Verify before any `git add -A`.
7. **Live DB reads need `tlsCAFile=certifi.where()`** (Python 3.14 has no local CA store),
   and `MONGO_URL` comes from the Beanstalk config. **Delete any file you write it to.**

---

## ⚠️ One thing that does NOT follow you to the PC

The **MemPalace / shared memory bridge is offline on the Mac** — it could not open its
tunnel all day. **Seven findings from today are queued locally on the Mac only** and have
NOT reached the shared pool: the deploy-identity rule, the WhatsApp reality, the US-sender
problem, the 4xx diagnosis, the `local_testing` recommendation, the plain-text-secrets
risk, and who holds the four profiles.

The **vault (`~/Documents/ClaudeMemory`) is fully up to date and pushed** — all of the
above is written there in `Projects/Layaa AI/eduflow.md`. On the PC, `git pull` the vault
first and you have everything. If the bridge comes back on the Mac, the queue will flush
by itself; nothing needs re-deriving either way.

---

## THE PROMPT — paste this into a new session on the PC

> Continue the EduFlow work handed off in
> `_bmad-output/HANDOFF-2026-08-08-evening-deployed.md`. Read that file first, and ignore
> `HANDOFF-2026-08-08-messaging-toolsearch-import.md` — its central claim about a blocked
> deploy was wrong and the file above explains why.
>
> Before starting: `git pull` in this repo AND in `~/Documents/ClaudeMemory` (the vault),
> which holds the durable notes. Confirm you are on `9f5e224` or later.
>
> Context in one line: everything is **deployed and live** — parent messaging, deferred
> tool loading, and spreadsheet import scoped across all four authority profiles. What
> remains is not code.
>
> Work these with me, checking before anything irreversible:
>
> 1. **WhatsApp.** It cannot send, and it is not three unset settings — there is no real
>    sender registered and no utility-category templates. Walk me through registering a
>    sender against the existing WhatsApp Business Account, then drafting fee and
>    attendance wording for Meta approval. Do not imply WhatsApp works until it does.
> 2. **The SMS sender.** Both Twilio numbers are US numbers. Advise concretely on an
>    Indian DLT-registered sender: what it costs, how long it takes, what I have to do.
> 3. **Credentials handover.** Passwords cannot be recovered. Recommend whether to reset
>    all four to temporary passwords, and tidy the usernames (`Aman Litt` has a space;
>    `accountant` and `management` are generic words).
> 4. **Decide `origin/local_testing`** (Shubham's Groq commit) with me. The handoff
>    recommends dropping it and salvaging only the flow logging. Do not merge blind.
> 5. **The 30 students without admission numbers** — that CSV is gitignored so it will not
>    be on this machine. Regenerate it from
>    `aaryans_database/Students-06-08-2026-12-08-00.xlsx` if that folder is here, and give
>    me the list to hand to the school.
>
> Standing rules: the test bar is ZERO failures — run
> `MONGO_URL=mongodb://127.0.0.1:27099/eduflow_test DB_NAME=eduflow_test python -m pytest tests/backend/ -q`
> and `cd frontend && CI=true npx jest` plus `npm run build`; never pin a pass count.
> Deploys run as `claude-hosting` — verify with `aws sts get-caller-identity` first.
> Do not run `migrations/run_all.py` against the live database. Write to me in plain,
> non-technical language, and be just as direct about failures as successes.
