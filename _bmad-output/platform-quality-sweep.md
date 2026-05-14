# EduFlow Platform Quality Sweep — BMad Method Master Tracker

**Started:** 2026-05-15
**Goal:** Enterprise-grade quality across the entire platform via full BMad ceremony applied part-by-part.
**Method:** For each part — `document-project` → `create-architecture` (if needed) → `create-epics-and-stories` → `check-implementation-readiness` → per-story `CS → DS → QA → CR` → `retrospective` → adversarial review.

## Sequence

User-confirmed order: **3 → 1 → 2 → 4 → 5 → 6 → 7 → 8 → 9 → ...**

| # | Part | Status | Sub-stories | Started | Closed | Notes |
|---|---|---|---|---|---|---|
| 1 | **Auth + RBAC** | 🟡 partial — review revealed gaps | 11/12 concerns closed; concern #1 (helper adoption) at 3% (4/130 routes) | 2026-05-15 | — | Hardening landed (migration 016, scope_resolver fallback removed, scoped_query, 48 scope tests, JWT/cookie hardening) BUT 3 parallel reviewers (adversarial-general, edge-case-hunter, party-mode) found 16 new issues. See `parts/auth-rbac/review-findings-and-fix-plan.md` for the full triage and ordered fix plan. **Do NOT start Part 2 until Part 1.5 closes these.** |
| 2 | **AI Layer** | ⏸️ blocked by Part 1.5 | TBD | — | — | Tool dispatch, confirm tokens, idempotency, rate limiter, content filter, audit, prompts |
| 3 | **Owner role (vertical)** | 🟦 queued | TBD | — | — | School Pulse, financial reports, fee collection, broadcaster — full stack |
| 4 | **Multi-tenancy + Data Layer** | 🟦 queued | TBD | — | — | schoolId propagation, scoped queries, migration hygiene, index/TTL audit |
| 5 | **Notifications + Real-time (SSE)** | 🟦 queued | TBD | — | — | in-app notifications, SSE keepalive, backpressure |
| 6 | **File Storage + Uploads** | 🟦 queued | TBD | — | — | S3 presigning, chat-file flow |
| 7 | **Observability + Audit** | 🟦 queued | TBD | — | — | Structured logs, audit_logs, health endpoints |
| 8 | **Frontend Foundation** | 🟦 queued | TBD | — | — | ChatInterface, ConfirmActionCard, ToolPage primitives, theme system |
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

- Migration 014 (`014_ensure_maintenance_user`) is missing from `run_all.py` — pre-existing, surface during Part 4 (Multi-tenancy + Data Layer).
- ALLOWED_ROLES override may unlock students past their YAML floor — surface during Part 1 (Auth + RBAC).
