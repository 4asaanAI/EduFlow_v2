from __future__ import annotations

import pytest

from ai.tool_access import is_tool_authorized
from ai.tool_functions_v2 import (
    BULK_TOOL_NAMES,
    EXPLICIT_CONFIRMATION_TOOL_NAMES,
    TOOL_REGISTRY,
    WRITE_TOOL_NAMES,
)
from routes import chat
from middleware.auth import verify_password


OWNER = {"id": "aman", "role": "owner", "sub_category": "owner"}
PRINCIPAL = {"id": "adesh", "role": "admin", "sub_category": "principal"}
ACCOUNTANT = {"id": "sonu", "role": "admin", "sub_category": "accountant"}
MANAGEMENT = {"id": "lalit", "role": "admin", "sub_category": "management"}


def _school_management_tool(tool_def: dict) -> bool:
    """A tool the registry offers to the school's leadership at all.

    Leadership (owner + principal) hold this whole surface, so "owner OR admin
    appears in roles" is the right question for them.
    """
    return bool(set(tool_def.get("roles") or ()).intersection({"owner", "admin"}))


def _open_to_any_admin(tool_def: dict) -> bool:
    """A tool the registry offers to admins, not to the school's owner alone.

    R2-3: the accountant and management heads are widened by `access_domain`, but
    only across tools the registry actually offers to an admin. A tool marked
    roles=["owner"] is owner-only however its domain reads — that distinction is what
    kept `year_end_transition`, the branch CRUD and the legal-entity CRUD out of
    Sonu's and Lalit's hands.
    """
    return "admin" in set(tool_def.get("roles") or ())


def test_every_registry_tool_has_an_explicit_access_domain():
    assert {tool.get("access_domain") for tool in TOOL_REGISTRY.values()} <= {
        "finance", "non_finance", "shared", "leadership",
    }
    assert all(tool.get("access_domain") for tool in TOOL_REGISTRY.values())


def test_owner_and_principal_have_the_complete_school_management_surface():
    gaps = []
    for name, tool in TOOL_REGISTRY.items():
        if not _school_management_tool(tool):
            continue
        if not is_tool_authorized(OWNER, tool) or not is_tool_authorized(PRINCIPAL, tool):
            gaps.append(name)
    assert gaps == []


def test_accountant_gets_only_finance_and_required_shared_lookups():
    wrong = []
    for name, tool in TOOL_REGISTRY.items():
        allowed = is_tool_authorized(ACCOUNTANT, tool)
        expected = _open_to_any_admin(tool) and tool["access_domain"] in {"finance", "shared"}
        if allowed != expected:
            wrong.append((name, tool["access_domain"], allowed, expected))
    assert wrong == []


def test_management_gets_everything_except_finance_and_leadership_private_tools():
    wrong = []
    for name, tool in TOOL_REGISTRY.items():
        allowed = is_tool_authorized(MANAGEMENT, tool)
        expected = _open_to_any_admin(tool) and tool["access_domain"] in {"non_finance", "shared"}
        if allowed != expected:
            wrong.append((name, tool["access_domain"], allowed, expected))
    assert wrong == []


@pytest.mark.parametrize("tool_name", [
    "get_payroll", "upsert_salary_structure", "disburse_salary",
    "correct_salary_disbursement", "create_accounting_period",
    "change_accounting_period_status",
])
def test_new_finance_controls_are_available_to_finance_profiles_only(tool_name):
    tool = TOOL_REGISTRY[tool_name]
    assert is_tool_authorized(OWNER, tool)
    assert is_tool_authorized(PRINCIPAL, tool)
    assert is_tool_authorized(ACCOUNTANT, tool)
    assert not is_tool_authorized(MANAGEMENT, tool)


def test_confirmation_set_is_exactly_destructive_bulk_and_reversals():
    destructive = {name for name, tool in TOOL_REGISTRY.items() if tool.get("destructive")}
    reversals = {
        "post_pos_return", "correct_fee_transaction", "correct_salary_disbursement",
        "change_accounting_period_status",
    }
    security_sensitive = {"set_profile_password"}
    assert EXPLICIT_CONFIRMATION_TOOL_NAMES == destructive | set(BULK_TOOL_NAMES) | reversals | security_sensitive
    assert set(EXPLICIT_CONFIRMATION_TOOL_NAMES) <= set(WRITE_TOOL_NAMES)
    ordinary = set(WRITE_TOOL_NAMES) - set(EXPLICIT_CONFIRMATION_TOOL_NAMES)
    assert ordinary
    assert all(not TOOL_REGISTRY[name].get("requires_confirmation") for name in ordinary)


def test_profile_account_permissions_are_exact():
    create_login = TOOL_REGISTRY["create_student_login"]
    set_password = TOOL_REGISTRY["set_profile_password"]
    for tool in (create_login, set_password):
        assert is_tool_authorized(OWNER, tool)
        assert is_tool_authorized(PRINCIPAL, tool)
        assert is_tool_authorized(MANAGEMENT, tool)
        assert not is_tool_authorized(ACCOUNTANT, tool)


async def test_password_confirmation_persists_only_a_bcrypt_hash(fake_db):
    original = list(fake_db.confirm_tokens.docs)
    try:
        event = await chat._build_confirm_event(
            "set_profile_password",
            {"username": "student.login", "new_password": "Changed@123"},
            OWNER,
            "session-password",
            fake_db,
        )
        token = await fake_db.confirm_tokens.find_one({"token": event["token"]})
        params = token["params"]
        assert "new_password" not in params
        assert verify_password("Changed@123", params["new_password_hash"])
        assert "Changed@123" not in str(event)
        assert "new_password_hash" not in str(event)
    finally:
        fake_db.confirm_tokens.docs[:] = original


async def test_ordinary_write_uses_automatic_token_and_hardened_dispatch(monkeypatch):
    captured = {}

    async def issue(**kwargs):
        captured["issue"] = kwargs
        return "server-token"

    async def dispatch(token, session_id, user, db, conv_id=None, destructive_ack=False):
        captured["dispatch"] = {
            "token": token, "session_id": session_id, "user": user,
            "db": db, "conv_id": conv_id, "destructive_ack": destructive_ack,
        }
        return {"success": True, "data": {"message": "done"}}

    monkeypatch.setattr(chat, "issue_confirm_token", issue)
    monkeypatch.setattr(chat, "_execute_confirmed_dispatch", dispatch)

    db = object()
    result = await chat._execute_automatic_write(
        "create_announcement", {"title": "Notice", "_private": "drop"},
        OWNER, "session-1", db, "conversation-1",
    )

    assert result["data"]["message"] == "done"
    assert captured["issue"]["confirmation_mode"] == "automatic"
    assert captured["issue"]["params"] == {"title": "Notice"}
    assert captured["dispatch"]["token"] == "server-token"
    assert captured["dispatch"]["destructive_ack"] is False
