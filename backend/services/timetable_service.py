from __future__ import annotations

import re
from typing import Any


TIMETABLE_FIELDS = {
    "class_id",
    "subject_id",
    "teacher_id",
    "day_of_week",
    "period_number",
    "start_time",
    "end_time",
    "room",
}
_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class TimetableValidationError(ValueError):
    pass


class TimetableConflictError(ValueError):
    pass


def normalise_timetable_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a safe, validated timetable payload without persistence fields."""
    slot = {key: payload.get(key) for key in TIMETABLE_FIELDS}
    for key in ("class_id", "subject_id"):
        value = slot.get(key)
        if not isinstance(value, str) or not value.strip():
            raise TimetableValidationError(f"{key} is required")
        slot[key] = value.strip()

    teacher_id = slot.get("teacher_id")
    if teacher_id is not None and not isinstance(teacher_id, str):
        raise TimetableValidationError("teacher_id must be a string")
    slot["teacher_id"] = (teacher_id or "").strip()

    room = slot.get("room")
    if room is not None and not isinstance(room, str):
        raise TimetableValidationError("room must be a string")
    slot["room"] = (room or "").strip()

    day = slot.get("day_of_week")
    if isinstance(day, bool) or not isinstance(day, int) or not 0 <= day <= 6:
        raise TimetableValidationError("day_of_week must be an integer from 0 to 6")

    period = slot.get("period_number")
    if isinstance(period, bool) or not isinstance(period, int) or not 1 <= period <= 20:
        raise TimetableValidationError("period_number must be an integer from 1 to 20")

    start_time = slot.get("start_time") or ""
    end_time = slot.get("end_time") or ""
    if bool(start_time) != bool(end_time):
        raise TimetableValidationError("start_time and end_time must be provided together")
    if start_time:
        if not isinstance(start_time, str) or not _TIME_RE.fullmatch(start_time):
            raise TimetableValidationError("start_time must use HH:MM format")
        if not isinstance(end_time, str) or not _TIME_RE.fullmatch(end_time):
            raise TimetableValidationError("end_time must use HH:MM format")
        if start_time >= end_time:
            raise TimetableValidationError("end_time must be later than start_time")
    slot["start_time"] = start_time
    slot["end_time"] = end_time
    return slot


async def validate_timetable_references(db, slot: dict[str, Any]) -> None:
    class_doc = await db.classes.find_one({"id": slot["class_id"]}, {"_id": 0, "id": 1})
    if not class_doc:
        raise TimetableValidationError("Class not found")

    subject = await db.subjects.find_one(
        {"id": slot["subject_id"], "class_id": slot["class_id"]},
        {"_id": 0, "id": 1},
    )
    if not subject:
        raise TimetableValidationError("Subject does not belong to the selected class")

    if slot["teacher_id"]:
        teacher = await db.staff.find_one(
            {"id": slot["teacher_id"]}, {"_id": 0, "id": 1, "staff_type": 1}
        )
        if not teacher:
            raise TimetableValidationError("Teacher not found")
        if teacher.get("staff_type") != "teacher":
            raise TimetableValidationError("Selected staff member is not a teacher")


async def ensure_timetable_slot_available(
    db,
    slot: dict[str, Any],
    *,
    exclude_slot_id: str | None = None,
) -> None:
    base = {"day_of_week": slot["day_of_week"], "period_number": slot["period_number"]}

    rows = await db.timetable_slots.find(
        base, {"_id": 0, "id": 1, "class_id": 1, "teacher_id": 1, "room": 1}
    ).to_list(500)
    rows = [row for row in rows if row.get("id") != exclude_slot_id]

    if any(row.get("class_id") == slot["class_id"] for row in rows):
        raise TimetableConflictError("Class already has a subject in this period")

    if slot["teacher_id"]:
        if any(row.get("teacher_id") == slot["teacher_id"] for row in rows):
            raise TimetableConflictError("Teacher is already assigned in this period")

    if slot["room"]:
        room_key = slot["room"].casefold()
        if any(str(row.get("room") or "").strip().casefold() == room_key for row in rows):
            raise TimetableConflictError("Room is already assigned in this period")


async def validate_timetable_slot(
    db,
    payload: dict[str, Any],
    *,
    exclude_slot_id: str | None = None,
) -> dict[str, Any]:
    slot = normalise_timetable_fields(payload)
    await validate_timetable_references(db, slot)
    await ensure_timetable_slot_available(db, slot, exclude_slot_id=exclude_slot_id)
    return slot
