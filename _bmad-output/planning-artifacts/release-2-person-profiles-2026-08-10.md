# Release 2 — Person profiles for Sonu and Lalit

**Raised:** 2026-08-10, by Abhimanyu, after meeting Aman and Adesh at Aaryans.
**Branch:** `release-2-person-profiles` (created 2026-08-10)
**Live progress log:** `_bmad-output/implementation-artifacts/release-2/PROGRESS.md`
← *that file, not this one, records what is done. This one records what the work is.*

**Goal:** give the accountant head (Sonu Ruhal) and the management person (Lalit Thomas)
their own logins so they keep the school's data current, without either of them reaching
what they should not.

**Hierarchy the school asked for:** Aman (owner) > Adesh (principal) > Sonu (accountant
head) > Lalit (management). Close-enough tools, because for now only these four people
touch the platform.

**Rollout this belongs to:**

| Release | Who gets in |
|---|---|
| 1 (live) | Aman, Adesh |
| **2 (this document)** | + Sonu, Lalit |
| 3 | + department heads, starting with Chaman Singh (transport head) |
| 4 | + whole admin staff (receptionist, IT, maintenance, support staff) |
| 5 | + teachers |
| 6 | + students |
| 7 | + parents (may merge with 6) |

---

## Decisions taken (Abhimanyu, 2026-08-10)

These are settled. Do not re-open them; ask about something else if it is unclear.
Where a decision excludes somebody, the exclusion is written out, because the
decisions list is what a later reader treats as authoritative.

1. **Lalit and money.** He sees a family's paid or unpaid flag, **as a visible field on
   his student screens**, and never a rupee figure anywhere. *(The "visible or merely
   not-forbidden" question is closed: visible. He is the person chasing day-to-day
   follow-ups and needs to know who is behind without knowing by how much.)*
2. **Sonu's non-money reach.** Staff attendance and leave, read only. Student attendance,
   read only. Full directory read, plus the columns he already owns. **Vendor records in
   full, and Lalit loses them.**
3. **Transport.** Build the transport head profile now for **Chaman Singh**, who already
   exists in the staff records with `sub_category: transport_head`. It stays dormant until
   Release 3. **Until then transport belongs to Aman, Adesh and Sonu, and Lalit loses it**
   (he has Routes & Vehicles and Route Optimisation today, by the accident in §1.2).
4. **Lalit and people records.** He may add and edit students and staff. He may not delete
   them, and he may not create or reset any login.
5. **Creating students.** Sonu may create new students, alongside Aman and Adesh. Lalit
   may too, under decision 4.
6. **Certificates and ID cards.** Lalit may create all of them, but nothing is produced
   until Aman or Adesh approves it, and that approval happens on the platform.
7. **Logins.** *Settled 2026-08-10, third and final version. This table is the target
   state; earlier wordings in this document's change log are superseded.*

   | Person | Login | Password |
   |---|---|---|
   | Aman Litt (owner) | `Aman Litt` — **unchanged, whatever it is today** | unchanged |
   | Adesh Singh (principal) | `Adesh Singh` — gains the surname | unchanged |
   | Sonu Ruhal (accountant) | `sonu.ruhal` — was `accountant` | unchanged |
   | Lalit Thomas (management) | `lalit.thomas` — was `management` | unchanged |

   **Every password stays exactly as it is** (decision 11), and **no password is written
   into this repository**. They follow a role-name pattern, Abhimanyu holds them, and an
   agent doing this work needs the login strings and never the passwords. Writing them into
   a tracked file would put them in the git history permanently for no gain.

   Display names follow the logins, so Adesh reads "Adesh Singh" in the header, in chat and
   in the audit trail.

   ⚠️ **One thing to confirm, not to guess.** Abhimanyu wrote Aman's and Adesh's with a
   space and Sonu's and Lalit's with a dot, which is consistent with Aman and Adesh keeping
   the login they already have while the two office accounts move to the tidier form.
   Migration 031 declares all four in the dotted form (`aman.litt`, `adesh.singh`), so the
   file and the instruction disagree for two of the four. **R2-0 reads the live rows and
   settles it. Default: leave Aman's and Adesh's login strings exactly as they already are
   and change only Adesh's display name.** Changing a login string that did not need
   changing is how the owner gets locked out of his own school.
8. **Staff messaging.** Every school employee must be reachable by chat inside the
   platform, appearing as each release lets them in.

9. **Certificate approval follows the hierarchy exactly.** *Confirmed 2026-08-10.*
   **Aman and Adesh issue directly. Sonu and Lalit create and wait for approval.** One
   rule, no exceptions to remember, matching Aman > Adesh > Sonu > Lalit. This closes the
   gap where Sonu, who sits above Lalit, had no certificate rights at all.
10. **All nine profiles get a proper definition now.** *Revised 2026-08-10. The first
    proposal was to freeze receptionist, IT, maintenance and support staff as they are and
    fix them in Release 4; Abhimanyu chose to define them properly today instead.* The
    matrix therefore carries a considered, written-down grant for every one of the nine,
    not four real ones and five placeholders.

    **Defining is not switching on.** Every profile below Lalit is built and tested now and
    stays dormant until its release. Nobody new gets a login until Abhimanyu says so.

    The drafts are in
    `_bmad-output/planning-artifacts/staff-profiles-draft-for-aman-2026-08-10.md`, written
    in plain words for **Aman to confirm before any of them go live**. They are a proposal,
    not a decision, and they raise nine questions he needs to answer.

