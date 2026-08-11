"""What Flo actually sends Azure when someone attaches a photograph.

WHY THIS FILE EXISTS. Every other test around images mocks `describe_image` out
(`tests/backend/api/test_chat_upload_ocr.py` patches it wholesale), so the upload route
was thoroughly covered while the one function that builds the real request had no tests
at all. That gap hid a fatal defect: the call passed `max_tokens`, which the current
model family rejects with HTTP 400 `unsupported_parameter`. Every photograph any member
of staff sent Flo failed, and the wording that came back ("the picture could not be
examined") sent them off to re-save images that were never the problem.

So these tests deliberately assert the SHAPE OF THE OUTGOING REQUEST, not just the
behaviour of a stub. A mock that accepts anything would have passed the whole time.
"""

from __future__ import annotations

import pytest

from services.vision_service import describe_image


PNG = b"\x89PNG\r\n\x1a\nfake-bytes-are-fine-nothing-decodes-them-here"


@pytest.fixture(autouse=True)
def _configured(monkeypatch):
    """vision_available() needs a key and an endpoint before it will try anything."""
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.invalid/openai/v1")


class _Message:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content, finish_reason="stop"):
        self.message = _Message(content)
        self.finish_reason = finish_reason


class _Response:
    def __init__(self, content, finish_reason="stop"):
        self.choices = [_Choice(content, finish_reason)]


def _install_fake_client(monkeypatch, *, response=None, raises=None):
    """Stand in for LLMClient and capture the exact kwargs of the outgoing call."""
    captured = {}

    class _Completions:
        def create(self, **kwargs):
            captured.update(kwargs)
            if raises is not None:
                raise raises
            return response

    class _Chat:
        completions = _Completions()

    class _Inner:
        chat = _Chat()

    class _FakeLLMClient:
        def __init__(self):
            self.deployment = "gpt-5.6-luna"
            self._client = _Inner()

    import ai.llm_client as llm_mod
    monkeypatch.setattr(llm_mod, "LLMClient", _FakeLLMClient)
    return captured


# ── the regression pin ────────────────────────────────────────────────────────

def test_the_token_ceiling_is_sent_as_max_completion_tokens(monkeypatch):
    """THE bug. `max_tokens` is rejected outright by the current model family.

    If this assertion ever fails, no photograph anyone sends Flo can be read -
    the request 400s before the model ever looks at the image.
    """
    captured = _install_fake_client(monkeypatch, response=_Response("A fee receipt."))

    describe_image(PNG, "image/png")

    assert "max_completion_tokens" in captured, (
        "the token ceiling must be sent as max_completion_tokens"
    )
    assert "max_tokens" not in captured, (
        "max_tokens is rejected with HTTP 400 unsupported_parameter - this is the "
        "exact defect that stopped every image from being read"
    )


def test_the_image_is_sent_as_a_data_uri_carrying_its_real_mime_type(monkeypatch):
    captured = _install_fake_client(monkeypatch, response=_Response("A group photo."))

    describe_image(PNG, "image/jpeg")

    content = captured["messages"][0]["content"]
    image_part = next(p for p in content if p["type"] == "image_url")
    assert image_part["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert any(p["type"] == "text" for p in content), "the question must be sent too"


def test_a_description_comes_back_as_understood(monkeypatch):
    _install_fake_client(monkeypatch, response=_Response("  An admission form.  "))

    result = describe_image(PNG, "image/png")

    assert result.understood
    assert result.description == "An admission form."
    assert result.available


# ── failures must not blame the photograph ────────────────────────────────────

def test_a_malformed_request_says_re_uploading_will_not_help(monkeypatch):
    """A 400 on our own parameter names is a code defect, not a bad picture.

    The old handler let this fall through to "could not be examined just now", and the
    screen then advised saving the image again as a new JPG - advice that could never
    have worked, because nothing about the image was wrong.
    """
    _install_fake_client(monkeypatch, raises=Exception(
        "Error code: 400 - {'error': {'message': \"Unsupported parameter: "
        "'max_tokens' is not supported with this model. Use 'max_completion_tokens' "
        "instead.\", 'type': 'invalid_request_error', 'code': 'unsupported_parameter'}}"
    ))

    result = describe_image(PNG, "image/png")

    assert not result.understood
    assert not result.available
    assert "will not help" in result.reason.lower()


def test_running_out_of_budget_does_not_read_as_an_unreadable_picture(monkeypatch):
    """Hidden reasoning eating the whole ceiling is our setting, not a blank page."""
    _install_fake_client(monkeypatch, response=_Response("", finish_reason="length"))

    result = describe_image(PNG, "image/png")

    assert not result.understood
    assert "nothing could be made out" not in result.reason.lower(), (
        "blaming the photograph for our own token ceiling is the Epic 4 defect class"
    )
    assert "length" in result.reason.lower()


def test_a_text_only_deployment_admits_it_rather_than_inventing(monkeypatch):
    _install_fake_client(monkeypatch, raises=Exception(
        "This model does not support image input."
    ))

    result = describe_image(PNG, "image/png")

    assert not result.understood
    assert not result.available
    assert "cannot look at pictures" in result.reason.lower()


def test_a_content_filter_refusal_is_not_mislabelled_as_a_text_only_model(monkeypatch):
    """"content" used to be a match-word, so a content-filter error was reported as
    "this model only accepts text" - a wrong and permanent-sounding answer to a
    per-image refusal."""
    _install_fake_client(monkeypatch, raises=Exception(
        "The response was filtered due to the prompt triggering content management policy."
    ))

    result = describe_image(PNG, "image/png")

    assert "only accepts text" not in result.reason.lower()


def test_the_caller_never_sees_raw_exception_text(monkeypatch):
    """Error opacity (P3)."""
    _install_fake_client(monkeypatch, raises=Exception("connreset at 10.0.0.4:443 secret-token-abc"))

    result = describe_image(PNG, "image/png")

    assert "secret-token-abc" not in result.reason
    assert "10.0.0.4" not in result.reason


def test_an_unconfigured_server_says_so_and_never_calls_out(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_KEY", raising=False)

    result = describe_image(PNG, "image/png")

    assert not result.available
    assert not result.understood
