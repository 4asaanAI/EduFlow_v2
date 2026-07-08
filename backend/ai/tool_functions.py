"""
Tool functions executed when the LLM requests them.
Each function queries MongoDB and returns structured data.

Part 2 Patch P1 (tenancy): every v1 tool now accepts an optional ``scope``
argument and routes every Mongo read through ``_tenant_query`` (which
composes scope.branch_id with the env-canonical schoolId via
``tenant.scoped_query``). Tests that still call these tools with the
legacy two-arg signature get ``scope=None`` and therefore no branch
filter — acceptable for unit tests that already isolate their fake DB to a
single tenant. Production call sites in ``routes/chat.py`` always pass the
resolved Scope.
"""
from __future__ import annotations

from datetime import datetime, date, timedelta
from database import get_db
from tenant import scoped_query
from services.actor_context import actor_ctx_from_user
from services.leave_service import (
    decide_leave,
    LeaveValidationError,
    LeaveNotFoundError,
    LeaveConflictError,
)
import logging, re

from ai.redaction import _mask_phone  # canonical phone mask (first-2 + last-3)

logger = logging.getLogger(__name__)


def _env(data, *, message: str = "", count: int | None = None,
         success: bool = True, denied: bool = False) -> dict:
    """R4.2/M1: the one tool-result envelope, shared by every v1 tool.

    `data` holds the payload (a list for list-primary tools so `recall_history`
    and the extractors can read `data`/`meta.count` uniformly; a dict for the
    composite dashboards). `denied=True` marks an authorization refusal (never an
    empty success); `success=False` with `denied=False` marks an operation failure.
    """
    if count is None:
        count = len(data) if isinstance(data, (list, dict)) else (1 if data else 0)
    return {
        "success": success,
        "data": data,
        "meta": {"count": count},
        "message": message,
        "denied": denied,
    }


def _scope_branch_id(scope):
    """Return scope.branch_id whether scope is a Scope dataclass or a dict."""
    if scope is None:
        return None
    if isinstance(scope, dict):
        return scope.get("branch_id")
    return getattr(scope, "branch_id", None)


def _tenant_query(scope, base: dict | None = None) -> dict:
    """Compose ``base`` with the requester's branch_id and schoolId.

    This is the canonical helper used by every v1 tool. It deliberately
    does NOT call ``scope.filter()`` — that helper is collection-aware and
    would, for example, splice ``{"id": student_id}`` into a
    ``student_attendance`` query for a self-only student. v1 tools already
    hand-craft the right student/class restrictions; here we only need to
    bolt on the cross-cutting tenancy axes (branch_id + schoolId).

    Owner gets ``branch_id=None`` → no branch_id clause (cross-branch by
    design); every other role gets the JWT-derived branch_id.
    """
    return scoped_query(dict(base or {}), branch_id=_scope_branch_id(scope))


