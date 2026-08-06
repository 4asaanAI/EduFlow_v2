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

### A1. 🔴 30 active students have NO admission number
They have names and are marked Active, but the matching rule is admission-number-only,
because matching on a name writes one child's details onto another child. Left completely
alone — not created, not matched.

By class: 2nd A (5), 7th A (4), 1st A (2), 3rd A (2), 6th A (2), NUR A (2), and one each in
11th Science A, 2nd C, 3rd D, 5th A, 5th C, 6th B, 6th C, 7th C, 8th A, 9th A, LKG A, LKG D,
UKG A.

**What is needed:** the school adds admission numbers to these 30 in their own system and
re-exports. They then load with no further work.

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

### C1. 🔴 ~71 columns have no field in EduFlow at all
The export is 122 columns. 38 are entirely blank. Of the 84 carrying data, only 13 have a
home in the student record. The other **71 cannot be stored without extending the schema**:
Aadhaar (student, mother, father, guardian), caste / category / religion / nationality,
PEN / APAAR / registration / enrolment / SR numbers, bank and official-bank blocks, PAN,
parent occupation / qualification / income / addresses / emails, TC number and date,
scholarship id and password, domicile / income / caste / DOB application numbers, Samagra id,
govt student and family ids, biometric code, height, weight, disability and RTE/BPL flags,
last school attended.

**What is needed:** decide which of these the school actually uses, then build fields for
those. Loading all 71 unconditionally would bloat the record with data nobody reads.

### C2. 🔴 Parent photographs have nowhere to go
127 mother photos, 128 father photos, 1 guardian photo. The `guardians` collection has no
photo field (`id, schoolId, student_id, name, relation, phone, whatsapp_phone, is_primary`).
The paths are valid — verified HTTP 200 image/jpeg when prefixed with `https://cdn.vedmarg.com/`.

**What is needed:** add a photo field to the guardian record, then load these 256.

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

**What is needed:** approval to do the migration (it is a bulk download + upload, plus a
rewrite of the stored URLs).

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

### F1. 🔴 The fee-structure export is empty
`Fees-Structure-06-08-2026-12-46.xlsx` contains a header row and a single `Total` row of
zeros. No fee heads, no amounts. Either the export failed or it needs different parameters.

**What is needed:** the school re-runs that export.

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
