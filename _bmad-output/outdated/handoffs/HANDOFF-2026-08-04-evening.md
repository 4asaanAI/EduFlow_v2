# Handoff — what is left after 2026-08-04 evening

Branch: `inspection-remediation-2026-08-04`. **Never pushed. Never deployed.**
Production runs `origin/local_testing`, NOT this branch — read
`_bmad-output/planning-artifacts/branch-reconciliation-2026-08-04.md` before any deploy talk.

**Baseline is 0 failures.** Last measured on this branch: backend **2033 passed / 0 failed /
14 deselected**, frontend **378 passed / 0 failed / 36 suites**, evals **18 passed**, real-Mongo
tier **13 passed**, production build compiles with the hook rule at error. Never pin a passing
count as a target (D-51 / D-56); the failure count is the bar.

How to run everything: `scripts/check.ps1`, or the commands in `CLAUDE.md` → Running Tests.
Local venv is `backend/.venv` (Python 3.12) and PowerShell needs its absolute path.

---

## Closed today, do not redo

Commits `88bd212`, `a004b49`, `69aab49`, `e2eed6f`.

D-05, D-17, D-25, D-29, D-41 (code only, needs a deploy), D-44 part 1, D-47, D-48, D-49, D-50,
D-51, D-52 (built, not blocking), D-53, D-54, D-57, D-58, D-59, D-60, D-62, D-63, D-64 (code).
Their entries in `_bmad-output/implementation-artifacts/ui-sweep/DEFERRED-AND-DISCOVERIES.md`
carry the evidence. The owner's second decision round is the table at the end of that file.

---

## TASK 1 — The tool merges (D-44 part 2)

**Owner said: "yes but properly, do not break anything."** That is the whole brief. Epic 9's
standing rule applies: **a wrong merge is worse than no merge.**

Three clusters were named in D-44 as looking like one job each without confidently being one:

| Cluster | Tools |
|---|---|
| Fee | `fee-tracker`, `smart-fee-defaulter`, `fee-receipts` |
| Messaging | `circular-sender`, `parent-message`, `attendance-alerts` |
| Document | `certificate-generator`, `id-card-generator` |

**Before merging anything, prove per cluster that no capability is lost.** The precedent that
matters: the School Directory was NOT allowed to replace Student Database, because Directory is
read-only while Student Database also creates, edits and erases students and shows class
strength. Removing it would have been a capability loss dressed up as a consolidation.

For each cluster, enumerate what each tool can do that its siblings cannot: what it writes, what
it can print or send, which roles and sub-categories reach it, and what its screen shows that the
others do not. Merge only where the answer is genuinely "nothing unique". Where a tool is unique,
say so and leave it. Report what you merged and what you did not, with the reason.

Tool registries live in four places that have drifted before: `ToolDashboard`, `CommandPalette`,
`Layout`, `Sidebar`. D-49 put the document-issuer rule into ONE definition
(`frontend/src/lib/toolPermissions.js`) with `DocumentIssuerMenus.test.js` checking all four
against the server. Follow that shape; do not add a fifth copy of anything.

Remember the certificate/ID-card gate changed today: owner, principal **and accountant** may
issue (`require_owner_principal_or_accountant`), and both routes are now branch-scoped (D-53).

---

## TASK 2 — The data load (D-06, D-07, D-08, D-10 and Track 2)

**Owner's instruction, verbatim in spirit:** compare `aaryans_database/` against what is on the
platform and add what is missing, but the folder mixes two financial years, so most of class 12
has passed out, and students or teachers who do not match are usually **this year's admissions**,
not errors. Add everything very carefully.

### What is actually in the folder (checked 2026-08-04)

| File | What it is | Size |
|---|---|---|
| `Students-22-06-2026-02-35-08.xlsx` | **Current**, exported 22 Jun 2026. Columns: SID, Photo, Name, Mobile, AdmissionNo, Class, Section, Address, MotherName, FatherName | 1,804 rows |
| `DETAINEES LIST 2025-26.xlsx` → sheet `StudentData` | **Last year (FY2025-26).** Columns: S.No, ADM NO, Adm.Date, Dob, Name of Student, Father Name, Mother Name, Contact No., House, gender, CLASS, Address | 1,743 rows |
| Same workbook, ~48 per-class sheets (`1-A`, `2-B 1`, `3C (2)`…) | last year's class lists, duplicated/renamed sheets, messy | ~47 rows each |
| `Teachers-22-06-2026-02-40.xlsx` | 83 teachers, exported 22 Jun 2026. **Header is on a lower row** — row 1 is a title banner | 85 rows |
| `more staff info.txt` | free text | — |
| WhatsApp `.jpeg` files | photos of school material | — |

