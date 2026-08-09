# Handoff prompt — paste this into a fresh session

---

You are continuing the Aaryans data transfer onto EduFlow. Read these first, in order —
they contain every decision and trap already found, and re-deriving them wastes a session:

1. `_bmad-output/planning-artifacts/data-load-anomalies-2026-08-06.md` — every anomaly, sections A–K
2. `aaryans_database/QUESTIONS-DETAIL-with-names-2026-08-06.md` — the name-level record list (gitignored, has pupil names)
3. `_bmad-output/QUESTIONS-FOR-THE-AARYANS-2026-08-06.md` — the name-free version sent to the school
4. `scripts/import_aaryans_*.py` and `scripts/migrate_photos_to_s3.py` — all dry-run by default

## How to connect

The live MongoDB Atlas connection is in `backend/.env` (`MONGO_URL`, `DB_NAME=eduflow`,
`SCHOOL_ID=aaryans-joya`). Python 3.8 on this Mac cannot load the test conftest — build a
venv from `/usr/local/opt/python@3.14/bin/python3.14` and `pip install -r backend/requirements.txt`.
**Mongo needs `tlsCAFile=certifi.where()`** or every connection fails with an SSL error.

AWS: use the `*_HOSTING` keys in the repo `.env` (IAM user `claude-hosting`).

## Non-negotiable rules, all learned the hard way

- **Match students on ADMISSION NUMBER only, never on name.** A name match writes one
  child's details onto another.
- **Never overwrite** — fill blanks only, and report what would have overwritten.
- **Never delete.** People missing from an export are listed, never removed.
- **Dry-run first, show the user, then apply.** Write a rollback manifest before writing.
- **Fill-blanks-only makes a load resumable** — this saved two jobs that timed out mid-run.
- **Print counts, never values.** Children's PII must not enter the transcript. Have scripts
  write names straight to a gitignored file instead.
- `aaryans_database/` is gitignored — pupil names go there, never into `_bmad-output/`.
- **Check spreadsheet cells for HYPERLINKS before writing a column off as junk.** The photo
  column looked like the literal word "View"; the link target was the real photograph.
  `load_workbook(path, data_only=True)` **without** `read_only=True` exposes `cell.hyperlink.target`.

## Already done and verified (do not redo)

1,872 students · 3,725 guardians (255 with photos) · 1,692 photographs copied to
`s3://eduflow-files-ap-south-1-210447603820/aaryans-joya/uploads/` · 43 carried-over fields
now editable · 9 office staff · 5 master lists (payment modes, mediums, categories,
religions, document types). Backend suite: 2,364 passed / 0 failed.

---

# THE WORK TO DO

## A. Two bugs the owner reported

**A1. Student houses show "not recorded" for everyone.** The 4 houses exist (Agamya, Agrim,
Aprajit, Atulya) but no student is assigned to one. Confirmed NOT caused by our loads (they
only fill blanks) — the export's `HouseBlock` column is empty for all 1,878 rows, and
migration `002_add_houses` was marked applied **without being run**. The owner believes
houses were assigned previously. **Investigate where that assignment lives** (check
migration 002, any older backup/export) and restore it. Do not invent assignments.

**A2. Parent photos don't appear on the child's profile.** The data is correct — 255 photos
are on the guardian records (`guardians.photo_url`). The child's profile screen simply does
not render them. **Frontend work**, not a data fix.

## B. New files the owner added to `aaryans_database/`

- **Two more fee-structure reports covering TRANSPORT fees** — read and reconcile
- **A list of enquiry-form leads** — import to the platform (there is an `enquiries`
  collection and a CRM: `crm_activities`, `crm_opportunities`, `admission_applications`)

## C. Corrections to `QUESTIONS-DETAIL-with-names-2026-08-06.md` (owner's numbered replies)

1. **Keep Dipanshu** as a pointer in the file, but **remove every other entry named "Adesh
   Singh"** — that is the PRINCIPAL's name, added as a test student account by mistake.
2. **The 30 students with no admission number FAILED the admission test and were rejected.**
   Safe to remove them from the file entirely. (This supersedes the earlier "they are
   enquiries, load them when they take admission".)
3. **Add all 28 students** (on platform, absent from the export) **to the NSO list.**
4. **Of the 23 staff:** add the **first 22 to the NSO list**; the **last one, Yachika**, is a
   NEW joiner whose data was never updated on Vedmarg — add her to the TEACHERS list.
5. **Add the 12 teachers** from the export to the EduFlow teacher list — they are new
   additions. **(Yachika appears in both 4 and 5 — deduplicate, do not create her twice.)**
6. **Recheck section 5** ("records where your file differs") — several entries have identical
   information but are reported as different. Find the comparison fault.
7. **The three impossible dates: set the year to 2021** in all three.
8. **The 4 in "12TH PASS OUT OLD DUE 25-26": KEEP them in the database.** They passed 12th but
   have not paid their fees and have not collected their marksheets. Add a proper **remark**
   explaining this, and set **financial year 2025-26**.
9. **The 136 fee-only students:** if they appear in the provided Excel list, add them as they
   are; otherwise leave them recorded in the file.
10. **Keep the 9 office staff** in the file.
11. **Make Chaman Singh the Transport Head** of the school.

> Note: the owner's list ran 1–10 but contained eleven instructions; the numbering above is
> corrected. Confirm 8/9 against the original message if anything reads ambiguously.

## D. Load everything not yet on the platform

The owner's standing instruction: *"you have so much data but still haven't added a lot of
it — please add them at the correct place as they should be."* Work through the anomalies
file and place remaining data where it belongs. **Keep the discipline: load what is
unambiguous, record what is not, never guess.**

## E. Still open from before

- **Switch photo SERVING to our own S3.** Files are copied, but `photo_url` still points at
  `cdn.vedmarg.com`, so **1,427 children's photographs remain publicly viewable by anyone
  with the link**. Needs a `file_uploads` record per image so `routes/upload.py:serve_file`
  can authorise and presign. **Highest-priority open item — real privacy consequence.**
- **`Ledger-Report-06-08-2026-01-03.xlsx`** is still only in the Google Drive folder
  "Vedmarg Data" — it must be copied into `aaryans_database/` by hand (too large to pull
  through a chat session). It holds the real payment transactions with dates and modes.

## F. Explicitly PAUSED by the owner — do not action without them raising it

- **Tightening the S3 IAM policy.** `claude-hosting` currently has FULL S3 access; it can
  read the CockRoach database backups and the CloudTrail audit logs. A scoped replacement is
  ready at `docs/iam-policy-claude-hosting-s3-photos.json`. Parked deliberately, not forgotten.
- **The 23 teachers** question (superseded in part by C4 above).
- **The fee ledger.** Three of the school's own exports disagree on total billed by up to
  **₹81 lakh** (₹8.69cr vs ₹7.88cr vs the school's own ₹8.02cr). Nothing may be written until
  the school says which students make up their ₹8.02 crore. See anomaly K5.

---

**Report back in plain, non-technical language** — the owner relays these to school staff.
Be just as direct about failures and risks, only in everyday words.
