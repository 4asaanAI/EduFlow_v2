# EduFlow - Claude Code Project Context

**Model:** Claude Sonnet 4.6 (1M context)
**Last updated:** 2026-08-05
**Working agent:** any capable coding model (Anthropic Sonnet/Opus or other providers) - execution protocols are written model-agnostically

> ## SHIPPED: Enterprise Commercial Operations (2026-08-05)
>
> Commit `3d989e1` is merged to `origin/main`. EduFlow now has lightweight legal-entity
> ownership/reporting, admissions CRM activities and opportunities, campus POS/retail with
> shifts, split payments and returns, entity-aware accounting-period controls, confirmed Flo
> write tools backed by the same domain services as REST, a permanent built-in `/stop-slop`
> communication habit, hardened prompt/KB context, and nine responsive owner/principal
> management hubs. Branding, theme, legacy records, the single active Joya branch, and current
> deep links were preserved. Hostel and full ERPNext/Frappe framework complexity remain out of
> scope. Source of truth: `_bmad-output/implementation-artifacts/spec-enterprise-commercial-operations.md`.
> Release gate: backend 2,163 passed / 0 failed / 15 credentialed deselected; frontend 439
> passed; responsive Chromium 3 passed; production build passed. No live school database was
> read or modified. The code is pushed, but backend deployment is not verified: the configured
> AWS identity can see no Elastic Beanstalk application or environment in any enabled region.

---

> ## ✅ SHIPPED - AI Layer Reliability (Zero Silent Failures) - completed 2026-07-10
>
> This initiative is **DONE and merged** - all 11 epics (R1–R11) shipped, plus the companion
> non-AI reliability set (R12–R15). See `_bmad-output/platform-quality-sweep.md` rows 18–19
> and `_bmad-output/implementation-artifacts/ai-reliability/epic-R*-completed.md`. Its planning
> docs remain in `_bmad-output/planning-artifacts/` for reference; the execution protocol
> (`EPIC-EXECUTION-PROTOCOL-AI-RELIABILITY.md`) and its 7 standing rules still govern any
> follow-on AI-layer work. *(This banner previously read "implementation has NOT started" -
> that was true when written and became stale after the work shipped; corrected 2026-07-23.)*
>
> ## 🚧 CURRENT INITIATIVE - UI Sweep (owner-reported defects, 2026-07-22) - branch `ui-sweep-2026-07-22`
>
> Decomposes the owner's reported defects into epics; same 7 standing rules and one-epic-per-run
> discipline. Plan: `_bmad-output/planning-artifacts/epics-ui-sweep-2026-07-22.md`; live logs in
> `_bmad-output/implementation-artifacts/ui-sweep/`. As of 2026-07-23, Epics 1–6, 8, 9, 10 are
> shipped and Epic 7 (School Directory) is built and gate-green, awaiting deploy. The remaining
> open work is the deeper tool-merge consolidation (`epic-7-tool-merge-impact-note.md`, D-44).
> **Baseline note (corrected 2026-08-04):** the "25 pinned failures" phrasing below is
> historical, and so is the "2–3 order-dependent failures" note that replaced it - D-03 ×2 and
> D-35 were all fixed on 2026-07-23. **The suite baseline is 0 failures.** It was 1967 passed /
> **1 failed** between 2026-07-25 and 2026-08-04 (the certificate permission test, NEW-01/02);
> that is now closed. Never re-pin a non-zero baseline.
>
> ## 🚧 CURRENT INITIATIVE - Inspection Remediation (2026-08-04) - branch `inspection-remediation-2026-08-04`
>
> The 14 findings of the 2026-08-04 platform inspection, worked in 3 blocks of 5/5/4.
> Process and the fixed handoff prompt: `_bmad-output/INSPECTION-REMEDIATION-PROTOCOL-2026-08-04.md`.
> **The register is the only source of truth for progress:**
> `_bmad-output/planning-artifacts/inspection-findings-2026-08-04.md`.
> Logs in `_bmad-output/implementation-artifacts/inspection-2026-08-04/`.

> ## 🚧 CURRENT INITIATIVE - Release 4: the platform can account for itself (2026-08-12) - branch `release-4-2026-08-12`
>
> **Start here:** `_bmad-output/implementation-artifacts/release-4/PROGRESS.md` is the ONLY
> record of what is done. The work itself is
> `_bmad-output/planning-artifacts/release-4-audit-undo-and-honest-menus-2026-08-12.md`.
>
> **Release 4 is NOT just "audit and undo".** That one line is all that was ever copied
> into these notes and it is about a quarter of what was agreed on 12 August. It is six
> parts: one shape for a recorded change, record everything, two-year retention with a
> monthly summary kept forever, undo what hurts and let Flo guide the rest, Flo watching
> storage and raising Layaa AI tickets in LayaaStat, and honest menus in one layout.
>
> **The one idea.** Release 3's faults were all "a query that quietly returned less than
> it should". Release 4's are the same shape moved sideways: **the platform quietly says
> less about itself than it should.** A change never written down looks exactly like a
> quiet day. A button that will be refused looks exactly like a working feature. The test
> for every part: can a person tell "nothing happened" from "we did not record it"?
>
> **Nine settled decisions are in Part 1 of the plan. Do not reopen them.** The two that
> catch people out: **Adesh must NOT see Aman's changes** in the audit trail, and **undo
> covers only what hurts the platform** while Flo talks people through the rest by hand.
>
> **What was found by reading, not assuming.** 16 of 39 areas write audit lines; the rest
> record nothing. Entries are kept forever and nothing deletes one. Undo is narrow because
> there are **eight different shapes** a change gets written in and only one carries a
> before value. The route from the school to Layaa AI **does not exist** (LayaaStat is
> telemetry one way, not a ticket inbox, and needs a piece in another repository). Menus
> are better than expected: the eight office desks are already default-deny off
> `profile_matrix.py` in all three places tools are shown, but **teachers, students and
> guardians are outside that table** with hand-written menus, and there are three
> different layouts where there should be one.
>
> **Grouping never grants, and nothing is ever dropped.** Both rules carry over from the
> post-Release-3 work and neither may be relaxed for a layout change.

