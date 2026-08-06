# Aaryans data load — running list of anomalies (opened 2026-08-06)

**Purpose.** Abhimanyu's instruction, 2026-08-06: *"keep adding the data first that doesn't
create any anomaly and keep making the note of the data that are anomalies as we will look
at it at the very end."* So this file is the parking place. Anything that cannot be loaded
cleanly, or that is loaded but carries a caveat, gets written down here instead of being
guessed at or silently dropped.

**Sources.** `aaryans_database/Students-06-08-2026-12-08-00.xlsx` (1,878 students),
`Teachers-06-08-2026-12-09.xlsx` (78), `Students-Fees-Structure-Report-06-08-2026-12-49.xlsx`
(2,004 rows), `Fees-Structure-06-08-2026-12-46.xlsx`.

**Confidentiality.** No child's name, number, address, date or photograph is recorded in
this file. Counts, classes and field names only. That is deliberate — this file is in git.

**Status key:** 🔴 needs a human decision · 🟡 loaded with a caveat · ⚪ noted, no action yet

---

## A. Students who could not be matched or loaded

### A1. ⚪ 30 "students" have no admission number — because they have not been admitted
**Explained by Abhimanyu, 2026-08-06: these have only ENQUIRED and REGISTERED. They have
not taken admission, which is exactly why they have no admission number.** So this is not a
data fault and nothing is missing. They are deliberately NOT on the platform.

**Action when it comes:** if and when any of them actually take admission, they will get an
admission number and can be loaded normally. Abhimanyu will say when. Until then, leave them
out — putting an un-admitted child on class lists and head counts would overstate the roll.

They sit in: 2nd A (5), 7th A (4), 1st A (2), 3rd A (2), 6th A (2), NUR A (2), and one each
in 11th Science A, 2nd C, 3rd D, 5th A, 5th C, 6th B, 6th C, 7th C, 8th A, 9th A, LKG A,
LKG D, UKG A — i.e. the class they have enquired FOR, not a class they are sitting in.

### A2. ⚪ 28 students are on the platform but absent from the export
Presumed left or passed out. **Not deleted** — the rule is that the platform is never
emptied on the strength of a file being shorter. Mostly 11th A (10) and 11th B (5), which
looks like students leaving after 11th; the rest are singles and pairs across 10 classes.

**What is needed:** the school confirms whether these 28 have actually left.

### A3. 🔴 4 students sit in a class that is not a class
Class name `12TH PASS OUT OLD DUE 25-26`, sections A and B. This is a fee-recovery bucket
for students who have already left. Creating them would put people who are gone onto class
lists, head counts and attendance registers. **Not created.**

**What is needed:** confirmation they are ex-students, then a decision on whether the
platform should model "left but still owes money" at all.

---

## B. Values that exist but were deliberately not written

