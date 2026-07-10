# Architecture — Frontend (React SPA)

_Generated: 2026-05-15 | Scan: deep | Part: frontend_

---

## Executive Summary

EduFlow's frontend is a **React 19 SPA** built with CRA + CRACO. It is a role-based chat-centric interface: all school management actions are accessible either through an AI chat assistant or through structured tool panels.

Key design decisions:
1. **Chat-first UX** — AI chat is the primary interaction pattern; tools are secondary panels
2. **Role-based rendering** — Sidebar links and tool components change based on `user.role` + `user.sub_category`
3. **Plain JavaScript** — No TypeScript; all files are `.js` / `.jsx`
4. **shadcn/ui design system** — Radix UI primitives + Tailwind CSS v3 (40+ base components)
5. **Context-based auth** — `UserContext` holds session state; no Redux

---

## Technology Stack

| Concern | Tech | Version |
|---------|------|---------|
| Framework | React | 19.0.0 |
| Router | React Router DOM | 7.5.1 |
| Build tool | CRA + CRACO | react-scripts 5.0.1 + @craco/craco 7.1.0 |
| Styling | Tailwind CSS | 3.4.17 (v3 — NOT v4) |
| Component system | shadcn/ui (Radix UI) | Various |
| Forms | React Hook Form + Zod | 7.56.2 + 3.24.4 |
| Charts | Recharts | 3.6.0 |
| Date handling | date-fns | **3.6.0** (pinned — v4 breaks react-day-picker) |
| Date picker | react-day-picker | **8.10.1** (pinned — v9 API incompatible) |
| HTTP (uploads) | axios | 1.8.4 |
| HTTP (all other) | Native `fetch()` | — |
| Icons | Lucide React | 0.507.0 (only icon library) |
| Toasts | sonner | 2.0.3 |
| Deployment | AWS Amplify | — |

---

## Architecture Pattern

**Single-page application** with:
- Context-based global state (Auth, Theme)
- Component composition via shadcn/ui primitives
- Role-based conditional rendering
- Centralized API client (`lib/api.js`)
- SSE streaming for AI responses

---

## Application Structure

```
src/
├── index.js          # React.render → <App />
├── App.js            # Route definitions + auth guard
│
├── contexts/
│   ├── UserContext.js     # Auth state: {user, token, login(), logout()}
│   └── ThemeContext.js    # Dark/light mode
│
├── lib/
│   ├── api.js             # All fetch() calls — organized by domain
│   ├── authSession.js     # localStorage helpers for session persistence
│   └── utils.js           # cn() (tailwind class merge), other utilities
│
├── components/            # Shell + cross-cutting components
│   ├── Layout.js          # Outer shell: sidebar + header + content area
│   ├── Sidebar.js         # Nav links (role-filtered)
│   ├── ChatInterface.js   # AI chat: SSE stream, message list, confirm dialogs
│   ├── InputBar.js        # Chat input with file attachment support
│   ├── MessageRenderer.js # Markdown + artifact renderer
│   └── ...
│
└── components/tools/      # Domain-specific tool panels
    ├── ToolPage.js        # Tool router: reads URL → renders correct tool
    ├── AdminTools.js      # Admin/owner management panel
    ├── OwnerTools.js      # School-level owner actions
    └── ...
```

---

## Auth Flow

```
1. Login
   UserContext.login(username, password)
   → POST /api/auth/login
   → store {user, token} in UserContext + localStorage
   → React Router navigates to /chat

2. Protected routes (App.js)
   <ProtectedRoute> reads UserContext.user
   → null → redirect to /login
   → present → render children

3. Token refresh
   api.js interceptor: if 401, POST /api/auth/refresh
   → success: retry original request
   → failure: UserContext.logout()

4. Logout
   UserContext.logout()
   → POST /api/auth/logout
   → clear localStorage + user state
   → navigate to /login
```

---

## Role-Based Rendering

The `user.role` and `user.sub_category` fields from the JWT control what the user sees:

| Role | sub_category | Tool Component | Sidebar Items |
|------|-------------|----------------|---------------|
| `owner` | — | OwnerTools + AdminTools | All |
| `admin` | `principal` | PrincipalDailyOps + AdminTools | Staff, Students, Attendance, Fees, Reports |
| `admin` | `accountant` | FeeCollection + AdminTools | Fees, Students |
| `admin` | `receptionist` | AdminTools | Visitors, Queries, Notifications |
| `admin` | `it_tech` | AdminTools | Issues (tech) |
| `admin` | `maintenance` | MaintenanceTools | Issues, Maintenance |
| `teacher` | — | TeacherTools + AttendanceRecorder | Academics, Attendance |
| `student` | — | StudentTools | My profile, My fees, My attendance |

---

## State Management

No Redux. Global state via React Context:

| Context | State | Provider location |
|---------|-------|------------------|
| `UserContext` | `user`, `token`, `login()`, `logout()` | `App.js` root |
| `ThemeContext` | `theme`, `setTheme()` | `App.js` root |

