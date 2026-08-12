"""Release 2, step 4 - the school bus: routes, rates, riders, and eleven months.

--------------------------------------------------------------------------------
The contradiction this fixes
--------------------------------------------------------------------------------

**The platform says not one of its students uses the bus.** The school's payment ledger
shows **1,235 children paying for it** between January and August, across 5,587 monthly
charges. One of those two is wrong, and it is the platform.

``transport_routes`` is also completely empty, so there was nowhere to record a route even
if somebody had wanted to.

--------------------------------------------------------------------------------
Where the routes and rates come from
--------------------------------------------------------------------------------

Step 1 found these, and the finding changed the plan (see
``step-1-fee-document-reconciliation-2026-08-11.md``):

* **The transport PDF is NOT a rate card.** The finishing plan called it "exactly the
  missing transport rate card". It is 22 pages of per-route collection totals and carries
  no monthly rate for any route. What it gives is confirmation of the route list.
* **The rate card is in ``Students-06-08-2026-12-08-00.xlsx``**, in two columns nobody had
  opened: ``Transport`` and ``TransportFees``. The first reads like ``8( - JOYA)``, a
  route number and the stop the child is picked up from. The second is that child's
  **annual** charge.

--------------------------------------------------------------------------------
Eleven months, not twelve. June is not charged
--------------------------------------------------------------------------------

The school closes for the summer and the buses do not run, though staff are still paid and
the school fee is still charged for that quarter.

**Proved twice over, from two different documents:**

* The ledger holds transport lines for eleven months. **There is not one June line in
  5,587 rows.** June is the only month in the year with none at all.
* **97% of the annual figures in the student export divide exactly by eleven.** The 42
  that do not are small odd amounts, which is what a child billed for only part of the
  year looks like.

So the monthly rate is the annual figure divided by **11**, and each route records
``billed_months`` explicitly rather than leaving the reader to remember the exception.

--------------------------------------------------------------------------------
What this writes
--------------------------------------------------------------------------------

1. **The routes**, one per route number, each carrying its stops and the monthly rate at
   each stop.
2. **The riders**: ``uses_transport``, ``bus_route``, ``route_zone_id`` and the monthly
   fare on each child who has a route named in the school's export.

**Transport carries no concession of any kind** (fee rules document, section 3) and that
is why no discount field is written here. It **is** fined, because it sits inside the
total before the fine is worked out, which is step 9's problem and not this one.

A child whose annual figure does not divide by eleven gets their route and their flag, but
**no monthly rate**, because the rate cannot be honestly derived from a part-year figure.
They are listed by admission number every time this runs.

--------------------------------------------------------------------------------
How to run it
--------------------------------------------------------------------------------

::

    backend/.venv/Scripts/python.exe backend/migrations/036_transport_routes_and_riders.py
    ... 036_transport_routes_and_riders.py --apply
    ... 036_transport_routes_and_riders.py --rollback <file it saved>

Never run this through ``run_all.py``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Dict, List

SCHOOL_ID = "aaryans-joya"

# The school year for the bus. June is missing on purpose and is the whole point.
BILLED_MONTHS = ["April", "May", "July", "August", "September", "October",
                 "November", "December", "January", "February", "March"]
MONTHS_BILLED = len(BILLED_MONTHS)  # 11

STUDENT_EXPORT = "Students-06-08-2026-12-08-00.xlsx"


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def parse_route_label(raw: str) -> tuple[str, str]:
    """``'8( - JOYA)'`` -> ``('8', 'JOYA')``: a route number and the child's stop.

    Three labels in the school's export have **no route number at all** -
    ``( - SINORA)``, ``( - JAMA PUR)`` and ``( - MOHANPUR)``. Those return an empty
    route and a real stop. The child still gets their flag, their stop and their rate;
    what they do not get is a route they were never put on. Inventing one would be a
    guess about which bus a child rides, and the school is the only place that knows.
    They are listed by admission number every time this runs.

    Returns ``(None, None)`` only when the label cannot be read at all, which blocks
    the whole migration rather than losing a child quietly.
    """
    match = re.match(r"^(.*?)\((.*?)\s*-\s*(.*)\)$", str(raw).strip())
    if not match:
        return None, None
    route = (match.group(1).strip() or match.group(2).strip())
    stop = match.group(3).strip()
    if not stop:
        return None, None
    return route, stop


def read_riders() -> dict:
    """admission number -> {route, stop, annual, monthly}. Reads a spreadsheet only."""
    import openpyxl

    path = os.path.join(_repo_root(), "aaryans_database", STUDENT_EXPORT)
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = list(wb.active.iter_rows(values_only=True))
    wb.close()
    idx = {c: i for i, c in enumerate(rows[0]) if c}

    # Column 0 is `SID`, the PREVIOUS system's internal id, not an admission number.
    # Keying on it matched zero students out of 1,375 and the migration refused to run.
    # `AdmissionNo` is the column the platform's `admission_number` actually holds.
    riders, unreadable = {}, []
    for row in rows[1:]:
        if not row:
            continue
        admission = row[idx["AdmissionNo"]]
        if admission in (None, ""):
            continue
        raw = row[idx["Transport"]]
        if raw in (None, "", "N/A"):
            continue
        route, stop = parse_route_label(raw)
        if stop is None:
            unreadable.append(str(raw))
            continue
        annual = row[idx["TransportFees"]]
        annual = int(annual) if isinstance(annual, (int, float)) and annual else 0
        # Only a figure that divides cleanly by eleven is a rate. A part-year figure is
        # not, and dividing it anyway would invent a number.
        monthly = 0
        if annual and abs(annual / MONTHS_BILLED - round(annual / MONTHS_BILLED)) < 1e-9:
            monthly = int(round(annual / MONTHS_BILLED))
        riders[str(admission).strip()] = {
            "route": route, "stop": stop, "annual": annual, "monthly": monthly,
        }
    return {"riders": riders, "unreadable": unreadable}


async def plan(db) -> dict:
    read = read_riders()
    riders = read["riders"]

    # ── the routes, built up from the stops children are picked up at ────────────
    stops_by_route: Dict[str, Dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    for row in riders.values():
        if not row["route"]:
            continue  # no route number on the label; see parse_route_label
        if row["monthly"]:
            stops_by_route[row["route"]][row["stop"]][row["monthly"]] += 1
        else:
            stops_by_route[row["route"]].setdefault(row["stop"], Counter())

    existing_routes = await db.transport_routes.find(
        {"schoolId": SCHOOL_ID}, {"_id": 0, "id": 1, "route_name": 1}
    ).to_list(500)
    have = {r.get("route_name") for r in existing_routes}

    now = datetime.now(timezone.utc).isoformat()
    new_routes = []
    for route_name in sorted(stops_by_route, key=lambda r: (not r.isdigit(), r.zfill(4))):
        if route_name in have:
            continue
        stops = []
        for stop_name, rates in sorted(stops_by_route[route_name].items()):
            # Where one stop shows more than one rate, the commonest is the stop's rate
            # and every rate seen is kept on the record rather than thrown away.
            fare = rates.most_common(1)[0][0] if rates else 0
            stops.append({
                "name": stop_name,
                "monthly_fare": fare,
                "annual_fare": fare * MONTHS_BILLED,
                "other_rates_seen": sorted(r for r in rates if r != fare),
            })
        fares = [s["monthly_fare"] for s in stops if s["monthly_fare"]]
        new_routes.append({
            "id": str(uuid.uuid4()),
            "schoolId": SCHOOL_ID,
            "route_name": route_name,
            "start_point": "The Aaryans, Joya",
            "end_point": stops[-1]["name"] if stops else "",
            "stops": stops,
            "driver_name": "", "driver_phone": "", "vehicle_no": "", "capacity": "",
            "fare": min(fares) if fares else 0,
            "billed_months": list(BILLED_MONTHS),
            "months_billed_per_year": MONTHS_BILLED,
            "not_billed_months": ["June"],
            "billing_note": (
                "Eleven months. June is not charged: the school closes for the summer and "
                "the buses do not run. Confirmed by the school's payment ledger, which "
                "holds no June transport line in 5,587 rows."
            ),
            "concessions": "none",
            "concession_note": (
                "Transport carries no concession of any kind - no sibling discount, no "
                "employee discount, no 5% for paying the year up front. It IS fined, "
                "because it sits inside the total before the fine is worked out."
            ),
            "is_active": True,
            "source": f"{STUDENT_EXPORT}, Transport and TransportFees columns",
            "created_at": now,
        })

    # ── the riders ───────────────────────────────────────────────────────────────
    students = await db.students.find(
        {"schoolId": SCHOOL_ID},
        {"_id": 0, "id": 1, "admission_number": 1, "uses_transport": 1,
         "bus_route": 1, "route_zone_id": 1, "transport_opted": 1},
    ).to_list(3000)

    route_id_by_name = {r["route_name"]: r["id"] for r in new_routes}
    for r in existing_routes:
        route_id_by_name.setdefault(r.get("route_name"), r.get("id"))

    rider_changes, no_rate, no_route, not_on_platform = [], [], [], 0
    matched = set()
    for s in students:
        adm = str(s.get("admission_number") or "").strip()
        row = riders.get(adm)
        if not row:
            continue
        matched.add(adm)
        if not row["monthly"]:
            no_rate.append({"admission_number": adm, "annual": row["annual"]})
        if not row["route"]:
            no_route.append({"admission_number": adm, "stop": row["stop"]})
        rider_changes.append({
            "id": s["id"],
            "admission_number": adm,
            "before": {
                "uses_transport": s.get("uses_transport"),
                "transport_opted": s.get("transport_opted"),
                "bus_route": s.get("bus_route"),
                "route_zone_id": s.get("route_zone_id"),
            },
            "after": {
                "uses_transport": True,
                "transport_opted": True,
                "bus_route": f"{row['route']} - {row['stop']}" if row["route"] else row["stop"],
                "route_zone_id": route_id_by_name.get(row["route"], ""),
                "transport_stop": row["stop"],
                "transport_monthly_fare": row["monthly"],
                "transport_annual_fare": row["monthly"] * MONTHS_BILLED,
            },
        })
    not_on_platform = len(set(riders) - matched)

    already_flagged = sum(1 for s in students if s.get("uses_transport"))

    return {
        "students_on_platform": len(students),
        "already_marked_as_riders": already_flagged,
        "routes_existing": len(existing_routes),
        "new_routes": new_routes,
        "rider_changes": rider_changes,
        "no_rate": no_rate,
        "no_route": no_route,
        "riders_in_export": len(riders),
        "riders_not_on_platform": not_on_platform,
        "unreadable_labels": read["unreadable"],
    }


async def apply(db, *, dry_run: bool = True) -> dict:
    result = await plan(db)
    if result["unreadable_labels"]:
        result["blocked_by"] = [
            f"{len(result['unreadable_labels'])} transport labels could not be read, so "
            "some children would silently get no route. Fix the parser first."
        ]
        return result

    result["rollback"] = {
        "route_ids": [r["id"] for r in result["new_routes"]],
        "students": [{"id": c["id"], "before": c["before"]} for c in result["rider_changes"]],
    }
    if dry_run:
        return result

    for route in result["new_routes"]:
        await db.transport_routes.insert_one({**route, "_id": route["id"]})
    for change in result["rider_changes"]:
        await db.students.update_one(
            {"schoolId": SCHOOL_ID, "id": change["id"]}, {"$set": change["after"]}
        )
    result["applied"] = True
    return result


async def rollback_from(db, path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        saved = json.load(handle)
    deleted = await db.transport_routes.delete_many(
        {"schoolId": SCHOOL_ID, "id": {"$in": saved["route_ids"]}}
    )
    for row in saved["students"]:
        restore = {k: v for k, v in row["before"].items() if v is not None}
        unset = {k: "" for k, v in row["before"].items() if v is None}
        unset.update({"transport_stop": "", "transport_monthly_fare": "",
                      "transport_annual_fare": ""})
        update = {}
        if restore:
            update["$set"] = restore
        if unset:
            update["$unset"] = unset
        if update:
            await db.students.update_one({"schoolId": SCHOOL_ID, "id": row["id"]}, update)
    return {"routes_deleted": deleted.deleted_count, "students_restored": len(saved["students"])}


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Release 2 step 4: transport.")
    parser.add_argument("--apply", action="store_true", help="actually write. Default is a dry run.")
    parser.add_argument("--rollback", help="path to a rollback file from a previous --apply")
    args = parser.parse_args()

    root = _repo_root()
    sys.path.insert(0, os.path.join(root, "backend"))
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(root, "backend", ".env"))
    except ImportError:
        pass
    from database import connect_db, get_db

    await connect_db()
    db = get_db()

    if args.rollback:
        out = await rollback_from(db, args.rollback)
        print(f"deleted {out['routes_deleted']} routes, restored {out['students_restored']} students")
        return 0

    result = await apply(db, dry_run=not args.apply)

    print(f"  students on the platform                 {result['students_on_platform']:>5}")
    print(f"  ... currently marked as using the bus    {result['already_marked_as_riders']:>5}   <-- the contradiction")
    print(f"  children with a route in the export      {result['riders_in_export']:>5}")
    print(f"  ... matched to a student on the platform {len(result['rider_changes']):>5}")
    print(f"  ... in the export but not on the platform{result['riders_not_on_platform']:>5}")
    print()
    print(f"  transport routes already there           {result['routes_existing']:>5}")
    print(f"  routes to create                         {len(result['new_routes']):>5}")
    stops = sum(len(r["stops"]) for r in result["new_routes"])
    print(f"  stops across those routes                {stops:>5}")
    print(f"  billed months per year                   {MONTHS_BILLED:>5}   (June excluded)")

    rates = sorted({s["monthly_fare"] for r in result["new_routes"] for s in r["stops"] if s["monthly_fare"]})
    if rates:
        print(f"  monthly rates                            {len(rates):>5}   from {min(rates):,} to {max(rates):,}")

    if result["no_route"]:
        print(f"\n  {len(result['no_route'])} children have a stop but NO route number in the")
        print("  school's export. They get their flag, their stop and their rate; they do")
        print("  NOT get a route, because inventing one is a guess about which bus a child")
        print("  rides. The school needs to assign these:")
        for row in result["no_route"]:
            print(f"    admission {row['admission_number']}  stop {row['stop']}")

    if result["no_rate"]:
        print(f"\n  {len(result['no_rate'])} children get a route and a flag but NO monthly rate:")
        print("  their annual figure does not divide by eleven, so it is a part-year")
        print("  amount and a rate cannot be honestly derived from it.")
        for row in result["no_rate"][:12]:
            print(f"    admission {row['admission_number']}  annual {row['annual']:,}")
        if len(result["no_rate"]) > 12:
            print(f"    ... and {len(result['no_rate']) - 12} more")

    if result.get("blocked_by"):
        print("\nNOTHING WAS CHANGED.")
        for b in result["blocked_by"]:
            print(f"  {b}")
        return 1

    if not args.apply:
        print("\nDry run. Nothing was changed. Re-run with --apply when you mean it.")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = os.path.join(os.path.dirname(root), f"rollback-036-transport-{stamp}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(result["rollback"], handle, indent=2)
    print(f"\nDone. Rollback saved OUTSIDE the repository at:\n  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