### B1. 🟡 24 values would have overwritten something already on the platform
Per instruction ("only add the blank data for now and keep making the list for the data that
would overwrite"): **17 addresses, 6 phone numbers, 1 roll number.** The platform's existing
value was kept in every case.

**What is needed:** a decision on which source wins for contact details. Worth knowing that
the platform's addresses look templated — 1,802 students share only 489 distinct addresses —
so the school's file may well be the better source here.

### B2. 🟡 3 dates are impossible and were left blank
One date of birth reading year **212**, two admission dates reading year **21**. Typing slips.
Left blank rather than guessed, because a wrong birthday follows a child onto certificates.

### B3. ⚪ Blank stays blank
Per instruction, a field blank in the export is left blank on the platform. Not an error —
recorded so nobody later reads "empty" as "lost". Counts at load time: 247 students had no
gender in the file, 849 no date of birth, 173 no admission date, 451 no photograph.

---

## C. Columns with real data and nowhere to put it

### C1. ✅ ~71 columns had no field in EduFlow — LOADED 2026-08-06
The export is 122 columns. 38 are entirely blank. Of the 84 carrying data, only 13 have a
home in the student record. The other **71 cannot be stored without extending the schema**:
Aadhaar (student, mother, father, guardian), caste / category / religion / nationality,
PEN / APAAR / registration / enrolment / SR numbers, bank and official-bank blocks, PAN,
parent occupation / qualification / income / addresses / emails, TC number and date,
scholarship id and password, domicile / income / caste / DOB application numbers, Samagra id,
govt student and family ids, biometric code, height, weight, disability and RTE/BPL flags,
last school attended.

**Done.** Abhimanyu asked for all 71 to be added and populated. `scripts/import_aaryans_extra_fields_2026_08_06.py`
loaded them into **1,844 students**. No model change was needed for them to be READABLE —
the students routes return raw Mongo documents rather than a `response_model`, so new keys
flow straight through the API.

Four names were changed by hand because the automatic snake_case was wrong or dangerous:
- **`CreatedAt` → `source_created_at`, never `created_at`.** Every student already has
  `created_at` meaning "when this record was made on EduFlow". Writing the school's export
  date over it would have destroyed our own audit metadata on 1,878 records with nothing to
  restore it from. Verified after the load: every `created_at` is still 2026 (ours), and the
  school's timestamps sit separately.
- `SID` → `source_sid` (automatic gives the unreadable `s_i_d`), `Username` →
  `source_username`, `LastActive` → `source_last_active`. These identify the school's
  PREVIOUS system, and the prefix stops anyone reading `username` as a login here.
- `Type` → `admission_type` (its values are `new`/`old`).

**Fees were nested under `fee_snapshot`, not written as loose fields** — deliberate, so that
money does not live in two places under similar names once the real ledger is built. It is a
point-in-time copy of what the export said on 6 Aug 2026 and must never be totalled as the
ledger.

**Still to do:** these fields are readable but not yet EDITABLE — `UPDATABLE_FIELDS` in
`student_service.py` and the UI forms have not been extended. And `source_created_at` holds
the source system's `DD Mon, YYYY HH:MM:SS` text verbatim rather than an ISO date.

### C2. 🔴 Parent photographs have nowhere to go
127 mother photos, 128 father photos, 1 guardian photo. The `guardians` collection has no
photo field (`id, schoolId, student_id, name, relation, phone, whatsapp_phone, is_primary`).
The paths are valid — verified HTTP 200 image/jpeg when prefixed with `https://cdn.vedmarg.com/`.

**Partly closed 2026-08-06.** The paths are now stored on the STUDENT record as
`mother_photo` / `father_photo` / `guardian_photo` (absolute URLs), so the data is no longer
lost. The `guardians` collection still has no photo field, so the photo sits beside the child
rather than beside the parent. **What is still needed:** a photo field on the guardian record
if parent photos should show on the parent's own profile.

---

## D. Photographs

### D1. 🟡 The "View" column is a hyperlink, and the link is the photo
**Corrected 2026-08-06.** An earlier pass read only cell *values*, saw the literal word
`View` on all 1,427 filled rows, and concluded the column was junk from an HTML export. That
was wrong. `View` is the link *label*; the hyperlink *target* is the real photograph on
`cdn.vedmarg.com`. Abhimanyu caught it by clicking one.

**Lesson worth keeping:** when a spreadsheet column looks like junk, check whether the cell
carries a hyperlink before writing it off. `openpyxl` needs `data_only=True` *without*
`read_only=True` to expose `cell.hyperlink.target`.

Counts: **1,427** student photos, **13** teacher photos (both as hyperlinks); parent photos
are relative paths in the cell value instead (see C2). All verified reachable.

### D2. 🟡 Photographs COPIED to the school's own S3 (2026-08-06) — serving still to switch
Every photo URL points at `cdn.vedmarg.com` — the school's *previous* software vendor — and
opens with **no authentication at all**. Two separate problems:

1. **Continuity.** If that vendor's CDN is switched off or the school stops paying, every
   photograph on EduFlow breaks at once. We do not control it.
2. **Privacy.** These are photographs of 1,427 children, publicly readable by anyone with
   the link, with no login. That is a real exposure and it exists *today*, independently of
   EduFlow — but pointing our platform at it makes us a participant in it.

**Recommendation:** download all 1,568 images and re-host them in the school's own S3
bucket under `{school_id}/uploads/...`, served through the authenticated route, then point
the records at those. Until that is done, the stored URLs are a dependency on someone else's
infrastructure.

**Approved by Abhimanyu 2026-08-06 — and then BLOCKED on permissions.** Neither AWS identity
available here can write to the bucket the app already uses
(`eduflow-files-ap-south-1-210447603820`): both `user/Claude` and `user/claude-hosting` are
refused `s3:ListBucket`, `s3:PutObject` and `s3:DeleteObject` on it.

**Do NOT solve this by creating a second bucket.** The app's serve route and its key
convention (`{school_id}/uploads/...`) already point at the existing one; a second bucket
fragments storage, needs new configuration on the server, and buys nothing. **Cost is not the
reason to hesitate either** — the whole set is roughly 1,700 images at ~45 KB, about **80 MB**,
which is under ₹0.20 a month of S3 storage. The blocker is purely a one-time IAM grant.

**What is needed:** add this to the `claude-hosting` user, scoped to the school's prefix only:
```json
{"Effect":"Allow",
 "Action":["s3:PutObject","s3:GetObject","s3:ListBucket"],
 "Resource":["arn:aws:s3:::eduflow-files-ap-south-1-210447603820",
             "arn:aws:s3:::eduflow-files-ap-south-1-210447603820/aaryans-joya/*"]}
```
Note it grants no delete, which keeps it consistent with D-34 (tightening this user, not
loosening it).

**COPIED 2026-08-06.** All **1,692** images (1,423 student, 13 staff, 256 parent) now sit in
`eduflow-files-ap-south-1-210447603820/aaryans-joya/uploads/`. Zero left behind. Three failed
on the first pass with transient network timeouts — re-checked individually, all three URLs
returned HTTP 200, and a re-run copied them, which is the resumable-by-design property paying
off a second time. Spot-checked 6 objects straight out of S3 by their magic bytes: all real
JPEG/PNG.

**Correct the size estimate on the record: the set is 212 MB, not the ~80 MB estimated from
a 45 KB average.** Real average is ~126 KB. Still trivial money (well under ₹1/month), and it
does not change the recommendation against a second bucket or against putting images in
MongoDB — if anything 212 MB makes the MongoDB option worse, being ~15x the whole database.

**WHAT IS STILL OPEN — the privacy half.** `photo_url` still points at `cdn.vedmarg.com`, so
the pictures are still SERVED from the public link. The continuity risk is closed (we hold
our own copies); the exposure is not. Switching needs a `file_uploads` record per image so
`routes/upload.py:serve_file` can authorise and presign it. **Do not mistake "copied" for
"done".**

**IAM NOTE:** full S3 access was granted to `claude-hosting` to unblock this, not the scoped
policy above. Verified: that key can currently read the CockRoach database backups and the
CloudTrail audit logs. Abhimanyu has parked the tightening deliberately — it is not
forgotten, and the scoped policy in `docs/` is ready to paste.

---

## E. Data quality found along the way

### E1. ⚪ Gender was written three ways
`male` / `female` / `boy`. The 4 `boy` values were normalised to `male` on load. Nothing lost.

### E2. ⚪ The school names streams inside the class; the platform does not
The export says `11th Science`, `11th Commerce`, `12th Science`, `12th Commerce`. The
platform has `11th` and `12th` with no stream. Verified on 2026-08-04 and again on
2026-08-06 that the **section matches every single time**, so this is a naming difference,
not a class move. Mapped by stripping the stream word.

**What is needed, eventually:** decide whether EduFlow should record the stream at all. Right
now a Science and a Commerce student in 11th A are indistinguishable on the platform.

### E3. ⚪ Transport is a route name, not a yes/no — and the platform contradicts itself
The `Transport` column holds a bus route (e.g. a village name with a route number), not a
flag. 1,378 students have one; the platform has no transport data at all.

Worse, **the platform disagrees with itself**: `ai/context_builder.py` counts students using
`transport_opted`, while `services/student_service.py` writes `uses_transport`. Setting one
would make Flo's transport figure disagree with the student records. **This is a live bug in
EduFlow, not a data problem.** Not loaded for that reason.

### E4. ⚪ 13 students are marked Inactive in the export
Spread across 9 classes. They were matched and enriched like any other; their status on the
platform was not changed, because status changes are a separate decision from data enrichment.

---

## F. Fees

### F1. ⚪ The fee-structure export is empty — set aside by decision
`Fees-Structure-06-08-2026-12-46.xlsx` contains a header row and a single `Total` row of
zeros. No fee heads, no amounts. Either the export failed or it needs different parameters.

**Closed by decision, 2026-08-06.** Abhimanyu: leave the empty structure export alone and
use the per-student fee report instead. No re-export needed.

### F2. 🟡 The two fee files agree with each other — the source is trustworthy
Cross-checked the per-student fee report against the fee columns inside the student export,
for the 1,844 students in both:

| Measure | Agree | Disagree |
|---|---|---|
| Total fees | 1,843 | 1 |
| Total paid | 1,840 | 4 |
| Total balance | 1,839 | 5 |
| Total discount | 1,840 | 4 |
| Total fine | 1,844 | 0 |

**What is needed:** the school resolves the handful that disagree; we do not pick a winner
on money.

### F3. 🔴 128 students have fees but are not in the student list
The fee report carries 1,972 admission numbers; the student export carries 1,848. Almost
certainly past students still carrying dues. And 4 students in the student list have no fee
row at all.

### F4. 🔴 The platform's fee ledger is empty, so this is a build, not a load
0 fee heads, 0 fee structures, 1 transaction. Importing means constructing the whole ledger
— roughly 11,000 line items across quarterly composite fees, registration, admission, last
year's dues, cheque-bounce, late fine and transport. Money data.

**What is needed:** build it, show class-wise totals to Abhimanyu / the accountant, load only
after that.

---

## G. Teachers — analysed, not loaded

### G1. 🔴 The export is smaller than the platform
78 teachers in the file; **89 staff on the platform** (88 teachers + 1 admin). 66 match on
name *and* phone together. **12 in the file are not on the platform**, and **23 on the
platform are not in the file.**

The file being shorter must not be read as "23 people left". Nothing was deleted and nothing
was loaded.

**What is needed:** the school confirms whether those 23 have left, and whether the 12 are
genuinely new.

### G2. ⚪ The teacher export has no staff id
The `StaffId` column is **entirely empty** for all 78 rows, so there is no stable key. Match
had to fall back to name+phone. Email and mobile both contain duplicates (4 each), so neither
is usable alone. `Username` is unique and is the better key if the school can export it
against the platform's records.

### G3. ⚪ Most teacher columns are empty
Of 40 columns: joining date, designation (76 of 78 blank), qualification (77 blank),
department, experience, bank details, PAN and Aadhaar are all blank or near-blank. The file
usefully carries name, contact, gender, class-teacher assignment (46) and status only.

---

## H. Office staff — on the platform NOWHERE, and not in any spreadsheet

### H1. ✅ Office staff — 9 LOADED 2026-08-06 (2 still without contacts)
From `aaryans_database/adminstaff.jpg` (added 2026-08-06). **None of these 10 is in the
teachers export, and none is on the platform.** The teachers export covers TEACHING staff
only, so the whole office is missing from EduFlow.

| Department | People |
|---|---|
| Admin office | Sakshi Gupta, Lalit Thomas, Sameer |
| Care taker | Sachin Sharma |
| Account office | Sonu (Accountant), Sachin Yadav (Asst.), Shivam Kumar (Asst.) |
| Reception | Asniya, Samiya Ansari |
| Social media | Vipin Kumar |

**Two problems before these can be created.**
1. **The photograph may be cut off.** "Social media / Vipin Kumar" is the last visible row
   and the image ends there. There may be more staff below the crop.
2. **Name and designation is all there is.** No phone, no email, no joining date, no staff
   id. A staff record built from that has no way to sign in and no way to be contacted —
   and `Staff` wants `user_id` and `staff_type`. Creating ten hollow records that then need
   editing by hand is worse than waiting for the detail.

These matter more than they look: the account office and reception map onto real EduFlow
roles (`accountant`, `receptionist`) that gate what a person can see and do.

**Loaded 2026-08-06** from the Employees screen Abhimanyu supplied, which carried email,
mobile and employee code. **9 created**, staff 89 → 98. All 9 have both an email and a
phone. Roles: 2 accountant, 3 management, 1 receptionist, 1 maintenance, 1 transport_head,
1 support_staff.

**The two sources reconcile rather than conflict:** `adminstaff.jpg` gives DESIGNATION
("Care Taker", "Receptionist"), the Employees screen gives DEPARTMENT ("Admin Office").
Both are stored — department from one, designation from the other. No guessing was needed.

**Still open:**
- **No logins were created.** 88 of 98 staff have a login; these 9 do not, because no
  credentials were supplied. They appear in staff lists and can be assigned, but cannot
  sign in. Deliberate — inventing passwords for real people is not ours to do.
- **2 people from the photograph are NOT in the Employees screen and have no contacts:**
  **SONU (Accountant)** and **SAMIYA ANSARI (Receptionist)**. Not created.
- **CHAMAN SINGH (Transport)** appears in the Employees screen but NOT in the photograph —
  so the photograph was indeed incomplete, as suspected.
- `support_staff` was used for the Social Media Executive; the platform has no
  social-media role. Harmless, but it is an approximation, not a fact.

*(`more staff info.txt` in the same folder was checked and does NOT cover these — it is a
subject-and-class teaching allocation from July, all teachers.)*

---

## I. On the platform but not in ANY spreadsheet — the separate list Abhimanyu asked for

Nothing here has been deleted or changed. This is the "we hold it, the school's files do
not mention it" list, kept apart on purpose so it is never confused with data that failed
to load.

### I1. ⚪ 28 students
All 28 are still marked **active** on the platform. By class: 11th A (10), 11th B (5),
6th A (2), 2nd B (2), NUR C (2), and one each in 10th A, 10th B, 12th A, 1st B, 1st C,
2nd E, NUR B.

The 11th concentration (15 of 28) looks like students who left after 11th rather than a
data fault.

### I2. ⚪ 23 staff
22 teachers and 1 admin, all currently active. By sub-category: 11 subject teachers,
11 class teachers, 1 with none set.

The teachers export lists 78 people; the platform holds 89. **A shorter file is not
evidence that 23 people left**, which is why nothing was removed.

**What is needed for both:** the school confirms who has genuinely left. Only then should
anything be deactivated — and deactivated, not deleted, so history survives.

---

## J. Verified twice — 2026-08-06

Abhimanyu asked for everything on the platform, and everything about to go on it, to be
cross-checked twice. Re-run against the LIVE database after all three loaders:

| Check | Result |
|---|---|
| Students | 1,872 |
| Duplicate admission numbers | **0** |
| `class_id` pointing at a class that does not exist | **0** |
| Missing schoolId / branch_id / academic_year_id | **0** |
| Blank name | **0** |
| `created_at` overwritten by the school's date | **0** (all still ours) |
| gender re-compared against the sheet | 1,671 compared, **0 mismatched** |
| date of birth re-compared | 1,056 compared, **0 mismatched** |
| admission date re-compared | 1,773 compared, **0 mismatched** |
| photo_url still holding the literal "View" | **0** |
| fee_snapshot leaked into top-level fields | **0** |

### J1. ⚪ 9 newly-created students have no guardian record
All 9 were created today. **8 have no father name, no mother name and no phone in the
export at all**; the 9th has both parents' names but no phone number. The loader creates a
guardian only when a name AND a phone both exist, so that it never invents a contact for a
family. Correct behaviour, recorded so the gap is visible: NUR D (8), 11th C (1).

**What is needed:** the school supplies parent contacts for those 9.

### J2. ⚪ The school's own class totals independently confirm the load
The class list screenshots from the school's system (2026-08-06) agree with EduFlow after
the load — 2nd = 220, 3rd = 160, 6th = 147, 10th = 101, and so on. Two systems arriving at
the same number by different routes is the strongest check available.

Those screenshots also show **sections that exist but hold no students** (LKG E/F, UKG E/F,
1st D/E/F, 4th C, 12th Science B). EduFlow does not have all of these. Not urgent — an empty
section changes no head count — but the school's structure is the authority.

---

## K. Fee ledger — computed, NOT yet written (2026-08-06)

Totals derived from `Students-Fees-Structure-Report`, cross-checked before any build:

| | Amount |
|---|---|
| Billed | ₹9,60,99,750 |
| Paid | ₹3,51,23,648 |
| **Outstanding** | **₹5,66,60,510** |
| Discount | ₹51,03,942 |

**The file reconciles with itself: 2,003 of 2,004 students satisfy
`fees + fine − discount − paid = balance` exactly.** One row is out by ₹990.

### K1. 🔴 ₹69.8 lakh of outstanding balance belongs to 136 students who are not on the platform
Real money, currently invisible to EduFlow. Includes the 4 passed-out and a spread across
live classes.

### K5. 🔴🔴 THE SCHOOL'S OWN REPORTS DISAGREE ABOUT WHAT HAS BEEN BILLED — STOP HERE
**Found 2026-08-06 by cross-checking the new `Fees-Structure-Report-Summary` against the
per-student report. This is the reason the ledger has NOT been built.**

Comparing like with like (the same 9 fee heads, Transport excluded from both, because the
class summary has no Transport block):

| Population counted | Total billed |
|---|---|
| Every row in the per-student report (2,004) | **₹8,69,36,010** |
| Only students who are in the student export (1,844) | **₹7,87,76,500** |
| **The school's own class summary** | **₹8,02,21,070** |

The school's figure sits BETWEEN the two, so it is counting *some* but not all of the
students who are absent from the student export. **16 of the 18 classes disagree**; only
`12th Commerce` and `12TH PASS OUT OLD DUE 25-26` tie exactly. The gap runs from ₹70,800
(5th, 12th Science) to **₹12.5 lakh (11th Science)**.

Depending on which population is correct, the school's total billed is anywhere between
₹7.88 crore and ₹8.69 crore — **a spread of ₹81 lakh.**

**Why this stops the build.** A ledger is not a report you can revise quietly later: once
~11,000 fee lines exist, every receipt, every outstanding-dues list and every parent
reminder is computed from them. Loading a figure that three of the school's own exports
disagree about would put a number on a parent's receipt that the school's books do not
recognise. The per-student report reconciles beautifully WITH ITSELF (2,003 of 2,004 rows
satisfy fees+fine−discount−paid=balance); that is internal consistency, and it is not the
same thing as agreeing with the class summary.

**What is needed — a human decision, not a guess:**
1. Which population should EduFlow bill: currently-enrolled students only, or everyone with
   an outstanding balance including those who have left?
2. Where does the school's own ₹8.02 crore come from — which students are in it?
3. Confirmation of the treatment of the 136 students carrying ₹69.8 lakh who are not on the
   platform at all.

Until those are answered, no fee data should be written.

### K2. 🔴 Build from the LEDGER report, not from these totals
The Google Drive folder "Vedmarg Data" holds `Ledger-Report-06-08-2026-01-03.xlsx` (3.9 MB),
which is almost certainly the actual transaction list — individual payments with dates and
payment modes. Building from the summary file instead would produce a ledger with **no
payment dates and no payment modes**, which is exactly what the school asked to have.
Waiting on that file being placed in `aaryans_database/`.

### K3. ⚪ 10 payment modes to create
Cash, PhonePe, GooglePay, IMPS, Bank Transfer, Cheque, Payment Gateway, UPI, Net Banking,
NEFT. From the school's own Masters screen.

### K4. ⚪ Other master lists still to add
Education mediums (hindi, english, sanskrit); reservation categories (general, obc, sbc, sc,
st, ews); religions (hindu, muslim, christian, sikh, buddhist, jain, dawoodi bohra); and 16
document types. All captured from the school's Masters screens, none added yet.

---

## L. Evening session, 2026-08-06 — houses, staff attendance, leads, photo serving

### L1. ✅ THE MISSING HOUSES WERE FOUND — 1,204 students restored
The owner reported every student showing "no house". The four real houses (Agamya, Agrim,
Aprajit, Atulya) existed; not one student was linked to one.

**The data was in `aaryans_database/DETAINEES LIST 2025-26.xlsx` all along.** The file
NAME is why it was missed: besides a detainees sheet it carries a `StudentData` master
sheet and one sheet per class, and **64 of those sheets have a `HOUSE` column**.

Two near-misses worth recording:
- The obvious source, the main student export's `HouseBlock` column, is empty for all
  1,878 rows. Correct to rule out — but ruling it out is not the same as concluding the
  data does not exist.
- **`migrations/002_add_houses.py` must NEVER be run here.** It creates four DIFFERENT
  houses (Shivaji/Tagore/Raman/Kalam) and assigns them **round-robin by cursor order** —
  it would have invented a house for all 1,872 children and made the bug look fixed.

Quality of the source: the class sheets and the master sheet agree on **every single
admission number — 0 conflicts across 1,362 students**, and the split is even
(Atulya 348, Aprajit 341, Agrim 340, Agamya 333). That is a real allocation.

**Loaded:** 1,204 matched a student on the platform; 0 overwrites; 158 belong to
admission numbers not on the platform. 668 students still have no house.

**Resolved by the owner, same evening:** Nursery, LKG and UKG are **not assigned houses by
the school**. That is not missing data — it is correct, and those children should show no
house. **Class 1 remains open** and the owner will confirm; recorded in the questions file.
So of the 668 without a house, only the Class 1 cohort is a genuine unknown.

### L2. ✅ A house could have no members even after the load — code bug, fixed
`tool_get_house_details` looked up members with `{"house_id": ...}`. **No student record
has a `house_id` field** — the student side is `house`, holding the NAME. So "who is in
Atulya?" answered zero regardless of the data. Fixed to query `house`.

The unit-test fixture set `house_id` too, which is why this survived: the test and the
code agreed on a field that does not exist in the database. Fixture corrected.

### L3. ✅ Staff attendance loaded — 7,729 records, 1 Apr to 1 Aug 2026
From the four `Staff attendance*.pdf` exports (265 pages). Three properties of that
export had to be handled or the load would have been silently wrong:
1. **A day's block spans ~3 pages and the `Date :` header appears once**, often mid-page.
   Reading per page dropped ~90% of rows.
2. **The exporter wraps text INSIDE a cell, mid-word** (`Abse⏎nt`, `admin_offic⏎e`).
   Fragments must be joined with NO separator — joining with a space corrupts every
   status and role value. Which then means a wrapped date arrives as `02 Apr,2026`, so
   the date pattern must not require the space.
3. **Consecutive files overlap by one day.** 01 May, 01 Jun and 01 Jul appear twice; the
   252 duplicate rows were verified to agree exactly before being de-duplicated.

The parse is self-checking: each day restarts its row numbering at 1, so a missed day
boundary shows up as a restart with no new date. The loader aborts unless that is zero.

**Matching is by NAME, not phone.** Many staff share the school's switchboard number
(8126965555), so a phone match is not identifying — phone is used only to confirm.
Result: 87 of 88 people resolved to exactly one record, 0 ambiguous. Two named
exceptions, both documented in the script: one person's row carries his designation
("SHIVAM KUMAR ACCOUNTANT"), and "THE AARYANS JOYA" is the school's own ERP login, not a
person, so it is excluded rather than given a 111-day attendance record.

**1,807 "pending" rows were deliberately NOT stored** — see L3a for exactly what they are.

### L3a. 🔴 What "pending" actually is, and the staff it exposes
Asked by the owner, 2026-08-06. The three states are cleanly separable in the data:

| State | Rows | Punch time? | Mode | Meaning |
|---|---|---|---|---|
| Present | 5,067 | **always** | Finger Print 4,975 / ERP 76 / Face 16 | the finger was on the scanner |
| Absent | 2,662 | never | **always ERP** | a human marked them absent in the software |
| **Pending** | **1,807** | never | **always blank** | **nothing happened at all** |

So pending is not "not yet decided" in any human sense: the device recorded nothing AND
nobody entered anything. That is 18.9% of all rows. Storing it as absence would have put
1,807 unexplained absences against real staff, and those feed leave balances and payroll —
which is why the loader drops them by design rather than by omission.

**What it exposes.** 11 people are pending on >80% of their days and **10 of those 11 are
the 12 teachers added today**; 4 staff have **no fingerprint punch at all** across four
months. The likeliest explanation is that they were never enrolled on the attendance
device — meaning their attendance is effectively not being captured. Per-person counts in
`aaryans_database/_attendance_pending_heavy.txt` (gitignored — staff names).

**What is needed:** the school confirms whether those staff are registered on the device.

### L4. ✅ 12 new teachers added; the attendance gap closed itself
Adding the 12 (owner correction 5, with Yachika de-duplicated per correction 4) took the
staff list 98 → 110 and took the attendance names that matched **from 74 of 88 to all
88**. No logins were created — the export has no credentials.

### L5. ✅ 101 enquiry leads loaded
From `Leads-06-08-2026-16-55.xlsx`. The platform had zero enquiries, so nothing could
collide. The file's rich parent detail (both parents' names, occupations, previous
school, address) is kept on the enquiry document rather than discarded.

