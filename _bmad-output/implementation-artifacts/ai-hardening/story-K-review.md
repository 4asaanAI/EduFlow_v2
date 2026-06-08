# Epic K — Epic-Close Multi-Lens Review

**Epic:** K — School-internals CRUD (hardened AI tools) · **Date:** 2026-06-08
**Branch:** `ai-layer-hardening-plan` · **Reviewer:** Claude (Opus 4.8, 1M)

Scope reviewed: `services/fee_config_service.py`, `services/academic_structure_service.py`,
`services/org_config_service.py`; route adapters in `routes/fees.py`, `routes/settings.py`,
`routes/activities.py`; `ai/tool_functions_v2.py` (16 new tools + adapters + registry);
`routes/chat.py` (required-params + labels); parity tests
(`fee_config_parity_test.py`, `academic_structure_parity_test.py`, `org_config_parity_test.py`);
`tests/backend/unit/test_epic_k_crud_guardrails.py`; `tests/backend/parity/corpus.py`.

## Result
**Suite:** 1121 passed, 25 failed (pinned pre-existing baseline — unchanged), 12 deselected,
0 skipped, **0 NEW failures** vs `/tmp/baseline_failures.txt` (exact set match, verified by
`comm`). +~120 net new passing tests (parity + guardrails). All Epic K stories' ACs met;
parity byte-identical on all three stories; Phase-1 lockdown + owner-only org config verified.

## Stories delivered
- **K.1 Fee config:** `fee_config_service` (structures + discount types). 5 AI tools
  (create/update structure, create/update/delete discount type). `delete_discount_type`
  destructive (F.10). REST routes in `fees.py` now thin adapters.
- **K.2 Academic structure:** `academic_structure_service` (classes incl. section field +
  houses). Per the approved scope decision, **new service-backed REST routes were added**
  (`POST/PATCH/DELETE /api/settings/classes`, `POST/PATCH/DELETE /api/activities/houses`)
  as the parity reference — **no new UI**. 6 AI tools; class/house deletes destructive (F.10).
- **K.3 Org config:** `org_config_service` (branches + school settings + year-end). 5 AI
  tools, **owner-only** (org config stays owner-only even in Phase 2, AD15).
  `delete_branch` + `year_end_transition` destructive/high-impact (F.10). REST adapters in
  `settings.py`.

## Lenses run
bmad-code-review · bmad-review-adversarial-general · bmad-review-edge-case-hunter ·
bmad-testarch-test-review · bmad-testarch-trace · bmad-testarch-nfr.

## Findings & fixes

| # | Sev | Lens | File | Issue | Fix | Regression test |
|---|-----|------|------|-------|-----|-----------------|
| 1 | High | adversarial / NFR5 | `services/academic_structure_service.py` | `create_class` derived `branch_id` from `params.get("branch_id") or actor_ctx.branch_id` — a **branch-scoped principal could pass another branch's `branch_id`** and create a class outside their scope (privilege/tenancy escape). | Only an **owner** (cross-branch authority) may target an arbitrary branch via params; a non-owner is pinned to `actor_ctx.branch_id`. | `test_principal_cannot_create_class_in_other_branch`, `test_owner_may_target_branch_on_create_class` |
| 2 | High | test-review / isolation | `parity/academic_structure_parity_test.py`, `parity/org_config_parity_test.py` | The autouse `_clean` fixtures **emptied entire shared-singleton collections** (`classes`, `academic_years`) at teardown; `fake_db` is a session-level singleton, so wiping seeded `class-1` broke later `POST /api/students` FK-validation → **5 cross-file failures in Epic J's student parity** when the suite ran together. | Fixtures now **save & restore** the touched collections instead of nuking them; same hardening added to the K guardrails file. | full suite re-run: exact baseline (0 new failures) — was 30 failed, now 25 |
| 3 | Med | edge-case | `services/fee_config_service.py` | `update_fee_structure` previously `$set` the raw request body (could overwrite `id`/`schoolId`/`_id` → tenant/identity escape). | Strip `_IMMUTABLE_KEYS` before `$set`; doc shape otherwise preserved (characterization). | `test_update_fee_structure_strips_immutable_keys` |
| 4 | Med | edge-case | `services/*` | Delete ops could orphan references. | `delete_class`/`delete_house`/`delete_branch` raise `*ConflictError` (409) when active students are still assigned. | `test_delete_class_blocked_when_active_students_assigned`, `test_delete_house_blocked_*`, `test_delete_branch_blocked_*` |
| 5 | Low | edge-case | `services/academic_structure_service.py` | No-op class update wrote spurious audit. | No-op short-circuit (`{"noop": True}`, no audit). | `test_update_class_noop_when_unchanged` |
| 6 | Med | trace / F.10 | `ai/tool_functions_v2.py` | Every assistant-reachable delete + the high-impact year-end must carry the `destructive` flag so the F.10 two-step confirm + actor-tagged deletion audit fire. | All 5 destructive tools flagged; auto-picked into `DESTRUCTIVE_TOOL_NAMES`. | `test_destructive_tools_flagged`, `test_non_destructive_tools_not_flagged`, parity `test_delete_discount_type_is_registered_destructive` |

## Non-bugs / deliberate decisions (dismissed with reason)
- **Audit added to fee-structure create/update (new vs pre-extraction REST):** the K.1 AC
  requires "audited". The audit row is added to BOTH entrypoints through the shared service,
  so AI↔REST parity holds; the structure doc shape is unchanged (characterization preserved).
- **`year_end_transition` flagged `destructive` writes an `action="delete"` deletion-audit
  row.** Semantically year-end is not a delete, but the AC requires it to "route through
  F.10's two-step confirm"; reusing F.10 gives the two-step gate + an actor-tagged "who ran
  the high-impact op" row. Accepted as the intended behavior, not a bug.
- **K.3 org-config tools are `roles=["owner"]` (principal blocked at the registry), not the
  K.1/K.2 owner+principal pattern.** Per AD15 "org-level config (branches/settings) stays
  owner-only even in Phase 2." Verified by `test_org_config_is_owner_only`.
- **Houses are school-scoped (no branch).** Mirrors the existing `GET /activities/houses`
  model; `create_house` intentionally takes no branch.
- **DPDP-to-LLM on write results:** confirmed-write results are returned from
  `/api/chat/confirm` to the client, NOT re-fed to the LLM (same posture as Epics A–J). No
  special-category PII in these config domains anyway.
- **Sync tests under module `pytestmark = asyncio`** emit a cosmetic PytestWarning but
  execute correctly (established platform convention).

## scoped_filter / scoped_query audit
`routes/fees.py`, `routes/settings.py`, `routes/activities.py` — the only `scoped_filter(`
hits are the **pre-existing** `_fee_query`/`_settings_query`/`_scope` school-scope helper
definitions (used by many read routes). No new inline scoping was added to any route handler;
all mutations delegate to services. Services use `scoped_query(branch_id=…)` for the
branch-scoped class domain (owner = cross-branch via `branch_id=None`, principal = own branch)
and `scoped_filter(school_id)` for the school-scoped house/discount/branch domains. Audit clean.

## Parity corpus / CI drift gate
16 new entries added across the three parity modules; `test_parity_corpus.py` green — no
write tool ships without a parity entry.