> ## ✅ SHIPPED - Release 3: the whole list, on any device (2026-08-12)
>
> **LIVE.** All thirteen items shipped together on 2026-08-12, as Abhimanyu decided.
> Backend `eduflow-release3-20260812-810fe43`, frontend Amplify job 143. *(This banner
> read "CODE-COMPLETE, GREEN, AND NOT DEPLOYED" until it went out; that was true when
> written and stale within hours. Do not leave a deploy state written down without a
> date beside it.)*
>
> **`main` has moved past it.** Release 3 is `810fe43`. Two more commits landed the same
> day from owner reports found once it was live, and they are NOT Release 3 scope - see
> "After Release 3" below. Current `main`: `e6f82fb`.
>
> **Start here:** `_bmad-output/implementation-artifacts/release-3/PROGRESS.md` is the ONLY
> record of what is done. Read it first, update it last, every run. There is no separate
> planning artifact for Release 3; the PROGRESS file carries the reasoning too.
>
> **The one idea behind the whole release.** Every serious fault found on 11 and 12 August
> was the same shape: **a query that quietly returned less than it should.** A lookup
> matching nobody looks like a lookup with nothing to do. A colleague missing to a 50-row
> cap looks like a colleague who left. "All" showing one row looks like a school with one
> student. An export stopping at 2,000 looks like a school with 2,000 children. So wherever
> this release added a filter, an "all" view, a download or a scroll, **the count is visible
> and a partial answer is impossible to mistake for a complete one.**
>
> **A truncated file is worse than a truncated screen**, because it leaves the building and
> gets filed as a record. That is why every export is now COMPLETE OR REFUSED, never short.
>
> Settled decisions, do not reopen: "All" on every table; exports need no confirm window;
> exports MUST respect the Release 2 permission table; the whole-school workbook is Aman and
> Adesh only; **a spreadsheet is NEVER trimmed** (Word and PDF still trim and still say so);
> audit and undo work is Release 4 and separate.
>
> ### What Release 3 changed that you will trip over
>
> | Thing | Where | Why it matters |
> |---|---|---|
> | One page-size ceiling, 500 | `backend/pagination.py`, 16 clamp sites | A page size below 1 is **refused with a 400**, never turned into 1. `max(1, -1)` used to make "All" show ONE ROW. |
> | Every export complete or refused | `routes/exports.py` `_read_all`, ceiling 100,000 | Nothing is ever silently dropped. Past the ceiling the request fails and says no file was made. |
> | Nine export builders, one dictionary | `EXPORT_BUILDERS` | The screen download, Flo, and the whole-school workbook all read through these. **Add a data set here, never beside a route.** |
> | Export permission | `require_export` / `may_export`, derived from `profile_matrix` | One rule asked two ways. Never write a second list of role names. |
> | Download on every table | `lib/exportTable.js`, `ui/ExportButton.js`, `POST /api/export/table` | The control refuses to save a file holding fewer rows than the table says it has. |
> | Filters on every tool table | `ToolPage.DataTable` | Written once for ~70 tables. **The download follows the filter.** |
> | Rows drawn as you scroll | `ui/DataTable` | "All" fetches everything; painting is spread out. The count says drawn AND loaded. |
> | Touch floor: 40px, 16px fields | `index.css` §7 (≤768px) and §7c (`pointer: coarse` + ≥769px) | §7c is NEW. A tablet is 810px wide, so it used to fall off the end of every touch rule and inherit desktop sizes. |
> | Real device tests | `playwright.config.js` projects `phone-pixel`, `tablet-ipad` | The old "responsive" project was Desktop Chrome made narrow: no touch, no pixel ratio. That is why the owner's iPhone report was missed. |
>
> **Never bind a module constant as a default argument** (`max_rows: int = MAX_ROWS`). Python
> evaluates it once at import, so the constant stops being live and every test that changes
> it is silently ignored. This cost a real failure on 12 August. Default to `None` and
> resolve inside the function.

---

