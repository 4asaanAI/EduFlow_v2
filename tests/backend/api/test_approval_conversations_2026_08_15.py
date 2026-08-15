"""The conversation attached to an approval. 2026-08-15.

Decisions 24, 26 and 29. The three that are easy to get wrong, and are pinned here:

  - somebody added WITHOUT the history must not be able to read what was said before
    they joined, attachments included;
  - a decided conversation closes, and only somebody who may decide that kind may
    re-open it, and never a refused one;
  - Flo is never a member.
"""

from __future__ import annotations

import pytest

from services import approval_registry as registry
from services import approval_thread_service as threads
from services.actor_context import actor_ctx_from_user

SCHOOL = "aaryans-joya"

OWNER = {"id": "aman", "role": "owner", "name": "Aman"}
PRINCIPAL = {"id": "adesh", "role": "admin", "sub_category": "principal", "name": "Adesh"}
ACCOUNTANT = {"id": "sonu", "role": "admin", "sub_category": "accountant", "name": "Sonu"}
TRANSPORT = {"id": "chaman", "role": "admin", "sub_category": "transport_head", "name": "Chaman"}
STRANGER = {"id": "nobody", "role": "admin", "sub_category": "support", "name": "Somebody Else"}


def _ctx(person):
    return actor_ctx_from_user(person, school_id=SCHOOL)


def _request(**over):
    return {
        "id": "req-1", "schoolId": SCHOOL, "status": "pending",
        "routing": "owner_and_principal", "title": "A bus repair",
        "description": "The clutch", "submitted_by": TRANSPORT["id"],
        "submitted_at": "2026-08-15T09:00:00+00:00", **over,
    }


@pytest.fixture
def seeded(fake_db):
    """Everyone who exists at this school, so role lookups find real people."""
    users_before = list(fake_db.users.docs)
    threads_before = list(fake_db.approval_threads.docs)
    messages_before = list(fake_db.approval_messages.docs)
    requests_before = list(fake_db.approval_requests.docs)
    notifications_before = list(fake_db.notifications.docs)
    fake_db.users.docs.extend([
        {"id": OWNER["id"], "schoolId": SCHOOL, "role": "owner", "name": "Aman"},
        {"id": PRINCIPAL["id"], "schoolId": SCHOOL, "role": "admin",
         "sub_category": "principal", "name": "Adesh"},
        {"id": ACCOUNTANT["id"], "schoolId": SCHOOL, "role": "admin",
         "sub_category": "accountant", "name": "Sonu"},
        {"id": TRANSPORT["id"], "schoolId": SCHOOL, "role": "admin",
         "sub_category": "transport_head", "name": "Chaman"},
        {"id": STRANGER["id"], "schoolId": SCHOOL, "role": "admin",
         "sub_category": "support", "name": "Somebody Else"},
    ])
    yield fake_db
    # Put back exactly what was there. The stand-in database is shared across the whole
    # session, so clearing a collection wholesale breaks a test in another file that
    # happens to run later.
    fake_db.users.docs[:] = users_before
    fake_db.approval_threads.docs[:] = threads_before
    fake_db.approval_messages.docs[:] = messages_before
    fake_db.approval_requests.docs[:] = requests_before
    fake_db.notifications.docs[:] = notifications_before


# ── Who is in the conversation to begin with ─────────────────────────────────


async def test_the_raiser_and_the_two_who_decide_are_in_it_from_the_start(seeded):
    doc = _request()
    people = await threads.default_participants(seeded, "general", doc, SCHOOL)
    assert set(people) == {TRANSPORT["id"], OWNER["id"], PRINCIPAL["id"]}


async def test_a_repair_cost_includes_the_accountant_head_because_he_pays_it(seeded):
    """Abhimanyu's own example of what "a default per kind" means. It reads off the
    action the request carries, so the same rule holds whoever asks for the money."""
    doc = _request(pending_action={"kind": "agree_a_repair_cost", "request_id": "f1"})
    people = await threads.default_participants(seeded, "general", doc, SCHOOL)
    assert ACCOUNTANT["id"] in people


