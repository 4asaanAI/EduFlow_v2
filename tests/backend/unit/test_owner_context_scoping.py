from datetime import date

import pytest

from ai import context_builder
from tests.backend.conftest import FakeCollection

pytestmark = pytest.mark.asyncio


async def test_owner_context_excludes_other_school_rows(fake_db):
    today = date.today().strftime("%Y-%m-%d")
    touched = [
        "students",
        "staff",
        "student_attendance",
        "fee_transactions",
        "house_points",
        "library_books",
        "library_transactions",
        "vehicles",
        "transport_routes",
        "inventory",
    ]
    originals = {}
    missing = []
    for name in touched:
        if hasattr(fake_db, name):
            originals[name] = list(getattr(fake_db, name).docs)
        else:
            setattr(fake_db, name, FakeCollection())
            missing.append(name)

    try:
        fake_db.students.docs[:] = [
            {"id": "s1", "schoolId": "aaryans-joya", "is_active": True},
            {"id": "s2", "schoolId": "other-school", "is_active": True},
        ]
        fake_db.staff.docs[:] = [
            {"id": "st1", "schoolId": "aaryans-joya", "is_active": True},
            {"id": "st2", "schoolId": "other-school", "is_active": True},
        ]
        fake_db.student_attendance.docs[:] = [
            {"schoolId": "aaryans-joya", "date": today, "status": "present"},
            {"schoolId": "other-school", "date": today, "status": "absent"},
        ]
        fake_db.fee_transactions.docs[:] = [
            {"schoolId": "aaryans-joya", "status": "pending", "amount": 100},
            {"schoolId": "aaryans-joya", "status": "paid", "paid_date": today, "amount": 25},
            {"schoolId": "other-school", "status": "pending", "amount": 900},
            {"schoolId": "other-school", "status": "paid", "paid_date": today, "amount": 75},
        ]
        fake_db.house_points.docs[:] = []
        fake_db.library_books.docs[:] = []
        fake_db.library_transactions.docs[:] = []
        fake_db.vehicles.docs[:] = []
        fake_db.transport_routes.docs[:] = []
        fake_db.inventory.docs[:] = []

        ctx = await context_builder._build_owner_context(fake_db, today)

        assert ctx["total_students"] == 1
        assert ctx["total_staff"] == 1
        assert ctx["attendance_rate"].startswith("100.0%")
        assert "100" in ctx["fee_outstanding"]
        assert "900" not in ctx["fee_outstanding"]
        assert "25" in ctx["todays_collections"]
        assert "75" not in ctx["todays_collections"]
    finally:
        for name, docs in originals.items():
            getattr(fake_db, name).docs[:] = docs
        for name in missing:
            delattr(fake_db, name)
