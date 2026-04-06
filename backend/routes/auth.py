from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    role: str
    username: str = ""
    password: str = ""


@router.post("/login")
async def login(body: LoginRequest):
    db = get_db()

    # Admin and Owner — free access, no password required
    if body.role in ["owner", "admin"]:
        free_users = {
            "owner": {"id": "user-owner-001", "name": "Aman", "role": "owner", "initials": "A"},
            "admin": {"id": "user-admin-001", "name": "Priya Sharma", "role": "admin", "initials": "PS"},
        }
        return {"success": True, "user": free_users[body.role]}

    # Teacher login — match by name (case-insensitive) + password
    if body.role == "teacher":
        auth = await db.auth_users.find_one(
            {"role": "teacher", "username": {"$regex": f"^{body.username.strip()}$", "$options": "i"}},
            {"_id": 0}
        )
        if not auth:
            raise HTTPException(401, "Teacher not found")
        if auth["password"] != body.password:
            raise HTTPException(401, "Incorrect password")
        return {"success": True, "user": auth["user_info"]}

    # Student login — match by admission_number + password (password = admission_number)
    if body.role == "student":
        auth = await db.auth_users.find_one(
            {"role": "student", "username": body.username.strip().upper()},
            {"_id": 0}
        )
        if not auth:
            raise HTTPException(401, "Student not found. Check admission number.")
        if auth["password"] != body.password.strip().upper():
            raise HTTPException(401, "Incorrect password. Password is your admission number.")
        return {"success": True, "user": auth["user_info"]}

    raise HTTPException(400, "Invalid role")


@router.get("/seed-status")
async def seed_status():
    db = get_db()
    count = await db.auth_users.count_documents({})
    classes = await db.classes.count_documents({})
    students = await db.students.count_documents({})
    staff = await db.staff.count_documents({})
    return {"auth_users": count, "classes": classes, "students": students, "staff": staff}
