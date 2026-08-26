from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, field_validator
from pymongo.errors import DuplicateKeyError

from pagination import clamp_page, clamp_page_size
from database import get_db
from services import audit_changes
from services.audit_service import write_audit
from services.profile_matrix import PROFILE_MATRIX, profile_of
from middleware.auth import require_school_staff
from services.sse import (
    KEEPALIVE_COMMENT,
    connect as sse_connect,
    disconnect as sse_disconnect,
    encode_sse,
    is_connected as sse_is_connected,
    normalize_session_id,
    publish as sse_publish,
)
from tenant import add_school_id, get_school_id, scoped_query


router = APIRouter(prefix="/api/messaging", tags=["messaging"])
require_messaging_profile = require_school_staff

# 2026-08-12 - OPENED TO THE WHOLE STAFF ROOM, on Abhimanyu's instruction.
#
# This was four profiles: the owner, the principal, the accountant head and the
# management head. Everybody else who works at the school could see the tool and had
# nobody in it. The school asked for what people already expect from a messaging app:
# any colleague can reach any colleague, and they can make groups.
#
# So membership is now a fact about the person, not a list of job titles: **you are in
# if you work here**. The owner, every admin profile and every teacher. A new member of
# staff appears the moment their login exists, without anybody editing this file, which
# is the same lesson R2-10 below already paid for once.
#
# WHO IS STILL OUT, and this is the line that must not move: **students and guardians.**
# They hold logins on this platform too. Messaging is the staff room, and a child or a
# parent inside it is a different product with different consent behind it. Roles are
# named here rather than "anyone with a login" precisely so that widening it again has
# to be a decision somebody writes down.
STAFF_ROLES = ("owner", "admin", "teacher")

# 2026-08-14 - NARROWED AGAIN, to whoever's release has actually landed.
#
# The instruction above ("you are in if you work here") was right about the RULE and wrong
# about the TIMING. Logins exist today for people whose release has not happened: seven
# office accounts created by migration 041 and four shared desks. None of them has ever
# been used, but every one of them was showing in the colleague list, so the school could
# see and try to message colleagues who cannot sign in. A contact who can never reply is
# worse than an absent one: it looks like they are ignoring you.
#
# Abhimanyu, 2026-08-14: **a profile appears in the staff room when its release lands.
# Not before, not after.** Today that is the four of Release 2, and this file does not
# name them.
#
# The test is the SAME question `profile_matrix` already answers, so nothing here needs
# maintaining and nobody has to remember to edit it: a profile appears when its row is
# marked `live`. Switching a profile on for its release makes it appear in the staff room
# on the same day, automatically, which is exactly what "along with the release" means.
#
# STAFF_ROLES stays as the floor underneath. Both filters apply. A profile that is
# somehow marked live but is not a staff role still does not get in, so a mistake in the
# matrix cannot put a child in the staff room.
def _release_has_landed(role: object, sub_category: object) -> bool:
    """True when this person's profile is switched on, per the permission table.

    Default deny. An unrecognised profile, or one whose release has not happened, is
    not a colleague you can message yet.
    """
    profile = profile_of({"role": role, "sub_category": sub_category})
    if not profile:
        return False
    return PROFILE_MATRIX[profile]["status"] == "live"

# R2-10, 2026-08-11 - REMOVED, and do not bring it back.
#
# This used to be a set of four usernames - aman.litt, adesh.singh, sonu.ruhal,
# lalit.thomas - matched against `username_lower`. The logins actually in production are
# `accountant` and `management`, and the other two are whatever they were created as, so
# the lookup matched NOBODY and the colleague list truthfully reported "0 colleagues
# available". That is the empty screen in the owner's screenshots.
#
# Renaming the logins (R2-11) would have made this work again by accident, which is
# precisely the wrong reason for it to work: the next employee to join would still have
# been invisible, and nobody would have known why.
#
# The lookup now asks the question the code actually wanted: WHO HOLDS THIS JOB. A login
# name is a way of typing your name in, not a statement of who somebody is.
#
# Both document shapes are matched. `auth_users` normally carries the person inside
# `user_info`, and `routes/auth.py` falls back to a top-level `role` for older records
# (see `login`), so a lookup that read only one of the two would drop whoever happens to
# be stored the other way. Every row is checked against STAFF_ROLES afterwards regardless,
# so a loose query cannot widen who appears.
STAFF_ROLE_FILTER = [
    {"user_info.role": {"$in": list(STAFF_ROLES)}},
    {"role": {"$in": list(STAFF_ROLES)}},
]
MAX_MESSAGE_LENGTH = 4000
MAX_GROUP_NAME_LENGTH = 80
# The whole staff room has to fit. There are 96 staff logins today and the old caps of
# 50 contacts and 20 presence rows were set when four people could message each other.
# A cap that silently truncates a colleague list is indistinguishable from that person
# having left, so these are set well above the school's size and the count is returned.
MAX_STAFF = 1000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _channel(user_id: str) -> str:
    return f"messaging:{user_id}"


