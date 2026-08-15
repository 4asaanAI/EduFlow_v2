"""The conversation welded to an approval, whatever kind of approval it is.

Approvals workflow, 2026-08-15. Abhimanyu's decisions 24 and 26, and the shape of an
AWS Support case, which he named directly: reply while it is open, resolve as a separate
and deliberate act, attach a quote or a bill, and re-open when something was missed.

**Four rules that are easy to get wrong. Read them before changing anything here.**

1. **Flo is NEVER a member of a thread** (decision 29). Nothing in this file writes a
   message on Flo's behalf and nothing ever should. Each person gets Flo privately, on
   their own screen, inside their own profile. Aman's Flo sees far more than Chaman's, so
   an answer printed into the shared transcript would be built on Aman's access and read
   by somebody who does not hold it. The permission table would be correct and the
   platform would leak anyway, through the transcript.

2. **Being added does not automatically hand over the history** (decision 26). The person
   doing the adding CHOOSES, exactly like adding somebody to a group chat, where
   sometimes what was said before should come with them and sometimes it must not. A
   participant added without the history sees only what was said from the moment they
   joined, attachments included.

3. **There is no admin inside a thread** (decision 26). Both the raiser and anybody who
   may decide can add somebody; nobody can remove anybody. Abhimanyu's reason was that
   ranks inside a chat would over-complicate a simple conversation.

4. **A decided thread closes and stays readable.** Approving or rejecting ends the
   conversation; nothing is ever deleted. Only somebody who may decide that KIND may
   re-open an approved one. A rejected one stays readable and cannot be re-opened
   (Abhimanyu, 2026-08-15): the raiser puts up a new version instead, and the reasoning
   behind the refusal stays there to be read.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from services import approval_registry as registry
from services.notification_service import create_notification
from tenant import scoped_filter, scoped_query


class ThreadError(Exception):
    """Base class."""


class ThreadClosed(ThreadError):
    """The conversation has ended -> HTTP 409."""


class ThreadForbidden(ThreadError):
    """Not in this conversation, or not entitled to do this -> HTTP 403."""


class ThreadValidationError(ThreadError):
    """Empty message, unknown person -> HTTP 400."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def thread_id(kind: str, record_id: str) -> str:
    return f"{kind}:{record_id}"


async def _users_matching(db, spec: dict, school_id: str) -> List[str]:
    rows = await db.users.find(
        scoped_filter(dict(spec), school_id), {"_id": 0, "id": 1}
    ).to_list(20)
    return [row["id"] for row in rows if row.get("id")]


async def default_participants(db, kind: str, doc: dict, school_id: str,
                               branch_id: Optional[str] = None) -> List[str]:
    """Who is in this conversation before anybody adds anyone.

    The raiser, plus whoever the KIND declares. Declared per kind rather than worked out
    here, so a seventh kind arrives with its own answer instead of inheriting one that
    happens to suit the six.
    """
    entry = registry.kind_or_raise(kind)
    people: List[str] = []
    raiser = doc.get(entry["raised_by_field"])
    if raiser:
        people.append(raiser)
    specs = list(entry.get("default_roles") or ())
    extra_roles = entry.get("extra_roles")
    if extra_roles:
        specs.extend(extra_roles(doc))
    for spec in specs:
        people.extend(await _users_matching(db, spec, school_id))
    extra_people = entry.get("extra_people")
    if extra_people:
        people.extend(await extra_people(db, doc, branch_id))
    seen, ordered = set(), []
    for person in people:
        if person and person not in seen:
            seen.add(person)
            ordered.append(person)
    return ordered