11. **The live-account exposure.** *2026-08-10.* Abhimanyu confirmed the `accountant` and
    `management` accounts are enabled in production; the screenshot that started this work
    was taken by logging into one of them. Their passwords follow the account name plus
    `@123`, on a public login page, guarding 1,876 children's records. Login locks out
    after 5 wrong attempts for 15 minutes (`routes/auth.py:55-56`), so the risk is the
    guessability of those two specific strings and nothing else.

    **Decision: the passwords stay as they are for now.** Abhimanyu was offered strong
    replacements and declined, knowingly, on 2026-08-10: the convenience of the current
    ones while only he holds them is worth more to him than closing a gap nobody has
    exploited. **This is a recorded acceptance of a known risk, not an oversight**, and it
    is written here so that nobody later reads it as something the team missed.

    **Do not quietly change them.** Anyone picking this work up: this was decided, and
    changing it back without asking would lock Abhimanyu out of the accounts he uses to
    check the work.

    **Revisit at R2-14, and raise it then.** Handover is the natural moment: that is when
    the passwords stop being Abhimanyu's alone and start being two more people's, and when
    the platform's address starts circulating at the school. The mechanism is ready when he
    wants it: logged in as Aman, the reset control on each profile, or simply asking Flo.
    It runs through `set_profile_password`, which audits the change and revokes open
    sessions. **Layaa does not touch the database to do this**, and no password is ever
    written into this repository.

---

## Part 1 — What is actually wrong today

Every item below was read out of the code on 2026-08-10 and verified, not assumed.
File and line references are given so the next agent can re-check rather than re-discover.
**The line numbers are as of 2026-08-10 and the work itself moves them.** Re-read the file
before trusting a number.

### 1.1 The root cause: the platform grants by subtraction

Two places decide what Sonu and Lalit get, and both work the same way:

- `frontend/src/lib/toolPermissions.js:71-73` — management = *"anything not in
  `FINANCE_TOOL_IDS` and not in `LEADERSHIP_ONLY_TOOL_IDS`"*.
- `backend/ai/tool_functions_v2.py:6796-6804` — every tool not named in
  `FINANCE_TOOL_NAMES`, `SHARED_LOOKUP_TOOL_NAMES` or `LEADERSHIP_ONLY_TOOL_NAMES`
  falls into the `else` branch and is stamped `access_domain = "non_finance"`, which is
  Lalit's.

Subtraction is why every defect below exists, and it is a permanent leak: any tool or
screen added tomorrow lands in Lalit's hands by default, silently. **Nothing in the
codebase states what Sonu and Lalit are supposed to have.** There is no list to read.

Measured 2026-08-10 by the two committed scripts in §4.2. Re-run them after every
sub-part; these numbers are a baseline to move, not decoration.

| Profile | Flo tools (of 161) | of those, writes | API routes (of 483) | Hubs | Screens offered |
|---|---|---|---|---|---|
| Aman (owner) | 155 | 100 | 350 | 9 | 56 |
| Adesh (principal) | 155 | 100 | 336 | 9 | 57 |
| Sonu (accountant) | 48 | 29 | 266 | 2 | 11 |
| Lalit (management) | 112 | 71 | 221 | 7 | 37 |
| Chaman (transport head) | 32 | 0 | 189 | 0 | see §1.10 |
| receptionist | 32 | 0 | 205 | 0 | see §1.10 |
| it_tech | 32 | 0 | 190 | 0 | see §1.10 |
| maintenance | 32 | 0 | 189 | 0 | see §1.10 |
| support_staff | 31 | 0 | 189 | 0 | see §1.10 |

**Two limits on that table, and both matter.** The route column *understates* reach: 106
routes carry no dependency-level guard and check permission inside the handler body, so
the script counts them as unreachable for everyone. The Hubs and Screens columns cover the
hub menu only; the bottom five profiles have no hubs but do have screens, from a different
list entirely (§1.10). A zero there means "no hubs", never "no screens". Both scripts print
these caveats when you run them.

### 1.2 The screenshot: Lalit is offered screens meant for other people

`frontend/src/lib/managementHubs.js:154-158`. `hubItemsForUser` sets
`hasProfileMatrix = true` for principal, accountant and management, and that flag then
skips the check for whether a screen was meant for the owner or the principal.

**Lalit inherits 18 such rows** (measured, not counted by eye): school-pulse,
principal-daily, document-scanner, admission-funnel, enquiry-register, circular-sender,
announcement-broadcaster, parent-message, student-transfer, academic-structure,
timetable-builder, attendance-recorder, staff-attendance-tracker, maintenance-schedule,
vendor-log, raise-maintenance, transport-manager, transport-optimisation.

Sonu inherits 7 the same way, all of them finance, so they are the right screens reaching
him by the wrong mechanism: fee-collection, fee-sync, fee-tracker, financial-reports,
accounting-periods, payroll-manager, expense-tracker.

**Not all 18 are wrong.** Lalit should keep most of them under decision 4; vendor-log and
the two transport rows must go under decisions 2 and 3, and school-pulse needs the
treatment in R2-2 rather than removal. The defect is the mechanism, not each row: he gets
them because nobody decided, and the same accident will hand him whatever is added next.

### 1.3 Lalit can see the school's money, in nine places

