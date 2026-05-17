# Deferred Work

## Deferred from: code review of 7-42-token-recharge-subscription-billing (2026-05-18)

- **Frontend handleRecharge silently swallows payment errors** — no user feedback when Stripe session creation fails (misconfigured key, 500, network error). Token bar stays showing "upgrade" but clicking does nothing. Phase 3 UX hardening. [frontend/src/components/ChatInterface.js]
- **customer.subscription.updated not handled** — subscription_status and subscription_current_period_end drift when Stripe fires plan-change, trial-end, or delinquency events. Delinquent accounts keep receiving renewal credits. Out of scope per story Scope Exclusions (Phase 3). [backend/routes/tokens.py — stripe_webhook]
- **conftest.py does not monkeypatch routes.tokens for full-suite tests** — the shared `client` fixture (main app) exercises real DB for token balance endpoints, while all other routes use FakeCollection. Pre-existing test isolation gap; masked by graceful fallback in get_balance. [tests/backend/conftest.py]
