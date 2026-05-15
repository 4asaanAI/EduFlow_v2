# EduFlow Platform Quality Sweep — BMad Method Master Tracker

**Started:** 2026-05-15
**Goal:** Enterprise-grade quality across the entire platform via full BMad ceremony applied part-by-part.
**Method:** For each part — `document-project` → `create-architecture` (if needed) → `create-epics-and-stories` → `check-implementation-readiness` → per-story `CS → DS → QA → CR` → `retrospective` → adversarial review.

## Sequence

User-confirmed order: **3 → 1 → 2 → 4 → 5 → 6 → 7 → 8 → 9 → ...**

| # | Part | Status | Sub-stories | Started | Closed | Notes |
|---|---|---|---|---|---|---|
| 0 | **Hotfixes** | ✅ done | 3 P0 production failures | 2026-05-15 | 2026-05-15 | Closed before Part 5: GET /uploads/serve/{filename} now requires auth and school-scoped lookup; receipt download path is guarded and backend receipt endpoint is covered by regression test; staff leave approval now uses require_owner_or_principal. |
| 0.5 | **Pre-Part-9 Infra** | 🟦 queued | 3 stories | — | — | MongoDB indexes (moved from P16), shared test factories, unauthenticated surface test. Run before Part 9 role verticals. |
| 1 | **Auth + RBAC** | ✅ done | 12/12 original concerns closed + all 16 Part 1.5 findings closed | 2026-05-15 | 2026-05-15 | Part 1 hardening + Part 1.5 fix sweep complete. ~119 of ~130 inline role checks migrated to `Depends(require_role/require_owner/require_owner_or_principal)`; 11 remaining are documented composite/dynamic gates annotated with `# auth:`. Migration 016 idempotent; scope_resolver denies by default; designation fallback removed; cookie phantom evicted; concurrent-refresh test now deterministically races; scoped_query rejects cross-branch attempts. 260 backend tests passing (up from 224 baseline). See `parts/auth-rbac/review-findings-and-fix-plan.md` for the 16 patches A–P. |
| 2 | **AI Layer** | ✅ done | 11 of 11 patches landed (P1–P11) | 2026-05-15 | 2026-05-15 | Audit done (47 raw findings → 11 patches). Wave 1 (P1–P5 Critical) `e8b4a70`. Wave 2 (P6–P11 Important+Polish) `7e82b31`. 311 backend tests passing (was 260 at Part 1 start). P6: registry sub_categories + _is_tool_authorized single gate; P7: announcement moderation in tool (pending_approval for teacher/student audience); P8: content filter on rich_blocks + tool data for students; P9: confirm-token tenant binding (school_id/branch_id), peek raises on Mongo error, $gte TTL, compensating decrement; P10: expires_at required on overrides, stable sort, migration 017; P11: safe_token_count coerce, restricted_exact+9 keys, phone exact-match, random.uniform delay, SSE keepalive comment, zero-width whitespace, _json_candidates rich extraction, numeric param validators. |
| 3 | **Owner role (vertical)** | ✅ done | 12/12 extracted FRs verified + full cross-part review sweep | 2026-05-15 | 2026-05-15 | Part 3 closed. All FRs verified. Full 5-agent party-mode review (Parts 1+2+3) found 29 additional bugs — all fixed across commits 13388ae, 22c467d, e260247. Backend: 387 tests passing (0 skipped). project-context.md fully refreshed (34 patterns). Key residual items deferred to Part 4: exports.py exam enrichment cross-tenant, require_access(role,sub_category) helper, migration 014 not in run_all.py, db.otps drop, branch-scope convention enforcement. |
| 4 | **Multi-tenancy + Data Layer** | ✅ done | 9/9 stories complete, full BMad ceremony | 2026-05-15 | 2026-05-15 | Full ceremony: document-project (10-file docs suite), architecture (4 ADRs), epics+stories (4 epics, 9 stories, 100% FR coverage), readiness check (READY), dev (E1+E2+E3+E4), retro, adversarial review (10 findings, 4 fixed). Commits 332743f→d79f333. 387→420 tests passing (0 skipped). Key wins: require_access() canonical auth helper, 35 AI tool scoped_query migrations, SCHOOL_ID startup guard, audit gate fail-open, migration 014 fix, otps dropped, 10-file docs/ suite generated. |
| 5 | **Notifications + Real-time (SSE)** | ✅ done | 6/6 sprint stories complete + P5.0/P5.4/P5.7 coverage | 2026-05-15 | 2026-05-15 | Canonical notification service with fail-open logging, route + AI notification migration, bounded fan-out, notification pagination meta fix, mark-all-read race boundary, compound index migration 019, chat keepalive data events, service keepalive loop, SSE session normalization, frontend stream_error retry path. Backend 450 tests passing; frontend build passing with existing warnings. |
| 6 | **File Storage + Uploads** | ✅ done | 6/6 sprint stories complete + P6.7/P6.8 coverage | 2026-05-15 | 2026-05-15 | Authenticated and school-scoped file serving, owner/admin-or-self access model, S3 tenant key prefixes, file_uploads schoolId backfill migration 020, role-based upload limits, manual magic-byte MIME validation, orphaned S3 rollback records, chat upload blocklist with ephemeral docs, optional persistence/audit for generated PDFs, scoped paginated list/delete, S3 error logging. Focused Part 6 suite: 32 tests passing. |
| 7 | **Observability + Audit** | ✅ done | 6/6 sprint stories complete + audit helper migration | 2026-05-15 | 2026-05-15 | Canonical fail-open audit helper, zero direct audit inserts outside the helper, branch-scoped/paginated audit reads, audit indexes migration 021, structured logging extras, auth success/failure logs without secrets, consistent error response shapes, slow-query instrumentation, S3/SMS readiness checks, and audit coverage matrix. Focused Part 7 suite: 79 tests passing. |
| 8 | **Frontend Foundation** | ✅ done | 10/10 stories complete | 2026-05-15 | 2026-05-15 | Jest/RTL setup, chat stream manual retry semantics, non-chat SSE reconnect/backoff, ConfirmActionCard double-submit guard, DOMPurify style/class/event stripping, contained tool ErrorBoundary, ToolPage loading/error primitives, singleton 401 refresh redirect, URL `?tool=` routing, semantic tokens, attendance draft TTL purge. Frontend tests: 7 suites / 16 tests passing. Frontend build passing with existing warnings. |
| 9 | **Principal role (vertical)** | 🟦 queued | TBD | — | — | Daily ops, approvals, attendance oversight |
| 10 | **Accountant role (vertical)** | 🟦 queued | TBD | — | — | Fee tracker, discounts, sync, payroll, expenses |
| 11 | **Receptionist role (vertical)** | 🟦 queued | TBD | — | — | Enquiries, admissions, visitors |
| 12 | **Maintenance Admin (vertical)** | 🟦 queued | TBD | — | — | Facility requests, work orders |
| 13 | **IT-Tech Admin (vertical)** | 🟦 queued | TBD | — | — | Tech tickets, system health |
| 14 | **Teacher role (vertical)** | ⏸️ gated | — | — | — | Gated on Story 7-39 (login activation) |
| 15 | **Student role (vertical)** | ⏸️ gated | — | — | — | Gated on Story 7-39 + DPDP parental consent |
| 16 | **Platform Integration** | 🟦 queued | TBD | — | — | Cross-role workflows, NFRs, full E2E, scale tests |

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

## Outstanding cross-cutting risks (track here as discovered)

- ~~Migration 014 (`014_ensure_maintenance_user`) is missing from `run_all.py`~~ **RESOLVED in Part 4** (commit d79f333, story p4-3) — 014 is now in run_all.py and verified by test_migrations.py CI guard.
- ALLOWED_ROLES override may unlock students past their YAML floor — surface during Part 1 (Auth + RBAC).
- Part 3 Owner role hardening follow-up closed on 2026-05-15: owner-exclusive role matrix, NFR2 test-count target, full backend pytest, and frontend build all completed. Remaining warnings are existing dependency/runtime warnings outside the Part 3 owner-role scope.