> ## ✅ SHIPPED - After Release 3: four owner reports from the live platform (2026-08-12)
>
> Found by Abhimanyu once Release 3 was live, fixed and deployed the same day. These are
> NOT Release 3 scope. Backend `eduflow-msgfix-20260812-6520aed`; frontend Amplify job 145.
> Current `main`: `e6f82fb`.
>
> **1. Every staff message send was returning a 500, and the message was saved anyway.**
> `insert_one` writes Mongo's `_id` into the caller's dict IN PLACE, and `send_message`
> echoed that same dict back. An ObjectId is not JSON, so FastAPI raised AFTER the write
> committed: the sender was told the opposite of what happened and sent again. **The
> stand-in DB is what hid it** - `FakeCollection.insert_one` appended without stamping
> `_id`, so the dict was clean in tests and dirty in production. It now stamps an ObjectId
> in place, exactly like Mongo, which closes the class rather than the instance. With the
> route fix reverted, three tests fail; before the conftest change, zero did.
> **Never return the dict you just inserted.** Read it back with `{"_id": 0}` or strip the key.
>
> **2. There was no inactivity sign-out anywhere, for any profile.** The Settings
> "Session timeout" dropdown offering 30 min / 1 hour / 2 hours **saved nothing and nothing
> read it**, so a protection that did not exist read as a decision already taken. A sign-in
> lasted 7 days and renewed itself. Now `frontend/src/lib/idleLogout.js`: **one hour, every
> profile, the owner included** (Abhimanyu, 2026-08-12), and the Settings control is real
> and drives it. It stores a **deadline, not a countdown** - a sleeping laptop stops timers,
> so a countdown would wake with time still on it and leave school records open on an
> unattended machine. One shared deadline in localStorage across tabs. A missing deadline
> means "not idle": a late sign-out is a smaller harm than throwing somebody out mid-sentence.
>
> **3. Same tab names on every profile.** Only owner and principal menus were clubbed; the
> accountant head, management head, office desks, teachers and students got one flat list.
> `groupToolsIntoHubs` in `lib/managementHubs.js` + `getGroupConfig` in `Sidebar.js`.
> **Two rules, neither may be relaxed:** grouping NEVER grants (each profile's tool list is
> resolved exactly as before; this only picks a tab, so a layout change can never widen the
> permission table), and **nothing is dropped** - `staff-tracker` is in the management head's
> list and in NO hub, so a tabs-only menu would have quietly removed it, which to the person
> looking is identical to access being withdrawn. Orphans are still listed.
>
> **4. The duplicate group icon in Messages is gone.** It opened the same window as the plus,
> which already carries a Direct/Group switch.
>
> ### Still open
>
> - **Aman showed "online" in messaging with nobody signed in. UNEXPLAINED - do not guess.**
>   The light is driven by whether a live stream connection exists right now
>   (`sse_is_connected`), not a stale timestamp, so it could not be reproduced from the code.
>   Two candidates: a genuinely open session somewhere (which the missing idle logout made
>   easy), or a stream registered in `sse_connect` whose `finally` never ran, leaving the
>   entry until the process restarts. The server has restarted since. **If it is still lit
>   with nobody signed in, it is the second one.** Ask before fixing.
> - **The idle sign-out has no "you are about to be signed out" warning**, and unsaved typing
>   is lost when it fires. Flagged to Abhimanyu; build it if it becomes a nuisance.
> - **The idle sign-out was proven by tests, not by sitting in a browser for an hour.** The
>   sleeping-laptop case is covered by a test. Real-device observation is still outstanding.

---

> ## ✅ SHIPPED - Release 2: person profiles for Sonu and Lalit (2026-08-10)
>
> Merged and live as `eduflow-release2-20260812-accfc64`. `main` is at `0b74b6e`.
> **Permissions are now granted by a written-down table, not by subtraction** -
> `backend/services/profile_matrix.py` is the source of truth and
> `frontend/src/lib/toolPermissions.js` is a GENERATED mirror of it. Never hand-edit the
> mirror. The pinned per-profile reach counts in
> `tests/backend/unit/test_all_nine_profiles_sweep_r2_13.py` are the alarm: a count moving
> without a written reason means somebody's access changed and nobody decided to.
>
> The school's accountant head (Sonu Ruhal) and management person (Lalit Thomas) have their
> own logins. **Reference, in this order:**
>
> 1. `_bmad-output/implementation-artifacts/release-2/PROGRESS.md` ← the ONLY record of
>    what is done. Read it first, update it last, every single run.
> 2. `_bmad-output/planning-artifacts/release-2-person-profiles-2026-08-10.md` ← what the
>    work is: the audit (Part 1), the 14 sub-parts (Part 2), the order (Part 3), and the
>    working notes an agent needs to resume cold (Part 4).
>
> **⚠️ The `accountant` and `management` logins are LIVE in production** (confirmed
> 2026-08-10). So everything below is a present condition, not a future risk. Their
> passwords are guessable and **that is a recorded decision of Abhimanyu's, not an
> oversight** (plan, decision 11). Do not change them: it would lock him out of the
> accounts he uses to check the work.
>
> **The one thing to understand.** Sonu's and Lalit's permissions are granted today by
> SUBTRACTION - management is defined as "everything not tagged finance", in
> `frontend/src/lib/toolPermissions.js` and at the bottom of `ai/tool_functions_v2.py`.
> Nothing states what they are supposed to have. That is why Lalit can currently see the
> school's fee figures, read any teacher's salary, open and close the accounting posting
> lock, and run the year-end promotion. R2-1 replaces subtraction with one written-down
> grant table, default deny, read by the menu, the server and Flo alike. Do not patch the
> symptoms without it.
>
> Eight decisions from Abhimanyu are recorded in the plan and are settled; do not re-open
> them.

---

> ## ⚠️ Deploys MUST run as the `claude-hosting` IAM user
>
> Three AWS logins exist for account `210447603820`. Only **`claude-hosting`** carries
> `AdministratorAccess-AWSElasticBeanstalk`. The `Claude` and `claude-code-dev-user`
> logins can read Elastic Beanstalk and can even create an application version, so a
> deploy looks fine right up until `update-environment` fails within seconds on
> `s3:DeleteObject` denied. **That is the wrong-key symptom, not a missing permission.
> Do not ask anyone to widen IAM for it** (a 2026-08-08 session did, and lost the day).
>
> Keys are `AWS_ACCESS_KEY_ID_HOSTING` / `AWS_SECRET_ACCESS_KEY_HOSTING` in the repo
> root `.env` (gitignored, untracked - verified). Confirm with
> `aws sts get-caller-identity` before deploying: the Arn must end `user/claude-hosting`.
>
> The failure happens BEFORE the running app is touched, so a failed deploy never takes
> the school down - it only leaves the environment Red, complaining that the instance
> runs an "incorrect application version". A successful deploy clears that.
>
> Verify a deploy by hitting a brand-new route: **401 proves the new code is live and
> still guarded; 404 means it did not ship.**
>
> **Building the bundle.** There is no deploy script. Build it by hand and CHECK IT
> against the last good one before uploading - a first attempt on 2026-08-08 silently
> dropped `.ebextensions/` (monitoring alarms, SSE timeout, tesseract OCR) and swept in
> stray files from `backend/uploads/`, which may hold real people's documents:
> ```bash
> SHA=$(git rev-parse --short HEAD); ZIP=deploy/eduflow-backend-main-$SHA.zip
> zip -qr $ZIP application.py Procfile requirements.txt backend .platform .ebextensions \
>   -x "*__pycache__*" "*.pyc" "backend/.env" "backend/.env.example" "backend/uploads/*"
> diff <(unzip -Z1 deploy/<last-good>.zip | sort) <(unzip -Z1 $ZIP | sort)   # expect no diff
> ```
> Then `aws s3 cp` it to `elasticbeanstalk-ap-south-1-210447603820`,
> `create-application-version`, and `update-environment`. `deploy/*.zip` is gitignored.
>
> **The frontend deploys itself.** Amplify app `ddxpej151tf13` (EduFlow_v2) builds on every
> push to `main`. Check with `aws amplify list-jobs --app-id ddxpej151tf13 --branch-name main`.

