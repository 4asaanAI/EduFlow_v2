# Project Overview — EduFlow

_Generated: 2026-05-15 | Scan: deep_

---

## What is EduFlow?

EduFlow is a **school management platform** built around an AI chat assistant. School staff (owners, principals, teachers, accountants, etc.) interact with the system primarily through natural language — asking the AI to show student data, record attendance, collect fees, generate reports, and more. Structured tool panels provide direct CRUD access for bulk operations.

---

## Architecture Type

**Multi-part web application** (SPA + REST API)

| Part | Technology | Hosting |
|------|-----------|---------|
| Frontend | React 19 SPA (CRA + CRACO, Tailwind, shadcn/ui) | AWS Amplify |
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
| **Staff** | CRUD, leave request management, attendance |
| **Attendance** | Bulk recording (student + staff), corrections, SSE real-time stream, low-attendance alerts |
| **Fees** | Fee structures, payment recording, discounts, SSE stream, per-student status |
| **Academics** | Assignments, exams, results, lesson plans, AI question paper generation |
| **AI Chat** | Role-scoped AI assistant with tool use, SSE streaming, action confirmation, token budget |
| **AI Tools** | 20+ named tools executable via `/api/tools/{tool_id}/execute` |
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

1. **School** — `schoolId` field on every document; value from `SCHOOL_ID` env var. Currently single-school per deployment.
2. **Branch** — `branch_id` field on operational docs; value from JWT claim. Multi-branch within one school.

All MongoDB queries are automatically scoped by `ScopedDatabase` (schoolId) and explicitly by `scoped_query()` (branch_id).

---

## User Roles

| Role | Sub-category | Capabilities |
|------|-------------|-------------|
| `owner` | — | Full access: all settings, AI budget, year-end transition |
| `admin` | `principal` | Staff management, approvals, leave decisions |
| `admin` | `accountant` | Fee collection, financial reports |
| `admin` | `receptionist` | Visitor log, queries, notifications |
| `admin` | `it_tech` | Tech support issues |
| `admin` | `maintenance` | Facility requests, maintenance schedule, vendors |
| `teacher` | — | Attendance, assignments, exams, lesson plans |
| `student` | — | Own profile, own fees, own attendance, own assignments |

---

## Quality Status (as of 2026-05-15)

| Part | Scope | Status |
|------|-------|--------|
| Part 1: Auth + RBAC | JWT, roles, branch scoping | ✅ Complete |
| Part 1.5: Fixes | 16 review findings | ✅ Complete |
| Part 2: AI Layer | Rate limiting, token budget, tool scoping | ✅ Complete |
| Part 3: Owner role | Owner vertical, exports, reports | ✅ Complete |
| Part 4: Multi-tenancy | Cross-tenant data, require_access(), migration gaps | 🔜 Next |

Backend test suite: **387 tests passing, 0 skipped**.

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
