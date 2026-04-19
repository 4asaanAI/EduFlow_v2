"""
Tool functions executed when the LLM requests them.
Each function queries MongoDB and returns structured data.
"""
from datetime import datetime, date, timedelta
from database import get_db
import logging, re

logger = logging.getLogger(__name__)


async def tool_get_school_pulse(params: dict, user: dict) -> dict:
    db = get_db()
    today = date.today().strftime("%Y-%m-%d")
    week_ago = (date.today() - timedelta(days=7)).strftime("%Y-%m-%d")

    total_students = await db.students.count_documents({"is_active": True})
    total_staff = await db.staff.count_documents({"is_active": True})

    # Student attendance today
    att_today = await db.student_attendance.find({"date": today}).to_list(1000)
    total_marked = len(att_today)
    present = sum(1 for a in att_today if a["status"] == "present")
    absent = sum(1 for a in att_today if a["status"] == "absent")
    att_rate = round(present / total_marked * 100, 1) if total_marked > 0 else 0

    # Staff attendance today
    staff_att = await db.staff_attendance.find({"date": today}).to_list(100)
    staff_absent = [a for a in staff_att if a["status"] == "absent"]
    staff_absent_names = []
    for sa in staff_absent:
        st = await db.staff.find_one({"id": sa["staff_id"]})
        if st:
            staff_absent_names.append(st["name"])

    # Fee stats
    fee_pipeline = [
        {"$group": {"_id": "$status", "total": {"$sum": "$amount"}, "count": {"$sum": 1}}}
    ]
    fee_stats = await db.fee_transactions.aggregate(fee_pipeline).to_list(10)
    fee_dict = {f["_id"]: {"total": f["total"], "count": f["count"]} for f in fee_stats}
    total_paid = fee_dict.get("paid", {}).get("total", 0)
    total_overdue = fee_dict.get("overdue", {}).get("total", 0)
    total_pending = fee_dict.get("pending", {}).get("total", 0)

    # Pending leaves
    pending_leaves = await db.leave_requests.find({"status": "pending"}).to_list(20)
    leave_details = []
    for lr in pending_leaves:
        staff = await db.staff.find_one({"id": lr["staff_id"]})
        leave_details.append({
            "id": lr["id"],
            "staff_name": staff["name"] if staff else "Unknown",
            "leave_type": lr["leave_type"],
            "start_date": lr["start_date"],
            "end_date": lr["end_date"],
            "reason": lr.get("reason", ""),
        })

    # Students absent 3+ consecutive days
    chronic_absent = []
    students_list = await db.students.find({"is_active": True}).to_list(500)
    for st in students_list[:50]:  # limit for performance
        absent_count = 0
        check_date = date.today()
        for i in range(5):
            d = (check_date - timedelta(days=i)).strftime("%Y-%m-%d")
            rec = await db.student_attendance.find_one({"student_id": st["id"], "date": d})
            if rec and rec["status"] == "absent":
                absent_count += 1
            else:
                break
        if absent_count >= 3:
            chronic_absent.append({"name": st["name"], "days": absent_count})

    def fmt_amount(a):
        if a >= 100000:
            return f"₹{a/100000:.1f}L"
        elif a >= 1000:
            return f"₹{a/1000:.0f}K"
        return f"₹{a:,.0f}"

    return {
        "summary": {
            "total_students": total_students,
            "total_staff": total_staff,
            "attendance_rate": f"{att_rate}%",
            "present_today": present,
            "absent_today": absent,
            "fee_collected": fmt_amount(total_paid),
            "fee_overdue": fmt_amount(total_overdue),
            "pending_leaves": len(pending_leaves),
        },
        "staff_absent_today": staff_absent_names,
        "pending_leave_requests": leave_details,
        "chronic_absent_students": chronic_absent,
        "fee_stats": {
            "paid": fmt_amount(total_paid),
            "overdue": fmt_amount(total_overdue),
            "pending": fmt_amount(total_pending),
        }
    }