| # | Where | What leaks |
|---|---|---|
| 1 | **School Pulse** (`SchoolPulse.js:103-104,176-177`) | "Fees Collected ₹…" and "Overdue Fees ₹…" tiles, plus a fee-collection summary line |
| 2 | **Smart Alerts** (`OwnerTools.js:1497`) | "Overdue fees: ₹… needs follow-up" |
| 3 | `GET /api/fees/class-summary` | fee dues per class. Guard `require_role("owner","admin")` — any admin |
| 4 | `GET /api/fees/status/{student_id}` | full fee status including amounts |
| 5 | `GET /api/fees/discounts/{student_id}` | discounts granted to a family |
| 6 | `GET /api/accounting/periods` | the accounting calendar |
| 7 | `PATCH /api/accounting/periods/{id}/status` | **he can open or close the posting lock** |
| 8 | `PATCH /api/ops/expenses/{id}` | **he can edit an expense** |
| 9 | `GET /api/staff/{staff_id}` (`routes/staff.py:556-565`) | **every teacher's salary**, one record at a time |

On #9: the staff *list* strips salary with the projection `{"_id":0,"salary":0}`
(`staff.py:280`); the single record returns `_public_staff(staff)`, which keeps it.

Vendor Log is a tenth exposure of a different kind: not a leak of figures, but a screen
decision 2 moves to Sonu.

### 1.4 Lalit can do owner-only things through Flo

`backend/services/ai_action_policy.py:70-80`, called from `ai/tool_access.py:33-35`.
The profile decision returns first and short-circuits the registry's own `roles` check.
It tests only whether `roles` *intersects* `{owner, admin}` — a tool marked
`roles=["owner"]` passes that test, and the domain check then hands it to Lalit.

Owner-only tools Lalit can run today: **`year_end_transition`** (promotes every student
on the roll to the next class), `create_branch`, `update_branch`, `delete_branch`,
`update_school_settings`, `get_branch_comparison`, `query_dashboard_summary`. Sonu gets
the finance-side equivalents: `create_legal_entity`, `delete_legal_entity`,
`set_default_legal_entity`.

None of these services carry their own role check. `org_config_service.py:10` says in so
many words that it relies on the route guard and the registry roles, and the Flo path
bypasses both.

### 1.5 Lalit and Sonu can both take people off the roll

`delete_student` and `delete_staff` have no role check inside the service. The REST
routes (`DELETE /api/students/{id}`, `DELETE /api/staff/{id}`) check only
`role in ADMIN_ROLES` (`students.py:103`, `staff.py:108`), which is any admin
sub-category, and the Flo path grants them as `non_finance`. This is a reversible
deactivation rather than destruction, and `set_enrolment_state` puts a person back, so it
is not a disaster. It is still against decision 4.

### 1.6 Certificates: the record asks permission, the printer does not, and they do not speak the same language

There are two certificate paths and only one respects Aman's rule.

- `services/certificate_service.py:41-75` **already does what decision 6 asks.** A
  certificate created by anyone who is not the owner or principal lands in
  `pending_approval` and raises a notification. Aman or Adesh approve it. This predates
  this initiative and must be extended, not rebuilt.
- `routes/image_gen.py:403-478` is the path that actually **prints** the document, and it
  has no approval step at all. Its guard (`require_document_issuer`, line 29) admits
  admin+management by a deliberate decision of 2026-08-08. So **Lalit can produce a
  Transfer Certificate PDF carrying the school's name, immediately, with nobody asked.**

⚠️ **The trap.** The two use different words for the same documents, so "apply the same
rule" is not a copy-paste and a careless fix silently passes the most sensitive document.

| | Types it knows |
|---|---|
| Approval list (`certificate_service.py:20`) | `bonafide`, `tc`, `transfer_certificate`, `character`, `merit` |
| Printer (`image_gen.py:34-41`) | `transfer`, `bonafide`, `character`, `sports`, `participation`, `migration` |

Only `bonafide` and `character` appear in both. The printer's `transfer` does **not** match
`transfer_certificate`, so a naive lookup lets a Transfer Certificate through unapproved.
`sports`, `participation` and `migration` have no approval rule at all, and `tc` and
`merit` do not exist on the printer. R2-9 must reconcile the vocabulary first, and decide
which of the six printable documents actually need approval. Recommendation: the ones that
assert a fact about a child's standing (transfer, bonafide, character, migration) do;
sports and participation are awards and do not.

### 1.7 Staff messaging is empty because the contact list is four hardcoded usernames

This is the "0 colleagues available" in the screenshots. `routes/messaging.py:37-40`:

```python
LEADERSHIP_USERNAMES = {"aman.litt", "adesh.singh", "sonu.ruhal", "lalit.thomas"}
```

`_leadership_contacts` (line 145) looks people up by `username_lower` against exactly
that set. The logins actually in production are reported as `accountant` and `management`,
and Aman's and Adesh's are whatever they were created as, so the lookup matches nobody and
the screen truthfully reports zero. Renaming the logins (decision 7) fixes it by accident
for these four, which is precisely the wrong reason for it to work: the next employee to
join would still be invisible.

**This is also the reason R2-11 is not a cosmetic change.** Something in this codebase
already joins on username. Assume there is more.

Two further things visible in the screenshots: the header reads **RECONNECTING**, so the
live message stream is not connecting in production; and there is **no way to search for a
person** in the New Message dialog, only Direct and Group buttons and, for a group, a name
field with no member picker.

### 1.8 Promises the platform breaks in the other direction

- **Adesh is offered Payroll & Payslips and then refused.** The menu grants the principal
  every screen; the payroll routes use `_require_owner_or_accountant`
  (`routes/payroll.py:43`), which excludes the principal. Eight routes.
- **Sonu is offered 11 screens and none of what he actually does.** No staff attendance,
  no student attendance, no vendors, no staff leave, no transport.
- **Sonu's Flo brief tells him attendance is out of scope** (`ai/prompts.py:1575`).
- **Lalit's Flo brief promises him logins** (`ai/prompts.py:1584`), which decision 4
  removes.