The two student files **complement** each other: the current one has the right class and section,
the older one has the date of birth, admission date, house and gender the platform is missing.

### Rules that are not negotiable

1. **Match on admission number only.** Names are not unique and are spelled inconsistently.
2. **NEVER take the class or section from the 2025-26 workbook.** It is last year's, and applying
   it would demote every continuing student. Class and section come from the June 2026 export.
3. A student in the 2025-26 file but not in the June 2026 export has most likely **left or passed
   out**. Do not create them. List them for the owner.
4. A student in the June 2026 export but not on the platform is most likely **a new admission**.
   Those are the ones to add.
5. Same logic for teachers and their designations.
6. `~$DETAINEES LIST 2025-26.xlsx` is an Excel lock file. Ignore it.

### The sequence, and do not skip a step

1. **Read-only comparison first.** Produce a written report: how many match, how many would be
   added, how many would be changed field by field, how many are unmatched in each direction, and
   a sample of each category. Nothing is written in this step.
2. **Show the owner that report and get a yes.** Writing to live student records is explicitly
   gated on his approval, every time (see the memory note "prod changes require explicit
   approval").
3. **Dry run**, then apply in batches, with a way back. Take a database backup or record exactly
   what changed per batch so any batch can be reversed on its own.
4. Anything that writes goes through a migration in `backend/migrations/` AND
   `backend/migrations/run_all.py` in the same change, per `CLAUDE.md`.

The live database address is in `backend/.env`. A guard in `tests/backend/conftest.py` refuses a
hosted cluster during tests (D-04) — do not defeat it; set the local test variables instead.

---

## TASK 3 — Items that are the owner's to do, not an agent's

Do NOT attempt these. The `Claude` AWS user was tested on 2026-08-04 and is denied
`wafv2:*`, `cloudfront:*`, `s3:ListAllMyBuckets` and `logs:*`. Remind him if he asks:

- **D-46 firewall.** He said flip it to blocking. **The exclusion must be added FIRST.** That rule
  blocks bodies over 8 KB; switching it on as-is breaks every chat attachment and every document
  upload, which is the D-42 outage all over again. Order: add the `/api/*` exclusion (or a >60 MB
  custom rule), verify a ~50 MB upload still works, then Block.
- **D-64 log purge.** He approved it. CloudFront and server access logs hold conversation-lookup
  URLs carrying id, name, email and role. The code side is already fixed.
- **T14 / D-34.** Remove the inline policy on IAM user `claude-hosting`. Identify it by CONTENTS,
  not name (he renamed it): it holds `s3:CreateBucket` + bucket-hardening on
  `eduflow-files-ap-south-1-210447603820`, and **`iam:PutRolePolicy` on
  `aws-elasticbeanstalk-ec2-role`**, which is the one that matters. Exact JSON:
  `deploy/s3-policy-FOR-THE-CLAUDE-HOSTING-USER.json`. Removing it breaks nothing.
- **D-52 make the check blocking.** Push this branch and open a PR so
  `.github/workflows/tests.yml` runs once, then Settings → Branches → require the **Tests** check
  on `main`.
- **Amplify tidy-up.** `REACT_APP_UPLOAD_URL` is now read by nothing and can be deleted.
- **A deploy.** D-41 (telemetry) and everything else on this branch is code-only until then.

---

## Still open by the owner's choice — do not re-raise

`T9`/`NEW-13` AI answer-quality baseline (needs the production Azure OpenAI key; the 55-question
corpus is ready) · `D-33` the three unproven abilities · `D-30`/`D-31` scanned PDFs and on-demand
vision · `D-32` stall thresholds (left alone deliberately: changing an unmeasured number only
moves the guess) · `D-20` the `ui-ux-pro-max` skill data.

## Watch this one

`D-65` — the frontend suite failed **once**, around the Owner screen's AI health report, and has
not reproduced in three full runs or three isolated runs. If it appears again it is real and it is
a timing problem in that test. Do not dismiss it as noise; that is how D-52 happened.
