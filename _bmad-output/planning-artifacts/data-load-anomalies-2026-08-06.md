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

### D2. 🔴 The photographs live on the previous vendor's CDN, and they are public
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

### H1. 🔴 10 office staff exist only in a photograph
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

**What is needed:** the full office list with contact details — ideally exported the same
way the teachers were — plus confirmation that the photo is not truncated.

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
