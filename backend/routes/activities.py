"""School activities — houses, student positions, sports teams."""
from __future__ import annotations

from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional

from database import get_db
from middleware.auth import require_role
from tenant import get_school_id, scoped_filter
from services.audit_service import write_audit

router = APIRouter(prefix="/api/activities", tags=["activities"])

ADMIN_ROLES = {"owner", "admin"}
READ_ROLES = {"owner", "admin", "teacher"}

HOUSE_COLOURS = {"Blue", "Green", "Red", "Yellow"}

VALID_POSITIONS = {
    "Head Boy", "Head Girl",
    "Vice Head Boy", "Vice Head Girl",
    "House Captain", "Vice House Captain",
    "Sports Captain", "Vice Sports Captain",
    "Class Monitor", "Assistant Monitor",
    "Prefect", "Council Member",
}

VALID_SPORTS = {
    "Cricket", "Football", "Basketball", "Volleyball",
    "Kabaddi", "Badminton", "Chess", "Table Tennis",
    "Debate", "Quiz", "Athletics", "Swimming",
    "Kho-Kho", "Handball",
}


def _scope(extra: dict | None = None) -> dict:
    return scoped_filter(extra or {}, get_school_id())


# ─────────────────── Houses ────────────────────────────────────────────────────

@router.get("/houses")
async def list_houses(request: Request, user: dict = Depends(require_role("owner", "admin", "teacher"))):
    db = get_db()
    houses = await db.houses.find(_scope(), {"_id": 0}).to_list(10)
    if not houses:
        # Seed defaults if none exist
        houses = []
        for colour in sorted(HOUSE_COLOURS):
            doc = {
                "_id": str(uuid.uuid4()),
                "id": str(uuid.uuid4()),
                "schoolId": get_school_id(),
                "name": colour,
                "colour": colour,
                "points": 0,
                "created_at": datetime.now().isoformat(),
            }
            await db.houses.insert_one(doc)
            doc.pop("_id", None)
            houses.append(doc)
    return {"success": True, "data": houses}


class HousePointsBody(BaseModel):
    delta: int
    reason: Optional[str] = None


