from backend.tenant import add_school_id, scoped_filter, validate_school_id


def test_add_school_id_sets_default_when_missing(monkeypatch):
    monkeypatch.setenv("SCHOOL_ID", "school-1")

    assert add_school_id({"name": "A"}) == {"name": "A", "schoolId": "school-1"}


def test_add_school_id_preserves_existing_value(monkeypatch):
    monkeypatch.setenv("SCHOOL_ID", "school-1")

    assert add_school_id({"schoolId": "school-2"}) == {"schoolId": "school-2"}


def test_scoped_filter_adds_strict_school_clause(monkeypatch):
    """Story 7-45: scoped_filter uses strict schoolId match (no $exists:False fallback)."""
    monkeypatch.setenv("SCHOOL_ID", "school-1")

    scoped = scoped_filter({"is_active": True})

    assert scoped == {"$and": [{"is_active": True}, {"schoolId": "school-1"}]}


def test_scoped_filter_does_not_wrap_existing_school_filter():
    assert scoped_filter({"schoolId": "school-2", "is_active": True}) == {
        "schoolId": "school-2",
        "is_active": True,
    }


# ─── scoped_query — Part 1.5 Patch I ────────────────────────────────────────

import pytest

from backend.tenant import scoped_query


def test_scoped_query_none_query_with_branch(monkeypatch):
    monkeypatch.setenv("SCHOOL_ID", "school-1")
    result = scoped_query(None, branch_id="b1")
    assert {"branch_id": "b1"} in result["$and"]


def test_scoped_query_empty_dict_with_branch(monkeypatch):
    monkeypatch.setenv("SCHOOL_ID", "school-1")
    result = scoped_query({}, branch_id="b1")
    assert {"branch_id": "b1"} in result["$and"]


def test_scoped_query_composes_with_existing_query(monkeypatch):
    monkeypatch.setenv("SCHOOL_ID", "school-1")
    result = scoped_query({"name": "x"}, branch_id="b1")
    # The user query must still be present.
    assert any(clause.get("name") == "x" or clause == {"name": "x"}
               or (isinstance(clause, dict) and "$and" in clause)
               for clause in result.get("$and", []))
    assert {"branch_id": "b1"} in result["$and"]


def test_scoped_query_rejects_cross_branch_attempt():
    """Caller-supplied branch_id in query must not silently override parameter."""
    with pytest.raises(ValueError):
        scoped_query({"branch_id": "b2"}, branch_id="b1")


def test_scoped_query_matching_branch_id_no_double_clause():
    """When caller already pinned the same branch_id, do not duplicate."""
    result = scoped_query({"branch_id": "b1"}, branch_id="b1")
    # Should not contain $and with two branch_id clauses.
    if "$and" in result:
        branch_clauses = [c for c in result["$and"] if "branch_id" in c]
        assert len(branch_clauses) <= 1


def test_scoped_query_or_composes_correctly(monkeypatch):
    monkeypatch.setenv("SCHOOL_ID", "school-1")
    q = {"$or": [{"name": "a"}, {"name": "b"}]}
    result = scoped_query(q, branch_id="b1")
    assert {"branch_id": "b1"} in result["$and"]


def test_scoped_query_detects_nested_branch_id_conflict():
    """A branch_id buried in $and must be detected, not silently accepted."""
    q = {"$and": [{"branch_id": "b2"}, {"is_active": True}]}
    with pytest.raises(ValueError):
        scoped_query(q, branch_id="b1")


def test_scoped_query_detects_nested_branch_id_in_or():
    q = {"$or": [{"branch_id": "b2"}, {"is_active": True}]}
    with pytest.raises(ValueError):
        scoped_query(q, branch_id="b1")


def test_scoped_query_empty_string_branch_id_skipped(monkeypatch):
    """Empty string is treated as None — no false-safe `{branch_id: ""}` clause."""
    monkeypatch.setenv("SCHOOL_ID", "school-1")
    result = scoped_query({}, branch_id="")
    # No branch_id clause should appear anywhere.
    def _has_branch(node):
        if isinstance(node, dict):
            if "branch_id" in node:
                return True
            for v in node.values():
                if _has_branch(v):
                    return True
        elif isinstance(node, list):
            return any(_has_branch(x) for x in node)
        return False
    assert not _has_branch(result)


def test_scoped_query_both_axes(monkeypatch):
    monkeypatch.setenv("SCHOOL_ID", "school-1")
    result = scoped_query({}, school_id="school-x", branch_id="b1")
    flat = str(result)
    assert "school-x" in flat
    assert "b1" in flat


# ─── validate_school_id — Part 4 Story 4.1 ──────────────────────────────────

def test_validate_school_id_passes_in_development(monkeypatch):
    """SCHOOL_ID unset + ENVIRONMENT=development must not raise."""
    monkeypatch.delenv("SCHOOL_ID", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    validate_school_id()  # should not raise


def test_validate_school_id_passes_in_test_env(monkeypatch):
    """SCHOOL_ID unset + ENVIRONMENT=test must not raise."""
    monkeypatch.delenv("SCHOOL_ID", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "test")
    validate_school_id()  # should not raise


def test_validate_school_id_raises_in_production(monkeypatch):
    """SCHOOL_ID unset + ENVIRONMENT=production must raise ValueError."""
    monkeypatch.delenv("SCHOOL_ID", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(ValueError, match="SCHOOL_ID environment variable is required"):
        validate_school_id()


def test_validate_school_id_raises_in_staging(monkeypatch):
    """SCHOOL_ID unset + ENVIRONMENT=staging must raise ValueError."""
    monkeypatch.delenv("SCHOOL_ID", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "staging")
    with pytest.raises(ValueError, match="SCHOOL_ID"):
        validate_school_id()


def test_validate_school_id_passes_when_set_in_production(monkeypatch):
    """SCHOOL_ID set + ENVIRONMENT=production must not raise."""
    monkeypatch.setenv("SCHOOL_ID", "my-school")
    monkeypatch.setenv("ENVIRONMENT", "production")
    validate_school_id()  # should not raise
