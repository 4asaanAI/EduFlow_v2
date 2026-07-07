---
date: '2026-05-12'
project: 'EduFlow Enterprise Upgrade'
assessor: 'BMAD Implementation Readiness Agent'
workflow: 'bmad-check-implementation-readiness'
stepsCompleted:
  - step-01-document-discovery
  - step-02-prd-analysis
  - step-03-epic-coverage-validation
  - step-04-ux-alignment
  - step-05-epic-quality-review
  - step-06-final-assessment
overallStatus: 'NEEDS WORK — Conditionally Ready'
---

# Implementation Readiness Assessment Report

**Date:** 2026-05-12
**Project:** EduFlow Enterprise Upgrade
**Assessor:** BMAD Implementation Readiness Agent (Autonomous Run)
**PRD Version:** Post-validation v2 (edited 2026-05-12, 1,172 lines, 95 FRs)

---

## Step 1: Document Discovery

### Document Inventory

**PRD Documents:**
- `/Users/abhimanyusingh/Desktop/eduflow/_bmad-output/planning-artifacts/prd.md` (whole document, 1,172 lines) — **USED FOR THIS ASSESSMENT**
- `/Users/abhimanyusingh/Desktop/eduflow/_bmad-output/planning-artifacts/prd-validation-report-v2.md` (validation report, round 2) — **USED AS REFERENCE**
- `/Users/abhimanyusingh/Desktop/eduflow/_bmad-output/planning-artifacts/prd-validation-report.md` (validation report, round 1) — reference only, superseded by v2

**Architecture Documents:**
- `/Users/abhimanyusingh/Desktop/eduflow/_bmad-output/planning-artifacts/architecture.md` (whole document, 482 lines) — **USED FOR THIS ASSESSMENT**

**Stories / Epics Documents:**
- `/Users/abhimanyusingh/Desktop/eduflow/_bmad-output/implementation-artifacts/stories.md` (whole document, 690 lines, 28 stories across 5 phases) — **USED FOR THIS ASSESSMENT**

**UX Design Documents:**
- None found — see UX Alignment section for impact assessment

**Project Context:**
- `/Users/abhimanyusingh/Desktop/eduflow/_bmad-output/project-context.md` — **USED AS REFERENCE**

### Duplicate Issues

No duplicate documents (no sharded versions exist alongside whole versions). No conflicts requiring resolution.

### Missing Documents

- UX Design document: Not found. This is a user-facing application with explicit mobile-first requirements — this is a **WARNING** (see Step 4).

---

## Step 2: PRD Analysis

### Functional Requirements Extracted

The PRD contains **95 Functional Requirements** across 22 capability areas (including 1 conditional FR).

| FR# | Summary |
|---|---|
| FR1 | Email + password login |
| FR2 | Role-based data access per RBAC matrix |
| FR3 | Owner can create/edit/deactivate/reassign staff accounts; deactivation invalidates sessions |
| FR4 | API-layer denial of requests outside caller's role |
| FR5 | Cross-role data access blocked at API layer |
| FR6 | Authenticated sessions + concurrent multi-device sessions |
| FR79 | Password reset via verified email link |
| FR7 | Natural language AI query scoped to user's role |
| FR8 | AI-executed data mutations (dispatch table gated on architecture approval) |
| FR9 | Confirm-action step for all AI mutations (plain-language summary) |
| FR10 | Confirm-action cannot be bypassed; tokens single-use, 5-min expiry |
| FR11 | Graceful degradation when Azure OpenAI is unavailable |
| FR12 | AI never reveals cross-role data |
| FR13 | AI always queries live DB — never fabricates data |
| FR86 | AI dispatch audit log (tool, params, user, time) |
| FR87 | Confirmation tokens single-use, 5-min expiry (enforced at API) |
| FR88 | Idempotency tokens on all data-mutating API endpoints |
| FR14 | Principal views real-time staff attendance (biometric SSE; manual fallback if API not available) |
| FR15 | Owner views real-time staff attendance |
| FR16 | System receives processed attendance events from biometric hardware API |
| FR17 | Attendance correction with mandatory reason; original record preserved |
| FR18 | Principal initiates substitution for absent teacher; assigns from available timetable-free staff |
| FR21 | Accountant records fee payment |
| FR22 | System prevents duplicate fee submissions via idempotency key |
| FR23 | Accountant views students with overdue fees, filterable by days |
| FR24 | Accountant logs contact event against student fee record |
| FR25 | Accountant configures discount types |
| FR26 | Accountant applies multiple discounts; system shows full breakdown |
| FR27 | Discount applications recorded with who/when/why |
| FR28 | Fee record correction with mandatory reason and audit trail |
| FR92 | Discount types are reusable; manageable catalogue (create/rename/deactivate) |
| FR93 | Owner views discount impact summary (aggregate revenue, discount, per-type breakdown) |
| FR29 | Owner and Accountant view fee collection summary |
| FR30 | Fee collection summary updates within 30 seconds of a payment |
| FR31 | Principal views per-student fee status (paid/unpaid/overdue) |
| FR32 | Fee status synced from fee software via API; conflict indicator; conflict queue escalation to Owner |
| FR33 | Receptionist logs parent/visitor entry |
| FR34 | Receptionist logs complaint/incident with severity |
| FR35 | Owner views all open complaints, incidents, visitor logs in one view |
| FR36 | Owner/Principal assigns follow-up with due date |
| FR37 | High-severity incidents trigger in-app notifications to Owner and Principal |
| FR38a | Owner/Principal can add follow-up entry to incident/complaint (append-only) |
| FR38b | Incident record displays entries in reverse-chronological order |
| FR39 | Owner/Principal can search/retrieve logs by subject, date, person, status |
| FR40 | Any Admin submits approval request with routing field |
| FR41 | Submitted approvals appear in Owner's dashboard with unread count |
| FR42 | Principal sees and acts on approval requests explicitly routed to them |
| FR43 | Owner (and routed Principal) approves/rejects with mandatory reason |
| FR44 | Submitting Admin notified of approval decision with reason |
| FR45 | All approval workflow actions in audit log |
| FR46 | Transport Head manages vehicle records |
| FR47 | Transport Head manages route zones |
| FR48 | Transport Head assigns students to route zones and vehicles |
| FR49 | Student assigned route zone from configured list; coordinates field nullable (Phase 2) |
| FR50 | Owner and Principal view full transport roster |
| FR51 | IT/Tech Admin logs/updates/closes tech requests |
| FR52 | Maintenance Admin logs/updates/closes facility requests; Owner confirms resolution |
| FR53 | IT/Tech cannot read Maintenance requests and vice versa (namespace isolation) |
| FR54 | Owner and Principal view all issues across both namespaces |
| FR55 | Category selector at intake routes to correct namespace; reassignment before first action |
| FR56 | Receptionist creates announcements targeted by role group |
| FR57 | Each user sees only announcements targeted to their role |
| FR77 | Authorised user can create/view/edit/deactivate student profiles |
| FR78 | Authorised user can create/view/edit/deactivate staff profiles |
| FR80 | In-app notifications with unread count; notification history drawer; tappable to source record |
| FR81 | Persistent navigation accessible from every screen |
| FR82 | List views with >20 records support pagination or infinite scroll + one sort option |
| FR83 | Owner dashboard: mobile-optimised, priority order (high-severity incidents → pending approvals → attendance → fee summary) |
| FR84 | Accountant generates/downloads printable fee receipt |
| FR85 | Owner/Principal export attendance or fee summary as downloadable document |
| FR58 | Owner monitors/triggers database import; schema + referential integrity validation before commit |
| FR59 | Every data-mutating operation records who/when/what changed |
| FR60 | Audit log visibility scoped by role |
| FR61 | DPDP erasure: Owner-authorised hard delete with two-track approach (PII hard delete + record pseudonymization) |
| FR62 | Attendance/academic records cannot be hard deleted under standard operations |
| FR89 | Audit log UI surface for Owner (all), Principal (academic+operational), Admins (own logs only) |
| FR90 | Principal/Owner creates/edits/views/imports timetable; timetable is authoritative for substitution |
| FR91 | Staff submit leave requests; Principal approves/rejects; approved leave reflected in substitution availability |
| FR63 | Any authorised user can upload file attachments to relevant records |
| FR64 | Uploaded files stored in S3-backed storage (survive redeployment) |
| FR65 | Files uploaded before S3 migration remain accessible after migration |
| FR66 | `/api/health/ready` endpoint with granular indicators (DB, AI, biometric API, job scheduler) |
| FR67 | Structured logs shipped to queryable destination in real time |
| FR68 | At least one active alert on error rate spike or critical failure |
| FR69 | Third-party integration unavailability shows "last updated X ago" instead of error |
| FR70 | AI inference spend monitored; alert on threshold breach |
| FR71 | Every data screen shows loading state during fetch |
| FR72 | Every data screen shows empty state with contextual guidance |
| FR73 | Every data screen shows error state with recovery guidance on failure |
| FR74 | All tool panels render correctly in light and dark themes without hardcoded colours |
| FR75 | Owner/Principal views fully functional on iOS Safari and Android Chrome at 375px; 44×44px touch targets; top-75% access |
| FR76 | AI chat input and confirm-action gate visible when mobile keyboard is open |
| FR94 | (Conditional) UDISE+ export dataset — activates only if confirmed by Aman |