@router.post("/houses/{house_id}/points")
async def award_points(house_id: str, body: HousePointsBody, request: Request, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    house = await db.houses.find_one(_scope({"id": house_id}), {"_id": 0})
    if not house:
        raise HTTPException(404, "House not found")
    new_points = max(0, house.get("points", 0) + body.delta)
    await db.houses.update_one(
        _scope({"id": house_id}),
        {"$set": {"points": new_points, "updated_at": datetime.now().isoformat()}},
    )
    log = {
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": get_school_id(),
        "house_id": house_id,
        "house_name": house.get("name"),
        "delta": body.delta,
        "new_total": new_points,
        "reason": body.reason,
        "awarded_by": user.get("id"),
        "created_at": datetime.now().isoformat(),
    }
    await db.house_points_log.insert_one(log)
    await write_audit(
        db,
        action="house_points_award",
        entity_id=house_id,
        collection="houses",
        changed_by=user.get("id"),
        changed_by_role=user.get("role", ""),
        school_id=get_school_id(),
        branch_id=user.get("branch_id", ""),
        changes={"delta": body.delta, "new_total": new_points, "reason": body.reason},
    )
    return {"success": True, "data": {"points": new_points}}


@router.get("/houses/{house_id}/points-log")
async def house_points_log(house_id: str, request: Request, user: dict = Depends(require_role("owner", "admin", "teacher"))):
    db = get_db()
    logs = await db.house_points_log.find(
        _scope({"house_id": house_id}), {"_id": 0}
    ).sort("created_at", -1).limit(50).to_list(50)
    return {"success": True, "data": logs}


# ─────────────────── Student Positions ────────────────────────────────────────

class PositionBody(BaseModel):
    student_id: str
    student_name: str
    position: str
    house: Optional[str] = None
    academic_year: Optional[str] = None
    notes: Optional[str] = None


@router.get("/positions")
async def list_positions(request: Request, academic_year: str = None, user: dict = Depends(require_role("owner", "admin", "teacher"))):
    db = get_db()
    query = {}
    if academic_year:
        query["academic_year"] = academic_year
    positions = await db.student_positions.find(_scope(query), {"_id": 0}).sort("position", 1).to_list(100)
    return {"success": True, "data": positions}


@router.post("/positions")
async def assign_position(body: PositionBody, request: Request, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    if body.position not in VALID_POSITIONS:
        raise HTTPException(400, f"Invalid position. Valid: {sorted(VALID_POSITIONS)}")
    existing = await db.student_positions.find_one(
        _scope({"position": body.position, "is_active": True}), {"_id": 0}
    )
    if existing:
        await db.student_positions.update_one(
            _scope({"id": existing["id"]}),
            {"$set": {"is_active": False, "ended_at": datetime.now().isoformat()}},
        )
    doc = {
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": get_school_id(),
        "student_id": body.student_id,
        "student_name": body.student_name,
        "position": body.position,
        "house": body.house,
        "academic_year": body.academic_year,
        "notes": body.notes,
        "is_active": True,
        "assigned_by": user.get("id"),
        "created_at": datetime.now().isoformat(),
    }
    await db.student_positions.insert_one(doc)
    await write_audit(
        db,
        action="student_position_assign",
        entity_id=doc["id"],
        collection="student_positions",
        changed_by=user.get("id"),
        changed_by_role=user.get("role", ""),
        school_id=get_school_id(),
        branch_id=user.get("branch_id", ""),
        changes={"student_id": body.student_id, "position": body.position},
    )
    doc.pop("_id", None)
    return {"success": True, "data": doc}


@router.delete("/positions/{position_id}")
async def remove_position(position_id: str, request: Request, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    pos = await db.student_positions.find_one(_scope({"id": position_id}), {"_id": 0})
    if not pos:
        raise HTTPException(404, "Position not found")
    await db.student_positions.update_one(
        _scope({"id": position_id}),
        {"$set": {"is_active": False, "ended_at": datetime.now().isoformat()}},
    )
    await write_audit(
        db,
        action="student_position_remove",
        entity_id=position_id,
        collection="student_positions",
        changed_by=user.get("id"),
        changed_by_role=user.get("role", ""),
        school_id=get_school_id(),
        branch_id=user.get("branch_id", ""),
        changes={"is_active": False},
    )
    return {"success": True}


# ─────────────────── Sports Teams ─────────────────────────────────────────────

class TeamBody(BaseModel):
    name: str
    sport: str
    captain_student_id: Optional[str] = None
    captain_name: Optional[str] = None
    members: Optional[List[str]] = None


class TeamMemberBody(BaseModel):
    student_id: str
    student_name: str
    role: str = "member"


@router.get("/teams")
async def list_teams(request: Request, user: dict = Depends(require_role("owner", "admin", "teacher"))):
    db = get_db()
    teams = await db.sports_teams.find(_scope({"is_active": True}), {"_id": 0}).sort("sport", 1).to_list(50)
    return {"success": True, "data": teams}


@router.post("/teams")
async def create_team(body: TeamBody, request: Request, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    if body.sport not in VALID_SPORTS:
        raise HTTPException(400, f"Invalid sport. Valid: {sorted(VALID_SPORTS)}")
    doc = {
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": get_school_id(),
        "name": body.name,
        "sport": body.sport,
        "captain_student_id": body.captain_student_id,
        "captain_name": body.captain_name,
        "members": body.members or [],
        "is_active": True,
        "created_by": user.get("id"),
        "created_at": datetime.now().isoformat(),
    }
    await db.sports_teams.insert_one(doc)
    await write_audit(
        db,
        action="sports_team_create",
        entity_id=doc["id"],
        collection="sports_teams",
        changed_by=user.get("id"),
        changed_by_role=user.get("role", ""),
        school_id=get_school_id(),
        branch_id=user.get("branch_id", ""),
        changes={"name": body.name, "sport": body.sport},
    )
    doc.pop("_id", None)
    return {"success": True, "data": doc}


@router.patch("/teams/{team_id}")
async def update_team(team_id: str, request: Request, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    team = await db.sports_teams.find_one(_scope({"id": team_id}), {"_id": 0})
    if not team:
        raise HTTPException(404, "Team not found")
    body = await request.json()
    allowed = {"name", "captain_student_id", "captain_name", "members", "is_active"}
    update = {k: v for k, v in body.items() if k in allowed}
    update["updated_at"] = datetime.now().isoformat()
    await db.sports_teams.update_one(_scope({"id": team_id}), {"$set": update})
    await write_audit(
        db,
        action="sports_team_update",
        entity_id=team_id,
        collection="sports_teams",
        changed_by=user.get("id"),
        changed_by_role=user.get("role", ""),
        school_id=get_school_id(),
        branch_id=user.get("branch_id", ""),
        changes=update,
    )
    return {"success": True}


@router.delete("/teams/{team_id}")
async def delete_team(team_id: str, request: Request, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    await db.sports_teams.update_one(
        _scope({"id": team_id}),
        {"$set": {"is_active": False, "updated_at": datetime.now().isoformat()}},
    )
    await write_audit(
        db,
        action="sports_team_delete",
        entity_id=team_id,
        collection="sports_teams",
        changed_by=user.get("id"),
        changed_by_role=user.get("role", ""),
        school_id=get_school_id(),
        branch_id=user.get("branch_id", ""),
        changes={"is_active": False},
    )
    return {"success": True}