def _clean_text(value: str, *, field: str, max_length: int) -> str:
    cleaned = re.sub(r"\r\n?", "\n", value or "").strip()
    if not cleaned:
        raise ValueError(f"{field} is required")
    if len(cleaned) > max_length:
        raise ValueError(f"{field} must be {max_length} characters or fewer")
    return cleaned


class DirectThreadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, value: str) -> str:
        return _clean_text(value, field="User", max_length=128)


class GroupThreadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    member_ids: list[str]

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _clean_text(value, field="Group name", max_length=MAX_GROUP_NAME_LENGTH)

    @field_validator("member_ids")
    @classmethod
    def validate_members(cls, value: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))
        if not cleaned:
            raise ValueError("Choose at least one group member")
        return cleaned


class GroupThreadUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    member_ids: Optional[list[str]] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _clean_text(value, field="Group name", max_length=MAX_GROUP_NAME_LENGTH)

    @field_validator("member_ids")
    @classmethod
    def validate_members(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        if value is None:
            return None
        cleaned = list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))
        if not cleaned:
            raise ValueError("Choose at least one group member")
        return cleaned


class MessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    reply_to_id: Optional[str] = None

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _clean_text(value, field="Message", max_length=MAX_MESSAGE_LENGTH)


class MessageEditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _clean_text(value, field="Message", max_length=MAX_MESSAGE_LENGTH)


def _scope(query: dict, user: dict) -> dict:
    return scoped_query(query, branch_id=user.get("branch_id"))


async def _staff_contacts(db, user: dict) -> list[dict]:
    """Everyone who works at the school and can sign in.

    Three filters do the work, and none of them is a list anybody has to maintain:

    * the login must be active, which is why the 21 staff who left in August drop out
      by themselves rather than lingering in a colleague list as people to message
    * the role must be one of :data:`STAFF_ROLES`, which keeps students and guardians
      out even though they hold logins on this same platform
    * the person's release must have landed, per :func:`_release_has_landed`. Logins
      exist for people who cannot yet sign in, and a colleague who can never answer is
      worse than one who is simply absent.
    """
    query = {
        "schoolId": get_school_id(),
        "is_active": {"$ne": False},
        "$or": STAFF_ROLE_FILTER,
    }
    if user.get("branch_id"):
        query["user_info.branch_id"] = user["branch_id"]
    rows = await db.auth_users.find(
        query,
        {"_id": 0, "id": 1, "role": 1, "sub_category": 1, "user_info": 1},
    ).to_list(MAX_STAFF)
    contacts = []
    for row in rows:
        info = row.get("user_info") or {}
        role = info.get("role") or row.get("role")
        sub_category = (
            info.get("sub_category")
            or row.get("sub_category")
            or ("owner" if role == "owner" else None)
        )
        user_id = info.get("id") or row.get("id")
        if not user_id or role not in STAFF_ROLES:
            continue
        if not _release_has_landed(role, sub_category):
            continue
        contacts.append({
            "id": user_id,
            "name": info.get("name") or "School profile",
            "role": role,
            "sub_category": sub_category,
        })
    contacts.sort(key=lambda item: (item["role"] != "owner", item["name"].casefold()))
    return contacts


async def _contact_map(db, user: dict) -> dict[str, dict]:
    return {contact["id"]: contact for contact in await _staff_contacts(db, user)}


async def _require_contact(db, user_id: str, actor: dict) -> dict:
    contact = (await _contact_map(db, actor)).get(user_id)
    if not contact:
        raise HTTPException(404, "Messaging profile not found")
    return contact


async def _thread_for_member(db, thread_id: str, user: dict) -> dict:
    thread = await db.platform_message_threads.find_one(
        _scope({"id": thread_id, "member_ids": user["id"]}, user), {"_id": 0}
    )
    if not thread:
        raise HTTPException(404, "Conversation not found")
    return thread