> ## 🆕 Parent messaging + deferred tool loading (2026-08-08) - DEPLOYED 2026-08-08 15:02 IST
>
> **Flo can now send WhatsApp/SMS to families for real**, always behind a confirm card that
> states how many families it reaches. One shared path: `services/messaging_service.py`,
> reached by `/api/parent-messaging/*` (panels) and `send_parent_message` (Flo), pinned by
> `tests/backend/parity/messaging_parity_test.py`. Templates live in `message_templates`
> and Flo can create/edit/delete them.
>
> **SMS wording is free; WhatsApp wording is not.** Meta requires pre-approved templates,
> so `update_message_template` on a WhatsApp template changes only the local PREVIEW. Real
> new wording goes through `submit_whatsapp_template` (Twilio Content API → Meta approval,
> minutes to a day, can be refused). Do not let any doc or prompt imply otherwise.
>
> ⚠️ **WhatsApp cannot send in production, and it is NOT just three unset env vars.**
> Corrected 2026-08-08 by reading the Twilio account directly. `TWILIO_WHATSAPP_FROM`
> and both template SIDs are indeed unset on Elastic Beanstalk - but there is nothing
> valid to set them to yet:
>
> - **No production WhatsApp sender exists.** The only sender on the account is
>   `whatsapp:+14155238886`, which is Twilio's shared *sandbox* number, and it is
>   `OFFLINE`. The sandbox can only message people who have themselves texted a join
>   code, so it can never reach the school's families. A WhatsApp Business Account does
>   exist (`waba_id 757370660501818`); a real sender number must be registered to it.
> - **No school templates exist.** The account holds 3 approved templates, all
>   `MARKETING`-category Layaa AI sales outreach. Fee and attendance reminders are
>   `UTILITY` and must be written and submitted separately. Sending school reminders on
>   a marketing template is wrong and risks the WhatsApp Business Account.
>
> The OLD bulk route silently recorded every recipient as "not_configured" and returned
> success - the new path fails loudly with a 503 naming the missing variable instead.
>
> SMS does have working credentials, but both numbers on the account are **US numbers**
> (`+12286410951`, `+15612508971`). To Indian parents that is expensive per message,
> arrives as an international sender, and is the kind of number Indian carriers filter.
> An Indian DLT-registered sender is the right answer for school SMS.
>
> **Deferred tool loading** (`ai/tool_search.py`) cut an owner/principal turn from ~36,400
> to ~9,700 tokens (73%). A small CORE set is described in full; everything else is listed
> BY NAME and its schema fetched via `search_tools` on demand. It replaced the old
> hide-by-role trim (`EXCLUDE_FOR_ROLE`, now empty), which had caused Flo to tell the
> school's owner an operation was "not available to me" about something they could do.
> **Nothing is ever hidden** - `test_tool_search.py` proves every authorized tool stays
> reachable for all 10 role profiles. Kill switch: `EDUFLOW_TOOL_SEARCH=0`.
>
> Adding a tool? Put it in CORE only if it is genuinely everyday - every CORE name is paid
> for on every turn by every user of that role.

---

> ## 🆕 Spreadsheet import is segment-scoped across four profiles (2026-08-08) - LIVE
>
> Live as `eduflow-main-20260808-9f5e224`. Import is no longer owner/principal-only:
>
> | Profile | May import |
> |---|---|
> | owner, principal (`leadership`) | the whole student record |
> | accountant (`finance`) | bank fields + contact numbers (fee reminders go to those) |
> | management (`non_finance`) | everything except the bank fields |
>
> **One place decides:** `data_import_service.IMPORT_FIELD_SCOPES`, keyed by
> `ai_action_policy.privileged_profile()` - the function that already defines these four
> profiles. Do not add a second copy of that mapping anywhere.
>
> **Out-of-segment columns are REPORTED, never silently dropped** -
> `columns_outside_your_access`, named in the preview before anyone confirms and in the
> result afterwards. A silently dropped column is indistinguishable from an imported one.
> For the same reason, an import where every usable column was out of scope says exactly
> that instead of "the database already has this information".
>
> **Three entrances, one service.** Flo's `preview_data_import` / `import_data_file`
> (chat attachment, by `file_id`), `POST /api/data-import/{preview,apply}` (JSON), and
> `POST /api/data-import/upload-{preview,apply}` (multipart, used by the screen). All
> reach `_build_plan` / `_apply_plan`; `tests/backend/parity/data_import_profile_scope_test.py`
> pins that the screen and the chat produce identical writes.
>
> ⚠️ **The sidebar "Data Import" panel has TWO tabs, and they are not the same feature.**
> "Update existing records" is the scoped import above, open to all four profiles.
> "Add new students" is the OLD `/api/import/{validate,commit}` route
> (`routes/import_data.py`), which **creates** students - minting admission numbers like
> `IMP20260808A3F2C` plus a guardian row each - and is **owner/principal only**, with no
> field scoping because the records are new. Never conflate the two: opening the create
> path to more profiles is how duplicate children and school-unapproved admission numbers
> get onto the roll.
>
> Import can never set fees, class, or enrolment status (`PROTECTED_FIELDS`), matches on
> admission number and never on name, and fills blanks only unless `overwrite=true`.
>
> **Fixed at the same time:** `import_data_file` was missing from `BULK_TOOL_NAMES`, so the
> loop at the bottom of `tool_functions_v2.py` set `requires_confirmation=False` and the
> confirm card its own description promised never appeared - on a tool that rewrites fields
> across the whole roll. Also removed a dead `"access_domain": "students"` literal on both
> import tools: that field is assigned from `SHARED_LOOKUP_TOOL_NAMES` further down the
> module, so the literal was overwritten while still reading as authoritative.

