# EduFlow — Architecture & Product Dossier
### Source document for pitch-deck generation (SISFS / incubator submission)

**Prepared:** 2026-07-01
**Product owner:** Layaa AI (Abhimanyu, Shubham)
**Purpose of this document:** This is a factual, repo-derived dossier of EduFlow — the product, its architecture, its differentiation, and its business plan-to-date. It is meant to be handed to another AI session (or a human) as **source material** to draft a pitch deck for incubator submission (India's Startup India Seed Fund Scheme — SISFS — portal). Every claim below is sourced from the live codebase and its planning artifacts, not invented. Sections marked **[UNVALIDATED]** are founder planning anchors, not audited numbers — flag them as such in any deck and do not present them as proven traction.

---

## 1. One-line pitch

**EduFlow is a chat-first, multi-role school management SaaS that replaces the paper diary and WhatsApp chaos of Indian schools with a single AI assistant that doesn't just answer questions — it executes school operations (attendance, fees, approvals) through natural language, gated by a deterministic confirmation step.**

---

## 2. The problem

Indian school administration (attendance, fees, staff leave, parent communication, incident logs) today runs on a fragmented stack of paper registers, WhatsApp groups, and Excel sheets. Existing school-management software (Teachmint, MyClassCampus, Fedena) digitizes this but keeps the same **form-based, menu-navigation paradigm** — it's still work to use, and it doesn't retain institutional memory (what was discussed with a parent last month, why a fee was waived, etc.).

The real competitor for a first customer isn't other school software — **it's the notebook and the WhatsApp group.** The bar to clear is "better than a notepad," not "better than Teachmint."

## 3. The solution

EduFlow puts a conversational AI assistant at the center of the product. School staff type or speak a natural-language instruction ("mark Priya absent today", "show me fee dues over 30 days", "log that Rahul's parents came in about a bullying complaint") and the AI:

1. Resolves the request against a **role- and branch-scoped view of the school's live database** (no staff member can see data outside their authority).
2. Executes real operations — not just answers — through a library of AI-callable tools that write to the same backend services the UI uses.
3. Gates every data-mutating action behind a **deterministic confirmation step** the user must approve before anything is written — the LLM proposes, a hard rule engine (not the model's judgment) enforces the safety boundary.
4. Leaves a durable, searchable **institutional memory** — every logged interaction becomes retrievable later ("what did we discuss with Rahul's parents last month?").

Structured "tool panels" (traditional CRUD screens) exist as a fallback for every function the AI performs, so no user is ever forced through chat — chat is the primary path, not the only path.

---

## 4. What makes it defensible (innovation & moat)

| Pattern | Why it matters |
|---|---|
| **Conversational operations, not conversational search** | Most "AI school software" bolts a chatbot onto a form-based ERP for Q&A. EduFlow's AI *executes* — attendance gets marked, fees get recorded, leave gets approved — through the same code path the UI uses. The conversational interface **is** the system, not a layer on top of one. |
| **Deterministic safety gate under a probabilistic model** | Every AI-proposed write passes through a hard confirm-action step and (in the architecture now being hardened) a shared service layer shared with the REST/UI routes — so an LLM write and a UI write are held to identical validation, multi-tenancy scoping, idempotency, and audit rules. This is the architectural answer to "how do you trust an LLM with real financial and academic records." |
| **Institutional memory as a product feature** | No incumbent offers a searchable log of the head-teacher's informal decisions and interactions. This is a moat that compounds — the longer a school uses EduFlow, the more valuable its retrievable history becomes, raising switching cost. |
| **India-specific fee-discount rule engine** | Sibling discounts, staff-relationship discounts, ad-hoc scholarships — configurable by the accountant without a developer, with full breakdown transparency (no black-box totals). This is a real domain-complexity barrier competitors underinvest in. |
| **First-mover in vernacular/regional Indian school ops** | Chat-first UX lowers the training burden for non-technical school staff dramatically compared to ERP-style navigation — a meaningful adoption advantage in Tier-2/3 India. |

---

## 5. Product scope today (what's built)

| Domain | Capabilities |
|---|---|
| **Authentication & RBAC** | JWT + httpOnly rotating refresh tokens, bcrypt password hashing, brute-force lockout, password reset via email, role hierarchy (owner / admin with 5 sub-categories / teacher / student) |
| **Students** | Full CRUD, guardian contacts, photos, class management, DPDP-compliant erasure path |
| **Staff** | CRUD, leave request workflow, attendance |
| **Attendance** | Bulk recording (student + staff), corrections with audit trail, real-time SSE stream, low-attendance alerts |
| **Fees** | Configurable fee structures, payment recording, a rule-based discount engine (sibling / staff-relation / ad-hoc), real-time SSE stream, idempotent transactions |
| **Academics** | Assignments, exams, results, lesson plans, AI-generated question papers |
| **AI Chat** | Role-scoped assistant, SSE streaming responses, 20+ AI-callable tools, per-role/action token budget and rate limiting |
| **Exports & Reporting** | CSV/Excel export across students, fees, attendance, staff, expenses, enquiries, exam results |
| **Notifications** | In-app system with unread counts, canonical `create_notification()` service |
| **SMS** | Twilio-backed fee reminders and parent messaging |
| **File Storage** | AWS S3-backed uploads (school-namespaced keys), presigned URLs, migrated off ephemeral disk |
| **Support / Helpdesk** | Internal query ticketing |
| **Maintenance & Operations** | Facility/tech issue tracking, vendor management, maintenance schedule |
| **Activities** | Houses, teams, positions, point tracking |
| **AI Image Generation** | Certificates, ID cards (via Google Gemini) |
| **Audit Log** | Full write-operation audit trail, viewable by owner/admin |
| **Operator Console** | Layaa AI's own super-admin panel: AI rate-limit overrides, platform health |

**Testing baseline:** 699 backend tests passing (0 skipped), covering authorization matrices per role × endpoint, AI tool-dispatch (correct execution / safe rejection on ambiguity / confirm-gate cannot be skipped), fee idempotency, and unauthenticated/wrong-role security tests on every route.

---

## 6. Technical architecture

### 6.1 System shape

```
                    AWS Amplify (React 19 SPA — frontend)
                              │  HTTPS (REST + SSE)
                              ▼
                    AWS Elastic Beanstalk (FastAPI — backend)
                              │
           ┌──────────────────┼───────────────────┬─────────────┐
           ▼                  ▼                    ▼             ▼
     MongoDB Atlas         AWS S3            Azure OpenAI    Google Gemini
     (primary DB)       (file storage)      (primary LLM)   (image gen, secondary LLM)
                                                   +
                                          Twilio SMS · SMTP email
```

Two independently deployed parts (frontend SPA, backend API) communicating **only** via REST HTTP and Server-Sent Events — no GraphQL, no gRPC, no shared memory.

### 6.2 Backend

| Layer | Technology |
|---|---|
| Framework | FastAPI 0.110 on Python 3.9, Uvicorn + Gunicorn |
| Database driver | Motor 3.3 (async MongoDB), Pydantic v2 validation throughout |
| Auth | python-jose JWT (HS256, 60-min access token) + bcrypt, httpOnly rotating refresh cookie (7-day) |
| AI | Azure OpenAI (GPT-5.3-class deployment) primary; Google Gemini secondary for image generation |
| File storage | boto3 → AWS S3, school-namespaced object keys |
| Messaging | Twilio (SMS), SMTP (transactional email) |
| Pattern | Domain-routed REST monolith — 27 route files, one `APIRouter` per domain, shared auth dependency injection, dedicated service layer, standalone AI subsystem |

**Multi-tenancy (dual-axis):**
- **School isolation** — every operational document carries `schoolId`; a `ScopedDatabase`/`ScopedCollection` proxy auto-injects and auto-filters it on every read/write. Currently one school per deployment (env-var-scoped); JWT-claim-based multi-school is an identified architecture evolution for scaling to many schools on shared infrastructure.
- **Branch isolation** — multi-campus schools scope by `branch_id` (from JWT claim), explicitly passed via `scoped_query()`; conflicting branch scoping raises a hard error rather than silently returning cross-branch data.

**AI request pipeline:**
```
User message → context_builder (role/scope-aware data fetch)
             → scope_resolver (which data this user may see)
             → prompts (role-specific system prompt)
             → content_filter (input safety check)
             → llm_client (Azure OpenAI primary / Gemini secondary)
             → tool_functions (20+ tools; every tool enforces scoped_query())
             → token_service (per-branch/per-user budget deduction)
             → SSE stream to client
```
Rate limiting is per-role, per-action, config-driven (`ai_rate_limits.yaml`), tracked in MongoDB.

**Security controls already in place:** JWT + httpOnly refresh, `require_role()`/`require_access()`/`require_owner()` FastAPI dependency gates, bcrypt hashing, brute-force lockout (5 attempts / 15 min), NoSQL-injection input validation, explicit CORS allowlist (no wildcard), HSTS + CSP + X-Frame-Options in production, idempotency-key support on mutating endpoints, full audit trail on writes, structured 500-error handling that never leaks internals.

### 6.3 Frontend

| Layer | Technology |
|---|---|
| Framework | React 19 (CRA + CRACO build) |
| Styling / components | Tailwind CSS v3 + shadcn/ui (Radix primitives), 40+ base components |
| Forms | React Hook Form + Zod |
| Routing | React Router v7 |
| State | React Context only (no Redux) — `UserContext` (auth), `ThemeContext` |
| Charts | Recharts |
| Language | Plain JavaScript — no TypeScript anywhere in the codebase |
| Deployment | AWS Amplify |

The UI is **chat-first**: `ChatInterface.js` (SSE-streamed conversation, markdown/table/artifact rendering, inline confirm-action cards, token-budget indicator) is the default landing surface. Role-specific "tool panels" (18+ components: fee collection, student database, staff tracker, attendance recorder, maintenance tools, etc.) provide direct structured access and are rendered conditionally based on `user.role` + `user.sub_category` — every capability the AI has is also reachable without chat.

### 6.4 Data model highlights

- MongoDB Atlas, string UUID4 IDs (no ObjectId exposure to clients)
- System collections (`auth_users`, `refresh_tokens`, `login_attempts`, OTPs) are exempt from tenant scoping by design
- Financial and academic records use **soft-correction with audit trail**, never hard delete — required for CBSE record-retention (5–7 years) and financial integrity; a separate hard-delete path exists only for DPDP erasure requests
- Discount engine stores full breakdown (original fee, each discount with label/value, final amount) — no black-box totals, full audit trail of who applied what and when

---

## 7. Compliance & data protection posture

Built for the Indian regulatory environment specifically (not a US-market product retrofitted for India):

- **DPDP Act 2023** is the primary compliance target — student data treated as personal data of minors; erasure-on-request capability built in; PII minimization enforced before any data reaches the LLM (`ai/redaction.py`); AI never sends identifiable student PII to the model without redaction.
- **No FERPA/COPPA** — explicitly out of scope; this is an India-only regulatory posture by design, keeping compliance surface area small and focused.
- **CBSE record-keeping** — attendance/academic records retained per board requirement (5 yrs), financial records per Indian standard (7 yrs) — hard delete is prohibited by design for these classes of record.
- **Biometric data** — hardware attendance integrations are scoped to receive only processed present/absent events, never raw biometric data (sensitive-category PII under DPDP).
- **Data residency** — AWS infra targets Mumbai (ap-south-1) for latency and residency; Azure OpenAI DPA/residency terms are an explicit pre-go-live gate for any deployment carrying live student PII.
- **AI action governance (in active hardening)** — a formal initiative (documented in `AI-LAYER-HARDENING-HANDOFF.md`) is underway to guarantee that every AI-triggered write goes through the *identical* validated service layer as the UI (parity), wrapped in atomic transactions, behind a kill-switch and shadow/dry-run rollout mode, with a two-step confirmation + actor-tagged audit log required for any destructive action. Phase 1 of this hardening restricts all AI write/action capability to Owner + Principal roles only, pending their live sign-off, before expanding to the rest of school staff.

This compliance-by-architecture posture (not compliance-as-afterthought) is a genuine differentiator for a category where most vendors are still digitizing paper forms without touching data-governance design.

---

## 8. Business plan & market (as scoped by founders — [UNVALIDATED] where marked)

**Current stage:** Pre-revenue. The Aaryans (a multi-branch CBSE school group in Uttar Pradesh) is the founding development pilot customer — ₹0 ARR today; post-pilot conversion to a paid plan is the first planned revenue event.

**Pilot gate:** four consecutive "clean" weeks (no unresolved data errors, no reversion to paper/WhatsApp, no unresolved support issue >48h) before pitching a second school.

**Go-to-market sequencing:** Phase 1 targets Owner + Admin-role staff only (principal, accountant, receptionist, IT/tech, maintenance, transport) with the full school database loaded from day one even though teachers/students aren't yet logging in — de-risks the trust-building phase before opening the platform to the full user base. Phase 2 activates teacher/student logins, WhatsApp integration, and richer reporting once retention is proven.

**[UNVALIDATED] revenue targets (founder planning anchors, explicitly flagged in internal docs as not yet pressure-tested against comparable products):**

| Horizon | Target |
|---|---|
| Year 1 | ₹8–12L ARR — 2–3 paying schools (including The Aaryans converting post-pilot) |
| Year 2 | ₹30–40L ARR — 10+ paying schools |
| Gross margin target | ≥65% |
| Net margin target | ≥30% |
| Provisional pricing anchor | ₹25,000–33,000 per school per month |

**Competitive landscape (as scoped by founders):**

| Competitor | Paradigm | EduFlow's difference |
|---|---|---|
| Teachmint | Form-based, teacher-first | Chat-first, owner/admin-first |
| MyClassCampus | ERP-style, complex navigation | Conversational, zero navigation |
| Fedena | Open-source, developer-configured | Opinionated, AI-native, zero-config |
| WhatsApp + Excel (status quo) | Fragmented, no institutional memory | Unified, searchable, persistent |

**Validation signal being tracked:** daily qualifying use (≥1 live AI query or logged tool action) by Owner and Principal within 2 weeks of go-live; a 10-question, self-authored operational walkthrough passed with zero paper/WhatsApp fallback at week 4; retention confirmed at month 3 before any second-school pitch.

---

## 9. Team-visible operator layer (why this matters for an incubator pitch)

EduFlow ships with its own internal operator console for the founding team (Layaa AI) — platform health monitoring, AI rate-limit administration, support ticket triage, and (in the growth-phase roadmap) token-based subscription billing and revenue tracking. This means the product is being built with **multi-tenant SaaS operability in mind from day one**, not retrofitted after a single-customer pilot — relevant evidence for scalability claims in a pitch.

---

## 10. Roadmap (as currently scoped)

| Phase | Scope |
|---|---|
| **MVP (current)** | Owner + all Admin sub-roles live, full CRUD, S3 storage, structured logging + health checks, graceful AI degradation, hardened test baseline |
| **Growth (next)** | Teacher/student logins activated, WhatsApp/Twilio parent notifications, advanced reporting (attendance/fee trend charts), token recharge + subscription billing, Layaa AI platform-health operator dashboard, new-school onboarding flow |
| **AI Layer Hardening (planned, gated on review)** | Shared-service parity between AI and UI writes, atomic multi-step "plan then confirm once" execution, DPDP-grade redaction, kill-switch + shadow-mode rollout, AI self-learning/memory for Owner & Principal, full student/staff/school-internals CRUD via AI, phased role rollout starting Owner+Principal-only |
| **Vision (scale)** | Mobile-first app, parent portal (fee payment, attendance alerts, teacher messaging), API access tier, CBSE/UP-Board-scoped AI tutoring, multi-campus/school-group support, automated regulatory reporting (UDISE+ pending confirmation) |

---

## 11. Notes for whoever drafts the pitch deck from this document

- Lead with the problem (paper diary + WhatsApp) and the paradigm shift (conversational execution, not conversational search) — that's the strongest differentiation story, not the tech stack.
- The **deterministic confirm-gate under a probabilistic model** is the most defensible technical story for a judge/reviewer skeptical of "AI does everything" pitches — use it to answer "how do you prevent the AI from making a mistake with real financial/academic data."
- Do **not** present the Year 1/Year 2 ARR figures as validated traction — they are explicitly flagged in the source planning docs as unvalidated founder anchors. Present them as "target" or "plan," and pair with the actual current stage (pre-revenue, single development pilot, gated second-school expansion).
- The compliance-by-design posture (DPDP-specific, not a US-compliance product retrofitted) is a strong India-market-fit argument for a scheme like SISFS, which specifically funds India-context innovation.
- If real usage data exists from The Aaryans pilot by the time the deck is built (daily active use rate, walkthrough pass/fail, weeks without paper fallback), that is the single most credible slide in the deck — surface it prominently once available. As of this document, that data was not present in the repository.