async def _publish_to_users(user_ids: list[str], event: dict) -> None:
    for user_id in set(user_ids):
        await sse_publish(_channel(user_id), event)


def _receipt_status(message: dict, receipts: list[dict]) -> dict:
    recipients = [
        row for row in receipts if row.get("user_id") != message.get("sender_id")
    ]
    if not recipients:
        return {"status": "sent", "delivered_count": 0, "read_count": 0, "recipient_count": 0}
    delivered = sum(1 for row in recipients if row.get("delivered_at"))
    read = sum(1 for row in recipients if row.get("read_at"))
    status = "read" if read == len(recipients) else "delivered" if delivered == len(recipients) else "sent"
    return {
        "status": status,
        "delivered_count": delivered,
        "read_count": read,
        "recipient_count": len(recipients),
    }


async def _serialize_thread(
    thread: dict,
    *,
    user_id: str,
    contacts: dict[str, dict],
    unread_count: int = 0,
    last_receipts: Optional[list[dict]] = None,
) -> dict:
    members = [contacts[member_id] for member_id in thread.get("member_ids", []) if member_id in contacts]
    if thread.get("kind") == "direct":
        other = next((member for member in members if member["id"] != user_id), None)
        title = (other or {}).get("name", "Conversation")
    else:
        title = thread.get("name") or "Group"
    data = {
        **{key: value for key, value in thread.items() if key != "_id"},
        "title": title,
        "members": members,
        "unread_count": unread_count,
    }
    last = thread.get("last_message")
    if last and last.get("sender_id") == user_id:
        data["last_message"]["receipt"] = _receipt_status(last, last_receipts or [])
    return data


@router.get("/contacts")
async def list_contacts(user: dict = Depends(require_messaging_profile)):
    db = get_db()
    contacts = await _staff_contacts(db, user)
    if user["id"] not in {contact["id"] for contact in contacts}:
        raise HTTPException(403, "Messaging is for school staff")
    presence_rows = await db.platform_message_presence.find(
        _scope({"user_id": {"$in": [contact["id"] for contact in contacts]}}, user), {"_id": 0}
    ).to_list(MAX_STAFF)
    presence = {row["user_id"]: row for row in presence_rows}
    data = []
    for contact in contacts:
        row = presence.get(contact["id"], {})
        data.append({
            **contact,
            "online": sse_is_connected(_channel(contact["id"])),
            "last_seen_at": row.get("last_seen_at"),
            "is_self": contact["id"] == user["id"],
        })
    return {"success": True, "data": data, "meta": {"count": len(data)}}


@router.get("/threads")
async def list_threads(user: dict = Depends(require_messaging_profile)):
    db = get_db()
    await _require_contact(db, user["id"], user)
    contacts = await _contact_map(db, user)
    threads = await db.platform_message_threads.find(
        _scope({"member_ids": user["id"]}, user), {"_id": 0}
    ).sort("updated_at", -1).to_list(100)
    thread_ids = [thread["id"] for thread in threads]
    unread_rows = await db.platform_message_receipts.find(
        _scope({"thread_id": {"$in": thread_ids}, "user_id": user["id"], "read_at": None}, user),
        {"_id": 0, "thread_id": 1},
    ).to_list(1000)
    unread_by_thread: dict[str, int] = {}
    for row in unread_rows:
        unread_by_thread[row["thread_id"]] = unread_by_thread.get(row["thread_id"], 0) + 1
    last_ids = [(thread.get("last_message") or {}).get("id") for thread in threads]
    last_ids = [message_id for message_id in last_ids if message_id]
    receipt_rows = await db.platform_message_receipts.find(
        _scope({"message_id": {"$in": last_ids}}, user), {"_id": 0}
    ).to_list(500)
    receipts_by_message: dict[str, list[dict]] = {}
    for row in receipt_rows:
        receipts_by_message.setdefault(row["message_id"], []).append(row)
    data = [
        await _serialize_thread(
            thread,
            user_id=user["id"],
            contacts=contacts,
            unread_count=unread_by_thread.get(thread["id"], 0),
            last_receipts=receipts_by_message.get((thread.get("last_message") or {}).get("id"), []),
        )
        for thread in threads
    ]
    return {
        "success": True,
        "data": data,
        "meta": {"count": len(data), "unread_total": sum(unread_by_thread.values())},
    }