---

## How To Talk To The Humans Here (MANDATORY)

**Always use plain, human, non-technical language** when explaining, reporting, or
replying - every message, not just end-of-task summaries. Abhimanyu and Shubham
read these to make decisions and to relay them to the school's staff, not to
review implementation detail.

- Lead with what it means in ordinary words. Use a technical name only when they
  have to type or click it - then give the exact string, clearly marked.
- Leave out internal machinery (file paths, class names, framework terms) unless
  asked, or unless it's the thing that must change.
- Plain ≠ vague or softened. Be just as direct about failures, costs, and risks -
  only in everyday words. If tests fail, say so plainly.
- This governs prose written *to* the user. Code, commit messages, and the epic
  logs keep their normal technical precision.

---

---

## IMPORTANT: `owner` is a SCHOOL role, not Abhimanyu

`owner` in this codebase is **the school's owner** (the account is "Aman Litt"). Abhimanyu is
the **founder of the platform** - he commissions the work and approves deploys, and he does
NOT hold the `owner` role. Corrected 2026-08-04 after several documents addressed him as
though he did ("your AI limit is used up", "only you can print certificates"), which is a
statement about a school staff account and could have produced the wrong decision about who
may do what.

In prose written to Abhimanyu, never say "you" for an `owner`-role capability - say "the
school's owner". In code, `owner` means exactly what it always did; nothing about the
permission model changes.

## What This Project Is

EduFlow is a **chat-first, multi-role school management SaaS** for The Aaryans (CBSE school, Joya, Amroha, UP, India). **ONE branch, `branch-joya`, and all 1,876 students sit on it** (1,842 active; counted live 2026-08-08 - every doc previously said 1,802, a figure that went stale after the 6 Aug load and was then copied forward. Do not hardcode a roll anywhere: count it) - the trust has other branches but this platform serves Joya only (Abhimanyu, 2026-07-22; see `backend/school_identity.py`). The wording here used to say "multi-branch", which was wrong and led an agent to raise branch-scoping as a live gap on 2026-08-04. Branch scoping still exists in the code and stays, but it guards a future second branch, not a present one.

School staff (owner, principal, teachers, accountants, etc.) manage attendance, fees, academics, staff, and operations through an AI chat assistant + structured tool panels.

**Stack:** React 19 SPA (AWS Amplify) ↔ FastAPI + Python 3.9 (AWS Elastic Beanstalk) ↔ MongoDB Atlas + AWS S3 + Azure OpenAI

---

## Quality Sweep Status

**Master tracker:** `_bmad-output/platform-quality-sweep.md`
**Project context (34 patterns):** `_bmad-output/project-context.md` ← load this first
**Docs suite:** `docs/index.md` ← full project documentation

| Part | Status | Tests |
|------|--------|-------|
| 1 Auth + RBAC | ✅ Done | - |
| 2 AI Layer | ✅ Done | - |
| 3 Owner role | ✅ Done | - |
| 4 Multi-tenancy | ✅ Done | 387→420 |
| 5–16 | ✅ All Done | 699 tests, full party-mode + adversarial ceremony |
| **Operations.py** | 🔧 Wave 3 in progress | expenses/incidents/transport branch isolation |

> **These are historical per-part figures, not a baseline.** They record how many tests each
> part added at the time it shipped; they are not the size of the suite today and must never
> be copied into a "the suite should show N" instruction (D-51/D-56). **The bar is the FAILURE
> count and it is ZERO.** No pass count is recorded here on purpose: every one ever written
> down went stale within days and was then copied forward as a target. Run the commands in
> **Running Tests** below and read the number they print.

**Epic files for all parts:** `_bmad-output/planning-artifacts/epic-part*.md`

---

## Critical Rules - Read Before Writing Any Code

### Python 3.9 (MANDATORY)
```python
from __future__ import annotations  # FIRST LINE in any file using str | None
```
Without this, the file fails to import at test collection time → all fixture-dependent tests silently skip. No exceptions.

### No TypeScript (MANDATORY)
All frontend files are `.js` / `.jsx`. Never create `.ts` / `.tsx`. No type annotations.

### Authentication
```python
# Always import from middleware.auth - never redefine locally
from middleware.auth import get_current_user, require_role, require_access, require_owner, require_owner_or_principal

# Role-only gate
Depends(require_role("owner", "admin"))

# Role + sub_category gate (use this for fine-grained access)
Depends(require_access("admin", sub_category="accountant"))

# Owner-only
Depends(require_owner)

# Owner or admin+principal
Depends(require_owner_or_principal)

# Owner, admin+accountant or admin+principal - the fee-reminder screens
# (WhatsApp defaulter list + bulk send). Widened from owner/accountant on
# 2026-08-08: the principal opens these screens, and the narrower gate made them
# look broken rather than forbidden.
Depends(require_owner_accountant_or_principal)
```

### Multi-tenancy (MANDATORY)
```python
# School scoping - automatic via ScopedDatabase
db = get_db()  # Always use this, never get_raw_db() for operational data
db.students.find(...)  # schoolId injected automatically by ScopedCollection

# Branch scoping - MUST pass explicitly
from tenant import scoped_query
db.students.find(scoped_query({"class_id": cls_id}, branch_id=user.get("branch_id")))

# Intentional school-wide (no branch filter) - add comment
db.classes.find(scoped_filter({}))  # branch-scope: intentional - cross-branch class list
```

