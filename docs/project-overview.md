# Project Overview - EduFlow

_Generated: 2026-05-15 | Scan: deep_

---

## What is EduFlow?

EduFlow is a **school management platform** built around an AI chat assistant. School staff (owners, principals, teachers, accountants, etc.) interact with the system primarily through natural language - asking the AI to show student data, record attendance, collect fees, generate reports, and more. Structured tool panels provide direct CRUD access for bulk operations.

---

## Architecture Type

**Multi-part web application** (SPA + REST API)

| Part | Technology | Hosting |
|------|-----------|---------|
| Frontend | React 19 SPA (Vite, Tailwind, shadcn/ui) | AWS Amplify |
| Backend | FastAPI (Python 3.9, Motor, MongoDB) | AWS Elastic Beanstalk |
| Database | MongoDB Atlas | Cloud |
| File storage | AWS S3 | Cloud |
| AI | Azure OpenAI (GPT-5.3) + Google Gemini | Cloud |

---

## Key Capabilities

| Domain | Features |
|--------|---------|
| **Authentication** | JWT + httpOnly refresh tokens, role-based access, brute-force lockout, password reset via email |
| **Students** | CRUD, guardian contacts, photos, class management, GDPR erasure |
| **Admissions** | One screen (added 2026-08-14) carrying enquiries, applications and pipeline value. Enquiry stages, follow-up call worklist, applications through assessment and offer, and enrolment that creates the child and the guardians in one transaction. **Enrolment has exactly one source and nobody can set it by hand.** |
| **Staff** | CRUD, leave request management, attendance |
| **Attendance** | Bulk recording (student + staff), corrections, SSE real-time stream, low-attendance alerts |
| **Fees** | Fee structures, payment recording, discounts, SSE stream, per-student status |
| **Academics** | Assignments, exams, results, lesson plans, AI question paper generation |
| **AI Chat** | Role-scoped AI assistant with tool use, SSE streaming, action confirmation, token budget |
| **AI Tools** | Named tools executable via `/api/tools/{tool_id}/execute`. Roughly 170 of them at 2026-08-14, about 100 of which write. _This said "20+" until then, which was out by a factor of eight._ The registry in `backend/ai/tool_functions_v2.py` is the only reliable count; what each profile may reach is pinned by a test that fails if anybody's access changes without a decision |
| **Exports** | CSV/Excel exports for students, fees, attendance, staff, expenses, enquiries, exam results |
| **Notifications** | In-app notification system with unread count |
| **SMS** | Twilio-backed fee reminders and parent messaging |
| **File Storage** | S3-backed document and photo storage |
| **Support Tickets** | Internal help desk query management |
| **Maintenance** | Facility/tech issue tracking + vendor management + schedule |
| **Activities** | School houses, teams, positions, points |
| **Image Generation** | AI-generated certificates and ID cards |
| **Audit Log** | Full audit trail for all write operations |
| **Operator Panel** | Super-admin AI rate limit overrides |

---

## Multi-Tenancy Model

EduFlow uses **dual-axis tenancy**:

1. **School** - `schoolId` field on every document; value from `SCHOOL_ID` env var. Currently single-school per deployment.
2. **Branch** - `branch_id` field on operational docs; value from JWT claim. The live school currently has one active Joya branch; scoping remains for future expansion.

All MongoDB queries are automatically scoped by `ScopedDatabase` (schoolId) and explicitly by `scoped_query()` (branch_id).

---

## User Roles

| Role | Sub-category | Capabilities |
|------|-------------|-------------|
| `owner` | - | Full access: all settings, AI budget, year-end transition |
| `admin` | `principal` | Staff management, approvals, leave decisions |
| `admin` | `accountant` | Fee collection, financial reports |
| `admin` | `receptionist` | Visitor log, queries, notifications |
| `admin` | `it_tech` | Tech support issues |
| `admin` | `maintenance` | Facility requests, maintenance schedule, vendors |
| `teacher` | - | Attendance, assignments, exams, lesson plans |
| `student` | - | Own profile, own fees, own attendance, own assignments |

---

## Quality Status

_Updated 2026-08-14. The table that stood here was dated 2026-05-15 and showed Part 4 as
"next"; Parts 1 to 16 of the quality sweep all completed, and several releases have shipped
since._

**The bar is the FAILURE count, and it is zero.** No pass count is recorded here on
purpose. This section used to pin "387 tests passing", which went stale within weeks and
was then read as a target. The suite grows every release; run it and read the number it
prints. See `CLAUDE.md` for the commands.

| Shipped | What |
|---|---|
| Quality sweep Parts 1 to 16 | Auth and RBAC, AI layer, owner vertical, multi-tenancy, role verticals |
| AI Layer Reliability (R1 to R15) | Zero silent failures |
| Release 2 (2026-08-10) | Person profiles for the accountant and management heads, and one written grant table replacing permission-by-subtraction |
| Release 3 (2026-08-12) | The whole list on any device: filters, complete-or-refused downloads, "All" views, phone and tablet touch floors |
| Release 4 (2026-08-13) | The platform can account for itself: audit trail, undo, honest menus |
| Admissions stage one (2026-08-14) | The two halves of the admissions funnel joined, on one screen |

**Not built:** admissions stage two (entrance tests as records, the paper, marking, and
enquiry families as a messaging audience). Whether an applicant may hold a sign-in to sit a
test on screen is an open question and is not settled.

---

## Repository Layout

```
eduflow/
├── backend/          # FastAPI server
├── frontend/         # React SPA
├── tests/            # Backend integration + E2E tests
├── _bmad-output/     # Planning artifacts + project context
└── docs/             # This documentation suite
```

---

## Getting Started

**Backend:**
```bash
cd backend
python3.9 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Edit with your values
uvicorn server:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
yarn install
yarn start             # Opens http://localhost:3000
```

**Tests:**
```bash
APP_AVAILABLE=true pytest tests/backend/ -v
```

**Full docs:** See [`docs/index.md`](./index.md)