@router.post("/threads/direct", status_code=201)
async def create_direct_thread(
    body: DirectThreadRequest,
    user: dict = Depends(require_messaging_profile),
):
    if body.user_id == user["id"]:
        raise HTTPException(400, "Choose another profile")
    db = get_db()
    await _require_contact(db, user["id"], user)
    await _require_contact(db, body.user_id, user)
    member_ids = sorted([user["id"], body.user_id])
    direct_key = ":".join(member_ids)
    existing = await db.platform_message_threads.find_one(
        _scope({"kind": "direct", "direct_key": direct_key}, user), {"_id": 0}
    )
    contacts = await _contact_map(db, user)
    if existing:
        return {
            "success": True,
            "data": await _serialize_thread(existing, user_id=user["id"], contacts=contacts),
            "meta": {"created": False},
        }
    now = _now()
    thread = {
        "id": str(uuid.uuid4()),
        "kind": "direct",
        "direct_key": direct_key,
        "branch_id": user.get("branch_id"),
        "member_ids": member_ids,
        "created_by": user["id"],
        "created_at": now,
        "updated_at": now,
        "last_message": None,
    }
    thread = add_school_id(thread)
    try:
        await db.platform_message_threads.insert_one(thread)
    except DuplicateKeyError:
        existing = await db.platform_message_threads.find_one(
            _scope({"kind": "direct", "direct_key": direct_key}, user), {"_id": 0}
        )
        if not existing:
            raise
        return {
            "success": True,
            "data": await _serialize_thread(existing, user_id=user["id"], contacts=contacts),
            "meta": {"created": False},
        }
    await _publish_to_users(member_ids, {"type": "thread_created", "thread_id": thread["id"]})
    return {
        "success": True,
        "data": await _serialize_thread(thread, user_id=user["id"], contacts=contacts),
        "meta": {"created": True},
    }


@router.post("/threads/groups", status_code=201)
async def create_group_thread(
    body: GroupThreadRequest,
    user: dict = Depends(require_messaging_profile),
):
    db = get_db()
    contacts = await _contact_map(db, user)
    if user["id"] not in contacts:
        raise HTTPException(403, "Messaging is for school staff")
    member_ids = list(dict.fromkeys([user["id"], *body.member_ids]))
    if len(member_ids) < 3:
        raise HTTPException(400, "A group needs at least three members; use a direct message for two")
    unknown = [member_id for member_id in member_ids if member_id not in contacts]
    if unknown:
        raise HTTPException(400, "One or more selected profiles cannot use messaging")
    now = _now()
    thread = {
        "id": str(uuid.uuid4()),
        "kind": "group",
        "name": body.name,
        "branch_id": user.get("branch_id"),
        "member_ids": member_ids,
        "admin_ids": [user["id"]],
        "created_by": user["id"],
        "created_at": now,
        "updated_at": now,
        "last_message": None,
    }
    thread = add_school_id(thread)
    await db.platform_message_threads.insert_one(thread)
    await _publish_to_users(member_ids, {"type": "thread_created", "thread_id": thread["id"]})
    return {
        "success": True,
        "data": await _serialize_thread(thread, user_id=user["id"], contacts=contacts),
    }


@router.patch("/threads/{thread_id}")
async def update_group_thread(
    thread_id: str,
    body: GroupThreadUpdate,
    user: dict = Depends(require_messaging_profile),
):
    db = get_db()
    thread = await _thread_for_member(db, thread_id, user)
    if thread.get("kind") != "group":
        raise HTTPException(400, "Direct conversations cannot be edited")
    if user["id"] not in thread.get("admin_ids", []):
        raise HTTPException(403, "Only a group admin can edit this group")
    changes = {"updated_at": _now()}
    if body.name is not None:
        changes["name"] = body.name
    if body.member_ids is not None:
        contacts = await _contact_map(db, user)
        member_ids = list(dict.fromkeys([thread["created_by"], user["id"], *body.member_ids]))
        if len(member_ids) < 3:
            raise HTTPException(400, "A group needs at least three members")
        if any(member_id not in contacts for member_id in member_ids):
            raise HTTPException(400, "One or more selected profiles cannot use messaging")
        changes["member_ids"] = member_ids
    await db.platform_message_threads.update_one(_scope({"id": thread_id}, user), {"$set": changes})
    # R4-2: sending a message is NOT audited - the message row itself carries who, what
    # and when, so it IS the record and copying it would store every message twice
    # (decision 13). Changing a group's membership is different: it decides who can read
    # the conversation from here on, and nothing else on the platform records it.
    await write_audit(
        db,
        action="message_thread_update",
        entity_id=thread_id,
        collection="platform_message_threads",
        changed_by=user.get("id", ""),
        changed_by_role=user.get("role", ""),
        school_id=get_school_id(),
        branch_id=user.get("branch_id", ""),
        changes=audit_changes.edit(thread, changes),
    )
    updated = {**thread, **changes}
    await _publish_to_users(
        list(set(thread.get("member_ids", [])) | set(updated.get("member_ids", []))),
        {"type": "thread_updated", "thread_id": thread_id},
    )
    return {
        "success": True,
        "data": await _serialize_thread(
            updated, user_id=user["id"], contacts=await _contact_map(db, user)
        ),
    }