async def test_an_ordinary_request_does_not_hand_the_accountant_head_the_conversation(seeded):
    """The opposite half of the rule, and the one that would leak if it were missing."""
    people = await threads.default_participants(seeded, "general", _request(), SCHOOL)
    assert ACCOUNTANT["id"] not in people


# ── Reading and replying ─────────────────────────────────────────────────────


async def test_somebody_with_nothing_to_do_with_it_cannot_read_or_reply(seeded):
    doc = _request()
    seeded.approval_requests.docs.append(doc)
    with pytest.raises(threads.ThreadForbidden):
        await threads.list_messages(seeded, STRANGER, "general", doc["id"], doc, SCHOOL)
    with pytest.raises(threads.ThreadForbidden):
        await threads.post_message(seeded, _ctx(STRANGER), STRANGER, "general",
                                   doc["id"], doc, "let me in")


async def test_the_person_who_asked_can_reply_even_though_he_decides_nothing(seeded):
    """The point of the conversation is that the person asking and the person deciding
    can talk before anybody presses a button."""
    doc = _request()
    seeded.approval_requests.docs.append(doc)
    message = await threads.post_message(
        seeded, _ctx(TRANSPORT), TRANSPORT, "general", doc["id"], doc,
        "The garage quoted twelve thousand.")
    assert message["author_id"] == TRANSPORT["id"]
    assert message["system"] is False


async def test_nobody_can_reply_once_it_has_been_decided(seeded):
    doc = _request()
    seeded.approval_requests.docs.append(doc)
    await threads.post_message(seeded, _ctx(TRANSPORT), TRANSPORT, "general",
                               doc["id"], doc, "first")
    await threads.close_thread(seeded, _ctx(OWNER), "general", doc["id"], doc,
                               "approve", "Go ahead")
    with pytest.raises(threads.ThreadClosed):
        await threads.post_message(seeded, _ctx(TRANSPORT), TRANSPORT, "general",
                                   doc["id"], doc, "one more thing")


async def test_the_decision_is_written_into_the_transcript(seeded):
    """So that reading the conversation from the top tells the whole story, rather than
    stopping at the last thing a person happened to type."""
    doc = _request()
    seeded.approval_requests.docs.append(doc)
    await threads.close_thread(seeded, _ctx(OWNER), "general", doc["id"], doc,
                               "reject", "Too expensive")
    read = await threads.list_messages(seeded, OWNER, "general", doc["id"], doc, SCHOOL)
    last = read["messages"][-1]
    assert last["system"] is True
    assert "rejected" in last["body"] and "Too expensive" in last["body"]


# ── Being added, with or without the history ─────────────────────────────────


async def test_somebody_added_without_the_history_starts_where_they_joined(seeded):
    """Decision 26, and the sharpest half of it. Exactly like being added to a group
    chat: sometimes what was said before should come with you and sometimes it must
    not."""
    doc = _request()
    seeded.approval_requests.docs.append(doc)
    await threads.post_message(seeded, _ctx(TRANSPORT), TRANSPORT, "general",
                               doc["id"], doc, "said before they joined")
    await threads.add_participant(seeded, _ctx(OWNER), OWNER, "general", doc["id"], doc,
                                  STRANGER["id"], share_history=False)
    await threads.post_message(seeded, _ctx(OWNER), OWNER, "general", doc["id"], doc,
                               "said after they joined")

    theirs = await threads.list_messages(seeded, STRANGER, "general", doc["id"], doc, SCHOOL)
    bodies = [m["body"] for m in theirs["messages"]]
    assert not any("before they joined" in b for b in bodies)
    assert any("after they joined" in b for b in bodies)


async def test_somebody_added_WITH_the_history_sees_all_of_it(seeded):
    doc = _request()
    seeded.approval_requests.docs.append(doc)
    await threads.post_message(seeded, _ctx(TRANSPORT), TRANSPORT, "general",
                               doc["id"], doc, "said before they joined")
    await threads.add_participant(seeded, _ctx(OWNER), OWNER, "general", doc["id"], doc,
                                  STRANGER["id"], share_history=True)
    theirs = await threads.list_messages(seeded, STRANGER, "general", doc["id"], doc, SCHOOL)
    assert any("before they joined" in m["body"] for m in theirs["messages"])