async def tool_get_school_pulse(params: dict, user: dict, scope=None) -> dict:
    db = get_db()
    today = date.today().strftime("%Y-%m-%d")
    week_ago = (date.today() - timedelta(days=7)).strftime("%Y-%m-%d")
    branch_id = _scope_branch_id(scope)

    total_students = await db.students.count_documents(_tenant_query(scope, {"is_active": True}))
    total_staff = await db.staff.count_documents(_tenant_query(scope, {"is_active": True}))

    # Student attendance today
    att_today = await db.student_attendance.find(_tenant_query(scope, {"date": today})).to_list(1000)
    total_marked = len(att_today)
    present = sum(1 for a in att_today if a.get("status") == "present")
    absent = sum(1 for a in att_today if a.get("status") == "absent")
    att_rate = round(present / total_marked * 100, 1) if total_marked > 0 else 0

    # Staff attendance today
    staff_att = await db.staff_attendance.find(_tenant_query(scope, {"date": today})).to_list(100)
    staff_absent = [a for a in staff_att if a.get("status") == "absent"]
    staff_absent_names = []
    for sa in staff_absent:
        st = await db.staff.find_one(_tenant_query(scope, {"id": sa.get("staff_id")}))
        if st:
            staff_absent_names.append(st.get("name", "Unknown"))

    # Fee stats — canonical formula (same as _fee_summary_payload + tool_get_fee_summary)
    fee_pipeline = [
        {"$match": _tenant_query(scope, {})},
        {
            "$group": {
                "_id": "$status",
                "total_amount": {"$sum": "$amount"},
                "total_paid_amount": {"$sum": {"$ifNull": ["$paid_amount", 0]}},
                "count": {"$sum": 1},
            }
        },
    ]
    fee_stats = await db.fee_transactions.aggregate(fee_pipeline).to_list(20)
    fd = {f["_id"]: f for f in fee_stats}

    def _fa(status: str) -> float:
        return float(fd.get(status, {}).get("total_amount", 0))

    def _fp(status: str) -> float:
        return float(fd.get(status, {}).get("total_paid_amount", 0))

    total_paid = _fa("paid") + _fp("partial")
    partial_remaining = max(0.0, _fa("partial") - _fp("partial"))
    total_outstanding = _fa("overdue") + _fa("pending") + _fa("unpaid") + partial_remaining

    # Pending leaves
    pending_leaves = await db.leave_requests.find(_tenant_query(scope, {"status": "pending"})).to_list(20)
    leave_details = []
    for lr in pending_leaves:
        staff = await db.staff.find_one(_tenant_query(scope, {"id": lr.get("staff_id")}))
        leave_details.append({
            "id": lr.get("id"),
            "staff_name": staff.get("name", "Unknown") if staff else "Unknown",
            "leave_type": lr.get("leave_type", ""),
            "start_date": lr.get("start_date", ""),
            "end_date": lr.get("end_date", ""),
            "reason": lr.get("reason", ""),
        })

    # Students absent 3+ consecutive days
    chronic_absent = []
    students_list = await db.students.find(_tenant_query(scope, {"is_active": True})).to_list(500)
    for st in students_list[:50]:  # limit for performance
        absent_count = 0
        check_date = date.today()
        for i in range(5):
            d = (check_date - timedelta(days=i)).strftime("%Y-%m-%d")
            rec = await db.student_attendance.find_one(_tenant_query(scope, {"student_id": st.get("id"), "date": d}))
            if rec and rec.get("status") == "absent":
                absent_count += 1
            else:
                break
        if absent_count >= 3:
            chronic_absent.append({"name": st.get("name", "Unknown"), "days": absent_count})

    fee_total_all = total_paid + total_outstanding
    fee_collection_rate = round(total_paid / fee_total_all * 100, 1) if fee_total_all > 0 else 0.0

    def fmt_amount(a):
        if a >= 100000:
            return f"₹{a/100000:.1f}L"
        elif a >= 1000:
            return f"₹{a/1000:.0f}K"
        return f"₹{a:,.0f}"

    return _env({
        "summary": {
            "total_students": total_students,
            "total_staff": total_staff,
            "attendance_rate": f"{att_rate}%",
            "present_today": present,
            "absent_today": absent,
            "fee_collected": fmt_amount(total_paid),
            "fee_overdue": fmt_amount(total_outstanding),
            "fee_collection_rate": f"{fee_collection_rate}%",
            "pending_leaves": len(pending_leaves),
        },
        "staff_absent_today": staff_absent_names,
        "pending_leave_requests": leave_details,
        "chronic_absent_students": chronic_absent,
        "fee_stats": {
            "paid": fmt_amount(total_paid),
            "overdue": fmt_amount(total_outstanding),
            "pending": fmt_amount(_fa("pending")),
            "collection_rate": f"{fee_collection_rate}%",
        }
    }, count=total_students)


