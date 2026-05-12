# EduFlow Platform Audit & Sprint Plan
**BMAD Code Review — Full Codebase Audit**  
Date: 2026-05-12 | Auditor: Claude (BMAD Code Review Skill)  
Requested by: Abhimanyu

---

## EXECUTIVE SUMMARY

Platform scored **5.8/10** before Phase 1–5 work. After Phases 1–5 completion, estimated **7.2/10**.  
Target: **9.0/10** enterprise-grade. Gap areas identified across 6 dimensions.

---

## AUDIT FINDINGS

### 🔴 CRITICAL (P0) — Broken User Experience

| ID | Finding | Location | Impact |
|----|---------|----------|--------|
| C-01 | Azure OpenAI 400 (content filter) shows raw JSON error in chat bubble | `ChatInterface.js:351` + `llm_client.py` | Users see cryptic error when asking about "complaints", "fee defaulters" etc. |
| C-02 | AI silent response — no text shown after tool execution | `ChatInterface.js:351` ai_unavailable handler | `currentStreamMsg` is null when event arrives, so message never renders |
| C-03 | Duplicate "Staff Tracker" in Owner sidebar | `Sidebar.js:23-24` | Two identical-named entries confuse navigation |
| C-04 | "Student Strength" and "Student Database" are redundant separate tabs | `Sidebar.js:19-20` | Duplicated data; 2 clicks where 1 suffices |
| C-05 | Principal profile has only 14 tools (missing fee defaulters, complaints, staff performance, smart alerts, transport) | `Sidebar.js:110` | Adesh can't do his job from the platform |

### 🟠 HIGH (P1) — Functional Gaps

| ID | Finding | Location | Impact |
|----|---------|----------|--------|
| H-01 | No file upload in AI chat — blocks document workflows | `InputBar.js`, `chat.py` | Can't share .pdf, .xlsx, images with AI |
| H-02 | Student profile missing: height, weight, photo, parents' photos, siblings, blood group, medical notes | `StudentDatabase.js`, `students` route | Incomplete profile for school use |
| H-03 | School activities entirely missing from frontend: sports teams, houses, positions (head boy/girl, prefects, monitors) | Frontend tools | Core school identity features absent |
| H-04 | Azure content filter blocks legitimate school queries ("parent complaints", "fee defaulters") — no graceful fallback | `llm_client.py` | Owner/Principal can't ask routine questions |
| H-05 | AI keyword map missing "parent complaint", "parent grievance" → `get_incident_complaint_visitor` | `chat.py:KEYWORD_TOOL_MAP` | Queries silently fail |

### 🟡 MEDIUM (P2) — Quality & Polish

| ID | Finding | Location | Impact |
|----|---------|----------|--------|
| M-01 | UI scored 4-5/10 vs ChatGPT's 10/10 (dark theme but sparse, no visual hierarchy) | All frontend components | Professional impression suffers |
| M-02 | AI system prompt doesn't know about Adesh's morning routine / Principal's daily workflow | `ai/prompts.py` | AI gives generic answers instead of contextual ones |
| M-03 | Staff Attendance Tracker listed as "Staff Tracker" — same name as Staff Tracker (profiles) | `Sidebar.js:24` | Already a C-03 fix, noting here too |
| M-04 | `tool_get_student_database` has N+1 query (class lookup per student in a loop) | `tool_functions_v2.py:~125` | Slow for 500+ students |
| M-05 | `to_list(500)` hardcoded in student database without pagination | `tool_functions_v2.py` | Won't scale beyond ~500 students |
| M-06 | Houses migration exists (`002_add_houses.py`) but no frontend UI surfaced | `migrations/` | Dead migration code |
| M-07 | Content filter (student role) overly aggressive — blocks "hacking" in cybersecurity context | `content_filter.py` | Legitimate curriculum blocked |

### 🟢 LOW (P3) — Technical Debt

| ID | Finding | Location | Impact |
|----|---------|----------|--------|
| L-01 | `tool_functions.py` (old) still imported in `tool_functions_v2.py` — legacy duplication | `tool_functions_v2.py:1-22` | Maintenance confusion |
| L-02 | `_call()` is sync, runs in `asyncio.to_thread` — correct but comments missing | `llm_client.py` | Future devs may break async contract |
| L-03 | `asyncio.create_task(_llm_call())` without exception handler — task failure undetectable | `chat.py:~910` | Silent failures hard to debug |
| L-04 | `print()` statements in production LLM paths (`llm_client.py:43,50`) | `llm_client.py` | Violates code quality rules |
| L-05 | `ADMIN_SUBCATEGORY_TOOLS` and `TOOLS_BY_ROLE.admin` can diverge silently | `Sidebar.js` | Tools shown to wrong roles |

---

## AGILE SPRINT PLAN

### Sprint 8-A: Critical Bug Fixes (Today)
**Goal: Zero broken UX. Target: 8.0/10**

