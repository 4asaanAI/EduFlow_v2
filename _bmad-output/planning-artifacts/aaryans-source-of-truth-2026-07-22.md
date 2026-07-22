# The Aaryans — Source of Truth vs Platform Reality

**Compiled:** 2026-07-22 · **Source:** `E:\Layaa AI\Clients\Education\The Aaryans\aaryans_database`
(8 photos, 3 spreadsheets, 1 text file) reconciled against a **read-only** query of the
live database (`eduflow` / `aaryans-joya`).

> Nothing in this document has been written to the database. It exists to drive
> Track 1 (UI) and to be the specification for Track 2 (the data load).

---

## 1. School identity

- **The Aaryans**, Senior Secondary Co-educational, CBSE **Affiliation No. 2133014**
- Prem Nagar, Joya, Delhi–Moradabad Highway, Distt. Amroha 244222 (U.P.)
- +91-8126965555 / 8126968888 · theaaryansjoya@gmail.com · www.theaaryans.in
- Current session on paper: **2026-27**. Database has 2 academic years, 2 branches.

---

## 2. Enquiry / Admission form — the authoritative student field list

From the printed **ENQUIRY FORM** (photo 1). Marked ✅ if the platform stores it,
❌ if there is nowhere to put it, ⚠️ if the field exists but is empty for every student.

| # | Field on the paper form | Platform |
|---|---|---|
| — | Reg. No. | ❌ no field |
| — | Admission No. | ✅ 100% filled |
| — | Class sought | ✅ |
| — | Session | ✅ (academic year) |
| 1 | Name of student | ✅ 100% |
| 1 | **Aadhar No. (student)** | ❌ no field |
| 2 | **D.O.B.** | ⚠️ field exists, **0 of 1802 filled** |
| 2 | Age | derive from D.O.B. |
| 2 | **Gender** | ⚠️ field exists, **0 of 1802 filled** |
| 2 | **Blood Group** | ⚠️ field exists, 0 filled |
| 3 | **Previous school attended** | ❌ no field |
| 4 | Father's Name | ✅ via `guardians` (3604 records) |
| 4 | **Father's Aadhar No.** | ❌ no field |
| 5 | Mother's Name | ✅ via `guardians` |
| 5 | **Mother's Aadhar No.** | ❌ no field |
| 6 | **PEN No. (Permanent Education Number / UDISE)** | ❌ no field |
| 7 | Address | ✅ 100% |
| 8 | Contact No. | ✅ 100% |
| 9 | Transport | ✅ `transport_opted` 100% |
| 10 | **APAAR ID + consent (Yes/No)** | ❌ no field |
| 11 | Declaration / T.C. undertaking | ❌ no field |
| — | Date, Place, Attended by | ❌ no field |
| — | **House** | ⚠️ field exists, **0 of 1802 filled** |
| — | **Admission Date** | ⚠️ field exists, **0 of 1802 filled** |

**Nine fields on the paper form have nowhere to live in the platform.** Five more
exist but are empty for every single student.

---

## 3. Documents required at admission (photo 2)

Four passport photos of student + two each of father and mother · T.C. in original ·
Municipal birth certificate (Xerox, first-time admission) · Aadhar card photocopy of
father, mother and student · Report card of last school · **PEN (UDISE)** and **APAAR ID**.
No admission is deemed complete until all are submitted — **time limit 7 days**.

→ Implies a **document-checklist feature** per student that does not exist today.

---

## 4. Age limits by class (photo 8) — admission validation rule

| Class | Age | Class | Age |
|---|---|---|---|
| NUR | 3 | V | 10 |
| LKG | 4 | VI | 11 |
| UKG | 5 | VII | 12 |
| I | 6 | VIII | 13 |
| II | 7 | IX | 14 |
| III | 8 | XI | 16 |
| IV | 9 | | |

Eligibility measured **as at July 2026**. Nothing in the platform validates this.

---

## 5. Fee structure 2026-27 (photo 7) — authoritative

