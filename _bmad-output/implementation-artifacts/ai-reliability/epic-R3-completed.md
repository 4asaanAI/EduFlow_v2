# Epic R3 — Prompt ↔ Registry Parity · Completed Log

**Goal:** the LLM is never advertised a tool that doesn't exist, isn't authorized,
or has a different schema. Fixes audit C4, H1, H2, H3, L4, L5, XM8.

**Branch:** `ai-reliability-r1-turn-completion` (R1/R2/R3 on the same branch per the standing instruction).
**Baseline:** 1313 passed (after R2) → **after R3: 1326 passed / 0 failed / 0 skipped** (13 mongo_real deselected).

---

## R3.1 — Canonical sub_category keys (C4)
**Files:** `backend/ai/prompts.py`, `backend/ai/context_builder.py`

- `TOOLS_BY_ROLE` key `("admin", "accounts")` → `("admin", "accountant")`; the
  `ROLE_RULES` key likewise. An accountant (`sub_category == "accountant"`) no
  longer falls through to the principal fallback tool list.
- `context_builder.build_school_context`: `sub_category == "accounts"` →
  `"accountant"`, so accountants get the **accounts-scoped context**, not the
  principal context (which over-exposes attendance/leaves/transport).

**ACs:** AC1 ✅ AC2 ✅
**Tests:** `parity/prompt_registry_parity_test.py::test_accountant_gets_accounts_not_principal_tools`,
`unit/test_r3_prompt_registry_parity.py::test_accountant_resolves_to_accounts_tools`,
`::test_accountant_context_is_accounts_not_principal`.

## R3.2 — Fix advertised schemas + dedup constants (H1, H3, L4)
**Files:** `backend/ai/prompts.py`, `backend/ai/tool_functions_v2.py`, `backend/routes/chat.py`

- **AC1 (award_house_points):** prompt schema `house_name/points/reason` →
  `student_name/points/reason` (the impl resolves the student, then their house).
  `category` was accepted but **never persisted** to the house-points service —
  dropped from the registry schema, the impl, and the confirm message.
- **AC2 (dedup):** the mid-module rebind of `TOOL_QUERY_MAINTENANCE_REQUESTS`,
  `TOOL_QUERY_AUDIT_LOG`, `TOOL_CONFIRM_RESOLUTION` (drifted schemas —
  `confirm_resolution` taught `ticket_id/resolution_note` vs the impl's
  `request_id/confirmation_note`) was **deleted**; the single canonical
  definitions (matching the registry) are reused. `confirm_resolution` is
  registry owner-only, so it is no longer advertised to maintenance admins.
  `query_maintenance_requests` gained `it_tech` in its registry `sub_categories`
  so the (already-intended) IT-tech ticket read matches the prompt.
- **AC3 (ghost filters):** `search_students` prompt param `search_term` → `query`
  (the impl reads `query`); `get_student_profile` `sections` ghost removed (prompt
  now advertises `student_id`/`search_term` per the impl); `get_fee_transactions`
  `class_name`/`days` ghosts removed (the impl reads only `student_id`/`status`).
- **AC4 (dedup labels):** `WRITE_TOOL_PARAM_LABELS` duplicate keys `content` and
  `student_name` collapsed to one entry each (Python had silently kept the later).
- Also fixed (surfaced by the gate): `get_school_pulse` (registry owner/admin-only)
  was advertised to all teacher variants → removed from the teacher tool lists.

**ACs:** AC1 ✅ AC2 ✅ AC3 ✅ AC4 ✅
**Tests:** `unit/test_r3_prompt_registry_parity.py::test_award_house_points_schema_matches_impl`
+ the parity gate assertions 1–3.

## R3.3 — Missing/unadvertised tools (H2, L5)
**Files:** `backend/ai/tool_functions_v2.py`, `backend/ai/prompts.py`

- **AC1 (get_announcements — H2):** implemented `tool_get_announcements` and
  registered it (`roles: ["student"]`). Student-safe: only **published**
  announcements (not drafts, not pending-approval) whose audience includes the
  caller's role; school-scoped automatically via the scoped db; a `days` window.
  Previously advertised to students but absent from the registry — a guaranteed
  dead tool call.
- **AC2 (recall_history — L5):** added to `_PRINCIPAL_TOOLS` — the registry
  already authorized principals; now it is actually advertised to them.

**ACs:** AC1 ✅ AC2 ✅
**Tests:** `unit/test_r3_prompt_registry_parity.py::test_get_announcements_*`,
parity gate `test_assertion4b_must_advertise_everywhere` (recall_history).

## R3.4 — The parity gate itself (XM8)
**Files:** `tests/backend/parity/prompt_registry_parity_test.py` (new), `backend/middleware/auth.py`

- New `VALID_SUB_CATEGORIES` frozenset in `middleware/auth.py` — the single source
  of truth for canonical sub_categories, imported by the gate.
- New CI gate module with the five §4 assertions for every `(role, sub_category)`
  prompt variant:
  1. every advertised tool exists in `TOOL_REGISTRY`;
  2. the advertising role/sub_category is registry-authorized (role + sub_category;
     the orthogonal Phase-1 action lockdown is deliberately excluded — it restricts
     execution, not tool existence);
  3. every advertised **required** param is satisfiable against the registry,
     directly or via a known name→id resolution alias (class_name→class_id, etc.);
  4. (a) every registry tool authorized for some variant is advertised to one of
     them, unless on the explicit `UNADVERTISED_OK` allowlist (26 panel-driven
     CRUD/ops tools); (b) `MUST_ADVERTISE_EVERYWHERE` tools (recall_history) appear
     for every authorized variant;
  5. prompt sub_category keys ⊆ `VALID_SUB_CATEGORIES`.
- All currently-known drift fixed so the gate is green at merge.

**ACs:** AC1–AC4 ✅ AC5 ✅
**Tests:** the 7 assertions in the new gate module.

**Design note on assertion 4 (reverse direction):** the architecture's ideal is
per-role exhaustive coverage ("every authorized tool appears in that role's
prompt"). A literal reading yields ~400 authorized-but-unadvertised pairs that are
overwhelmingly *intentional* (roles curate a focused tool subset; advertising all
65 tools to every admin would bloat the prompt and dilute the LLM). Implementing it
as a 400-entry allowlist would be brittle noise. The gate therefore realizes
assertion 4 in two meaningful forms: global coverage (no registry tool is dead in
*all* prompts) + a `MUST_ADVERTISE_EVERYWHERE` set for tools that must reach every
authorized role (the L5 class of bug). This catches real regressions without
encoding hundreds of intentional omissions.

---

## Files touched
- `backend/ai/prompts.py` — accountant keys, award_house_points/search_students/get_student_profile/get_fee_transactions schemas, constant dedup, get_school_pulse removed from teachers, recall_history added to principals.
- `backend/ai/context_builder.py` — accountant context routing.
- `backend/ai/tool_functions_v2.py` — award_house_points category drop, query_maintenance_requests it_tech sub_category, `tool_get_announcements` impl + registry entry.
- `backend/routes/chat.py` — WRITE_TOOL_PARAM_LABELS dedup.
- `backend/middleware/auth.py` — `VALID_SUB_CATEGORIES`.
- Tests: `parity/prompt_registry_parity_test.py` (new, 7), `unit/test_r3_prompt_registry_parity.py` (new, 9); updated `parity/write_classification_guard_test.py` (+get_announcements), `unit/test_wave2_patches.py` (query_maintenance_requests subs).