| Story | Title | Effort |
|-------|-------|--------|
| 8A-01 | Fix duplicate Staff Tracker → rename to "Staff Attendance" | XS |
| 8A-02 | Merge Student Strength into Student Database (strength tab + stats) | S |
| 8A-03 | Expand Principal tools from 14 → 20 (add fee defaulters, complaints, staff performance, smart alerts, financial overview, transport) | S |
| 8A-04 | Fix AI silent/blank response — ai_unavailable event must render even with no prior text_delta | XS |
| 8A-05 | Fix Azure content filter errors — graceful degradation with canned helpful response | S |
| 8A-06 | Remove print() from llm_client.py — use logger | XS |
| 8A-07 | Add "parent complaint" keywords to AI keyword map | XS |

### Sprint 8-B: AI File Upload (Week 1)
**Goal: AI can read files. Target: 8.3/10**

| Story | Title | Effort |
|-------|-------|--------|
| 8B-01 | Backend: `/api/chat/upload` multipart endpoint — accept file, extract text (pdf/docx/xlsx/txt/md/html/pptx/png/jpg/heic/mp3/mp4/zip) | M |
| 8B-02 | Frontend: File attachment button in InputBar — clip icon, file picker, preview strip | M |
| 8B-03 | AI context: attach extracted file content to user message sent to LLM | S |
| 8B-04 | Zip extraction: unzip, read text files inside, summarise directory structure | S |

### Sprint 8-C: Student Profile Enhancement (Week 1-2)
**Goal: Complete student record. Target: 8.5/10**

| Story | Title | Effort |
|-------|-------|--------|
| 8C-01 | Extend student model: height, weight, blood_group, medical_notes, emergency_contact, siblings_in_school | S |
| 8C-02 | Parents data: mother_name, mother_phone, mother_occupation, mother_photo, father_name, father_phone, father_occupation, father_photo, annual_income | S |
| 8C-03 | Frontend: multi-section student profile modal (Personal, Parents, Medical, Academic, Activities) | M |
| 8C-04 | Student photo upload + parent photo upload (S3) | S |

### Sprint 8-D: School Activities System (Week 2)
**Goal: School identity & extra-curricular fully tracked. Target: 8.7/10**

| Story | Title | Effort |
|-------|-------|--------|
| 8D-01 | Backend: `student_positions` collection — head boy/girl, prefects, class monitors, sports captains | S |
| 8D-02 | Backend: `sports_teams` — cricket, football, chess, debate, etc. with roster and fixtures | S |
| 8D-03 | Backend: Houses system (Blue/Sapphire, Green/Emerald, Red/Ruby, Yellow/Gold) — points, members, events | S |
| 8D-04 | Frontend: School Activities hub — Houses leaderboard, Sports teams, Positions panel | M |
| 8D-05 | AI tools: get_sports_teams, get_student_positions, house-related queries | S |

### Sprint 8-E: UI Overhaul (Week 2-3)
**Goal: UI 4-5/10 → 8.5/10. ChatGPT-grade polish.**

| Story | Title | Effort |
|-------|-------|--------|
| 8E-01 | Chat interface redesign: message bubbles, avatar system, markdown rendering, code blocks, tables | L |
| 8E-02 | Sidebar redesign: search, grouping, better tool cards, smooth animations | M |
| 8E-03 | Tool panels: consistent card design, loading skeletons, empty states, error states | L |
| 8E-04 | Global: typography scale, spacing system, micro-animations, focus states | M |
| 8E-05 | InputBar: file attachment, slash commands polish, send button animation | M |

### Sprint 8-F: Principal Morning Workflow & AI Intelligence (Week 3)
**Goal: Adesh's first 30 mins fully AI-assisted. Target: 9.0/10**

| Story | Title | Effort |
|-------|-------|--------|
| 8F-01 | Principal Daily Brief: C-class duty check, transport first trip, urgent issues, bell timing changes, round checklist | M |
| 8F-02 | AI system prompt: Principal context — morning workflow, round checklist, timetable awareness | S |
| 8F-03 | Bell/timetable modification flow: AI-assisted bell change request → confirm action → SMS notify | M |
| 8F-04 | Parent complaints AI tool: list open complaints with category, severity, action status | S |

---

## SCORING MATRIX

| Dimension | Before | After Sprint 8-A | After All Sprints |
|-----------|--------|-----------------|-------------------|
| Architecture | 8.5/10 | 8.5/10 | 9.0/10 |
| AI Layer | 5.0/10 | 7.5/10 | 9.0/10 |
| Frontend UI | 4.5/10 | 5.5/10 | 8.5/10 |
| Feature Completeness | 6.5/10 | 7.5/10 | 9.0/10 |
| Security | 8.0/10 | 8.5/10 | 9.0/10 |
| Data Model | 7.0/10 | 7.5/10 | 9.0/10 |
| **OVERALL** | **5.8/10** | **7.5/10** | **9.0/10** |

---

*Generated by BMAD Code Review — implementing Sprint 8-A immediately.*
