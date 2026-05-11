---
stepsCompleted:
  - step-01-init
  - step-02-discovery
  - step-02b-vision
  - step-02c-executive-summary
  - step-03-success
  - step-04-journeys
  - step-05-domain
  - step-06-innovation
  - step-07-project-type
  - step-08-scoping
  - step-09-functional
  - step-10-nonfunctional
  - step-11-polish
  - step-12-complete
  - step-e-01-discovery
  - step-e-02-review
  - step-e-03-edit
releaseMode: phased
status: complete
completedAt: '2026-05-11'
lastEdited: '2026-05-12'
editHistory:
  - date: '2026-05-12'
    changes: 'Post-validation edit: added 4 admin user journeys, formalized discount engine FRs, DPDP/CBSE pseudonymization fix, Success Criteria referee + use-event definitions, 30+ targeted FR/NFR measurability and leakage fixes'
inputDocuments:
  - 'memory/PRD.md'
  - 'EDUFLOW_BUILD_PLAN.md'
  - 'DEPLOYMENT_READINESS.md'
  - '_bmad-output/project-context.md'
workflowType: 'prd'
classification:
  projectType: 'Multi-role SaaS Web App'
  domain: 'EdTech / School Management'
  complexity: 'high'
  projectContext: 'brownfield'
  scopeConstraint: 'quality-upgrade-only'
---

# Product Requirements Document — EduFlow Enterprise Upgrade

**Author:** Abhimanyu  
**Date:** 2026-05-11

---

## Executive Summary

EduFlow is a chat-first school management platform built for The Aaryans (Aman), a multi-branch CBSE school group in Uttar Pradesh. The platform gives school owners, principals, teachers, and students a single conversational interface to manage attendance, fees, staff, academics, and AI-assisted learning — replacing fragmented tools and WhatsApp workflows with one integrated system.

This PRD defines an **enterprise quality upgrade** of the existing platform. The scope is strictly contained to: hardening what exists, eliminating the gap between demo quality and daily operational trust, and making EduFlow the kind of system a principal stakes their morning on. **No net-new features are in scope**, with one documented exception: the Maintenance Admin profile, which is a new build required to complete the admin profile set committed to the client. All other scope is hardening and quality upgrade of existing functionality. Feature additions beyond this exception will be addressed in a subsequent PRD once this foundation is solid.

### What Makes This Special

EduFlow's differentiator is **conversational depth** — the AI doesn't just answer questions, it executes school operations (mark attendance, collect fees, approve leaves) through natural language, with a deterministic rule engine validating every write action before it executes. Most school management software is form-based and passive; EduFlow is intent-driven and active.

The upgrade target is the gap between *functional* and *trustworthy*: complete CRUD where only Create+Read exists today, consistent UX states (loading, empty, error) everywhere, theme coherence across all tool panels, S3-backed file storage replacing ephemeral disk, structured observability, and a test baseline that prevents regressions.

### Project Classification

| Dimension | Value |
|---|---|
| **Project Type** | Multi-role SaaS Web App |
| **Domain** | EdTech / School Management (India, CBSE) |
| **Complexity** | High — multi-tenant, AI-integrated, role-hierarchy, real-time SSE streaming |
| **Project Context** | Brownfield — live system, active client, partially deployed on AWS Amplify |
| **Client** | The Aaryans / Aman (owner) — single school, CBSE, Uttar Pradesh |
| **Scope** | Enterprise quality upgrade only — no net-new features |

---

## Success Criteria

### User Success

**Go-live target (Phase 1):** Owner (Aman) and all Admin profiles — Principal (Adesh), Accountant, Transport Head, Receptionist, IT/Tech, Maintenance. Teachers and students are intentionally deferred to Phase 2; they will be brought onto the live platform only after Owner and Admin profiles have validated it in daily use.

**Full school database loaded from day one.** Even though teachers and students don't log in yet, all their records — student profiles, attendance history, fee records, staff data, class information — are fully imported and visible to Owner and Admin profiles. Aman and Adesh have complete visibility of the entire school database from the moment they go live.

**Success is reached when:**

- Aman can answer any operational question about his school — fee status, today's attendance, a staff member's leave record, a parent meeting he logged last week — using EduFlow alone, without touching a paper register or calling anyone
- Adesh can track, approve, and act on daily operations (leave requests, substitutions, exam schedules, announcements) entirely within the platform
- Every Admin profile type performs their primary workflow in EduFlow without paper backup:
  - **Accountant**: fee collection, fee status lookup, expense logging
  - **Receptionist**: visitor and enquiry logging, announcements
  - **Transport Head**: route and vehicle assignment, transport roster lookup
  - **IT/Tech**: tech request logging and status tracking
  - **Maintenance**: facility request logging and status tracking (separate profile — new build in this upgrade)
- The platform replaces the hand-written diary: every meeting, follow-up, and decision is logged and retrievable conversationally
- When Phase 2 begins, teacher and student logins work correctly for all existing tools — the database is already there, only access is being unlocked

**Measurable user targets:**
- Owner and Principal each use the platform at least once per day within 2 weeks of go-live — a qualifying use event is defined as: ≥1 AI query that returns a live data result OR ≥1 tool-panel write operation logged per session
- At the 4-week mark: a structured walkthrough where Aman and Adesh answer 10 operational questions they themselves choose — using EduFlow alone, with no fallback to paper or WhatsApp. A satisfactory answer requires EduFlow to return the correct data without manual supplementation. Aman's explicit sign-off, facilitated by Abhimanyu, declares the walkthrough passed — the operator does not call this gate unilaterally.
- All Admin profiles performing their primary workflows without paper backup within 30 days of deployment

**Pilot failure condition (what "not clean" looks like):**
- Any fee or attendance record is wrong and requires manual correction outside the platform
- Aman or Adesh reverts to paper/WhatsApp for a workflow the platform is supposed to cover
- A support issue goes unresolved for more than 48 hours
- Any of the above resets the 4-week clean-run clock

---

### Business Success

| Metric | Value |
|---|---|
| **Current ARR** | ₹0 — The Aaryans is the development pilot; post-pilot conversion to a paying plan is the first revenue event |
| **Pilot gate** | 4 consecutive clean weeks (see failure condition above) before pitching school #2 |
| **Year 1** | ₹8–12L ARR — 2–3 paying school clients (includes The Aaryans converting post-pilot) |
| **Year 2** | ₹30–40L ARR — 10+ paying school clients |
| **Gross margin target** | ≥65% — requires AI inference costs (Azure OpenAI), S3 storage, and SMS/WhatsApp costs to be tracked from day one |
| **Net margin target** | ≥30% |
| **Retention signal** | The Aaryans still actively using the platform at month 3 post-go-live — defined as ≥1 qualifying use event per week across Owner and Admin profiles (see user success definition above); not just signed up, actively using |
| **Provisional pricing** | ₹25–33K per school per month — unvalidated planning anchor implied by Year 1 ARR targets; to be pressure-tested before first external sales pitch |

**Note on business metrics:** Year 1 and Year 2 targets are planning anchors based on founder judgment, not yet validated against comparable products in the Indian school management market (Teachmint, MyClassCampus, etc.). These should be pressure-tested before the first external sales pitch.

---

### Technical Success

| Metric | Current | Target |
|---|---|---|
| Deployment readiness score | 5.8/10 | **≥8.5/10** — scored against the rubric in `DEPLOYMENT_READINESS.md` (Backend ≥9, Frontend ≥8, Infrastructure ≥9, Security ≥9). Rubric is locked at the time of this PRD and does not change during the upgrade. |
| CRUD completeness | ~40% | 100% — every tool supports Create, Read, Update, Delete where appropriate. Attendance and fee records use a correction-with-audit-trail approach, not hard delete (deleting financial/academic records creates compliance risk). |
| UX state coverage | Inconsistent | Loading, empty, and error states on every screen that shows data — including recovery guidance when a write operation fails partway through |
| Theme consistency | Partial | All tool panels respect dark/light theme correctly — no hardcoded colors |
| File storage | Ephemeral disk | S3-backed — files survive redeployment. Existing files migrated; migration tested against a copy of production data before running on live |
| Test coverage | Zero | See Testing Success below |
| Observability | Minimal | Structured logs shipped to a queryable destination + `/api/health/ready` endpoint + at least one active alert (e.g. error rate spike) so the team knows when something breaks before Aman does |
| AI response degradation | Not defined | If Azure OpenAI is unavailable, the platform degrades gracefully — tool panels still work, only the chat AI is temporarily unavailable. No OpenAI outage should prevent fee collection or attendance marking via the tool panels. |
| Write operation performance | Not defined | p95 ≤ 500ms for standard API operations; tool panel initial load ≤ 3s on 4G. See Non-Functional Requirements — Performance for full targets. |

---

### Testing Success

The test baseline must reflect the actual risk profile of this system — an AI that executes real financial and academic operations on behalf of real school staff.

**Minimum test coverage for go-live:**

- **Core route tests (Pytest):** Auth, attendance, fee collection, and student CRUD routes — minimum 1 happy-path + 1 auth-failure test per route
- **Authorization matrix tests:** For every user role (owner, principal, admin profiles) × every sensitive data endpoint — each cell explicitly asserts correct access or correct denial. A teacher must never see fee records; an admin from one role must not access another role's restricted data.
- **AI tool-dispatch tests:** For each operation the AI can trigger (mark attendance, record fee, update a record) — tests covering: correct execution on clear instruction, safe rejection on ambiguous instruction, and confirmation that the confirm-action step cannot be skipped
- **Fee idempotency:** A duplicate fee submission (e.g. double-tap, network retry) must not create a duplicate payment record
- **Confirm-action flow:** Every data-mutating operation has a test asserting the confirmation step fires before any data changes

**Frontend:** No automated test suite for MVP. The confirm-action flow (the user-facing safety net for all write operations) gets manual smoke-test coverage before go-live.

---

### Measurable Outcomes

- **2 weeks post go-live**: Owner and Principal each active on the platform daily
- **4 weeks post go-live**: Aman and Adesh pass a 10-question walkthrough using questions they wrote themselves — no paper, no WhatsApp
- **30 days post go-live**: All Admin profiles performing primary workflows without paper backup
- **Month 3**: The Aaryans still actively using the platform — retention confirmed before any school #2 pitch
- **Zero unconfirmed write operations**: Every data-mutating AI action passes through the confirm-action flow — no exceptions
- **Zero data leaks**: Each role sees only their permitted data, enforced at the API layer and verified by automated tests
- **No silent failures**: If anything breaks, the team gets an alert before Aman notices