**Total FRs:** 95 (including 1 conditional)

---

### Non-Functional Requirements Extracted

**Performance:**
- API response time (standard operations): p95 ≤ 500ms
- Tool panel initial load: ≤ 3s to interactive on simulated 4G (10 Mbps)
- Fee collection summary refresh: ≤ 30s from payment event
- AI chat response first token: ≤ 3s
- File upload confirmation: ≤ 5s for files ≤ 10MB
- Database import: ≤ 2 hours for full school dataset (background operation)

**Security:**
- Passwords hashed with bcrypt; never stored/logged in plaintext
- Access tokens ≤ 1 hour; refresh tokens revocable; deactivation invalidates all sessions
- All traffic over HTTPS/TLS 1.2+; HTTP not served
- Session cookies: `HttpOnly`, `Secure`, `SameSite=Strict`
- Confirmation tokens: 5-minute expiry, single-use, session-bound
- All data encrypted at rest and in transit
- No PII in log fields — log references entity IDs only
- Student PII anonymised before reaching Azure OpenAI
- Biometric raw payload not persisted
- RBAC enforced server-side only
- AI endpoints: max 50,000 tokens/session (provisional)
- Idempotency tokens honoured within 24-hour window
- Dependencies pinned; no unreviewed auto-updates in production
- File access via time-limited authenticated URLs (≤ 1 hour)
- Confirmation token validation unavailability → fail-closed (write operations rejected)
- Log schema validated in CI to reject PII field names

**Reliability:**
- Platform availability: ≥ 99.5% monthly uptime
- Zero data loss on redeployment (S3-backed storage + managed DB)
- Write operation atomicity: complete or fail cleanly — no silent partial writes
- Third-party integration failure must not cause platform downtime (independent degradation)
- Deployments must not interrupt active user sessions
- Background jobs retry with increasing delay; failures logged and alertable
- Database: replica-set topology required to meet 99.5% SLA
- Token store: TTL-capable backend (MongoDB TTL collection or Redis)

**Real-Time Communication (SSE):**
- Keepalive event every 30 seconds on all active SSE channels
- Tab regains visibility → reconnect + fresh state snapshot before resuming event stream
- Multiple tabs for same user: no duplicate event processing (session deduplication)
- Upstream data source unavailable → channel stays open and silent; "last updated X ago"
- SSE routes: HTTP timeout ≥ 300 seconds on hosting platform (CloudFront/ALB configuration required)

**Scalability:**
- Phase 1: ≥ 100 concurrent authenticated users without API degradation
- Phase 1: ≥ 50 concurrent SSE connections per server instance
- Phase 2: `schoolId` field enables schema-per-tenant partitioning without breaking migration
- Per-school API credentials for fee sync and biometric integrations from first implementation
- Existing collections must be backfilled with `schoolId` before authorization matrix tests are valid

**Integration Quality:**
- Biometric API: tolerate up to 4 hours downtime without data loss; events processed in arrival order after recovery
- Fee sync: conflicts surfaced to Accountant within one sync cycle; conflict queue escalation to Owner visibility
- AWS S3: checksum verification on all write operations; failed uploads surface clear error; no partial records
- Azure OpenAI: 30-second response timeout; graceful degradation on timeout
- Email: delivery failures must not cause primary operation to fail; failures logged

**Data Retention:**
- Attendance/academic records: 5-year minimum (CBSE); hard delete prohibited except DPDP erasure
- Fee/financial records: 7-year minimum; correction-with-audit-trail only
- Student PII: duration of enrolment + 5 years; hard delete on DPDP erasure request
- Staff records: employment + 2 years; soft delete under standard operations
- Audit logs (general): 2-year minimum; no hard delete
- AI dispatch audit logs: 2-year minimum; no hard delete

**Browser/Device Support:**
- Mobile (Owner/Principal): iOS Safari latest 2 versions; Android Chrome latest 2 versions; 375px minimum viewport; 44×44px touch targets
- Desktop/Tablet (Admin profiles): Chrome, Firefox, Safari latest 2 versions each; 1024px minimum viewport
- Not supported: Internet Explorer, pre-Chromium Edge

**Accessibility (Minimum):**
- Colour contrast ≥ 4.5:1 for body text in both themes
- Visible focus state: minimum 2px solid outline with ≥ 3:1 contrast ratio against adjacent background
- All form inputs with associated labels (no placeholder-only labelling)
- No information conveyed through colour alone

