from __future__ import annotations
"""Notifications API — Story 16: persistent in-app notifications + role-scoped digest"""
from fastapi import APIRouter, Request, HTTPException, Depends
from database import get_db
from middleware.auth import get_current_user, require_role
from services.notification_service import create_notification as create_persistent_notification
from tenant import get_school_id, scoped_filter
from datetime import datetime, date

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def get_user(req: Request):
    return get_current_user(req)


# Epic 6, Story 6.2: the server-side sort whitelist. An unrecognised value falls
# back to the default rather than reaching a query, so the parameter can never
# select an ordering the caller was not offered. Same rule Epic 3 set for tables.
SORT_ORDERS = {
    "newest": -1,
    "oldest": 1,
}
DEFAULT_SORT = "newest"


async def count_unread(db, user_id: str) -> int:
    """The ONE place "how many are unread" is decided (Epic 6, readiness Q-1).

    Both `GET /unread-count` (which the header bell reads) and `meta.unread_total`
    on the list endpoint (which the panel and the All Notifications page read) call
    this. Written twice they would agree today and diverge the first time anyone
    added a filter to one of them — and the symptom would be a count the owner
    cannot believe, which is the defect this epic exists to remove.
    """
    return await db.notifications.count_documents(
        # branch-scope: intentional — a notification belongs to ONE user, and
        # user_id is strictly narrower than branch_id. Notification documents
        # carry no branch_id at all (services/notification_service.py builds them
        # with add_school_id only), so scoped_query(branch_id=...) here would
        # match nothing and silently empty every bell in the school.
        scoped_filter({"user_id": user_id, "read": False}, get_school_id())
    )


@router.get("")
async def get_notifications(
    request: Request,
    page: int = 1,
    limit: int = 20,
    sort: str = DEFAULT_SORT,
    unread_only: bool = False,
    include_digest: bool = True,
):
    """List a user's notifications.

    CALLED WITH NO ARGUMENTS BY `NotificationsPanel`, which is in the header on
    every screen. Every default here is chosen so that call gets exactly what it
    got before this endpoint learned to page — digest rows on page 1, the
    "All Good" fallback, newest first. `tests/backend/api/test_notifications.py`
    pins that; a regression here is a regression everywhere.

    `include_digest=False` is what the All Notifications page passes. The digest
    and fallback rows are synthesised per request and carry no id: a sensible
    empty state inside a dropdown, and a fabricated row among real ones inside a
    table that has a row count, a sort order and a page indicator.
    """
    db = get_db()
    user = get_user(request)
    limit = min(max(limit, 1), 50)
    skip = max(page - 1, 0) * limit
    direction = SORT_ORDERS.get(sort, SORT_ORDERS[DEFAULT_SORT])

    # Persistent notifications from the notifications collection
    base = {"user_id": user["id"]}
    if unread_only:
        base["read"] = False
    # branch-scope: intentional — scoped to the caller's own user_id, which is
    # narrower than any branch. See count_unread() above for why adding a
    # branch_id clause would return nothing.
    query = scoped_filter(base, get_school_id())
    total = await db.notifications.count_documents(query)
    persistent = await db.notifications.find(query, {"_id": 0}).sort("created_at", direction).skip(skip).limit(limit).to_list(limit)

    # The digest and the fallback are always read by construction, so "unread
    # only" can never legitimately be satisfied by one. The two filters compose.
    synthetic_allowed = include_digest and not unread_only

    # Enrich with digest items only on page 1
    digest = []
    if page == 1 and synthetic_allowed:
        role = user["role"]
        today = date.today().strftime("%Y-%m-%d")
        ann_query = scoped_filter({"is_draft": {"$ne": True}}, get_school_id())
        recent_ann = await db.announcements.find(ann_query, {"_id": 0, "title": 1, "created_at": 1, "audience_roles": 1}).sort("created_at", -1).to_list(5)

        if role in ["owner", "admin"]:
            pending = await db.leave_requests.count_documents(scoped_filter({"status": "pending"}, get_school_id()))
            if pending > 0:
                digest.append({"type": "warning", "title": "Pending Leave Requests", "message": f"{pending} leave request(s) awaiting approval", "time": "Now", "read": True, "is_digest": True})
            overdue = await db.fee_transactions.count_documents(scoped_filter({"status": "overdue"}, get_school_id()))
            if overdue > 0:
                digest.append({"type": "error", "title": "Fee Overdue", "message": f"{overdue} fee transaction(s) overdue", "time": "Today", "read": True, "is_digest": True})
            open_facility = await db.facility_requests.count_documents(scoped_filter({"status": {"$in": ["open", "in_progress"]}}, get_school_id()))
            if open_facility > 0:
                digest.append({"type": "info", "title": "Open Facility Requests", "message": f"{open_facility} facility request(s) in progress", "time": "Today", "read": True, "is_digest": True})

        elif role == "teacher":
            staff = await db.staff.find_one(scoped_filter({"user_id": user["id"]}, get_school_id()))
            if staff:
                my_leaves = await db.leave_requests.count_documents(scoped_filter({"staff_id": staff["id"], "status": "pending"}, get_school_id()))
                if my_leaves > 0:
                    digest.append({"type": "info", "title": "Leave Status", "message": "Your leave request is pending approval", "time": "Now", "read": True, "is_digest": True})

        elif role == "student":
            own = await db.students.find_one(scoped_filter({"user_id": user["id"]}, get_school_id()))
            if own:
                records = await db.student_attendance.find(scoped_filter({"student_id": own["id"]}, get_school_id())).to_list(200)
                if records:
                    present = sum(1 for r in records if r["status"] == "present")
                    rate = round(present / len(records) * 100, 1)
                    if rate < 75:
                        digest.append({"type": "error", "title": "Low Attendance", "message": f"Your attendance is {rate}% — below 75% threshold", "time": "Today", "read": True, "is_digest": True})
                overdue = await db.fee_transactions.count_documents(scoped_filter({"student_id": own["id"], "status": {"$in": ["overdue", "pending"]}}, get_school_id()))
                if overdue > 0:
                    digest.append({"type": "warning", "title": "Fee Due", "message": f"{overdue} fee payment(s) pending", "time": "Today", "read": True, "is_digest": True})

        for a in recent_ann[:2]:
            target_roles = a.get("audience_roles", [])
            if not target_roles or "all" in target_roles or role in target_roles:
                digest.append({"type": "info", "title": "Announcement", "message": a["title"], "time": a.get("created_at", "")[:10], "read": True, "is_digest": True})

    digest_count = len(digest)
    combined = persistent + digest
    has_fallback = False
    if not combined and page == 1 and synthetic_allowed:
        has_fallback = True
        combined = [{"type": "success", "title": "All Good", "message": "No pending actions for now", "time": "Now", "read": True, "is_digest": True}]

    return {
        "success": True,
        "data": combined[:limit + digest_count],
        "meta": {
            "page": page,
            "limit": limit,
            "total": total,
            "digest_count": digest_count,
            "has_fallback": has_fallback,
            # Across ALL pages, not this one — so the bell, the panel and the
            # All Notifications page are three readings of one number.
            "unread_total": await count_unread(db, user["id"]),
            "sort": sort if sort in SORT_ORDERS else DEFAULT_SORT,
        },
    }


