---
stepsCompleted: [1, 2, 3, 4]
session_topic: Maintenance Admin profile and tools for The Aaryans school
session_goals: Design comprehensive maintenance workflow tools, escalation from other roles, and notification system
selected_approach: ai-recommended
techniques_used: [six-thinking-hats, cross-pollination, scamper, morphological-analysis]
ideas_generated: 68
---

# Brainstorming Session: School Maintenance Profile
**Date:** 2026-05-13 | **Project:** EduFlow | **User:** Abhimanyusingh

---

## Session Overview

**Topic:** What tools, workflows, and data should a Maintenance Admin have? Plus escalation from Owner/Admin/Teacher with photo attachments and Owner+Principal notifications.

**Context:** Single-campus Indian school, ~20 staff, common issues: broken furniture, plumbing, electrical, AC/exhaust/ventilation, painting, pest control, cleaning supplies.

---

## Phase 1: Six Thinking Hats

### ⚪ White Hat — Facts & Data
1. Maintenance requests currently have no structured lifecycle (open → in-progress → closed)
2. Only maintenance admin can currently create facility requests — no escalation from teachers/owners
3. No photo evidence trail exists for before/after comparison
4. No preventive schedule — everything is reactive
5. ~20 school staff means low ticket volume (5-15 per week), needs simplicity
6. Common categories: furniture, plumbing, electrical, AC/HVAC, painting, pest, cleaning, civil
7. Vendor/contractor calls happen informally — no record
8. Materials consumed per job are never tracked
9. Owner and Principal have no real-time visibility into open issues

### ❤️ Red Hat — Emotions & Intuition
10. Maintenance staff feel invisible — their work goes unacknowledged
11. Teachers get frustrated when a broken chair stays broken for days with no update
12. Principal wants to know "is the school functional today?" at a glance
13. Owner wants accountability — who asked for what, who fixed it, what it cost
14. Quick wins: just being able to say "I raised this, it's in-progress" reduces frustration enormously
15. Photo evidence removes blame games — "it was already like that"

### 🌟 Yellow Hat — Benefits & Optimism
16. Digital tickets create accountability automatically
17. Photo before/after proves work was done — useful for vendor payment disputes
18. Preventive scheduling saves money (catch AC filter before it fails)
19. Vendor log lets school negotiate better rates over time
20. Materials tracker builds a budget history — "we spend ₹8,000/month on supplies"
21. Notification to Owner+Principal means zero surprises at end of day
22. Status updates reduce "is it done yet?" questions to maintenance staff

### ⚫ Black Hat — Risks & Caution
23. Complex UX will be abandoned — maintenance staff may not be tech-savvy
24. Photo uploads drain storage — need S3 + size limits
25. Too many categories create confusion — keep it to 8-10 max
26. Notification overload: every tiny request pinging Owner all day is annoying
27. Preventive scheduling without reminders is useless — needs alerts
28. Vendor info is sensitive — don't expose contact details to all roles

### 💚 Green Hat — Creative Ideas
29. QR code stickers on each asset → scan to raise a request for that specific asset
30. "Daily walkthrough" checklist — maintenance does a morning inspection round
31. Cost estimate field per ticket → Owner approves above ₹X threshold
32. "Repeat issue" flag — same problem recurring on same asset flags it for replacement
33. Maintenance calendar view — see what's due this week at a glance
34. Simple "thumbs up" confirmation from requester when issue is resolved
35. Work history per location (e.g., "Room 4B — 3 issues this month")

### 🔵 Blue Hat — Process & Structure
36. Core flow: Raise Request → Assign/Accept → Update Progress → Mark Done → Notify Requester
37. Priority levels: Critical (safety) / High (disrupts class) / Medium / Low (cosmetic)
38. SLA targets: Critical = same day, High = 2 days, Medium = 1 week, Low = 2 weeks
39. Two creation paths: raised by others (escalation) vs raised by maintenance themselves (scheduled/self-initiated)
40. Status: open → accepted → in_progress → pending_parts → done → verified

---

## Phase 2: Cross-Pollination (Hotel / Hospital / Construction)

### From Hotel Industry (maintenance CMMS)
41. Work order number — printable slip to hand to contractor with job details
42. Location taxonomy: Building > Floor > Room (School: Block > Floor > Room/Area)
43. Asset register with condition score (1–5 stars) updated on each maintenance visit
44. Shift handover log — "These 3 jobs weren't finished, carry forward tomorrow"
45. "Do Not Disturb" flag — room/space is under maintenance, don't schedule classes there

### From Hospital Maintenance (safety-critical)
46. Priority escalation timer — if Critical ticket not accepted in 2 hours, auto-notify Owner
47. Safety checklist before closing electrical/gas jobs
48. "Out of Service" tag on broken equipment — visible in asset register
49. Emergency contact card — maintenance knows who to call for each category (plumber, electrician)
50. Contractor insurance/certification field — know if the vendor is certified