---

### Additional Requirements & Constraints

**Compliance:**
- DPDP Act 2023 (India): data minimisation, right to erasure (two-track approach), no PII to external APIs without DPA
- CBSE record retention: 5-year minimum for attendance and academic records
- Financial retention: 7-year minimum
- Data residency: AWS Mumbai (ap-south-1); Azure OpenAI India endpoint or Microsoft DPA required pre-go-live
- Azure OpenAI DPA must be signed before EduFlow goes live with any student PII

**Technical Constraints:**
- Brownfield project — existing codebase on AWS Amplify/Elastic Beanstalk
- Scope strictly limited to enterprise quality upgrade (no net-new features except Maintenance Admin profile)
- Solo implementer (Abhimanyu)
- Two external API integrations (biometric hardware, fee software) — MVP or Growth depending on vendor readiness

---

### PRD Completeness Assessment

The PRD is strong. It achieved a 4.5/5 rating in the Round 2 validation. All 10 BMAD sections are complete, 95 FRs are defined with measurable criteria, 9 user journeys cover all Phase 1 roles, DPDP/CBSE conflict is legally resolved with a concrete two-track approach, the dispatch table is formally defined in Appendix A, and all previously-identified validation gaps are closed. The remaining constraints (FR8 architecture gate, FR64/FR65 S3 technology name, UDISE+ conditional) are all documented as known and acceptable.

---

## Step 3: Epic Coverage Validation

The stories document is titled "Implementation Stories" and structured in 5 phases rather than traditional named epics. For the purposes of this assessment, each phase is treated as an epic-equivalent grouping.

### Epic / Phase Overview

| Phase | Name | Stories |
|---|---|---|
| Phase 1 | Foundation & Infrastructure | Stories 1–4 |
| Phase 2 | Core CRUD Completeness | Stories 5–10 |
| Phase 3 | New Capabilities | Stories 11–17 |
| Phase 4 | AI & Safety Hardening | Stories 18–20 |
| Phase 5 | Observability & Quality | Stories 21–28 |

### FR Coverage Matrix