@router.get("/unread-count")
async def get_unread_count(request: Request):
    db = get_db()
    user = get_user(request)
    return {"success": True, "data": {"unread_count": await count_unread(db, user["id"])}}


@router.patch("/{notification_id}/read")
async def mark_notification_read(notification_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    result = await db.notifications.update_one(
        scoped_filter({"id": notification_id, "user_id": user["id"]}, get_school_id()),
        {"$set": {"read": True, "read_at": datetime.now().isoformat()}}
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Notification not found")
    return {"success": True}


@router.patch("/mark-all-read")
async def mark_all_read(request: Request):
    db = get_db()
    user = get_user(request)
    request_start = datetime.now().isoformat()
    await db.notifications.update_many(
        scoped_filter(
            {"user_id": user["id"], "read": False, "created_at": {"$lt": request_start}},
            get_school_id(),
        ),
        {"$set": {"read": True, "read_at": request_start}}
    )
    return {"success": True}


_SOURCE_COLLECTION = {
    "facility_request":  "facility_requests",
    "incident":          "incidents",
    "announcement":      "announcements",
    "certificate":       "certificates",
    "substitution":      "substitutions",
    "approval_request":  "approval_requests",
    "tech_request":      "tech_requests",
    "leave_request":     "leave_requests",
    "fee_transaction":   "fee_transactions",
    "visitor":           "visitor_log",
}

_ACTION_LABELS = {
    # facility requests (exact strings from issues.py _write_audit calls)
    "facility_request_create":   "Facility request raised",
    "facility_request_update":   "Request updated",
    "facility_request_escalate": "Escalated to owner",
    # tech requests
    "tech_request_create":       "Tech issue raised",
    "tech_request_update":       "Tech issue updated",
    # leave
    "leave_approved":      "Leave request approved",
    "leave_rejected":      "Leave request rejected",
    "leave_created":       "Leave request submitted",
    # incidents
    "incident_created":    "Incident reported",
    "incident_resolved":   "Incident resolved",
    "incident_updated":    "Incident updated",
    # announcements
    "announcement_published": "Announcement published",
    "announcement_created":   "Announcement created",
    # certificates
    "cert_created":        "Certificate requested",
    "cert_approved":       "Certificate approved",
    "cert_rejected":       "Certificate rejected",
    # substitutions
    "substitution_assigned": "Substitute assigned",
    # fees
    "fee_paid":            "Payment received",
    "fee_overdue":         "Marked overdue",
    # approvals
    "approval_created":    "Approval request submitted",
    "approval_approved":   "Request approved",
    "approval_rejected":   "Request rejected",
}


def _build_timeline_from_record(rec: dict, source_type: str) -> list[dict]:
    """Synthesize baseline creation event from source record fields."""
    events = []
    created_at = rec.get("created_at") or rec.get("applied_at") or rec.get("reported_at") or ""
    if created_at:
        label_map = {
            "leave_request":   "Leave request submitted",
            "facility_request": "Facility request raised",
            "incident":        "Incident reported",
            "announcement":    "Announcement created",
            "certificate":     "Certificate requested",
            "substitution":    "Substitution created",
            "approval_request": "Approval request submitted",
            "tech_request":    "Tech request raised",
            "fee_transaction": "Fee transaction created",
            "visitor":         "Visitor checked in",
        }
        events.append({
            "event_type": "created",
            "label": label_map.get(source_type, "Record created"),
            "detail": None,
            "actor": rec.get("created_by_name") or rec.get("staff_name") or rec.get("student_name") or rec.get("requested_by") or "",
            "actor_role": rec.get("created_by_role") or "",
            "timestamp": created_at,
            "is_current": False,
        })
    return events


def _build_current_status_event(rec: dict, source_type: str) -> dict | None:
    """Build a terminal event from the record's current status."""
    status = rec.get("status", "")
    if not status or status in ("pending", "open", "active"):
        return None
    status_label = {
        "approved": "Approved",
        "rejected": "Rejected",
        "resolved": "Resolved",
        "closed":   "Closed",
        "paid":     "Payment received",
        "overdue":  "Marked overdue",
        "in_progress": "Work started",
        "assigned": "Substitute assigned",
        "published": "Published",
        "completed": "Completed",
    }.get(status, status.replace("_", " ").title())

    timestamp = (
        rec.get("resolved_at") or rec.get("approved_at") or
        rec.get("rejected_at") or rec.get("paid_at") or
        rec.get("updated_at") or rec.get("modified_at") or ""
    )
    detail = rec.get("rejection_reason") or rec.get("resolution_notes") or rec.get("resolution") or None
    actor = (
        rec.get("approved_by_name") or rec.get("resolved_by_name") or
        rec.get("rejected_by_name") or rec.get("assigned_by_name") or ""
    )
    return {
        "event_type": "status_change",
        "label": status_label,
        "detail": detail,
        "actor": actor,
        "actor_role": rec.get("approved_by_role") or rec.get("resolved_by_role") or "",
        "timestamp": timestamp,
        "is_current": True,
    }


def _source_summary(rec: dict, source_type: str) -> dict:
    """Extract key display fields from a source record."""
    status = rec.get("status", "")
    base = {"source_type": source_type, "status": status, "id": rec.get("id", "")}

    if source_type == "leave_request":
        return {**base, "title": f"{rec.get('leave_type', 'Leave')} request", "subtitle": f"{rec.get('start_date', '')} → {rec.get('end_date', '')}", "detail": rec.get("reason", "")}
    if source_type == "facility_request":
        return {**base, "title": rec.get("title") or rec.get("description", "Facility request"), "subtitle": f"Location: {rec.get('location', '—')}", "detail": rec.get("description", "")}
    if source_type == "incident":
        return {**base, "title": rec.get("title") or rec.get("incident_type", "Incident"), "subtitle": f"Severity: {rec.get('severity', '—')}", "detail": rec.get("description", "")}
    if source_type == "announcement":
        audience = ", ".join(rec.get("audience_roles") or ["All"])
        return {**base, "title": rec.get("title", "Announcement"), "subtitle": f"Audience: {audience}", "detail": rec.get("body") or rec.get("content", "")}
    if source_type == "certificate":
        return {**base, "title": f"{rec.get('cert_type') or rec.get('type', 'Certificate')} certificate", "subtitle": f"Student: {rec.get('student_name', '—')}", "detail": rec.get("purpose") or rec.get("reason", "")}
    if source_type == "substitution":
        return {**base, "title": f"Period {rec.get('period_number', '—')} substitution", "subtitle": f"Substitute: {rec.get('substitute_teacher_name', '—')}", "detail": f"Class: {rec.get('class_name', '—')}"}
    if source_type in ("tech_request", "approval_request"):
        return {**base, "title": rec.get("title") or rec.get("description", source_type.replace("_", " ").title()), "subtitle": rec.get("category") or rec.get("type", ""), "detail": rec.get("description", "")}
    if source_type == "fee_transaction":
        return {**base, "title": f"Fee — ₹{rec.get('amount', 0):,}", "subtitle": f"Student: {rec.get('student_name', '—')}", "detail": rec.get("fee_type", "")}
    if source_type == "visitor":
        return {**base, "title": f"Visitor: {rec.get('visitor_name', '—')}", "subtitle": f"Purpose: {rec.get('purpose', '—')}", "detail": ""}
    return {**base, "title": rec.get("title") or source_type.replace("_", " ").title(), "subtitle": "", "detail": ""}


@router.get("/{notification_id}/detail")
async def get_notification_detail(notification_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    school_id = get_school_id()

    notif = await db.notifications.find_one(
        scoped_filter({"id": notification_id, "user_id": user["id"]}, school_id), {"_id": 0}
    )
    if not notif:
        raise HTTPException(404, "Notification not found")

    # Mark read as side-effect
    if not notif.get("read"):
        await db.notifications.update_one(
            {"id": notification_id},
            {"$set": {"read": True, "read_at": datetime.now().isoformat()}}
        )

    source_type = notif.get("source_record_type") or ""
    source_id   = notif.get("source_record_id") or ""
    source = None
    timeline = []

    if source_type and source_id:
        coll_name = _SOURCE_COLLECTION.get(source_type)
        if coll_name:
            coll = getattr(db, coll_name, None)
            if coll is not None:
                source = await coll.find_one(
                    scoped_filter({"id": source_id}, school_id), {"_id": 0}
                )

        if source:
            # Baseline creation event from the record itself
            timeline = _build_timeline_from_record(source, source_type)

            # Audit log events for this record
            audit_entries = await db.audit_logs.find(
                scoped_filter({"entity_id": source_id}, school_id), {"_id": 0}
            ).sort("created_at", 1).to_list(50)

            for entry in audit_entries:
                action = entry.get("action", "")
                # Skip create events — already synthesised from record itself
                if action in ("facility_request_create", "tech_request_create"):
                    continue
                label = _ACTION_LABELS.get(action) or action.replace("_", " ").title()
                changes = entry.get("changes") or {}
                # updates wrap their payload in a nested "changes" key; escalate/create are flat
                inner = changes.get("changes") or changes
                detail_parts = []
                status_val = inner.get("status")
                if status_val:
                    detail_parts.append(f"Status → {status_val.replace('_', ' ')}")
                priority_val = inner.get("priority") or changes.get("priority")
                if priority_val and not status_val:
                    detail_parts.append(f"Priority → {priority_val}")
                for reason_key in ("rejection_reason", "escalation_reason", "resolution"):
                    val = inner.get(reason_key) or changes.get(reason_key)
                    if val:
                        detail_parts.append(val)
                        break
                timeline.append({
                    "event_type": action,
                    "label": label,
                    "detail": "; ".join(detail_parts) or None,
                    "actor": entry.get("changed_by_name") or entry.get("changed_by") or "",
                    "actor_role": entry.get("changed_by_role") or "",
                    "timestamp": entry.get("created_at") or entry.get("timestamp") or "",
                    "is_current": False,
                })

            # Terminal status event from record
            terminal = _build_current_status_event(source, source_type)
            if terminal and terminal.get("timestamp"):
                timeline.append(terminal)

            # Deduplicate by timestamp+label, keep order
            seen = set()
            deduped = []
            for ev in timeline:
                key = (ev["timestamp"], ev["label"])
                if key not in seen:
                    seen.add(key)
                    deduped.append(ev)
            timeline = sorted(deduped, key=lambda e: e["timestamp"])
            if timeline:
                timeline[-1]["is_current"] = True

    return {
        "success": True,
        "data": {
            "notification": notif,
            "source": _source_summary(source, source_type) if source else None,
            "timeline": timeline,
        }
    }


@router.post("")
async def create_notification(request: Request, user: dict = Depends(require_role("owner", "admin"))):
    """Internal endpoint: create a notification for a specific user."""
    db = get_db()
    body = await request.json()
    if not body.get("user_id") or not body.get("title") or not body.get("message"):
        raise HTTPException(400, "user_id, title, and message are required")
    ok = await create_persistent_notification(
        db,
        user_id=body["user_id"],
        notification_type=body.get("type", "info"),
        title=body["title"],
        message=body["message"],
        source_id=body.get("source_record_id", ""),
        source_type=body.get("source_record_type", ""),
    )
    if not ok:
        raise HTTPException(503, "Notification could not be created")
    created = await db.notifications.find_one(
        scoped_filter(
            {
                "user_id": body["user_id"],
                "title": body["title"],
                "message": body["message"],
            },
            get_school_id(),
        ),
        {"_id": 0},
    )
    return {"success": True, "data": created}