@router.get("/threads/{thread_id}/messages")
async def list_messages(
    thread_id: str,
    before: Optional[str] = None,
    limit: int = 50,
    user: dict = Depends(require_messaging_profile),
):
    db = get_db()
    await _thread_for_member(db, thread_id, user)
    limit = clamp_page_size(limit)
    query = {"thread_id": thread_id}
    if before:
        query["created_at"] = {"$lt": before}
    messages = await db.platform_messages.find(_scope(query, user), {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    messages.reverse()
    message_ids = [message["id"] for message in messages]
    receipts = await db.platform_message_receipts.find(
        _scope({"message_id": {"$in": message_ids}}, user), {"_id": 0}
    ).to_list(500)
    receipts_by_message: dict[str, list[dict]] = {}
    for row in receipts:
        receipts_by_message.setdefault(row["message_id"], []).append(row)
    contacts = await _contact_map(db, user)
    reply_ids = [message.get("reply_to_id") for message in messages if message.get("reply_to_id")]
    reply_rows = await db.platform_messages.find(
        _scope({"id": {"$in": reply_ids}}, user), {"_id": 0, "id": 1, "sender_id": 1, "text": 1, "deleted_at": 1}
    ).to_list(100)
    replies = {row["id"]: row for row in reply_rows}
    data = []
    for message in messages:
        sender = contacts.get(message.get("sender_id"), {})
        reply = replies.get(message.get("reply_to_id"))
        data.append({
            **message,
            "sender_name": sender.get("name", "School profile"),
            "reply_to": ({
                "id": reply["id"],
                "sender_name": contacts.get(reply.get("sender_id"), {}).get("name", "School profile"),
                "text": "This message was deleted" if reply.get("deleted_at") else reply.get("text", ""),
            } if reply else None),
            "receipt": _receipt_status(message, receipts_by_message.get(message["id"], [])),
        })
    return {"success": True, "data": data, "meta": {"count": len(data), "has_more": len(data) == limit}}


@router.post("/threads/{thread_id}/messages", status_code=201)
async def send_message(
    thread_id: str,
    body: MessageRequest,
    user: dict = Depends(require_messaging_profile),
):
    db = get_db()
    thread = await _thread_for_member(db, thread_id, user)
    if body.reply_to_id:
        reply = await db.platform_messages.find_one(
            _scope({"id": body.reply_to_id, "thread_id": thread_id}, user), {"_id": 0, "id": 1}
        )
        if not reply:
            raise HTTPException(400, "Reply target is not in this conversation")
    now = _now()
    message = {
        "id": str(uuid.uuid4()),
        "thread_id": thread_id,
        "branch_id": user.get("branch_id"),
        "sender_id": user["id"],
        "text": body.text,
        "reply_to_id": body.reply_to_id,
        "created_at": now,
        "edited_at": None,
        "deleted_at": None,
    }
    receipts = []
    for member_id in thread["member_ids"]:
        is_sender = member_id == user["id"]
        receipts.append({
            "id": str(uuid.uuid4()),
            "thread_id": thread_id,
            "branch_id": user.get("branch_id"),
            "message_id": message["id"],
            "user_id": member_id,
            "delivered_at": now if is_sender or sse_is_connected(_channel(member_id)) else None,
            "read_at": now if is_sender else None,
        })
    message = add_school_id(message)
    receipts = [add_school_id(receipt) for receipt in receipts]
    await db.platform_messages.insert_one(message)
    await db.platform_message_receipts.insert_many(receipts)
    # insert_one stamps Mongo's own `_id` into the dict IN PLACE. `message` is
    # echoed back to the sender below, and an ObjectId cannot be turned into
    # JSON - the send 500'd for everyone while the message itself was saved and
    # delivered, so the sender saw a failure that had not happened. Every other
    # response in this file reads back with `{"_id": 0}` or strips the key; this
    # was the one that returned the dict it had just written.
    message.pop("_id", None)
    last_message = {
        "id": message["id"],
        "sender_id": user["id"],
        "text": body.text[:180],
        "created_at": now,
        "deleted_at": None,
    }
    await db.platform_message_threads.update_one(
        _scope({"id": thread_id}, user), {"$set": {"last_message": last_message, "updated_at": now}}
    )
    event = {"type": "message", "thread_id": thread_id, "message": message}
    await _publish_to_users(thread["member_ids"], event)
    return {
        "success": True,
        "data": {
            **message,
            "sender_name": user.get("name") or "School profile",
            "reply_to": None,
            "receipt": _receipt_status(message, receipts),
        },
    }


@router.patch("/threads/{thread_id}/read")
async def mark_thread_read(
    thread_id: str,
    user: dict = Depends(require_messaging_profile),
):
    db = get_db()
    thread = await _thread_for_member(db, thread_id, user)
    query = _scope({"thread_id": thread_id, "user_id": user["id"], "read_at": None}, user)
    pending = await db.platform_message_receipts.find(query, {"_id": 0, "message_id": 1}).to_list(500)
    if pending:
        now = _now()
        await db.platform_message_receipts.update_many(
            query, {"$set": {"delivered_at": now, "read_at": now}}
        )
        await _publish_to_users(thread["member_ids"], {
            "type": "receipt",
            "thread_id": thread_id,
            "message_ids": [row["message_id"] for row in pending],
            "user_id": user["id"],
            "status": "read",
            "at": now,
        })
    return {"success": True, "data": {"updated": len(pending)}}


@router.post("/threads/{thread_id}/typing", status_code=204)
async def send_typing(
    thread_id: str,
    user: dict = Depends(require_messaging_profile),
):
    db = get_db()
    thread = await _thread_for_member(db, thread_id, user)
    recipients = [member_id for member_id in thread["member_ids"] if member_id != user["id"]]
    await _publish_to_users(recipients, {
        "type": "typing",
        "thread_id": thread_id,
        "user_id": user["id"],
        "name": user.get("name") or "Someone",
    })


@router.patch("/messages/{message_id}")
async def edit_message(
    message_id: str,
    body: MessageEditRequest,
    user: dict = Depends(require_messaging_profile),
):
    db = get_db()
    message = await db.platform_messages.find_one(
        _scope({"id": message_id, "sender_id": user["id"]}, user), {"_id": 0}
    )
    if not message or message.get("deleted_at"):
        raise HTTPException(404, "Message not found")
    await _thread_for_member(db, message["thread_id"], user)
    created = datetime.fromisoformat(message["created_at"].replace("Z", "+00:00"))
    if (datetime.now(timezone.utc) - created).total_seconds() > 900:
        raise HTTPException(409, "Messages can be edited for 15 minutes")
    edited_at = _now()
    await db.platform_messages.update_one(
        _scope({"id": message_id}, user), {"$set": {"text": body.text, "edited_at": edited_at}}
    )
    # R4-2. An edit REPLACES what was said. The message row afterwards shows only the
    # new wording, so without this the earlier wording is gone and there is no sign a
    # change ever happened. This is the one part of messaging the message table cannot
    # tell you about itself.
    await write_audit(
        db,
        action="message_edit",
        entity_id=message_id,
        collection="platform_messages",
        changed_by=user.get("id", ""),
        changed_by_role=user.get("role", ""),
        school_id=get_school_id(),
        branch_id=user.get("branch_id", ""),
        changes=audit_changes.edit(message, {"text": body.text, "edited_at": edited_at}),
    )
    thread = await db.platform_message_threads.find_one(_scope({"id": message["thread_id"]}, user), {"_id": 0})
    if thread and (thread.get("last_message") or {}).get("id") == message_id:
        await db.platform_message_threads.update_one(
            _scope({"id": thread["id"]}, user), {"$set": {"last_message.text": body.text[:180], "updated_at": edited_at}}
        )
    if thread:
        await _publish_to_users(thread["member_ids"], {
            "type": "message_updated", "thread_id": thread["id"], "message_id": message_id,
            "text": body.text, "edited_at": edited_at,
        })
    return {"success": True, "data": {"id": message_id, "text": body.text, "edited_at": edited_at}}


@router.delete("/messages/{message_id}")
async def delete_message(
    message_id: str,
    user: dict = Depends(require_messaging_profile),
):
    db = get_db()
    message = await db.platform_messages.find_one(
        _scope({"id": message_id, "sender_id": user["id"]}, user), {"_id": 0}
    )
    if not message or message.get("deleted_at"):
        raise HTTPException(404, "Message not found")
    thread = await _thread_for_member(db, message["thread_id"], user)
    deleted_at = _now()
    deletion = {
        "text": "",
        "deleted_at": deleted_at,
    }
    await db.platform_messages.update_one(
        _scope({"id": message_id}, user), {"$set": deletion}
    )
    if (thread.get("last_message") or {}).get("id") == message_id:
        await db.platform_message_threads.update_one(
            _scope({"id": thread["id"]}, user),
            {"$set": {"last_message.text": "This message was deleted", "last_message.deleted_at": deleted_at}},
        )
    await _publish_to_users(thread["member_ids"], {
        "type": "message_deleted", "thread_id": thread["id"], "message_id": message_id,
        "deleted_at": deleted_at,
    })
    # Decision 13: sending is not audited because the message row IS the record, but
    # this update removes the only copy of what was said. The audit row is the part
    # that can still answer who removed it and when.
    await write_audit(
        db,
        action="message_delete",
        entity_id=message_id,
        collection="platform_messages",
        changed_by=user.get("id", ""),
        changed_by_role=user.get("role", ""),
        school_id=get_school_id(),
        branch_id=user.get("branch_id", ""),
        changes=audit_changes.removed(message),
    )
    return {"success": True}


@router.get("/stream")
async def messaging_stream(
    request: Request,
    user: dict = Depends(require_messaging_profile),
):
    db = get_db()
    await _require_contact(db, user["id"], user)
    session_id = normalize_session_id(request.headers.get("X-SSE-Session-ID"))
    queue = await sse_connect(_channel(user["id"]), session_id)
    contacts = await _staff_contacts(db, user)
    contact_ids = [contact["id"] for contact in contacts]
    connected_at = _now()
    await db.platform_message_presence.update_one(
        _scope({"user_id": user["id"]}, user),
        {"$set": {"user_id": user["id"], "branch_id": user.get("branch_id"), "last_seen_at": connected_at}},
        upsert=True,
    )
    pending = await db.platform_message_receipts.find(
        _scope({"user_id": user["id"], "delivered_at": None}, user), {"_id": 0, "message_id": 1, "thread_id": 1}
    ).to_list(1000)
    if pending:
        await db.platform_message_receipts.update_many(
            _scope({"user_id": user["id"], "delivered_at": None}, user),
            {"$set": {"delivered_at": connected_at}},
        )
    await _publish_to_users(contact_ids, {
        "type": "presence", "user_id": user["id"], "online": True, "last_seen_at": connected_at,
    })
    if pending:
        await _publish_to_users(contact_ids, {
            "type": "receipt", "user_id": user["id"], "status": "delivered",
            "message_ids": [row["message_id"] for row in pending],
            "thread_ids": list({row["thread_id"] for row in pending}), "at": connected_at,
        })

    async def event_generator():
        try:
            yield encode_sse({"type": "ready", "user_id": user["id"]})
            while True:
                if await request.is_disconnected():
                    break
                event = await queue.get()
                if event == KEEPALIVE_COMMENT:
                    yield KEEPALIVE_COMMENT
                    continue
                if isinstance(event, dict) and event.get("type") == "close":
                    break
                yield encode_sse(event)
        except asyncio.CancelledError:
            raise
        finally:
            await sse_disconnect(_channel(user["id"]), session_id, queue)
            last_seen = _now()
            await db.platform_message_presence.update_one(
                _scope({"user_id": user["id"]}, user),
                {"$set": {"user_id": user["id"], "branch_id": user.get("branch_id"), "last_seen_at": last_seen}},
                upsert=True,
            )
            still_online = sse_is_connected(_channel(user["id"]))
            await _publish_to_users(contact_ids, {
                "type": "presence", "user_id": user["id"], "online": still_online,
                "last_seen_at": last_seen,
            })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