| Class band | Admission fee | Composite/month | Sibling conc./mo | Quarterly | Sibling conc./qtr | **Total** |
|---|---|---|---|---|---|---|
| Nur–UKG | 12,000 | 2,350 | 470 | 7,050 | 1,410 | 28,200 |
| I–II | 12,000 | 2,750 | 520 | 8,250 | 1,560 | 33,000 |
| III–V | 13,000 | 2,950 | 550 | 8,850 | 1,650 | 35,400 |
| VI–VIII | 13,000 | 3,250 | 600 | 9,750 | 1,800 | 39,000 |
| IX–X | 16,500 | 4,000 | 700 | 12,000 | 2,100 | 48,000 |
| XI–XII Com | 16,500 | 5,500 | 870 | 16,500 | 2,610 | 66,000 |
| XI–XII Sci | 16,500 | 5,900 | 970 | 17,700 | 2,910 | 70,800 |

- Registration fee: **₹1,200** (Nursery–VIII), **₹1,500** (IX–XII)
- Four quarterly instalments, due 15 Apr / 15 Jul / 15 Oct / 15 Jan
- **Late fine ₹10/day**; after 3rd month of an instalment the name is struck off
  and re-admission costs **₹1,000** plus arrears
- **5% discount** on full-session payment made on or before 30 April
- Transport extra, 11 months

→ Platform has 7 `fee_discount_types` but **1 fee transaction total**. The sibling
concession, the ₹10/day fine, the 5% early-payment discount and the strike-off rule
are all business logic that needs checking against this table.

---

## 6. Transport (photo 6)

**~250 named pick-up points** with both old and new 2026-27 monthly rates
(range roughly ₹620–₹1,900). Examples: Joya 620→650, Amroha Roadways 870→910,
Moradabad 1,610→1,680, Venkateshwar University 1,910→1,900.

→ Platform has transport tools and `transport_opted` on every student, but the
**route/rate table is not loaded** (`route_id` empty for all 1802 students).

---

## 7. Houses (photo 5) — names confirmed

**ATULYA · AGRIM · AGAMYA · APRAJIT** — 4 houses, matching the 4 in `houses`.
The assembly rota assigns staff to each house week by week.

→ `houses` collection is correct. **Student house assignment is empty for all 1802**,
even though the DETAINEES spreadsheet carries a House column.

---

## 8. Staff designations (photo 4) — the school's real vocabulary

The staff attendance register uses a **"Desi."** column with these values:

| Code | Meaning |
|---|---|
| **PRIN** | Principal |
| **NTT** | Nursery Teacher Training (pre-primary) |
| **PRT** | Primary Teacher |
| **TGT** | Trained Graduate Teacher |
| **PGT** | Post Graduate Teacher |
| **Other** | Non-teaching |

**This is the taxonomy the school actually uses** — not `class_teacher` /
`subject_teacher`. Directly relevant to the roles redesign.

**Leave types on the register:** Casual · Medical · **Special** · **Without Pay**
(plus Leave Balance and Total Attendance columns).
→ Platform tracks Casual / Medical / **Earned**. `Special` and `Without Pay`
are missing; `Earned` is not on the school's register.

---

## 9. Class teachers (photo 3)

A complete **class → class-teacher** list for all 48 sections, NUR-A through 12-C.
(4-C is blank on the sheet.) Names are informal first names ("Preeti Singh mam",
"Furqan Sir") and need matching against the 89 staff records.

---

## 10. Subject allocation (`more staff info.txt`)

Subject-wise teacher → class-section mapping for ~50 teachers across English, Hindi,
Sanskrit, Maths, Science/Physics, Social Science, Computer, Art, Sports, G.K.,
Commerce, Music, Dance, Library.

**Already partly in the database:** the `subjects` collection holds **293 records**
with `name`, `class_id` and `teacher_id` — Music 36, Library 36, Art 32, Computer 30,
Science 29, English 27, Sports 27, Hindi 25, Mathematics 19, Dance 18, G.K. 7,
Social Science 6, Commerce 1. `period_links` holds another 293 rows tying
teacher + subject + class.

→ **Subjects are not missing.** The Staff Tracker simply never reads them, and the
`staff.subject` field (empty for all 89) duplicates what `subjects` already holds.
Read from `subjects`; do not populate `staff.subject`.

---

## 11. Database reality — counts and gaps

| Collection | Count | Note |
|---|---|---|
| students | 1,802 | school's list has **1,804** — 2 unaccounted |
| guardians | 3,604 | ≈2 per student |
| staff | 89 | school's teacher sheet has **83** — 6 more than supplied |
| users | 1,892 | vs **1,898** `auth_users` — 6 logins with no user |
| classes | 48 | matches the class-teacher sheet |
| subjects | 293 | populated |
| period_links | 293 | populated |
| houses | 4 | populated, unassigned |
| fee_transactions | **1** | effectively unused |
| academic_years | 2 | |