async def tool_get_fee_summary(params: dict, user: dict, scope=None) -> dict:
    """Canonical fee summary — identical formula to _fee_summary_payload (REST API).

    collected   = SUM(amount WHERE paid) + SUM(paid_amount WHERE partial)
    outstanding = SUM(amount WHERE overdue/pending/unpaid) + SUM(amount-paid_amount WHERE partial)
    rate        = collected / (collected + outstanding) * 100
    defaulters  = all students with any outstanding balance (not only status='overdue')
    """
    db = get_db()
    today_dt = date.today()

    # 1. Aggregate stats by status (canonical — same pipeline as REST API)
    pipeline = [
        {"$match": _tenant_query(scope, {})},
        {
            "$group": {
                "_id": "$status",
                "total_amount": {"$sum": "$amount"},
                "total_paid_amount": {"$sum": {"$ifNull": ["$paid_amount", 0]}},
                "count": {"$sum": 1},
                "student_ids": {"$addToSet": "$student_id"},
            }
        },
    ]
    rows = await db.fee_transactions.aggregate(pipeline).to_list(20)
    s = {r["_id"]: r for r in rows}

    def _a(status: str) -> float:
        return float(s.get(status, {}).get("total_amount", 0))

    def _p(status: str) -> float:
        return float(s.get(status, {}).get("total_paid_amount", 0))

    def _sids(status: str) -> set:
        return {sid for sid in s.get(status, {}).get("student_ids", []) if sid}

    total_collected = _a("paid") + _p("partial")
    partial_remaining = max(0.0, _a("partial") - _p("partial"))
    total_outstanding = _a("overdue") + _a("pending") + _a("unpaid") + partial_remaining
    total_all = total_collected + total_outstanding
    collection_rate = round(total_collected / total_all * 100, 1) if total_all > 0 else 0.0

    # 2. All outstanding transactions for defaulters list (pending/overdue/unpaid/partial)
    outstanding_txns = await db.fee_transactions.find(
        _tenant_query(scope, {"status": {"$in": ["overdue", "pending", "unpaid", "partial"]}})
    ).to_list(1000)

    # Build per-student outstanding balance
    student_dues: dict = {}
    for txn in outstanding_txns:
        sid = txn.get("student_id")
        if not sid:
            continue
        status = txn.get("status", "")
        amount = float(txn.get("amount", 0))
        paid_amt = float(txn.get("paid_amount") or 0) if status == "partial" else 0.0
        owed = max(0.0, amount - paid_amt)
        due = txn.get("due_date", "")
        if sid not in student_dues:
            student_dues[sid] = {"owed": 0.0, "oldest_due": due}
        student_dues[sid]["owed"] += owed
        if due and (not student_dues[sid]["oldest_due"] or due < student_dues[sid]["oldest_due"]):
            student_dues[sid]["oldest_due"] = due

    # 3. Batch-fetch student + class + guardian info (no N+1 queries)
    if student_dues:
        sid_list = list(student_dues.keys())
        students_docs = await db.students.find(
            _tenant_query(scope, {"id": {"$in": sid_list}}),
            {"_id": 0, "id": 1, "name": 1, "class_id": 1, "phone": 1},
        ).to_list(len(sid_list))
        class_ids = list({st.get("class_id") for st in students_docs if st.get("class_id")})
        classes_docs = await db.classes.find(
            _tenant_query(scope, {"id": {"$in": class_ids}}),
            {"_id": 0, "id": 1, "name": 1, "section": 1},
        ).to_list(len(class_ids))
        guardians_docs = await db.guardians.find(
            {"student_id": {"$in": sid_list}},
            {"_id": 0, "student_id": 1, "phone": 1, "is_primary": 1},
        ).to_list(len(sid_list) * 4)
        student_map = {st["id"]: st for st in students_docs}
        class_map = {c["id"]: c for c in classes_docs}
        # Build guardian phone map: prefer primary guardian, else first found
        guardian_phone_map: dict = {}
        for g in guardians_docs:
            gsid = g.get("student_id")
            if not gsid:
                continue
            if gsid not in guardian_phone_map or g.get("is_primary"):
                guardian_phone_map[gsid] = g.get("phone", "")
    else:
        student_map, class_map, guardian_phone_map = {}, {}, {}

    defaulters = []
    for sid, dues in student_dues.items():
        if dues["owed"] <= 0:
            continue
        student = student_map.get(sid)
        if not student:
            continue
        cls = class_map.get(student.get("class_id", ""))
        class_name = f"{cls.get('name', '')}-{cls.get('section', '')}" if cls else "N/A"
        oldest_due = dues["oldest_due"]
        days_overdue = 0
        if oldest_due:
            try:
                due_dt = datetime.strptime(oldest_due, "%Y-%m-%d").date()
                days_overdue = max(0, (today_dt - due_dt).days)
            except Exception:
                pass
        # R4.4/DPDP: mask guardian phones AT SOURCE (defense in depth, matching
        # get_transport_status / redaction.py) — never emit raw numbers from a tool.
        phone = _mask_phone(guardian_phone_map.get(sid) or student.get("phone", ""))
        defaulters.append({
            "student_name": student.get("name", "Unknown"),
            "class": class_name,
            "amount_overdue": dues["owed"],
            "amount_overdue_fmt": f"₹{dues['owed']:,.0f}",
            "days_overdue": days_overdue,
            "student_id": sid,
            "phone": phone,
            "guardian_phone": phone,
            "father_phone": "",
            "mother_phone": "",
        })

    defaulters.sort(key=lambda x: x["amount_overdue"], reverse=True)

    def fmt(a: float) -> str:
        if a >= 100000:
            return f"₹{a/100000:.2f}L"
        return f"₹{a:,.0f}"

    return _env({
        "stats": {
            "total_collected": fmt(total_collected),
            "total_outstanding": fmt(total_outstanding),
            "total_outstanding_raw": total_outstanding,
            "students_with_dues": len(defaulters),
            "overdue_60_days": sum(1 for d in defaulters if d["days_overdue"] >= 60),
            "collection_rate": f"{collection_rate}%",
        },
        "defaulters": defaulters,
        "total_defaulters": len(defaulters),
    }, count=len(defaulters))


async def tool_get_staff_status(params: dict, user: dict, scope=None) -> dict:
    db = get_db()
    today = date.today().strftime("%Y-%m-%d")

    all_staff = await db.staff.find(_tenant_query(scope, {"is_active": True})).to_list(100)
    staff_att = await db.staff_attendance.find(_tenant_query(scope, {"date": today})).to_list(100)
    att_by_id = {a["staff_id"]: a for a in staff_att}

    staff_data = []
    late_staff = []
    absent_staff = []

    for s in all_staff:
        att = att_by_id.get(s.get("id"))
        status = att.get("status", "not_marked") if att else "not_marked"

        # tenancy: users collection is global identity; staff row was already
        # scoped above, so the user_id lookup is safe.
        user_rec = await db.users.find_one({"id": s["user_id"]}) if s.get("user_id") else None
        staff_type = s.get("staff_type", "") or ""
        role_label = (user_rec.get("role", staff_type) if user_rec else staff_type).capitalize()

        entry = {
            "id": s.get("id"),
            "name": s.get("name", "Unknown"),
            "role": role_label,
            "staff_type": staff_type,
            "status": status,
        }
        staff_data.append(entry)
        if status == "absent":
            absent_staff.append(s.get("name", "Unknown"))
        elif status == "late":
            late_staff.append(s.get("name", "Unknown"))

    # Late arrivals in last 5 days
    late_patterns = []
    for s in all_staff:
        late_count = 0
        for i in range(5):
            d = (date.today() - timedelta(days=i)).strftime("%Y-%m-%d")
            rec = await db.staff_attendance.find_one(_tenant_query(scope, {"staff_id": s.get("id"), "date": d, "status": "late"}))
            if rec:
                late_count += 1
        if late_count >= 3:
            late_patterns.append({"name": s.get("name", "Unknown"), "late_days": late_count})

    # Pending leaves
    pending_leaves = await db.leave_requests.find(_tenant_query(scope, {"status": "pending"})).to_list(20)
    leave_details = []
    for lr in pending_leaves:
        st = await db.staff.find_one(_tenant_query(scope, {"id": lr.get("staff_id")}))
        leave_details.append({
            "id": lr.get("id"),
            "staff_name": st.get("name", "Unknown") if st else "Unknown",
            "staff_type": st.get("staff_type", "") if st else "",
            "leave_type": (lr.get("leave_type", "") or "").capitalize(),
            "start_date": lr.get("start_date", ""),
            "end_date": lr.get("end_date", ""),
            "reason": lr.get("reason", ""),
        })

    return _env({
        "total_staff": len(all_staff),
        "present_today": sum(1 for s in staff_data if s["status"] == "present"),
        "absent_today": len(absent_staff),
        "late_today": len(late_staff),
        "absent_names": absent_staff,
        "late_pattern_staff": late_patterns,
        "staff_list": staff_data,
        "pending_leaves": leave_details,
    }, count=len(all_staff))