---

## Product Scope

### MVP — Minimum Viable Product

*Everything required for Aman and Adesh (Owner + Admin profiles) to replace paper with EduFlow in daily operations. Full school database loaded. Teachers and students are not yet logging in.*

- Full school database imported: all student profiles, attendance history, fee records, staff data, class information — fully visible to Owner and Admin
- Full CRUD on all existing tool panels — Create, Read, Update, Delete where appropriate; soft correction with audit trail for attendance and fee records
- Owner and all Admin profile types fully functional with correct data scoping
- Consistent UX states (loading / empty / error / recovery) across every tool panel
- Theme coherence: all panels respect dark/light CSS variables — no hardcoded colors
- S3-backed file storage for uploads (replacing ephemeral disk), with migration of existing files
- Deployment readiness score ≥8.5/10 (per locked rubric)
- Structured logging shipped to queryable destination + `/api/health/ready` + at least one active alert
- AI graceful degradation: platform works when Azure OpenAI is unavailable
- Test baseline: authorization matrix, AI tool-dispatch, fee idempotency, confirm-action coverage, core route tests

### Growth Features (Post-MVP)

*What makes EduFlow ready for Phase 2 (teachers + students) and competitive for school #2 pitch.*

- Teacher and Student logins activated — database already there, access unlocked
- WhatsApp/Twilio integration — fee reminders and attendance alerts to parents
- Advanced reporting: attendance trend charts, fee collection bar charts (Recharts)
- Token recharge and subscription billing system
- Platform health monitoring dashboard for Layaa AI (operator view)
- School onboarding flow — new school setup, school-specific configuration

### Vision (Future)

*EduFlow as the operating system for schools across India.*

- Mobile-first app (React Native or PWA)
- Parent portal: fee payments, attendance notifications, teacher communication
- API access tier for school integrations
- CBSE/UP Board curriculum intelligence — AI tutoring scoped to board syllabus
- School group support — multi-campus architecture for clients running multiple branches under one owner
- Automated regulatory reporting

*For the full capability breakdown by phase including must-have capabilities, triggers, and risk mitigations, see Project Scoping & Phased Development.*

---

## User Journeys

### Journey 1: Aman — "Nothing Slips Through" (Owner, Happy Path)

**Before EduFlow:** Aman walks into school on Monday morning carrying the weight of everything he doesn't know. Did anyone come to complain on Friday? He doesn't know — the receptionist might have written it on a notepad, might have told him on WhatsApp, might have forgotten. Is the broken chair in Class 7 fixed? He asked the maintenance guy last week and wrote it in his diary, but he has no idea if it happened. A teacher texted him about a staff dispute — where did that message go? He opens five WhatsApp conversations, flips through his diary, walks over to the accountant's desk. It takes 45 minutes just to know what happened while he was away.

