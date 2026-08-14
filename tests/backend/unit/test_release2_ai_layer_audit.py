"""Release 2 audit of the AI layer for the four live profiles, 2026-08-12.

Written after checking every tool the owner, the principal, Sonu and Lalit reach. These
pin the three things the audit found, so none of them can quietly come back.

1. The two fee writes that cannot be taken back stop for a human decision. Writing
   `requires_confirmation: True` in a registry entry does NOT do that on its own: the loop
   at the foot of `tool_functions_v2.py` overwrites the flag from
   `EXPLICIT_CONFIRMATION_TOOL_NAMES`, so a tool whose description promises a confirm card
   can silently never show one. That trap has bitten this project before.
2. Flo reaches for the tool that RECOMPUTES a concession, not the one that types a figure
   in by hand, when somebody uses the office's everyday word "discount".
3. The accountant head's brief describes the fee powers he actually has.
"""

from __future__ import annotations

import pytest

from ai import tool_search
from ai.tool_access import is_tool_authorized
from ai.tool_functions_v2 import (
    EXPLICIT_CONFIRMATION_TOOL_NAMES,
    FINANCE_TOOL_NAMES,
    TOOL_REGISTRY,
)

STEP_10_TOOLS = [
    "explain_student_fee", "calculate_late_fine", "set_student_concession",
    "record_admission_concession", "set_right_to_education",
]

FINANCE_DESKS = {
    "owner": {"id": "o", "role": "owner"},
    "principal": {"id": "p", "role": "admin", "sub_category": "principal"},
    "accountant": {"id": "a", "role": "admin", "sub_category": "accountant"},
}
EVERYONE_ELSE = {
    "management": {"id": "m", "role": "admin", "sub_category": "management"},
    "teacher": {"id": "t", "role": "teacher"},
    "receptionist": {"id": "r", "role": "admin", "sub_category": "receptionist"},
    "transport_head": {"id": "x", "role": "admin", "sub_category": "transport_head"},
    "it_tech": {"id": "i", "role": "admin", "sub_category": "it_tech"},
    "maintenance": {"id": "n", "role": "admin", "sub_category": "maintenance"},
    "support_staff": {"id": "s", "role": "admin", "sub_category": "support_staff"},
}


@pytest.mark.parametrize("tool_name", STEP_10_TOOLS)
def test_every_new_fee_tool_is_finance_by_name(tool_name):
    # The classification loop still ends in `else: non_finance`, so a tool nobody
    # classifies lands with the management head, who must never see a rupee figure.
    assert tool_name in FINANCE_TOOL_NAMES
    assert TOOL_REGISTRY[tool_name]["access_domain"] == "finance"


@pytest.mark.parametrize("who", sorted(FINANCE_DESKS))
@pytest.mark.parametrize("tool_name", STEP_10_TOOLS)
def test_the_three_finance_desks_reach_all_five(who, tool_name):
    assert is_tool_authorized(FINANCE_DESKS[who], TOOL_REGISTRY[tool_name])


@pytest.mark.parametrize("who", sorted(EVERYONE_ELSE))
@pytest.mark.parametrize("tool_name", STEP_10_TOOLS)
def test_nobody_else_reaches_any_of_them(who, tool_name):
    assert not is_tool_authorized(EVERYONE_ELSE[who], TOOL_REGISTRY[tool_name])


@pytest.mark.parametrize("tool_name", STEP_10_TOOLS[2:])
def test_the_three_fee_writes_are_ordinary_immediate_writes(tool_name):
    """Checked on the REGISTRY as it stands after the classification loop, not on what
    the entry was written with, because the loop is what decides.

    Writing ``requires_confirmation: True`` into a registry entry does nothing on its
    own: the loop at the foot of ``tool_functions_v2.py`` overwrites it from
    ``EXPLICIT_CONFIRMATION_TOOL_NAMES``. All three of these entries were written with
    that flag and none of them gets a confirm card, which is the trap this project has
    hit before with ``import_data_file``.

    They are ordinary writes ON PURPOSE, and the audit nearly changed that before
    checking. All three are single-record and reversible by one further call before any
    quarter is billed, and ``apply_discount`` - which puts a real discount on a real
    child - has always been an ordinary write here. They still go through the same
    token-bound, transactional, kill-switched and write-ahead-audited dispatcher.
    """
    assert tool_name not in EXPLICIT_CONFIRMATION_TOOL_NAMES
    assert TOOL_REGISTRY[tool_name]["requires_confirmation"] is False