async def tool_get_attendance_overview(params: dict, user: dict, scope=None) -> dict:
    db = get_db()
    days = params.get("days", 30)
    class_id = params.get("class_id")

    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    query = {
        "date": {
            "$gte": start_date.strftime("%Y-%m-%d"),
            "$lte": end_date.strftime("%Y-%m-%d"),
        }
    }
    if class_id:
        query["class_id"] = class_id

    records = await db.student_attendance.find(_tenant_query(scope, query)).to_list(5000)

    # Daily stats
    daily = {}
    for r in records:
        d = r.get("date")
        if d is None:
            continue
        if d not in daily:
            daily[d] = {"present": 0, "absent": 0, "total": 0}
        daily[d]["total"] += 1
        if r.get("status") == "present":
            daily[d]["present"] += 1
        elif r.get("status") == "absent":
            daily[d]["absent"] += 1

    daily_list = sorted(
        [{"date": k, **v, "rate": round(v["present"] / v["total"] * 100, 1) if v["total"] > 0 else 0}
         for k, v in daily.items()],
        key=lambda x: x["date"],
    )

    avg_rate = round(sum(d["rate"] for d in daily_list) / len(daily_list), 1) if daily_list else 0

    # Class-wise today
    today = end_date.strftime("%Y-%m-%d")
    classes = await db.classes.find(_tenant_query(scope, {})).to_list(20)
    class_stats = []
    for cls in classes:
        cls_records = await db.student_attendance.find(_tenant_query(scope, {"date": today, "class_id": cls["id"]})).to_list(100)
        if cls_records:
            p = sum(1 for r in cls_records if r.get("status") == "present")
            t = len(cls_records)
            class_stats.append({
                "class": f"{cls.get('name', '')}-{cls.get('section', '')}",
                "present": p,
                "total": t,
                "rate": f"{round(p/t*100,1)}%",
            })

    return _env({
        "period": f"Last {days} days",
        "avg_attendance_rate": f"{avg_rate}%",
        "daily_trend": daily_list[-7:],  # last 7 days for conciseness
        "class_stats_today": class_stats,
        "total_records": len(records),
    }, count=len(records))


