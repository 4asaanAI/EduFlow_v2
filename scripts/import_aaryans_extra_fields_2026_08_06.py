"""Load the remaining 71 student columns. DRY RUN BY DEFAULT.

    python scripts/import_aaryans_extra_fields_2026_08_06.py           # report only
    python scripts/import_aaryans_extra_fields_2026_08_06.py --apply   # writes

Third and last of the student loaders:
  1. `import_aaryans_2026_08_06.py`        - the 13 columns that already had a home
  2. `import_aaryans_photos_2026_08_06.py` - the photographs (hyperlink targets)
  3. this one                              - the other 71 columns

Abhimanyu, 2026-08-06: *"add those additional 71 columns over the platform and populate
the data in them as well"*. No Pydantic change is needed for these to be READABLE: the
students routes return raw Mongo documents rather than a `response_model`, so extra keys
flow straight through the API. They are NOT yet editable in the UI or via PATCH - that
needs `UPDATABLE_FIELDS` and form work, recorded as a follow-up.

NAME MAP: mostly automatic snake_case, but four names were changed by hand because the
automatic one was wrong or dangerous:

  * `CreatedAt` -> `source_created_at`, NOT `created_at`. **This one matters.** Every
    student document already has `created_at`, meaning "when this record was made on
    EduFlow". Writing the school's export date over it would destroy our own audit
    metadata on 1,878 records and there would be nothing to restore it from.
  * `SID` -> `source_sid` (the automatic snake_case gives the unreadable `s_i_d`), and
    `Username` -> `source_username`, `LastActive` -> `source_last_active`. These are
    identifiers belonging to the school's PREVIOUS system, not to EduFlow; the prefix
    keeps that obvious so nobody later mistakes `username` for a login on this platform.
  * `Type` -> `admission_type` (its values are `new`/`old`, nothing to do with a data type).

FEES are nested under `fee_snapshot` rather than written as loose top-level fields.
Deliberate: a proper fee ledger is being built from
`Students-Fees-Structure-Report-06-08-2026-12-49.xlsx`, and money living in two places
under similar names is how a platform ends up disagreeing with itself about what a family
owes. `fee_snapshot` is explicitly a point-in-time copy of what the school's export said
on 6 Aug 2026 - it is NOT the ledger and must never be totalled as if it were.

PARENT PHOTOS (`MotherPhoto`/`FatherPhoto`/`GuardianPhoto`) are relative paths in the
export; they are converted to absolute CDN URLs here and stored on the STUDENT record.
That partly closes anomaly C2 - the `guardians` collection still has no photo field, so
the photo sits beside the child rather than beside the parent.

Rules carried over and unchanged: never overwrite (only blank fields are filled), never
delete, blank in the export stays blank on the platform.

Confidentiality: counts only to the console. No value is ever printed.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import uuid
from collections import Counter
from pathlib import Path

import certifi
import openpyxl
from dotenv import load_dotenv
from pymongo import MongoClient

REPO = Path(__file__).resolve().parent.parent
load_dotenv(REPO / "backend" / ".env")
XLSX = REPO / "aaryans_database" / "Students-06-08-2026-12-08-00.xlsx"
SCHOOL_ID = os.environ.get("SCHOOL_ID", "aaryans-joya")
CDN_BASE = "https://cdn.vedmarg.com/"

# Already loaded by loader 1 or 2 - never touched again here.
ALREADY = {"Name", "AdmissionNo", "RollNo", "Dob", "Gender", "Address", "AdmissionDate",
           "Status", "Photo", "Class", "Section", "Mobile", "Transport"}

FEE_COLS = {"TransportFees", "SchoolTotalFees", "TotalDiscount", "GrossTotalFees",
            "Fine", "PaidFees", "Discount", "BalanceFees"}

PHOTO_COLS = {"MotherPhoto", "FatherPhoto", "GuardianPhoto"}

# Hand-checked overrides. See the module docstring for why each one exists.
RENAME = {
    "CreatedAt": "source_created_at",   # must NOT become created_at
    "SID": "source_sid",
    "Username": "source_username",
    "LastActive": "source_last_active",
    "Type": "admission_type",
    "AadharNo": "aadhaar_no",
    "MotherAadharNo": "mother_aadhaar_no",
    "FatherAadharNo": "father_aadhaar_no",
}

# Fields that must never be written by this script even if a column maps to them.
PROTECTED = {"id", "_id", "schoolId", "branch_id", "academic_year_id", "class_id",
             "created_at", "updated_at", "name", "admission_number", "roll_number",
             "status", "is_active", "photo_url", "user_id"}

YES_NO = {"yes": True, "no": False, "true": True, "false": False}


def snake(s: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", str(s)).lower().replace("__", "_")


def field_name(col: str) -> str:
    return RENAME.get(col, snake(col))


def coerce(col: str, v):
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    if col in PHOTO_COLS:
        return s if s.startswith("http") else CDN_BASE + s.lstrip("/")
    if col in FEE_COLS:
        try:
            return round(float(s.replace(",", "")), 2)
        except ValueError:
            return None
    low = s.lower()
    if low in YES_NO and col.startswith(("Is", "Has")) or col == "Dropout":
        return YES_NO.get(low, s)
    # Dates in this export are always '06 Aug, 2026' - a named month, no ambiguity.
    if col.endswith("Date") or col in ("TcDate",):
        try:
            return datetime.datetime.strptime(s, "%d %b, %Y").strftime("%Y-%m-%d")
        except ValueError:
            return s
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== {'APPLY (writing)' if args.apply else 'DRY RUN (nothing is written)'} ===\n")

    client = MongoClient(os.environ["MONGO_URL"], tlsCAFile=certifi.where(),
                         serverSelectionTimeoutMS=30000)
    db = client[os.environ["DB_NAME"]]

    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    ws = wb.active
    it = ws.iter_rows(values_only=True)
    hdr = list(next(it))
    ix = {h: i for i, h in enumerate(hdr)}
    rows = [r for r in it if any(c is not None for c in r)]
    wb.close()

    cols = []
    for h in hdr:
        if h in ALREADY or h is None:
            continue
        if not any(r[ix[h]] not in (None, "") for r in rows):
            continue          # entirely blank in this export
        fn = field_name(h)
        if fn in PROTECTED:
            print(f"  !! refusing to write column {h} -> protected field {fn}")
            continue
        cols.append(h)

    live = {}
    for d in db.students.find({"schoolId": SCHOOL_ID}, {"_id": 0}):
        a = str(d.get("admission_number") or "").strip().upper()
        if a:
            live[a] = d

    filled = Counter()
    skipped_existing = Counter()
    updates = []
    unmatched = 0
    for r in rows:
        adm = str(r[ix["AdmissionNo"]] or "").strip().upper()
        if adm.endswith(".0"):
            adm = adm[:-2]
        if not adm:
            continue
        doc = live.get(adm)
        if not doc:
            unmatched += 1
            continue
        upd, fee = {}, {}
        for h in cols:
            val = coerce(h, r[ix[h]])
            if val is None:
                continue
            if h in FEE_COLS:
                fee[field_name(h)] = val
                continue
            fn = field_name(h)
            if doc.get(fn) in (None, ""):
                upd[fn] = val
                filled[fn] += 1
            else:
                skipped_existing[fn] += 1
        if fee and not doc.get("fee_snapshot"):
            fee["as_of"] = "2026-08-06"
            fee["source"] = "Students-06-08-2026 export; NOT the fee ledger"
            upd["fee_snapshot"] = fee
            filled["fee_snapshot"] += 1
        if upd:
            upd["updated_at"] = datetime.datetime.now().isoformat()
            updates.append((doc["id"], upd))

    print(f"columns being imported            : {len(cols)}")
    print(f"students matched                  : {len(rows) - unmatched}")
    print(f"rows with no student on platform  : {unmatched}")
    print(f"students receiving >=1 new field  : {len(updates)}\n")
    print("VALUES TO BE WRITTEN, per field (blank-only):")
    for k, v in sorted(filled.items(), key=lambda x: -x[1]):
        print(f"   {k:30s} {v}")
    if skipped_existing:
        print("\nALREADY HELD A VALUE - left alone (never overwritten):")
        for k, v in sorted(skipped_existing.items(), key=lambda x: -x[1]):
            print(f"   {k:30s} {v}")

    if not args.apply:
        print("\n--- DRY RUN. Nothing was written. ---")
        client.close()
        return

    rb = Path(os.environ.get("ROLLBACK_DIR", Path.home())) / \
        f"aaryans_extrafields_rollback_{datetime.datetime.now():%Y%m%d_%H%M%S}.json"
    rb.write_text(json.dumps({
        "written_at": datetime.datetime.now().isoformat(),
        "undo": [{"id": i, "unset": [k for k in u if k != "updated_at"]} for i, u in updates],
    }, indent=1))
    print(f"\n  rollback manifest -> {rb}")

    n = 0
    for sid_, upd in updates:
        db.students.update_one({"id": sid_, "schoolId": SCHOOL_ID}, {"$set": upd})
        n += 1
        if n % 400 == 0:
            print(f"    {n}/{len(updates)}")
    print(f"  updated {n} students")

    db.audit_logs.insert_one({
        "id": str(uuid.uuid4()), "schoolId": SCHOOL_ID, "branch_id": "branch-joya",
        "action": "bulk_import", "collection": "students",
        "entity_id": "aaryans-extra-fields-2026-08-06",
        "changed_by": "layaa-ai-data-load", "changed_by_role": "system",
        "changes": {"columns": len(cols), "students_updated": n,
                    "fields_filled": dict(filled)},
        "created_at": datetime.datetime.now().isoformat(),
    })
    print("  wrote 1 audit entry")
    client.close()


if __name__ == "__main__":
    main()