| FR# | PRD Summary | Story Coverage | Status |
|---|---|---|---|
| FR1 | Email + password login | Story 2 (Auth Hardening) | ✓ Covered |
| FR2 | RBAC data access per matrix | Story 21 (auth matrix tests), implied in all stories | ✓ Covered |
| FR3 | Owner creates/edits/deactivates/reassigns staff; deactivation invalidates sessions | Story 2 (session invalidation), Story 6 (staff CRUD) | ✓ Covered |
| FR4 | API-layer denial for wrong role | Story 21 (auth matrix) | ✓ Covered |
| FR5 | Cross-role data blocked at API | Story 21 (auth matrix) | ✓ Covered |
| FR6 | Authenticated sessions + concurrent multi-device | Story 2 (auth hardening) | ✓ Covered |
| FR79 | Password reset via email | **NOT FOUND** in any story | ❌ MISSING |
| FR7 | Natural language AI query scoped to role | Story 18 (AI dispatch), implied in Phase 4 | ✓ Covered |
| FR8 | AI-executed mutations via dispatch table | Story 18 (AI dispatch formal implementation) | ✓ Covered |
| FR9 | Confirm-action step for AI mutations | Story 18 (AI dispatch), Story 22 (AI dispatch tests) | ✓ Covered |
| FR10 | Confirm-action cannot be bypassed; 5-min expiry | Story 18 (AI dispatch), Story 19 (token hardening) | ✓ Covered |
| FR11 | Graceful degradation when AI unavailable | Story 20 (AI graceful degradation) | ✓ Covered |
| FR12 | AI never reveals cross-role data | Story 18 (dispatch), Story 21 (auth matrix) | ✓ Covered |
| FR13 | AI queries live DB — never fabricates | Story 18 (dispatch implementation) | ✓ Covered |
| FR86 | AI dispatch audit log | Story 18 (dispatch implementation) | ✓ Covered |
| FR87 | Confirmation tokens single-use, 5-min expiry at API layer | Story 18, Story 19 | ✓ Covered |
| FR88 | Idempotency tokens on all data-mutating endpoints | Story 19 (fee idempotency + token hardening) | ✓ Covered |
| FR14 | Principal views real-time staff attendance; manual fallback | Story 7 (attendance CRUD + manual entry), Story 28 (SSE) | ✓ Covered |
| FR15 | Owner views real-time staff attendance | Story 28 (SSE real-time) | ✓ Covered |
| FR16 | System receives processed attendance events from biometric API | **NOT EXPLICITLY COVERED** — Story 7 covers correction and manual entry; biometric API integration endpoint is not addressed | ⚠️ PARTIAL |
| FR17 | Attendance correction with mandatory reason; original preserved | Story 7 (attendance correction with audit trail) | ✓ Covered |
| FR18 | Principal initiates substitution workflow | Story 17 (timetable — required for substitution) + Story 18 (AI dispatch: `initiate_substitution`) | ✓ Covered |
| FR21 | Accountant records fee payment | Story 8 (fee CRUD) | ✓ Covered |
| FR22 | Duplicate fee submission prevention (idempotency) | Story 8, Story 19 | ✓ Covered |
| FR23 | Accountant views overdue fee students by filter | Story 8 | ✓ Covered |
| FR24 | Accountant logs contact event against fee record | Story 8 | ✓ Covered |
| FR25 | Accountant configures discount types | Story 9 (discount engine) | ✓ Covered |
| FR26 | Accountant applies multiple discounts with full breakdown | Story 9 | ✓ Covered |
| FR27 | Discount applications logged with who/when/why | Story 9 | ✓ Covered |
| FR28 | Fee record correction with mandatory reason + audit trail | Story 8 | ✓ Covered |
| FR92 | Reusable discount types catalogue | Story 9 | ✓ Covered |
| FR93 | Owner views discount impact summary | Story 9 | ✓ Covered |
| FR29 | Owner + Accountant view fee collection summary | Story 8 | ✓ Covered |
| FR30 | Fee summary updates within 30 seconds of payment | Story 8, Story 28 (SSE) | ✓ Covered |
| FR31 | Principal views per-student fee status | Story 8 | ✓ Covered |
| FR32 | Fee status synced from fee software; conflict surfaced; conflict queue escalation | **NOT COVERED** — no story addresses fee software API integration or sync conflict handling | ❌ MISSING |
| FR33 | Receptionist logs visitor entry | Story 13 (incident, complaint & visitor management) | ✓ Covered |
| FR34 | Receptionist logs complaint/incident with severity | Story 13 | ✓ Covered |
| FR35 | Owner views all open complaints/incidents/visitor logs | Story 13 | ✓ Covered |
| FR36 | Owner/Principal assigns follow-up with due date | Story 13 | ✓ Covered |
| FR37 | High-severity incidents trigger in-app notifications | Story 13, Story 16 (notifications) | ✓ Covered |
| FR38a | Append-only follow-up entries to incident/complaint | Story 13 | ✓ Covered |
| FR38b | Incident displays entries in reverse-chronological order | Story 13 | ✓ Covered |
| FR39 | Owner/Principal search/retrieve logs by subject/date/person/status | Story 13 | ✓ Covered |
| FR40 | Any Admin submits approval request with routing field | Story 10 (operations — leave + approvals) | ✓ Covered |
| FR41 | Submitted approvals in Owner dashboard with unread count | Story 10, Story 16 (notifications) | ✓ Covered |
| FR42 | Principal sees/acts on routed approval requests | Story 10 | ✓ Covered |
| FR43 | Owner/Principal approves/rejects with mandatory reason | Story 10 | ✓ Covered |
| FR44 | Submitting Admin notified of decision | Story 10, Story 16 | ✓ Covered |
| FR45 | All approval workflow actions in audit log | Story 10 | ✓ Covered |
| FR46 | Transport Head manages vehicle records | Story 15 (transport management) | ✓ Covered |
| FR47 | Transport Head manages route zones | Story 15 | ✓ Covered |
| FR48 | Transport Head assigns students to route zones and vehicles | Story 15 | ✓ Covered |
| FR49 | Student assigned route zone from configured list; coordinates nullable | Story 15 | ✓ Covered |
| FR50 | Owner and Principal view full transport roster | Story 15 | ✓ Covered |
| FR51 | IT/Tech Admin logs/updates/closes tech requests | Story 12 (IT/Tech namespace) | ✓ Covered |
| FR52 | Maintenance Admin logs/updates/closes facility requests; Owner confirms resolution | Story 11 (Maintenance Admin profile) | ✓ Covered |
| FR53 | IT/Tech cannot read Maintenance requests and vice versa | Story 11, Story 12 | ✓ Covered |
| FR54 | Owner and Principal view all issues across both namespaces | Story 11, Story 12 | ✓ Covered |
| FR55 | Category selector at intake; reassignment before first action | Story 12 | ✓ Covered |
| FR56 | Receptionist creates role-targeted announcements | Story 14 (announcements) | ✓ Covered |
| FR57 | Users see only announcements targeted to their role | Story 14 | ✓ Covered |
| FR77 | Authorised user creates/views/edits/deactivates student profiles | Story 5 (student CRUD) | ✓ Covered |
| FR78 | Authorised user creates/views/edits/deactivates staff profiles | Story 6 (staff CRUD) | ✓ Covered |
| FR80 | In-app notifications with unread count; drawer; tappable to source | Story 16 (in-app notifications) | ✓ Covered |
| FR81 | Persistent navigation accessible from every screen | **NOT COVERED** — no story addresses navigation/sidebar improvements | ❌ MISSING |
| FR82 | List views with >20 records: pagination/infinite scroll + one sort option | Story 5 (pagination in student list), Story 6 (staff list), Story 8 (fee list), Story 10 (leave list); but no story explicitly ensures ALL list views comply | ⚠️ PARTIAL |
| FR83 | Owner dashboard: mobile-optimised, priority order | Story 27 (mobile responsiveness) | ✓ Covered |
| FR84 | Accountant generates/downloads printable fee receipt | **NOT COVERED** — no story covers fee receipt generation | ❌ MISSING |
| FR85 | Owner/Principal export attendance or fee summary as downloadable document | **NOT COVERED** — no story covers export/download functionality | ❌ MISSING |
| FR58 | Owner monitors/triggers DB import; schema + referential integrity validation | **NOT COVERED** — no story addresses the database import capability | ❌ MISSING |
| FR59 | Every data-mutating operation records who/when/what | Story 5, 6, 7, 8, 9, 10, 11, 12, 13, 15 (included in audit trail ACs) | ✓ Covered |
| FR60 | Audit log scoped by role | Story 5 (DPDP erasure), Story 21 (auth matrix tests) | ✓ Partially Covered |
| FR61 | DPDP erasure: two-track approach (PII hard delete + pseudonymization) | Story 5 (student profile CRUD includes /erase endpoint) | ✓ Covered |
| FR62 | Attendance/academic records cannot be hard deleted | Story 7 (hard delete returns 405) | ✓ Covered |
| FR89 | Audit log UI surface for all scoped roles | **NOT COVERED** — no story creates the audit log UI surface | ❌ MISSING |
| FR90 | Principal/Owner creates/edits/views/imports timetable | Story 17 (timetable management) | ✓ Covered |
| FR91 | Staff submit leave requests; Principal approves/rejects; reflected in substitution | Story 10 (leave requests) | ✓ Covered |
| FR63 | Any authorised user uploads file attachments to records | Story 1 (S3 migration covers upload capability) | ✓ Covered |
| FR64 | Files in S3-backed storage; survive redeployment | Story 1 | ✓ Covered |
| FR65 | Pre-migration files remain accessible after migration | Story 1 | ✓ Covered |
| FR66 | `/api/health/ready` with granular indicators | Story 4 (health endpoint + logging) | ✓ Covered |
| FR67 | Structured logs shipped to queryable destination | Story 4 | ✓ Covered |
| FR68 | At least one active alert on error rate spike | Story 4 | ✓ Covered |
| FR69 | Third-party integration unavailability shows "last updated X ago" | Story 20 (AI graceful degradation) | ✓ Covered |
| FR70 | AI inference spend monitored; alert on threshold | Story 4 | ✓ Covered |
| FR71 | Every data screen shows loading state | Story 25 (UX states) | ✓ Covered |
| FR72 | Every data screen shows empty state with guidance | Story 25 | ✓ Covered |
| FR73 | Every data screen shows error state with recovery | Story 25 | ✓ Covered |
| FR74 | All tool panels render correctly in light and dark themes | Story 26 (theme coherence) | ✓ Covered |
| FR75 | Owner/Principal views functional on mobile; 375px; 44×44px; top-75% | Story 27 (mobile responsiveness) | ✓ Covered |
| FR76 | AI chat input and confirm-action visible when keyboard open | Story 27 | ✓ Covered |
| FR94 | (Conditional) UDISE+ export | Not in stories — acceptable, conditional FR only activates on client confirmation | ✓ Acceptable Gap |

### Missing FR Coverage Summary