### Always-empty fields

- **students:** `dob`, `gender`, `blood_group`, `admission_date`, `house`, `route_id`
- **staff:** `subject`, `salary`, `email`, `address`, `join_date`; `department` 1 of 89

### Role / designation reality

```
staff_type:    teacher 88 · admin 1
designation:   Class Teacher 49 · Teacher 39 · Principal 1     <- populated, never displayed
role/sub_cat:  student/(blank) 1802 · teacher/class_teacher 49
               teacher/subject_teacher 39 · owner/(blank) 1 · admin/principal 1
```

`designation` already holds a readable label. The Staff Tracker shows
`role / sub_category` instead — the sole cause of the "teacher / subject_teacher"
column the owner objected to.

### Classes are stored unsorted

`11th-A, 1st-A, 2nd-C, 2nd-E, 3rd-A, 3rd-B, 4th-B, 5th-B, 6th-B, 7th-C, LKG-A, NUR-D, …`

Correct order for every dropdown in the app:
**NUR → LKG → UKG → 1st … 12th**, then section A→E.

---

## 11b. ⚠️ The DETAINEES workbook is LAST YEAR'S data (FY 2025-26)

Confirmed by the owner, 2026-07-22. This governs how it may be used.

**Safe to carry forward** — these do not change with the session:
`Dob` · `gender` · `Father Name` · `Mother Name` · `Adm.Date` · `ADM NO` · `Address`
(`House` is very likely stable but should be confirmed with the school before loading.)

**MUST NOT be used to set anything current:**
- The `CLASS` column is the **2025-26** class. Every continuing student has since been
  promoted, so writing it would roll the whole school back a year.
- Current class/section comes from `Students-22-06-2026-02-35-08.xlsx` (exported
  22 Jun 2026, i.e. the 2026-27 session) or from the live database, never from this file.
- Anything loaded from it must be recorded with provenance
  `source: detainees_list_2025_26` so it is never mistaken for current-year data.

The same workbook also holds **PROMOTION LIST** sheets (`2-A`, `3A`, …) captioned
"Class- 1-A → 2-A PROMOTION LIST (2025-26)". These are the 2025-26 → 2026-27 promotion
mapping and can be used to *verify* the current class assignments rather than set them.

### Can the files actually be matched? — measured, not assumed

| Source | Rows | Matched to a live student by admission number |
|---|---|---|
| `Students-22-06-2026.xlsx` | 1,804 | **1,802 (99%)** — 2 unmatched: `19968`, `211309` |
| `DETAINEES → StudentData` | 1,743 | **1,551 (88%)** — 192 unmatched |
| Overlap between the two files | — | 1,553 shared admission numbers |

- **Admission number is a valid join key.** The database carries both numbering
  series — older `15xxx` and newer `25xxxx` — and they line up across all sources.
- The 192 unmatched detainees rows are consistent with students who left or were
  not promoted; expected for last year's list, not a data fault.
- **Name is NOT a safe key**: only 79% of detainee names match, and **114 live student
  names are duplicated**. Join on admission number only.

---

## 12. Consequences for the build

**Track 1 (UI, no writes) can use immediately:**
- `designation` instead of `role / sub_category` in the staff table
- the `subjects` collection to show what each teacher teaches
- the class ordering rule above, applied to every class dropdown
- empty-state text that says "not recorded" rather than showing a bare dash,
  since we now know these fields were never filled rather than genuinely blank

**Track 2 (data load, needs approval) covers:**
1. Student D.O.B., gender, house, admission date — from `DETAINEES LIST → StudentData`,
   **FY2025-26 data**, joined on admission number only, expected coverage ~1,551 of
   1,802 students (88%). Class/section from this file must be ignored — see §11b.
2. Transport routes and rates — from the transport photo (~250 points)
3. Fee structure 2026-27 — from the fee photo
4. Class-teacher assignments — from the class-teacher photo
5. Reconciling the 1,802 vs 1,804 students, 89 vs 83 staff, 1,892 vs 1,898 logins

**New fields/features the paper forms imply, not yet scoped:**
Aadhar (×3), PEN/UDISE, APAAR ID + consent, previous school, registration number,
admission document checklist, age-limit validation, sibling concession,
late fine and strike-off rules, Special and Without-Pay leave types.