### 1.9 What the platform already gets right — do not "fix" these

- **Password resets are already safe.** `account_management_service.py:237-240`:
  management may change only *student* passwords, and nobody but the owner may change an
  owner's. An early read of the tool registry suggested Lalit could reset Aman's
  password; reading the service proved that wrong. Verify before alarming.
- **Salary edits are already blocked.** `salary` is in `staff_service.OWNER_ONLY_FIELDS`
  and is stripped for every non-owner.
- **Spreadsheet import is already scoped per profile**, and out-of-segment columns are
  reported rather than silently dropped (`data_import_service.IMPORT_FIELD_SCOPES`).
- **Flo already has a separate written brief** per profile (`ai/prompts.py:1569-1587`).
  They need correcting, not inventing.
- **The directory screens carry no money at all** — School Directory, Student Database
  and Staff Tracker were searched for fee, salary, amount and rupee fields. Clean.
- **The certificate record flow already has approval** (§1.6). Extend it to printing;
  do not rebuild it.
- **The four profiles below Lalit have no write access at all today.** Measured: zero
  write tools each, because the Phase-1 lockdown in `ai_action_policy.py` still governs
  them. Whatever else Release 2 does, it must not be the thing that gives them writes.

### 1.10 The four profiles nobody has mentioned, and why they can break

`middleware/auth.py:89-97` recognises **eight** admin sub-categories, not four:
principal, accountant, transport_head, receptionist, it_tech, maintenance, management,
support_staff. Release 2 concerns four of them. The other four have working access today
and a default-deny matrix that names only the ones we care about would silently strip
them.

Their menus come from a different place: not the hubs, but the flat
`ADMIN_SUBCATEGORY_TOOLS` map in `frontend/src/components/Sidebar.js:179-191`.
transport_head has 6 screens listed, receptionist 9, it_tech 4, maintenance 3.

**`support_staff` has no entry in that map at all.** `getSidebarTools` falls through to
the generic admin list minus the hubs, so a support-staff account is currently offered
most of the admin menu. The server refuses much of it, so this is a menu full of dead
buttons rather than an open door, but it is exactly the "offered then refused" failure
this plan is fixing for Adesh. Record it in the matrix; fix it properly in Release 4.

---

## Part 2 — The plan, broken into sub-parts

**The principle.** Stop granting by subtraction. Write down, in one file, exactly what
each person gets: every screen, every tool, every route, named. Anything not on the list
is denied. The menu, the server and Flo all read that one file, so they cannot drift
apart, and a feature added next month gives nobody anything until someone decides who it
belongs to.

That file is also what Releases 3 through 7 extend. This is the pattern, not a patch.

**Sizing.** Rough, so the school can be told something. A "day" is one focused working
session. These are estimates and the first two will tell us how wrong they are.

### R2-0 — Who can log in right now ✅ ANSWERED 2026-08-10

**The `accountant` and `management` accounts are LIVE.** Abhimanyu confirmed it: the
screenshot that started this work was taken by logging into the management account. So
every defect in Part 1 is a live condition, not a future risk. The plan was originally
written as though Release 2 had not happened. It had, partly, and nobody had said so.

**What that changes, and what it does not.** It does not change the order of work below.
It does change how the findings read: §1.3's nine money leaks and §1.4's owner-only tools
are reachable today, by anyone holding those two logins. Right now that is Abhimanyu alone.

Three things still need reading, and they still block R2-11:

- Has migration `031_provision_school_leadership_accounts.py` run in production, and what do
  the four `auth_users` rows actually say?
- Have the accounts ever been used by anyone other than Abhimanyu? Check last-login and the
  audit log.
- What are Aman's and Adesh's exact usernames today? (Reported as `Aman Litt` and `Adesh`,
  which are display names, so the login strings are unconfirmed.)

Read-only. Rule 8 in §4.1 stands: no unapproved change to the live database.

**Passwords: see decision 11.** They stay as they are, by Abhimanyu's explicit choice.
Do not change them; revisit at R2-14.

*Done when:* the three questions above are answered in the progress log and Abhimanyu has
seen them.

### R2-1 — The permission matrix (one source of truth)

**2 to 3 days.**

Create `backend/services/profile_matrix.py` and a generated JS mirror the frontend imports.
Profiles keyed by the person's job. Every entry names screen ids, Flo tool names, API route
groups, and read versus write. **Default deny.**

**All nine profiles go in, properly defined, not four real ones and five placeholders**
(decision 10, revised). The five below Lalit are built from the drafts in
`staff-profiles-draft-for-aman-2026-08-10.md`, **once Aman has confirmed them**, and every
one stays dormant until its release. Defining is not switching on.

If Aman's answers have not arrived when this sub-part starts, build the four in Release 2
first and leave the five as clearly-labelled stubs rather than guessing. A guessed profile
that ships is indistinguishable from an agreed one six weeks later.

Decide and write down how the mirror is produced: a checked-in generated file with a test
that fails when it drifts is simpler than a build step, and it keeps Jest and Vite working
without either learning to run Python. Whichever way, the drift test is the point.

*Done when:* the file exists, all three surfaces read it, no other file makes a per-profile
decision, and the §1.1 numbers are unchanged for all nine profiles. This sub-part is a
refactor: it must move nothing.

### R2-2 — Close the nine money leaks to Lalit

**3 to 4 days. The biggest block.**