| FR# | Missing Requirement | Impact |
|---|---|---|
| FR79 | Password reset via verified email link | Medium — required for basic account recovery |
| FR32 | Fee software API integration + sync conflict handling + conflict queue escalation | High — Accountant journey depends on this; also an integration quality NFR |
| FR81 | Persistent navigation surface accessible from every screen | Medium — UX requirement; existing implementation may satisfy but no story verifies |
| FR82 | ALL list views comply with pagination + sort (not just the ones explicitly mentioned) | Low — partially covered; gap is ensuring completeness across all list views |
| FR84 | Accountant generates and downloads printable fee receipt | High — directly in accountant's primary workflow |
| FR85 | Owner/Principal export attendance or fee summary as downloadable document | Medium — named in MVP must-have capabilities |
| FR58 | Owner monitors/triggers database import with validation | High — database import is a go-live prerequisite; full school database loaded from day one |
| FR89 | Audit log UI surface for scoped roles | Medium — compliance and trust requirement; FR60 covers scoping policy but no story builds the UI |

### Coverage Statistics

- **Total PRD FRs (excluding conditional FR94):** 94
- **FRs fully covered in stories:** 80
- **FRs partially covered:** 2 (FR16, FR82)
- **FRs not covered:** 8 (FR79, FR32, FR81, FR84, FR85, FR58, FR89 — FR82 borderline)
- **Coverage percentage:** ~85.1% (80/94)

---

## Step 4: UX Alignment Assessment

### UX Document Status

**NOT FOUND.** No UX design documents exist in the planning artifacts directory. Checked patterns:
- `*ux*.md` — no matches
- `*design*.md` — no matches
- `*wireframe*.md` — no matches
- `*mockup*.md` — no matches

### UX Implied by PRD?

Yes — strongly implied and explicitly required:

1. The PRD contains detailed mobile-first requirements (FR75, FR76, FR83) specifying exact viewport sizes (375px), touch targets (44×44px), and viewport coverage thresholds (top 75%)
2. The PRD specifies a chat-first interface as the core product differentiator
3. The PRD specifies consistent UX states (loading/empty/error) across every data screen (FR71, FR72, FR73)
4. The PRD specifies theme coherence in dark and dark modes (FR74)
5. The PRD specifies a notification history drawer, confirm-action card layout, and Owner dashboard mobile priority order (FR80, FR83)
6. Multiple user journeys describe specific UI interactions (thread view, status badges, assignment info, severity flagging on dashboards)

### Alignment Issues

Since no UX document exists, a formal UX ↔ PRD alignment check cannot be performed. However, the following UX concerns arise from the stories:

1. **No wireframes or mockups exist** for the 5 new tool panels being built: `MaintenanceTools.js`, IT/Tech panel (currently unnamed), transport management panel, incident/complaint thread view, announcement creation. Developers will be implementing UI without design references.

2. **Mobile-first gaps in implementation guidance**: While Story 27 specifies mobile acceptance criteria, there are no design references for how Owner and Principal views should be restructured for 375px viewports. The existing codebase uses a 120px fixed sidebar — it is unclear whether this is mobile-responsive or requires redesign.

3. **Confirm-action card UX** (`ConfirmActionCard.js` exists in the codebase): There is no design specification for how this card should render within the mobile keyboard-open state (FR76). Story 27 specifies the acceptance criterion but provides no design guidance.

4. **Notification drawer UX**: FR80 specifies a notification history drawer with reverse-chronological order, tappable items, and unread count. Story 16 specifies the API but no design guidance for the drawer component.

5. **Owner dashboard mobile priority layout (FR83)**: The explicit priority order (high-severity incidents → pending approvals → attendance → fee summary) requires a specific UI design. No design reference exists.

### Warnings

**WARNING — UX DOCUMENTATION GAP (HIGH PRIORITY):**
This is a user-facing application with complex mobile requirements, multiple new UI surfaces, and a chat-first paradigm. The absence of UX documentation means:

- Developers will make UI design decisions autonomously — inconsistency is likely across 5+ new tool panels
- Mobile-first requirements (FR75, FR76, FR83) are acceptance criteria without design references — implementation risk is high
- The notification drawer, confirm-action gate, and Owner dashboard priority layout require explicit design decisions before implementation

**RECOMMENDATION:** Before implementation begins on Phase 3 (New Capabilities) and Phase 5 Story 27 (Mobile Responsiveness), create at minimum:
- Low-fidelity wireframes for the 5 new tool panels
- Mobile layout wireframe for Owner and Principal priority views
- Notification drawer component design
- Confirm-action card mobile layout

---

## Step 5: Epic Quality Review

### Epic Structure Validation

The stories document uses a phase-based structure rather than user-value epics. Each phase is assessed as follows:

---

#### Phase 1 — Foundation & Infrastructure (Stories 1–4)

**User Value Assessment:** BORDERLINE — Phase 1 is an infrastructure phase (S3 migration, auth hardening, schoolId backfill, health endpoint). These deliver operational reliability and security, not direct user-visible features. However, they are correctly identified as preconditions and explicitly gated as critical go-live requirements. This is acceptable for a brownfield quality upgrade where the scope is explicitly "hardening" and these are preconditions for everything else.

**Independence:** ✓ Phase 1 stories can be executed independently. Story 1 (S3) and Story 2 (Auth) are independent of each other. Story 3 (schoolId) depends on the existing DB schema, not Phase 1 stories. Story 4 (health/logging) is independent.

**Greenfield/Brownfield check:** Correctly brownfield — existing entry point, existing infrastructure, no initial project setup story needed.

**Story Quality Issues — Phase 1:**

**Story 2 (Auth Hardening):** A dependency on frontend handling (access token in React state, not localStorage) is noted but the stories document does not explicitly call out that this is a **breaking change** for existing logged-in users who have tokens in localStorage. No migration strategy for existing `eduflow_token` localStorage entries is specified. This is a UX regression risk on deployment.

**Story 3 (schoolId backfill):** Correctly scoped as a migration + forward-compatibility measure. Minor: the story does not mention updating `scope_resolver.py` to validate `schoolId` presence in queries, which is needed for the authorization matrix tests to be meaningful.

**Story 4 (Health/Logging):** The `biometric API reachability` check in FR66 is listed in the acceptance criteria, but no biometric API integration story exists in Phase 1. The health endpoint must check a service that isn't implemented yet. The AC should be conditional on biometric integration being available — this is not specified.

---

#### Phase 2 — Core CRUD Completeness (Stories 5–10)

**User Value Assessment:** ✓ GOOD — Each story delivers direct user-visible functionality (student records, staff records, attendance, fee management, discounts, leave/approvals). Users cannot use the platform without these.

**Independence:** ✓ Phases are correctly sequenced. Story 5 (student) and Story 6 (staff) are independent. Story 7 (attendance) depends on Story 6 (staff must exist), which is correctly noted in the dependency map. Story 8 (fee) depends on Story 5 (student) — correctly noted. Story 9 (discount) depends on Story 8 — correctly noted. Story 10 (leave/approvals) depends on Story 6 (staff) — correctly noted.

**Story Quality Issues — Phase 2:**

