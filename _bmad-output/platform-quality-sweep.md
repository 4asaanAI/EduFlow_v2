# EduFlow Platform Quality Sweep — BMad Method Master Tracker

**Started:** 2026-05-15
**Goal:** Enterprise-grade quality across the entire platform via full BMad ceremony applied part-by-part.
**Method:** For each part — `document-project` → `create-architecture` (if needed) → `create-epics-and-stories` → `check-implementation-readiness` → per-story `CS → DS → QA → CR` → `retrospective` → adversarial review.

## Sequence

User-confirmed order: **3 → 1 → 2 → 4 → 5 → 6 → 7 → 8 → 9 → ...**

| # | Part | Status | Sub-stories | Started | Closed | Notes |
|---|---|---|---|---|---|---|
| 0 | **Hotfixes** | ✅ done | 3 P0 production failures | 2026-05-15 | 2026-05-15 | Closed before Part 5: GET /uploads/serve/{filename} now requires auth and school-scoped lookup; receipt download path is guarded and backend receipt endpoint is covered by regression test; staff leave approval now uses require_owner_or_principal. |
| 0.5 | **Pre-Part-9 Infra** | ✅ done | 3/3 stories | 2026-05-16 | 2026-05-16 | 5 indexes (exam_results, audit_logs, lesson_plans, sms_logs TTL, notifications), factories.py (6 factories), unauthenticated surface test (caught+fixed 9 open routes in academics/settings/students). |
| 1 | **Auth + RBAC** | ✅ done | 12/12 original concerns closed + all 16 Part 1.5 findings closed | 2026-05-15 | 2026-05-15 | Part 1 hardening + Part 1.5 fix sweep complete. ~119 of ~130 inline role checks migrated to `Depends(require_role/require_owner/require_owner_or_principal)`; 11 remaining are documented composite/dynamic gates annotated with `# auth:`. Migration 016 idempotent; scope_resolver denies by default; designation fallback removed; cookie phantom evicted; concurrent-refresh test now deterministically races; scoped_query rejects cross-branch attempts. 260 backend tests passing (up from 224 baseline). See `parts/auth-rbac/review-findings-and-fix-plan.md` for the 16 patches A–P. |
| 2 | **AI Layer** | ✅ done | 11 of 11 patches landed (P1–P11) | 2026-05-15 | 2026-05-15 | Audit done (47 raw findings → 11 patches). Wave 1 (P1–P5 Critical) `e8b4a70`. Wave 2 (P6–P11 Important+Polish) `7e82b31`. 311 backend tests passing (was 260 at Part 1 start). P6: registry sub_categories + _is_tool_authorized single gate; P7: announcement moderation in tool (pending_approval for teacher/student audience); P8: content filter on rich_blocks + tool data for students; P9: confirm-token tenant binding (school_id/branch_id), peek raises on Mongo error, $gte TTL, compensating decrement; P10: expires_at required on overrides, stable sort, migration 017; P11: safe_token_count coerce, restricted_exact+9 keys, phone exact-match, random.uniform delay, SSE keepalive comment, zero-width whitespace, _json_candidates rich extraction, numeric param validators. |
| 3 | **Owner role (vertical)** | ✅ done | 12/12 extracted FRs verified + full cross-part review sweep | 2026-05-15 | 2026-05-15 | Part 3 closed. All FRs verified. Full 5-agent party-mode review (Parts 1+2+3) found 29 additional bugs — all fixed across commits 13388ae, 22c467d, e260247. Backend: 387 tests passing (0 skipped). project-context.md fully refreshed (34 patterns). Key residual items deferred to Part 4: exports.py exam enrichment cross-tenant, require_access(role,sub_category) helper, migration 014 not in run_all.py, db.otps drop, branch-scope convention enforcement. |
| 4 | **Multi-tenancy + Data Layer** | ✅ done | 9/9 stories complete, full BMad ceremony | 2026-05-15 | 2026-05-15 | Full ceremony: document-project (10-file docs suite), architecture (4 ADRs), epics+stories (4 epics, 9 stories, 100% FR coverage), readiness check (READY), dev (E1+E2+E3+E4), retro, adversarial review (10 findings, 4 fixed). Commits 332743f→d79f333. 387→420 tests passing (0 skipped). Key wins: require_access() canonical auth helper, 35 AI tool scoped_query migrations, SCHOOL_ID startup guard, audit gate fail-open, migration 014 fix, otps dropped, 10-file docs/ suite generated. |
| 5 | **Notifications + Real-time (SSE)** | ✅ done | 6/6 sprint stories complete + P5.0/P5.4/P5.7 coverage | 2026-05-15 | 2026-05-15 | Canonical notification service with fail-open logging, route + AI notification migration, bounded fan-out, notification pagination meta fix, mark-all-read race boundary, compound index migration 019, chat keepalive data events, service keepalive loop, SSE session normalization, frontend stream_error retry path. Backend 450 tests passing; frontend build passing with existing warnings. |
| 6 | **File Storage + Uploads** | ✅ done | 6/6 sprint stories complete + P6.7/P6.8 coverage | 2026-05-15 | 2026-05-15 | Authenticated and school-scoped file serving, owner/admin-or-self access model, S3 tenant key prefixes, file_uploads schoolId backfill migration 020, role-based upload limits, manual magic-byte MIME validation, orphaned S3 rollback records, chat upload blocklist with ephemeral docs, optional persistence/audit for generated PDFs, scoped paginated list/delete, S3 error logging. Focused Part 6 suite: 32 tests passing. |
| 7 | **Observability + Audit** | ✅ done | 6/6 sprint stories complete + audit helper migration | 2026-05-15 | 2026-05-15 | Canonical fail-open audit helper, zero direct audit inserts outside the helper, branch-scoped/paginated audit reads, audit indexes migration 021, structured logging extras, auth success/failure logs without secrets, consistent error response shapes, slow-query instrumentation, S3/SMS readiness checks, and audit coverage matrix. Focused Part 7 suite: 79 tests passing. |
| 8 | **Frontend Foundation** | ✅ done | 10/10 stories complete | 2026-05-15 | 2026-05-15 | Jest/RTL setup, chat stream manual retry semantics, non-chat SSE reconnect/backoff, ConfirmActionCard double-submit guard, DOMPurify style/class/event stripping, contained tool ErrorBoundary, ToolPage loading/error primitives, singleton 401 refresh redirect, URL `?tool=` routing, semantic tokens, attendance draft TTL purge. Frontend tests: 7 suites / 16 tests passing. Frontend build passing with existing warnings. |
| 9 | **Principal role (vertical)** | ✅ done | 8/8 stories complete | 2026-05-16 | 2026-05-16 | P9.1 PrincipalDailyOps lesson plan card; P9.2 leave approval notification+audit+idempotency; P9.3 class-summary + staff/today attendance endpoints (aggregation pipeline); P9.4 announcement broadcast gate (principal direct, audience injection guard); P9.5 lesson-plan-completion endpoint + exam access; P9.6 fee-collection-summary → principal access; P9.7 OWNER_ONLY_FIELDS staff PATCH guard (self-update privilege escalation closed); P9.8 incident POST any-user + PATCH resolve principal. 507→545 tests. Security bonus: 9 open routes found+fixed by surface test. |
| 10 | **Accountant role (vertical)** | ✅ done | 9/9 stories complete | 2026-05-16 | 2026-05-16 | P10.0 URL audit (0 extra 404s); P10.1 partial payments + receipt endpoint; P10.2 FeeSync idempotency + hung-job timeout + polling; P10.3 fee structure POST/PATCH (owner-only); P10.4 discount approval gate (Decimal threshold, pending_discount_approvals); P10.5 correction own-only guard + original_snapshot + correction_count; P10.6 expense auth → owner/accountant only + expense summary; P10.7 export 7→13 columns + N+1 batch fix; P10.8 payroll routes (new backend/routes/payroll.py + unique disbursement index). 545→598 tests (+53). |
| 11 | **Receptionist role (vertical)** | ✅ done | 5/5 stories + full ceremony | 2026-05-15 | 2026-05-16 | Party-mode review found 27 bugs — branch isolation (scoped_filter→scoped_query across all 13 handlers), force:true visitor bypass+rate-limit, on_behalf_of_phone DPDP masking, character/merit cert approval gate, is_overdue SLA flag, enquiry backward-transition EC-11.2 guard, receptionist ticket visibility fix, pending-checkout URL renamed. +13 tests. |
| 12 | **Maintenance Admin (vertical)** | ✅ done | 5/5 stories + full ceremony | 2026-05-15 | 2026-05-16 | Adversarial review found 17 bugs — SLA hours corrected (urgent:6h→4h, low:120h→168h), escalation rate-limit+status guard+owner notification, photos_append atomic $size guard (EC-12.3), cost-summary endpoint (MongoDB $sum null-safe), single-record GET /facility/{id}, upcoming schedule endpoint, overdue=true filter, calendar-correct monthly recurrence (not timedelta 30), is_overdue/due_at field renames. +13 tests. |
| 13 | **IT-Tech Admin (vertical)** | ✅ done | 5/5 stories + full ceremony | 2026-05-15 | 2026-05-16 | Adversarial review found 14 bugs — BLOCKER: IT-tech could reset owner password (fixed with target-role guard), BLOCKER: health/system made live Twilio/S3 calls (fixed), admin_reset_password audit log + no plaintext in response, admin_unlock_user clears lockout fields + audit, users_over_80_pct using per-user effective limit, GET /issues/tech uses require_access, branch_code unique DB index, POST /branches endpoint. +5 tests. |
| 14 | **Teacher role (vertical)** | ✅ done | 6/6 stories + full ceremony | 2026-05-15 | 2026-05-16 | Adversarial review found 10 bugs — CRITICAL: bulk results hard-aborted on first bad row (fixed: collect errors per-row, partial success shape), zero audit entries on bulk attendance (fixed: one entry/class), question papers missing schoolId (cross-tenant), /results/{id}/publish endpoint added, HoD scope bypass for cross-class assignments, /staff/me routing order fixed (FastAPI shadow), OWNER_ONLY_FIELDS for teacher class scope in student list. +8 tests. |
| 15 | **Student role (vertical)** | ✅ done | 5/5 stories + full ceremony | 2026-05-15 | 2026-05-16 | Adversarial review found 9 bugs — CRITICAL: SKIP_CONSENT_CHECK startup ValueError guard added, student IDOR on /fees/status/{id} fixed (ownership check), /fees/my summary block added (partial paid_amount counted), guardian annual_income/occupation stripped from student view, teacher class scope enforcement in student list. +3 tests. |
| 16 | **Platform Integration** | ✅ done | 6/6 stories + full ceremony | 2026-05-15 | 2026-05-16 | Adversarial review found 13 bugs — CRITICAL: health/ready never returned 503 on DB failure (fixed), 401 responses now include WWW-Authenticate: Bearer header, sms_logs created_at stored as native datetime (TTL was silently no-op on string), Motor maxPoolSize=50 configured, 4 performance indexes added (ptm_notes, question_papers, lesson_plans, curriculum_progress), 503 DB-down test. +1 test. |
| 17 | **AI Layer Hardening (Agentic Actions)** | 🔧 planning | PRD complete | 2026-06-07 | — | Brownfield initiative: harden EXISTING AI tools so the main chat (`chat.py`/`/api/chat`, not the floating bubble) reliably PERFORMS actions with AI-action↔UI-action data parity (shared service layer + differential state-diff tests), agentic multi-step chaining under plan-then-confirm-once (atomic all-or-nothing + saga fallback), DPDP-compliant for children's data. Owner+Principal are the acceptance gate (Phase 1). No new tools/UI. PRD: `planning-artifacts/prd-ai-layer-hardening.md` (30 FRs, 25 NFRs, 7-job pilot inventory). Readiness check ✅ READY (0 critical). Architecture ✅ complete (`architecture-ai-layer-hardening.md`, 13 ADs incl. shared write-path, plan-then-confirm-once, atomic txn+saga, AD12 real-Mongo test tier; epics sequenced A→B→C→D). Epics & stories ✅ complete (`epics-ai-layer-hardening.md`, **11 epics / 53 stories**, FR1–FR42 mapped; +self-learning Epic G cloned from Odysseus; found 3 pre-existing AI defects → fixed in Epic B). **Shubham review #1 applied (2026-06-07):** dropped Story A.0; added Epics J/K (student/staff + school-internals CRUD) + Story F.10 (two-step destructive confirm + deletion audit); FR37–42 + AD15. **Review gate CLEARED (final feedback in from user + Shubham).** Plan final: 11 epics / 54 stories, FR1–FR43; Phase-1 = Owner+Principal only across the whole school DB; students unchanged. Readiness re-check (run 2, WITH epics) ✅ **GO** — 100% FR1–43 coverage, 0 critical, report `implementation-readiness-report-ai-layer-hardening-2026-06-08.md`. **Cleared to implement Epic A.1 — awaiting user's explicit greenlight to start coding.** |

