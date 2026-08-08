from __future__ import annotations

import importlib

import pytest

from tests.backend.conftest import FakeCollection


class Database:
    def __init__(self):
        self.staff = FakeCollection([
            {"id": "adesh-staff", "schoolId": "aaryans-joya", "branch_id": "branch-joya", "name": "ADESH SINGH", "user_id": "adesh-user"},
            {"id": "sonu-staff", "schoolId": "aaryans-joya", "branch_id": "branch-joya", "name": "SONU RUHAL", "user_id": "sonu-user", "role": "teacher"},
            {"id": "lalit-staff", "schoolId": "aaryans-joya", "branch_id": "branch-joya", "name": "LALIT THOMAS", "phone": "existing-phone"},
        ])
        self.auth_users = FakeCollection([
            {"id": "aman-user", "schoolId": "aaryans-joya", "username": "old-owner", "username_lower": "old-owner", "password_hash": "old", "user_info": {"id": "aman-user", "name": "Aman Litt", "role": "owner"}},
            {"id": "adesh-user", "schoolId": "aaryans-joya", "username": "old-principal", "username_lower": "old-principal", "password_hash": "old", "user_info": {"id": "adesh-user", "name": "ADESH SINGH", "role": "admin", "sub_category": "principal"}},
            {"id": "sonu-user", "schoolId": "aaryans-joya", "username": "SONURUHAL", "username_lower": "sonuruhal", "password_hash": "old", "user_info": {"id": "sonu-user", "name": "SONU RUHAL", "role": "teacher"}},
        ])
        self.users = FakeCollection()
        self.refresh_tokens = FakeCollection([
            {"id": "session-1", "user_id": "aman-user", "revoked_at": None},
            {"id": "session-2", "user_id": "sonu-user", "revoked_at": None},
        ])
        self.audit_logs = FakeCollection()


@pytest.mark.parametrize(
    "username,role,sub_category",
    [
        ("aman.litt", "owner", "owner"),
        ("adesh.singh", "admin", "principal"),
        ("sonu.ruhal", "admin", "accountant"),
        ("lalit.thomas", "admin", "management"),
    ],
)
async def test_migration_provisions_reviewed_accounts_without_password_change_gate(
    username, role, sub_category,
):
    migration = importlib.import_module("backend.migrations.031_provision_school_leadership_accounts")
    db = Database()

    await migration.migrate(db)

    auth = await db.auth_users.find_one({"username_lower": username})
    assert auth is not None
    assert auth["password_hash"].startswith("$2b$12$")
    assert auth["must_change_password"] is False
    assert auth["user_info"]["role"] == role
    assert auth["user_info"]["sub_category"] == sub_category
    assert auth["user_info"]["branch_id"] == "branch-joya"


async def test_migration_reuses_staff_rows_revokes_sessions_and_is_idempotent():
    migration = importlib.import_module("backend.migrations.031_provision_school_leadership_accounts")
    db = Database()

    await migration.migrate(db)
    await migration.migrate(db)

    assert len(db.staff.docs) == 3
    assert len(db.auth_users.docs) == 4
    sonu = await db.staff.find_one({"id": "sonu-staff"})
    assert sonu["phone"] == "8014646146"
    assert sonu["role"] == "admin"
    assert sonu["sub_category"] == "accountant"
    assert sonu["designation"] == "ACCOUNTANT HEAD"
    assert "email" not in sonu
    assert "dob" not in sonu
    assert "gender" not in sonu
    assert "qualification" not in sonu
    lalit = await db.staff.find_one({"id": "lalit-staff"})
    assert lalit["phone"] == "existing-phone"
    assert lalit["sub_category"] == "management"
    assert all(row.get("revoked_at") for row in db.refresh_tokens.docs)
    assert len(db.audit_logs.docs) == 8


async def test_migration_fails_closed_before_writes_when_lalit_is_ambiguous():
    migration = importlib.import_module("backend.migrations.031_provision_school_leadership_accounts")
    db = Database()
    db.staff.docs.append({
        "id": "lalit-duplicate",
        "schoolId": "aaryans-joya",
        "name": "Lalit   Thomas",
    })
    before_auth = [dict(row) for row in db.auth_users.docs]

    with pytest.raises(RuntimeError, match="multiple staff rows for Lalit Thomas"):
        await migration.migrate(db)

    assert db.auth_users.docs == before_auth


async def test_migration_fails_closed_on_username_collision():
    migration = importlib.import_module("backend.migrations.031_provision_school_leadership_accounts")
    db = Database()
    db.auth_users.docs.append({
        "id": "unrelated-user",
        "schoolId": "aaryans-joya",
        "username": "lalit.thomas",
        "username_lower": "lalit.thomas",
        "user_info": {"id": "unrelated-user", "name": "Someone Else", "role": "teacher"},
    })

    with pytest.raises(RuntimeError, match="username collision for lalit.thomas"):
        await migration.migrate(db)
