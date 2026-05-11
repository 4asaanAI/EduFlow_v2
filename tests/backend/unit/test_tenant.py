from backend.tenant import add_school_id, scoped_filter


def test_add_school_id_sets_default_when_missing(monkeypatch):
    monkeypatch.setenv("SCHOOL_ID", "school-1")

    assert add_school_id({"name": "A"}) == {"name": "A", "schoolId": "school-1"}


def test_add_school_id_preserves_existing_value(monkeypatch):
    monkeypatch.setenv("SCHOOL_ID", "school-1")

    assert add_school_id({"schoolId": "school-2"}) == {"schoolId": "school-2"}


def test_scoped_filter_adds_school_clause_without_dropping_legacy_docs(monkeypatch):
    monkeypatch.setenv("SCHOOL_ID", "school-1")

    scoped = scoped_filter({"is_active": True})

    assert scoped == {
        "$and": [
            {"is_active": True},
            {"$or": [{"schoolId": "school-1"}, {"schoolId": {"$exists": False}}]},
        ]
    }


def test_scoped_filter_does_not_wrap_existing_school_filter():
    assert scoped_filter({"schoolId": "school-2", "is_active": True}) == {
        "schoolId": "school-2",
        "is_active": True,
    }