**Legend:** 📋 next · 🟢 in-progress · ✅ done · 🟦 queued · ⏸️ gated

## Per-Part BMad Cycle (Full Ceremony)

1. **Scope & document** — `bmad-document-project` on the part's surface area → `_bmad-output/parts/<part-slug>/scope.md`
2. **Architecture** — `bmad-create-architecture` if architectural changes are expected → `_bmad-output/parts/<part-slug>/architecture.md`
3. **Stories** — `bmad-create-epics-and-stories` → list of stories targeted at the part
4. **Readiness check** — `bmad-check-implementation-readiness` → gate before coding
5. **Per story** — `bmad-create-story` → `bmad-dev-story` → `bmad-qa-generate-e2e-tests` → `bmad-code-review`
6. **Retro** — `bmad-retrospective` → lessons captured for the next part
7. **Final adversarial pass** — `bmad-review-adversarial-general` on the whole part's diff

## Stale-context discipline

`_bmad-output/project-context.md` is the foundation that every BMad skill loads as persistent fact. **Refresh it before each Part kicks off** via `bmad-generate-project-context` — the codebase moves faster than the document.

## Decisions captured

- **Frontend Foundation is a separate part (#8)** — shared components audited once, not re-touched per vertical.
- **Per-part rigor: full ceremony** — slower but enterprise-grade.
- **Teacher and Student verticals are gated** on Story 7-39 (auth activation) regardless of sweep order.

## Final State (2026-05-16) — Quality Sweep COMPLETE

**Backend tests: 699 passing, 0 skipped.** Commit: `c7630f8`

**Branch isolation: 3 waves complete**
- Wave 1 (Part 4): `tool_functions_v2.py` — 35 callsites
- Wave 2 (Part 11 review): `issues.py` — 34 callsites  
- Wave 3 (Round 2 review): `operations.py` — 19 callsites (expenses/incidents/transport/assets)
- Remaining `scoped_filter` in `operations.py` are intentionally school-wide (leave_requests, announcements, users) with `# branch-scope: intentional` comments

**Platform integrity review results:** Party-mode + adversarial + edge-case + architecture + UX + code quality all applied across 2 rounds. 50+ bugs found and fixed. 40 new tests added.

**AI layer hardening:** LLM temp 0.2/0.7, max_tokens 1200, 4 new tools (timetable, exam analytics, upcoming events, parent message draft), Hindi content filter (16 patterns), it_tech/maintenance scope resolvers.

**Frontend fully wired:** All 6 missing endpoint connections added (class-summary, cost-summary, upcoming schedule, 202 discount-pending, pending-approvals panel, fee/my summary).

## Outstanding cross-cutting risks (track here as discovered)

- ~~Migration 014~~ **RESOLVED in Part 4**
- ~~`db.otps` dead collection~~ **RESOLVED in Part 4** — dropped via migration 018
- ALLOWED_ROLES override may unlock students past their YAML floor — tracked, low risk.
- `_normalize_fee_key` now uses `|` separator — safe. Old `:` separator could cause collision with fee_heads containing colons.
- `export_results` N+1 — **RESOLVED in Round 2 review**
- `issues.py`/`operations.py` branch isolation — **RESOLVED via 3-wave migration**

## Next Steps (Product Backlog)

1. **NEXT: Story 7-39** — Teacher/student login activation (gates all teacher+student features)
2. **6-34** — MongoDB Atlas M10 upgrade (production readiness)
3. **6-35** — Azure OpenAI India region + DPA sign-off (compliance)
4. Deploy → 4 clean pilot weeks → Phase 7 growth features
5. **7-40** WhatsApp/Twilio → **7-42** Token billing → **7-43** Health dashboard → **7-44** School onboarding → **7-45** SaaS multi-tenancy → **7-46** Google Maps transport
