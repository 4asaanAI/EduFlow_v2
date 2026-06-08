# Story A.4 — Announcement service parity (moderation honored)

**Epic:** A · **Status:** DONE (10 new tests green; dual-entrypoint status parity; zero new failures vs pinned baseline)
**FRs:** FR13, FR14

## ⚠️ Notable behavior change (policy resolution) — please review
The committed code was **internally contradictory**: the REST route exempted owner/principal
from moderation (Policy A, EC-9.1, documented; `test_announcements.py` green confirms it), but the
AI `tool_create_announcement` moderated **everyone** (Policy B; `test_wave2_patches.py` green confirmed
owner→staff=pending). A shared gate can hold only ONE policy, so parity forced a choice.

**Decision: canonical = Policy A (the route), per the A.4 AC "exactly as the route does."** Rationale:
owner/principal ARE the approvers — self-moderation is a pointless round-trip; EC-9.1 is the later,
documented, intentional behavior. **Consequence:** an owner/principal AI announcement now **publishes
directly (active)** instead of being held for approval — matching the panel. Under the Phase-1 lockdown
(AI = owner/principal only), this means Phase-1 AI announcements are never self-held (correct).

- The 5 `test_announcement_moderation.py` tests assert the **pre-EC-9.1** "moderate owner too" policy and
  remain **pinned-failing** (they pre-date EC-9.1; not introduced or worsened here).
- 2 `test_wave2_patches.py` AI-unit tests that pinned the divergent owner→pending behavior were updated to
  use a **non-exempt role (reception)** so they still exercise the content gate (staff/students → pending).

## Implementation
- `services/announcement_service.py::decide_announcement_status(actor_ctx, audience_type, target_roles, *, raw_audience_roles=None)`
  — the single moderation gate (EC-9.1 + Story 7-47); raises `AnnouncementValidationError` (principal→owner).
- `routes/operations.py::create_announcement` → calls the gate (maps error to 422); the inline principal
  guard + the `_should_require_approval`/`_announcement_requires_approval` helpers + `PRINCIPAL_ALLOWED_AUDIENCES`
  were **deleted** (dead after centralization). `_announcement_target_roles` kept (audience resolution).
- `ai/tool_functions_v2.py::tool_create_announcement` → calls the gate (removes its duplicated inline gate),
  now honoring the owner/principal exemption.
- `project-context.md §Announcement Moderation` updated to point at the service (was referencing the deleted helper).

## Parity / audit
- Dual-entrypoint parity test (`parity/announcement_parity_test.py`): owner→all→active and reception→all→pending,
  identical via REST and AI.
- grep audit: create_announcement handler adds no `scoped_filter` (insert via `add_school_id`); clean.
