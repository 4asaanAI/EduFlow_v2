# Quick Spec: Enterprise Fee Lifecycle

**Status:** implemented; full-suite regression pending

## Goal

Add versioned fee configuration, installment scheduling, deterministic charge generation, and optional Razorpay school-fee checkout without changing existing transactions or requiring a live migration during development.

## Acceptance Criteria

1. Existing fee structures remain readable and editable; every update records an immutable revision snapshot.
2. Fee heads and installments are validated as positive, dated, and internally unique.
3. Charge preview returns exactly what generation would create without writing data.
4. Charge generation is idempotent per student, structure version, installment, and fee head.
5. Generated charges use the existing `fee_transactions` shape and summary math.
6. Student checkout is restricted to the student’s own outstanding transactions.
7. Guardian checkout is restricted to explicitly linked wards.
8. Razorpay payment links are optional and fail closed when configuration is absent.
9. Verified school-fee webhooks use the durable webhook inbox and idempotently settle charges.
10. Existing token billing behavior remains unchanged.
11. APIs have unauthenticated/wrong-role and lifecycle tests.
12. No command connects to or modifies the school’s live database.

## Non-Goals

- No automatic production scheduling or deployment.
- No mutation of existing live fee structures or transactions.
- No branding or theme changes.

## Suggested Review Order

1. Version and installment service.
2. Charge preview/generation endpoints.
3. School-fee checkout and webhook routing.
4. Panel wiring and tests.

## Implemented

- Immutable fee-structure revision snapshots and validated installment replacement.
- Dry-run charge previews and idempotent per-version charge generation.
- Owner schedule editor with responsive installment and fee-head controls.
- Student/guardian-scoped Razorpay hosted checkout and durable webhook settlement.
- Student fee-status checkout action without changing the existing page theme.
- Focused backend and frontend tests. No production connection or migration was run.