async def tool_get_fee_summary(params: dict, user: dict) -> dict:
    db = get_db()

    # Defaulters - students with overdue fees
    overdue_txns = await db.fee_transactions.find({"status": "overdue"}).to_list(200)
    
    # Group by student
    student_dues = {}
    for txn in overdue_txns:
        sid = txn.get("student_id")
        if not sid:
            continue
        if sid not in student_dues:
            student_dues[sid] = {"amount": 0, "count": 0, "oldest_due": txn.get("due_date", "")}
        student_dues[sid]["amount"] += txn.get("amount", 0)
        student_dues[sid]["count"] += 1
        due = txn.get("due_date", "")
        if due and due < student_dues[sid]["oldest_due"]:
            student_dues[sid]["oldest_due"] = due

    # Enrich with student data
    defaulters = []
    for sid, dues in student_dues.items():
        student = await db.students.find_one({"id": sid})
        if student:
            cls = await db.classes.find_one({"id": student.get("class_id")})
            class_name = f"{cls.get('name', '')}-{cls.get('section', '')}" if cls else "N/A"
            
            # Calculate days overdue
            if dues["oldest_due"]:
                try:
                    due_dt = datetime.strptime(dues["oldest_due"], "%Y-%m-%d").date()
                    days_overdue = (date.today() - due_dt).days
                except:
                    days_overdue = 0
            else:
                days_overdue = 0

            defaulters.append({
                "student_name": student["name"],
                "class": class_name,
                "amount_overdue": dues["amount"],
                "amount_overdue_fmt": f"₹{dues['amount']:,.0f}",
                "days_overdue": days_overdue,
                "student_id": sid,
            })

    defaulters.sort(key=lambda x: x["amount_overdue"], reverse=True)

    # Overall stats
    pipeline = [
        {"$group": {"_id": "$status", "total": {"$sum": "$amount"}, "count": {"$sum": 1}}}
    ]
    stats = await db.fee_transactions.aggregate(pipeline).to_list(10)
    stats_dict = {s["_id"]: s for s in stats}

    total_collected = stats_dict.get("paid", {}).get("total", 0)
    total_overdue = stats_dict.get("overdue", {}).get("total", 0)
    total_pending = stats_dict.get("pending", {}).get("total", 0)
    total_all = total_collected + total_overdue + total_pending
    collection_rate = round(total_collected / total_all * 100, 1) if total_all > 0 else 0

    def fmt(a):
        if a >= 100000:
            return f"₹{a/100000:.2f}L"
        return f"₹{a:,.0f}"

    return {
        "stats": {
            "total_overdue": fmt(total_overdue),
            "total_overdue_raw": total_overdue,
            "students_with_dues": len(defaulters),
            "overdue_60_days": sum(1 for d in defaulters if d["days_overdue"] >= 60),
            "collection_rate": f"{collection_rate}%",
            "total_collected": fmt(total_collected),
        },
        "defaulters": defaulters,
        "total_defaulters": len(defaulters),
    }


async def tool_get_staff_status(params: dict, user: dict) -> dict:
    db = get_db()
    today = date.today().strftime("%Y-%m-%d")

    all_staff = await db.staff.find({"is_active": True}).to_list(100)
    staff_att = await db.staff_attendance.find({"date": today}).to_list(100)
    att_by_id = {a["staff_id"]: a for a in staff_att}

    staff_data = []
    late_staff = []
    absent_staff = []

    for s in all_staff:
        att = att_by_id.get(s["id"])
        status = att["status"] if att else "not_marked"
        
        user_rec = await db.users.find_one({"id": s["user_id"]}) if s.get("user_id") else None
        role_label = user_rec["role"].capitalize() if user_rec else s["staff_type"].capitalize()
        
        entry = {
            "id": s["id"],
            "name": s["name"],
            "role": role_label,
            "staff_type": s["staff_type"],
            "status": status,
        }
        staff_data.append(entry)
        if status == "absent":
            absent_staff.append(s["name"])
        elif status == "late":
            late_staff.append(s["name"])

    # Late arrivals in last 5 days
    late_patterns = []
    for s in all_staff:
        late_count = 0
        for i in range(5):
            d = (date.today() - timedelta(days=i)).strftime("%Y-%m-%d")
            rec = await db.staff_attendance.find_one({"staff_id": s["id"], "date": d, "status": "late"})
            if rec:
                late_count += 1
        if late_count >= 3:
            late_patterns.append({"name": s["name"], "late_days": late_count})

    # Pending leaves
    pending_leaves = await db.leave_requests.find({"status": "pending"}).to_list(20)
    leave_details = []
    for lr in pending_leaves:
        st = await db.staff.find_one({"id": lr["staff_id"]})
        leave_details.append({
            "id": lr["id"],
            "staff_name": st["name"] if st else "Unknown",
            "staff_type": st["staff_type"] if st else "",
            "leave_type": lr["leave_type"].capitalize(),
            "start_date": lr["start_date"],
            "end_date": lr["end_date"],
            "reason": lr.get("reason", ""),
        })

    return {
        "total_staff": len(all_staff),
        "present_today": sum(1 for s in staff_data if s["status"] == "present"),
        "absent_today": len(absent_staff),
        "late_today": len(late_staff),
        "absent_names": absent_staff,
        "late_pattern_staff": late_patterns,
        "staff_list": staff_data,
        "pending_leaves": leave_details,
    }


