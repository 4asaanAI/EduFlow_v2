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
    roles=["owner"] is owner-only however its domain reads - that distinction is what
    kept `year_end_transition`, the branch CRUD and the legal-entity CRUD out of
    Sonu's and Lalit's hands.
    """
    return "admin" in set(tool_def.get("roles") or ())


def _named_in_the_matrix(profile, tool_name, expected, open_to_admin):
    """R2-5: the matrix may name a tool for or against a profile, overriding its domain.

    Four domains cannot express "the accountant head yes, the management head no"
    about a school bus route - both would have to be called finance. A denial always
    wins over a grant, because the safe answer to a contradiction is no.
    """
    from services.profile_matrix import PROFILE_MATRIX

    entry = PROFILE_MATRIX[profile]
    if tool_name in entry["extra_tools"] and open_to_admin:
        expected = True
    if tool_name in entry["denied_tools"]:
        expected = False
    return expected


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
        expected = _named_in_the_matrix("accountant", name, expected, _open_to_any_admin(tool))
        if allowed != expected:
            wrong.append((name, tool["access_domain"], allowed, expected))
    assert wrong == []


def test_management_gets_everything_except_finance_and_leadership_private_tools():
    wrong = []
    for name, tool in TOOL_REGISTRY.items():
        allowed = is_tool_authorized(MANAGEMENT, tool)
        expected = _open_to_any_admin(tool) and tool["access_domain"] in {"non_finance", "shared"}
        expected = _named_in_the_matrix("management", name, expected, _open_to_any_admin(tool))
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
    # R4-5, 2026-08-12. A fifth reason joins the four, and it is a new KIND of reason
    # rather than a new member of an old one: `report_platform_problem` is the only tool
    # that sends anything OUT OF THE SCHOOL. It is not destructive, not bulk, not a
    # reversal and not a password, so leaving it out of this list would have been the
    # correct reading of the old rule and the wrong answer. Somebody must be able to
    # tell "Flo helped me" from "Flo told my supplier what I was doing", and the confirm
    # card is how they tell.
    leaves_the_school = {"report_platform_problem"}
    assert EXPLICIT_CONFIRMATION_TOOL_NAMES == (
        destructive | set(BULK_TOOL_NAMES) | reversals | security_sensitive | leaves_the_school
    )
    assert set(EXPLICIT_CONFIRMATION_TOOL_NAMES) <= set(WRITE_TOOL_NAMES)
    ordinary = set(WRITE_TOOL_NAMES) - set(EXPLICIT_CONFIRMATION_TOOL_NAMES)
    assert ordinary
    assert all(not TOOL_REGISTRY[name].get("requires_confirmation") for name in ordinary)


def test_profile_account_permissions_are_exact():
    """R2-4 / decision 4, 2026-08-10: the management head no longer holds these.

    This test previously asserted that MANAGEMENT could use both. That was the earlier
    intent, and the narrower rules underneath it were sound - the service still limits
    management to STUDENT passwords and lets nobody but the school's owner change an
    owner's. It was reversed deliberately, not by accident: handing someone a way into
    the platform, or changing a password guarding 1,876 children's records, belongs to
    the two people who run the school.

    The narrower service rules stay exactly as they are. This is the outer door in
    front of them, and if the decision is ever reversed again, the way back is to take
    these two names out of LEADERSHIP_ONLY_TOOL_NAMES - not to loosen the service.
    """
    create_login = TOOL_REGISTRY["create_student_login"]
    set_password = TOOL_REGISTRY["set_profile_password"]
    for tool in (create_login, set_password):
        assert is_tool_authorized(OWNER, tool)
        assert is_tool_authorized(PRINCIPAL, tool)
        assert not is_tool_authorized(MANAGEMENT, tool)
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
