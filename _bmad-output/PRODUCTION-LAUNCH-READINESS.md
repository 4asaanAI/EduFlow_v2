# EduFlow — Production Launch Readiness (The Aaryans, Joya)

**Target:** Full production launch for The Aaryans — **2,000+ users** — by **end of July 2026**.
**Created:** 2026-07-11 · **Owner sponsor:** Abhimanyu / Shubham · **School stakeholders:** Owner (Aman Litt), Principal (Adesh Singh)
**Current status:** Live in limited use — Owner + Principal are actively testing. R1–R15 reliability initiative shipped; chat/upload/responsive fixes live.

> This is the single tracking list to get from "owner+principal testing" to "2,000+ users live."
> Update the `Status` column as items land. P0 blocks launch; P1 is must-have; P2 is polish.

---

## Snapshot — what is already solid ✅

Verified against the live database + deployment on 2026-07-11:

- **All 2,000 logins are provisioned.** 1,802 students + 88 teachers + 7 admins + 1 owner all have working bcrypt passwords. Every student is flagged `must_change_password` (they set their own on first login). **Auth is not a blocker.**
- **Core data is linked.** All 1,802 students have a `class_id` (attendance + fees will work). 48 classes, 3,604 guardian records present.
- **Reliability shipped.** AI Layer Reliability (R1–R11) + Platform Reliability (R12–R15) merged and deployed to Elastic Beanstalk. Chat now never ends silently; frontend is screen-responsive; chat file-upload works via CloudFront; dummy data purged; principal profile corrected to Adesh Singh.
- **Deployment shape.** Backend on EB (`Eduflow-env-1`, ap-south-1) behind CloudFront; frontend on Amplify (auto-deploys from `main`); MongoDB Atlas; Azure OpenAI; Twilio SMS confirmed working (200 OK in logs).

---

## 🔴 P0 — Hard blockers (must fix before opening to 2,000 users)

| # | Item | Detail | Status |
|---|------|--------|--------|
| P0-1 | **Multi-worker SSE drops notifications** | **CONFIRMED bug.** Procfile runs `gunicorn --workers 4`, but the safety guard `validate_multi_worker_config()` checks the `WEB_CONCURRENCY` env var (unset → reads as 1), so it passes while 4 workers actually run with an **in-process** SSE registry and **no `REDIS_URL` broker**. A notification/live-update published on worker A never reaches a user whose SSE connection is on worker B (~75% intra-instance drop). Chat streaming itself is unaffected (same-request). **Fix:** either (a) run 1 worker/instance (`--workers 1` + `WEB_CONCURRENCY=1`) and rely on instance autoscaling — recommended, no new infra; or (b) add a Redis broker (`REDIS_URL`) for true multi-worker fan-out. | ☐ Not started |
| P0-2 | **Load & capacity test at 2K scale** | EB is B1 with autoscale 1→4 instances (CPU 70% trigger). No one has validated 2,000 users — especially the morning attendance rush + AI-chat spikes — against that + the current MongoDB Atlas tier. Run a realistic load test (peak concurrency, SSE fan-out, AI token throughput) and right-size instance/Atlas tiers before launch day. | ☐ Not started |

---

## 🟠 P1 — Must-have (weeks 2–3)