async def tool_get_attendance_overview(params: dict, user: dict) -> dict:
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

    records = await db.student_attendance.find(query).to_list(5000)

    # Daily stats
    daily = {}
    for r in records:
        d = r["date"]
        if d not in daily:
            daily[d] = {"present": 0, "absent": 0, "total": 0}
        daily[d]["total"] += 1
        if r["status"] == "present":
            daily[d]["present"] += 1
        elif r["status"] == "absent":
            daily[d]["absent"] += 1

    daily_list = sorted(
        [{"date": k, **v, "rate": round(v["present"] / v["total"] * 100, 1) if v["total"] > 0 else 0}
         for k, v in daily.items()],
        key=lambda x: x["date"],
    )

    avg_rate = round(sum(d["rate"] for d in daily_list) / len(daily_list), 1) if daily_list else 0

    # Class-wise today
    today = end_date.strftime("%Y-%m-%d")
    classes = await db.classes.find().to_list(20)
    class_stats = []
    for cls in classes:
        cls_records = await db.student_attendance.find({"date": today, "class_id": cls["id"]}).to_list(100)
        if cls_records:
            p = sum(1 for r in cls_records if r["status"] == "present")
            t = len(cls_records)
            class_stats.append({
                "class": f"{cls['name']}-{cls['section']}",
                "present": p,
                "total": t,
                "rate": f"{round(p/t*100,1)}%",
            })

    return {
        "period": f"Last {days} days",
        "avg_attendance_rate": f"{avg_rate}%",
        "daily_trend": daily_list[-7:],  # last 7 days for conciseness
        "class_stats_today": class_stats,
        "total_records": len(records),
    }


async def tool_get_smart_alerts(params: dict, user: dict) -> dict:
    db = get_db()
    today = date.today().strftime("%Y-%m-%d")
    alerts = []

    # Chronic absentees (3+ days)
    students = await db.students.find({"is_active": True}).to_list(500)
    chronic = 0
    for st in students[:100]:
        abs_count = 0
        for i in range(5):
            d = (date.today() - timedelta(days=i)).strftime("%Y-%m-%d")
            rec = await db.student_attendance.find_one({"student_id": st["id"], "date": d})
            if rec and rec["status"] == "absent":
                abs_count += 1
            else:
                break
        if abs_count >= 3:
            chronic += 1

    if chronic > 0:
        alerts.append({"type": "warning", "category": "Attendance", "text": f"{chronic} students absent 3+ consecutive days", "priority": "high"})

    # Staff absent today
    staff_absent = await db.staff_attendance.count_documents({"date": today, "status": "absent"})
    if staff_absent > 0:
        alerts.append({"type": "warning", "category": "Staff", "text": f"{staff_absent} staff absent today", "priority": "medium"})

    # Overdue fees 60+ days
    overdue_60 = 0
    overdue_txns = await db.fee_transactions.find({"status": "overdue"}).to_list(200)
    for txn in overdue_txns:
        if txn.get("due_date"):
            try:
                due_dt = datetime.strptime(txn["due_date"], "%Y-%m-%d").date()
                if (date.today() - due_dt).days >= 60:
                    overdue_60 += 1
            except:
                pass

    if overdue_60 > 0:
        alerts.append({"type": "critical", "category": "Fees", "text": f"{overdue_60} fee transactions overdue 60+ days", "priority": "high"})

    # Pending leave requests
    pending_leaves = await db.leave_requests.count_documents({"status": "pending"})
    if pending_leaves > 0:
        alerts.append({"type": "info", "category": "Leaves", "text": f"{pending_leaves} leave requests pending approval", "priority": "low"})

    # Positive alerts
    fee_pipeline = [{"$group": {"_id": "$status", "total": {"$sum": "$amount"}}}]
    fee_stats = await db.fee_transactions.aggregate(fee_pipeline).to_list(10)
    fee_dict = {f["_id"]: f["total"] for f in fee_stats}
    total = sum(fee_dict.values())
    if total > 0:
        rate = fee_dict.get("paid", 0) / total * 100
        if rate >= 80:
            alerts.append({"type": "success", "category": "Fees", "text": f"Fee collection at {rate:.1f}% — excellent!", "priority": "info"})

    return {"alerts": alerts, "total_alerts": len(alerts), "critical_count": sum(1 for a in alerts if a["type"] == "critical")}