### From Construction Site Management
51. Before/after photo mandatory for jobs above ₹500 cost estimate
52. Daily progress log — brief note per active job, not just on status change
53. Punch list — final walkthrough items before declaring job "done"
54. Materials indent request — submit a list of supplies needed to Owner for approval
55. Defect liability period — track if same issue recurs within 30 days of "fix"

---

## Phase 3: SCAMPER

- **S**ubstitute: Replace WhatsApp messages to maintenance with structured tickets — eliminates lost requests
- **C**ombine: Combine ticket queue + asset tracker + vendor log in one "Maintenance Hub" view
- **A**dapt: Adapt work-order concept — printable/shareable summary per job
- **M**odify: Add "impact" field (how many students/classes affected) to help prioritize
- **P**ut to other uses: Ticket history becomes evidence for annual infrastructure budget ask to management
- **E**liminate: No complex workflows — just: Raise → Accept → Progress → Done → Notify
- **R**everse: Shift from 100% reactive to 20% preventive (scheduled recurring tasks)

---

## Phase 4: Morphological Analysis — Tool Feature Matrix

| Dimension | Option A | Option B | Option C |
|-----------|----------|----------|----------|
| Request creation | Form with fields | AI chat ("fix the AC in room 4") | QR scan on asset |
| Photo evidence | Optional always | Required for high/critical | Required on close |
| Notification | In-app only | In-app + future SMS | Owner+Principal only |
| Priority | 2 levels | 4 levels (Critical/High/Med/Low) | Auto-inferred from category |
| Vendor tracking | None | Name + phone + job type | Full vendor profile |
| Preventive schedule | None | Manual calendar entries | AI-suggested based on asset age |
| Cost tracking | None | Cost estimate per job | Estimate + actual + materials |
| Requester feedback | None | "Resolved?" yes/no | Star rating |

**Selected options:** B, B, B (in-app + Owner+Principal), B (4 levels), A (name+phone), A (manual calendar), B (estimate + materials), A (yes/no) — balanced for a small school

---

## Final Tool List: Maintenance Admin Profile

### Core Tools (Maintenance Admin sees these)

| # | Tool ID | Tool Name | Purpose |
|---|---------|-----------|---------|
| 1 | `maintenance-dashboard` | Maintenance Dashboard | Today's open/critical/in-progress at a glance |
| 2 | `maintenance-requests` | Work Orders | Full ticket queue with filters, priority, category, location |
| 3 | `maintenance-schedule` | Preventive Schedule | Recurring tasks calendar (AC service, pest control dates) |
| 4 | `asset-condition-log` | Asset Register | School assets with condition rating, location, last serviced |
| 5 | `vendor-log` | Vendor Log | Contractors used: name, phone, speciality, last called |
| 6 | `materials-tracker` | Materials Tracker | Supplies used per job + low-stock flag |
| 7 | `query-section` | Query & Support | Help tickets |

### Escalation Tool (Owner + Admin-non-maintenance + Teacher)

| # | Tool ID | Tool Name | Purpose |
|---|---------|-----------|---------|
| 8 | `raise-maintenance` | Raise Maintenance Request | Form: category + description + location + priority + photo upload (up to 3 photos) |

---

## Implementation Decisions

### Backend
- Extend `facility_requests` collection: add `photos[]`, `priority`, `cost_estimate`, `materials_used[]`, `vendor_name`, `vendor_phone`, `assigned_to`
- New collection: `maintenance_schedule` — recurring tasks with `frequency`, `next_due`, `last_done`
- New collection: `school_assets` — asset register with `condition_score`, `location`, `last_serviced`
- New collection: `maintenance_vendors` — vendor directory
- Notification trigger: on any facility_request create → push notification to all `owner` + all `principal` sub_category users
- Status: `open` → `accepted` → `in_progress` → `pending_parts` → `done`

### Frontend
- Fix login: ensure maintenance user exists (migration or seed upsert)
- Rebuild `MaintenanceTools.js` — full featured, 6+ tools
- Add `RaiseMaintenance` component to Owner sidebar tool list + admin (non-maintenance) + teacher sidebar
- Notification integration: call notification API on request create

### Login Fix
- Root cause: `auth_users` document for maintenance user may not exist in live DB (seed was updated but not re-run)
- Fix: add `/api/maintenance/ensure-demo-user` startup hook OR add migration 010
- Better: make seed idempotent with upsert, document re-run instructions

---

## Key Design Principles

1. **Mobile-friendly forms** — maintenance staff log issues from their phone while walking the campus
2. **Photo-first** — 3 photo slots per request (camera icon prominent)
3. **One-tap status update** — don't make maintenance fill out forms to say "done"
4. **No info loss** — if requester is a teacher, maintenance can reply/comment back to them
5. **Owner notification is high-signal, not noisy** — only on NEW requests and status → done transitions