async def ensure_thread(db, kind: str, record_id: str, doc: dict, school_id: str,
                        branch_id: Optional[str] = None) -> dict:
    """Fetch this approval's conversation, creating it the first time somebody opens it.

    Created lazily rather than when the request is raised, deliberately: the six kinds
    are written by six different services and threading a creation call through all of
    them is six chances to miss one, which would leave an approval that cannot be
    discussed and no sign of why.
    """
    tid = thread_id(kind, record_id)
    existing = await db.approval_threads.find_one(
        scoped_filter({"id": tid}, school_id), {"_id": 0}
    )
    if existing:
        return existing
    now = _now()
    thread = {
        "_id": tid,
        "id": tid,
        "schoolId": school_id,
        "kind": kind,
        "record_id": record_id,
        "status": "open",
        "participants": [
            {"user_id": person, "added_by": None, "added_at": now,
             "can_read_history": True, "joined_after_message": 0, "joined_at": now}
            for person in await default_participants(db, kind, doc, school_id, branch_id)
        ],
        "created_at": now,
    }
    await db.approval_threads.insert_one(thread)
    return {key: value for key, value in thread.items() if key != "_id"}


def _participant(thread: dict, user_id: str) -> Optional[dict]:
    for person in thread.get("participants") or []:
        if person.get("user_id") == user_id:
            return person
    return None


async def may_read(db, user: dict, kind: str, record_id: str, doc: dict,
                   thread: Optional[dict] = None) -> bool:
    """Who may read this conversation.

    Anybody in it, plus anybody who may decide that request. The second half is not a
    widening: a person who can approve something must be able to read what was said about
    it, and they can already open the request itself.
    """
    if await registry.may_decide(db, kind, user, doc):
        return True
    if thread is None:
        return False
    return _participant(thread, user.get("id")) is not None


def visible_messages(thread: dict, messages: List[dict], user_id: str) -> List[dict]:
    """Apply rule 2: somebody added without the history starts where they joined.

    **The boundary is a message NUMBER, not a timestamp, and that is deliberate.** The
    first version compared the time a person joined against the time each message was
    written. Two of those can be identical to the microsecond, and when they were, a
    message from before the person joined counted as being from after it and their whole
    history was handed over. A clock is not fine-grained enough to answer a permission
    question. Every message in a thread carries its position in that thread instead, so
    "before you joined" is exact rather than nearly always right.
    """
    person = _participant(thread, user_id)
    if not person or person.get("can_read_history", True):
        return messages
    boundary = person.get("joined_after_message", 0)
    return [m for m in messages if (m.get("seq") or 0) > boundary]


async def list_messages(db, user: dict, kind: str, record_id: str, doc: dict,
                        school_id: str, branch_id: Optional[str] = None) -> dict:
    thread = await ensure_thread(db, kind, record_id, doc, school_id, branch_id)
    if not await may_read(db, user, kind, record_id, doc, thread):
        raise ThreadForbidden("You are not part of this conversation.")
    messages = await db.approval_messages.find(
        scoped_filter({"thread_id": thread["id"]}, school_id), {"_id": 0}
    ).to_list(500)
    messages.sort(key=lambda m: (m.get("seq") or 0, m.get("created_at") or ""))
    return {
        "thread": thread,
        "messages": visible_messages(thread, messages, user.get("id")),
    }


async def post_message(db, actor_ctx, user: dict, kind: str, record_id: str, doc: dict,
                       body: str, attachments: Optional[List[str]] = None) -> dict:
    """Reply, while the request is still open.

    Anybody in the conversation may reply, which is decision 24 and is wider than who may
    decide on purpose: the point of the thread is that the person who asked and the person
    deciding can talk before anybody presses a button.
    """
    text = (body or "").strip()
    if not text and not attachments:
        raise ThreadValidationError("A reply needs something in it.")
    thread = await ensure_thread(db, kind, record_id, doc, actor_ctx.school_id,
                                 actor_ctx.branch_id)
    if not await may_read(db, user, kind, record_id, doc, thread):
        raise ThreadForbidden("You are not part of this conversation.")
    if thread.get("status") != "open":
        raise ThreadClosed(
            "This has been decided, so the conversation is closed. It can be re-opened "
            "by somebody who decides this kind of request."
        )
    return await _write_message(
        db, actor_ctx, thread, text, author_id=user.get("id"),
        author_name=user.get("name") or "", attachments=attachments,
    )


async def _message_count(db, thread_id_value: str, school_id: str) -> int:
    existing = await db.approval_messages.find(
        scoped_filter({"thread_id": thread_id_value}, school_id), {"_id": 0, "seq": 1}
    ).to_list(1000)
    return max([m.get("seq") or 0 for m in existing] or [0])