async def tool_get_smart_alerts(params: dict, user: dict, scope=None) -> dict:
    db = get_db()
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    alerts = []

    # ── 1. Chronic absentees — batched (fixes N+1 and 100-student cap) ──────
    date_window = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(5)]
    raw_att = await db.student_attendance.find(
        _tenant_query(scope, {"date": {"$in": date_window}})
    ).to_list(20000)
    att_by_student: dict[str, dict[str, str]] = {}
    for rec in raw_att:
        sid = rec.get("student_id")
        if sid is None:
            continue
        if sid not in att_by_student:
            att_by_student[sid] = {}
        att_by_student[sid][rec["date"]] = rec.get("status", "")
    chronic = 0
    for sid, day_map in att_by_student.items():
        consec = 0
        for i in range(5):
            if day_map.get((today - timedelta(days=i)).strftime("%Y-%m-%d")) == "absent":
                consec += 1
            else:
                break
        if consec >= 3:
            chronic += 1
    if chronic > 0:
        alerts.append({"type": "warning", "category": "Attendance",
                        "text": f"{chronic} students absent 3+ consecutive days", "priority": "high"})

    # ── 2. Students below 75% attendance this month ──────────────────────────
    month_start = today.replace(day=1).strftime("%Y-%m-%d")
    monthly_agg = await db.student_attendance.aggregate([
        {"$match": _tenant_query(scope, {"date": {"$gte": month_start, "$lte": today_str}})},
        {"$group": {"_id": "$student_id", "total": {"$sum": 1},
                    "present": {"$sum": {"$cond": [{"$eq": ["$status", "present"]}, 1, 0]}}}},
    ]).to_list(5000)
    low_att = sum(1 for s in monthly_agg if s["total"] >= 5 and (s["present"] / s["total"]) < 0.75)
    if low_att > 0:
        alerts.append({"type": "warning", "category": "Attendance",
                        "text": f"{low_att} students below 75% attendance this month", "priority": "high"})

    # ── 3. Today's overall attendance rate ───────────────────────────────────
    today_att = await db.student_attendance.find(
        _tenant_query(scope, {"date": today_str})
    ).to_list(5000)
    if today_att:
        present_today = sum(1 for r in today_att if r.get("status") == "present")
        rate_today = present_today / len(today_att)
        if rate_today >= 0.95:
            alerts.append({"type": "success", "category": "Attendance",
                            "text": f"Excellent attendance today — {rate_today*100:.0f}% students present", "priority": "info"})
        elif rate_today < 0.70:
            alerts.append({"type": "warning", "category": "Attendance",
                            "text": f"Today's attendance only {rate_today*100:.0f}% — below 70% threshold", "priority": "medium"})

    # ── 4. Staff absence ─────────────────────────────────────────────────────
    total_staff = await db.staff.count_documents(_tenant_query(scope, {"is_active": True}))
    staff_absent = await db.staff_attendance.count_documents(
        _tenant_query(scope, {"date": today_str, "status": "absent"})
    )
    if staff_absent > 0:
        if total_staff > 0 and (staff_absent / total_staff) >= 0.20:
            pct = int(staff_absent / total_staff * 100)
            alerts.append({"type": "critical", "category": "Staff",
                            "text": f"High staff absence: {staff_absent}/{total_staff} staff absent today ({pct}%)", "priority": "high"})
        else:
            alerts.append({"type": "warning", "category": "Staff",
                            "text": f"{staff_absent} staff absent today", "priority": "medium"})

    # ── 5. Fee overdue — split 30-59 days (warning) and 60+ days (critical) ──
    overdue_txns = await db.fee_transactions.find(
        _tenant_query(scope, {"status": "overdue"})
    ).to_list(1000)
    overdue_60, overdue_30 = 0, 0
    for txn in overdue_txns:
        if txn.get("due_date"):
            try:
                days_late = (today - datetime.strptime(txn["due_date"], "%Y-%m-%d").date()).days
                if days_late >= 60:
                    overdue_60 += 1
                elif days_late >= 30:
                    overdue_30 += 1
            except Exception:
                pass
    if overdue_60 > 0:
        alerts.append({"type": "critical", "category": "Fees",
                        "text": f"{overdue_60} fee transactions overdue 60+ days", "priority": "high"})
    if overdue_30 > 0:
        alerts.append({"type": "warning", "category": "Fees",
                        "text": f"{overdue_30} fee transactions overdue 30–59 days", "priority": "medium"})

    # ── 6. Fee collection rate ───────────────────────────────────────────────
    fee_stats = await db.fee_transactions.aggregate([
        {"$match": _tenant_query(scope, {})},
        {"$group": {"_id": "$status", "total": {"$sum": "$amount"}}},
    ]).to_list(10)
    fee_dict = {f["_id"]: f["total"] for f in fee_stats}
    grand_total = sum(fee_dict.values())
    if grand_total > 0:
        coll_rate = fee_dict.get("paid", 0) / grand_total * 100
        if coll_rate >= 80:
            alerts.append({"type": "success", "category": "Fees",
                            "text": f"Fee collection at {coll_rate:.1f}% — excellent!", "priority": "info"})
        elif coll_rate < 30:
            alerts.append({"type": "critical", "category": "Fees",
                            "text": f"Fee collection critically low at {coll_rate:.1f}%", "priority": "high"})

    # ── 7. Leave requests — stale (3+ days) vs fresh pending ────────────────
    pending_leaves = await db.leave_requests.find(
        _tenant_query(scope, {"status": "pending"})
    ).to_list(200)
    stale_cutoff = (today - timedelta(days=3)).isoformat()
    stale_leaves = [l for l in pending_leaves if l.get("created_at", "9999") < stale_cutoff]
    if stale_leaves:
        alerts.append({"type": "warning", "category": "Leaves",
                        "text": f"{len(stale_leaves)} leave request(s) pending 3+ days — decision overdue", "priority": "medium"})
    elif pending_leaves:
        alerts.append({"type": "info", "category": "Leaves",
                        "text": f"{len(pending_leaves)} leave request(s) pending approval", "priority": "low"})

    # ── 8. Facility requests open > 3 days ───────────────────────────────────
    fac_cutoff = (today - timedelta(days=3)).isoformat()
    open_facility = await db.facility_requests.count_documents(
        _tenant_query(scope, {"status": {"$nin": ["done", "closed"]}, "created_at": {"$lt": fac_cutoff}})
    )
    if open_facility > 0:
        alerts.append({"type": "warning", "category": "Maintenance",
                        "text": f"{open_facility} facility request(s) open for 3+ days unresolved", "priority": "medium"})

    # ── 9. Tech requests unresolved ──────────────────────────────────────────
    open_tech = await db.tech_requests.count_documents(
        _tenant_query(scope, {"status": {"$nin": ["done", "closed"]}})
    )
    if open_tech > 0:
        alerts.append({"type": "info", "category": "Tech Issues",
                        "text": f"{open_tech} tech request(s) awaiting resolution", "priority": "low"})

    # ── 10. Incidents unresolved > 7 days ────────────────────────────────────
    inc_cutoff = (today - timedelta(days=7)).isoformat()
    old_incidents = await db.incidents.count_documents(
        _tenant_query(scope, {"status": {"$nin": ["resolved", "closed"]}, "created_at": {"$lt": inc_cutoff}})
    )
    if old_incidents > 0:
        alerts.append({"type": "critical", "category": "Incidents",
                        "text": f"{old_incidents} incident(s) unresolved for 7+ days", "priority": "high"})

    # ── 11. Visitors still checked in ────────────────────────────────────────
    visitors_in = await db.visitor_log.count_documents(
        _tenant_query(scope, {"time_out": None})
    )
    if visitors_in > 0:
        alerts.append({"type": "info", "category": "Visitors",
                        "text": f"{visitors_in} visitor(s) still checked in — checkout not recorded", "priority": "low"})

    # ── 12. Stale admissions enquiries (new, no follow-up 7+ days) ───────────
    enq_cutoff = (today - timedelta(days=7)).isoformat()
    stale_enq = await db.enquiries.count_documents(
        _tenant_query(scope, {"status": "new", "created_at": {"$lt": enq_cutoff}})
    )
    if stale_enq > 0:
        alerts.append({"type": "warning", "category": "Admissions",
                        "text": f"{stale_enq} enquiry/enquiries with no follow-up for 7+ days", "priority": "medium"})

    # Sort: critical → warning → info → success, then high → medium → low
    _type_order = {"critical": 0, "warning": 1, "info": 2, "success": 3}
    _pri_order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    alerts.sort(key=lambda a: (_type_order.get(a["type"], 4), _pri_order.get(a["priority"], 4)))

    return _env({
        "alerts": alerts,
        "total_alerts": len(alerts),
        "critical_count": sum(1 for a in alerts if a["type"] == "critical"),
        "warning_count": sum(1 for a in alerts if a["type"] == "warning"),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }, count=len(alerts))