**Story 8 (Fee Management):** This story is rated "Large" effort and covers: fee payment recording, idempotency, overdue lists, contact logging, correction with audit trail, collection summary, SSE update, principal fee view, AND fee software API sync (FR32). However, FR32 (fee software sync + conflict handling) is **not included in Story 8's acceptance criteria**. It appears in the FR list in the PRD but is entirely absent from Story 8. This is the same gap identified in Step 3 — FR32 is uncovered.

**Story 9 (Discount Engine):** The story correctly mirrors the PRD's domain requirements. However, the AC for discount impact summary (`GET /api/fees/discount-summary`) does not specify whether this is a live query or cached — given it aggregates across all enrolled students, this could be a performance concern at scale. Minor gap.

**Story 10 (Leave Requests + Approvals):** The story combines leave requests AND the general approvals workflow into one story. Given the effort is rated "Medium," this may be undersized — the approvals workflow alone includes routing logic, unread-count badges, notification delivery, mandatory reason fields, and audit trail. The dependency note "(Story 16 — notifications — must be implemented or stubbed)" is appropriate but means this story cannot be fully acceptance-tested until Story 16 is delivered.

---

#### Phase 3 — New Capabilities (Stories 11–17)

**User Value Assessment:** ✓ GOOD — Phase 3 delivers entirely new user-visible capabilities: Maintenance Admin profile, IT/Tech namespace, incident management, announcements, transport management, notifications, and timetable.

**Independence:** ✓ Stories 11, 12, 13, 14, 15, 17 are largely independent. Story 16 (notifications) is a dependency for Stories 10, 11, and 13 but Story 16 is placed in Phase 3 alongside them. The dependency map notes this cross-dependency, and the stories allow stubbing.

**Story Quality Issues — Phase 3:**

**Story 11 (Maintenance Admin Profile):** This is a new profile build — full role, data model, tool panel, RBAC enforcement, and tests. The story correctly covers all these dimensions. The acceptance criteria include `MaintenanceTools.js` frontend panel with loading/empty/error states. However, there are no design specifications (see UX gap in Step 4). The story is complete but may produce inconsistent UI without design guidance.

**Story 12 (IT/Tech Admin — Issue Tracker):** The story correctly focuses on namespace isolation. However, the AC for reassignment ("reassignment allowed before first action") does not specify what "first action" means programmatically — is it the first status update, the first note, or the first assignment? This AC is ambiguous and could lead to inconsistent implementation.

**Story 13 (Incident, Complaint & Visitor Management):** The story is comprehensive. One concern: FR32's conflict queue surfacing for Owner is not mentioned here or elsewhere. Also, the AI `query_incidents` dispatch (Q4 in Appendix A) is a read-only tool — the story's full-text search requirement for "description and involved_parties" implies a MongoDB text index is needed. This should be explicitly noted in technical guidance or this story's technical notes.

**Story 14 (Announcements):** Correctly scoped as a small story. The dependency on Story 16 (notifications) is noted. One minor gap: the story does not mention that announcements should also appear in the Owner/Principal dashboard view alongside incidents and approvals — FR35 and FR83 imply owners should see new announcements.

**Story 16 (In-App Notifications):** The story includes all trigger conditions correctly. The AC for "Unread count via `GET /api/notifications/unread-count` — called on mount and after each SSE event" introduces a polling concern: if this is called after every SSE event, it could generate significant load. The architecture does not specify a caching strategy for the unread count — minor gap.

**Story 17 (Timetable Management):** The story is well-structured. One gap: the bulk import endpoint (`PUT /api/academics/timetable/import`) accepts a payload and validates referential integrity. The story does not specify what happens to existing timetable entries on bulk import — is it a replace or an append? This ambiguity could lead to data duplication if the import is run twice.

---

#### Phase 4 — AI & Safety Hardening (Stories 18–20)

**User Value Assessment:** ✓ ACCEPTABLE for safety and reliability concerns — these stories enforce correctness and safety rather than adding features. They are correctly deferred to after CRUD is solid.

**Independence:** Story 18 depends on Story 17 (timetable — substitution tool) and all Phase 2 CRUD stories (the dispatch table tools operate on those entities). Story 19 extends Story 18. Story 20 extends Story 4. These dependencies are correctly noted.

**Story Quality Issues — Phase 4:**

**Story 18 (AI Dispatch Table):** This is the most complex story in the entire backlog. The AC correctly covers all 9 write dispatches, confirm-action enforcement, token storage, cross-session validation, and the AI dispatch audit log. One concern: the story does not specify how `tool_functions.py` and `tool_functions_v2.py` (the "tool v1 + v2 split" gap noted in the architecture document) is handled. If both registries exist, which one is authoritative for Phase 4 dispatches? The architecture document identifies this as a known maintenance overhead gap but it is not resolved by any story.

**Story 19 (Fee Idempotency + Confirmation Token Hardening):** The story correctly extends Story 8's idempotency and Story 18's confirmation tokens. One concern: the AC states "replaying a `POST /api/chat/confirm` with an already-used token returns the original result, not a 400 error." This is a reasonable UX approach for network retries, but it conflicts with the NFR "Confirmation tokens: single-use; once consumed or expired, replaying the token must not trigger any data change." The NFR says 400 on replay; this story says return original result. This is a **direct contradiction** between a story AC and the PRD NFR. The implementation team will need to resolve which behavior is correct — the PRD's NFR is the authority, so this story AC should be updated.

**Story 20 (AI Graceful Degradation):** Well-scoped. All ACs are testable and align with the PRD's FR11 and FR69.

---

#### Phase 5 — Observability & Quality (Stories 21–28)

**User Value Assessment:** ✓ MIXED — Stories 21–24 are test stories (team value, not user value). Stories 25–28 deliver user-visible quality improvements (UX states, theme, mobile, SSE). This is acceptable — test coverage is a go-live gate and cannot be deferred.

**Independence:** Stories 21–24 can run in parallel with Phase 4. Stories 25–26 can run in parallel with Phase 3 for existing tool panels. Story 27 (mobile) depends on the Owner dashboard (Story 16 for notifications, Story 13 for incidents) being in place to test the priority layout. Story 28 (SSE) depends on Story 4 (health endpoint).

**Story Quality Issues — Phase 5:**

**Story 21 (Authorization Matrix Tests):** The matrix covers Owner, Principal, Accountant, Receptionist, Transport Head, IT/Tech Admin, Maintenance Admin, Staff, Student. This is comprehensive. One minor gap: the story specifies `mongomock` or `motor-mock` but the architecture document mentions the existing project uses Motor 3.3.1 with `httpx.AsyncClient` — the testing stack choice should be confirmed against what is already in use (the project-context.md states Motor mock is not used today, and tests should not run against live MongoDB).

**Story 22 (AI Tool Dispatch Tests):** Well-structured. All 9 write dispatches are covered. The LLM is correctly mocked.