async def _write_message(db, actor_ctx, thread: dict, text: str, *, author_id,
                         author_name: str = "", attachments=None,
                         system: bool = False) -> dict:
    message_id = str(uuid.uuid4())
    record = {
        "_id": message_id,
        "id": message_id,
        "schoolId": actor_ctx.school_id,
        "thread_id": thread["id"],
        # Its position in this conversation. What "before you joined" is measured
        # against; see `visible_messages` for why a timestamp will not do.
        "seq": await _message_count(db, thread["id"], actor_ctx.school_id) + 1,
        "kind": thread["kind"],
        "record_id": thread["record_id"],
        "author_id": author_id,
        "author_name": author_name,
        "body": text,
        "attachments": list(attachments or []),
        # A system line is what the platform itself says happened: an edit, a decision,
        # somebody being brought in. Drawn differently so nobody reads it as a person's
        # opinion.
        "system": system,
        "created_at": _now(),
    }
    await db.approval_messages.insert_one(record)
    if not system:
        for person in thread.get("participants") or []:
            if person.get("user_id") and person["user_id"] != author_id:
                await create_notification(
                    db,
                    user_id=person["user_id"],
                    notification_type="approval_reply",
                    title="New reply on an approval",
                    message=text[:140],
                    source_id=thread["record_id"],
                    source_type="approval_thread",
                )
    return {key: value for key, value in record.items() if key != "_id"}


async def system_note(db, actor_ctx, kind: str, record_id: str, doc: dict, text: str) -> None:
    """Write what the platform did into the transcript, so nothing happens invisibly."""
    thread = await ensure_thread(db, kind, record_id, doc, actor_ctx.school_id,
                                 actor_ctx.branch_id)
    await _write_message(db, actor_ctx, thread, text, author_id=None, system=True)


async def add_participant(db, actor_ctx, user: dict, kind: str, record_id: str, doc: dict,
                          new_user_id: str, share_history: bool) -> dict:
    """Bring somebody into the conversation, with or without what was said before.

    Both the raiser and anybody who may decide can do this (decision 26): if the raiser
    did not bring in the person who was needed, the approver should be able to, and either
    can ask the other in the thread to do it.
    """
    thread = await ensure_thread(db, kind, record_id, doc, actor_ctx.school_id,
                                 actor_ctx.branch_id)
    if not await may_read(db, user, kind, record_id, doc, thread):
        raise ThreadForbidden("You are not part of this conversation.")
    if not new_user_id:
        raise ThreadValidationError("Say who is being added.")
    if _participant(thread, new_user_id):
        raise ThreadValidationError("That person is already in this conversation.")
    target = await db.users.find_one(
        scoped_filter({"id": new_user_id}, actor_ctx.school_id), {"_id": 0, "id": 1, "name": 1}
    )
    if not target:
        raise ThreadValidationError("That person does not have an account here.")

    now = _now()
    entry = {
        "user_id": new_user_id,
        "added_by": actor_ctx.user_id,
        "added_at": now,
        "can_read_history": bool(share_history),
        # Where their view starts, when the history is NOT shared: they see message
        # numbers ABOVE this one and nothing at or below it.
        "joined_after_message": await _message_count(db, thread["id"], actor_ctx.school_id),
        "joined_at": now,
    }
    await db.approval_threads.update_one(
        scoped_filter({"id": thread["id"]}, actor_ctx.school_id),
        {"$push": {"participants": entry}},
    )
    thread["participants"] = list(thread.get("participants") or []) + [entry]
    await _write_message(
        db, actor_ctx, thread,
        "%s was brought into this conversation%s." % (
            target.get("name") or "Somebody",
            "" if share_history else ", without what was said before",
        ),
        author_id=None, system=True,
    )
    await create_notification(
        db,
        user_id=new_user_id,
        notification_type="approval_added_to_thread",
        title="You were added to an approval",
        message=registry.to_card(kind, doc).get("title") or "An approval request",
        source_id=record_id,
        source_type="approval_thread",
    )
    return entry