async def tool_search_students(params: dict, user: dict, scope=None) -> dict:
    db = get_db()
    query_str = params.get("query", "")
    class_name = params.get("class_name")

    filter_q = {"is_active": True}
    if query_str:
        safe_q = re.escape(query_str)
        filter_q["$or"] = [
            {"name": {"$regex": safe_q, "$options": "i"}},
            {"admission_number": {"$regex": safe_q, "$options": "i"}},
        ]
    if class_name:
        cls = await db.classes.find_one(_tenant_query(scope, {"name": {"$regex": re.escape(class_name), "$options": "i"}}))
        if cls:
            filter_q["class_id"] = cls["id"]

    students = await db.students.find(_tenant_query(scope, filter_q)).to_list(20)
    result = []
    for s in students:
        cls = await db.classes.find_one(_tenant_query(scope, {"id": s.get("class_id")}))
        class_label = f"{cls.get('name', '')}-{cls.get('section', '')}" if cls else "N/A"
        result.append({
            "id": s.get("id"),
            "name": s.get("name", "Unknown"),
            "class": class_label,
            "admission_number": s.get("admission_number", "N/A"),
            "roll_number": s.get("roll_number", "N/A"),
            "status": s.get("status", "active"),
        })

    msg = "" if result else f"No students matched '{query_str}'." if query_str else "No students found."
    return _env(result, message=msg, count=len(result))


async def tool_get_fee_transactions(params: dict, user: dict, scope=None) -> dict:
    db = get_db()
    student_id = params.get("student_id")
    status_filter = params.get("status")

    query = {}
    if student_id:
        query["student_id"] = student_id
    if status_filter:
        query["status"] = status_filter

    txns = await db.fee_transactions.find(_tenant_query(scope, query)).to_list(50)
    result = []
    for t in txns:
        student = await db.students.find_one(_tenant_query(scope, {"id": t.get("student_id")}))
        result.append({
            "id": t.get("id"),
            "student_name": student.get("name", "Unknown") if student else "Unknown",
            "fee_type": t.get("fee_type", "N/A"),
            "amount": f"₹{float(t.get('amount', 0)):,.0f}",
            "due_date": t.get("due_date", "N/A"),
            "paid_date": t.get("paid_date", "N/A"),
            "status": t.get("status", "N/A"),
            "payment_mode": t.get("payment_mode", "N/A"),
        })

    return _env(result, count=len(result))


async def tool_approve_leave(params: dict, user: dict, scope=None) -> dict:
    # Thin adapter over services.leave_service.decide_leave — the SAME write path
    # as PATCH /api/staff/leaves/{id}. Story A.2: the AI decision now notifies the
    # staff member, writes the audit row, enforces the pending-only guard, requires
    # a rejection reason, and stamps a UTC approved_at — identical to the panel.
    leave_id = params.get("leave_id")
    if not leave_id:
        return _env(None, success=False, message="leave_id is required", count=0)
    action = params.get("action", "approve")
    reason = params.get("reason", "")
    new_status = "approved" if action == "approve" else "rejected"

    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_scope_branch_id(scope))
    service_params = {"leave_id": leave_id, "status": new_status}
    if reason:
        service_params["rejection_reason"] = reason

    try:
        result = await decide_leave(db, actor_ctx, service_params)
    except LeaveNotFoundError:
        return _env(None, success=False, message="Leave request not found", count=0)
    except (LeaveValidationError, LeaveConflictError) as e:
        return _env(None, success=False, message=str(e), count=0)

    leave = result.get("leave") if isinstance(result, dict) else None
    staff = None
    if leave and leave.get("staff_id"):
        staff = await db.staff.find_one(_tenant_query(scope, {"id": leave["staff_id"]}))
    staff_name = staff.get("name", "staff member") if staff else "staff member"
    return _env(
        {"leave_id": leave_id, "new_status": new_status},
        message=f"Leave request {new_status} for {staff_name}",
        count=1,
    )