**Story 23 (Core Route Tests):** The story covers auth, attendance, fee, student CRUD, and staff CRUD. It does not include routes for the new capabilities in Phase 3 (incidents, announcements, transport, issues). These routes will have no test coverage unless a Phase 3 test story is added or this story is expanded. Given that Story 21 covers the authorization matrix for all roles, the gap is specifically happy-path functional tests for Phase 3 routes.

**Story 24 (Scope Resolver Unit Tests):** Well-structured and appropriately small. Correctly covers deny-by-default behaviour.

**Story 25 (UX States):** The story covers all existing and new tool panels. The AC "No hardcoded loading text — empty and error states use language appropriate to the context" is good but not easily testable in an automated way. Manual review will be required.

**Story 26 (Theme Coherence):** The grep-based AC is a pragmatic automated check. The story is appropriately scoped.

**Story 27 (Mobile Responsiveness):** Critical go-live gate. The ACs are specific and testable. One concern: the story requires testing on actual iOS Safari and Android Chrome — not simulators or emulators. This requires physical device access. This is not mentioned as a constraint or prerequisite. For a solo implementer, this is a realistic risk.

**Story 28 (SSE Real-Time):** The story correctly covers keepalive, reconnect, session deduplication, upstream unavailability, and timeout configuration. The CloudFront/ALB timeout configuration is specifically called out as needing verification — this is the right approach. One gap: Story 28 does not specify how session deduplication is implemented (what constitutes a `session_id` — is it a per-tab UUID, a cookie, or something else?). The architecture document mentions `session_id` in the context of confirmation tokens but not SSE deduplication.

---

### Best Practices Compliance Checklist — Summary

| Criterion | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 |
|---|---|---|---|---|---|
| Delivers user value | ⚠️ Infra | ✓ | ✓ | ⚠️ Safety | ✓ Mixed |
| Epic can function independently | ✓ | ✓ | ✓ | ✓ | ✓ |
| Stories appropriately sized | ✓ | ⚠️ Story 10 may be undersized | ✓ | ✓ | ✓ |
| No forward dependencies | ✓ | ✓ | ✓ | ✓ | ✓ |
| Database tables created when needed | ✓ | ✓ | ✓ | ✓ | N/A |
| Clear acceptance criteria | ✓ | ⚠️ Story 8 missing FR32 | ⚠️ Story 12 ambiguous reassignment AC | ⚠️ Story 19 contradicts NFR | ✓ |
| Traceability to FRs maintained | ✓ | ⚠️ FR32, FR84, FR85, FR58, FR89 uncovered | ✓ | ✓ | ✓ |

### Quality Assessment by Severity

**Critical Violations:**

1. **Story 19 vs. PRD NFR contradiction on confirmation token replay behavior.** Story 19 AC states replay of a used confirmation token should return the original result (HTTP 200). The PRD NFR Security section states "replaying an expired or already-used token must not trigger any data change" — which does not specify the HTTP status but clearly does not intend a success response. The PRD's FR10 states "replaying an expired or already-used token must not execute any data change." Resolution: define clearly whether replay returns 400 (fail-closed) or the original result (retry-safe). Given the PRD explicitly calls this out as a safety architecture requirement, fail-closed (400 or 409) is the correct interpretation.

**Major Issues:**

2. **FR32 not covered in any story** — fee software API integration and sync conflict handling is a named integration requirement in the PRD, a named integration quality NFR, and a key part of the Accountant journey. Its absence from the story backlog is a significant gap.

3. **FR84 (fee receipt) and FR85 (export attendance/fee summary) not covered in any story** — both are explicitly listed in MVP must-have capabilities and have dedicated FR numbers. No story exists for either. Story 23 mentions `routes/exports.py` exists in the codebase, but no story delivers the user-visible feature.

4. **FR58 (database import capability) not covered** — the initial database import is explicitly called a go-live prerequisite in the PRD ("Full school database loaded from day one"). No story addresses the import trigger UI, schema validation surface, or referential integrity checks.

5. **FR89 (audit log UI) not covered** — while audit log scoping policy is covered by FR60 and tested by Story 21, there is no story building the actual UI surface through which Owner, Principal, and Admins access their permitted audit log entries.

6. **FR79 (password reset) not covered** — a basic account recovery feature required for go-live; the IT/Tech Admin story (Story 9 in Journey 9) specifically references FR79 as being triggered in the journey narrative, but no implementation story exists.

7. **Tool v1 + v2 registry split not resolved** — the architecture document flags `tool_functions.py` and `tool_functions_v2.py` as a known maintenance overhead gap. No story consolidates them. Story 18 adds new dispatches to `tool_functions_v2.py` but the split persists.

**Minor Concerns:**

8. **Story 2 auth hardening: no migration strategy for existing localStorage tokens** — risk of UX regression on deployment.

9. **Story 10 may be undersized** — combining leave requests + full approvals workflow into one "Medium" effort story is aggressive.

10. **Story 12: "first action" in reassignment AC is ambiguous** — needs clarification before implementation.

11. **Story 13: MongoDB text index requirement for full-text search** is not mentioned in technical notes.

12. **Story 14: announcements visibility in Owner/Principal dashboard** not explicitly addressed.

13. **Story 17: bulk timetable import replace vs. append behavior** is unspecified.

14. **Story 23: Phase 3 routes have no functional test coverage** — only authorization is tested, not happy-path functionality.

15. **Story 27: physical device requirement** for mobile testing is not called out as a constraint.

16. **Story 28: SSE session deduplication mechanism** (`session_id` format) is not specified.

17. **Story 4: health endpoint biometric check** is specified but biometric integration is not implemented in any story.

---

## Step 6: Final Assessment

### Summary of Findings by Category

| Category | Status | Key Issues |
|---|---|---|
| PRD Quality | ✓ PASS (4.5/5) | Strong, externally validated — no major issues |
| Architecture Alignment | ✓ PASS | Architecture is consistent with PRD; all technology choices documented |
| FR Coverage in Stories | ⚠️ NEEDS WORK | 8 FRs uncovered (FR79, FR32, FR81, FR84, FR85, FR58, FR89); 2 partially covered |
| UX Documentation | ❌ GAP | No UX documentation for a user-facing application with complex mobile requirements |
| Story Quality | ⚠️ NEEDS WORK | 1 critical contradiction (Story 19 vs. NFR); 6 major missing stories; 9 minor issues |
| Dependency Map | ✓ PASS | Dependencies correctly identified and sequenced |
| Go-Live Checklist | ⚠️ INCOMPLETE | 5 of the 9 named go-live gates are correctly covered; FR32, FR58, FR84, FR89 are missing from go-live gate list |

---

### Overall Readiness Status

**NEEDS WORK — Conditionally Ready**

The EduFlow Enterprise Upgrade planning artifacts are strong in quality and structure. The PRD is at production-grade quality. The architecture is well-documented and consistent with the PRD. The story set covers approximately 85% of functional requirements with high-quality acceptance criteria. However, the implementation is not ready to begin without resolving the issues below.