async def close_thread(db, actor_ctx, kind: str, record_id: str, doc: dict,
                       decision: str, reason: str) -> None:
    """End the conversation when the request is decided, and say so in the transcript."""
    thread = await ensure_thread(db, kind, record_id, doc, actor_ctx.school_id,
                                 actor_ctx.branch_id)
    await db.approval_threads.update_one(
        scoped_filter({"id": thread["id"]}, actor_ctx.school_id),
        {"$set": {"status": "closed", "closed_at": _now(),
                  "closed_decision": decision, "closed_reason": reason}},
    )
    word = "approved" if decision == "approve" else "rejected"
    await _write_message(
        db, actor_ctx, thread,
        f"This was {word}. Reason given: {reason}" if reason else f"This was {word}.",
        author_id=None, system=True,
    )


async def reopen_thread(db, actor_ctx, user: dict, kind: str, record_id: str, doc: dict,
                        reason: str) -> dict:
    """Re-open a closed conversation.

    Restricted to somebody who may decide that kind, which is decision 24 word for word.
    A REJECTED one cannot be re-opened (Abhimanyu, 2026-08-15): the refusal stands and
    the raiser puts up a new version, so a "no" cannot be quietly turned into a "yes" on
    the same record.
    """
    thread = await ensure_thread(db, kind, record_id, doc, actor_ctx.school_id,
                                 actor_ctx.branch_id)
    if not await registry.may_decide(db, kind, user, doc):
        raise ThreadForbidden(
            "Only somebody who decides this kind of request can re-open it."
        )
    if thread.get("status") == "open":
        raise ThreadValidationError("This conversation is already open.")
    if thread.get("closed_decision") == "reject":
        raise ThreadForbidden(
            "A refused request stays refused. Ask for it again as a new request, so the "
            "reason it was refused stays readable beside it."
        )
    await db.approval_threads.update_one(
        scoped_filter({"id": thread["id"]}, actor_ctx.school_id),
        {"$set": {"status": "open", "reopened_by": actor_ctx.user_id,
                  "reopened_at": _now(), "reopen_reason": reason}},
    )
    await _write_message(
        db, actor_ctx, thread,
        f"This was re-opened. Reason given: {reason}" if reason else "This was re-opened.",
        author_id=None, system=True,
    )
    return {"status": "open"}


# ── Attachments ───────────────────────────────────────────────────────────────
#
# A file attached to an approval goes through the ordinary upload route, so it gets the
# ordinary rules: the same list of allowed file types, the same size ceiling for that
# person's role, the same check that the contents match the extension, the same private
# bucket and the same short-lived signed link. Nothing about the 2026-08-15 photo work is
# worked around; there is no second way to put a file into this school's storage.
#
# What DOES have to change is who may open one. The ordinary rule is "your own file, or
# the owner or the principal". Under that rule the accountant head, who is in a repair-cost
# conversation precisely because he is the one who pays, could see that a quote had been
# attached and could not open it. So there is one extra way in, and it is deliberately
# narrow: the file is attached to a message in a conversation you are in, AND that message
# is one you are allowed to see. A participant added without the history cannot open an
# attachment from before they joined, which is the same rule as the text and would be a
# hole if it were not.


async def may_open_attachment(db, user: dict, file_id: str, school_id: str) -> bool:
    """Is this file attached to an approval conversation this person may read?"""
    message = await db.approval_messages.find_one(
        scoped_filter({"attachments": file_id}, school_id), {"_id": 0}
    )
    if not message:
        return False
    thread = await db.approval_threads.find_one(
        scoped_filter({"id": message.get("thread_id")}, school_id), {"_id": 0}
    )
    if not thread:
        return False
    try:
        doc = await registry.load(db, thread["kind"], thread["record_id"], school_id)
    except registry.ApprovalKindUnknown:
        return False
    if not await may_read(db, user, thread["kind"], thread["record_id"], doc, thread):
        return False
    # The history rule again: seeing the message is what entitles you to its attachment.
    return bool(visible_messages(thread, [message], user.get("id")))