Fix everything in §1.3. For School Pulse and Smart Alerts, build a non-finance variant
rather than hiding the whole screen; Lalit still needs the attendance and staffing half of
both. For `GET /api/fees/status/{id}`, return the paid or unpaid flag with amounts
stripped, and surface that flag on his student screens, per decision 1. For
`GET /api/staff/{id}`, drop `salary` at the response boundary for anyone who is not owner,
principal or accountant. Move the accounting-period and expense routes onto the finance
profiles. Take Vendor Log off Lalit.

*Done when*, and these are three separate checks because no single test can do it:

1. **Routes:** a backend test asserts Lalit gets 403 on every route in §1.3 items 3 to 8,
   and that `GET /api/staff/{id}` returns no `salary` key for him.
2. **Payloads:** a backend test asserts `GET /api/fees/status/{id}` as Lalit returns the
   flag and no amount field, by key name, not by grepping for a rupee sign.
3. **Screens:** a frontend test renders School Pulse and Smart Alerts as Lalit and asserts
   the money tiles are absent.

### R2-3 — Close the owner-only hole

**Half a day. Smallest, highest severity.**

Fix `profile_authorization_decision` so the registry's `roles` list is still honoured: a
tool marked owner-only stays owner-only whatever its domain says. Re-check the twelve tools
in §1.4.

*Done when:* a test asserts that for every owner-only tool in the registry, all eight
non-owner profiles are refused, and the §1.1 tool counts change only where intended.

### R2-4 — People records: who may add, edit, remove

**1 to 2 days.**

Per decision 4. Lalit: add and edit students and staff, yes; delete, no; logins, no.
Move the delete guard off `role in ADMIN_ROLES` and into the service, so the screen and
Flo inherit the same answer. Remove `create_student_login` and `set_profile_password` from
Lalit. Per decision 5, add student creation to Sonu.

Do not touch the owner-only salary strip or the student-password limit while in these
files (§1.9).

### R2-5 — Sonu's full remit

**2 days.**

Add, read only: staff attendance, staff leave, student attendance. Add in full: vendor
records, and transport (routes, vehicles, optimisation) as the contingency under decision
3. Add student creation. Correct his Flo brief so it no longer says attendance is out of
scope.

### R2-6 — Fix the dead buttons, for Adesh and for support staff

**1 to 2 days.**

Reconcile every menu with what the server accepts, both directions. Rule: if the menu
offers it, the server accepts it, or it comes out of the menu.

Two known cases, and R2-13's sweep finds the rest. **Adesh** is offered Payroll & Payslips
and refused by eight routes (§1.8). **Support staff** has no menu list at all and falls
through to most of the admin menu, nearly all of it refused (§1.10); under decision 10 as
revised this is now in scope rather than deferred, and its answer comes from the draft in
`staff-profiles-draft-for-aman-2026-08-10.md`.

### R2-7 — One vocabulary: the same department groups for everyone

**1 to 2 days.**

*Decided 2026-08-10.* Sonu and Lalit keep the same department groups Aman and Adesh see,
by name: School Overview, School Database, Finance & Campus Sales, Admissions &
Communication, Academics & Activities, People & Attendance, Campus Library & Assets,
Transport, Reports AI & Governance. They see only the rows their profile grants, and **a
group with nothing in it does not appear at all** rather than opening onto an empty page.
Do not invent per-person group names: one word for one thing across the school, and
Releases 3 through 7 slot straight in.

The problem being fixed is not the group names. It is that today Sonu gets 2 of the 9
groups and Lalit gets 18 rows meant for other people (§1.2).

### R2-8 — Flo per person

**1 day.**

Correct both briefs against the decisions above. Make Flo introduce itself in terms of that
person's job. Make every refusal name who to ask instead ("that is Sonu's to change, or
Adesh's") rather than a flat "not available to me", which this project has already been
bitten by once.

### R2-9 — Certificates and ID cards need approval before they print

**2 days, and read §1.6 twice before starting.**

Per decision 6, and decision 9 if Abhimanyu confirms it. In order:

1. **Reconcile the vocabulary first.** The approval list and the printer name the same
   documents differently, and only two strings overlap. Until one list governs both, any
   "apply the same rule" change passes Transfer Certificates straight through.
2. Decide which of the six printable documents need approval. Recommendation in §1.6:
   transfer, bonafide, character and migration yes; sports and participation no.
3. Extend the existing approval rule to `routes/image_gen.py`. **Do not build a second
   approval system.**
4. ID cards need the rule too and are in no approval list today.
5. Add the approval queue to Aman's and Adesh's screens and notifications, and give Lalit
   a clear "waiting for approval" state so he is never left wondering.

*Done when:* a test proves each of the six document types is either refused or queued for
Lalit, and issued directly for Aman and Adesh, **asserted by type name**, so a vocabulary
drift fails the test rather than passing a certificate.

### R2-10 — Staff messaging: a real colleague directory

**Diagnosis half a day; the rest unknown until the diagnosis lands. Budget 3 days and
expect to re-plan.**

⚠️ **There are two unrelated messaging systems and they are easily confused.** This
sub-part is about `backend/routes/messaging.py`, the **staff-to-staff** chat: threads,
groups, read receipts, live stream. It is NOT `backend/routes/parent_messaging.py` and
`services/messaging_service.py`, which send WhatsApp and SMS to families and shipped on
2026-08-08 (see
`_bmad-output/outdated/handoffs/HANDOFF-2026-08-08-messaging-toolsearch-import.md`, which
warns about exactly this mix-up). Nothing in R2-10 touches the parent path.

**Diagnose before fixing.** Nobody has established whether the live message stream ever
worked in production. RECONNECTING has at least three possible causes and they need
different people: the stream code itself, the guard refusing the request, or CloudFront and
Amplify buffering a server-sent-event response. **If it is the third, this is an
infrastructure task, not a code one, and the estimate above is meaningless.** Find out
which before writing anything.

