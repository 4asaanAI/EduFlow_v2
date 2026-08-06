from __future__ import annotations

"""The recycle bin, the NSO list and the TC-issued list, for students and staff.

Owner request 10, 2026-08-06. These are three views of the same collection, which is
why one helper in `services/enrolment_status.py` answers for both the student list and
the staff list. The point of the tests is that the three views stay distinct: an NSO
person is not a TC-issued person, and the recycle bin holds both.
"""

from middleware.auth import create_jwt


def _bearer(payload: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


OWNER = {"user_id": "own-1", "role": "owner", "sub_category": "owner", "name": "Aman Litt"}
PRINCIPAL = {"user_id": "prn-1", "role": "admin", "sub_category": "principal", "name": "P"}
ACCOUNTANT = {"user_id": "acc-1", "role": "admin", "sub_category": "accountant", "name": "A"}
TEACHER = {"user_id": "tch-1", "role": "teacher", "name": "T"}


def _ids(response) -> set:
    return {row["id"] for row in response.json()["data"]}


def _make_student(client, auth_headers, student_data, state=None) -> str:
    resp = client.post("/api/students", json=student_data, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    student_id = resp.json()["data"]["id"]
    if state:
        moved = client.post(
            f"/api/students/{student_id}/enrolment", json={"state": state}, headers=_bearer(OWNER)
        )
        assert moved.status_code == 200, moved.text
    return student_id


# ─── Who may look at people who are off the roll ────────────────────────────────

def test_the_recycle_bin_is_refused_to_an_accountant(client):
    resp = client.get("/api/students?enrolment_state=off_roll", headers=_bearer(ACCOUNTANT))
    assert resp.status_code == 403


def test_the_nso_list_is_refused_to_a_teacher(client):
    resp = client.get("/api/students?enrolment_state=nso", headers=_bearer(TEACHER))
    assert resp.status_code == 403


def test_the_principal_may_open_the_recycle_bin(client):
    # The principal may press Restore, so a principal who cannot see the list cannot
    # use the button they are allowed to press.
    resp = client.get("/api/students?enrolment_state=off_roll", headers=_bearer(PRINCIPAL))
    assert resp.status_code == 200


def test_a_teacher_may_still_ask_for_the_daily_register(client):
    # `on_register` is the one off-roll-touching view a teacher needs: an NSO child is
    # marked absent every morning, which is the entire reason the state exists.
    resp = client.get("/api/students?enrolment_state=on_register", headers=_bearer(TEACHER))
    assert resp.status_code == 200


def test_an_unknown_view_is_a_400_not_a_silent_full_list(client):
    resp = client.get("/api/students?enrolment_state=everyone", headers=_bearer(OWNER))
    assert resp.status_code == 400


# ─── The three views are actually different ─────────────────────────────────────

def test_the_three_student_views_hold_the_right_people(client, auth_headers, student_data):
    on_roll = _make_student(client, auth_headers, {**student_data, "name": "On Roll"})
    nso = _make_student(client, auth_headers, {**student_data, "name": "Nso One", "roll_number": "R-NSO"}, state="nso")
    left = _make_student(client, auth_headers, {**student_data, "name": "Gone", "roll_number": "R-TC"}, state="tc_issued")

    headers = _bearer(OWNER)
    active = _ids(client.get("/api/students?enrolment_state=active&limit=500", headers=headers))
    nso_list = _ids(client.get("/api/students?enrolment_state=nso&limit=500", headers=headers))
    tc_list = _ids(client.get("/api/students?enrolment_state=tc_issued&limit=500", headers=headers))
    bin_list = _ids(client.get("/api/students?enrolment_state=off_roll&limit=500", headers=headers))
    register = _ids(client.get("/api/students?enrolment_state=on_register&limit=500", headers=headers))

    assert on_roll in active and nso not in active and left not in active
    assert nso_list & {on_roll, nso, left} == {nso}
    assert tc_list & {on_roll, nso, left} == {left}
    # The recycle bin is everything off the roll, which is both of them.
    assert bin_list & {on_roll, nso, left} == {nso, left}
    # The register is on the roll PLUS NSO, and never the child who has their TC.
    assert register & {on_roll, nso, left} == {on_roll, nso}


def test_a_row_says_which_state_it_is_in(client, auth_headers, student_data):
    # So the screen can badge a row without owning a second copy of the rule.
    nso = _make_student(client, auth_headers, {**student_data, "name": "Badged"}, state="nso")
    rows = client.get("/api/students?enrolment_state=nso&limit=500", headers=_bearer(OWNER)).json()["data"]
    row = next(r for r in rows if r["id"] == nso)
    assert row["enrolment_state"] == "nso"
    assert "register" in row["enrolment_label"]


def test_searching_inside_a_view_stays_inside_that_view(client, auth_headers, student_data):
    """The regression this guards: "on the register" is itself an OR, so a search
    term used to overwrite it and quietly search the whole school."""
    _make_student(client, auth_headers, {**student_data, "name": "Findable Gone", "roll_number": "R-G"}, state="tc_issued")
    kept = _make_student(client, auth_headers, {**student_data, "name": "Findable Here", "roll_number": "R-H"})

    found = _ids(client.get(
        "/api/students?enrolment_state=on_register&search=Findable&limit=500", headers=_bearer(OWNER)
    ))
    assert kept in found
    assert all(
        row["enrolment_state"] != "tc_issued"
        for row in client.get(
            "/api/students?enrolment_state=on_register&search=Findable&limit=500", headers=_bearer(OWNER)
        ).json()["data"]
    )


# ─── The counts people read ─────────────────────────────────────────────────────

def test_the_summary_counts_the_roll_and_the_nso_list_separately(client, auth_headers, student_data):
    """Owner request 10: Flo must never answer "1,801 students" when the honest
    answer is "1,801 on the roll, 3 on the NSO list who are still marked every day"."""
    before = client.get("/api/students/enrolment-summary", headers=_bearer(OWNER)).json()["data"]

    _make_student(client, auth_headers, {**student_data, "name": "Counted"})
    _make_student(client, auth_headers, {**student_data, "name": "Nso Counted", "roll_number": "R-N2"}, state="nso")

    after = client.get("/api/students/enrolment-summary", headers=_bearer(OWNER)).json()["data"]

    assert after["on_roll"] == before["on_roll"] + 1
    assert after["nso"] == before["nso"] + 1
    # The register is the sum of the two, which is the number of names a teacher marks.
    assert after["on_register"] == after["on_roll"] + after["nso"]


def test_the_summary_is_refused_to_a_signed_out_visitor(client):
    assert client.get("/api/students/enrolment-summary").status_code == 401


def test_the_summary_is_refused_to_a_parent(client):
    resp = client.get(
        "/api/students/enrolment-summary",
        headers=_bearer({"user_id": "par-1", "role": "parent", "name": "G"}),
    )
    assert resp.status_code == 403


# ─── The staff twin ─────────────────────────────────────────────────────────────

def _make_staff(client, auth_headers, name, state=None) -> str:
    resp = client.post(
        "/api/staff/",
        json={"name": name, "staff_type": "teacher", "role": "teacher"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    staff_id = resp.json()["data"]["id"]
    if state:
        moved = client.post(
            f"/api/staff/{staff_id}/enrolment", json={"state": state}, headers=_bearer(OWNER)
        )
        assert moved.status_code == 200, moved.text
    return staff_id


def test_the_three_staff_views_hold_the_right_people(client, auth_headers):
    on_roll = _make_staff(client, auth_headers, "Staff On Roll")
    nso = _make_staff(client, auth_headers, "Staff Nso", state="nso")
    left = _make_staff(client, auth_headers, "Staff Gone", state="tc_issued")

    headers = _bearer(OWNER)
    active = _ids(client.get("/api/staff/?enrolment_state=active&limit=500", headers=headers))
    nso_list = _ids(client.get("/api/staff/?enrolment_state=nso&limit=500", headers=headers))
    bin_list = _ids(client.get("/api/staff/?enrolment_state=off_roll&limit=500", headers=headers))

    assert on_roll in active and nso not in active and left not in active
    assert nso_list & {on_roll, nso, left} == {nso}
    assert bin_list & {on_roll, nso, left} == {nso, left}


def test_the_staff_recycle_bin_is_refused_to_an_accountant(client):
    resp = client.get("/api/staff/?enrolment_state=off_roll", headers=_bearer(ACCOUNTANT))
    assert resp.status_code == 403


def test_staff_can_be_searched_by_name(client, auth_headers):
    """Owner note, 2026-08-07: several lists had no way to search and no way to reach
    past the first page. This is the staff list half of that."""
    wanted = _make_staff(client, auth_headers, "Searchable Sunita")
    _make_staff(client, auth_headers, "Someone Else Entirely")

    found = _ids(client.get("/api/staff/?search=Sunita&limit=500", headers=_bearer(OWNER)))

    assert wanted in found
    assert len(found) == 1


def test_the_staff_summary_counts_the_roll_and_the_nso_list_separately(client, auth_headers):
    before = client.get("/api/staff/enrolment-summary", headers=_bearer(OWNER)).json()["data"]
    _make_staff(client, auth_headers, "Summary On Roll")
    _make_staff(client, auth_headers, "Summary Nso", state="nso")
    after = client.get("/api/staff/enrolment-summary", headers=_bearer(OWNER)).json()["data"]

    assert after["on_roll"] == before["on_roll"] + 1
    assert after["nso"] == before["nso"] + 1
    assert after["on_register"] == after["on_roll"] + after["nso"]


def test_the_staff_summary_unauthenticated_returns_401(client):
    assert client.get("/api/staff/enrolment-summary").status_code == 401


def test_the_staff_summary_wrong_role_returns_403(client):
    assert client.get("/api/staff/enrolment-summary", headers=_bearer(TEACHER)).status_code == 403
