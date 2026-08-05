# Quick Spec: Durable Razorpay Webhook Inbox

**Status:** done

## Goal

Ensure a verified billing event cannot be lost when its business handler fails, while keeping all existing Razorpay idempotency protections.

## Acceptance Criteria

1. Every signature-verified event receives a stable provider ID or body-hash fallback.
2. The verified event is journaled before token/subscription mutation starts.
3. Successful processing marks the inbox row processed.
4. Failed processing marks the row failed and returns a retryable HTTP failure instead of acknowledging and losing it.
5. Re-delivery of a processed event returns success without running the business handler twice.
6. Signature failures are never journaled.
7. Inbox indexes support unique event identity and failed-event operations.
8. Existing Razorpay webhook tests and new durability tests pass.

## Non-Goals

- No provider change.
- No checkout UI or pricing change.
- No live webhook replay during this implementation.

## Suggested Review Order

1. Inbox persistence helpers.
2. Webhook route lifecycle.
3. Index and tests.