Then, per decision 8:

- Replace the four hardcoded usernames (§1.7) with "everyone whose login exists and whose
  release has arrived", read from the same matrix as R2-1.
- Add a person search to the New Message dialog and a member picker to New Group; neither
  exists.
- Decide and write down who may message whom as later releases land. Release 5 puts
  teachers in; Release 6 puts students in, and a student-to-staff channel is a different
  question from staff-to-staff. **This needs an explicit answer before Release 5**, not
  at the time.

*Done when:* the RECONNECTING cause is written down and either fixed or raised as
infrastructure work; and Aman, Adesh, Sonu and Lalit see each other, can search, and can
start both a direct chat and a group.

### R2-11 — Rename the two office logins, and Adesh's display name

**Half a day, and it is still the riskiest half-day in this plan.**

Per decision 7, third version. **Smaller than it was:** only `accountant` → `sonu.ruhal`
and `management` → `lalit.thomas` are real login changes. Aman keeps his login untouched.
Adesh gains "Singh", and if his login string already works, change only the display name.
Passwords unchanged for everyone.

**Do not widen this back out to all four** because migration 031 declares the dotted form
for Aman and Adesh too. The file and Abhimanyu's instruction disagree, and the instruction
wins; see the warning under decision 7.

That reduction matters: Aman and Adesh are the only two people using the platform today, so
touching only the two accounts nobody depends on removes most of the lock-out risk. Do not
undo it for tidiness.

**Before touching anything:**

1. R2-0 must be finished, so the live rows are known rather than guessed. In particular,
   confirm Aman's and Adesh's exact login strings before deciding whether either needs to
   change at all.
2. **Find everything that joins on username, not on user id.** §1.7 is proof there is at
   least one: staff messaging looks people up by `username_lower`. Search the whole
   codebase for `username` before assuming that is the only one. Audit rows, notifications,
   chat threads and the `requested_by` and `issued_by` fields on certificates all carry
   identifiers; confirm each stores a user id.
3. **Rehearse it.** Load a copy of the four auth rows into the local test database, run the
   change there, and log in as each of the four before going near production.

**Rollback, written before the change and not after:**

- Take a copy of every `auth_users` row you are about to touch, including `user_info`, and
  save it where Abhimanyu can reach it without a working login.
- The undo is a single update per row restoring `username` and `username_lower`. Write and
  rehearse that statement in the same session, before running the change.
- **If this is ever widened to include Aman, a failure locks the school's owner out of his
  own school.** That is the reason the scope shrank to the two office accounts.

**On the day:** tell the school beforehand, do it at a quiet hour, and have the new
usernames in Abhimanyu's hand before the change, not after. Confirm by logging in as each
of the four, including the two you did not touch.

### R2-12 — Build the transport head profile for Chaman Singh

**Half a day.**

Per decision 3. Chaman Singh already exists in staff with `sub_category: transport_head`
(confirmed in `scripts/apply_owner_corrections_2026_08_06.py:25-26`); he has no login.
Define his profile in the matrix with transport in full and nothing else, and leave it
dormant. Release 3 turns it on and hands transport over from Sonu.

### R2-13 — The proof

**2 days, though most of it is written alongside the sub-parts above.**

One test that walks **all nine profiles**, not four, across all three surfaces: every screen
the menu offers, every route, all 161 Flo tools. It asserts the matrix and fails when a new
tool or screen is added without an owner.

It must also pin decision 10 as revised: each of the five profiles below Lalit matches its
agreed definition, and none of them gained a write tool by accident (all five have zero
writes today, §1.9). This test is what keeps Releases 3 through 7 honest, and it is the
only thing standing between a default-deny matrix and five staff profiles quietly losing
their access or quietly gaining someone else's.

### R2-15 — A daily digest for Aman and Adesh

**2 days.**

Aman asked for everything on the platform to be visible to him. Today that means opening
the Audit Log and reading it, which is a screen you have to remember to go and look at.

Build a once-a-day summary for Aman and Adesh: what Sonu and Lalit changed, how many
student and staff records were added or edited, fee and payroll activity for Aman, and
anything unusual. Delivered inside the platform. **Not on WhatsApp yet**: there is still no
production WhatsApp sender (see the standing note in `CLAUDE.md`), so design it so the
channel can be added later without rewriting it.

The material is already there. `db.audit_logs` records who changed what, when, and the
previous value. This is a reader over existing data, not new recording.

Keep it short enough to actually be read. A digest nobody opens is worse than the audit log,
because it feels like oversight without being any.

### R2-16 — What data is still missing, and who fills it

**Report: 1 day. The loading itself depends on what Aman sends.**

Aman says the only thing pending is the database. Three parts:

1. **A completeness report for Aman.** Scan the student and staff records and list which
   fields are empty and how many records each gap affects: "412 students have no guardian
   email", "the whole roll has no house allocation", and so on. Hand him one list of what
   the school still needs to supply, rather than discovering the gaps one screen at a time
   for the next six months.

   ⚠️ **This reads the live school database.** Read-only, no writes, and Abhimanyu approves
   the run before it happens (rule 8, §4.1). Produce it as a summary of counts, not an
   export of children's records.

2. **Fee structures and balances.** Class-wise fees, transport fees, discounts, and what
   each family has paid so far this year. **This is Sonu's first job** and he cannot start
   without it. Confirm whether it comes as a spreadsheet from the school or Sonu types it.

3. **Transport routes, stops and riders.** Sits with Sonu until Chaman arrives in Release 3.
   Needed before that profile is worth switching on.

