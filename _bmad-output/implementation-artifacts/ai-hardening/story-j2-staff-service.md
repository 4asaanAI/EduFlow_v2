# Story J.2 — Staff create & edit (hardened AI tools)

**Epic:** J · **Status:** DONE · **FRs:** FR41, AD15
**Phase-1 role gate:** Owner + Principal ONLY (`roles=["owner","admin"], sub_categories=["principal"]`).

## Scope
Expose existing staff create/edit (REST) to the assistant as hardened tools wrapping a
single shared `services/staff_service.py`. Create/edit only — staff hard-delete
(`DELETE /staff/{id}`, soft-deactivate + session revoke) is NOT AI-reachable in Phase 1;
any destructive staff op routes through F.10 (Epic J ships no delete tool).

## Shared service (`services/staff_service.py`, P1 signature)
- `create_staff(db, actor_ctx, params, *, ...)` → privileged-account gate (owner-only for
  owner/admin role or any sub_category), `_create_or_link_user` (auth_users create/link +
  temp password), `staff` insert, `create` audit + `credential_issued` audit.
- `update_staff(db, actor_ctx, params, *, ...)` → PROFILE_FIELDS whitelist, owner-only
  role/sub_category/salary, leave-balance authority (owner/principal), accounts-salary,
  OWNER_ONLY_FIELDS silent strip for non-owners, no-op short-circuit, auth_users user_info sync.
- Domain exceptions: `StaffValidationError`(400), `StaffNotFoundError`(404),
  `StaffAuthorizationError`(403), `LinkedUserNotFoundError`(404). Never `HTTPException`.

## Adapters
- `routes/staff.py`: create/update become thin adapters (parse → service → domain-error→HTTP).
- `ai/tool_functions_v2.py`: `tool_create_staff`, `tool_update_staff`.

## Security / parity / audit
- **Temp password is never surfaced to the LLM/chat** — the AI tool drops it from the
  returned data and emits an out-of-band-delivery note (regression test
  `test_create_staff_ai_does_not_leak_temp_password`). REST still returns it once for
  the human operator. DB state (hashed in `auth_users`) is identical → parity holds.
- Dual-entrypoint parity (`parity/staff_parity_test.py`): `staff` + `auth_users` +
  `audit_logs` byte-identical (volatile-masked incl. `password_hash`). Corpus entries added.
- OWNER_ONLY_FIELDS protection now lives in the service → applied identically on both paths.
- grep audit: staff create/update handlers delegate to the service (no inline `scoped_filter`
  mutation); existing `scoped_filter` hits on the other staff routes are read-only and unchanged.
