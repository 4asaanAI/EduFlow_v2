"""Unit tests for middleware.auth role-helper dependencies.

Part 1.5 Patch K coverage: empty-tuple rejection, .get() robustness for
missing-role payloads, and dependency-shape conformance.
"""

from __future__ import annotations

import os
import sys
import types

import pytest
from fastapi import HTTPException

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from middleware import auth as auth_module  # noqa: E402


def _fake_request(headers=None):
    """Minimal stand-in for fastapi.Request with the attributes used by the helpers."""
    headers = headers or {}
    req = types.SimpleNamespace()
    req.headers = headers
    req.url = types.SimpleNamespace(path="/test")
    return req


def _patched_get_current_user(monkeypatch, user_dict):
    monkeypatch.setattr(auth_module, "get_current_user", lambda request: user_dict)


def test_require_role_empty_tuple_raises_at_factory():
    with pytest.raises(ValueError):
        auth_module.require_role()


def test_require_role_allows_matching_role(monkeypatch):
    _patched_get_current_user(monkeypatch, {"role": "owner"})
    dep = auth_module.require_role("owner", "admin")
    result = dep(_fake_request())
    assert result["role"] == "owner"


def test_require_role_denies_mismatched_role(monkeypatch):
    _patched_get_current_user(monkeypatch, {"role": "teacher"})
    dep = auth_module.require_role("owner", "admin")
    with pytest.raises(HTTPException) as exc:
        dep(_fake_request())
    assert exc.value.status_code == 403
    # Error must NOT leak the role list.
    assert exc.value.detail == "Forbidden"


def test_require_role_handles_missing_role_key(monkeypatch):
    # Patch K: dict without "role" must yield clean 403, not KeyError → 500.
    _patched_get_current_user(monkeypatch, {})
    dep = auth_module.require_role("owner")
    with pytest.raises(HTTPException) as exc:
        dep(_fake_request())
    assert exc.value.status_code == 403


def test_require_owner_allows_owner(monkeypatch):
    _patched_get_current_user(monkeypatch, {"role": "owner", "id": "u1"})
    assert auth_module.require_owner(_fake_request())["id"] == "u1"


def test_require_owner_denies_non_owner(monkeypatch):
    _patched_get_current_user(monkeypatch, {"role": "admin"})
    with pytest.raises(HTTPException) as exc:
        auth_module.require_owner(_fake_request())
    assert exc.value.status_code == 403
    assert exc.value.detail == "Forbidden"


def test_require_owner_handles_missing_role_key(monkeypatch):
    _patched_get_current_user(monkeypatch, {})
    with pytest.raises(HTTPException) as exc:
        auth_module.require_owner(_fake_request())
    assert exc.value.status_code == 403


def test_require_owner_or_principal_allows_owner(monkeypatch):
    _patched_get_current_user(monkeypatch, {"role": "owner"})
    assert auth_module.require_owner_or_principal(_fake_request())["role"] == "owner"


def test_require_owner_or_principal_allows_principal(monkeypatch):
    _patched_get_current_user(
        monkeypatch, {"role": "admin", "sub_category": "principal"}
    )
    assert auth_module.require_owner_or_principal(_fake_request())["role"] == "admin"


def test_require_owner_or_principal_denies_accountant(monkeypatch):
    _patched_get_current_user(
        monkeypatch, {"role": "admin", "sub_category": "accountant"}
    )
    with pytest.raises(HTTPException) as exc:
        auth_module.require_owner_or_principal(_fake_request())
    assert exc.value.status_code == 403


def test_require_owner_or_principal_handles_missing_keys(monkeypatch):
    _patched_get_current_user(monkeypatch, {})
    with pytest.raises(HTTPException) as exc:
        auth_module.require_owner_or_principal(_fake_request())
    assert exc.value.status_code == 403


# ─── require_owner_principal_or_management (academic structure section) ───────

def test_require_opm_allows_owner(monkeypatch):
    _patched_get_current_user(monkeypatch, {"role": "owner", "id": "u1"})
    assert auth_module.require_owner_principal_or_management(_fake_request())["id"] == "u1"


def test_require_opm_allows_principal(monkeypatch):
    _patched_get_current_user(monkeypatch, {"role": "admin", "sub_category": "principal"})
    assert auth_module.require_owner_principal_or_management(_fake_request())["role"] == "admin"


def test_require_opm_allows_management(monkeypatch):
    _patched_get_current_user(monkeypatch, {"role": "admin", "sub_category": "management"})
    assert auth_module.require_owner_principal_or_management(_fake_request())["role"] == "admin"


def test_require_opm_denies_accountant(monkeypatch):
    _patched_get_current_user(monkeypatch, {"role": "admin", "sub_category": "accountant"})
    with pytest.raises(HTTPException) as exc:
        auth_module.require_owner_principal_or_management(_fake_request())
    assert exc.value.status_code == 403
    assert exc.value.detail == "Forbidden"


def test_require_opm_denies_teacher(monkeypatch):
    _patched_get_current_user(monkeypatch, {"role": "teacher"})
    with pytest.raises(HTTPException) as exc:
        auth_module.require_owner_principal_or_management(_fake_request())
    assert exc.value.status_code == 403


def test_require_opm_handles_missing_keys(monkeypatch):
    _patched_get_current_user(monkeypatch, {})
    with pytest.raises(HTTPException) as exc:
        auth_module.require_owner_principal_or_management(_fake_request())
    assert exc.value.status_code == 403
