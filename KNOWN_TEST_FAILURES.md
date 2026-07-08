# Known Backend Test Failures — origin/main baseline

**Date recorded:** 2026-07-08
**Recorded by:** environment/recovery setup pass (NOT fixed — documented only, per request)
**Branch:** `main` @ `f22e3ff` (fresh clone, in sync with origin)
**Interpreter:** Python 3.12.10 (venv at `backend/.venv`)
**Command:** `cd backend && .venv/Scripts/python -m pytest ../tests/backend -q`

## Summary

```
1290 collected / 12 deselected (mongo_real) / 1278 selected
1239 passed, 39 failed   (37.8s)
```

> ⚠️ These 39 failures are **pre-existing on `origin/main`** — they are NOT caused by the
> local environment/dependency setup. They are the "~25 pre-existing test failures" referenced
> in the abandoned `layaastat-integration-and-baseline-fixes` branch commit
> (`c807160` "…fix 25 pre-existing test failures…"), which was intentionally **not merged**
> (decision: keep `main` over the branch). The test *files* exist in `main`, but the
> *implementations* they exercise live only on that branch, so the tests 404 / AttributeError.
>
> **Deliberately left unfixed for now.**

## Root-cause categories

The failures are deterministic **behavioral** assertions (404 = route not registered in `main`,
`AttributeError` = function absent in `main`, wrong status value). `pytest.ini` does **not** set
`filterwarnings = error`, so the `DeprecationWarning` lines in tracebacks are context only, not the
cause. Nothing here is dependency-version drift.

| # | Feature area (missing in `main`) | Failing file | Count | Representative error |
|---|----------------------------------|--------------|-------|----------------------|
| 1 | School onboarding                | `unit/test_school_onboarding.py` | 15 | `routes.operator has no attribute 'send_welcome_email'`; routes 404 |
| 2 | Razorpay subscriptions/webhooks  | `unit/test_razorpay_checkout.py` | 6 | subscription endpoints `404`; role gate mismatches |
| 3 | Announcement moderation gate     | `api/test_announcement_moderation.py` | 5 | `assert 'active' == 'pending_approval'` |
| 4 | Owner Part-3 QA (FeeSync UI etc.)| `api/test_owner_part3_qa.py` | 4 | `FileNotFoundError: frontend/src/components/tools/FeeSync.js` (component only on branch) |
| 5 | Receptionist complaints (P11)    | `unit/test_receptionist_p11.py` | 2 | on-behalf-of / routing endpoints `404` |
| 6 | Multi-tenancy: school deactivate | `unit/test_multi_tenancy_enforcement.py` | 2 | `assert 404 == 403` / refresh-token invalidation |
| 7 | WhatsApp fee reminders           | `unit/test_whatsapp_reminders.py` | 1 | defaulters endpoint `404` |
| 8 | External fee sync                | `api/test_fee_sync.py` | 1 | `test_sync_requires_external_fee_env` |
| 9 | Staff CRUD pagination            | `api/test_staff.py` | 1 | `test_list_staff_paginates_and_sorts` |
| 10| Unauthenticated route surface    | `test_unauthenticated_surface.py` | 1 | `test_protected_get_routes_require_auth` |

## Full failing-test list (39)