async def tool_get_enquiries(params: dict, user: dict, scope=None) -> dict:
    db = get_db()
    status_filter = params.get("status")
    query = {}
    if status_filter:
        query["status"] = status_filter

    enquiries = await db.enquiries.find(_tenant_query(scope, query)).sort("created_at", -1).to_list(20)

    status_counts = {}
    all_enquiries = await db.enquiries.find(_tenant_query(scope, {})).to_list(200)
    for e in all_enquiries:
        s = e.get("status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1

    data = [
        {
            "id": e.get("id"),
            "student_name": e.get("student_name", "Unknown"),
            "parent_name": e.get("parent_name", "Unknown"),
            # R4.4/AC2: mask to the canonical last-3 rule (was first-5 exposed).
            "phone": _mask_phone(e.get("phone", "")),
            "class_applying": e.get("class_applying", "N/A"),
            "status": e.get("status", "unknown"),
            "source": e.get("source", "N/A"),
            "created_at": (e.get("created_at") or "")[:10],
        }
        for e in enquiries
    ]
    return _env(
        data,
        count=len(all_enquiries),
        message="" if data else "No admission enquiries found.",
    ) | {"funnel": status_counts}


async def tool_get_my_attendance(params: dict, user: dict, scope=None) -> dict:
    db = get_db()
    # Tenancy: locate the student row in the requester's tenant.
    student = await db.students.find_one(_tenant_query(scope, {"user_id": user["id"]}))
    if not student:
        return _env(None, success=False, message="Student record not found", count=0)

    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    records = await db.student_attendance.find(_tenant_query(scope, {
        "student_id": student["id"],
        "date": {"$gte": start_date.strftime("%Y-%m-%d"), "$lte": end_date.strftime("%Y-%m-%d")},
    })).to_list(100)

    present = sum(1 for r in records if r.get("status") == "present")
    total = len(records)
    rate = round(present / total * 100, 1) if total > 0 else 0

    return _env({
        "student_name": student.get("name", "Student"),
        "period": "Last 30 days",
        "total_days": total,
        "present": present,
        "absent": total - present,
        "attendance_rate": f"{rate}%",
        "records": [{"date": r.get("date"), "status": r.get("status")} for r in records[-7:]],
    }, count=total)


async def tool_get_my_fees(params: dict, user: dict, scope=None) -> dict:
    db = get_db()
    student = await db.students.find_one(_tenant_query(scope, {"user_id": user["id"]}))
    if not student:
        return _env(None, success=False, message="Student record not found", count=0)

    txns = await db.fee_transactions.find(_tenant_query(scope, {"student_id": student["id"]})).to_list(50)
    return _env({
        "student_name": student.get("name", "Student"),
        "transactions": [
            {"fee_type": t.get("fee_type", "N/A"), "amount": f"₹{float(t.get('amount', 0)):,.0f}",
             "status": t.get("status", "N/A"), "due_date": t.get("due_date", "N/A"),
             "paid_date": t.get("paid_date", "N/A")} for t in txns
        ],
        "total_paid": f"₹{sum(float(t.get('amount', 0)) for t in txns if t.get('status') == 'paid'):,.0f}",
        "total_pending": f"₹{sum(float(t.get('amount', 0)) for t in txns if t.get('status') in ['pending', 'overdue']):,.0f}",
    }, count=len(txns))


async def tool_get_my_results(params: dict, user: dict, scope=None) -> dict:
    db = get_db()
    student = await db.students.find_one(_tenant_query(scope, {"user_id": user["id"]}))
    if not student:
        return _env(None, success=False, message="Student record not found", count=0)

    results = await db.exam_results.find(_tenant_query(scope, {"student_id": student["id"]})).to_list(50)
    enriched = []
    for r in results:
        subj = await db.subjects.find_one(_tenant_query(scope, {"id": r.get("subject_id")}))
        exam = await db.exams.find_one(_tenant_query(scope, {"id": r.get("exam_id")}))
        enriched.append({
            "exam": exam.get("name", "N/A") if exam else "N/A",
            "subject": subj.get("name", "N/A") if subj else "N/A",
            "marks": f"{r.get('marks_obtained', 0)}/{r.get('max_marks', 100)}",
            "grade": r.get("grade", "N/A"),
        })

    return _env(
        {"student_name": student.get("name", "Student"), "results": enriched, "total_exams": len(enriched)},
        count=len(enriched),
    )


async def tool_get_financial_report(params: dict, user: dict, scope=None) -> dict:
    """Financial report: expected revenue vs actually collected (by fee type).

    total_expected = all fee transaction amounts (what should be collected)
    total_collected = paid in full + paid_amount from partial payments
    collection_rate = total_collected / total_expected * 100
    """
    db = get_db()
    fee_pipeline = [
        {"$match": _tenant_query(scope, {})},
        {"$group": {"_id": "$fee_type", "total": {"$sum": "$amount"}, "count": {"$sum": 1}}},
    ]
    fee_by_type = await db.fee_transactions.aggregate(fee_pipeline).to_list(20)

    # Collect paid (full) and partial (paid_amount portion) per fee_type
    paid_pipeline = [
        {"$match": _tenant_query(scope, {"status": {"$in": ["paid", "partial"]}})},
        {
            "$group": {
                "_id": "$fee_type",
                "total": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$status", "partial"]},
                            {"$ifNull": ["$paid_amount", 0]},
                            "$amount",
                        ]
                    }
                },
            }
        },
    ]
    paid_by_type = {f["_id"]: f["total"] for f in await db.fee_transactions.aggregate(paid_pipeline).to_list(20)}

    total_expected = sum(f["total"] for f in fee_by_type)
    total_collected = sum(paid_by_type.values())

    def fmt(a):
        if a >= 100000:
            return f"₹{a/100000:.2f}L"
        return f"₹{a:,.0f}"

    return _env({
        "total_expected": fmt(total_expected),
        "total_collected": fmt(total_collected),
        "collection_rate": f"{round(total_collected/total_expected*100,1)}%" if total_expected else "N/A",
        "by_fee_type": [
            {"fee_type": f.get("_id"), "expected": fmt(f.get("total", 0)), "collected": fmt(paid_by_type.get(f.get("_id"), 0))}
            for f in fee_by_type
        ],
    }, count=len(fee_by_type))


