"""
Apply the owner's numbered corrections that touch the DATABASE (2026-08-06).

Corrections 1, 2, 9 and 10 change only the question document, not the platform, and are
made there. The three handled here are:

  3.  The 28 children who are on EduFlow but absent from the school's new export go on
      the NSO list — off the roll, but STILL on the daily register, because that is
      exactly what NSO means at this school (see services/enrolment_status.py). A
      teacher keeps marking them, which is how the school notices if one walks back in.
      They are NOT deleted and NOT marked as having left.

  7.  The three impossible dates ("17 Apr, 0021" twice and "12 Apr, 0212") are set to
      the year 2021. They were left blank on the original load rather than guessed; the
      owner has now supplied the year.

  8.  The 4 children in the class "12TH PASS OUT OLD DUE 25-26" are KEPT. They passed
      12th but have not paid their fees and have not collected their marksheets. They
      were never created (anomaly A3) precisely because putting them on a live class
      list would have overstated the roll. They are created here as TC_ISSUED — off the
      roll AND off the daily register — so no head count, class list or attendance
      register picks them up, while the record and the debt still exist. Each carries a
      plain-English remark saying why, and financial year 2025-26.

  Correction 11 (Chaman Singh = Transport Head) needed no change: he was already
  created with sub_category `transport_head`. Verified, not re-written.

RULES OBSERVED: match on admission number only; never delete; fill blanks only where a
value already exists; dry-run by default; rollback manifest before any write.

Usage:
    python scripts/apply_owner_corrections_2026_08_06.py            # dry run
    python scripts/apply_owner_corrections_2026_08_06.py --apply
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import certifi
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / "backend" / ".env")
sys.path.insert(0, str(ROOT / "backend"))

SCHOOL_ID = os.environ.get("SCHOOL_ID", "aaryans-joya")
BRANCH_ID = "branch-joya"
ACADEMIC_YEAR_ID = "ay-2025-26"

NSO = "nso"
TC_ISSUED = "tc_issued"


def fields_for(state: str) -> dict:
    """Mirror of services/enrolment_status.fields_for — is_active and status, together."""
    return {"is_active": state == "active", "status": state}


# ---------------------------------------------------------------------------------
# WHERE THE PUPIL-IDENTIFYING INPUTS LIVE, AND WHY THEY ARE NOT IN THIS FILE
#
# This script needs 28 admission numbers (correction 3), 4 children's names
# (correction 8), and 3 admission-number/date-of-birth pairs (correction 7). None of it
# may sit in the code repository: the standing rule on this data transfer is that no
# child's name, number or date enters git, which is why `aaryans_database/` is gitignored
# and why every other loader in this folder prints counts rather than values. Embedding
# any of it here would have quietly broken that.
#
# So it is all read from `aaryans_database/_owner_corrections_input.json`, which stays
# beside the school's other confidential files. The script fails loudly if it is missing
# rather than silently doing nothing.
# ---------------------------------------------------------------------------------
INPUT_FILE = ROOT / "aaryans_database" / "_owner_corrections_input.json"


def load_inputs() -> tuple[list[str], list[dict], list[tuple]]:
    if not INPUT_FILE.exists():
        raise SystemExit(
            f"ERROR: required input file not found: {INPUT_FILE}\n"
            "It holds the admission numbers, names and dates for corrections 3, 7 and 8\n"
            "and is kept out of git on purpose. Restore it from the school's data folder."
        )
    data = json.loads(INPUT_FILE.read_text())
    date_fixes = [(d["admission_number"], d["field"], d["value"]) for d in data["date_fixes"]]
    return data["nso_admission_numbers"], data["passed_out_12th"], date_fixes

REMARK = ("Passed class 12 in the 2025-26 session. Fees are still outstanding and the "
          "marksheet has not been collected. Kept on the platform deliberately so the "
          "debt stays visible; off the roll and off the daily register, so this record "
          "is not counted in any class list, head count or attendance register.")


async def main(apply: bool) -> int:
    NSO_ADMISSIONS, PASSED_OUT, DATE_FIXES = load_inputs()
    client = AsyncIOMotorClient(os.environ["MONGO_URL"], tlsCAFile=certifi.where(), retryWrites=True)
    db = client[os.environ["DB_NAME"]]
    now = datetime.now(timezone.utc).isoformat()
    try:
        print("=" * 68)
        print("OWNER CORRECTIONS 3, 7, 8 — 2026-08-06")
        print("=" * 68)

        # ---- 3. NSO -------------------------------------------------------------
        found_nso, already_nso, missing_nso = [], 0, 0
        for a in NSO_ADMISSIONS:
            s = await db.students.find_one(
                {"schoolId": SCHOOL_ID, "admission_number": a},
                {"_id": 0, "id": 1, "status": 1, "is_active": 1})
            if not s:
                missing_nso += 1
                continue
            if s.get("status") == NSO:
                already_nso += 1
                continue
            found_nso.append((s["id"], s.get("status"), s.get("is_active")))
        print(f"\n3. NSO list")
        print(f"   admission numbers given      : {len(NSO_ADMISSIONS)}")
        print(f"   found and would change       : {len(found_nso)}")
        print(f"   already NSO                  : {already_nso}")
        print(f"   not found on the platform    : {missing_nso}")

        # ---- 7. dates -----------------------------------------------------------
        date_todo, date_occupied, date_missing = [], [], 0
        for a, f, v in DATE_FIXES:
            s = await db.students.find_one({"schoolId": SCHOOL_ID, "admission_number": a},
                                           {"_id": 0, "id": 1, f: 1})
            if not s:
                date_missing += 1
                continue
            if s.get(f):
                # never overwrite: if something is already there, report instead
                date_occupied.append((a, f, s.get(f), v))
            else:
                date_todo.append((s["id"], f, v))
        print(f"\n7. impossible dates -> 2021")
        print(f"   blank and would be filled    : {len(date_todo)}")
        print(f"   already hold a value (kept)  : {len(date_occupied)}")
        print(f"   student not found            : {date_missing}")

        # ---- 8. the four who passed out -----------------------------------------
        po_create, po_exists = [], 0
        for p in PASSED_OUT:
            s = await db.students.find_one(
                {"schoolId": SCHOOL_ID, "admission_number": p["admission_number"]}, {"_id": 0, "id": 1})
            if s:
                po_exists += 1
            else:
                po_create.append(p)
        classes = {}
        for sec in ("A", "B"):
            c = await db.classes.find_one({"schoolId": SCHOOL_ID, "name": "12th", "section": sec},
                                          {"_id": 0, "id": 1})
            classes[sec] = c["id"] if c else None
        print(f"\n8. '12TH PASS OUT OLD DUE 25-26'")
        print(f"   would create                 : {len(po_create)}")
        print(f"   already on the platform      : {po_exists}")
        print(f"   class ids resolved           : {classes}")
        if any(v is None for v in classes.values()):
            print("   ABORT: could not resolve a 12th class — refusing to create orphan records.")
            return 1
        print(f"   they are created OFF the roll and OFF the register (status={TC_ISSUED})")

        if not apply:
            print("\nDRY RUN — nothing written. Re-run with --apply to write.")
            return 0

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        manifest = ROOT / "aaryans_database" / f"_rollback_corrections_{stamp}.json"
        new_ids = [str(uuid.uuid4()) for _ in po_create]
        manifest.write_text(json.dumps({
            "script": Path(__file__).name, "written_at": stamp,
            "nso_students": [{"id": i, "previous_status": st, "previous_is_active": ia}
                             for i, st, ia in found_nso],
            "date_fills": [{"id": i, "field": f, "written": v, "previous": None}
                           for i, f, v in date_todo],
            "created_student_ids": new_ids,
            "note": ("Roll back: restore previous_status/previous_is_active on nso_students; "
                     "unset the named field on date_fills; delete created_student_ids."),
        }, indent=1))
        print(f"\nrollback manifest -> {manifest.name}")

        n = 0
        for sid, _, _ in found_nso:
            r = await db.students.update_one(
                {"id": sid, "schoolId": SCHOOL_ID},
                {"$set": {**fields_for(NSO), "updated_at": now,
                          "nso_reason": "Absent from the school's 06 Aug 2026 export; "
                                        "school to confirm whether they have left."}})
            n += r.modified_count
        print(f"3. students moved to NSO       : {n}")

        d = 0
        for sid, f, v in date_todo:
            r = await db.students.update_one(
                {"id": sid, "schoolId": SCHOOL_ID, "$or": [{f: None}, {f: ""}, {f: {"$exists": False}}]},
                {"$set": {f: v, "updated_at": now}})
            d += r.modified_count
        print(f"7. dates filled                : {d}")

        docs = []
        for nid, p in zip(new_ids, po_create):
            docs.append({
                "id": nid, "_id": nid,
                "schoolId": SCHOOL_ID, "branch_id": BRANCH_ID,
                "academic_year_id": ACADEMIC_YEAR_ID,
                "class_id": classes[p["section"]],
                "admission_number": p["admission_number"],
                "name": p["name"],
                **fields_for(TC_ISSUED),
                "remark": REMARK,
                "financial_year": "2025-26",
                "outstanding_balance_at_import": p["balance"],
                "marksheet_withheld": True,
                "created_at": now,
                "source": "owner-correction-8-2026-08-06",
            })
        if docs:
            await db.students.insert_many(docs)
        print(f"8. passed-out records created  : {len(docs)}")

        total = await db.students.count_documents({"schoolId": SCHOOL_ID})
        on_roll = await db.students.count_documents({"schoolId": SCHOOL_ID, "is_active": True})
        on_register = await db.students.count_documents(
            {"schoolId": SCHOOL_ID, "$or": [{"is_active": True}, {"status": NSO}]})
        print(f"\nverify — student records total : {total}")
        print(f"        on the roll (head count): {on_roll}")
        print(f"        on the daily register   : {on_register}")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    sys.exit(asyncio.run(main(ap.parse_args().apply)))