| # | Item | Detail | Status |
|---|------|--------|--------|
| P1-1 | **Durable file storage (S3) unconfigured** | Health endpoint reports `s3: not_configured`; `S3_BUCKET` is absent from the EB environment. Certificates, ID cards, student documents, and fee-receipt PDFs will not persist. Wire up the S3 bucket + IAM if any of those are in the launch scope. (Note: chat file-upload is in-memory and already works — this is about *durable* document storage.) | ☐ Not started |
| P1-2 | **Staff data quality** | **88/89 staff have blank `department`; 89/89 blank `subject`** (visible in the owner/principal UI). Also: ~23 staff from the official OASIS website list are not yet added; 57 DB teachers are not on the official list (stale/duplicates to reconcile). Backfill department/subject, add the new staff (with OASIS IDs), and reconcile the extras. | ☐ Not started |
| P1-3 | **Student credential rollout** | Logins exist and are provisioned, but there is no mechanism to distribute 1,802 students'/parents' username + temp password. Build a rollout path (SMS via the working Twilio integration, or printable credential slips). `must_change_password` is already set so first login forces a reset. | ☐ Not started |
| P1-4 | **Monitoring, alerting & backup drill** | Verify the LayaaStat / CloudWatch pipeline surfaces real errors; add an on-call alert on 5xx spikes / health-red; perform one real MongoDB Atlas restore drill to confirm backups are recoverable. | ☐ Not started |
| P1-5 | **Data migration: `accounts` → `accountant`** | One-time migration of `auth_users.sub_category: "accounts" → "accountant"`, then remove the `_is_accounts` backward-compat shim in `fees.py`. (Deferred item from R12/R13.) | ☐ Not started |
| P1-6 | **Data migration: Razorpay idempotency index** | Add unique index `{razorpay_reference_id: 1}` on `token_purchases` to make top-up dedupe DB-enforced (currently `find_one`-checked). (Deferred item from R12.) | ☐ Not started |
| P1-7 | **DPDP / minors posture** | Students are minors. Confirm the parental-consent gate posture (`SKIP_CONSENT_CHECK` must be false in prod) and make the guardian-contact-exposure decision flagged in R15.2 (least-exposure vs operational utility). | ☐ Not started |
| P1-8 | **Security review** | Public login surface for 2,000 users. Confirm rate limiting (shipped in R15) holds under load, run a security review of the auth + AI-write surfaces, and verify no secrets leak in logs/errors. | ☐ Not started |

---

## 🟡 P2 — Polish (as time permits)

| # | Item | Detail | Status |
|---|------|--------|--------|
| P2-1 | **Token-usage server-side aggregation** | `settings.py::get_token_usage_admin` does an unbounded `.to_list(None)` on `token_usage` (grows one row per LLM call). Replace with a Mongo aggregation before the table gets large. (R15.3) | ☐ Not started |
| P2-2 | **tz-aware UTC sweep** | ~120 naive `datetime.now()`/`utcnow()` calls across ~16 route files. Source-of-record already fixed; remaining calls are correct on UTC servers but lack the tz tag. Mechanical hygiene sweep. (R15.4) | ☐ Not started |
| P2-3 | **`chat.py` single-exit persistence** | Two pre-turn fatal paths (Phase-1 save-message, Phase-4 context-build) don't persist a fallback assistant message, and a few early returns skip the Phase-14 token debit. User-facing symptom is already covered by the R8 client backstop; this is backend consolidation. (R1/R8) | ☐ Not started |
| P2-4 | **`ai_rate_limiter` tenancy scoping** | `check_and_increment` uses `find_one_and_update`, which `ScopedCollection` doesn't override → schoolId injection bypassed on that call. No live impact on single-school-per-instance, but harden with real-Mongo verification. (R11.6) | ☐ Not started |
| P2-5 | **Dead-code cleanup** | Unused `_cert_prompt`/`_id_card_prompt` + imports in `image_gen.py`; test-infra gaps (`FakeCursor.sort` mixed-key TypeError, `FakeCollection.distinct` missing); pre-existing `LayoutRouting.test.js` harness failure. | ☐ Not started |

---

## 🔄 Ongoing

| # | Item | Detail | Status |
|---|------|--------|--------|
| ONG-1 | **UAT bug capture** | The owner + principal are already testing. Keep a simple running log of their findings so real-world bugs feed this list and get triaged into P0/P1/P2. | ☐ Ongoing |

---

## Suggested 3-week shape (to 2026-07-31)

- **Week 1 (Jul 11–17):** P0-1 (SSE multi-worker fix) + P0-2 (load test & right-size). Nothing else matters if the platform drops notifications or buckles at scale.
- **Week 2 (Jul 18–24):** P1-1 (S3), P1-2 (staff data), P1-5 + P1-6 (migrations), P1-8 (security review).
- **Week 3 (Jul 25–31):** P1-3 (credential rollout), P1-4 (monitoring + backup drill), P1-7 (DPDP); buffer for UAT bugs; P2 items only if time allows.

**Recommended first task: P0-1 (SSE multi-worker fix)** — confirmed, well-scoped, reversible. For launch, single-worker-per-instance + instance autoscaling is the simplest safe posture (no new infra); the guard was written to prefer exactly that.

---

## Change log

- 2026-07-11 — Initial launch-readiness plan created from a live DB + deployment probe.
