"""Who may reach the concession and late-fine routes, checked by calling them.

Release 2 audit, 2026-08-12. The permission sweep counts routes per profile, which is a
good drift alarm and is not the same as watching the door refuse somebody. Every new
endpoint in this project needs an unauthenticated test and a wrong-role test; these are
the wrong-role halves for the five routes added in step 10.

The one that matters is the management head. Every one of these routes either names a
rupee figure on a family's bill or decides whether one is owed, and decision 1 says Lalit
never sees a rupee figure.
"""

from __future__ import annotations

import pytest

from middleware.auth import create_jwt

ROUTES = [
    ("get", "/api/fees/concessions/stu-1/explain", None),
    ("post", "/api/fees/concessions/set",
     {"student_id": "stu-1", "concession": "sibling", "granted": True}),
    ("post", "/api/fees/concessions/admission",
     {"student_id": "stu-1", "amount": 100, "authorised_by": "Aman Litt"}),
    ("post", "/api/fees/concessions/right-to-education",
     {"student_id": "stu-1", "holds_place": True, "reason": "letter seen"}),
    ("post", "/api/fees/late-fine/calculate",
     {"quarters": [], "as_of": "2026-09-01"}),
]

REFUSED = {
    "management": {"user_id": "m", "role": "admin", "sub_category": "management", "name": "Lalit"},
    "teacher": {"user_id": "t", "role": "teacher", "name": "A Teacher"},
    "student": {"user_id": "s", "role": "student", "name": "A Student"},
    "parent": {"user_id": "g", "role": "parent", "name": "A Parent"},
    "receptionist": {"user_id": "r", "role": "admin", "sub_category": "receptionist", "name": "Front desk"},
}

ALLOWED = {
    "owner": {"user_id": "o", "role": "owner", "name": "Aman"},
    "principal": {"user_id": "p", "role": "admin", "sub_category": "principal", "name": "Adesh"},
    "accountant": {"user_id": "a", "role": "admin", "sub_category": "accountant", "name": "Sonu"},
}


def _headers(claims):
    return {"Authorization": "Bearer " + create_jwt({**claims, "schoolId": "aaryans-joya"})}


def _call(client, method, path, body, headers):
    if method == "get":
        return client.get(path, headers=headers)
    return client.post(path, json=body or {}, headers=headers)


@pytest.mark.parametrize("method,path,body", ROUTES)
@pytest.mark.parametrize("who", sorted(REFUSED))
def test_the_wrong_desk_is_refused(client, method, path, body, who):
    resp = _call(client, method, path, body, _headers(REFUSED[who]))
    assert resp.status_code == 403, (
        f"{who} reached {method.upper()} {path} and got {resp.status_code}. Every one of "
        "these routes is money."
    )


@pytest.mark.parametrize("method,path,body", ROUTES)
@pytest.mark.parametrize("who", sorted(ALLOWED))
def test_the_three_finance_desks_are_not_refused(client, method, path, body, who):
    # They must REACH the route. A 404 on a made-up student is a working door; a 403
    # would make their own screens dead buttons, which is the defect shape this
    # initiative keeps finding.
    resp = _call(client, method, path, body, _headers(ALLOWED[who]))
    assert resp.status_code != 403, f"{who} was refused {method.upper()} {path}"


@pytest.mark.parametrize("method,path,body", ROUTES)
def test_no_authorization_header_is_refused(client, method, path, body):
    resp = _call(client, method, path, body, {})
    assert resp.status_code == 401
