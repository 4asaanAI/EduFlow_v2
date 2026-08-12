"""An attached photograph must actually reach the model.

WHY THIS FILE EXISTS. Flo told the school's owner that a photo "could not be examined"
and advised re-saving it. Two independent faults had to be fixed before any image could
work, and this file guards the second one.

The chat pipeline saves the user's turn to the database as PLAIN TEXT (Phase 1) and then
rebuilds the whole request from those stored rows (Phase 5). The image is therefore gone
by the time the request is assembled, and every path that calls the model has to put it
back. The two tool-calling paths did. The ordinary no-tool path did not - so a photo sent
with a plain question, which is the commonest way anyone sends one, was precisely the case
where the model received the words and never the picture.

The first fault is pinned separately in `test_vision_service.py`.
"""

from __future__ import annotations

from routes.chat import _reattach_image, _user_content


IMG = "data:image/jpeg;base64,QUJD"


def _history():
    """History as Phase 5 rebuilds it - text only, current turn last."""
    return [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "Hello! How can I help?"},
        {"role": "user", "content": "what about this?"},
    ]


def test_the_picture_is_attached_to_the_current_turn():
    out = _reattach_image(_history(), "what about this?", IMG)

    last = out[-1]
    assert last["role"] == "user"
    assert isinstance(last["content"], list), (
        "a turn carrying an image must be multimodal content, not a plain string - "
        "a string is exactly how the image got silently dropped"
    )
    urls = [p["image_url"]["url"] for p in last["content"] if p["type"] == "image_url"]
    assert urls == [IMG]


def test_the_question_survives_alongside_the_picture():
    out = _reattach_image(_history(), "what about this?", IMG)

    texts = [p["text"] for p in out[-1]["content"] if p["type"] == "text"]
    assert texts == ["what about this?"]


def test_earlier_conversation_is_left_untouched():
    history = _history()
    out = _reattach_image(history, "what about this?", IMG)

    assert out[:-1] == history[:-1], "only the current turn should change"
    assert len(out) == len(history), "re-attaching must not add or drop a turn"


def test_the_current_turn_is_replaced_not_duplicated():
    out = _reattach_image(_history(), "what about this?", IMG)

    user_turns = [m for m in out if m["role"] == "user"]
    assert len(user_turns) == 2, "the current turn must be replaced, not appended twice"


def test_a_conversation_with_no_image_is_returned_unchanged():
    history = _history()

    assert _reattach_image(history, "what about this?", None) is history
    assert _reattach_image(history, "what about this?", "") is history


def test_empty_history_is_safe():
    """Guards the slice: messages[:-1] on an empty list must not invent a turn."""
    assert _reattach_image([], "hi", IMG) == []


# ── the content builder itself ────────────────────────────────────────────────

def test_user_content_is_a_plain_string_when_there_is_no_image():
    assert _user_content("just text", None) == "just text"


def test_user_content_carries_both_parts_when_there_is_an_image():
    content = _user_content("read this", IMG)

    assert [p["type"] for p in content] == ["text", "image_url"]
    assert content[1]["image_url"]["url"] == IMG