def test_the_confirm_set_did_not_grow_to_accommodate_them():
    # The companion assertion lives in test_flo_profile_matrix.py, which pins the confirm
    # set to exactly destructive, bulk, reversals and security-sensitive. This one says
    # the same thing from the Release 2 side, so a later run cannot quietly widen it.
    from ai.tool_functions_v2 import BULK_TOOL_NAMES

    destructive = {n for n, t in TOOL_REGISTRY.items() if t.get("destructive")}
    assert EXPLICIT_CONFIRMATION_TOOL_NAMES == destructive | set(BULK_TOOL_NAMES) | {
        # "post_pos_return" was here until 2026-08-14 and went with campus retail.
        "correct_fee_transaction", "correct_salary_disbursement",
        "change_accounting_period_status", "set_profile_password",
        # R4-5, 2026-08-12. The set grew by one, and the Release 2 concern this test
        # guards is unharmed: it was written to stop the confirm set being widened to
        # make ORDINARY SCHOOL WRITES feel safer, which is a design change dressed as a
        # tidy-up. `report_platform_problem` is not a school write at all. It is the only
        # tool that sends anything out of the school, and the confirm card is how a
        # person tells "Flo helped me" from "Flo told my supplier what I was doing".
        "report_platform_problem",
        # A6, 2026-08-14. The set grew by one again, and again the Release 2 concern is
        # unharmed. `enroll_admission_application` is not an ordinary school write made
        # to feel safer: it is the one write that brings a person into existence, and
        # nothing takes it back. The other four admissions tools added in the same run
        # are ordinary single-record writes and are deliberately NOT here.
        "enroll_admission_application",
    }


@pytest.mark.parametrize("phrase,expected", [
    ("employee child discount", "set_student_concession"),
    ("give this child the employee discount", "set_student_concession"),
    ("one time discount at admission", "record_admission_concession"),
    ("rte student", "explain_student_fee"),
    ("late fee", "calculate_late_fine"),
    ("fine for paying late", "calculate_late_fine"),
    ("why is this family charged this much", "explain_student_fee"),
])
def test_the_offices_own_words_find_the_tool_that_recomputes(phrase, expected):
    # `apply_discount` types a figure in by hand and would be wrong the next quarter. The
    # school calls its four named concessions "discounts", and the search ranks names
    # heavily, so without the synonyms in tool_search the everyday phrase found the wrong
    # tool on money.
    defs = {n: t for n, t in TOOL_REGISTRY.items()
            if is_tool_authorized(FINANCE_DESKS["accountant"], t)}
    assert tool_search.rank(phrase, defs)[0] == expected


def test_all_five_are_named_in_the_catalogue_flo_is_given():
    # Deferred loading lists tools BY NAME and fetches the schema on demand. A tool
    # missing from that list is a tool Flo cannot know exists.
    defs = {n: t for n, t in TOOL_REGISTRY.items()
            if is_tool_authorized(FINANCE_DESKS["accountant"], t)}
    catalogue = str(tool_search.catalogue_block(defs))
    for name in STEP_10_TOOLS:
        assert name in catalogue, f"{name} is not named in the catalogue Flo is given"


def test_the_accountant_brief_describes_the_fee_powers_he_has():
    from ai.prompts import ROLE_RULES as ROLE_BRIEFS

    brief = ROLE_BRIEFS[("admin", "accountant")].lower()
    for phrase in ["explain_student_fee", "set_student_concession",
                   "record_admission_concession", "set_right_to_education",
                   "calculate_late_fine"]:
        assert phrase in brief, f"Sonu's brief never mentions {phrase}"
    # And the one sentence that must never be lost.
    assert "only one daily fine" in brief


def test_the_management_brief_still_promises_no_rupee_figure():
    from ai.prompts import ROLE_RULES as ROLE_BRIEFS

    brief = ROLE_BRIEFS[("admin", "management")].lower()
    assert "never see a rupee figure" in brief
    for name in STEP_10_TOOLS:
        assert name not in brief, f"Lalit's brief offers {name}, which he cannot reach"


# ── Release 2 audit finding 8: the owner's daily summary and money ──────────


@pytest.mark.parametrize("action,expected", [
    ("concession_set", "changed a fee concession"),
    ("admission_concession_recorded", "changed a fee concession"),
    ("right_to_education_set", "changed a Right to Education place"),
    ("fee_charges_reworked_after_concession_change",
     "re-worked a family's bills after a concession changed"),
])
def test_the_daily_summary_says_what_happened_in_plain_words(action, expected):
    # Before this they all read as "changed something", which is a poor way to tell the
    # school's owner that a family's bill moved.
    from services.daily_digest_service import _describe_action

    assert _describe_action(action) == expected


def test_a_concession_change_counts_as_money_even_though_it_sits_on_the_child():
    # It is recorded against the student, so by collection alone the owner's money figure
    # missed it. Deciding a child owes no school fee at all is money by any reading.
    from services.daily_digest_service import FINANCE_ACTIONS, FINANCE_COLLECTIONS

    assert "student" not in FINANCE_COLLECTIONS
    for action in ("concession_set", "right_to_education_set"):
        assert any(word in action for word in FINANCE_ACTIONS)