async def test_the_raiser_can_bring_somebody_in_too_not_only_the_approver(seeded):
    """Decision 26: if the raiser did not bring in the person who was needed the
    approver can, and either can ask the other to."""
    doc = _request()
    seeded.approval_requests.docs.append(doc)
    entry = await threads.add_participant(
        seeded, _ctx(TRANSPORT), TRANSPORT, "general", doc["id"], doc,
        ACCOUNTANT["id"], share_history=True)
    assert entry["user_id"] == ACCOUNTANT["id"]
    assert entry["added_by"] == TRANSPORT["id"]


async def test_a_stranger_cannot_add_themselves(seeded):
    doc = _request()
    seeded.approval_requests.docs.append(doc)
    with pytest.raises(threads.ThreadForbidden):
        await threads.add_participant(seeded, _ctx(STRANGER), STRANGER, "general",
                                      doc["id"], doc, STRANGER["id"], share_history=True)


async def test_bringing_somebody_in_is_said_out_loud_in_the_conversation(seeded):
    """Nothing about a conversation changes invisibly. A person joining silently is how
    somebody says something in front of an audience they did not know was there."""
    doc = _request()
    seeded.approval_requests.docs.append(doc)
    await threads.add_participant(seeded, _ctx(OWNER), OWNER, "general", doc["id"], doc,
                                  ACCOUNTANT["id"], share_history=False)
    read = await threads.list_messages(seeded, OWNER, "general", doc["id"], doc, SCHOOL)
    note = read["messages"][-1]
    assert note["system"] is True
    assert "Sonu" in note["body"] and "without what was said before" in note["body"]


# ── Re-opening ───────────────────────────────────────────────────────────────


async def test_only_somebody_who_decides_that_kind_may_reopen_it(seeded):
    doc = _request()
    seeded.approval_requests.docs.append(doc)
    await threads.close_thread(seeded, _ctx(OWNER), "general", doc["id"], doc,
                               "approve", "yes")
    with pytest.raises(threads.ThreadForbidden):
        await threads.reopen_thread(seeded, _ctx(TRANSPORT), TRANSPORT, "general",
                                    doc["id"], doc, "I got it wrong")
    assert await threads.reopen_thread(seeded, _ctx(OWNER), OWNER, "general",
                                       doc["id"], doc, "Second thoughts")


async def test_a_refused_request_stays_refused_and_cannot_be_reopened(seeded):
    """Abhimanyu, 2026-08-15. The refusal stands and the person puts up a new version,
    so a no cannot be quietly turned into a yes on the same record, and the reason it
    was refused stays readable beside it."""
    doc = _request()
    seeded.approval_requests.docs.append(doc)
    await threads.close_thread(seeded, _ctx(OWNER), "general", doc["id"], doc,
                               "reject", "Too expensive")
    with pytest.raises(threads.ThreadForbidden):
        await threads.reopen_thread(seeded, _ctx(OWNER), OWNER, "general", doc["id"],
                                    doc, "Actually go ahead")


async def test_a_refused_conversation_is_still_readable(seeded):
    """Nothing is ever destroyed. The reasoning behind a refusal is often the most
    useful thing in the whole thread."""
    doc = _request()
    seeded.approval_requests.docs.append(doc)
    await threads.post_message(seeded, _ctx(TRANSPORT), TRANSPORT, "general",
                               doc["id"], doc, "twelve thousand")
    await threads.close_thread(seeded, _ctx(OWNER), "general", doc["id"], doc,
                               "reject", "Too expensive")
    read = await threads.list_messages(seeded, TRANSPORT, "general", doc["id"], doc, SCHOOL)
    assert any("twelve thousand" in m["body"] for m in read["messages"])


# ── Attachments ──────────────────────────────────────────────────────────────