**Scoped_query audit (Parts 9-13 MANDATORY):** Before merging any role-vertical story, run:
```bash
grep -n "scoped_filter(" backend/routes/<new_file>.py
```
Every hit must EITHER have a `# branch-scope: intentional - <reason>` comment (approved, do not change) OR be migrated to `scoped_query(branch_id=user.get("branch_id"))`. A hit WITH the comment is a passing result - never convert intentional cross-branch queries.

### Database
- All DB ops must be `async`/`await` with Motor - never pymongo in request handlers
- **Motor cursors:** `find()` returns a cursor, NOT a coroutine. Always chain `.to_list(N)`:
  ```python
  # CORRECT
  items = await db.students.find(query).to_list(500)
  # WRONG - awaiting a cursor object, not the data
  items = await db.students.find(query)
  ```
- Never expose `_id` in responses: `.find(query, {"_id": 0})`
- IDs are string UUID4 - never MongoDB ObjectId
- N+1 queries: batch with `{"id": {"$in": [...]}}` + build a dict, never loop queries
- New indexes go in `database.py → _create_indexes()` only
- New migrations: add to `backend/migrations/` AND update `backend/migrations/run_all.py` in the same PR

### ⛔ NEVER run `run_all.py` against the live school database

**Run migrations one at a time, after reading what that specific file does.** Not the runner.