**Not done deliberately:** 53 lead names also match an enrolled child's name. None were
linked or merged — a name is not an identity. 5 share a name with the 30 rejected
applicants and were loaded ACTIVE as the school's own file has them, and reported.

### L6. 🔴 THE LEDGER REPORT IS NOT WHAT K2 EXPECTED — it cannot build a fee ledger
`Ledger-Report-06-08-2026-01-03.xlsx` has arrived. **K2's assumption was wrong.**

It is 69,572 rows of a running school-level account: `Session, Transaction ID, Type
(cr/dr), Amount, Current Amount, Created By, Creation Date`. Covering 2024-25, 2025-26
and 2026-27, 29 Mar 2024 → 6 Aug 2026.

**There is NO student identifier and NO payment mode in it.** So it cannot post a single
payment to a single child's account, which is exactly what a fee ledger has to do. The
hope that this file would unblock the ledger is closed — it does not.

### L7. 🔴 The transport reports do NOT reconcile — a second, independent ₹9 lakh gap
The owner asked for the two new transport fee reports to be read and reconciled. They do
not reconcile.

| Source | Transport billed | Transport paid |
|---|---|---|
| The per-student fee report (1,468 students charged) | **₹1,61,23,170** | ₹52,90,380 |
| The school's own transport summary (51 route blocks) | **₹1,52,20,280** | ₹53,33,290 |
| **Gap** | **₹9,02,890** | ₹42,910 |

