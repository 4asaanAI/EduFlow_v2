# EduFlow — PRD v1.3.0
**Last Updated:** April 2026 | School: The Aaryans, CBSE, Lucknow, UP

## Architecture
- Frontend: React + Tailwind + shadcn/ui, dark/light theme
- Backend: FastAPI (Python)
- Database: MongoDB (motor/async)
- LLM: OpenAI GPT-4o (Emergent key) + Gemini 2.5 Flash fallback
- URL: https://classroom-ai-hub-4.preview.emergentagent.com

## School Org Context (The Aaryans)
Head (Aman/Owner) → Principal (Adeen Sir) → 4 Depts:
1. Accounts
2. Admin (Medical, Reception, Admission, Day-to-Day: Peon/Aaya/Sweeper/Guard/Gardner)
3. Transport (Head + 4-5 Drivers + Conductors)  
4. Teachers: KG (Nursery/LKG/UKG: Incharge→Class Teacher) | 1-12: HOD→Coordinators(4-5,6-8,9-12)→Teachers/Class Teachers | Subjects: Eng/Hindi/Maths/Science/SSt/Sports/Music/Arts/Library/Computers

## Session 3 (Comprehensive Iteration)

### P0 Fixes
- Theme fix: ChatInterface, InputBar, MessageRenderer all use isDark from useTheme() — no more hardcoded dark colors. HTML-generated markdown uses theme-aware colors.
- Search results clickable: tools → open-tool event, students → student-database, staff → staff-tracker, announcements → announcement-broadcaster
- Notifications clickable: each notification routes to relevant tool
- Slash `/` and `@` work mid-sentence anywhere in input, not just at start
- Slash shows ALL role-specific tools in scrollable list with keyboard nav
- @ mentions enriched with sub_role (class name for students, dept/subject for staff)
- Backend: slash-prefixed keywords added to KEYWORD_TOOL_MAP (e.g. /school-pulse, /fee-collection, etc.)
- Data persistence: settings save to DB, study planner saves to DB

### P1 Features
- Daily Brief: typing "daily brief" / "morning summary" / "aaj ka haal" triggers comprehensive summary
- All ComingSoon tools replaced: CustomReportBuilder (CSV download links), BoardReport (real metrics), WorksheetCreator (save/load), SubstitutionViewer, PracticeTest (AI-generated MCQ quiz), CareerGuidance (LLM with student context), PayrollPreparer (owner-only), CustomFormBuilder (create+save), AutomatedReport (schedule config)
- File Upload: POST /api/uploads with drag-drop, preview, delete, role-based type restrictions (students: pdf/images only)
- Export: CSV exports for students, fees, attendance, staff, expenses, enquiries, exam results via /api/export/*
- Timetable: seeded with Class 9-A data (15 slots Mon-Wed)
- School org context injected into every AI prompt
- Rename "AI Health Report" → "Health Report"
- Settings notifications save to MongoDB with Save button
- Custom forms backend: GET/POST /api/settings/forms

### P2 Items
- Emergent watermark hidden via CSS
- Mobile search bar: search button triggers panel (desktop shows inline bar)
- Backend routes: /api/search (enriched with sub_role), /api/notifications (role-scoped), /api/exports/*, /api/uploads, /api/academics/worksheets

## What Still Needs Building
### Next Session P0
- Light theme: ToolPage.js (tool panels) still has hardcoded dark colors — needs useTheme integration
- WhatsApp/Twilio integration
- Token usage API (MongoDB collection, count per user/month)

### P1
- CRUD: Edit/Delete buttons on all tools (currently Create+Read only for most)
- School Pulse threshold: slider value save to school_settings + flag classes below threshold
- Better timetable UI: multi-class view, conflict detection
- Reports: charts with recharts (attendance trend line, fee bar chart)
- Profile modal: wire to token_usage MongoDB collection

### P2
- JWT phone OTP authentication
- Student/Admin transfer workflow
- ID card generator (HTML print template)
- Parent message composer (WhatsApp queue)

## Environment Variables
MONGO_URL, DB_NAME, CORS_ORIGINS (protected)
EMERGENT_LLM_KEY=sk-emergent-cF2E90dFaB30fBe29B
LLM_PROVIDER=openai, LLM_MODEL=gpt-4o
LLM_FALLBACK_PROVIDER=gemini, LLM_FALLBACK_MODEL=gemini-2.5-flash
SCHOOL_NAME=The Aaryans, SCHOOL_BOARD=CBSE, SCHOOL_CITY=Lucknow, SCHOOL_STATE=Uttar Pradesh