Parts 2 and 3 go through the spreadsheet import that already exists and is already scoped
per profile (§1.9). Do not build a new loader.

### R2-17 — One page each for Sonu and Lalit

**1 day.**

Two short guides in plain language, one per person, written for someone who has never used
the platform: this is your screen, these are the five things you will do most, this is how
you ask Flo, this is who to go to when something is wrong. Abhimanyu walks each of them
through it once, in person.

Write them in the same voice as `staff-profiles-draft-for-aman-2026-08-10.md`. No screen
ids, no field names, no jargon. If a sentence needs a technical word to make sense, the
screen is the thing that needs fixing.

### R2-18 — Same-day undo

**2 to 3 days.**

Lalit is typing the school's day-to-day data and will make mistakes, and under decision 4
he cannot delete anything. Give him and Sonu a way to reverse **their own** change on the
**same day**. Older than that, or somebody else's change, goes to Adesh.

**It is buildable from what already exists.** Audit rows carry `changed_by`, `created_at`
and `changes` in the shape `{field: {"previous": …, "new": …}}`, so an undo is a write-back
of the previous value.

**Verify the shape before designing around it.** Not every write path uses that shape
consistently: `student_service.py:393` records `{"previous_state": {"previous": …, "new": …}}`
instead. An undo built on an assumed shape silently does nothing on the paths that differ,
which is worse than not having it. Audit every write path Lalit and Sonu can reach, and make
the shape consistent first if it is not.

Decide and write down: does an undo produce its own audit row? It must. Reversing a change
is itself a change, and Aman's digest (R2-15) should show both.

### R2-14 — Accounts, handover, go-live

**1 day, plus a week of watching.**

Hand credentials over in person, watch the first week, then start Release 3.

**Definition of done for the whole release**, so there is something to sign rather than a
feeling:

1. All nine profiles measured by the §4.2 scripts and matching the matrix exactly.
2. Backend, frontend and build gates green, 0 failures.
3. Lalit's three checks in R2-2 passing.
4. Deployed, and each of the four logs in and walks their own menu with someone watching.
5. No screen offered that the server refuses, for any of the four.
6. Aman has had at least one daily digest and says it tells him what he wanted to know.
7. Sonu and Lalit each have their one-page guide and have been walked through it.
8. The completeness report has reached Aman, and the fee and transport data is either
   loaded or has a named date.

**Sign-off:** Abhimanyu approves the technical release. Aman accepts it on the school's
behalf, because he is the one who asked for it and the one who lives with it.

**"Watch the first week" means:** check the audit log daily for anything Sonu or Lalit did
that surprises anyone, check for 403s in the logs (a 403 is a menu still offering something
the server refuses), and ask Aman directly at the end of the week rather than waiting for a
complaint.

---

## Part 3 — Order of work

One sub-part per run. Suite green before the next. Update the progress log every time.

| # | Sub-part | Why here |
|---|---|---|
| 1 | **R2-0** | Blocks everything. Tells us whether this is planning or an incident. |
| 2 | **R2-1** | The matrix. Everything below reads it. |
| 3 | **R2-3** | The owner-only hole. Smallest, highest severity. |
| 4 | **R2-2** | The money leaks. Biggest single block. |
| 5 | **R2-4** | People records. |
| 6 | **R2-5** + **R2-6** | Sonu's additions and Adesh's refusals. Can pair. |
| 7 | **R2-9** | Certificate and ID card approval. |
| 8 | **R2-10** | Staff messaging. Diagnose first; may re-plan. |
| 9 | **R2-7** + **R2-8** | Menu grouping and Flo briefs. Can pair. |
| 10 | **R2-18** | Same-day undo. Needs the money and people work settled first. |
| 11 | **R2-15** | Aman's daily digest. Reads what the sub-parts above now record correctly. |
| 12 | **R2-12** | Transport head profile, dormant. |
| 13 | **R2-13** | The proof. Written alongside; run whole here. |
| 14 | **R2-11** | Rename the two office logins. Late on purpose: it revokes their sessions. |
| 15 | **R2-17** | The two guides. Written once the screens have stopped moving. |
| 16 | **R2-14** | Go-live. |

**R2-16 runs alongside, not in sequence.** The completeness report can be produced as soon
as Abhimanyu approves the read, and the answer goes to Aman, who then has to gather things
from the school. Start it early precisely because it waits on other people.

Rough total: **23 to 30 working days**, plus whatever R2-10's diagnosis turns up and
whatever the school's data gaps turn out to be. Treat that as a shape, not a promise, and
revise it after R2-1.

## Part 4 — Working notes for whoever picks this up

### 4.1 The rules that govern this work

Inherited from `CLAUDE.md` and the earlier execution protocols; they still apply.

1. **The suite baseline is 0 failures.** Never pin a pass count; run the suite and read
   what it prints.
2. **Never run `backend/migrations/run_all.py` against the live school database.** One
   migration at a time, after reading what that file does.
3. **Deploys run as the `claude-hosting` IAM user.** Confirm with
   `aws sts get-caller-identity` first; the Arn must end `user/claude-hosting`.
4. **No TypeScript.** `.js` and `.jsx` only.
5. **`from __future__ import annotations` is the first line** of any Python file using
   `str | None`.
6. **Do not add `pytestmark = pytest.mark.asyncio`** to test files; `asyncio_mode = auto`
   already handles it.
7. **`owner` is the school's owner (Aman), never Abhimanyu.** In prose written to
   Abhimanyu, say "the school's owner", not "you".
8. **Never modify the live school database without Abhimanyu's explicit approval**, and
   never read it beyond what a named sub-part requires. R2-0 is read-only.