async def tool_search_students(params: dict, user: dict) -> dict:
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
        cls = await db.classes.find_one({"name": {"$regex": re.escape(class_name), "$options": "i"}})
        if cls:
            filter_q["class_id"] = cls["id"]

    students = await db.students.find(filter_q).to_list(20)
    result = []
    for s in students:
        cls = await db.classes.find_one({"id": s.get("class_id")})
        class_label = f"{cls['name']}-{cls['section']}" if cls else "N/A"
        result.append({
            "id": s["id"],
            "name": s["name"],
            "class": class_label,
            "admission_number": s.get("admission_number", "N/A"),
            "roll_number": s.get("roll_number", "N/A"),
            "status": s.get("status", "active"),
        })

    return {"students": result, "total": len(result), "query": query_str}


async def tool_get_fee_transactions(params: dict, user: dict) -> dict:
    db = get_db()
    student_id = params.get("student_id")
    status_filter = params.get("status")

    query = {}
    if student_id:
        query["student_id"] = student_id
    if status_filter:
        query["status"] = status_filter

    txns = await db.fee_transactions.find(query).to_list(50)
    result = []
    for t in txns:
        student = await db.students.find_one({"id": t["student_id"]})
        result.append({
            "id": t["id"],
            "student_name": student["name"] if student else "Unknown",
            "fee_type": t["fee_type"],
            "amount": f"₹{t['amount']:,.0f}",
            "due_date": t.get("due_date", "N/A"),
            "paid_date": t.get("paid_date", "N/A"),
            "status": t["status"],
            "payment_mode": t.get("payment_mode", "N/A"),
        })

    return {"transactions": result, "total": len(result)}


async def tool_approve_leave(params: dict, user: dict) -> dict:
    db = get_db()
    leave_id = params.get("leave_id")
    action = params.get("action", "approve")
    reason = params.get("reason", "")

    if not leave_id:
        return {"error": "leave_id is required"}

    leave = await db.leave_requests.find_one({"id": leave_id})
    if not leave:
        return {"error": f"Leave request {leave_id} not found"}

    new_status = "approved" if action == "approve" else "rejected"
    update = {
        "status": new_status,
        "approved_by": user["id"],
        "approved_at": datetime.now().isoformat(),
    }
    if action == "reject" and reason:
        update["rejection_reason"] = reason

    await db.leave_requests.update_one({"id": leave_id}, {"$set": update})

    staff = await db.staff.find_one({"id": leave["staff_id"]})
    return {
        "success": True,
        "message": f"Leave request {new_status} for {staff['name'] if staff else 'staff member'}",
        "leave_id": leave_id,
        "new_status": new_status,
    }


async def tool_get_enquiries(params: dict, user: dict) -> dict:
    db = get_db()
    status_filter = params.get("status")
    query = {}
    if status_filter:
        query["status"] = status_filter

    enquiries = await db.enquiries.find(query).sort("created_at", -1).to_list(20)

    status_counts = {}
    all_enquiries = await db.enquiries.find().to_list(200)
    for e in all_enquiries:
        s = e["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    return {
        "enquiries": [
            {
                "id": e["id"],
                "student_name": e["student_name"],
                "parent_name": e["parent_name"],
                "phone": e["phone"][:5] + "XXXXX",
                "class_applying": e.get("class_applying", "N/A"),
                "status": e["status"],
                "source": e.get("source", "N/A"),
                "created_at": e["created_at"][:10],
            }
            for e in enquiries
        ],
        "funnel": status_counts,
        "total": len(all_enquiries),
    }


async def tool_get_my_attendance(params: dict, user: dict) -> dict:
    db = get_db()
    student = await db.students.find_one({"user_id": user["id"]})
    if not student:
        return {"error": "Student record not found"}

    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    records = await db.student_attendance.find({
        "student_id": student["id"],
        "date": {"$gte": start_date.strftime("%Y-%m-%d"), "$lte": end_date.strftime("%Y-%m-%d")},
    }).to_list(100)

    present = sum(1 for r in records if r["status"] == "present")
    total = len(records)
    rate = round(present / total * 100, 1) if total > 0 else 0

    return {
        "student_name": student["name"],
        "period": "Last 30 days",
        "total_days": total,
        "present": present,
        "absent": total - present,
        "attendance_rate": f"{rate}%",
        "records": [{"date": r["date"], "status": r["status"]} for r in records[-7:]],
    }