**With EduFlow — Opening Scene:** Aman opens EduFlow at 8:30 AM on Monday. He types: *"What happened over the weekend? Any parent visits, complaints, or pending issues?"* The AI responds with a summary: two parent visits logged by reception (one fee query resolved, one complaint about a teacher's behaviour filed and tagged as pending follow-up), one maintenance request open (broken desk in Class 4, logged Friday, unresolved), one staff complaint submitted by the sports teacher about equipment storage.

**Rising Action:** Aman taps into the teacher behaviour complaint. He sees the full entry the receptionist logged — parent name, date and time of visit, child's class, summary of the complaint, which staff member handled it. He asks: *"Has Adesh seen this?"* The AI confirms it was flagged to the principal's dashboard. He types: *"Mark this as: reviewed by owner, assign follow-up to Adesh by Wednesday."* Done — no WhatsApp, no call, no risk of it getting lost.

He moves to the broken desk. He types: *"Is this fixed?"* Status: open. He assigns it to maintenance with a deadline.

**Climax:** Aman asks: *"Show me all open complaints and pending maintenance requests."* He sees everything in one list — five items, each with a status, an owner, and a deadline. For the first time on a Monday morning, he knows exactly what's unresolved. He doesn't need to chase anyone.

**Resolution:** By 9:15 AM, Aman has reviewed everything that happened since Friday, assigned follow-ups, and knows the fee collection status for the week — all from a single conversation. His diary stays in his drawer. He doesn't text a single person to ask "what happened."

**Capabilities revealed:** Visitor and parent visit logging, complaint/incident tracking with status and assignment, maintenance request tracking, owner dashboard summary, AI-driven daily briefing, cross-department visibility for owner role.

---

### Journey 2: Aman — A Complaint That Could Have Become a Crisis (Owner, Edge Case)

**Opening Scene:** A parent arrives furious on a Thursday afternoon — their child was allegedly humiliated by a teacher in front of the class. The receptionist logs it in EduFlow: parent name, child's name, class, teacher name, description of incident, severity flagged as high.

**Rising Action:** The moment the log is saved, it appears in Aman's EduFlow dashboard flagged as high-severity. He's not at school — he's at a meeting. He sees it on his phone. He pulls up the entry, reads the full account, and types: *"Who is available to speak with this parent today?"* The AI checks the schedule and suggests Adesh is free at 4 PM.

**Climax:** Aman types: *"Log that Adesh will meet the parent at 4 PM today. Flag this complaint for my review by Friday with Adesh's notes."* The incident doesn't fall through the cracks. Adesh meets the parent, logs his notes. On Friday, Aman reviews the full thread — complaint, meeting, resolution, outcome — in one place.

**Resolution:** Without EduFlow, this complaint would have lived on a notepad, reached Aman via a WhatsApp message, and probably been forgotten within a week. With EduFlow, it's documented, actioned, and resolved — with full history available if the parent ever returns.

**Capabilities revealed:** Severity flagging on incidents, owner notification for high-severity events, incident-to-action assignment, multi-step incident thread (log → action → resolution → review), mobile-accessible owner dashboard.

---

### Journey 3: Adesh — Running the School Day (Principal, Daily Operations)

**Opening Scene:** Adesh arrives at 7:45 AM. Before EduFlow, his first task was physically walking to the attendance register to see which teachers had marked in, then checking with the transport head, then fielding WhatsApp messages from parents, then dealing with a teacher who hadn't shown up for first period. He was reactive all morning — things came to him, not the other way around.

**Integration note:** Staff attendance is captured automatically via the school's biometric hardware. EduFlow pulls this data via API — Adesh never manually enters who is present. The system already knows.

**With EduFlow — Rising Action:** Adesh opens EduFlow and asks: *"Who is absent today?"* The AI pulls from the biometric integration: 2 teachers absent, 1 support staff absent. It flags that Class 9-B has no teacher assigned to period 2. Adesh types: *"Who can cover period 2 Class 9-B?"* The AI queries the timetable (FR90) to find staff with no conflicting period and surfaces two available options — Adesh selects one and approves the substitution. The AI facilitates discovery; Adesh makes the decision.

**Climax:** He asks: *"Any parent meetings scheduled today?"* Two entries from the receptionist's log. He reviews them and adds a preparation note. He checks the open complaint from Journey 2 — sees Aman's instruction to follow up with the parent at 4 PM. His day is fully organised before 8:15 AM.

**Resolution:** Adesh spends his morning on actual decisions, not information gathering. When Aman asks him "what happened today," Adesh doesn't reconstruct from memory — he opens the log.

**Capabilities revealed:** Biometric API integration for real-time staff attendance, substitution workflow, timetable awareness, parent meeting log visible to principal, incident cross-linking to principal task list.

---

### Journey 4: The Accountant — Fee Collection and Follow-ups

**Before EduFlow:** The accountant manages fee collection from a standalone desktop software. It shows who has paid and who hasn't. But it doesn't talk to anything else. Every morning she exports a list of defaulters, calls or messages parents manually, logs payments by hand, and prepares a weekly summary for Aman in a spreadsheet. It takes hours and things slip.

**Integration note:** The school's existing fee collection software is the source of truth for fee payments. EduFlow integrates with it via API — pulling the latest fee status for every student automatically. The accountant doesn't re-enter data.

**With EduFlow — Opening Scene:** The accountant opens EduFlow on Tuesday morning. She asks: *"Show me students with fees overdue by more than 30 days."* EduFlow pulls from the integrated fee software and returns a list: 12 students, sorted by amount overdue, with parent contact details.

**Rising Action:** She asks: *"Which of these haven't been contacted yet this month?"* EduFlow cross-references the contact log and returns 7 names. She initiates follow-up reminders. She logs a call — one parent agreed to pay by Friday, partial payment accepted.

**Climax:** Aman asks for the fee collection status. Instead of preparing a report, the accountant asks EduFlow: *"Generate fee collection summary for this month."* It produces instantly — total collected, total outstanding, number of defaulters, percentage collected. She shares it with Aman from within the platform.

**Resolution:** The accountant's energy goes to decisions and conversations, not data entry. The fee software still does what it does — EduFlow surfaces the data where it's useful.

**Capabilities revealed:** Fee software API integration (read-only, syncing payment status), defaulter tracking with contact history, manual note logging against fee records, fee summary report generation, parent contact log.

---

### Journey 5: Layaa AI Operator (Abhimanyu) — Platform Health

**Opening Scene:** Abhimanyu gets an alert at 9:15 AM: error rate on the EduFlow backend has spiked. He opens the platform health dashboard.

**Rising Action:** The dashboard shows 23 errors in the last 10 minutes, all from the fee software integration endpoint — a third-party timeout, not an EduFlow code issue. He confirms this in the structured logs within seconds.

**Climax:** The platform is degrading gracefully — tool panels still work, the chat AI still works, only the live fee sync is temporarily paused. Aman and the accountant see a banner: *"Fee data is temporarily paused — last updated 45 minutes ago."* They're not blocked. Abhimanyu fixes the integration timeout configuration and restarts the sync. Data catches up automatically.

**Resolution:** The issue is resolved in 20 minutes. No one called Aman to say "the platform is broken." The failure was contained, communicated, and fixed without drama.

**Capabilities revealed:** Structured logging with alerting, graceful degradation for third-party integrations, user-visible sync status indicators, integration retry and recovery logic.

**Phase note:** The operator health *dashboard* referenced in this journey is a Phase 2 Growth feature. Phase 1 delivers structured logs, alerts, and the `/api/health/ready` endpoint — Abhimanyu investigates via logs, not a dashboard UI.

---

### Journey 6: Maintenance Admin — Facility Request to Resolution

**Before EduFlow:** When a classroom chair breaks or a ceiling fan stops working, it gets reported to Aman verbally, via WhatsApp, or via a handwritten note passed along the corridor. Nobody knows if the request is being acted on. The maintenance worker acts on verbal memory. Three weeks later, Aman asks about the broken chair and discovers it was never fixed — the note got lost. There is no record that the request was ever made.

**Opening Scene:** A teacher notices a broken window latch in the library and logs it in EduFlow from the teacher's panel. The request appears immediately in the Maintenance Admin's facility request queue — type: facility, description: broken window latch, location: library, logged by: English teacher, timestamp: 9:14 AM.

**Rising Action:** The Maintenance Admin opens the queue on their panel. They review the request, change the status to "In Progress," and add a note: "Contacted vendor for replacement latch — expected delivery Thursday." The request is now visible to the Owner with its updated status. No WhatsApp message required.

When the latch arrives on Thursday, the Maintenance Admin logs the repair completion and marks the request "Completed — pending owner confirmation." Aman sees it in his dashboard flagged for review.

**Climax:** Aman opens the request from his phone. He sees the full thread: original report, in-progress update, completion note. He taps "Confirm resolved." The request is closed with a full audit trail — who logged it, who worked on it, when it was completed, when it was confirmed.

**Resolution:** At the end of the month, Aman asks EduFlow: "Show me all facility requests this month — how many were resolved, how many are still open?" He gets a list. No facility issue has slipped through without being logged. The maintenance worker's workload is visible. Nothing is tracked in memory or WhatsApp.

**Capabilities revealed:** Facility request logging by any staff profile, Maintenance Admin queue and status management, status thread with notes, Owner confirmation-of-resolution workflow, facility request summary view for Owner, cross-department visibility.

---

### Journey 7: Receptionist — Visitor Log and Announcement

**Before EduFlow:** The receptionist keeps a physical visitor register on the front desk. When a parent walks in, they write the name and reason in the register — sometimes. If Aman later wants to know who came in last Tuesday or what the complaint was about, he calls the receptionist or looks for the register himself. Announcements go out on a class group WhatsApp or via the peon walking room to room.

**Opening Scene:** A parent arrives at 11 AM on a Wednesday — Mrs. Sharma, mother of Aryan Sharma, Class 6-B. She wants to speak with someone about her son's attendance record. The Receptionist opens EduFlow on the front-desk device and logs the visit: parent name, student name, class, purpose of visit, time of arrival. While waiting, the parent also raises a concern about the school canteen food.

**Rising Action:** The Receptionist creates two entries: a visitor log for the attendance query (routed to Principal for follow-up) and an incident/complaint for the canteen concern (severity: low, assigned to a senior admin for acknowledgement). Both entries are immediately visible in Aman's and Adesh's dashboards — no phone call required.

At 2 PM, the Receptionist needs to inform teaching staff that the Parent-Teacher Meeting scheduled for Friday has been moved to next Monday. She creates an announcement in EduFlow targeted to the "Teachers" role group. Every logged-in teacher sees it in their notification feed. No WhatsApp group required.

**Climax:** Adesh, reviewing his dashboard at the end of the day, sees the complaint about the canteen and Aman's instruction to follow up. The visitor log shows the parent's contact details and the issue. Adesh logs a note that he spoke with the canteen vendor and the concern will be addressed. The complaint thread is now closed.

**Resolution:** On Friday, Aman asks EduFlow how many parent visits were logged this week. He gets a count and a list. The canteen complaint has a resolution note on it. Nothing was lost, nothing was reconstructed from memory.

**Capabilities revealed:** Visitor and parent entry logging, incident and complaint creation by Receptionist, severity routing to principal/owner dashboards, role-targeted announcements, contact details associated with visitor log, complaint thread resolution by principal.

---

### Journey 8: Transport Head — Route Assignment and Roster

**Before EduFlow:** The Transport Head manages vehicle routes in an Excel sheet and a physical notebook. When a new student enrols and the parents ask which bus route covers their area, the Transport Head looks it up manually and calls them back. When the Owner wants to know how many students are on each bus, he asks the Transport Head, who counts from the notebook. If a vehicle breaks down, there is no quick way to find which students are affected.

**Opening Scene:** Three new students are joining Class 5-A at the start of the term. Their parents have all requested school transport. The Transport Head opens EduFlow and pulls up the student records for all three. One student lives in Sector 7 — that's Route Zone B. The second lives near the railway station — Route Zone D. The third is just 200 metres from school — no bus required.

**Rising Action:** The Transport Head assigns Route Zone B to the first student and Route Zone D to the second. The third student's fee profile is updated with no transport fee. Each assignment is recorded instantly — no Excel, no phone call to the accountant to adjust the fee.

A week later, Vehicle 3 (the bus covering Route Zone B) is in for maintenance. The Transport Head needs to know how many students are affected. He opens the Route Zone B view in EduFlow — 23 students, with their names, class sections, and parent contact details in a single list.

**Climax:** The Transport Head shares the list with the Receptionist who coordinates alternate arrangements. Aman asks from his phone: "How many students use school transport?" EduFlow returns a count — 87 students across 4 route zones, 6 vehicles, with current zone assignments.

**Resolution:** The Transport Head's roster is always current in EduFlow. No student enrolment changes the Excel file anymore — it changes the EduFlow record, and the roster updates automatically. The Owner has real-time transport visibility without asking anyone.

**Capabilities revealed:** Transport Head vehicle record management, route zone creation and management, student-to-route-zone assignment, student transport roster view filtered by zone or vehicle, Owner and Principal full transport roster view, parent contact details accessible in zone roster.

---

### Journey 9: IT/Tech Admin — Tech Request Triage

**Before EduFlow:** Tech issues at the school come in through WhatsApp, verbal reports, and the occasional handwritten note slipped under the IT room door. The IT/Tech Admin has no queue — just a mental list that gets longer. When Aman asks "What tech issues are open?", the IT Admin tries to reconstruct from memory and WhatsApp chat history. Some issues get resolved. Some get forgotten.

**Opening Scene:** Monday morning, three issues arrive almost simultaneously. A teacher reports that the smartboard in Class 8-A won't connect to the laptop. The accounts department says the printer is offline. A staff member can't log in to EduFlow — password issue.

**Rising Action:** The IT/Tech Admin logs all three as tech requests in EduFlow: smartboard connectivity (Category: Hardware, assigned to self), printer offline (Category: Hardware, assigned to self), password reset (Category: Account Access — this one is resolved immediately by triggering the password reset from FR79 and the request is closed with a note).

Two are now in the queue as Open. The smartboard takes priority — it's blocking a scheduled class. The IT Admin updates its status to "In Progress" and adds a note: "Identified HDMI cable fault — cable on order." The teacher who logged it can see the status has changed.

**Climax:** By Wednesday, the smartboard cable arrives and is replaced. The IT Admin closes the request with a resolution note. The printer issue is escalated to an external vendor — the IT Admin updates the status to "Escalated" with the vendor's name and ticket number.

Aman opens his dashboard and checks open issues. He sees 1 open tech request (printer, escalated to vendor) and 0 open facility requests. He can tell at a glance that nothing is being ignored.

**Resolution:** At the end of the month, the IT Admin can show a history of all requests logged, resolved, and their resolution time. Aman gets visibility without asking. No issue disappears into WhatsApp.

**Capabilities revealed:** IT/Tech Admin tech request logging with category and self-assignment, status management and note threads, escalation logging with external references, namespace isolation (tech vs. facility requests), Owner unified view across both namespaces, submitter can see status updates on their own logged request.

---

### Journey Requirements Summary

| Journey | Key Capabilities Revealed |
|---|---|
| Aman — Morning Visibility | Complaint/incident log, maintenance request tracking, owner dashboard summary, AI daily briefing |
| Aman — Crisis Complaint | Severity flagging, incident assignment, multi-step resolution thread, mobile owner access |
| Adesh — School Day | Biometric API integration, substitution workflow, principal task view, timetable awareness |
| Accountant — Fee Follow-ups | Fee software API integration, defaulter tracking, contact log, report generation |
| Operator — Platform Health | Alerting, graceful degradation, sync status indicators, operator health dashboard |
| Maintenance Admin — Facility Request | Facility request queue, status + note management, owner confirmation-of-resolution, summary view |
| Receptionist — Visitor Log & Announcement | Visitor logging, complaint creation with routing, role-targeted announcements, complaint thread resolution |
| Transport Head — Route Assignment | Vehicle and route zone management, student-to-zone assignment, zone roster with parent contacts |
| IT/Tech Admin — Tech Request Triage | Tech request logging with category, status management, escalation logging, namespace isolation |

**Two integration requirements surfaced by these journeys — require scoping decision:**
1. **Biometric hardware API** — automatic staff attendance sync into EduFlow
2. **Fee collection software API** — automatic student fee status sync into EduFlow

Both are foundational to the principal and accountant journeys being operationally real. Placement in MVP vs. Growth depends on API availability from the respective vendors.

---

## Domain-Specific Requirements

### Compliance & Regulatory

**India — DPDP Act 2023 (Digital Personal Data Protection Act)**
- Student data (name, attendance, academic records, fee history) is personal data under the Act — must be processed only for the stated school management purpose
- Students are minors (under 18) — when student logins go live in Phase 2, parental consent must be obtained before processing their data. Phase 1 (Owner + Admin only) is lower risk since students are not interacting with the platform directly, but student records stored in the database are still subject to protection obligations
- Data must not be shared with third parties without consent — AI inference via Azure OpenAI must not send identifiable student data to the LLM without appropriate data processing agreements
- Right to erasure: if a student leaves the school, their data must be deletable on request — the soft-correction/audit-trail model must coexist with a hard-delete capability for DPDP compliance requests

**CBSE Record-Keeping**
- Attendance and academic records must be retained for a minimum period (typically 5 years for CBSE schools) — hard delete of these records is prohibited; the audit-trail-only correction model is the right approach
- Fee records are financial documents — subject to standard Indian financial record retention (typically 7 years)

**No US regulations apply** — FERPA and COPPA are US federal laws and have no jurisdiction over an Indian school.

**UDISE+ (Investigation Required Before Phase 2 Scope Finalisation)**
UDISE+ (Ministry of Education's Unified District Information System for Education) requires annual submission of student enrolment, attendance, and demographic data for CBSE schools. EduFlow stores this data. Whether UDISE+ export is a regulatory dependency for The Aaryans — or is currently handled manually via another system — requires client confirmation. If EduFlow is expected to support UDISE+ submission, a dedicated FR for data export in the required format must be added before Phase 2 scope is finalised. **Action required:** confirm with Aman before Phase 2 begins.

---

### Fee Domain Complexity — Discount Policy Engine

The Aaryans applies a range of fee discounts to students, and the accountant must be able to configure, apply, and track these without needing a developer. This is a significant domain requirement: the discount system must be a **configurable rule engine**, not a set of hard-coded fields.

**Known discount types (to be confirmed and expanded by the accountant):**

| Discount Type | Trigger | Notes |
|---|---|---|
| Sibling discount — 2 siblings | 2 children from the same family enrolled simultaneously | Percentage to be configured |
| Sibling discount — 3+ siblings | 3 or more children from the same family enrolled simultaneously | Different (higher) percentage |
| Staff relationship discount | Student's parent/guardian is personally known to a staff member | Applied at accountant's discretion |
| Custom / ad-hoc discount | Any other reason the accountant defines | Open-ended — see below |

**Custom discount requirement:**
The accountant must be able to create a new discount type at any time with:
- A name/label for the discount (e.g. "Merit Scholarship", "Management Quota", "Flood Relief 2025")
- The discount value (flat amount or percentage)
- Whether it is recurring (applies every term) or one-time
- An optional note explaining the reason

**Per-student discount application:**
- Any number of discounts can be applied to a single student's fee profile simultaneously
- The system must show the original fee amount, each discount applied (with its label and value), and the final payable amount — no black-box calculations
- The accountant applies discounts at enrolment or at any point during the academic year
- All discount applications are logged with who applied them and when (audit trail)

**Relationship to fee software integration:**
If the fee collection software is integrated via API, EduFlow's discount records must either:
(a) sync back to the fee software so it generates the correct payable amount, or
(b) EduFlow manages discounts independently and the fee software sees only the post-discount amount

This decision depends on the fee software's capabilities and must be resolved before integration implementation.

---

### Technical Constraints

**Student and Staff PII**
- Names, contact numbers, addresses, academic records, and fee history are all PII — must not appear in logs, must not be sent to external services without data processing agreements
- Staff biometric data (from the hardware integration) is sensitive biometric PII under DPDP — EduFlow must not store raw biometric data; it should only receive and store the processed attendance event (present/absent, timestamp) from the hardware API

**Financial Data Integrity**
- Fee records are financial documents — corrections must be logged with who made the change, when, and why. No silent overwrites
- Discount applications are permanent records — a discount once applied and a payment once recorded must not be silently deleted; corrections require an audit entry
- Duplicate payment protection is required
- Fee data from the integrated software is read-only in EduFlow — the fee collection software remains the source of truth; EduFlow never writes back to it

**AI Content Safety (Phase 2 — Student Interactions)**
- When student logins go live, the AI must not answer questions outside the school/academic context — content filter already exists in the codebase and must be enforced for all student-role interactions
- The AI must never reveal one student's data to another student — scope resolver enforces this at the query level

**Data Residency**
- AWS infrastructure should use the Mumbai (ap-south-1) region to keep school and student data within India — relevant for DPDP compliance and latency to UP-based users
- **Pre-go-live compliance gate:** The Azure OpenAI data processing agreement (DPA) confirming India-region data processing and DPDP-compliant terms must be signed and on record before EduFlow goes live with any student PII. This is not a Phase 2 item — student records are loaded from day one.

---

### Integration Requirements

| Integration | Purpose | Data Flow | Phase |
|---|---|---|---|
| Biometric hardware API | Staff attendance sync | Hardware → EduFlow (processed attendance events only — no raw biometric data) | MVP or Growth depending on vendor API availability |
| Fee collection software API | Student fee status sync | Fee software → EduFlow (read-only); discount sync direction TBD based on software capability | MVP or Growth depending on vendor API availability |

**Integration constraint:** EduFlow is always the consumer, never the writer, unless the fee software supports a discount write-back API. This limits risk — if EduFlow has a bug, it cannot corrupt the authoritative data in either system.

---

### Domain-Specific Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Discount miscalculation leads to wrong fee amount charged | Medium | High | Discount engine shows full calculation breakdown — original fee, each discount, final amount. No black-box totals. |
| Student PII exposed via AI chat response | Medium | High | Scope resolver enforces role-based data access at query level; content filter active for student role |
| Fee record corrupted or duplicated | Low | High | Soft-correction audit trail; idempotency test; fee software remains source of truth |
| Biometric data stored raw in EduFlow | Low | High | Integration spec: receive processed attendance events only, never raw biometric data |
| DPDP erasure request cannot be fulfilled | Medium | Medium | Hard-delete capability must exist for DPDP compliance requests, even if not exposed in normal UI |
| Data residency violation | Low | Medium | Use AWS Mumbai region; confirm Azure OpenAI India-region endpoint or establish DPA with Microsoft |
| AI hallucinates a fee amount or discount | Medium | High | AI never fabricates structured fee data — always queries the database first; confirm-action flow for all write operations |

---

## Innovation & Novel Patterns

### Detected Innovation Areas

**1. Conversational School Operations (Primary Differentiator)**
EduFlow replaces the form-based paradigm of every existing school management product with a chat-first interface. The primary user action is a natural language instruction, not a menu navigation. This is not a feature layered on top of a traditional system — the conversational interface *is* the system.

What this means for the upgrade: the quality of the AI's intent-parsing, the reliability of tool dispatch, and the safety of the confirm-action flow are not secondary concerns — they are the product. Any regression in these areas is a regression in EduFlow's core differentiator.

**2. AI-Executed Operations with Deterministic Safety Gate**
The combination of LLM-based intent parsing + a hard confirm-action step before any data mutation is a novel architecture pattern for operational school software. It gives the UX benefit of natural language while maintaining the safety guarantees of a traditional form submission.

The innovation risk: if the confirm-action gate is ever bypassed (by an LLM that decides an instruction is "obviously confirmed"), the safety architecture collapses. The test requirement for confirm-action flow coverage is non-negotiable.

**3. Institutional Memory via Conversational Log**
EduFlow replaces the head teacher's diary. Parent visits, complaints, maintenance requests, staff interactions — all logged and retrievable through conversation. No existing school software offers this. The value isn't in the logging itself but in the retrieval: *"What did we discuss with Rahul's parents last month?"* answered instantly.

---

### Market Context & Competitive Landscape

| Competitor | Paradigm | EduFlow Difference |
|---|---|---|
| Teachmint | Form-based, teacher-first | Chat-first, owner/admin-first |
| MyClassCampus | ERP-style, complex navigation | Conversational, zero navigation |
| Fedena | Open-source, developer-configured | Opinionated, AI-native |
| WhatsApp + Excel (current state) | Fragmented, no institutional memory | Unified, searchable, persistent |

The real competition for EduFlow's Phase 1 users (Aman and Adesh) is not another school software — it's the paper diary and WhatsApp. The bar for winning is not "better than Teachmint" but "better than a notepad."

---

### Validation Approach

- **Primary validation**: The 4-week pilot at The Aaryans. If Aman stops using his diary and Adesh stops using WhatsApp for internal coordination, the innovation is working.
- **Leading indicator**: Daily active use within 2 weeks of go-live (≥1 AI query or tool action per day per primary user).
- **Failure signal**: If users default to the tool panel UI and bypass the chat interface entirely, the conversational paradigm hasn't landed — investigate why.

---

### Risk Mitigation

| Innovation Risk | Mitigation |
|---|---|
| Chat interface feels unreliable, users abandon it for forms | Tool panels remain fully functional as a fallback — users are never forced through chat |
| AI misparses an instruction and executes wrong operation | Confirm-action gate is mandatory for all writes; every mutation shows exactly what will change before it does |
| Institutional memory only works if staff actually log things | Logging must be frictionless — receptionist logs a parent visit in one sentence, not a 10-field form |
| Competitive products copy the chat interface | First-mover advantage in the Indian vernacular school market; deepen the institutional memory moat |

---

## Platform Architecture & Technical Requirements

### Project-Type Overview

EduFlow is a multi-role SaaS web application for school management. Its technical profile is a server-rendered + API hybrid (Next.js frontend, Python/FastAPI backend, MongoDB), serving seven distinct admin profile types under a five-tier role hierarchy, with separate data scopes and permission boundaries. The current deployment targets a single tenant (The Aaryans); multi-tenancy is a planned Growth-phase concern.

### Technical Architecture Considerations

#### Tenant Model

**Current state:** Single-tenant architecture — all data belongs to The Aaryans. No tenant isolation is implemented today.

**Planned direction (not yet finalized):** Schema-per-tenant isolation — each school gets its own isolated set of database collections. Strongest data boundary, cleanest DPDP compliance path (per-school erasure is a single collection drop). Trade-off is operational complexity at scale, which is acceptable for a platform handling minors' PII.

**Deferred to Growth phase.** Multi-tenancy triggers when school #2 onboards. All new data models in this upgrade must include a `schoolId` field as a forward-compatibility measure, even if not enforced today.

#### RBAC Matrix

| Role | Data Scope | Write Permissions |
|---|---|---|
| **Owner** | Entire school — all data, all departments, all financials | All operations + system configuration |
| **Principal** | All academic and operational data + student-level fee status | Academic ops, leave approval, substitution, announcements, approval decisions |
| **Admin — Accountant** | Fee records, student financial profiles, expense logs | Fee collection, discount application, expense logging |
| **Admin — Receptionist** | Visitor logs, enquiries, announcements | Visitor entry, enquiry logging, announcement creation, approval requests |
| **Admin — Transport Head** | Transport roster, routes, vehicle assignments, route zones | Route/vehicle assignment, transport log updates, approval requests |
| **Admin — IT/Tech** | Tech issue tracker (`tech_request` type only) | IT issue logging, status updates, tech request management, approval requests |
| **Admin — Maintenance** | Facility issue tracker (`facility_request` type only) | Maintenance request logging, status updates, task assignment, approval requests |
| **Teacher** *(Phase 2)* | Own class roster, own attendance records, own timetable | Attendance marking for own classes only |
| **Student** *(Phase 2)* | Own academic record, own fee status, own timetable | None — read-only + AI query within own scope |

**Fee visibility split:**
- Principal sees per-student fee status (paid / unpaid / overdue) — useful for academic decisions (exam eligibility, report cards)
- Principal does not see school-wide financial aggregates (total collected, expense reports, revenue) — Owner-only

**New in this upgrade:** The Maintenance admin profile does not yet exist in the platform. Full implementation required: role definition, data model, tool panel, permission matrix enforcement, and test coverage.

**Enforcement:** RBAC enforced at the API layer on every sensitive endpoint. Verified by the authorization matrix test suite.

#### Issue Tracker — Namespace Isolation

Two distinct issue types at the data model level:

| Type | Owned By | Scope |
|---|---|---|
| `tech_request` | IT/Tech admin | Hardware, software, network, device issues |
| `facility_request` | Maintenance admin | Physical facility, furniture, infrastructure issues |

Each profile's tool panel queries and writes only to its own namespace. Cross-profile read access is explicitly denied. Overlap cases (e.g. broken projector — hardware or facility?) are resolved at intake via a category selector that routes to the correct type. No shared issue inbox.

#### Approvals Workflow

Any Admin profile can submit an approval request for significant school-wide actions (major purchases, policy changes, large facility work, staff additions above a threshold). Phase 1 model:

- Requester submits: title, description, estimated impact/cost, supporting note
- Request appears in Owner dashboard with an unread-count badge; Principal also sees it if flagged as requiring academic sign-off
- Owner approves or rejects with a mandatory reason field
- Requester is notified of the outcome
- Full audit trail: who submitted, who decided, when, reason

**Escalation and expiry:** Not required for Phase 1. Deferred to Growth.

**Notification surface:** Unread-count indicator on Owner and Principal dashboards. No push notification required for Phase 1.

#### Audit Log Visibility

| Role | Audit Log Access |
|---|---|
| Owner | All audit logs across all profiles and operations |
| Principal | Academic and operational audit logs only — fee correction logs excluded |
| Accountant | Own fee-related audit logs only |
| All other Admin profiles | Own operation logs only |

#### Mobile-First Requirements

Owner (Aman) and Principal (Adesh) will use EduFlow primarily on mobile from day one. This is a go-live constraint, not a future consideration.

- All Owner and Principal views must be fully functional on iOS Safari and Android Chrome — no horizontal scrolling, no truncated data, no non-tappable elements
- AI chat interface must remain usable with the mobile keyboard open — input area must stay visible and not be obscured
- Priority screens for mobile: dashboard summary, complaint/incident log, leave approval, substitution workflow, student fee status, pending approvals
- SSE reconnect-on-focus and heartbeat behaviour specified in Non-Functional Requirements — Real-Time Communication (SSE)

Admin profile tool panels (Accountant, Receptionist, Transport, IT/Tech, Maintenance) are desktop/tablet-first. Mobile access must not break them, but mobile optimisation is not required for this release.

#### Real-Time Requirements

| Surface | Who Needs It | Trigger |
|---|---|---|
| Staff attendance | Principal + Owner | Biometric event received — SSE push to active sessions |
| Fee collection summary | Accountant + Owner | Fee payment recorded — SSE push or ≤30s poll |

Session deduplication, keepalive heartbeat, reconnect-on-focus, and graceful degradation behaviour are specified in Non-Functional Requirements — Real-Time Communication (SSE).

#### Transport — Phase 1 Scope

Transport Head manages routes and vehicle assignments manually via the tool panel. Student records include a route zone field (not raw home address) for assignment purposes.

**Phase 2 Growth item — Transport Route Optimisation:** Google Maps Distance Matrix API + proximity clustering to automatically group students into vehicles for cost-efficient routing. Deferred until Aman explicitly requests it. Groundwork: student records should store a route zone and (backend-only, never displayed) geographic coordinates to avoid a data migration when this feature is built.

#### Integration Architecture

| Integration | Data Direction | EduFlow Role | Phase |
|---|---|---|---|
| Biometric hardware API | Hardware → EduFlow | Consumer — processed attendance events only; no raw biometric data stored | MVP or Growth (vendor-dependent) |
| Fee collection software API | Fee software → EduFlow | Consumer — read-only fee status sync | MVP or Growth (vendor-dependent) |
| Azure OpenAI | EduFlow → Azure | Client — anonymised query context only; no raw PII | Live today |
| AWS S3 | EduFlow → S3 | Client — file upload/retrieval | MVP (upgrade target) |

#### Compliance Requirements

| Requirement | Scope | Note |
|---|---|---|
| DPDP Act 2023 — data minimisation | All PII | No PII in logs; no raw PII sent to external APIs without DPA |
| DPDP Act 2023 — right to erasure | Student records | Hard-delete capability required alongside soft-correction model |
| CBSE retention | Academic records | 5-year minimum; hard delete prohibited |
| Financial retention | Fee records | 7-year minimum; corrections via audit trail only |
| Data residency | All data | AWS Mumbai (ap-south-1); Azure OpenAI India endpoint or Microsoft DPA required |

### Implementation Considerations

- **Maintenance profile (new):** Full build required — role, data model, tool panel, RBAC enforcement, test coverage
- **Subscription tiers:** Out of scope for this PRD
- **AI write rate limiting:** Phase 1 known gap — no per-session throttle on AI-executed mutations. Documented for Growth-phase hardening
- **Announcement moderation:** Phase 1 known gap — Receptionist-authored announcements are unmoderated. Approval gate deferred to Phase 2 when teachers and students are live
- **`schoolId` forward-compatibility:** All new or modified data models must include a `schoolId` field even though single-tenant enforcement is not yet active

---

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Operational trust — the minimum that makes Aman and Adesh stake their morning on EduFlow instead of paper. Not a feature demo, not a prototype. A daily-use system that is correct, complete, and recoverable when something goes wrong.

**What "complete" means for this MVP:** Every role that goes live on day one (Owner + all Admin profiles) must be able to perform their full primary workflow without hitting a dead end — no missing delete buttons, no broken edit forms, no screens that crash on empty data. The database is fully loaded. The AI works. The platform doesn't lose files on redeploy.

**Resource requirements:** One full-stack engineer (Abhimanyu) as primary implementer. No additional hires assumed for Phase 1. Scope decisions must be realistic against a solo implementation timeline.

---

### Phase 1 — MVP Feature Set (Go-Live with Aman + Admin Profiles)

**Core user journeys supported:**
- Aman's morning visibility loop (dashboard summary, complaint/incident log, pending approvals)
- Aman's crisis complaint handling (severity flagging, incident assignment, resolution thread)
- Adesh's daily operations (staff attendance, substitution, leave approval, student fee status)
- Accountant fee workflow (collection, discount engine, defaulter tracking, contact log)
- Receptionist workflow (visitor log, enquiry, announcements)
- Transport Head workflow (route/vehicle assignment, roster, zone-based grouping)
- IT/Tech workflow (tech request logging and status management)
- Maintenance workflow (facility request logging and status management) ← new profile, full build
- Operator platform health (structured logs, alerts, health endpoint, graceful degradation)

**Must-Have Capabilities:**

| Capability | Notes |
|---|---|
| Full CRUD on all existing tool panels | Correction-with-audit-trail for attendance and fee records |
| Full school database import | Students, staff, fees, attendance history — visible to Owner + Admin from day one |
| Maintenance admin profile | New — full build: role, data model, tool panel, RBAC enforcement, tests |
| Approvals workflow | Any Admin → Owner/Principal dashboard → approve/reject with reason → audit trail |
| Mobile-first for Owner + Principal | iOS Safari + Android Chrome; AI chat usable with keyboard open |
| SSE real-time — staff attendance | Push to Principal + Owner sessions; session dedup; heartbeat; reconnect-on-focus |
| SSE real-time — fee collection summary | Push or ≤30s poll on fee write events |
| Consistent UX states | Loading, empty, error + recovery guidance on every data screen |
| Theme coherence | All tool panels respect dark/light CSS variables — no hardcoded colours |
| S3-backed file storage | Files survive redeployment; existing files migrated and tested on prod copy first |
| Discount policy engine | Configurable rule-based discounts; full calculation breakdown; audit trail on application |
| RBAC enforcement at API layer | Seven admin profile types + Owner + Principal; verified by authorization matrix tests |
| Issue tracker namespace isolation | `tech_request` (IT/Tech) and `facility_request` (Maintenance) — no cross-profile read |
| Audit log scoping | Owner (all), Principal (academic + operational), others (own logs only) |
| AI graceful degradation | Platform functional when Azure OpenAI is unavailable; chat-only surfaces show unavailable state |
| Structured observability | Structured logs to queryable destination + `/api/health/ready` + ≥1 active alert |
| Test baseline | Auth matrix, AI tool-dispatch, fee idempotency, confirm-action, core route tests |
| Timetable management | Principal/Owner creates and manages school timetable; required for substitution workflow |
| Leave request workflow | Staff submit leave requests; Principal approves/rejects; approved leave reflected in substitution availability |
| `schoolId` forward-compatibility | All new/modified data models include `schoolId` field |
| Student route zone (transport) | Route zone stored per student; coordinates field optional/nullable for Phase 2 |

---

### Phase 2 — Growth Features (Post-Pilot, Pre-School #2)

*Triggered after 4 consecutive clean weeks with The Aaryans. Required before pitching school #2.*

| Capability | Trigger |
|---|---|
| Teacher + Student logins activated | Database already loaded; access unlocked post-pilot validation |
| WhatsApp/Twilio integration | Fee reminders and attendance alerts to parents |
| Advanced reporting (Recharts) | Attendance trend charts, fee collection bar charts |
| Token recharge + subscription billing | First revenue event — The Aaryans converts from pilot to paying |
| Platform health dashboard (operator view) | Layaa AI internal monitoring |
| School onboarding flow | New school setup and configuration — required before school #2 |
| Multi-tenancy (schema-per-tenant) | Required before school #2; `schoolId` groundwork laid in Phase 1 |
| Google Maps transport optimisation | Proximity clustering, Distance Matrix API, route map view — when Aman requests it |
| Announcement moderation / approval gate | Required when teachers + students are live and reading Receptionist content |
| AI write rate limiting | Per-session throttle on AI-executed mutations — Phase 1 known gap |

---

### Phase 3 — Vision (Scale)

*EduFlow as the operating system for schools across India.*

- Mobile app (React Native or PWA)
- Parent portal — fee payments, attendance notifications, teacher communication
- API access tier for school integrations
- CBSE/UP Board curriculum intelligence — AI tutoring scoped to board syllabus
- Multi-campus architecture — one owner, multiple branches
- Automated regulatory reporting

---

### Risk Mitigation Strategy

**Technical Risks:**

| Risk | Mitigation |
|---|---|
| Brownfield codebase — unknown debt and existing bugs | Deployment readiness rubric (locked in `DEPLOYMENT_READINESS.md`) provides a structured audit baseline. Score gates go-live. |
| SSE mobile reconnect complexity underestimated | Named as an explicit deliverable. Manual smoke-test on iOS Safari + Android Chrome before go-live. |
| S3 migration corrupts or loses existing files | Migration tested against a copy of production data before running on live. Rollback plan documented. |
| New Maintenance profile introduces RBAC regression | Authorization matrix test suite covers all seven admin profiles × all sensitive endpoints before go-live. |
| Fee idempotency failure causes duplicate records | Dedicated idempotency test; fee software remains source of truth for payment records. |

**Market Risks:**

| Risk | Mitigation |
|---|---|
| Single pilot client — if The Aaryans churns, no revenue signal exists | 4-week clean-run gate enforced before any school #2 pitch. Month-3 retention confirmed before scaling. |
| Aman and Adesh adoption slower than expected | Daily-use target (≥1 action/day) tracked from week 1. If missed by week 2, investigate and fix before the 4-week clock starts. |
| Users bypass chat and use only tool panels | Leading indicator monitored. If chat is consistently avoided, investigate UX friction before declaring the conversational paradigm successful. |

**Resource Risks:**

| Risk | Mitigation |
|---|---|
| Solo implementer — illness or overload delays go-live | Scope is strictly bounded. No scope creep during Phase 1. Growth features are explicitly deferred and documented. |
| Vendor API unavailability (biometric hardware, fee software) | Both integrations are MVP-or-Growth depending on vendor readiness. Platform goes live without them if APIs are not ready — manual workflows cover the gap for Phase 1. |
| Azure OpenAI cost overrun during pilot | Graceful degradation already required. Cost monitoring added to observability scope — at least one alert on daily inference spend threshold. |
| User onboarding gap — staff don't know how to use the platform | Operator (Abhimanyu) responsible for a guided first session with each Phase 1 role before go-live. Absence of training is a pilot risk; must be treated as a go-live prerequisite, not an afterthought. |
| AI write rate limiting (Phase 1 known gap) | Phase 1 explicitly accepts this risk for a single-school controlled rollout with known users and known device count. Risk documented; Growth-phase hardening is a firm commitment. If any session compromise is detected pre-Phase 2, rate limiting is fast-tracked. |

---

## Functional Requirements

*This is the capability contract. UX designers will only design what is listed here. Architects will only support what is listed here. Implementation will only build what is listed here. Any capability not in this list does not exist in the final product.*

*Note: FR19 and FR20 (SSE keepalive interval and reconnect-on-focus behaviour) have been moved to Non-Functional Requirements — they are implementation constraints, not user-facing capabilities.*

---

### 1. Identity & Access

- **FR1:** Any user can log in to EduFlow using email and password credentials
- **FR2:** The system grants each user access to exactly the data and operations permitted by their assigned role, as defined in the RBAC matrix maintained in the architecture specification; the RBAC matrix must be defined and approved before implementation of any role-gated API endpoint begins
- **FR3:** Owner can create, edit, deactivate, and reassign roles for staff accounts; deactivating an account immediately invalidates all active sessions for that user
- **FR4:** The system denies any API request where the caller's role does not have permission for the requested data or operation, regardless of UI state — enforcement is at the API layer, not the frontend
- **FR5:** Each role sees only their permitted data scope — cross-role data access is blocked at the API layer
- **FR6:** The system maintains authenticated sessions and supports concurrent sessions across multiple devices for the same user
- **FR79:** Any user can initiate a password reset via a verified link sent to their registered email address

---

### 2. AI Conversational Interface

- **FR7:** Any authenticated user can submit a natural language query or instruction to the AI and receive a contextually relevant response scoped to their role's permitted data
- **FR8:** The AI can execute data-mutating operations on behalf of the user from a defined set of permitted tool dispatches; the complete dispatch table (intent → tool → required parameters → side effects) is maintained in the architecture specification. **Implementation of FR8 is gated on the architecture specification containing the approved dispatch table — this FR is a scope placeholder until that specification is completed and approved; no AI-executed mutation may be implemented without it.**
- **FR9:** Every data-mutating AI operation must present a confirm-action step to the user showing a plain-language summary of exactly what will change — entity names in the user's operational vocabulary (student name, fee term, class name), not technical identifiers or field names — before any data is written
- **FR10:** The confirm-action step cannot be bypassed; confirmation tokens are single-use and expire after **5 minutes**; replaying an expired or already-used token must not execute any data change
- **FR11:** When Azure OpenAI is unavailable, the platform continues to function fully — tool panels remain operable, all non-AI workflows are unaffected, and the chat interface shows a clear unavailable state
- **FR12:** The AI never reveals one user's data to another user whose role does not permit access to that data
- **FR13:** The AI retrieves structured data (fees, attendance, student records) by querying the live database — it never fabricates or infers data values in responses
- **FR86:** The system maintains an AI dispatch audit log, separate from the general operations audit log, recording: which tool was invoked, with what parameters, by which user, and at what time — for every AI-executed operation
- **FR87:** Confirmation tokens issued for AI-executed write operations are single-use and expire after **5 minutes**; the system enforces this at the API layer independently of the frontend
- **FR88:** All data-mutating API endpoints accept and honour a client-provided idempotency token; submitting the same token a second time returns the original result without re-executing the operation

---

### 3. Attendance Management

- **FR14:** Principal can view real-time staff attendance status, updated automatically when biometric events are received — without a page refresh. If the biometric API is not available at MVP launch, Principal can manually mark individual staff attendance as an interim measure until the integration is active; manual entries are flagged as manually-entered in the audit trail.
- **FR15:** Owner can view real-time staff attendance status
- **FR16:** The system receives processed attendance events from the biometric hardware API and reflects them in the platform without requiring manual data entry
- **FR17:** Attendance records can be corrected with a mandatory reason field; the original record is preserved in the audit trail and not overwritten
- **FR18:** Principal can initiate a substitution assignment when a teacher is absent, selecting from available staff who have no conflicting period in the active timetable; the assigned substitute and affected class are notified of the assignment

---

### 4. Fee Management

- **FR21:** Accountant can record a fee payment against a student's account
- **FR22:** The system prevents duplicate fee submissions using a defined idempotency key (student ID + fee period + fee head); concurrent or retried submissions with the same key return the original record without creating a duplicate entry
- **FR23:** Accountant can view a list of students with fees overdue, filterable by number of days overdue
- **FR24:** Accountant can log a contact event (call, message, visit) against a student's fee record with date, outcome, and notes
- **FR25:** Accountant can configure discount types with a name, value (flat amount or percentage), recurrence (one-time or per-term), and an optional reason note
- **FR26:** Accountant can apply one or more discounts to a student's fee profile; the system displays the original fee amount, each discount applied with its label and value, and the resulting payable amount — no black-box totals
- **FR27:** All discount applications are recorded with who applied them, when, and why
- **FR28:** Fee records can be corrected with a mandatory reason field and full audit trail; financial records are never silently overwritten or deleted
- **FR92:** Discount types configured by the Accountant are reusable — once created, a discount type appears in the discount selection list for any student's fee profile without requiring reconfiguration; the full catalogue of active discount types is manageable (create, rename, deactivate) by the Accountant
- **FR93:** Owner can view a discount impact summary showing aggregate discount commitments across all enrolled students — total expected fee revenue, total discount value applied, and per-discount-type count and aggregate value — to support fee planning decisions
- **FR29:** Owner and Accountant can view a fee collection summary showing total collected, total outstanding, and number of defaulters for a selected period
- **FR30:** Fee collection summary updates within 30 seconds when a payment is recorded
- **FR31:** Principal can view per-student fee status (paid / unpaid / overdue) for academic decision-making
- **FR32:** The system syncs student fee status from the designated fee collection software via a configured API integration on a scheduled interval; when a sync conflict exists (EduFlow record differs from source), a visible discrepancy indicator surfaces for the Accountant to resolve manually. The fee software record is the authoritative source in any conflict; when the Accountant resolves a conflict, the resolution is logged with who resolved it, when, and which value was accepted as correct. The conflict queue must not grow silently — unresolved conflicts older than one sync cycle are escalated to Owner visibility.

---

### 5. Incident, Complaint & Visitor Management

- **FR33:** Receptionist can log a parent or visitor entry with name, purpose, child or staff involved, date and time, and outcome
- **FR34:** Receptionist can log a complaint or incident with a description, severity level (including high-severity), and involved parties
- **FR35:** Owner can view all open complaints, incidents, and visitor logs across the school in a single view
- **FR36:** Owner and Principal can assign a follow-up action on any complaint or incident to a named staff member with a due date
- **FR37:** High-severity incidents trigger an immediate in-app notification to Owner and Principal and are flagged prominently in their dashboards
- **FR38a:** Owner or Principal can add a follow-up entry to any existing complaint or incident record — each entry captures author, timestamp, and content, preserving the full chronological thread without overwriting prior entries
- **FR38b:** The complaint or incident record displays all entries in reverse-chronological order by default, with author and timestamp visible for each entry in a single scrollable thread view
- **FR39:** Owner and Principal can search and retrieve any logged complaint, incident, or visitor record conversationally or via search, by subject, date, person involved, or status

---

### 6. Approvals Workflow

- **FR40:** Any Admin profile can submit an approval request with a title, description, estimated impact or cost, supporting note, and a routing field indicating whether the request requires Owner only or Owner and Principal sign-off
- **FR41:** Submitted approval requests appear in the Owner's dashboard with an unread-count indicator; requests routed for academic sign-off also appear in the Principal's dashboard
- **FR42:** Principal sees and can act on approval requests that the submitting Admin explicitly routed for academic sign-off using the routing field in FR40
- **FR43:** Owner (and Principal where applicable) can approve or reject an approval request with a mandatory reason field
- **FR44:** The submitting Admin receives an in-app notification when their approval request is approved or rejected, including the reason provided
- **FR45:** Every approval request submission, routing decision, approval or rejection, and reason is recorded in the audit log

---

### 7. Transport Management

- **FR46:** Transport Head can create and manage vehicle records including vehicle identifier and passenger capacity
- **FR47:** Transport Head can create and manage route zones covering the school's service area
- **FR48:** Transport Head can assign students to route zones and to specific vehicles
- **FR49:** Transport Head can assign a student to a route zone; the assigned route zone is displayed on the student's transport record and is selectable from the configured list of route zones (FR47). *(Architecture note: the student record schema includes an optional geographic coordinates field, nullable in Phase 1, reserved for Phase 2 route optimisation — no data collection mechanism is required in Phase 1.)*
- **FR50:** Owner and Principal can view the full transport roster and vehicle assignments

---

### 8. Issue Tracking

- **FR51:** IT/Tech admin can log, update, and close tech requests (`tech_request` type) covering hardware, software, network, and device issues
- **FR52:** Maintenance admin can log, update, and close facility requests (`facility_request` type) covering physical facility, furniture, and infrastructure issues; the Owner (not the Maintenance admin) confirms resolution — closure by Maintenance admin marks the request as "pending owner confirmation" until the Owner reviews and confirms the resolution is satisfactory
- **FR53:** IT/Tech admin cannot read Maintenance facility requests and Maintenance admin cannot read IT/Tech tech requests — namespace isolation is enforced at the API layer
- **FR54:** Owner and Principal can view all open issues across both the tech and facility namespaces in a unified view
- **FR55:** At issue intake, a category selector routes the submission to the correct namespace (tech or facility); the submitter can reassign to the other namespace before first action is taken

---

### 9. Announcements

- **FR56:** Receptionist can create an announcement and target it to all logged-in users or to one or more specific role groups
- **FR57:** Each logged-in user sees only announcements targeted to all users or to their specific role group

---

### 10. Student & Staff Records

- **FR77:** Any authorised user (per their role scope) can create, view, edit, and deactivate a student profile including enrolment details, class assignment, contact information, fee profile reference, and route zone
- **FR78:** Any authorised user (per their role scope) can create, view, edit, and deactivate a staff profile including role assignment, contact information, and employment details

---

### 11. Notifications

- **FR80:** The system delivers in-app notifications with an unread-count indicator to the relevant user when: a high-severity incident is logged (Owner + Principal), an approval request is submitted or decided (Owner, Principal, or submitting Admin as applicable), or a follow-up assigned to them is approaching its due date. Tapping the unread-count indicator opens a notification history drawer showing all recent notifications in reverse-chronological order; each notification is tappable and navigates directly to the source record.

---

### 12. Navigation & Discovery

- **FR81:** Any authenticated user can navigate between all capability areas available to their role from a persistent navigation surface accessible from every screen
- **FR82:** Any list view that may contain more than 20 records supports pagination or infinite scroll, and at minimum one column-level sort option

---

### 13. Dashboard Composition

- **FR83:** The Owner dashboard presents a prioritised real-time summary composited as a single first-screen view optimised for mobile, in this explicit priority order: (1) open high-severity incidents, (2) pending approvals with unread count, (3) today's staff attendance status, (4) current fee collection summary

---

### 14. Export & Print

- **FR84:** Accountant can generate and download a printable fee receipt for any recorded payment
- **FR85:** Owner and Principal can export an attendance summary or fee collection summary as a downloadable document

---

### 15. Data Management & Audit

- **FR58:** Owner can monitor and trigger the school database import; the initial import before go-live is performed by the operator (Abhimanyu); the import includes schema validation plus referential integrity checks (student → class exists, staff → role valid, fee record → fee head exists) and surfaces all invalid records before committing any data
- **FR59:** Every data-mutating operation (create, update, correction) records who performed it, when, and what changed
- **FR60:** Audit log visibility is scoped by role: Owner sees all logs across all profiles and operations; Principal sees academic and operational logs, excluding fee correction logs; Admin profiles see only their own operation logs
- **FR61:** Any student record can be subject to a DPDP erasure request, authorised by the Owner role with a mandatory reason field citing the DPDP legal basis; an irreversible pre-deletion audit record is generated before any data is removed. Erasure execution follows a two-track approach to reconcile DPDP right-to-erasure with CBSE 5-year retention obligations: (1) Direct PII fields (name, contact details, parent details, fee history, address) are hard-deleted across all collections; (2) Attendance and academic records containing that student's data are pseudonymized — the student's identifying fields are replaced with a non-reversible anonymized token — so the CBSE-required record structure is preserved without retaining personally identifiable data. This pseudonymization approach satisfies both obligations simultaneously. A legal opinion confirming this interpretation should be obtained before the first erasure request is processed in production.
- **FR62:** Attendance and academic records cannot be hard-deleted under standard operations — only correction-with-audit-trail is available through the normal UI
- **FR89:** Owner, Principal, and Admin profiles (each scoped to their own operation logs only) can view and search their permitted audit log entries through a dedicated UI surface; Owner can view, search, and filter the full audit log across all operations and all profiles

---

### 16. Timetable Management

- **FR90:** Principal (or Owner) can create, edit, view, and import the school timetable defining class, period, subject, and assigned teacher; the timetable is the authoritative source for staff availability checks in the substitution workflow (FR18)

---

### 17. Leave Management

- **FR91:** Teaching and support staff can submit a leave request specifying date range, leave type (sick / casual / planned), and reason; Principal can approve or reject any leave request with a mandatory reason; approved leave is automatically reflected in staff availability for the substitution workflow

---

### 18. *(Section 18 omitted — numbering artifact from an intermediate draft revision; section numbering continues from 17 to 19)*

### 19. File Management

- **FR63:** Any authorised user can upload a file attachment to a relevant record (incident log, approval request, staff profile, student profile, etc.)
- **FR64:** Uploaded files are stored in S3-backed storage and remain accessible across platform redeployments
- **FR65:** Files uploaded before the S3 migration are migrated and remain accessible after the migration completes

---

### 20. Platform Observability & Health

- **FR66:** The platform exposes a `/api/health/ready` endpoint that reflects the live operational status of the backend, with granular indicators for: database connectivity, AI service reachability, biometric API reachability, and background job scheduler status
- **FR67:** Structured logs are shipped to a queryable destination in real time
- **FR68:** At least one active alert notifies the operator (Abhimanyu) when an error rate spike or critical failure condition occurs
- **FR69:** When a third-party integration (biometric API, fee software sync) is unavailable, the platform continues to function and displays a "last updated X time ago" staleness indicator rather than an error state
- **FR70:** AI inference spend is monitored and an alert fires when daily spend exceeds a configured threshold

---

### 21. UX Foundations

- **FR71:** Every screen that displays data shows a loading state while data is being fetched
- **FR72:** Every screen that displays data shows an empty state with contextual guidance when no records exist
- **FR73:** Every screen that displays data shows an error state with recovery guidance when a fetch or write operation fails
- **FR74:** All tool panels render correctly in both light and dark themes without hardcoded colours
- **FR75:** All Owner and Principal views are fully functional on iOS Safari and Android Chrome at mobile viewport sizes; all primary actions are reachable within the top 75% of a 375px-wide portrait viewport (supporting single-thumb use without repositioning the hand); touch targets meet minimum tap-target size (44×44px); priority surfaces (dashboard, chat, incident log, approvals, pending actions) are accessible without horizontal scrolling or zooming
- **FR76:** The AI chat input area and the full conversation viewport (including the confirm-action gate) remain visible and correctly positioned when the mobile keyboard is open

---

*Total: 95 functional requirements across 21 capability areas. (FR38 split into FR38a/b; FR92, FR93, FR94 added.)*

---

### 22. Conditional Requirements (Activate on Client Confirmation)

- **FR94:** *(Conditional — activates if UDISE+ reporting is confirmed as mandatory for The Aaryans)* Owner or a designated Admin can export a UDISE+ submission dataset covering: student enrolment counts by class and gender, aggregate attendance data by term, staff headcount by role, and school infrastructure details — in the format required by the Ministry of Education's annual submission portal. This FR is a placeholder; scope inclusion requires explicit confirmation from Aman before Phase 2 scope is finalised.

---

## Appendix A: Preliminary AI Dispatch Table

*This table defines the MVP set of AI-executable mutations — operations the AI may perform on behalf of a user after passing the confirm-action gate (FR9/FR10). It is derived from the functional requirements and user journey narratives in this PRD. The architecture specification will formalize parameter schemas, error handling, and extend this table for Growth and Vision phases. No operation may be implemented as an AI-dispatched mutation unless it appears in this table or is approved via the architecture specification.*

*FR8 implementation is gated on architecture specification approval. This table satisfies the testability requirement for MVP scope only.*

| # | Tool Name | Intent | Required Parameters | Permitted Roles | Side Effects |
|---|---|---|---|---|---|
| 1 | `assign_followup` | Assign a follow-up action on a complaint or incident to a named staff member | `record_id`, `assignee_staff_id`, `due_date`, `note` | Owner, Principal | Audit log entry; in-app notification to assignee |
| 2 | `update_incident_status` | Update the status of a complaint, incident, or maintenance request | `record_id`, `new_status`, `note` | Owner, Principal, Maintenance Admin (facility only) | Audit log entry; status change visible in dashboard |
| 3 | `add_thread_entry` | Add a follow-up entry to an existing complaint or incident thread | `record_id`, `content` | Owner, Principal | Thread entry created; audit log; original record unchanged |
| 4 | `initiate_substitution` | Approve a substitution assignment for an absent teacher | `absent_staff_id`, `substitute_staff_id`, `class_id`, `period_id` | Principal | Substitution record created; notification to substitute and affected class; audit log |
| 5 | `correct_attendance` | Apply a correction to an existing attendance record with mandatory reason | `record_id`, `correction_type`, `reason` | Principal, Owner | Original record preserved in audit trail; corrected record created; audit log |
| 6 | `log_contact_event` | Log a contact event (call, message, visit) against a student's fee record | `student_id`, `contact_type`, `outcome`, `note` | Accountant | Contact event appended to student fee record; audit log |
| 7 | `apply_discount` | Apply a configured discount type to a student's fee profile | `student_id`, `discount_type_id`, `effective_from` | Accountant | Discount applied to fee profile; updated payable amount calculated; audit log with who applied and when |
| 8 | `decide_approval_request` | Approve or reject a pending approval request with a mandatory reason | `request_id`, `decision` (approve/reject), `reason` | Owner (all); Principal (academic-routed only) | Decision recorded; audit log; notification to submitting Admin |
| 9 | `confirm_resolution` | Owner confirms a facility request marked complete by Maintenance Admin | `request_id`, `confirmation_note` | Owner | Request closed; audit log; Maintenance Admin notified |

**Query dispatches** (no confirm-action gate required — read-only, no data mutation):

| # | Tool Name | Intent | Permitted Roles |
|---|---|---|---|
| Q1 | `query_dashboard_summary` | Composite summary of open incidents, pending approvals, attendance, fee status | Owner |
| Q2 | `query_attendance_status` | Current staff attendance status from biometric feed | Owner, Principal |
| Q3 | `query_fee_status` | Fee status, defaulters, overdue list for a student or cohort | Owner, Accountant, Principal (read-only) |
| Q4 | `query_incidents` | Open complaints, incidents, or visitor logs by status/date/person | Owner, Principal |
| Q5 | `query_staff_availability` | Available staff for a given period, filtered against timetable | Principal |
| Q6 | `query_maintenance_requests` | Open facility requests by status, date, or location | Owner, Maintenance Admin |
| Q7 | `query_student_record` | Student profile, fee profile, transport assignment | Owner, Principal, Accountant (fee scope), Transport Head (transport scope) |
| Q8 | `query_audit_log` | Scoped audit log entries per role (FR89) | Owner (all); others (own logs only) |

---

## Non-Functional Requirements

### Performance

| Requirement | Target | Context |
|---|---|---|
| API response time — standard data operations | p95 ≤ 500ms | Measured from API request receipt to response sent; excludes AI inference calls |
| Tool panel initial load | ≤ 3s to interactive | Measured from API response receipt to interactive UI on a simulated 4G connection (10 Mbps) |
| Fee collection summary refresh | ≤ 30s from payment event | Maximum latency between a recorded payment and the updated summary visible to Accountant or Owner |
| AI chat response — first token | ≤ 3s | Time from user submitting a message to first streamed token appearing |
| File upload confirmation | ≤ 5s for files ≤ 10MB | Upload must surface a success or failure state within this window |
| Database import | ≤ 2 hours for a full school dataset | Background operation; user receives a completion notification |

---

### Security

**Authentication & Session Management**
- All passwords are hashed using bcrypt or equivalent — plaintext passwords are never stored or logged
- Access tokens are short-lived (≤ 1 hour); refresh tokens are revocable; deactivating a user account immediately invalidates all active sessions and refresh tokens for that user
- All client-server communication is over HTTPS/TLS 1.2 or higher; HTTP is not served
- Session cookies are `HttpOnly`, `Secure`, and `SameSite=Strict`

**Confirmation Token Security**
- Confirmation tokens for AI-executed write operations expire after 5 minutes
- Each token is single-use; once consumed or expired, replaying the token must not trigger any data change
- Tokens are bound to the issuing session — a token from session A cannot be consumed by session B

**Data Protection**
- All data is encrypted at rest and in transit
- No PII (student names, contact numbers, addresses, fee amounts, biometric event data) appears in structured log fields — log records reference entity IDs only
- Student PII is never sent to Azure OpenAI as raw data — queries are anonymised or reference IDs before reaching the model
- Biometric data received from hardware API is processed into attendance events; the raw biometric payload is not persisted

**API Security**
- RBAC enforcement is implemented server-side; client-side role checks are UI conveniences only and are never the authoritative gate
- AI chat endpoints are rate-limited per authenticated session — maximum 50,000 tokens consumed per session; this limit is a provisional planning anchor and must be confirmed against observed usage patterns before go-live
- Idempotency tokens are honoured within a 24-hour window from first submission
- Third-party dependencies are pinned to specific versions; no unreviewed auto-updates in production
- File storage is not publicly accessible; all file access uses time-limited authenticated URLs generated per-request (expiry ≤ 1 hour)
- If confirmation token validation is unavailable, write operations are rejected — the confirm-action gate must not be bypassed even when the token service is degraded (fail-closed behaviour is mandatory)
- Log schema is validated in CI to reject log entries containing defined PII field names (student name, contact number, address, fee amount, biometric identifiers) — this check runs on every build before deployment

---

### Reliability

| Requirement | Target |
|---|---|
| Platform availability | ≥ 99.5% monthly uptime, excluding announced maintenance windows |
| Data durability | Zero data loss on redeployment — S3-backed storage and managed database are independent of the application server lifecycle |
| Write operation atomicity | Every write operation either completes fully or fails cleanly with an error surfaced to the user — no silent partial writes |
| Third-party integration isolation | Failure of the biometric API, fee software sync, or Azure OpenAI must not cause platform downtime — each integration degrades independently |
| Deployment continuity | New deployments must not interrupt active user sessions |
| Background job durability | Scheduled jobs (fee sync, notification delivery) retry on transient failure with increasing delay between retries; failed jobs are logged and alertable |
| Database topology | Platform availability target (≥99.5% monthly) requires replica-set database topology — a standalone database instance cannot meet this SLA; the token store (for idempotency and confirm-action tokens) requires a TTL-capable backend (e.g., MongoDB TTL collection or Redis) configured before go-live |

---

### Real-Time Communication (SSE)

*Formerly FR19 and FR20 — moved here as implementation constraints, not user-facing capabilities.*

- The server sends a keepalive event on every active SSE channel every 30 seconds so the client can distinguish a dead connection from a quiet one
- When a browser tab regains visibility after being in the background, the client re-establishes the SSE connection and fetches a fresh state snapshot before resuming the event stream — applies to both the attendance and fee summary channels
- Multiple open tabs for the same authenticated user must not result in duplicate event processing — session deduplication is enforced at the server
- If the upstream data source for an SSE channel is unavailable, the channel remains open and silent rather than erroring — the client shows the "last updated X ago" indicator
- Persistent SSE connections require the hosting platform's HTTP timeout to be configured to ≥300 seconds — the default timeout would otherwise terminate live channels. Implementation approach: CloudFront behaviour-level timeout override on SSE routes, or ALB placement in front of the Amplify origin. This configuration must be applied and verified before go-live; it is not automatic.

---

### Scalability

**Phase 1 — Single School**
- System must support ≥ 100 concurrent authenticated users without degradation in API response times
- System must support ≥ 50 concurrent SSE connections per server instance

**Phase 2 — Multi-School**
- The `schoolId` field in all data models must enable schema-per-tenant partitioning without requiring a breaking schema migration when multi-tenancy is activated
- Fee software sync and biometric integration must support per-school API credentials and sync schedules from the first implementation — this configuration model is built in Phase 1 with a single configured school, not retrofitted when school #2 onboards
- Existing collections must be backfilled with the `schoolId` field before the authorization matrix tests are valid — a query without a `schoolId` filter on a multi-tenant collection cannot be caught by tests on single-tenant data; the backfill must be verified before go-live

**Constraint:** Phase 1 targets a single school with ≤ 20 admin staff concurrently active. Premature horizontal scaling infrastructure is explicitly out of scope.

---

### Integration Quality

| Integration | Reliability Requirement |
|---|---|
| Biometric hardware API | Must tolerate vendor API downtime up to 4 hours without data loss; events received after recovery must be processed in arrival order |
| Fee collection software API | Sync conflicts must be surfaced to the Accountant within one sync cycle; the conflict queue must not grow silently |
| AWS S3 | All file write operations include checksum verification; failed uploads surface a clear error and do not create partial file records |
| Azure OpenAI | Response timeout is 30 seconds; if exceeded, graceful degradation activates automatically; no hanging requests |
| Email (password reset, notifications) | Transactional email is not in the critical path — a failed email delivery must not cause the primary operation to fail; delivery failures are logged |

---

### Data Retention

| Data Category | Minimum Retention | Hard Delete Permitted? |
|---|---|---|
| Attendance and academic records | 5 years (CBSE requirement) | No — correction-with-audit-trail only; hard delete only on verified DPDP erasure request |
| Fee and financial records | 7 years (Indian financial regulations) | No — same as above |
| Student PII | Duration of enrolment + 5 years | Yes — hard delete on verified DPDP erasure request, coordinated across all collections |
| Staff records | Duration of employment + 2 years | Soft delete (deactivation) under standard operations |
| Audit logs (general) | 2 years minimum | No |
| AI dispatch audit logs | 2 years minimum | No |

---

### Browser & Device Support

**Mobile — Owner and Principal (primary interface):**
- iOS Safari — latest 2 major versions
- Android Chrome — latest 2 major versions
- Minimum supported viewport: 375px width (iPhone SE)
- All interactive elements: minimum 44 × 44px touch target
- Portrait orientation is primary; landscape must not break layouts

**Desktop/Tablet — Admin profiles (primary interface):**
- Chrome, Firefox, Safari — latest 2 major versions each
- Minimum supported viewport: 1024px width

**Not supported:** Internet Explorer, pre-Chromium Edge

---

### Accessibility

*EduFlow Phase 1 users are school administration staff, not a broad public audience. Full WCAG 2.1 AA compliance is not required for this release. The following minimums apply:*

- Colour contrast ratio ≥ 4.5:1 for all body text in both light and dark themes
- All interactive elements have a visible focus state for keyboard navigation — minimum 2px solid outline with ≥3:1 contrast ratio against the adjacent background colour
- All form inputs have associated labels — placeholder-only labelling is not acceptable
- No information is conveyed through colour alone

*Screen reader compatibility and full WCAG landmark compliance are deferred to Phase 2 when student and teacher logins go live.*