---

### Critical Issues Requiring Immediate Action

**1. Story 19 contradicts PRD NFR on confirmation token replay (Critical)**
- Story 19 AC says replay of used token → return original result (HTTP 200)
- PRD NFR Security + FR10 say used/expired token must not execute any data change
- Resolution required: align Story 19 to PRD. Correct behavior is fail-closed (400/409 on replay). Network retry safety for fee operations should be handled through the general idempotency mechanism (FR88/Story 19's idempotency token ACs), not by making confirmation tokens replayable.

**2. FR32 (Fee Software API Integration) has no story (Major)**
- The fee software API sync, conflict detection, conflict queue, and Owner escalation are named in MVP scope and the Accountant journey narrative depends on them
- Create a new story: "Fee Software API Integration — Sync + Conflict Handling" covering: scheduled sync endpoint, conflict detection and surfacing to Accountant, conflict resolution logging, conflict queue escalation to Owner if unresolved for >1 sync cycle
- Estimate: Medium-Large effort. Vendor API availability is a risk — the story should include a fallback mode (manual fee status entry by Accountant) if the vendor API is not ready

**3. FR58 (Database Import) has no story (Major)**
- "Full school database loaded from day one" is a go-live prerequisite stated in the PRD Executive Summary, Success Criteria, and Phase 1 must-have capabilities
- Create a new story: "School Database Import — Owner Trigger + Validation UI" covering: import trigger for Owner, schema validation, referential integrity checks (student → class, staff → role, fee record → fee head), surface of invalid records before commit, import progress indicator
- This story should be inserted in Phase 1 (it is a foundation prerequisite) or at the start of Phase 2

**4. FR84 (Fee Receipt) + FR85 (Export) have no stories (Major)**
- Both are named in MVP must-have capabilities
- Create new story: "Exports and Printables — Fee Receipt, Attendance Summary, Fee Collection Summary" covering: fee receipt PDF generation for Accountant; downloadable attendance summary for Owner/Principal; downloadable fee collection summary. The `routes/exports.py` route already exists — these are UI and export-generation completions

**5. FR89 (Audit Log UI) has no story (Major)**
- FR89 specifies a dedicated UI surface for audit log access, with role-scoped views
- Create new story: "Audit Log UI — Scoped View for Owner, Principal, and Admins" covering: UI surface, search and filter capabilities, role-scoped data visibility enforcement (testing tie-in with Story 21)

**6. FR79 (Password Reset) has no story (Medium)**
- Password reset is referenced in the IT/Tech Admin journey and is a basic account management feature
- Create new story: "Password Reset via Email Link" — small effort; add to Phase 1 (it is an auth foundation capability alongside Story 2)

---

### Recommended Next Steps

1. **Resolve Story 19 contradiction** — update the confirmation token replay AC to align with PRD NFR. Decision: fail-closed (400/409 on replay) is the correct interpretation. No code change needed yet; update the story before implementation begins.

2. **Create 5 missing stories** — FR32 (fee sync), FR58 (DB import), FR84+FR85 (exports/receipts), FR89 (audit log UI), FR79 (password reset). These 5 stories should be sized, prioritised, and added to the backlog before Phase 2 implementation begins. Recommended placement:
   - FR79 (password reset) → Phase 1, Story 2.5 (after auth hardening)
   - FR58 (DB import) → Phase 1 or Phase 2 start
   - FR32 (fee sync) → Phase 2 (after Story 8 fee CRUD, as Story 8.5 or Story 10.5)
   - FR84+FR85 (exports/receipts) → Phase 3 (alongside new capabilities)
   - FR89 (audit log UI) → Phase 3 or Phase 5

3. **Create minimum viable UX documentation before Phase 3 begins** — at minimum: low-fidelity wireframes for 5 new tool panels (Maintenance, IT/Tech, incident thread view, announcements, transport), mobile layout wireframe for Owner/Principal priority views, notification drawer design, confirm-action card mobile layout. Without this, Phase 3 implementation will produce inconsistent UI.

4. **Clarify Story 12 "first action" ambiguity** — define programmatically what constitutes the first action on an issue before namespace reassignment is no longer permitted.

5. **Specify Story 17 bulk import behavior** — replace vs. append. Add an AC: "Bulk import replaces all existing timetable entries for the affected class/day combination — duplicate period entries are rejected with a validation error before any data is committed."

6. **Address Story 28 SSE session deduplication implementation** — specify what `session_id` is (recommend: browser tab UUID generated at page load, sent as SSE query parameter, stored in tab sessionStorage).

7. **Add Story 3 scope: update `scope_resolver.py` to validate `schoolId` presence** — add AC to Story 3 or Story 21.

8. **Address Story 2 auth migration risk** — add AC: "Users with existing `eduflow_token` in localStorage are gracefully migrated on first load — existing session is cleared and the user is prompted to log in again with a clear message."

9. **Add Story 4 health check conditional for biometric API** — update AC: "Biometric API reachability check is included only if `BIOMETRIC_API_URL` env var is set; if not set, the indicator is absent from the health response (not shown as error)."

10. **Revise the go-live checklist** to add: Story for DB import (FR58) as a hard gate; Story for fee receipt (FR84) and export (FR85); Story 16 (notifications) as a hard gate since it is a dependency for Stories 10, 11, and 13.

---

### Issues Count Summary

| Severity | Count | Action |
|---|---|---|
| Critical (story contradiction) | 1 | Must fix before implementation of Story 19 |
| Major (missing stories for named MVP FRs) | 5 gaps → 5 new stories needed | Must create before Phase 2 begins |
| Major (tool registry split unresolved) | 1 | Address in Story 18 scope |
| Minor (story AC ambiguities and gaps) | 9 | Resolve during story refinement |
| Warning (UX documentation gap) | 1 | Address before Phase 3 implementation |

**Total issues identified:** 17 across 6 categories.

---

### Final Note

This assessment identified 17 issues across 6 categories. The foundation is solid — a PRD scoring 4.5/5 with 95 well-defined functional requirements, a comprehensive architecture document, and 28 well-structured stories covering 85% of requirements is genuinely strong work. The gaps are specific and actionable, not symptomatic of unclear product thinking.

The 5 missing stories represent known MVP scope that was defined in the PRD but not yet translated into stories. Creating those stories is the primary prerequisite for implementation to begin safely. The Story 19 contradiction is the only issue that could cause a real-world safety regression — it must be resolved before Phase 4 implementation begins.

Once the missing stories are created and the Story 19 contradiction is resolved, this project is ready for implementation to begin on Phase 1.

---

*Report generated by BMAD Implementation Readiness Agent (Autonomous Run)*
*Date: 2026-05-12*
*Input documents: prd.md (v2), architecture.md, stories.md, prd-validation-report-v2.md, project-context.md*
