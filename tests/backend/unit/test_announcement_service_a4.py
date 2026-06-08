"""Story A.4 — announcement moderation gate: centralized decision + AI honors it.

Pins the SERVICE gate decision and proves the AI `create_announcement` tool now
honors the EC-9.1 role exemption (owner/principal broadcast directly) it previously
ignored — bringing it into parity with the REST route.
"""

from __future__ import annotations

import pytest

from services.actor_context import actor_ctx_from_user
from services.announcement_service import (
    decide_announcement_status,
    AnnouncementValidationError,
)
from ai import tool_functions_v2

pytestmark = pytest.mark.asyncio

OWNER = {"id": "o1", "role": "owner", "name": "Owner"}
PRINCIPAL = {"id": "p1", "role": "admin", "sub_category": "principal", "name": "Principal"}
RECEPTION = {"id": "r1", "role": "admin", "sub_category": "reception", "name": "Reception"}
ALL_ROLES = ["teacher", "student", "admin", "parent"]


def _ctx(user):
    return actor_ctx_from_user(user, school_id="aaryans-joya")


# ─── pure gate decisions ──────────────────────────────────────────────────────

def test_owner_broadcasts_directly():
    assert decide_announcement_status(_ctx(OWNER), "all", ALL_ROLES) == "active"


def test_principal_broadcasts_directly():
    assert decide_announcement_status(_ctx(PRINCIPAL), "all", ALL_ROLES) == "active"


def test_principal_targeting_owner_raises():
    with pytest.raises(AnnouncementValidationError):
        decide_announcement_status(_ctx(PRINCIPAL), "role", ["owner"], raw_audience_roles=["owner"])


def test_nonexempt_all_audience_pending():
    assert decide_announcement_status(_ctx(RECEPTION), "all", ALL_ROLES) == "pending_approval"


def test_nonexempt_teacher_audience_pending():
    assert decide_announcement_status(_ctx(RECEPTION), "role", ["teacher"]) == "pending_approval"


def test_nonexempt_admin_only_active():
    assert decide_announcement_status(_ctx(RECEPTION), "role", ["admin"]) == "active"


# ─── AI tool now honors the exemption (the corrected divergence) ──────────────

@pytest.fixture
def _clean(fake_db):
    fake_db.announcements.docs[:] = []
    fake_db.audit_logs.docs[:] = []
    yield
    fake_db.announcements.docs[:] = []
    fake_db.audit_logs.docs[:] = []


async def test_ai_owner_announcement_now_broadcasts_directly(fake_db, monkeypatch, _clean):
    """Regression: the old AI tool over-moderated — an owner's all-audience announcement
    was held for approval. It now publishes directly (active), matching the panel."""
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_create_announcement(
        {"title": "All hands", "content": "Read this.", "audience_type": "all"}, OWNER, None
    )
    assert out["success"] is True
    assert out["data"]["status"] == "active"


async def test_ai_nonexempt_announcement_still_gated(fake_db, monkeypatch, _clean):
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_create_announcement(
        {"title": "Staff Notice", "content": "Meeting.", "audience_type": "staff"}, RECEPTION, None
    )
    assert out["data"]["status"] == "pending_approval"
