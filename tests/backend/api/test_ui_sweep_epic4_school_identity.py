"""UI Sweep Epic 4 â€” the school's own identity.

Stories 4.3 (stored once, complete) and 4.4 (the assistant briefed from the record).

The defect these close is D-15/D-15b: the school's city was written into ten places,
five of them said Lucknow, correcting the code missed a stored value, and the assistant
kept answering from a module constant after the database had been fixed.
"""
from __future__ import annotations

import pytest

from middleware.auth import create_jwt

pytestmark = pytest.mark.asyncio


def _bearer(payload: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


def _owner():
    return _bearer({"user_id": "e4i-owner", "role": "owner", "name": "Owner"})


def _teacher():
    return _bearer({"user_id": "e4i-teach", "role": "teacher", "name": "Teacher"})


@pytest.fixture(autouse=True)
def _clean(fake_db):
    # Snapshot/restore — the FakeDb is a session-wide singleton, so wiping a
    # collection outright deletes rows other test files depend on.
    saved = list(fake_db.school_settings.docs)
    fake_db.school_settings.docs[:] = []
    yield
    fake_db.school_settings.docs[:] = saved


# â”€â”€ Story 4.3 â€” one verified source â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_no_stored_record_returns_the_verified_details(client, fake_db):
    """With nothing stored, the school still sees its OWN details â€” not a placeholder.

    This is the mechanism that let the city correction reach the product without a
    database write.
    """
    resp = client.get("/api/settings/school", headers=_owner())
    assert resp.status_code == 200
    d = resp.json()["data"]

    assert d["city"] == "Joya, Amroha"
    assert "Lucknow" not in str(d)
    assert d["affiliation_no"] == "2133014"
    assert d["school_code"] == "81936"
    assert d["email"] == "theaaryansjoya@gmail.com"
    assert d["website"] == "www.theaaryans.in"
    assert d["principal"] == "Adesh Singh"
    assert "Amroha" in d["address"]


def test_a_stored_value_always_wins(client, fake_db):
    fake_db.school_settings.docs.append({
        "id": "main", "schoolId": "aaryans-joya",
        "school_name": "The Aaryans", "city": "Somewhere Else",
    })
    resp = client.get("/api/settings/school", headers=_owner())
    d = resp.json()["data"]

    assert d["city"] == "Somewhere Else", "a stored record must not be overridden"
    # Fields the record does not carry still come from the verified source.
    assert d["affiliation_no"] == "2133014"


def test_a_field_the_owner_cleared_stays_cleared(client, fake_db):
    """A default that reinstates a value someone deliberately deleted is a defect
    wearing a good intention â€” and impossible for them to diagnose."""
    fake_db.school_settings.docs.append({
        "id": "main", "schoolId": "aaryans-joya", "website": "", "phone": "",
    })
    resp = client.get("/api/settings/school", headers=_owner())
    d = resp.json()["data"]

    assert d["website"] == "", "a cleared field must not be refilled by the fallback"
    assert d["phone"] == ""


def test_affiliation_number_is_settable_by_the_owner(client, fake_db):
    """A field the form posts but the whitelist drops is discarded silently â€” the
    Owner's edit vanishes behind a success message."""
    from services.org_config_service import SCHOOL_SETTINGS_FIELDS

    assert "affiliation_no" in SCHOOL_SETTINGS_FIELDS
    assert "school_code" in SCHOOL_SETTINGS_FIELDS

    resp = client.patch(
        "/api/settings/school",
        json={"affiliation_no": "2133014", "school_code": "81936"},
        headers=_owner(),
    )
    assert resp.status_code == 200
    stored = fake_db.school_settings.docs[0]
    assert stored["affiliation_no"] == "2133014"
    assert stored["school_code"] == "81936"


def test_every_form_field_is_accepted_by_the_server(client):
    """Guards the class of bug, not one instance: anything School Settings can post
    must be in the whitelist."""
    from services.org_config_service import SCHOOL_SETTINGS_FIELDS

    posted_by_the_form = {
        "school_name", "board", "established", "principal", "affiliation_no",
        "school_code", "city", "state", "address", "phone", "email", "website",
        "logo_url", "attendance_threshold", "ai_context",
    }
    missing = posted_by_the_form - set(SCHOOL_SETTINGS_FIELDS)
    assert not missing, f"School Settings posts these but the server drops them: {sorted(missing)}"


def test_school_profile_is_readable_by_every_role(client):
    resp = client.get("/api/settings/school", headers=_teacher())
    assert resp.status_code == 200
    assert resp.json()["data"]["city"] == "Joya, Amroha"


def test_school_settings_unauthenticated_returns_401(client):
    assert client.get("/api/settings/school").status_code == 401


def test_school_settings_update_wrong_role_returns_403(client):
    resp = client.patch("/api/settings/school", json={"city": "X"}, headers=_teacher())
    assert resp.status_code == 403


def test_no_screen_carries_a_hard_coded_school_identity():
    """D-15 was five files each writing the school's location in for themselves."""
    import pathlib
    import re

    src = pathlib.Path(__file__).resolve().parents[3] / "frontend" / "src"
    offenders = []
    for path in src.rglob("*.js"):
        if "__tests__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            if line.strip().startswith(("//", "*", "/*")):
                continue
            # "DPS Lucknow" is a legitimate example of ANOTHER school, used as the
            # placeholder in a transfer-certificate destination field. Filtered on the
            # full line, before truncation, or a long line hides the exemption.
            if "DPS Lucknow" in line:
                continue
            if re.search(r"Lucknow|0522-\d|theararyans", line):
                offenders.append(f"{path.name}: {line.strip()[:90]}")
    # DPS Lucknow is a legitimate example of ANOTHER school in a transfer-certificate
    # placeholder â€” the school's own identity is what must not be hard-coded.
    offenders = [o for o in offenders if "DPS Lucknow" not in o]
    assert not offenders, "hard-coded school identity found:\n" + "\n".join(offenders)


# â”€â”€ Story 4.4 â€” the assistant is briefed from the record â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_assistant_is_told_the_principals_name():
    """The builder read `principal_name`; the record stores `principal`. The lookup
    never once matched, so the assistant has never known who the principal is."""
    from ai.prompts import build_system_prompt

    prompt = build_system_prompt(
        user={"role": "owner", "name": "Owner"},
        school_context={},
        school_settings={"principal": "Adesh Singh"},
    )
    assert "Adesh Singh" in prompt


def test_assistant_identity_follows_the_stored_record():
    """Correcting the record must correct the assistant. It did not, which is exactly
    why it kept saying Lucknow after the data was fixed."""
    from ai.prompts import build_system_prompt

    prompt = build_system_prompt(
        user={"role": "owner", "name": "Owner"},
        school_context={},
        school_settings={
            "school_name": "Riverside Academy", "board": "ICSE", "city": "Nashik",
        },
    )
    assert "Riverside Academy" in prompt
    assert "Nashik" in prompt
    assert "The Aaryans" not in prompt
    assert "Joya" not in prompt


def test_assistant_never_says_lucknow_with_no_record():
    from ai.prompts import build_system_prompt, ORG_CONTEXT

    prompt = build_system_prompt(user={"role": "owner", "name": "Owner"}, school_context={})
    assert "Lucknow" not in prompt
    assert "Lucknow" not in ORG_CONTEXT
    assert "Joya, Amroha" in prompt


def test_assistant_gets_the_affiliation_and_contacts():
    from ai.prompts import build_system_prompt

    prompt = build_system_prompt(user={"role": "owner", "name": "Owner"}, school_context={})
    assert "2133014" in prompt
    assert "theaaryansjoya@gmail.com" in prompt
    assert "www.theaaryans.in" in prompt


def test_a_missing_detail_is_admitted_not_invented():
    """The assistant repeating a plausible phone number it made up is worse than it
    saying it does not have one."""
    from ai.prompts import build_system_prompt

    prompt = build_system_prompt(
        user={"role": "owner", "name": "Owner"},
        school_context={},
        school_settings={"phone": "", "email": "", "website": "", "affiliation_no": "",
                         "school_code": ""},
    )
    assert "not recorded" in prompt


def test_fee_structure_reaches_the_assistant_when_recorded():
    from ai.prompts import build_system_prompt

    summary = "Class IX-X: admission 16,500; composite 4,000/month; total 48,000/year."
    prompt = build_system_prompt(
        user={"role": "owner", "name": "Owner"},
        school_context={},
        school_settings={"ai_context": {"fee_structure": summary}},
    )
    assert summary in prompt


def test_no_fee_structure_recorded_adds_no_empty_section():
    from ai.prompts import build_system_prompt

    prompt = build_system_prompt(user={"role": "owner", "name": "Owner"}, school_context={})
    assert "FEE STRUCTURE" not in prompt


def test_context_builder_projects_the_fields_the_prompt_needs():
    """Widened projection, not a second query â€” this runs once per chat turn."""
    import inspect

    from ai import context_builder

    src = inspect.getsource(context_builder.build_school_context)
    projection_start = src.index("db.school_settings.find_one")
    projection = src[projection_start:projection_start + 500]
    for field in ("principal", "board", "city", "phone", "email", "website",
                  "affiliation_no", "ai_context"):
        assert f'"{field}": 1' in projection, f"{field} is not projected for the prompt"

    assert src.count("db.school_settings.find_one") == 1, (
        "the school record must be read once per turn, not twice"
    )