`_create_indexes()` does **not** run in production (see `database.py` - it is gated on
`CREATE_INDEXES_ON_STARTUP` / non-prod `ENVIRONMENT`, deliberately, so deploying code can never
silently alter the school's data). That means migrations are the only way indexes reach
production, which makes the runner tempting. Do not use it.

**Why (2026-08-06).** The `_migrations` tracking collection was empty while the work behind
those migrations had long since been done by other means, so `run_all.py --status` reported
**0 of 29 applied** and the runner would have executed all of them against 1,802 real students.
Six of them insert **convincing fake data** into what they assume is a fresh demo school:
invented bus routes with real Joya stop names (004), NCERT library books (005), vendors like
"Sharma Furniture Works" (006), discount types plus a fee profile per student (007), events such
as "Republic Day Celebration" (008), and expenses billed to UPPCL (009). `002` reassigns houses
to students who already have them.

The tracking collection now records 28 of 29, each entry carrying a category and evidence, with
`marked_without_running: true` where nothing was executed. **`012_migrate_uploads_to_s3` is the
only one still pending** and is genuinely outstanding; its own docstring says to rehearse it
against a copy of production first.

```bash
# Correct: read the file, then run that one migration and record it.
#   python -c "import 0NN_name; await 0NN_name.migrate(db=db)"  (see the pattern in git history)
# Wrong: python backend/migrations/run_all.py   ← executes every untracked migration
```

### Notification utility (canonical - set in Part 5)
```python
# ✅ CANONICAL (Part 5 ✅ shipped) - ALL notification writes use:
from services.notification_service import create_notification
await create_notification(db=db, user_id=..., title=..., body=...)
# NEVER call db.notifications.insert_one() directly in route handlers
```

### S3 key naming (canonical - set in Part 6)
```python
# ⚠️  Convention established in Part 6 - all new uploads after P6.2 ships use:
key = f"{school_id}/uploads/{file_id}/{safe_filename}"
# Never: f"uploads/{file_id}/{safe_filename}"  ← no school namespace
```

### API Conventions
```python
# Response shapes
{"success": True, "data": [...], "meta": {"count": N}}  # list
{"success": True, "data": {...}}                         # single object

# Errors - ALWAYS raise HTTPException, never return raw dicts
raise HTTPException(status_code=404, detail="Not found")

# 500 errors - global_exception_handler in server.py returns:
{"success": False, "detail": "An internal error occurred"}
# All other HTTPException handlers return:
{"detail": "message"}
# Do NOT add "success" field to non-500 error responses
```

### Frontend Conventions
```js
// API calls - always go through api.js, never inline fetch
import api from '@/lib/api'

// Auth state
const { user, token } = useContext(UserContext)

// File uploads only - use axios; all other calls use native fetch
import axios from 'axios'  // upload only

// Icons - Lucide only
import { Users, BookOpen } from 'lucide-react'

// Path aliases
import { Button } from '@/components/ui/button'  // not ../../components/...

// Tool routing - use React Router v7 primitives (useSearchParams or <Route>)
// NEVER use raw window.location.hash alongside react-router-dom - they conflict
```

---

## Testing Conventions (MANDATORY)

### Every new test file
```python
from __future__ import annotations
import pytest
# NO module-level `pytestmark = pytest.mark.asyncio`. `pytest.ini` sets
# `asyncio_mode = auto`, so every `async def test_…` is marked automatically.
# Adding the mark by hand also lands it on the SYNC tests in the same file, which
# pytest then warns about once per test - that produced 611 warnings before the
# 2026-08-05 audit (A-8). Only add an explicit mark for a tier marker, e.g.
# `pytestmark = [pytest.mark.mongo_real]`.
```

### FakeCursor pattern (async iteration support)
```python
# FakeCursor in conftest.py supports both .to_list() AND async-for
# Use it for any collection that's iterated with `async for doc in cursor:`
from tests.backend.conftest import FakeCollection, FakeCursor
```

### Tenant isolation in fixtures
```python
# Every fixture that creates DB documents must include schoolId:
{"id": "test-id", "schoolId": "aaryans-joya", "branch_id": "branch-a", ...}

# For cross-tenant tests, create docs with different schoolId values:
{"id": "other-school-doc", "schoolId": "other-school", ...}
# Then verify the SUT does NOT return other-school docs
```

### Security test convention (MANDATORY for every new endpoint)
```python
# Every new route MUST have these two tests:
def test_endpoint_unauthenticated_returns_401(client):
    resp = client.get("/api/new-endpoint")  # no Authorization header
    assert resp.status_code == 401

def test_endpoint_wrong_role_returns_403(client):
    headers = _bearer({"user_id": "u1", "role": "student", "name": "T"})
    resp = client.get("/api/new-endpoint", headers=headers)
    assert resp.status_code == 403
```

### Async test timing (keepalive, TTL, delays)
```python
# NEVER sleep(30) in tests. Always monkeypatch the constant:
def test_keepalive_sends_ping(monkeypatch):
    monkeypatch.setattr("services.sse.KEEPALIVE_SECONDS", 0.05)
    # now the loop fires in 50ms, testable with asyncio.wait_for
```

### Shared test factories
```python
# ✅ CANONICAL (pre-p9-2 ✅ shipped) - use for ALL test data creation (Parts 9+):
from tests.backend.factories import make_student, make_staff, make_fee_transaction
# Do NOT create one-off dicts inline - they fragment into 6 different formats by Part 13
```

### Parametrize decision rule
- Use `@pytest.mark.parametrize` when testing the same code path with N ≥ 3 input variations
- Use separate test functions when each case needs different setup/teardown or different assertions
- Never parametrize across security boundaries (each role variant should be its own named test)

---

## Project Structure Quick Reference

```
backend/
├── server.py          # FastAPI app + all routers registered here
├── database.py        # ScopedDatabase, ScopedCollection, _create_indexes()
├── tenant.py          # scoped_filter(), scoped_query(), validate_school_id()
├── middleware/auth.py # get_current_user, require_role, require_access, require_owner*
├── routes/            # 27 route files - one per domain
├── ai/                # tool_functions_v2.py (active), context_builder.py, llm_client.py
├── services/          # s3_storage, sse, email_service, token_service, confirm_tokens
│                      # notification_service.py ✅ (Part 5)
└── migrations/        # 29 scripts. Run ONE AT A TIME - never run_all.py on prod (see above)

frontend/src/
├── lib/api.js         # ALL API calls - single source of truth
├── contexts/          # UserContext (auth), ThemeContext
├── components/        # Layout, ChatInterface, ConfirmActionCard, etc.
└── components/tools/  # Role-specific panels: TeacherTools, FeeCollection, etc.

tests/backend/
├── conftest.py        # FakeCollection, FakeCursor (has __aiter__/__anext__)
├── factories.py       # Shared test data factories ✅ (pre-p9-2)
├── api/               # HTTP integration tests
├── unit/              # Unit tests
└── test_unauthenticated_surface.py  # Enumerates all routes, asserts 401 ✅ (pre-p9-3)

_bmad-output/
├── project-context.md     # 34 critical patterns - load before implementing
├── platform-quality-sweep.md  # master sweep tracker
├── planning-artifacts/    # epic files for all parts
└── parts/                 # per-part ADRs, architecture, epics
```

---

## Architecture Decisions (ADRs)

| Decision | Verdict | File |
|----------|---------|------|
| schoolId: env-var vs JWT | **env-var per instance** (Option A) | `parts/multi-tenancy/adr-001` |
| Audit gate: sync vs fail-open | **fail-open** (logger.warning + proceed) | `parts/multi-tenancy/adr-002` |
| Branch scoping: auto vs explicit | **explicit** (`scoped_query(branch_id=...)`) | `_bmad-output/parts/multi-tenancy/architecture.md §3` |
| Auth: one helper vs per-role | **`require_access()` canonical** | `middleware/auth.py` |
| Notification utility | **`create_notification()` canonical** | set in Part 5 |
| S3 key namespace | **`{school_id}/uploads/...`** | set in Part 6 |
| Audit service | **`write_audit()` via `audit_service.py`** | ✅ Part 7 shipped |
| AI PII redaction | **`ai/redaction.py:redact_for_llm()`** - surgical (special-category keys only; never over-block the LLM) | ✅ AI-Hardening F.1 |
| AI-write kill-switch | **`services/ai_kill_switch.py`** (`db.system_flags.ai_writes_enabled`, fails open) | ✅ F.4 - runbook `docs/deployment-runbook.md` §8 |
| Phase-1 action lockdown | **`services/ai_action_policy.py`** single switch `LOCKDOWN_ENABLED` (Owner+Principal-only AI writes) | ✅ F.11/FR43 - Phase 2 widens it, no engine change |
| AI write-tool parity gate | **`tests/backend/parity/` corpus + CI drift gate** | ✅ F.6 - new write tool ⇒ add parity test + corpus entry |

---

## Hotfixes (Ship Before Part 5)

These are active production failures - do NOT wait for their respective sweep parts.
Sprint-status keys: `hotfix-1-file-serve-unauthenticated`, `hotfix-2-fee-collection-receipt-404`, `hotfix-3-leave-approval-rbac-any-admin`

| Hotfix | File | Fix |
|--------|------|-----|
| `hotfix-1-file-serve-unauthenticated` | `backend/routes/upload.py` | `GET /serve/{filename}` has NO auth at all. Add `Depends(get_current_user)` and a `schoolId`-scoped DB lookup. ⚠️ `hotfix-1` = minimal auth guard only. P6.1 (Part 6) adds the full presigned-URL rewrite on top of this guard - do them in order. |
| `hotfix-2-fee-collection-receipt-404` | `frontend/src/components/tools/FeeCollection.js` | `downloadReceipt` calls `GET /api/fees/transactions/{id}/receipt` which does not exist. Fix the URL to match an actual backend endpoint (e.g. re-use the export endpoint or create a minimal receipt route). |
| `hotfix-3-leave-approval-rbac-any-admin` | `backend/routes/staff.py` | `PATCH /leaves/{id}` uses `require_role("owner","admin")` allowing ANY admin sub_category to approve leaves. Use `Depends(require_owner_or_principal)` which correctly allows owner OR admin+principal only. ⚠️ Do NOT use `require_access("owner","admin", sub_category="principal")` - `require_access` does NOT bypass the sub_category check for owner, which would lock the owner out. |

---

## Part Coordination Notes

- **Parts 5 + 8 ship as a coordinated pair** - SSE keepalive contract (Part 5) must be stable before frontend SSE reconnect (Part 8) is implemented
- **Part 9 is the `require_access()` pattern-setter** - Parts 10-13 cross-reference Part 9 for the correct `require_access(role, sub_category)` usage pattern
- **Part 16 MongoDB indexes move to pre-Part-9** - index migration runs before role vertical work to avoid collection scans under load
- **P6.1 + P6.2 serve_file() collision** - both stories modify `serve_file()` in `upload.py`. P6.2 must EXTEND the auth check from P6.1, not replace it
- **Parts 14-15 gated on Story 7-39** - Story 7-39 activates teacher/student logins. Parts 14-15 cannot begin until 7-39 ships. Parts 9-13 are NOT gated

---

## Running Tests

```bash
# Backend (from repo root) - the bar is 0 failed. No pass count is pinned here: the count
# grows every epic, so a written-down number goes stale and then gets read as a target.
# A dozen or so deselected is normal (the credentialed mongo_real + llm_eval tiers).
# Pin the DB first, or a fail-closed guard in conftest.py stops the run (D-04):
#   MONGO_URL=mongodb://127.0.0.1:27099/eduflow_test DB_NAME=eduflow_test
python -m pytest tests/backend/ -q

# Frontend unit tests - the bar is 0 failed. RUN FROM THE `frontend/` FOLDER, not the root.
# (The two LayoutRouting.test.js failures this line used to warn about were fixed by T12 on
# 2026-08-04; the suite is fully green.)
cd frontend && CI=true npx jest

# ⚠️  This line used to read `npx craco test --watchAll=false`. The frontend moved to Vite +
# plain Jest and craco is NOT installed - that command dies with "could not determine
# executable to run", which reads like a broken machine rather than a stale doc. Corrected
# 2026-08-08. There is no craco.config.js in the repo; do not reintroduce that command.

# Frontend production build - this is what Amplify runs, and it RUNS LINT FIRST
# (`npm run build` = `eslint src --max-warnings=0` then `vite build`). A lint warning
# fails the deploy, so run this before pushing frontend changes, not just the tests.
cd frontend && npm run build

# Frontend E2E
npx playwright test

# Phone and tablet (Release 3, item E). These are REAL device profiles - touch,
# `isMobile`, and a proper device pixel ratio. The older `responsive-chromium` project is
# Desktop Chrome with the window made narrow, which is a small desktop and not a phone;
# that is why the owner's iPhone 15 Pro report of 2026-08-06 was not caught by a green
# suite. Phone and tablet are the PRIMARY devices; desktop is secondary.
npx playwright test --project=phone-pixel --project=tablet-ipad

# ⚠️ Running the E2E suite against the app on a port OTHER than 3000
# `tests/support/e2e_backend.py` is a stand-in server. It used to pin its allowed origin
# to `http://localhost:3000`, so on any other port the browser SILENTLY DROPPED every
# reply and the sign-in page just sat there with no error on it - a dropped response
# looks exactly like a server that never answered. It now echoes the caller's origin
# back, so any port works. If something else on this machine already holds :3000 (it
# often does), build the frontend with `REACT_APP_BACKEND_URL=http://localhost:8000`,
# serve it with `npx vite preview --port 3100`, and pass `BASE_URL=http://localhost:3100`.

# Dev server
cd backend && uvicorn server:app --reload --port 8000
cd frontend && npm start        # Vite on :3000 (both package-lock.json and yarn.lock
                                # exist; npm is what the build and CI actually use)
```

**If tests skip silently:** a file is missing `from __future__ import annotations` - find it and add it.

---

## Before Implementing Any Story

1. Read `_bmad-output/project-context.md` (34 patterns)
2. Read the relevant epic file in `_bmad-output/planning-artifacts/epic-part{N}-*.md`
3. Run `python -m pytest tests/backend/ -x -q` to confirm baseline
4. Check the specific route file + its test file before writing new code
5. Every new test file needs `from __future__ import annotations`. It does NOT need
   `pytestmark = pytest.mark.asyncio` - `asyncio_mode = auto` handles that (audit A-8)
6. Every new endpoint needs: unauthenticated test + wrong-role test (security convention)
7. Role-vertical stories (Parts 9-13): run `grep -n "scoped_filter(" backend/routes/<file>.py` and audit every hit

---

## Key Env Vars (Backend)

```bash
MONGO_URL=mongodb+srv://...    # Required
DB_NAME=eduflow                # Required
JWT_SECRET=...                 # Required in non-dev
SCHOOL_ID=aaryans-joya        # Required in non-dev (raises ValueError if missing)
CORS_ORIGINS=http://localhost:3000
ENVIRONMENT=development        # development | staging | production
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_API_KEY=...        # preferred (SDK-native); AZURE_OPENAI_KEY also accepted (R9.1)
AZURE_OPENAI_DEPLOYMENT=gpt-5.6-luna   # Azure deployment name - this is a Beanstalk env var,
# not a code constant. It was "Odin" through 2026-08-06, switched to gpt-5.6-luna same day.
# Always confirm the LIVE value via `aws elasticbeanstalk describe-configuration-settings`
# before trusting this file or llm_client.py's fallback default - both have drifted before.
# Non-dev: a missing Azure key OR endpoint raises ValueError at startup (fail-loud, like SCHOOL_ID)
S3_BUCKET=...
AWS_REGION=ap-south-1
```