async def test_the_accountant_head_can_open_a_quote_attached_to_a_repair_he_is_paying(seeded):
    """Under the ordinary file rule he could see that a quote existed and could not open
    it, because a file belongs to whoever uploaded it plus the owner and the principal."""
    doc = _request(pending_action={"kind": "agree_a_repair_cost", "request_id": "f1"})
    seeded.approval_requests.docs.append(doc)
    await threads.post_message(seeded, _ctx(TRANSPORT), TRANSPORT, "general",
                               doc["id"], doc, "The quote", attachments=["file-1"])
    assert await threads.may_open_attachment(seeded, ACCOUNTANT, "file-1", SCHOOL) is True


async def test_somebody_outside_the_conversation_cannot_open_its_attachment(seeded):
    doc = _request()
    seeded.approval_requests.docs.append(doc)
    await threads.post_message(seeded, _ctx(TRANSPORT), TRANSPORT, "general",
                               doc["id"], doc, "The quote", attachments=["file-2"])
    assert await threads.may_open_attachment(seeded, STRANGER, "file-2", SCHOOL) is False


async def test_a_late_joiner_without_the_history_cannot_open_an_earlier_attachment(seeded):
    """The same rule as the text. If it applied to words and not to files, hiding the
    history would be pointless: the bill is usually the sensitive part."""
    doc = _request()
    seeded.approval_requests.docs.append(doc)
    await threads.post_message(seeded, _ctx(TRANSPORT), TRANSPORT, "general",
                               doc["id"], doc, "Earlier", attachments=["file-3"])
    await threads.add_participant(seeded, _ctx(OWNER), OWNER, "general", doc["id"], doc,
                                  STRANGER["id"], share_history=False)
    await threads.post_message(seeded, _ctx(OWNER), OWNER, "general", doc["id"], doc,
                               "Later", attachments=["file-4"])
    assert await threads.may_open_attachment(seeded, STRANGER, "file-3", SCHOOL) is False
    assert await threads.may_open_attachment(seeded, STRANGER, "file-4", SCHOOL) is True


async def test_a_file_that_belongs_to_no_approval_is_untouched_by_this_rule(seeded):
    """The extra way in is checked SECOND and only for approval attachments, so every
    other file on the platform behaves exactly as it did yesterday."""
    assert await threads.may_open_attachment(seeded, OWNER, "some-other-file", SCHOOL) is False


# ── Flo is never in here ─────────────────────────────────────────────────────


def test_the_conversation_code_knows_nothing_about_flo(seeded):
    """Decision 29, pinned as a fact about the file rather than as a behaviour.

    Aman's Flo and Adesh's Flo see far more than Chaman's. An answer printed into the
    shared transcript would be built on one person's access and read by somebody who
    does not hold it: the permission table would be correct and the platform would leak
    anyway, through the transcript. So the safest possible statement is that this module
    cannot reach the assistant at all.
    """
    import inspect

    from services import approval_thread_service

    source = inspect.getsource(approval_thread_service)
    for forbidden in ("llm_client", "tool_functions", "from ai.", "import ai."):
        assert forbidden not in source, (
            f"the approval conversation must never reach the assistant, found {forbidden!r}"
        )


async def test_every_message_is_written_by_a_person_or_by_the_platform_itself(seeded):
    """There is no third kind of author, and in particular no assistant.

    A system line is what the platform says happened - an edit, a decision, somebody
    being brought in - and is drawn differently so nobody reads it as an opinion.
    """
    doc = _request()
    seeded.approval_requests.docs.append(doc)
    await threads.post_message(seeded, _ctx(TRANSPORT), TRANSPORT, "general",
                               doc["id"], doc, "a person speaking")
    await threads.close_thread(seeded, _ctx(OWNER), "general", doc["id"], doc,
                               "approve", "fine")
    read = await threads.list_messages(seeded, OWNER, "general", doc["id"], doc, SCHOOL)
    for message in read["messages"]:
        if message["system"]:
            assert message["author_id"] is None
        else:
            assert message["author_id"] in {OWNER["id"], PRINCIPAL["id"], TRANSPORT["id"]}