Local state in components via `useState` / `useReducer`.

---

## API Client (`lib/api.js`)

All backend calls go through `lib/api.js`. Pattern:
```js
// All other endpoints — native fetch()
const res = await fetch(`${API_BASE}/students`, {
  headers: { Authorization: `Bearer ${token}` }
})

// File uploads only — axios
const res = await axios.post(`${API_BASE}/uploads`, formData, {
  headers: { Authorization: `Bearer ${token}` }
})
```

`API_BASE` defaults to `http://localhost:8000` in dev, configured via `REACT_APP_API_URL` env var in prod.

---

## Component Inventory

### Shell Components
| Component | Purpose |
|-----------|---------|
| `Layout.js` | Outer container — sidebar + main area |
| `Sidebar.js` | Navigation (role-filtered links) |
| `Header.js` | Top bar — user menu, notifications badge, theme toggle |
| `ErrorBoundary.js` | React error boundary for route-level crashes |

### Auth Components
| Component | Purpose |
|-----------|---------|
| `Login.js` | Username/password login form |
| `ForgotPassword.js` | Password reset request form |
| `ResetPassword.js` | Password reset via token (from email link) |

### AI Chat Components
| Component | Purpose |
|-----------|---------|
| `ChatInterface.js` | Conversation list + message thread + SSE stream handler |
| `InputBar.js` | Message input with attachment support |
| `MessageRenderer.js` | Renders AI messages (markdown, tables, action buttons, artifacts) |
| `ThinkingProcess.js` | Expandable "thinking steps" display |
| `ConfirmActionCard.js` | Confirmation prompt for destructive AI actions |
| `CommandPalette.js` | ⌘K global command palette |
| `TokenBudgetBar.js` | AI token remaining budget indicator |

### Management Components
| Component | Purpose |
|-----------|---------|
| `ToolDashboard.js` | Tool selection grid (navigates to ToolPage) |
| `ProfileModal.js` | User profile view/edit modal |
| `SettingsModal.js` | School settings modal (owner/admin) |
| `Toast.js` | Toast notification renderer (sonner) |

### Tool Panels
| Component | Role | Domain |
|-----------|------|--------|
| `OwnerTools.js` | owner | School settings, AI budget, year-end transition |
| `AdminTools.js` | admin | General admin panel |
| `PrincipalDailyOps.js` | principal | Daily ops dashboard |
| `TeacherTools.js` | teacher | Assignments, exams, lesson plans |
| `StudentTools.js` | student | Profile, fees, attendance, assignments |
| `AttendanceRecorder.js` | teacher/admin | Bulk attendance recording |
| `FeeCollection.js` | accountant/admin | Fee payment recording |
| `FeeSync.js` | accountant | Fee synchronization |
| `StudentDatabase.js` | admin/owner | Student CRUD interface |
| `StaffTracker.js` | admin/owner | Staff management + leave |
| `SchoolPulse.js` | admin/owner | Dashboard analytics |
| `AuditLog.js` | admin/owner | Audit trail viewer |
| `FileUpload.js` | All | Document upload + management |
| `IncidentTracker.js` | All | Incident reporting |
| `MaintenanceTools.js` | maintenance | Maintenance requests + schedule + vendors |
| `QuerySection.js` | All | Support ticket management |
| `SchoolActivities.js` | admin | Houses, positions, teams |
| `TimetableBuilder.js` | admin/teacher | Timetable construction |

### shadcn/ui Primitives (40+ components)
Accordion, AlertDialog, Alert, AspectRatio, Avatar, Badge, Breadcrumb, Button, Calendar, Card, Carousel, Checkbox, Collapsible, Command, ContextMenu, Dialog, Drawer, DropdownMenu, Form, HoverCard, Input, InputOTP, Label, Menubar, NavigationMenu, Pagination, Popover, Progress, RadioGroup, Resizable, ScrollArea, Select, Separator, Sheet, Skeleton, Slider, Sonner, Switch, Table, Tabs, Textarea, Toast, Toaster, ToggleGroup, Toggle, Tooltip.

---

## Build & Deployment

**Local dev:**
```bash
cd frontend
yarn install
yarn start       # CRA dev server on :3000
```

**Build:**
```bash
yarn build       # → frontend/build/ (via craco)
```

**Path alias:** `@/` maps to `src/` (configured in `craco.config.js` + `jsconfig.json`).

**AWS Amplify (prod):**
- Build command: `yarn build`
- Output directory: `build/`
- Environment var: `REACT_APP_API_URL` → backend URL

---

## Known Constraints

- **Plain JS only** — never create `.ts`/`.tsx` files
- **Tailwind v3** — do NOT use v4 syntax; `@layer base` conflicts
- **date-fns v3** — pinned; upgrading to v4 breaks `react-day-picker 8.x`
- **react-day-picker 8.x** — pinned; v9 API is incompatible
- **axios for uploads only** — all other HTTP calls use native `fetch()`
- **Lucide React only** — no other icon library
- **No TypeScript** — no `tsc`, no type annotations