### 4.2 How to re-measure everything in §1.1

Both scripts are committed, so the numbers are reproducible rather than described. Both
are safe: they import the app and the frontend modules and read them in memory, touching no
database and sending no request. **Re-run them after every sub-part** and put the numbers
in the progress log.

```bash
backend/.venv/Scripts/python.exe scripts/audit_profile_reach.py   # Flo tools + API routes
node scripts/audit_profile_menus.mjs                              # hub menus
node scripts/audit_profile_menus.mjs --ids                        # ... with every screen id
```

Each script prints its own limits. Read them before quoting a number: the route column
understates reach because 106 routes check permission inside the handler body, and the menu
script covers hubs only, so a zero for the bottom five profiles means "no hubs" and never
"no screens".

Use `backend/.venv/Scripts/python.exe` (Python 3.12). The machine's `py -3.9` is 3.9.0 and
cannot build the bcrypt and cryptography wheels.

### 4.3 Where this is verified

**There is no staging environment.** That is a real gap and it shapes how this ships.

- Everything up to deployment is verified against the local test database
  (`MONGO_URL=mongodb://127.0.0.1:27099/eduflow_test DB_NAME=eduflow_test`) plus the three
  gates in §4.1 rule 1.
- The two audit scripts are the regression check between sub-parts: run them before and
  after, and explain every number that moved.
- **R2-11 gets a rehearsal** against a local copy of the four auth rows, because it is the
  one step whose failure locks the school out.
- Deployment is verified by hitting a brand-new route: 401 proves the new code is live and
  still guarded, 404 means it did not ship. Then log in as each of the four.

### 4.4 Still open

1. **Aman's answers to the five profile drafts**
   (`staff-profiles-draft-for-aman-2026-08-10.md`). Nine questions, the sharpest being
   whether the receptionist should keep Student Transfer and Commercial Operations, and
   whether maintenance may still edit the vendor list now that vendors are Sonu's. Blocks
   the five dormant profiles in R2-1, not the four live ones.
2. **Who may message whom** from Release 5 (teachers) and Release 6 (students)? Needed
   before Release 5, not during it.
3. **The three reading tasks left in R2-0**: has 031 run, have the two accounts been used
   by anyone but Abhimanyu, and what are Aman's and Adesh's exact login strings. Blocks
   R2-11.
4. **Passwords at handover** (decision 11). Not open now; raise it again at R2-14 and let
   Abhimanyu decide with the school about to be given the address.

---

## Change log for this document

| Date | Change |
|---|---|
| 2026-08-10 | Created after the audit. Decisions 1-4 recorded. |
| 2026-08-10 | Revised after Abhimanyu's answers: transport returns to Sonu as a contingency and Chaman Singh's profile is built dormant (3); Sonu may create students (5); certificates and ID cards need approval before printing (6); logins rename (7); staff messaging added as R2-10 (8). Added Part 4 so any agent can resume. |
| 2026-08-10 (later) | Decision 7 widened to all four logins including Aman and Adesh, with display names. R2-7 settled on one shared vocabulary of department groups. |
| 2026-08-10 (readiness gaps) | Four sub-parts added after asking what was still missing. **R2-15**, a daily digest for Aman, because "everything is visible to me" currently means remembering to open the audit log. **R2-16**, a report of which fields are empty across the roll, so Aman gets one list of what the school still owes rather than discovering gaps for six months, plus the fee and transport data Sonu cannot start without. **R2-17**, a one-page guide each for Sonu and Lalit. **R2-18**, same-day undo of their own changes, since Lalit types all day and cannot delete. Total moved from 17-22 days to 23-30. Definition of done gained three items. |
| 2026-08-10 (final credentials) | Decision 7, third and last version. **Only the two office logins change**: `accountant` → `sonu.ruhal`, `management` → `lalit.thomas`. Aman keeps his login untouched and Adesh gains "Singh", which reverses the earlier "all four move to the dotted 031 form". R2-11 shrank accordingly and most of the lock-out risk went with it. Passwords unchanged for everyone, and none is written into this repository. |
| 2026-08-10 (Abhimanyu's answers) | **R2-0 answered: the `accountant` and `management` accounts are LIVE**, so Part 1 describes a present condition, not a future risk. Decision 9 confirmed: Sonu and Lalit both create-and-await-approval, Aman and Adesh issue directly. Decision 10 **reversed**: the five profiles below Lalit get proper definitions now rather than being frozen until Release 4, drafted for Aman in `staff-profiles-draft-for-aman-2026-08-10.md` and dormant until their release. Decision 11 added: passwords stay as they are, a risk Abhimanyu accepted knowingly, to be revisited at handover. Support staff moved into R2-6's scope. |
| 2026-08-10 (adversarial review) | Nineteen findings folded in. Added **R2-0**, because nobody had checked whether Sonu's and Lalit's logins are already live. Added §1.10 and decision 10: the platform has eight admin profiles, not four, and a default-deny matrix would have silently stripped the other four. Rewrote §1.6 after finding the approval list and the printer use different words for the same documents, so the obvious fix would have passed Transfer Certificates unapproved. Added decision 9 (Sonu's certificate rights, previously undefined). Committed both audit scripts instead of describing them, and corrected §1.2 from 12 rows to a measured 18. Filled the writes column for all nine profiles. Gave R2-11 a rollback and a rehearsal rather than only a warning. Split R2-2's untestable acceptance criterion into three real ones. Made R2-10 diagnose before fixing. Added sizing, a definition of done, sign-off, and §4.3 on where any of this is verified. |
