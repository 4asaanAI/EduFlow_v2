# EduFlow — Student & Teacher Tools Reference

> **Last updated:** 2026-06-13  
> **Scope:** All structured panel tools and AI-chat tools available to the `student` and `teacher` roles.  
> Two access surfaces exist for each role: the **Tool Dashboard** (structured UI panels launched via `?tool=<id>`) and the **AI Chat** (natural-language assistant with backend tool-calls). Both are documented here.

---

## Table of Contents

1. [How Tools Are Accessed](#how-tools-are-accessed)
2. [Student Tools — Panel UI](#student-tools--panel-ui)
   - [AI Tutor](#1-ai-tutor)
   - [Doubt Solver](#2-doubt-solver)
   - [Homework & Assignments](#3-homework--assignments)
   - [My Attendance](#4-my-attendance)
   - [My Results](#5-my-results)
   - [Practice Tests](#6-practice-tests)
   - [Study Planner](#7-study-planner)
   - [Career Guidance AI](#8-career-guidance-ai)
   - [My Fees](#9-my-fees)
   - [PTM Summary](#10-ptm-summary)
   - [Forms](#11-forms)
   - [Raise Maintenance Request](#12-raise-maintenance-request-student)
3. [Student Tools — AI Chat](#student-tools--ai-chat)
4. [Teacher Tools — Panel UI](#teacher-tools--panel-ui)
   - [Attendance (Class)](#1-attendance-class)
   - [Assignments](#2-assignments)
   - [Question Papers](#3-question-papers)
   - [Report Cards](#4-report-cards)
   - [Student Performance (Admin view)](#5-student-performance-admin-view)
   - [Leave Application](#6-leave-application)
   - [Lesson Plans](#7-lesson-plans)
   - [Worksheets](#8-worksheets)
   - [Class Analytics](#9-class-analytics)
   - [Substitutions](#10-substitutions)
   - [PTM Notes](#11-ptm-notes)
   - [Curriculum Tracker](#12-curriculum-tracker)
   - [Forms](#13-forms-teacher)
   - [Raise Maintenance Request](#14-raise-maintenance-request-teacher)
5. [Teacher Tools — AI Chat](#teacher-tools--ai-chat)
6. [Role vs. Tool Access Matrix](#role-vs-tool-access-matrix)
7. [Shared Tool Details](#shared-tool-details)

---

## How Tools Are Accessed

### Panel Tools
All panel tools open as full-page views inside the EduFlow SPA at `/?tool=<tool-id>`.

**Student** — 12 tools, mapped in `frontend/src/components/ToolDashboard.js:TOOL_SETS.student`  
**Teacher** — 14 tools, mapped in `frontend/src/components/ToolDashboard.js:TOOL_SETS.teacher`

Tool components load lazily through `frontend/src/components/Layout.js:loadTool()`. The routing precedence is: `OWNERS → ADMINS → TEACHERS → STUDENTS`. Tools that appear in both the teacher list and the admin list (e.g., `report-card-builder`) load the **AdminTools** version because that array is checked first.

### AI Chat Tools
The AI assistant (chat route `POST /api/chat/conversations/:id/messages`) invokes backend tool functions from `backend/ai/tool_functions_v2.py`. Each tool in `TOOL_REGISTRY` declares a `"roles"` array. The auth middleware enforces role-level gating before any tool runs.

---

## Student Tools — Panel UI

### 1. AI Tutor
**Tool ID:** `ai-tutor`  
**Component:** `frontend/src/components/tools/StudentTools.js:AiTutor`

#### What it does
A persistent conversational AI tutor powered by the school's Azure OpenAI deployment. The student types a question in a chat interface and receives a streaming response. The conversation is stored per-student in a dedicated chat conversation (keyed `tutor_conv_<userId>` in localStorage, backed by a real conversation record).

The tutor is explicitly prompted to follow NCERT/CBSE curriculum and will hint rather than directly solve assignment questions.

#### How it works
1. On first load, creates a new conversation via `POST /api/chat/conversations` with title "AI Tutor".  
2. Every message hits `POST /api/chat/conversations/:id/messages` as a server-sent event (SSE) stream.  
3. The response is rendered token-by-token.

#### Impacted areas
| Layer | Detail |
|-------|---------|
| **DB** | `conversations` collection (new doc on first visit), `messages` collection (each turn) |
| **AI** | Azure OpenAI call via `backend/routes/chat.py` / `backend/ai/llm_client.py` |
| **Tokens** | Consumes the student's AI token quota |
| **Audit** | Chat messages emit a LayaaStat SSE event (observability) |

#### Roles that see this tool
`student` only

---

### 2. Doubt Solver
**Tool ID:** `doubt-solver`  
**Component:** `frontend/src/components/tools/StudentTools.js:DoubtSolver`

#### What it does
A one-shot question answering tool. The student types a doubt, clicks "Solve My Doubt", and gets an AI answer displayed inline below the input. Unlike the AI Tutor, this is stateless — each click creates a brand-new conversation.

#### How it works
1. Click "Solve My Doubt" → creates a new conversation via `POST /api/chat/conversations`.  
2. Sends `"Doubt: <text>"` as the first message and streams the response into a single text block.

#### Impacted areas
| Layer | Detail |
|-------|---------|
| **DB** | `conversations` + `messages` (a new conversation is created for each doubt) |
| **AI** | Azure OpenAI call |
| **Tokens** | Consumes AI token quota |

#### Roles that see this tool
`student` only

---

### 3. Homework & Assignments
**Tool ID:** `homework-viewer`  
**Component:** `frontend/src/components/tools/StudentTools.js:HomeworkViewer`

#### What it does
Shows the student all assignments their class has been given. Assignments are read from the backend scoped to the student's `class_id`. Each row shows title, subject, due date, and an OVERDUE/ACTIVE badge. Clicking a row opens a detail view showing the full description/instructions.

Stats header shows total, overdue, and upcoming counts.

#### How it works
- `GET /api/academics/assignments` — the backend scopes the query to the student's enrolled class (`backend/routes/academics.py:list_assignments`, line 65–68). No class_id filter is needed from the frontend because the backend reads the student record and injects it.

#### Impacted areas
| Layer | Detail |
|-------|---------|
| **DB** | `assignments` collection (read-only), `students` collection (to resolve class_id), `subjects` + `classes` collections (for enrichment) |
| **Backend** | `backend/routes/academics.py` → `GET /api/academics/assignments` |

#### Roles that see this tool
`student` only

---

### 4. My Attendance
**Tool ID:** `attendance-self-check`  
**Component:** `frontend/src/components/tools/StudentTools.js:AttendanceSelfCheck`

#### What it does
Shows the student their own attendance statistics and a rolling 7-day history table. Displays:
- Attendance percentage (highlighted red if below 75%)
- Present days, absent days, total days (last 30 days)
- ⚠️ Warning banner if attendance is below 75% (exam eligibility risk)

#### How it works
- Calls `executeTool('get_my_attendance', {}, currentUser)` from `frontend/src/lib/api.js`.  
- This hits `POST /api/tools/execute` with `{ tool: "get_my_attendance" }`.  
- The backend AI tool `tool_get_my_attendance` resolves the student via `user_id`, then queries `student_attendance` for the last 30 days.

#### Impacted areas
| Layer | Detail |
|-------|---------|
| **DB** | `students` (resolve student record by user_id), `student_attendance` (last 30 days) |
| **Backend** | `backend/routes/tools.py` → `POST /api/tools/execute`, calls `tool_get_my_attendance` |
| **AI tool** | `backend/ai/tool_functions.py:tool_get_my_attendance` |

#### Roles that see this tool
`student` only

---

### 5. My Results
**Tool ID:** `result-viewer`  
**Component:** `frontend/src/components/tools/StudentTools.js:ResultViewer`

#### What it does
Shows the student all their exam results. Displays exam name, subject, marks obtained out of max marks, and a grade badge (A = green, B = blue, others = yellow).

#### How it works
- Calls `executeTool('get_my_results', {}, currentUser)`.  
- The backend tool `tool_get_my_results` resolves the student, fetches `exam_results` for that student_id, and enriches each row with subject name (from `subjects`) and exam name (from `exams`).

#### Impacted areas
| Layer | Detail |
|-------|---------|
| **DB** | `students`, `exam_results`, `subjects`, `exams` |
| **Backend** | `POST /api/tools/execute` → `tool_get_my_results` |
| **AI tool** | `backend/ai/tool_functions.py:tool_get_my_results` |

#### Roles that see this tool
`student` only

---

### 6. Practice Tests
**Tool ID:** `practice-test`  
**Component:** `frontend/src/components/tools/StudentTools.js:PracticeTest`

#### What it does
Generates AI-powered 5-question MCQ quizzes on demand. The student picks a subject (Mathematics, Science, English, Social Science, Hindi), optionally enters a specific topic, and selects difficulty (Easy / Medium / Hard). The AI generates the questions, the student answers, and clicks "Submit Test" to see their score with correct answers highlighted.

Questions are parsed from a structured AI response format:
```
Q: [question]
A) ... B) ... C) ... D) ...
Answer: [letter]
```

Score feedback: `≥80%` → Excellent, `≥60%` → Good effort, `<60%` → Keep practicing.

#### How it works
1. Creates a new conversation `POST /api/chat/conversations` with title "Practice Test".  
2. Sends a structured prompt requesting exactly 5 MCQs in a fixed format.  
3. Parses the streamed response client-side with regex block-splitting.  
4. No server-side storage of questions or answers — entirely ephemeral.

#### Impacted areas
| Layer | Detail |
|-------|---------|
| **DB** | `conversations` + `messages` (ephemeral per test run) |
| **AI** | Azure OpenAI call |
| **Tokens** | Consumes AI token quota per test generation |

#### Roles that see this tool
`student` only

---

### 7. Study Planner
**Tool ID:** `study-planner`  
**Component:** `frontend/src/components/tools/StudentTools.js:StudyPlanner`

#### What it does
A persistent weekly study schedule. The student fills in a text field for each weekday (Monday–Saturday) with what they plan to study (e.g. "Maths Chapter 5, Physics revision"). Clicking "Save My Plan" persists it to the backend. The plan is reloaded on next visit.

#### How it works
- Load: `GET /api/ops/study-plan` — returns the student's saved plan.
- Save: `POST /api/ops/study-plan` — upserts the plan document.
- The backend stores the plan keyed by `user_id` in the operations collection.

#### Impacted areas
| Layer | Detail |
|-------|---------|
| **DB** | `study_plans` (or similar ops collection) keyed by `user_id` |
| **Backend** | `backend/routes/operations.py` → `GET /api/ops/study-plan`, `POST /api/ops/study-plan` |

#### Roles that see this tool
`student` only

---

### 8. Career Guidance AI
**Tool ID:** `career-guidance`  
**Component:** `frontend/src/components/tools/StudentTools.js:CareerGuidance`

#### What it does
AI-powered career counselling personalised to the student's academic performance. Loads the student's exam results for context, then lets them ask free-form career questions (or click suggestion chips like "What career should I choose based on my marks?").

The AI prompt is enriched with the student's actual result data (subject-wise marks) so advice is personalised.

Suggestion chips: "What career should I choose based on my marks?", "How to prepare for IIT JEE?", "What are options after 10th?", "Tell me about medical careers", "What subjects for IAS/UPSC?".

#### How it works
1. On mount: `GET /api/academics/results` to load the student's results for context.  
2. On question: creates a new conversation and sends a composite prompt containing `"Student's results: ..."` + the question.

#### Impacted areas
| Layer | Detail |
|-------|---------|
| **DB** | `exam_results` (read for context), `conversations` + `messages` |
| **AI** | Azure OpenAI call |
| **Tokens** | Consumes AI token quota |

#### Roles that see this tool
`student` only

---

### 9. My Fees
**Tool ID:** `fee-status-viewer`  
**Component:** `frontend/src/components/tools/StudentTools.js:FeeStatusViewer`

#### What it does
Shows the student their personal fee payment history and financial summary. Displays:
- Total Paid (green) and Outstanding Balance (red) summary cards
- A table of all fee transactions: fee type, amount, due date, paid/pending/overdue badge

#### How it works
- `GET /api/fees/my` — the backend scopes the query to the logged-in student's `student_id`. Returns both `data` (transaction list) and `summary` (aggregated totals).

#### Impacted areas
| Layer | Detail |
|-------|---------|
| **DB** | `fee_transactions` (filtered by `student_id`) |
| **Backend** | `backend/routes/fees.py` → `GET /api/fees/my` |

#### Roles that see this tool
`student` only

---

### 10. PTM Summary
**Tool ID:** `ptm-summary-viewer`  
**Component:** `frontend/src/components/tools/StudentTools.js:PtmSummaryViewer`

#### What it does
Allows the student to read the notes their teacher recorded about them in parent-teacher meetings. Each note card shows the PTM note text and the date it was recorded. Read-only.

#### How it works
- `GET /api/academics/ptm-notes` — the backend scopes results to the calling user's student_id (for students), returning only notes where `student_id` matches.

#### Impacted areas
| Layer | Detail |
|-------|---------|
| **DB** | `ptm_notes` collection (read-only, student-scoped) |
| **Backend** | `backend/routes/academics.py` → `GET /api/academics/ptm-notes` |

#### Roles that see this tool
`student` only (notes are authored by teachers; students read them here)

---

### 11. Forms
**Tool ID:** `form-submissions`  
**Component:** `frontend/src/components/tools/StudentTools.js:FormSubmissions` (also exported from TeacherTools.js via re-export)

#### What it does
Displays all active survey/school forms that are relevant to the student's role (`audience === 'all'` or `audience === 'students'`). The student selects a form, fills in its fields (text, number, email, date, textarea, select, radio types), and submits. A success confirmation is shown after submission.

#### How it works
- Load: `GET /api/settings/forms` — returns published forms.
- Filter client-side: only shows forms where `audience` matches `'all'`, `'students'`, or `'parents'`.
- Submit: `POST /api/settings/forms/:id/responses` with `{ answers: { fieldLabel: value } }`.

#### Impacted areas
| Layer | Detail |
|-------|---------|
| **DB** | `forms` collection (read), `form_responses` collection (write on submit) |
| **Backend** | `backend/routes/settings.py` → `GET /api/settings/forms`, `POST /api/settings/forms/:id/responses` |

#### Roles that see this tool
`student`, `teacher`

---

### 12. Raise Maintenance Request (Student)
**Tool ID:** `raise-maintenance`  
**Component:** `frontend/src/components/tools/MaintenanceTools.js:RaiseMaintenanceRequest`

#### What it does
Lets the student (and teacher) report a facility or tech issue. The user chooses:
- **Request type:** Facility (plumbing, electrical, civil, cleaning, security, carpentry, painting, pest control, HVAC, fire safety, landscaping) or Tech (hardware, software, network, printer, projector)
- **Description** and **Location**
- **Priority** (low/medium/high/urgent — facility only)
- Optionally attach photos (facility only)

After submission, the appropriate team is notified. The tool also shows the user's own open and resolved requests in a separate section.

#### How it works
- Load: `GET /api/issues/facility?limit=20` + `GET /api/issues/tech?limit=20` — filtered server-side to the requesting user's submissions.
- Create facility: `POST /api/issues/facility`
- Create tech: `POST /api/issues/tech`

#### Impacted areas
| Layer | Detail |
|-------|---------|
| **DB** | `facility_requests` or `tech_issues` collection |
| **Backend** | `backend/routes/issues.py` → `POST /api/issues/facility`, `POST /api/issues/tech` |
| **Notifications** | Maintenance team or IT team notified via `create_notification` |

#### Roles that see this tool
`student`, `teacher`, `admin_accountant`, `admin_transport_head`, `admin_receptionist`, `admin_it_tech`, `admin_maintenance`

---

## Student Tools — AI Chat

The AI assistant available to students in the chat sidebar has access to these backend tools:

| Tool name | What it does | DB collections |
|-----------|-------------|----------------|
| `get_my_attendance` | Student's own attendance for the last 30 days (rate, present/absent counts, 7-day history) | `students`, `student_attendance` |
| `get_my_fees` | Student's own fee transactions (type, amount, status, paid/due dates), total paid and total pending | `students`, `fee_transactions` |
| `get_my_results` | Student's own exam results enriched with subject and exam names | `students`, `exam_results`, `subjects`, `exams` |
| `get_student_profile` | Full profile for themselves: personal info, attendance stats, fees, guardian details | `students`, `student_attendance`, `fee_transactions`, `guardians` |
| `get_house_standings` | House points leaderboard with category breakdown (academics, sports, discipline, cultural) | `houses`, `house_points` |
| `get_house_details` | Details for a specific house: members, captains, recent awards | `houses`, `house_members`, `house_points` |
| `get_student_council` | Student council positions (head boy/girl, captains, prefects) | `student_council` |
| `get_library_status` | Library overview: total books, issued, overdue | `library_items`, `library_loans` |

> **Note:** Students cannot trigger any write operations through the AI chat. All write tools are gated to `owner` / `admin` / `teacher` roles at the TOOL_REGISTRY level (`backend/ai/tool_functions_v2.py`).

---

## Teacher Tools — Panel UI

### 1. Attendance (Class)
**Tool ID:** `class-attendance-marker`  
**Component:** `frontend/src/components/tools/TeacherTools.js:ClassAttendanceMarker`

#### What it does
The primary daily attendance tool for teachers. The teacher selects a class (pre-populated from their assigned classes) and a date. The tool loads the student roster with their current attendance status for that date. The teacher can:
- Click P/A/L buttons on individual rows to mark Present/Absent/Late
- Use "All Present" or "All Absent" bulk actions
- See live counters (present/absent/total) update as marks are made
- Click "Save Attendance" to persist all records in a single bulk API call

#### How it works
- Load classes: `GET /api/classes` (filtered to teacher's assignments).
- Load roster: `GET /api/attendance/student/today/:class_id?date=YYYY-MM-DD`.
- Save: `bulkMarkAttendance({ class_id, date, records })` → `POST /api/attendance/student/bulk`.

#### Impacted areas
| Layer | Detail |
|-------|---------|
| **DB** | `student_attendance` (upsert per student per date) |
| **Backend** | `backend/routes/attendance.py` → `GET /api/attendance/student/today/:class_id`, `POST /api/attendance/student/bulk` |
| **Audit** | Attendance writes go through `write_audit_doc` in `audit_service` |
| **Notifications** | Absent students may trigger SMS/notification (if attendance alerts are configured) |

#### Roles that see this tool
`teacher`

---

### 2. Assignments
**Tool ID:** `assignment-generator`  
**Component:** `frontend/src/components/tools/TeacherTools.js:AssignmentGenerator`

#### What it does
Full CRUD for homework assignments. The teacher can:
- **Create** an assignment: pick class + subject, set title, description/instructions, and due date
- **Edit** an existing assignment inline
- **Delete** an assignment (with confirmation dialog)

The assignment list shows all assignments the teacher has created, with class name and subject name resolved for display.

When a teacher creates an assignment, it immediately becomes visible to all students in that class via the [Homework Viewer](#3-homework--assignments) tool.

#### How it works
- List: `GET /api/academics/assignments` — backend filters to `teacher_id: user.id` for teachers.
- Create: `POST /api/academics/assignments`
- Edit: `PATCH /api/academics/assignments/:id`
- Delete: `DELETE /api/academics/assignments/:id`

#### Impacted areas
| Layer | Detail |
|-------|---------|
| **DB** | `assignments` collection |
| **Backend** | `backend/routes/academics.py` → all assignment routes |
| **Student impact** | Students in the target class see new/updated assignments in their Homework Viewer |
| **Audit** | Create/edit/delete calls go through audit logging |

#### Roles that see this tool
`teacher`

---

### 3. Question Papers
**Tool ID:** `question-paper-creator`  
**Component:** `frontend/src/components/tools/TeacherTools.js:QuestionPaperCreator`

#### What it does
AI-assisted question paper generation with a full in-browser editor and multi-format export. The teacher:
1. Fills a form: subject, paper title, chapters (comma-separated), total marks, difficulty mix (sliders for Easy/Medium/Hard %).
2. Clicks "Generate with AI" — the backend generates the paper content using Azure OpenAI.
3. The generated paper opens in a rich-text editor with a formatting toolbar (Bold, Underline, Bullet List, H2/H3/P, Undo/Redo).
4. The teacher can edit the paper, then save changes or export as:
   - **PDF** (via html2pdf.js — creates a temporary visible overlay, renders to A4)
   - **Word** (`.doc` using mhtml MIME type)
   - **HTML** (standalone HTML file)

Previously saved papers are listed and can be re-opened for editing.

#### How it works
- Generate: `POST /api/academics/question-papers/generate` — calls Azure OpenAI with a structured prompt, stores the generated content.
- List: `GET /api/academics/question-papers` — filtered to `teacher_id`.
- Get detail: `GET /api/academics/question-papers/:id`
- Save edits: `PATCH /api/academics/question-papers/:id` with `{ title, generated_content }`.
- Delete: `DELETE /api/academics/question-papers/:id`

#### Impacted areas
| Layer | Detail |
|-------|---------|
| **DB** | `question_papers` collection |
| **Backend** | `backend/routes/academics.py` → question-paper routes (lines 426–522) |
| **AI** | Azure OpenAI call to generate paper content |
| **Tokens** | Consumes AI token quota |
| **Exports** | Client-side only (PDF via html2pdf.js, Word via Blob, HTML via Blob) |

#### Roles that see this tool
`teacher`

---

### 4. Report Cards
**Tool ID:** `report-card-builder`  
**Component:** `frontend/src/components/tools/AdminTools.js:ReportCardBuilder`

> **Note:** Although this tool appears in the teacher tool set, the component loaded is from `AdminTools.js` because the layout routing checks the `ADMINS` array before `TEACHERS` (see `Layout.js:40,41`).

#### What it does
Allows viewing of exam results per exam for report card purposes. The teacher selects an exam from a dropdown, and the table shows all results for that exam: student name, subject name, marks obtained, max marks, and grade badge.

This is currently a **read-only view** — marks entry/bulk import happens through the admin-level results bulk route.

#### How it works
- Load exams: `GET /api/academics/exams`.
- Load results: `GET /api/academics/results?exam_id=<id>`.

#### Impacted areas
| Layer | Detail |
|-------|---------|
| **DB** | `exams`, `exam_results` (read-only) |
| **Backend** | `backend/routes/academics.py` → `GET /api/academics/exams`, `GET /api/academics/results` |

#### Roles that see this tool
`teacher`, `admin` (all sub-roles)

---

### 5. Student Performance (Admin view)
**Tool ID:** `student-performance-viewer`  
**Component:** `frontend/src/components/tools/AdminTools.js:StudentPerformanceViewer`

> **Note:** Like Report Cards, this loads the AdminTools version.

#### What it does
School-level performance overview showing all students. For each student: average marks across all exams, computed grade (A1/A2/B1/B2/C based on percentage), and number of exam entries. Stats header shows: total students, total exam entries, count above 80%, count below 60%.

Clicking a student opens a detailed view showing their individual subject results and attendance summary (present/absent/total/rate).

#### How it works
- Load: `GET /api/students` + `GET /api/academics/results`.
- Detail: `GET /api/academics/results?student_id=<id>` + `GET /api/attendance/student?student_id=<id>`.

#### Impacted areas
| Layer | Detail |
|-------|---------|
| **DB** | `students`, `exam_results`, `student_attendance` |
| **Backend** | `backend/routes/academics.py`, `backend/routes/attendance.py` |

#### Roles that see this tool
`teacher`, `admin` (all sub-roles)

---

### 6. Leave Application
**Tool ID:** `leave-application`  
**Component:** `frontend/src/components/tools/TeacherTools.js:LeaveApplication`

#### What it does
Lets the teacher apply for their own leave and view their personal leave history. The form includes:
- **Leave type:** casual / medical / earned / maternity / paternity / unpaid
- **Start date** and **End date**
- **Reason** (required)

Leave history table shows all past applications with type, dates, status badge (pending/approved/rejected/cancelled), and reason snippet.

#### How it works
- Load history: `GET /api/staff/leaves/my` — returns only the calling teacher's leave records.
- Submit: `POST /api/ops/leaves` with `{ leave_type, start_date, end_date, reason }`.
- Approval is handled by the owner/principal via `PATCH /api/staff/leaves/:id` (not available to teachers).

#### Impacted areas
| Layer | Detail |
|-------|---------|
| **DB** | `staff_leaves` collection |
| **Backend** | `backend/routes/staff.py` → `GET /api/staff/leaves/my`; `backend/routes/operations.py` → `POST /api/ops/leaves` |
| **Notifications** | Leave submission may notify the principal |
| **Approval gate** | Only owner or admin+principal can approve (`require_owner_or_principal`) |

#### Roles that see this tool
`teacher`

---

### 7. Lesson Plans
**Tool ID:** `lesson-plan-generator`  
**Component:** `frontend/src/components/tools/TeacherTools.js:LessonPlanGenerator`

#### What it does
Full CRUD for weekly lesson plans. The teacher creates a lesson plan entry specifying:
- Class and section
- Subject
- Week date (the Monday anchor for that week)
- Chapter / Topic name (required)
- Lesson notes / content (free-text description, objectives, activities)

The list view shows all plans with chapter, subject, class, and week date. Plans can be edited or deleted.

#### How it works
- List: `GET /api/academics/lesson-plans` — backend filters to the calling teacher's `staff_id` / `user_id`.
- Create: `POST /api/academics/lesson-plans` — body wraps `content` into `{ description, topics: [], objectives: [] }`.
- Edit: `PATCH /api/academics/lesson-plans/:id`.
- Delete: `DELETE /api/academics/lesson-plans/:id`.
- A separate review endpoint exists: `PATCH /api/academics/lesson-plans/:id/review` (used by principals).

#### Impacted areas
| Layer | Detail |
|-------|---------|
| **DB** | `lesson_plans` collection |
| **Backend** | `backend/routes/academics.py` → lesson-plan routes (lines 274–426) |
| **Principal view** | Lesson completion tracked via `GET /api/academics/lesson-plan-completion` (visible to admins) |

#### Roles that see this tool
`teacher`

---

### 8. Worksheets
**Tool ID:** `worksheet-creator`  
**Component:** `frontend/src/components/tools/TeacherTools.js:WorksheetCreator`

#### What it does
Full CRUD for practice/revision worksheets. The teacher specifies:
- **Subject**
- **Type:** practice / revision / homework
- **Topic** (chapter name or topic — required)
- **Content / Questions** (free-text — the actual worksheet questions or instructions)

Worksheets are stored per-teacher and displayed in a table with topic, subject, type, and creation date.

#### How it works
- List: `GET /api/academics/worksheets`.
- Create: `POST /api/academics/worksheets`.
- Edit: `PATCH /api/academics/worksheets/:id`.
- Delete: `DELETE /api/academics/worksheets/:id`.

#### Impacted areas
| Layer | Detail |
|-------|---------|
| **DB** | `worksheets` collection |
| **Backend** | `backend/routes/academics.py` → worksheet routes (lines 745–808) |

#### Roles that see this tool
`teacher`

---

### 9. Class Analytics
**Tool ID:** `class-performance-analytics`  
**Component:** `frontend/src/components/tools/TeacherTools.js:ClassPerformanceAnalytics`

#### What it does
Analytics dashboard scoped to a single class. The teacher picks a class from a dropdown. The tool then loads:
- **Stats header:** students enrolled, result entries count, average marks (as X/100), count of students scoring ≥80%.
- **Results table** if results exist: student name, subject, marks, grade badge.
- **Student list** if no results: student name, roll number, "No Results" badge.

#### How it works
- Load classes: `GET /api/classes` (teacher-scoped).
- On class select: parallel calls to `GET /api/students?class_id=<id>` + `GET /api/academics/results?class_id=<id>`.

#### Impacted areas
| Layer | Detail |
|-------|---------|
| **DB** | `classes`, `students`, `exam_results` |
| **Backend** | `backend/routes/students.py`, `backend/routes/academics.py` |

#### Roles that see this tool
`teacher`

---

### 10. Substitutions
**Tool ID:** `substitution-viewer`  
**Component:** `frontend/src/components/tools/TeacherTools.js:SubstitutionViewer`

#### What it does
Shows the teacher their substitution assignments — periods they have been assigned to cover for an absent colleague. Displays: date, period number, original teacher name, class, and subject.

If there are no substitution assignments, a "No substitution assignments for today" message is shown.

#### How it works
- `GET /api/academics/substitutions?user_id=<userId>` — returns substitution entries where `substitute_teacher_id` matches the calling user's staff record.

#### Impacted areas
| Layer | Detail |
|-------|---------|
| **DB** | `substitutions` or `timetable_substitutions` collection |
| **Backend** | `backend/routes/academics.py` → `GET /api/academics/substitutions` (lines 809–886) |
| **Creation** | Substitutions are created by the principal via the AI chat (`tool_initiate_substitution`) or `POST /api/academics/substitutions` |

#### Roles that see this tool
`teacher`

---

### 11. PTM Notes
**Tool ID:** `ptm-notes`  
**Component:** `frontend/src/components/tools/TeacherTools.js:PtmNotes`

#### What it does
Full CRUD for parent-teacher meeting notes. The teacher selects a class, then picks a student from that class, and writes notes about the meeting. Notes are time-stamped and shown in a table with student name, truncated note, and date.

Notes written here become visible to the corresponding student in their [PTM Summary](#10-ptm-summary) tool.

#### How it works
- List: `GET /api/academics/ptm-notes` — backend scopes to `teacher_id` for teachers.
- Create: `POST /api/academics/ptm-notes` with `{ student_id, notes }`.
- Edit: `PATCH /api/academics/ptm-notes/:id`.
- Delete: `DELETE /api/academics/ptm-notes/:id`.

#### Impacted areas
| Layer | Detail |
|-------|---------|
| **DB** | `ptm_notes` collection |
| **Backend** | `backend/routes/academics.py` → PTM notes routes (lines 673–744) |
| **Student impact** | Students can read their own notes via PTM Summary tool |

#### Roles that see this tool
`teacher`

---

### 12. Curriculum Tracker
**Tool ID:** `curriculum-tracker`  
**Component:** `frontend/src/components/tools/TeacherTools.js:CurriculumTracker`

#### What it does
Syllabus coverage tracker. The teacher adds topics/chapters per class and subject, and marks each with a status:
- `not_started` (gray)
- `in_progress` (yellow)
- `completed` (green)
- `revised` (blue)

The full table shows topic, class, subject, status badge, and last updated date.

#### How it works
- List: `GET /api/academics/curriculum`.
- Create: `POST /api/academics/curriculum` with `{ class_id, subject_id, topic, status }`.
- Edit: `PATCH /api/academics/curriculum/:id`.
- Delete: `DELETE /api/academics/curriculum/:id`.

#### Impacted areas
| Layer | Detail |
|-------|---------|
| **DB** | `curriculum_progress` (or similar) collection |
| **Backend** | `backend/routes/academics.py` → curriculum routes (lines 907–954) |
| **Admin visibility** | Principals/admin can view lesson plan completion via `GET /api/academics/lesson-plan-completion` |

#### Roles that see this tool
`teacher`

---

### 13. Forms (Teacher)
**Tool ID:** `form-submissions`  
**Component:** Same `FormSubmissions` component re-exported from `StudentTools.js`

#### What it does
Identical behaviour to the student Forms tool but filters for forms with `audience === 'all'` or `audience === 'teachers'`. Teachers fill in and submit school-issued surveys, feedback forms, or event sign-ups.

#### Roles that see this tool
`teacher`, `student`

---

### 14. Raise Maintenance Request (Teacher)
**Tool ID:** `raise-maintenance`  
**Component:** `frontend/src/components/tools/MaintenanceTools.js:RaiseMaintenanceRequest`

Same component as the [student version](#12-raise-maintenance-request-student). Teachers can report facility and tech issues, and view their own submitted requests.

#### Roles that see this tool
`teacher`, `student`, and several admin sub-roles

---

## Teacher Tools — AI Chat

The AI assistant available to teachers in the chat sidebar has access to these backend tools:

| Tool name | Scope | What it does | DB collections |
|-----------|-------|-------------|----------------|
| `get_attendance_overview` | teacher-scoped | Attendance trends over N days. Teachers see only their assigned classes. | `student_attendance`, `classes` |
| `get_class_wise_attendance` | teacher-scoped | Per-class attendance summary for a date range. Teachers see own class only. | `student_attendance`, `classes` |
| `search_students` | teacher-scoped | Search students by name or admission number. Teachers see only students in their assigned classes. | `students`, `classes` |
| `get_student_database` | teacher-scoped | Full student list with filters. Teachers see own classes only. | `students`, `classes` |
| `get_class_list` | read | All classes with section, class teacher name, and student count. | `classes`, `staff` |
| `get_today_class_attendance` | teacher-scoped | Today's attendance for a class with present/absent/unmarked lists. | `student_attendance`, `students` |
| `get_student_profile` | teacher-scoped | Full profile for a named student: personal info, attendance, fees, guardian. | `students`, `student_attendance`, `fee_transactions`, `guardians` |
| `get_my_class_students` | teacher-only | Students in the teacher's assigned classes. Auto-scoped, no parameters needed. | `staff`, `classes`, `students` |
| `get_house_standings` | read | House points leaderboard. | `houses`, `house_points` |
| `get_house_details` | read | Details of a specific house. | `houses`, `house_members` |
| `award_house_points` | **write** | Award house points to a student. Requires confirmation. Creates audit entry. | `house_points`, `students` |
| `get_student_council` | read | Student council positions. | `student_council` |
| `get_library_status` | read | Library overview: books, issued, overdue. | `library_items`, `library_loans` |
| `get_upcoming_events` | read | Upcoming exams, events, and announcements in the next N days. | `exams`, `activities`, `announcements` |
| `get_timetable` | read | Full timetable for a class with teacher names. | `timetable_slots`, `staff`, `classes` |
| `get_exam_results_summary` | teacher-scoped | Exam results summary for a class and exam. | `exam_results`, `students`, `subjects` |
| `draft_parent_message` | read | Draft a contextual parent-facing message for a student (returns draft text, does not send). | `students`, `classes`, `fee_transactions`, `student_attendance` |
| `create_announcement` | **write** | Create a school announcement. Requires confirmation. | `announcements` |
| `get_upcoming_events` | read | Upcoming exams and school events in a date window. | `exams`, `activities` |

> **Write gate:** Teacher write tools (`award_house_points`, `create_announcement`) go through the `ai_action_policy.py` Phase-1 lockdown check and require explicit user confirmation before executing. They also create audit log entries.

---

## Role vs. Tool Access Matrix

### Panel Tool Dashboard

| Tool ID | Student | Teacher |
|---------|---------|---------|
| `ai-tutor` | ✅ | — |
| `doubt-solver` | ✅ | — |
| `homework-viewer` | ✅ | — |
| `attendance-self-check` | ✅ | — |
| `result-viewer` | ✅ | — |
| `practice-test` | ✅ | — |
| `study-planner` | ✅ | — |
| `career-guidance` | ✅ | — |
| `fee-status-viewer` | ✅ | — |
| `ptm-summary-viewer` | ✅ | — |
| `form-submissions` | ✅ | ✅ |
| `raise-maintenance` | ✅ | ✅ |
| `class-attendance-marker` | — | ✅ |
| `assignment-generator` | — | ✅ |
| `question-paper-creator` | — | ✅ |
| `report-card-builder` | — | ✅ (AdminTools component) |
| `student-performance-viewer` | — | ✅ (AdminTools component) |
| `leave-application` | — | ✅ |
| `lesson-plan-generator` | — | ✅ |
| `worksheet-creator` | — | ✅ |
| `class-performance-analytics` | — | ✅ |
| `substitution-viewer` | — | ✅ |
| `ptm-notes` | — | ✅ |
| `curriculum-tracker` | — | ✅ |

### AI Chat Tool Registry

| AI Tool | Student | Teacher | Owner | Admin |
|---------|---------|---------|-------|-------|
| `get_my_attendance` | ✅ | — | — | — |
| `get_my_fees` | ✅ | — | — | — |
| `get_my_results` | ✅ | — | — | — |
| `get_student_profile` | ✅ | ✅ | ✅ | ✅ |
| `get_house_standings` | ✅ | ✅ | ✅ | ✅ |
| `get_house_details` | ✅ | ✅ | ✅ | ✅ |
| `get_student_council` | ✅ | ✅ | ✅ | ✅ |
| `get_library_status` | ✅ | ✅ | ✅ | ✅ |
| `get_attendance_overview` | — | ✅ | ✅ | ✅ |
| `search_students` | — | ✅ | ✅ | ✅ |
| `get_student_database` | — | ✅ | ✅ | ✅ |
| `get_class_list` | — | ✅ | ✅ | ✅ |
| `get_today_class_attendance` | — | ✅ | ✅ | ✅ |
| `get_class_wise_attendance` | — | ✅ | ✅ | ✅ |
| `get_my_class_students` | — | ✅ | — | — |
| `award_house_points` | — | ✅ | ✅ | ✅ |
| `get_timetable` | — | ✅ | ✅ | ✅ |
| `get_exam_results_summary` | — | ✅ | ✅ | ✅ |
| `draft_parent_message` | — | ✅ | ✅ | ✅ |
| `create_announcement` | — | ✅ | ✅ | ✅ |
| `get_upcoming_events` | — | ✅ | ✅ | ✅ |

---

## Shared Tool Details

### Forms (`form-submissions`)
**Used by:** student, teacher

The `FormSubmissions` component is defined in `StudentTools.js` and re-exported from `TeacherTools.js` (`export { FormSubmissions } from './StudentTools'`). The audience filter is purely client-side. Both roles go through the same backend endpoints:

- `GET /api/settings/forms` — list active forms
- `POST /api/settings/forms/:id/responses` — submit a response

Field types supported: `text`, `number`, `email`, `date`, `textarea`, `select`, `radio`.

---

### Raise Maintenance Request (`raise-maintenance`)
**Used by:** student, teacher, admin_accountant, admin_transport_head, admin_receptionist, admin_it_tech, admin_maintenance

Single component `RaiseMaintenanceRequest` handles both facility and tech issue submission. The request type dropdown (facility vs. tech) controls which API endpoint and category options are shown.

Backend routes:
- Facility: `GET/POST /api/issues/facility`
- Tech: `GET/POST /api/issues/tech`

Both endpoints in `backend/routes/issues.py` are open to any authenticated user for creation. The maintenance team (admin_maintenance) and IT team (admin_it_tech) have separate tools (`facility-requests`, `tech-issues`) to manage and resolve submitted requests.

---

### PTM Notes vs. PTM Summary (cross-role pair)
| Role | Tool | Can do |
|------|------|--------|
| Teacher | `ptm-notes` (`PtmNotes`) | Create, edit, delete notes about any student in their classes |
| Student | `ptm-summary-viewer` (`PtmSummaryViewer`) | Read-only view of notes written about themselves |

Both hit `GET /api/academics/ptm-notes`. The backend scopes the result: teachers see all notes they authored; students see only notes where `student_id` matches their own record.

---

### Homework Assignment cross-role pair
| Role | Tool | Can do |
|------|------|--------|
| Teacher | `assignment-generator` (`AssignmentGenerator`) | Create, edit, delete assignments for a class |
| Student | `homework-viewer` (`HomeworkViewer`) | Read-only view of assignments for their enrolled class |

Both hit `GET /api/academics/assignments`. The backend scopes: teacher queries filter by `teacher_id`; student queries filter by the student's `class_id`.

---

*End of document.*