async def tool_get_daily_brief(params: dict, user: dict, scope=None) -> dict:
    """Comprehensive daily brief combining school pulse, alerts, and fee summary."""
    db = get_db()
    today = date.today().strftime("%Y-%m-%d")
    day_name = date.today().strftime("%A, %d %B %Y")

    # Get core data in parallel-style sequence — propagate scope to each sub-tool.
    # R4.2: sub-tools now return the envelope, so read their payloads from `data`.
    pulse = (await tool_get_school_pulse({}, user, scope)).get("data", {})
    alerts = (await tool_get_smart_alerts({}, user, scope)).get("data", {})
    fee = (await tool_get_fee_summary({}, user, scope)).get("data", {})

    # Upcoming events/announcements
    upcoming = await db.announcements.find(
        _tenant_query(scope, {"is_draft": False}),
        {"_id": 0, "title": 1, "created_at": 1},
    ).sort("created_at", -1).to_list(3)

    return _env({
        "date": day_name,
        "greeting": f"Good morning! Here's your daily brief for {day_name}.",
        "attendance": {
            "rate": pulse.get("summary", {}).get("attendance_rate", "Not marked"),
            "present": pulse.get("summary", {}).get("present_today", 0),
            "absent": pulse.get("summary", {}).get("absent_today", 0),
            "staff_absent": pulse.get("staff_absent_today", []),
        },
        "leaves": {
            "pending_count": pulse.get("summary", {}).get("pending_leaves", 0),
            "requests": pulse.get("pending_leave_requests", [])[:3],
        },
        "fees": {
            "collected": fee.get("stats", {}).get("total_collected", "N/A"),
            "overdue": fee.get("stats", {}).get("total_outstanding", "N/A"),
            "collection_rate": fee.get("stats", {}).get("collection_rate", "N/A"),
            "top_defaulters": fee.get("defaulters", [])[:3],
        },
        "alerts": alerts.get("alerts", [])[:5],
        "chronic_absent_students": pulse.get("chronic_absent_students", []),
        "announcements": [a.get("title") for a in upcoming],
    }, count=1)


# Tool registry
TOOL_REGISTRY = {
    "get_school_pulse": {"fn": tool_get_school_pulse, "roles": ["owner", "admin"]},
    "get_daily_brief": {"fn": tool_get_daily_brief, "roles": ["owner", "admin"]},
    "get_fee_summary": {"fn": tool_get_fee_summary, "roles": ["owner", "admin"]},
    "get_staff_status": {"fn": tool_get_staff_status, "roles": ["owner", "admin"]},
    "get_attendance_overview": {"fn": tool_get_attendance_overview, "roles": ["owner", "admin", "teacher"]},
    "get_smart_alerts": {"fn": tool_get_smart_alerts, "roles": ["owner", "admin"]},
    "get_financial_report": {"fn": tool_get_financial_report, "roles": ["owner"]},
    "search_students": {"fn": tool_search_students, "roles": ["owner", "admin", "teacher"]},
    "get_fee_transactions": {"fn": tool_get_fee_transactions, "roles": ["owner", "admin"]},
    "approve_leave": {"fn": tool_approve_leave, "roles": ["owner", "admin"]},
    "get_enquiries": {"fn": tool_get_enquiries, "roles": ["owner", "admin"]},
    "get_my_attendance": {"fn": tool_get_my_attendance, "roles": ["student"]},
    "get_my_fees": {"fn": tool_get_my_fees, "roles": ["student"]},
    "get_my_results": {"fn": tool_get_my_results, "roles": ["student"]},
}
