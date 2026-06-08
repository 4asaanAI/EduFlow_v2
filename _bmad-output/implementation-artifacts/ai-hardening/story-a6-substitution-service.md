# Story A.6 — Substitution service parity

**Epic:** A · **Status:** DONE (4 new tests + existing phase3 substitution test green; parity byte-identical; zero new failures)
**FRs:** FR13, FR14

## Case-by-case parity resolution
The AI tool and REST route diverged substantially (different input contracts + missing fields):

| Behavior | Old AI tool | REST route | **Canonical (service)** |
|---|---|---|---|
| `status` field | ❌ omitted | `"assigned"` | `"assigned"` (AI fix) |
| write mode | plain `insert` (dup-prone) | `upsert` dedup on (date, absent, class, period) | `upsert` dedup (AI fix) |
| audit action | `initiate_substitution` | `assign` | `assign` |
| `period_id` field | present | absent | dropped (aligns to REST) |
| substitute notification | ✅ notifies | ❌ none | ✅ notify (additive on REST → "fan-out matches") |
| input contract | `absent_staff_id/substitute_staff_id/period_id`(+slot lookup) | `*_teacher_id/period_number` | each adapter resolves its own shape → passes canonical fields |

## Implementation
- `services/substitution_service.py::initiate_substitution(db, actor_ctx, params, *, session=None, idempotency_key=None)`
  — writes the canonical substitution (status `assigned`, upsert-dedup), `assign` audit, and notifies the substitute.
- `routes/academics.py::create_substitution` → thin adapter (keeps its body required-field 400; now also notifies via service).
- `ai/tool_functions_v2.py::tool_initiate_substitution` → thin adapter; keeps its timetable-slot resolution
  (period_id → subject_id/period_number), then calls the service. Now writes status + upserts + `assign` audit.

## Parity / audit
- Parity test (`parity/substitution_parity_test.py`): REST (explicit period_number/subject_id) vs AI (slot-resolved)
  → substitution doc + `assign` audit + `substitution_assigned` notification byte-identical (mask ids/timestamps;
  also `entity_id`/`record_id`/`source_id` since they reference the freshly-generated substitution id).
- Existing `test_phase3_capabilities.py` substitution-plan test stays green (REST characterization).
- grep audit: create_substitution handler now has 0 `scoped_filter`/`scoped_query` (delegates to service; the
  upsert filter is school-scoped by ScopedCollection on upsert in prod, matching the prior REST behavior).