```
api/test_announcement_moderation.py::test_all_audience_requires_approval_and_expands_roles
api/test_announcement_moderation.py::test_class_audience_requires_approval_and_targets_students
api/test_announcement_moderation.py::test_mixed_admin_teacher_still_pending
api/test_announcement_moderation.py::test_student_targeted_also_lands_in_pending
api/test_announcement_moderation.py::test_teacher_targeted_announcement_lands_in_pending
api/test_fee_sync.py::TestFeeSync::test_sync_requires_external_fee_env
api/test_owner_part3_qa.py::test_fee_sync_ui_displays_use_theirs_overwritten_fields
api/test_owner_part3_qa.py::test_frontend_announcement_broadcaster_sends_moderated_roles
api/test_owner_part3_qa.py::test_frontend_auth_headers_do_not_pass_stale_current_user[frontend/src/components/tools/FeeCollection.js]
api/test_owner_part3_qa.py::test_frontend_auth_headers_do_not_pass_stale_current_user[frontend/src/components/tools/FeeSync.js]
api/test_owner_part3_qa.py::test_frontend_auth_headers_do_not_pass_stale_current_user[frontend/src/components/tools/OwnerTools.js]
api/test_staff.py::TestStaffCrud::test_list_staff_paginates_and_sorts
test_unauthenticated_surface.py::test_protected_get_routes_require_auth
unit/test_multi_tenancy_enforcement.py::test_deactivate_school_invalidates_refresh_tokens
unit/test_multi_tenancy_enforcement.py::test_middleware_wrong_role_returns_403
unit/test_razorpay_checkout.py::test_create_checkout_session_wrong_role_403
unit/test_razorpay_checkout.py::test_create_subscription_session_owner_success
unit/test_razorpay_checkout.py::test_create_subscription_session_wrong_role_403
unit/test_razorpay_checkout.py::test_packs_endpoint_includes_subscriptions
unit/test_razorpay_checkout.py::test_webhook_payment_link_paid_credits_tokens
unit/test_razorpay_checkout.py::test_webhook_subscription_charged_credits_pool
unit/test_receptionist_p11.py::test_complaint_routing_fees_goes_to_accountant
unit/test_receptionist_p11.py::test_complaint_stores_on_behalf_of_phone
unit/test_school_onboarding.py::test_create_school_duplicate_id_returns_409
unit/test_school_onboarding.py::test_create_school_email_fail_open
unit/test_school_onboarding.py::test_create_school_invalid_slug_returns_400
unit/test_school_onboarding.py::test_create_school_invalid_slug_uppercase_returns_400
unit/test_school_onboarding.py::test_create_school_success
unit/test_school_onboarding.py::test_create_school_unauthenticated_returns_401
unit/test_school_onboarding.py::test_create_school_wrong_role_returns_403
unit/test_school_onboarding.py::test_deactivate_school_success
unit/test_school_onboarding.py::test_deactivate_school_unauthenticated_returns_401
unit/test_school_onboarding.py::test_deactivate_school_wrong_role_returns_403
unit/test_school_onboarding.py::test_onboarding_status_all_incomplete
unit/test_school_onboarding.py::test_onboarding_status_complete_sets_active
unit/test_school_onboarding.py::test_onboarding_status_partial
unit/test_school_onboarding.py::test_onboarding_status_unauthenticated_returns_401
unit/test_school_onboarding.py::test_onboarding_status_wrong_role_returns_403
unit/test_whatsapp_reminders.py::test_whatsapp_defaulters_owner_returns_ok
```

## Environment note (why the venv is Python 3.12, not 3.9)

- `.python-version` pins **3.12**; the app's Rust-built wheels (`bcrypt`, `cryptography`) require it.
- The machine's `py -3.9` resolves to **Python 3.9.0** (Oct 2020) — too old; its stable-ABI
  `python3.dll` is missing an entry point those wheels need, so imports fail with
  `DLL load failed while importing _bcrypt/_rust: The specified procedure could not be found`
  (`0xc0000139`). Python **3.12.10** was installed (winget, user scope) and the venv rebuilt on it.
- `numpy`/`pydantic-core` happened to import on 3.9.0, but `cryptography` + `bcrypt` did not, so
  the FastAPI app could not import at all on 3.9.0. 3.12 fixes it.

## Status

This file is **untracked** (not committed) — it does not affect `main`'s sync with origin.
No fixes applied. When ready to address these, the reference fix set is the un-merged
`layaastat-integration-and-baseline-fixes` branch (safe on origin @ `c807160`).