async def tool_get_my_fees(params: dict, user: dict) -> dict:
    db = get_db()
    student = await db.students.find_one({"user_id": user["id"]})
    if not student:
        return {"error": "Student record not found"}

    txns = await db.fee_transactions.find({"student_id": student["id"]}).to_list(50)
    return {
        "student_name": student["name"],
        "transactions": [
            {"fee_type": t["fee_type"], "amount": f"₹{t['amount']:,.0f}",
             "status": t["status"], "due_date": t.get("due_date", "N/A"),
             "paid_date": t.get("paid_date", "N/A")} for t in txns
        ],
        "total_paid": f"₹{sum(t['amount'] for t in txns if t['status'] == 'paid'):,.0f}",
        "total_pending": f"₹{sum(t['amount'] for t in txns if t['status'] in ['pending', 'overdue']):,.0f}",
    }


async def tool_get_my_results(params: dict, user: dict) -> dict:
    db = get_db()
    student = await db.students.find_one({"user_id": user["id"]})
    if not student:
        return {"error": "Student record not found"}

    results = await db.exam_results.find({"student_id": student["id"]}).to_list(50)
    enriched = []
    for r in results:
        subj = await db.subjects.find_one({"id": r.get("subject_id")})
        exam = await db.exams.find_one({"id": r.get("exam_id")})
        enriched.append({
            "exam": exam["name"] if exam else "N/A",
            "subject": subj["name"] if subj else "N/A",
            "marks": f"{r.get('marks_obtained', 0)}/{r.get('max_marks', 100)}",
            "grade": r.get("grade", "N/A"),
        })

    return {"student_name": student["name"], "results": enriched, "total_exams": len(enriched)}


async def tool_get_financial_report(params: dict, user: dict) -> dict:
    db = get_db()
    fee_pipeline = [{"$group": {"_id": "$fee_type", "total": {"$sum": "$amount"}, "count": {"$sum": 1}}}]
    fee_by_type = await db.fee_transactions.aggregate(fee_pipeline).to_list(20)

    paid_pipeline = [
        {"$match": {"status": "paid"}},
        {"$group": {"_id": "$fee_type", "total": {"$sum": "$amount"}}},
    ]
    paid_by_type = {f["_id"]: f["total"] for f in await db.fee_transactions.aggregate(paid_pipeline).to_list(20)}

    total_expected = sum(f["total"] for f in fee_by_type)
    total_collected = sum(paid_by_type.values())

    def fmt(a):
        if a >= 100000:
            return f"₹{a/100000:.2f}L"
        return f"₹{a:,.0f}"

    return {
        "total_expected": fmt(total_expected),
        "total_collected": fmt(total_collected),
        "collection_rate": f"{round(total_collected/total_expected*100,1)}%" if total_expected else "N/A",
        "by_fee_type": [
            {"fee_type": f["_id"], "expected": fmt(f["total"]), "collected": fmt(paid_by_type.get(f["_id"], 0))}
            for f in fee_by_type
        ],
    }


async def tool_get_daily_brief(params: dict, user: dict) -> dict:
    """Comprehensive daily brief combining school pulse, alerts, and fee summary."""
    db = get_db()
    today = date.today().strftime("%Y-%m-%d")
    day_name = date.today().strftime("%A, %d %B %Y")

    # Get core data in parallel-style sequence
    pulse = await tool_get_school_pulse({}, user)
    alerts = await tool_get_smart_alerts({}, user)
    fee = await tool_get_fee_summary({}, user)

    # Upcoming events/announcements
    upcoming = await db.announcements.find({"is_draft": False}, {"_id": 0, "title": 1, "created_at": 1}).sort("created_at", -1).to_list(3)

    return {
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
            "overdue": fee.get("stats", {}).get("total_overdue", "N/A"),
            "collection_rate": fee.get("stats", {}).get("collection_rate", "N/A"),
            "top_defaulters": fee.get("defaulters", [])[:3],
        },
        "alerts": alerts.get("alerts", [])[:5],
        "chronic_absent_students": pulse.get("chronic_absent_students", []),
        "announcements": [a["title"] for a in upcoming],
    }


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