This matters more than its size: K5 found the school's reports disagreeing by ₹81 lakh on
the nine non-transport fee heads, and the natural hope was that the missing transport
block explained it. It does not — **transport disagrees separately, on its own.** Two
independent disagreements point at a reporting problem in the source system, not a single
missing piece. **The fee ledger stays paused, and this strengthens the reason.**

### L8. ✅ Photographs now served from the school's own bucket, not the vendor's CDN
This was the highest-priority open item (D2's "privacy half"). It is closed.

**The trap that had blocked it:** the obvious fix — repointing `photo_url` at
`/api/uploads/serve/...` — does not work. Screens render photographs with a plain
`<img src=...>`, and an `<img>` tag cannot send an `Authorization` header. Doing that
would have replaced 1,423 working photographs with broken images. (The platform's own
guardian-photo upload already writes that URL shape, so that path was already broken —
this fixes it too.)

**What was done instead** (`backend/services/photo_url_service.py`): the record keeps its
history, and the API answers with a freshly signed, short-lived S3 link at read time. A
signed link carries its own credential in the query string, so `<img src=...>` works with
**no frontend change**, the link expires on its own, and the public `cdn.vedmarg.com`
address never leaves the server. A vendor URL is never returned as a fallback — a missing
key yields no photograph, which is the entire point.

Guardian rows had no S3 key (the keys were written to the child's record), so 255 were
backfilled first — otherwise switching would have blanked the 255 parent photos that
currently work. Verified: signed links for student, staff and guardian photos all return
real JPEGs from our own bucket. 9 regression tests added.

**Still true:** the images remain public *on the vendor's CDN*. That is the vendor's
infrastructure and outside our control. What has changed is that EduFlow no longer hands
anyone that address.

### L9. ⚪ Bug A2 (parent photos) was a MISDIAGNOSIS — there is no frontend fault
The handoff recorded this as frontend work. It is not. The profile screen renders
`guardian.photo_url` correctly, the API returns it, and the vendor CDN was serving the
images (verified HTTP 200).

**The real position: only 129 of 1,876 children — 7% — have any parent photograph in the
school's data at all.** 255 guardian records carry one, and they resolve to 129 children,
every one of which exists. Anyone opening a handful of profiles would almost certainly
see none, because 93% genuinely have none. **What is needed:** parent photographs for the
other children, if the school wants them shown. No code change will conjure them.

### L10. ⚪ The academic year record is named inconsistently
The academic year with id `ay-2025-26` is **named "2026-27"** and is the current year;
`ay-2024-25` is named "2024-25". Every one of the 1,872 students sits on `ay-2025-26`.
Harmless today because only one year is in use, but the id and the name disagree, and
anything reading the name will report the wrong session. Recorded, not changed — renaming
a live academic year is not a data-load decision.

### L11. ⚪ 8 test records under the principal's name are on the roll
The owner identified 8 student records in NUR D as carrying **the principal's name**,
entered as test accounts by mistake on the old system. They arrived through the school's
own export with real admission numbers, so they were not deleted. **They are counted in
the Nursery roll today.** Awaiting confirmation to move them off the roll (moved, not
destroyed).

*The name and the 8 admission numbers are in the gitignored questions file, §10 — this
file records no name or number, including a member of staff's.*

---

## Change log

- **2026-08-06** — file opened. Students loaded (1,802 → 1,872; 1,765 enriched). Sections A,
  B, C, E, F, G recorded from the load and the read-only comparison. Section D added after
  Abhimanyu found that the `View` column is hyperlinked and the earlier "junk column"
  conclusion was wrong.
- **2026-08-06, later** — photographs loaded: **1,423 students and 13 staff** now carry a
  `photo_url`, taken from the hyperlink targets. Verified by fetching URLs back out of the
  live database: all returned `200 image/jpeg`, 30–64 KB. Three photos belong to admission
  numbers with no student on the platform (the passed-out group, anomaly A3) and were not
  used. 446 students have no photograph in the file and were left blank (B3). Parent photos
  remain unwritten (C2) and the CDN dependency stands (D2) — both still open.
- **2026-08-06, evening** — section L added. Houses found and restored (1,204 students);
  staff attendance loaded (7,729 records, Apr–Aug); 12 teachers added; 101 enquiry leads
  loaded; owner corrections 3, 7 and 8 applied; photographs switched to signed serving
  from the school's own bucket. The ledger report turned out **not** to be a per-student
  transaction list (L6) and the transport reports were found **not** to reconcile (L7),
  so the fee ledger remains paused. Backend suite: 2,373 passed / 0 failed.