# ── Release 2 audit finding: what an unclassified tool gets ─────────────────


def test_every_tool_is_classified_by_name_and_none_relies_on_the_default():
    from ai.tool_functions_v2 import (
        LEADERSHIP_ONLY_TOOL_NAMES, NON_FINANCE_TOOL_NAMES, SHARED_LOOKUP_TOOL_NAMES,
    )

    unlisted = [
        name for name in TOOL_REGISTRY
        if name not in FINANCE_TOOL_NAMES
        and name not in SHARED_LOOKUP_TOOL_NAMES
        and name not in LEADERSHIP_ONLY_TOOL_NAMES
        and name not in NON_FINANCE_TOOL_NAMES
    ]
    assert unlisted == [], (
        "These tools are on no list, so nobody has said who they belong to: "
        f"{sorted(unlisted)}. They now reach leadership only, which is the safe answer "
        "and probably not the intended one. Put each on the right list."
    )


def test_an_unclassified_tool_lands_on_leadership_and_not_on_the_management_head():
    """The default used to be `non_finance`, so a new tool nobody classified was handed
    to the one profile that must never see a rupee figure. This drives the real
    classification code with a made-up tool rather than asserting on a constant."""
    import importlib

    module = importlib.import_module("ai.tool_functions_v2")
    invented = {"tool_name": "invent_something_nobody_classified",
                "roles": ["owner", "admin"], "dispatch_type": "read"}

    # The same three questions the loop at the foot of that module asks, in order.
    name = invented["tool_name"]
    assert name not in module.LEADERSHIP_ONLY_TOOL_NAMES
    assert name not in FINANCE_TOOL_NAMES
    assert name not in module.SHARED_LOOKUP_TOOL_NAMES
    assert name not in module.NON_FINANCE_TOOL_NAMES

    invented["access_domain"] = "leadership"
    assert not is_tool_authorized(EVERYONE_ELSE["management"], invented)
    assert is_tool_authorized(FINANCE_DESKS["owner"], invented)


# ── Release 2 audit finding: what the same-day undo may put back ────────────


@pytest.mark.parametrize("field", ["rte_place", "concessions", "siblings"])
def test_the_undo_will_not_put_a_billing_decision_back(field):
    """A Right to Education place decides whether a family is billed at all, and these
    three are also the only writes that RE-WORK bills already raised. Putting the field
    back through the undo would leave those re-worked bills describing a rule that no
    longer applies, which is worse than not undoing at all. They are changed the way they
    were set instead, on the record or through Flo."""
    from services.undo_service import PROTECTED_FIELDS

    assert field in PROTECTED_FIELDS


# ── Release 2 audit finding: what "ready to send" is allowed to mean ────────


def test_whatsapp_says_the_real_obstacle_and_not_just_a_missing_setting(monkeypatch):
    """Naming a missing variable reads as "fill this in and it works". For WhatsApp that
    is untrue: there is no sender registered to the school and no approved school
    templates, so somebody would have set the variable, pressed send, and found out from
    a parent."""
    from services import messaging_service

    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC-real")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token")
    monkeypatch.delenv("TWILIO_WHATSAPP_FROM", raising=False)

    status = messaging_service.channel_status("whatsapp")
    assert status["ready"] is False
    joined = " ".join(status["warnings"]).lower()
    assert "sandbox" in joined
    assert "approve" in joined


def test_the_sandbox_number_is_called_out_even_when_it_is_set(monkeypatch):
    from services import messaging_service

    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC-real")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token")
    monkeypatch.setenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

    status = messaging_service.channel_status("whatsapp")
    assert status["ready"] is True          # the settings ARE filled in
    assert any("SANDBOX" in w for w in status["warnings"])


def test_an_american_sms_sender_is_called_out_for_an_indian_school(monkeypatch):
    from services import messaging_service

    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC-real")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+12286410951")

    status = messaging_service.channel_status("sms")
    assert status["ready"] is True
    assert any("not an Indian number" in w for w in status["warnings"])


def test_an_indian_sender_draws_no_warning(monkeypatch):
    from services import messaging_service

    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC-real")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+919876543210")

    assert messaging_service.channel_status("sms")["warnings"] == []


# ── The school on one page (Abhimanyu, 2026-08-12) ─────────────────────────


def test_only_the_two_who_run_the_school_reach_the_summary():
    tool = TOOL_REGISTRY["get_school_summary"]
    assert tool["access_domain"] == "leadership"
    for who in ("owner", "principal"):
        assert is_tool_authorized(FINANCE_DESKS[who], tool)
    for who in EVERYONE_ELSE:
        assert not is_tool_authorized(EVERYONE_ELSE[who], tool)
    # The accountant head runs the school's money and still does not get the whole page:
    # it carries the roll and everyone's changes as well.
    assert not is_tool_authorized(FINANCE_DESKS["accountant"], tool)
