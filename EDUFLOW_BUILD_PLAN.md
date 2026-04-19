# EduFlow — Final Comprehensive Build Plan
## Probabilistic Understanding + Deterministic Execution

**Architecture:** LLM reads and writes (probabilistic) → Rule engine validates and executes (deterministic)
**Goal:** Zero data leaks, zero hallucinated actions, full decision transparency, 100% accuracy on data operations
**Multi-branch ready:** Single database, branch-scoped queries, unified owner dashboard
**Board support:** CBSE, ICSE, UP Board, Bihar Board curriculum in AI knowledge base
**Status:** Awaiting approval before execution

---

## DESIGN PRINCIPLE: CHAT-FIRST, NOT TOOL-FIRST

Most functionality lives **inside the chat** as natural conversation, not as separate tool panels. Tool panels exist only for complex CRUD interfaces that genuinely need a dedicated UI (like bulk attendance marking or fee receipt printing).

**Rule of thumb:**
- If a user can describe what they want in one sentence → **chat handles it**
- If it needs a form with 5+ fields, drag-drop, or visual grid → **dedicated tool panel**

**Merged tools (chat-native, no separate panel):**

| Instead of separate tool | Handled via chat as |
|--------------------------|---------------------|
| School Pulse + Daily Brief | "How's the school today?" → auto-decides which data to pull |
| Smart Alerts + Health Report | "Any issues?" → combined alert + health response |
| Student Search + Student Profile | "Tell me about Rahul in 4B" → search + profile in one response |
| Fee Summary + Fee Defaulters | "Fee status" → summary with defaulters inline |
| AI Tutor + Doubt Solver | Single chat-based learning assistant for students |
| Career Guidance + Study Planner | Single "My Guide" chat context for students |
| Custom Report Builder + Board Report | "Generate a report on..." → chat builds it |
| Leave Manager + Leave Requests | "Show pending leaves" or "Approve Rajesh's leave" → chat handles both |
| Attendance Overview + Class-wise Attendance | "Attendance for class 4B this week" → one tool internally, one response |

**Remains as dedicated tool panels (needs visual UI):**

| Tool Panel | Why it needs a panel |
|------------|---------------------|
| Student Database | Bulk view, filters, edit/delete, CSV export — table grid |
| Fee Collection | Receipt printing, bulk fee entry, payment mode selection |
| Attendance Recorder | Class grid with Present/Absent/Late toggles per student |
| Timetable | Visual weekly grid, drag-drop slots |
| Assignment Creator | Rich text editor, file attachments, deadline picker |
| File Upload | Drag-drop area, preview, S3 management |
| Settings | Form-based configuration |
| Transport Manager | Route map, stop assignment, vehicle list |
| Library Manager | Book catalog, issue/return scanner, overdue list |
| Inventory Manager | Category tree, stock counts, vendor list |

---

## PHASE 0-A: MULTI-BRANCH ARCHITECTURE

### 0A.1 Branch Collection

```json
{
  "id": "branch-aaryans-joya",
  "name": "The Aaryans - Joya",
  "code": "JOYA",
  "type": "school",              // "school" | "coaching" | "preschool"
  "board": "CBSE",
  "city": "Joya", "state": "Uttar Pradesh",
  "address": "...", "phone": "...",
  "principal_staff_id": "staff-xxx",
  "owner_user_id": "user-owner-001",
  "academic_year": "2025-26",
  "settings": {                   // branch-level settings
    "attendance_threshold": 75,
    "fee_late_penalty_percent": 2,
    "sms_enabled": false
  },
  "is_active": true
}
```

**SSA-Akshat branches:**
1. The Aaryans - Joya (school, CBSE)
2. The Aaryans - Meerut (school, CBSE)
3. SSA Coaching Centre (coaching)

### 0A.2 branch_id on Every Collection

ALL existing collections get `branch_id`. Migration sets default for existing docs. Owner queries can omit branch_id to see all, or filter to one.

---

## PHASE 0-B: HOUSE SYSTEM & STUDENT POSITIONS

### 4 Houses (per branch)

| House | Color | Named After | Motto |
|-------|-------|-------------|-------|
| Shivaji House | Green #22C55E | Chhatrapati Shivaji | Courage and Valor |
| Tagore House | Yellow #EAB308 | Rabindranath Tagore | Creativity and Wisdom |
| Raman House | Red #EF4444 | C.V. Raman | Discovery and Innovation |
| Kalam House | Blue #3B82F6 | APJ Abdul Kalam | Vision and Service |

### Student Positions (complete)

**School-level:** Head Boy, Head Girl, Deputy Head Boy/Girl, School Captain (Sports), Cultural Secretary, Literary Secretary, Discipline Head (Boy/Girl), Environment Secretary, Tech Club Head, Editorial Board Head

**House-level (×4):** House Captain (Boy/Girl), Vice Captain (Boy/Girl), Sports Captain, Cultural Captain, Prefects (4-6)

**Class-level (per section):** Class Monitor (Boy/Girl), Class Prefect/CR, Subject Representative

**Special duty:** Corridor Prefects, Library Prefect, Lab Prefect, Assembly Prefect, Gate Duty Prefect

### House Points System

Categories: `sports`, `cultural`, `academic`, `discipline`, `community_service`
Points awarded by any teacher. Leaderboard visible to all roles.

---

## PHASE 0-C: TRANSPORT SYSTEM

### Collections

**`vehicles` collection:**
```json
{
  "id": "vehicle-001",
  "branch_id": "branch-aaryans-joya",
  "vehicle_number": "UP-14-AB-1234",
  "vehicle_type": "bus",           // "bus" | "van" | "auto"
  "capacity": 40,
  "driver_staff_id": "staff-driver-001",
  "conductor_staff_id": "staff-conductor-001",
  "gps_device_id": null,           // for future GPS integration
  "insurance_expiry": "2027-03-31",
  "fitness_expiry": "2026-12-31",
  "is_active": true
}
```

**`transport_routes` collection:**
```json
{
  "id": "route-001",
  "branch_id": "branch-aaryans-joya",
  "name": "Route 1 - Joya Market → School",
  "vehicle_id": "vehicle-001",
  "stops": [
    {"name": "Joya Market", "pickup_time": "07:15", "drop_time": "14:30", "order": 1},
    {"name": "Gandhi Chowk", "pickup_time": "07:25", "drop_time": "14:20", "order": 2},
    {"name": "School Gate", "pickup_time": "07:45", "drop_time": "14:00", "order": 3}
  ],
  "monthly_fee": 1500,
  "is_active": true
}
```

**`student_transport` collection (student ↔ route mapping):**
```json
{
  "student_id": "student-xxx",
  "route_id": "route-001",
  "stop_name": "Gandhi Chowk",
  "transport_type": "both",        // "pickup" | "drop" | "both"
  "start_date": "2025-04-01",
  "is_active": true
}
```

---

## PHASE 0-D: LIBRARY SYSTEM

### Collections

**`library_books` collection:**
```json
{
  "id": "book-001",
  "branch_id": "branch-aaryans-joya",
  "title": "The Story of My Experiments with Truth",
  "author": "Mahatma Gandhi",
  "isbn": "978-0486245935",
  "category": "biography",         // "fiction" | "non_fiction" | "reference" | "textbook" | "biography" | "science" | "ncert"
  "subject": "social_studies",     // null for non-academic
  "class_range": "9-12",           // age-appropriate range, null for all
  "language": "english",
  "total_copies": 3,
  "available_copies": 2,
  "shelf_location": "A-3-12",
  "accession_numbers": ["ACC001", "ACC002", "ACC003"],
  "is_active": true
}
```

**`library_transactions` collection:**
```json
{
  "id": "lt-001",
  "branch_id": "branch-aaryans-joya",
  "book_id": "book-001",
  "accession_number": "ACC001",
  "borrower_type": "student",       // "student" | "staff"
  "borrower_id": "student-xxx",
  "issued_by_staff_id": "staff-librarian-001",
  "issue_date": "2026-03-01",
  "due_date": "2026-03-15",
  "return_date": null,              // null = not returned yet
  "fine_amount": 0,
  "status": "issued"                // "issued" | "returned" | "overdue" | "lost"
}
```

### Library Rules (deterministic)
- Students: max 2 books at a time, 14-day loan period
- Teachers: max 5 books, 30-day loan period
- Overdue fine: ₹2/day (configurable per branch)
- Lost book: replacement cost + ₹50 processing fee
- NCERT/textbook copies: reference only (no issue)

---

## PHASE 0-E: INVENTORY & VENDOR MANAGEMENT

### Collections

**`inventory_items` collection:**
```json
{
  "id": "inv-001",
  "branch_id": "branch-aaryans-joya",
  "name": "Student Desk (Double)",
  "category": "furniture",          // See categories below
  "sub_category": "classroom",
  "quantity": 120,
  "unit": "pieces",
  "condition": "good",             // "new" | "good" | "fair" | "damaged" | "disposed"
  "location": "Building A, All Classrooms",
  "purchase_date": "2023-06-15",
  "purchase_price": 2500,
  "vendor_id": "vendor-001",
  "warranty_expiry": "2026-06-15",
  "last_audit_date": "2026-01-10",
  "notes": "",
  "is_active": true
}
```

**Inventory categories:**
```
furniture       → classroom (desks, chairs, tables, boards), office, lab, library, staff room
it_equipment    → computers, projectors, printers, smart_class, servers, networking
lab_equipment   → physics, chemistry, biology, computer_lab
sports          → cricket, football, volleyball, basketball, athletics, indoor_games
library         → tracked separately in library_books collection
stationery      → chalk, markers, registers, paper, files
cleaning        → brooms, mops, dustbins, sanitizer, cleaning_liquid
medical         → first_aid, medicines, equipment
uniform_store   → if school sells uniforms
electrical      → fans, lights, switches, wiring
infrastructure  → water_tanks, generators, pumps, solar_panels
```

**`vendors` collection:**
```json
{
  "id": "vendor-001",
  "branch_id": "branch-aaryans-joya",
  "name": "Sharma Furniture Works",
  "category": "furniture",
  "contact_person": "Rakesh Sharma",
  "phone": "9876543210",
  "email": "rakesh@sharma.com",
  "address": "Industrial Area, Joya",
  "gstin": "09XXXXX1234X1Z5",
  "payment_terms": "50% advance, 50% on delivery",
  "rating": 4,                      // 1-5
  "total_orders": 12,
  "total_amount_paid": 450000,
  "last_order_date": "2026-02-20",
  "is_active": true
}
```

**`purchase_orders` collection:**
```json
{
  "id": "po-001",
  "branch_id": "branch-aaryans-joya",
  "vendor_id": "vendor-001",
  "items": [
    {"inventory_item_id": "inv-001", "description": "Student Desk Double", "quantity": 20, "unit_price": 2500, "total": 50000}
  ],
  "subtotal": 50000,
  "gst_amount": 9000,
  "total_amount": 59000,
  "status": "delivered",             // "draft" | "approved" | "ordered" | "delivered" | "cancelled"
  "approved_by_staff_id": "staff-owner",
  "order_date": "2026-02-15",
  "delivery_date": "2026-02-20",
  "payment_status": "paid",          // "pending" | "partial" | "paid"
  "created_by_staff_id": "staff-admin"
}
```

---

## PHASE 0-F: FEE STRUCTURE WITH DYNAMIC DISCOUNTS

### Enhanced Fee Structure

```json
// fee_structures collection (enhanced)
{
  "id": "fs-001",
  "branch_id": "branch-aaryans-joya",
  "academic_year": "2025-26",
  "class_group": "1-5",             // "nursery-ukg" | "1-5" | "6-8" | "9-10" | "11-12"
  "fee_components": [
    {"name": "Tuition Fee", "amount": 3000, "frequency": "monthly", "is_mandatory": true},
    {"name": "Annual Charges", "amount": 5000, "frequency": "annual", "is_mandatory": true},
    {"name": "Transport Fee", "amount": 1500, "frequency": "monthly", "is_mandatory": false},
    {"name": "Computer Lab", "amount": 500, "frequency": "quarterly", "is_mandatory": true},
    {"name": "Smart Class", "amount": 300, "frequency": "monthly", "is_mandatory": false},
    {"name": "Activity Fee", "amount": 2000, "frequency": "annual", "is_mandatory": true}
  ],
  "total_annual": 52000
}
```

### Dynamic Discount System

```json
// fee_discounts collection (new)
{
  "id": "fd-001",
  "branch_id": "branch-aaryans-joya",
  "name": "Sibling Discount (2 siblings)",
  "discount_type": "sibling",       // See types below
  "discount_mode": "percentage",     // "percentage" | "fixed_amount"
  "discount_value": 10,             // 10%
  "conditions": {
    "sibling_count": 2,             // exactly 2 siblings enrolled
    "applies_to": "younger",        // "younger" | "all" | "eldest"
    "max_discount": 5000            // cap per year
  },
  "applicable_components": ["tuition"],  // which fee components, null = all
  "is_active": true,
  "academic_year": "2025-26"
}
```

**Discount types:**
```
sibling              → 2 siblings: 10% on younger. 3 siblings: 15% each. 4+: 20% each.
staff_child          → Children of teaching staff: 50% off tuition
staff_relative       → Known of staff member: 5-10% (custom per case)
merit_scholarship    → Academic excellence: up to 100% tuition waiver
sports_scholarship   → Sports achievement: 25-50% off
financial_hardship   → Case-by-case: 10-100% (requires owner approval)
early_payment        → Full year paid by April 30: 5% off
single_parent        → 10% off tuition
defence_ward         → Armed forces family: 15% off
custom               → Free-text reason + custom amount (owner approval needed)
```

### Student Fee Profile

```json
// student_fee_profile (embedded in students or separate collection)
{
  "student_id": "student-xxx",
  "fee_structure_id": "fs-001",
  "applied_discounts": [
    {"discount_id": "fd-001", "name": "Sibling Discount", "percentage": 10, "annual_savings": 3600},
    {"discount_id": "fd-custom-001", "name": "Principal's Discretion", "fixed_amount": 2000, "reason": "Financial hardship"}
  ],
  "net_annual_fee": 46400,          // 52000 - 3600 - 2000
  "sibling_ids": ["student-yyy"],   // linked siblings for auto-discount
  "custom_notes": "Father is school bus driver. Approved by Aman Sir.",
  "approved_by": "staff-owner"
}
```

---

## PHASE 0-G: SCHOOL EVENTS & ACTIVITIES

### Collections

**`school_events` collection:**
```json
{
  "id": "event-001",
  "branch_id": "branch-aaryans-joya",
  "name": "Annual Sports Day 2026",
  "type": "sports_day",
  "category": "annual",            // "annual" | "national" | "cultural" | "academic" | "competition" | "external"
  "date_start": "2026-02-20",
  "date_end": "2026-02-21",
  "time_start": "08:00",
  "time_end": "14:00",
  "venue": "School Ground",
  "description": "Inter-house sports competition",
  "organizer_staff_id": "staff-sports-teacher",
  "participating_houses": ["house-green", "house-yellow", "house-red", "house-blue"],
  "participating_classes": [],      // empty = all classes
  "budget": 50000,
  "actual_spend": null,
  "results": null,                  // filled after event
  "photos_album_id": null,
  "status": "upcoming",            // "upcoming" | "ongoing" | "completed" | "cancelled"
  "is_public": true                 // visible to parents/students
}
```

**Standard school events (pre-seeded per academic year):**

| Event | Date | Category | Type |
|-------|------|----------|------|
| Independence Day | Aug 15 | national | flag_hoisting, cultural_program |
| Teachers' Day | Sep 5 | national | cultural_program |
| Gandhi Jayanti | Oct 2 | national | special_assembly |
| Children's Day | Nov 14 | national | fun_activities |
| Republic Day | Jan 26 | national | flag_hoisting, parade |
| Annual Day / Annual Function | Dec/Jan | annual | stage_performance |
| Sports Day / Sports Meet | Feb | annual | inter_house_sports |
| Science Exhibition | Nov | academic | project_display |
| Art Competition | Oct | cultural | drawing, painting |
| Inter-School Tournament | Varies | competition | cricket, football, etc. |
| Parent-Teacher Meeting | Quarterly | academic | discussion |
| Exam Week (Unit Test / Half-Yearly / Final) | As per calendar | academic | examination |
| Diwali Celebration | Oct/Nov | cultural | rangoli, diya |
| Holi Celebration | Mar | cultural | colors, music |
| Christmas Celebration | Dec | cultural | carol, skit |
| Raksha Bandhan | Aug | cultural | craft_activity |

### Sports Teams

**`sports_teams` collection:**
```json
{
  "id": "team-cricket-u14",
  "branch_id": "branch-aaryans-joya",
  "sport": "cricket",              // "cricket" | "football" | "volleyball" | "basketball" | "kabaddi" | "kho_kho" | "badminton" | "table_tennis" | "athletics" | "chess"
  "age_group": "under_14",         // "under_10" | "under_14" | "under_17" | "open"
  "gender": "boys",                // "boys" | "girls" | "mixed"
  "coach_staff_id": "staff-sports-teacher",
  "captain_student_id": "student-xxx",
  "vice_captain_student_id": "student-yyy",
  "members": ["student-xxx", "student-yyy", ...],
  "achievements": [
    {"event": "District Cricket Tournament 2025", "result": "Runner-up", "date": "2025-11-15"}
  ],
  "academic_year": "2025-26"
}
```

### Co-Curricular Activities / Clubs

```
Art Club, Music Club, Dance Club, Drama/Theatre Club, Debate Club,
Science Club, Math Club, Eco Club, Literary Club (Hindi/English),
Computer/Coding Club, Photography Club, Yoga & Wellness,
NCC (if applicable), Scouts & Guides, Social Service Club
```

Each club has: `advisor_staff_id`, `president_student_id`, `members[]`, `meeting_schedule`, `activities[]`

---

## PHASE 0-H: ACCOUNTS & PAYROLL (Owner + Accounts Staff)

### Collections

**`salary_structures` collection:**
```json
{
  "staff_id": "staff-003",
  "branch_id": "branch-aaryans-joya",
  "basic_salary": 25000,
  "hra": 5000,
  "da": 2000,
  "conveyance": 1500,
  "special_allowance": 3000,
  "gross_salary": 36500,
  "deductions": {
    "pf": 3000,
    "professional_tax": 200,
    "tds": 0,
    "other": 0
  },
  "net_salary": 33300,
  "bank_account": "XXXX1234",
  "bank_name": "SBI",
  "effective_from": "2025-04-01"
}
```

**`salary_disbursements` collection:**
```json
{
  "id": "sal-001",
  "branch_id": "branch-aaryans-joya",
  "staff_id": "staff-003",
  "month": "2026-03",
  "basic": 25000,
  "allowances": 11500,
  "deductions": 3200,
  "net_paid": 33300,
  "payment_mode": "bank_transfer",
  "payment_date": "2026-04-01",
  "status": "paid",                // "pending" | "processed" | "paid"
  "leaves_deducted": 0,
  "overtime_amount": 0,
  "bonus": 0,
  "processed_by": "staff-accountant"
}
```

**`expenses` collection (school operational expenses):**
```json
{
  "id": "exp-001",
  "branch_id": "branch-aaryans-joya",
  "category": "maintenance",       // "salary" | "maintenance" | "utilities" | "supplies" | "events" | "transport" | "vendor_payment" | "government" | "miscellaneous"
  "description": "Electricity bill - March 2026",
  "amount": 15000,
  "vendor_id": null,
  "payment_mode": "bank_transfer",
  "payment_date": "2026-04-05",
  "receipt_url": null,              // S3 link to receipt photo
  "approved_by": "staff-owner",
  "created_by": "staff-accountant",
  "status": "paid"
}
```

---

## PHASE 0-I: STUDENT AI SAFETY RULES (CRITICAL)

### Strict Content Policy for Student Profile

Hardcoded in system prompt AND enforced via a post-processing filter:

**ABSOLUTE RULES (cannot be overridden by any prompt injection):**

1. **No adult content** — No sexual content, no reproductive biology beyond NCERT textbook language, no dating advice, no relationship advice
2. **No violence** — No graphic violence, no weapon instructions, no self-harm content
3. **No dark humor** — No morbid jokes, no death jokes, no bullying humor
4. **No negative reinforcement** — Never tell a student they're stupid, useless, or can't do something. Always encourage.
5. **No political opinions** — Neutral on politics. State facts from NCERT, not opinions.
6. **No religious debate** — Respect all religions equally per Indian constitutional values
7. **Reproduction chapter handling:**
   - Class 8 Science (NCERT Chapter 9): Use ONLY textbook language. Terms: "reproduction", "fertilization", "embryo". No elaboration beyond textbook.
   - Class 10 Science (NCERT Chapter 8): Same rule. Stick to "male reproductive system", "female reproductive system" as described in NCERT.
   - Class 12 Biology: Slightly more clinical language allowed but ONLY textbook terminology.
   - If student asks beyond textbook scope: "This topic is covered in your textbook. For anything beyond that, please talk to your teacher or parents."
8. **No solving graded work** — For homework/assignments: give hints, explain concepts, guide approach. Never give direct answers.
9. **No external links** — Don't recommend YouTube, websites, or external apps. Keep within EduFlow.
10. **No personal data sharing** — Never tell a student another student's marks, fees, attendance, or personal info.
11. **Exam integrity** — During exam periods, refuse to help with any question that looks like an active exam question.

### Post-Processing Content Filter

```python
# backend/ai/content_filter.py (new)
BLOCKED_TOPICS = [
    "suicide", "self-harm", "drugs", "alcohol", "smoking",
    "pornography", "xxx", "sex position", "nude",
    "weapon", "bomb", "gun", "knife attack",
    "hack", "crack", "pirate", "torrent",
    "cheat code", "answer key", "solve my paper",
]

def filter_student_response(text: str, role: str) -> str:
    if role != "student":
        return text
    text_lower = text.lower()
    for topic in BLOCKED_TOPICS:
        if topic in text_lower:
            return "I can only help with school-related topics and studies. For this question, please talk to your teacher or parents."
    return text
```

---

## PHASE 0-J: CURRICULUM KNOWLEDGE BASE

### Board-Specific Curriculum Data

The AI needs to know the syllabus to help students effectively. Store as structured data, not just in the LLM's training data.

**`curriculum` collection:**
```json
{
  "board": "CBSE",
  "class": 10,
  "subject": "Science",
  "chapters": [
    {"number": 1, "name": "Chemical Reactions and Equations", "topics": ["combination", "decomposition", "displacement", "redox"]},
    {"number": 2, "name": "Acids, Bases and Salts", "topics": ["pH scale", "indicators", "neutralization"]},
    ...
    {"number": 8, "name": "How do Organisms Reproduce?", "topics": ["asexual reproduction", "sexual reproduction", "human reproductive system"], "content_flag": "sensitive_medical"},
    ...
  ],
  "textbook": "NCERT Science Class 10",
  "academic_year": "2025-26"
}
```

**Boards to cover:**
- CBSE (all classes Nursery-12)
- ICSE/ISC (all classes)
- UP Board (Classes 9-12)
- Bihar Board / BSEB (Classes 9-12)

**How AI uses it:**
- Student asks "What's in Chapter 5 of Science?" → AI looks up curriculum for their class + board
- Teacher asks "Create an assignment for Class 10 Science Chapter 3" → AI knows the topics
- Content filter checks `content_flag: "sensitive_medical"` → applies strict language rules

---

## STAFF SCHEMA & SUB-CATEGORIES (Phase 0-Staff — unchanged from previous version)

[Retained from previous plan — full hierarchy: Owner → Principal → HODs/Coordinators/Class Teachers/Subject Teachers/KG Incharges + Admin sub-categories + Support staff + Transport]

---

## DATA HIERARCHY & ACCESS CONTROL MATRIX (Enhanced)

### Who Can See What — Full Matrix

| Data | Owner | Principal | Accounts | Transport Head | Receptionist | Support Staff | HOD | Coordinator | Class Teacher | Subject Teacher | KG Incharge | Student |
|------|-------|-----------|----------|----------------|--------------|---------------|-----|-------------|---------------|-----------------|-------------|---------|
| All students | All | All | Names+fees | Bus students | Basic | None | Subject classes | Range classes | Own class | Assigned classes | Own KG | Self |
| Attendance | All | All | None | None | None | Self | Subject classes | Range classes | Own class | None | Own KG | Self |
| Fees | All | All | All | None | None | None | None | None | None | None | None | Self |
| Results | All | All | None | None | None | None | Subject classes | Range classes | Own class | Assigned subject | Own KG | Self |
| Staff data | All | All | Accounts team | Transport team | None | Self | Subject teachers | Range teachers | None | None | KG teachers | None |
| Salaries | Finance tool | None | Payroll view | None | None | None | None | None | None | None | None | None |
| Leaves | All | All | None | Transport | None | Self | None | None | Self | Self | Self | None |
| Fee structures | All | All | All | None | None | None | None | None | None | None | None | Own class |
| Financial reports | All | None | Partial | None | None | None | None | None | None | None | None | None |
| Enquiries | All | All | None | None | All | None | None | None | None | None | None | None |
| Inventory | All | All | Accounts view | Transport items | None | None | Lab equip | None | None | None | None | None |
| Library | All | All | Fine amounts | None | None | None | All | All | Own class | Assigned | Own KG | Self |
| Transport | All | All | Fee data | All | None | None | None | None | None | None | None | Own route |
| Vendors | All | All | All | None | None | None | None | None | None | None | None | None |
| Purchase orders | All | Approval | Processing | None | None | None | None | None | None | None | None | None |
| Salary disbursements | All | None | Processing | None | None | None | None | None | None | None | None | None |
| Events calendar | All | All | All | All | All | All | All | All | All | All | All | Public |
| House standings | All | All | None | None | None | None | All | All | All | All | All | All |
| Sports teams | All | All | None | None | None | None | Sports teacher | Range | Own class | Sports | None | Own team |
| School settings | All | None | None | None | None | None | None | None | None | None | None | None |

### Sub-categories WITHOUT platform access (data-only)

These staff members don't log in. Their data exists for admin reference:

- Peon, Aaya, Sweeper, Guard, Gardener → attendance + salary tracked by admin/accounts
- Drivers, Conductors → attendance + salary + route assignment tracked by transport head
- Medical staff → attendance + salary tracked

---

## CONFLICT PREVENTION RULES (Tool Clashes)

| Conflict Scenario | Resolution |
|-------------------|------------|
| Teacher creates assignment via Assignment Creator → Student asks AI Tutor to solve it | AI Tutor gives hints and explanations, NEVER direct answers. Detects assignment questions by matching against `assignments` collection. |
| Two teachers mark attendance for same class | Only class teacher can mark. Subject teacher attendance is separate (period-wise, if tracked). System rejects duplicate daily attendance. |
| Accounts processes fee → Owner also tries from chat | Both use same `fee_transactions` collection. Optimistic locking: check `updated_at` before write. |
| Student asks about another student's marks | Scope resolver returns ONLY self data. Even if student guesses an ID, the query filter blocks it. |
| Admin approves leave → Owner also tries | First approval wins. Second sees "Already processed by [name]". |
| Chat-based fee query → Fee Collection panel | Both read same data. No conflict — reads are safe. Writes go through same service layer. |

---

## TOOL PANELS VS CHAT CAPABILITIES

### Dedicated Tool Panels (10 — need visual UI)

| Panel | Roles | Why it needs a panel |
|-------|-------|---------------------|
| Student Database | owner, admin | Bulk table, filters, edit, CSV export |
| Fee Collection | owner, admin, accounts | Receipt printing, bulk entry, payment mode |
| Attendance Recorder | owner, admin, teacher | Per-student grid with toggle buttons |
| Timetable | owner, admin, teacher | Visual weekly grid, drag-drop |
| Assignment Manager | teacher | Rich text editor, file attachments, grading |
| Transport Manager | owner, admin, transport_head | Route map, vehicle list, stop assignment |
| Library Manager | owner, admin, librarian | Book catalog, barcode scan, issue/return |
| Inventory Manager | owner, admin, accounts | Category tree, stock counts, vendor orders |
| Settings | owner | School config, thresholds, SMS, integrations |
| File Upload | all (role-filtered) | Drag-drop, preview, S3 storage |

### Chat-Native Capabilities (everything else — no separate panel)

The chat handles these by calling internal tools server-side:

**Owner/Admin chat can:**
- Query any data: "How many students in class 4B?", "Who owes fees?", "Staff absent today?"
- Generate reports: "End of day report", "This month's financial summary", "Attendance trend for last 30 days"
- Approve/reject: "Approve Rajesh's leave", "Reject the purchase order for desks"
- School pulse: "How's the school?", "Any issues today?"
- Fee queries: "What's the fee structure for class 9?", "How much discount does Rahul get?"
- Vendor queries: "Who supplies our lab equipment?", "When was the last furniture order?"
- Event queries: "What's coming up this month?", "When is Sports Day?"
- Library: "Which books are overdue?", "How many books does the library have?"
- Transport: "Which bus route covers Gandhi Chowk?", "How many students use transport?"
- House standings: "Which house is leading?", "Give 10 points to Shivaji house for Rahul's win"
- Inventory: "How many projectors do we have?", "When does the computer lab warranty expire?"
- Student council: "Who is Head Boy this year?", "List all prefects"
- Cross-branch: "Compare attendance between Joya and Meerut branches"

**Teacher chat can:**
- Own class queries: "Show my class attendance today", "Who's absent in 4B?"
- Assignment help: "Create a Math worksheet for Class 9 on Quadratic Equations"
- Student info: "Tell me about Rahul's attendance pattern" (own class only)
- House points: "Give 5 points to Kalam House for Sneha's debate performance"
- Own schedule: "What's my timetable tomorrow?"
- Own leaves: "How many casual leaves do I have left?"
- Library: "Which students from my class have overdue books?"

**Student chat can (AI Tutor mode):**
- Ask doubts: "Explain photosynthesis", "What is the Pythagorean theorem?"
- Curriculum-aware: "What topics are in Chapter 5 of Maths?"
- Study planning: "Help me make a study plan for finals"
- Own data: "What's my attendance?", "Did my fees get paid?", "What are my marks?"
- Assignments: "What homework do I have?" (but NOT "solve my homework")
- Library: "Which books do I have issued?"
- House: "How many points does my house have?"
- Events: "When is the next holiday?"

---

## EXECUTION ORDER (Final — 18 Steps)

| Step | Phase | What | Priority | Effort |
|------|-------|------|----------|--------|
| 1 | 0-A | Multi-branch: `branches` collection, `branch_id` on all collections | P0 | L |
| 2 | 0-B | Houses + student positions: collections, schema, seed | P0 | M |
| 3 | 0-Staff | Staff schema upgrade + sub-categories + hierarchy | P0 | L |
| 4 | 0-C | Transport: `vehicles`, `transport_routes`, `student_transport` | P0 | M |
| 5 | 0-D | Library: `library_books`, `library_transactions` | P0 | M |
| 6 | 0-E | Inventory + vendors: `inventory_items`, `vendors`, `purchase_orders` | P0 | M |
| 7 | 0-F | Fee discounts: `fee_discounts`, `student_fee_profile` | P0 | M |
| 8 | 0-G | Events + sports teams + clubs | P1 | M |
| 9 | 0-H | Accounts + payroll: salary structures, disbursements, expenses | P0 | L |
| 10 | 0-I | Student AI safety: content filter + blocked topics | P0 | S |
| 11 | 0-J | Curriculum KB: CBSE, ICSE, UP Board, Bihar Board syllabus data | P1 | L |
| 12 | 1.1-1.8 | Bug fixes (8 items) | P0 | M |
| 13 | Scope | Scope resolver with branch + sub-category + all new collections | P0 | L |
| 14 | Prompts | System prompt rewrite: 30+ internal tools, full hierarchy, safety rules, curriculum | P0 | L |
| 15 | Tools | All chat-callable tools (data + write + house + transport + library + inventory) | P0 | XL |
| 16 | Params | LLM parameter extraction + resolution for all entities | P0 | M |
| 17 | SSE | Thinking events + ThinkingProcess.js + ChatInterface update | P0 | M |
| 18 | Extras | Confirm actions, navigate events, multi-tool chaining, frontend polish | P1 | L |

---

## NEW MONGODB COLLECTIONS (Summary)

| Collection | Purpose | Documents |
|------------|---------|-----------|
| `branches` | School campuses | 3 (Joya + Meerut + Coaching) |
| `houses` | House system per branch | 4 per branch = 12 |
| `house_points` | Point awards | Grows over time |
| `vehicles` | School buses/vans | ~5-10 per branch |
| `transport_routes` | Bus routes with stops | ~5-10 per branch |
| `student_transport` | Student ↔ route mapping | 1 per transported student |
| `library_books` | Book catalog | ~500-2000 per branch |
| `library_transactions` | Issue/return log | Grows over time |
| `inventory_items` | School assets | ~200-500 per branch |
| `vendors` | Supplier directory | ~20-50 |
| `purchase_orders` | Procurement | Grows over time |
| `fee_discounts` | Discount rules | ~10-15 types |
| `student_fee_profiles` | Per-student fee + discounts | 1 per student |
| `salary_structures` | Staff pay structure | 1 per staff |
| `salary_disbursements` | Monthly salary records | 1 per staff per month |
| `expenses` | School expenses | Grows over time |
| `school_events` | Annual events calendar | ~20-30 per year |
| `sports_teams` | Sport team rosters | ~10-15 per branch |
| `clubs` | Co-curricular clubs | ~10-15 per branch |
| `curriculum` | Board-wise syllabus | ~200 entries (all boards × classes × subjects) |

**Total new collections: 20**
**Existing collections: 15+**
**Grand total: 35+ collections**

---

## PHASE 0-K: PERSONAL INFO ACCESS — HIERARCHICAL VISIBILITY

### Principle: Only Your Direct Superior Sees Your Personal Info

Personal info = phone, address, DOB, guardian details, emergency contact, Aadhaar (last 4), bank details, medical info.

**NOT personal info** (visible to broader roles): name, class/section, attendance %, fee status (paid/unpaid — not amount details), house, positions held.

### Access Rules (hardcoded in scope resolver)

```
PERSONAL INFO VISIBILITY:
Owner         → Can see personal info of: ALL (everyone in the school)
Principal     → Can see personal info of: All staff (except owner), all students
HOD           → Can see personal info of: Teachers in their subject
Coordinator   → Can see personal info of: Teachers + students in their class range
KG Incharge   → Can see personal info of: KG teachers + students in their KG class
Class Teacher → Can see personal info of: Students in their class-section only
Subject Teacher → CANNOT see personal info (only academic data: results, assignments)
Transport Head → Can see personal info of: Drivers + conductors only
Accounts      → Can see personal info of: NONE (only financial data — amounts, not personal)
All others    → Can see personal info of: SELF ONLY
Student       → Can see: OWN personal info + class collective analytics (no names attached)
```

### Student Collective Analytics (what students CAN see)

Students can see **anonymized class/school-level data** — never individual data of other students:

- "Class 9-A average attendance: 92%" (no names)
- "Your attendance: 88% — class rank: 15/40" (own rank, not others')
- "School topper scored 95% in Maths" (name shown ONLY if school policy allows — configurable)
- "Your class average in Science: 72%. Your score: 78%. You're above average." (comparative, not naming others)
- House standings (aggregate points, not individual contributors — unless points are public)

### Financial Data — Special Access

| Data Type | Owner | Accounts | Principal | Others |
|-----------|-------|----------|-----------|--------|
| Staff salaries (individual) | Yes | Yes (payroll processing) | No | No |
| Salary structures (all) | Yes | Yes | No | No |
| Fee transactions (all) | Yes | Yes | No | No |
| Fee discounts (who gets what) | Yes | Yes | No | No |
| Expense records | Yes | Yes | No | No |
| Revenue reports | Yes | Yes (partial) | No | No |
| Purchase orders (amounts) | Yes | Yes | Yes (approval) | No |
| Student fee — own | Yes | Yes | No | Student (self only) |
| Token recharge revenue | Layaa AI admin only (see Phase 0-L) | No | No | No |

### Implementation in Scope Resolver

```python
async def can_see_personal_info(viewer: dict, target_staff_or_student: dict, db) -> bool:
    """Deterministic check: can viewer see target's personal info?"""
    viewer_role = viewer.get("role")
    viewer_staff = await db.staff.find_one({"user_id": viewer["id"]})
    
    if viewer_role == "owner":
        return True
    
    if viewer_role == "admin":
        sub_cat = viewer_staff.get("sub_category") if viewer_staff else "admin"
        if sub_cat == "principal":
            return True  # principal sees all staff + students personal info
        if sub_cat == "transport_head":
            # only transport team personal info
            target_dept = target_staff_or_student.get("department")
            return target_dept == "transport"
        if sub_cat == "accountant":
            return False  # accounts sees financial data only, not personal
        return False  # receptionist, medical, support → self only
    
    if viewer_role == "teacher":
        designation = viewer_staff.get("designation") if viewer_staff else "teacher"
        if designation == "hod":
            # teachers in their subject
            return target_staff_or_student.get("subject") == viewer_staff.get("subject")
        if designation == "coordinator":
            # staff + students in their class range
            return is_in_class_range(target_staff_or_student, viewer_staff.get("coordinator_range"))
        if viewer_staff and viewer_staff.get("is_class_teacher"):
            # students in their class-section only
            return target_staff_or_student.get("class_id") == viewer_staff.get("class_teacher_of")
        return False  # subject teacher → no personal info access
    
    return False  # student → self only (handled separately)
```

---

## PHASE 0-L: TOKEN RECHARGE & SUBSCRIPTION SYSTEM

### Subscription Plans (school-level)

```json
// subscription_plans (static config, not in DB — hardcoded or in settings)
{
  "plans": [
    {
      "id": "starter",
      "name": "Starter",
      "monthly_price": 2999,
      "included_tokens": 500000,
      "max_users": 50,
      "features": ["chat", "attendance", "fees", "basic_reports"],
      "ai_tutor": false,
      "multi_branch": false
    },
    {
      "id": "growth",
      "name": "Growth",
      "monthly_price": 7999,
      "included_tokens": 2000000,
      "max_users": 200,
      "features": ["all_starter", "ai_tutor", "library", "transport", "inventory", "advanced_reports"],
      "ai_tutor": true,
      "multi_branch": false
    },
    {
      "id": "enterprise",
      "name": "Enterprise",
      "monthly_price": 14999,
      "included_tokens": 5000000,
      "max_users": "unlimited",
      "features": ["all_growth", "multi_branch", "payroll", "custom_forms", "api_access", "priority_support"],
      "ai_tutor": true,
      "multi_branch": true
    }
  ]
}
```

### Subscription Plans — Derived from Layaa AI Hybrid Pricing Framework

**Pricing methodology:** Hybrid model (Cost-Plus Floor + Value-Based Ceiling) from Layaa AI's pricing framework.

**Floor calculation (Stage 1 rates, AI-assisted hours):**
```
Variable cost per client/month:
  Cloud compute:           ₹500-1,500
  AI API (base features):  ₹300-800
  WhatsApp notifications:  ₹200-500
  Support overhead:        ₹500-1,000
  Total variable:          ₹1,500-3,800/month

At 65-70% gross margin target, minimum subscription:
  ₹1,500 ÷ 0.30 = ₹5,000/month (floor for smallest plan)
```

**Ceiling calculation (value-based):**
```
Client's manual cost (school with 500 students):
  Admin staff (2 × ₹18,000/month):  ₹4,32,000/year
  Fee collection errors (~5%):        ₹50,000/year
  Total annual value:                 ₹4,82,000

Value capture at 12-15%:  ₹57,000-72,000/year = ₹4,750-6,000/month
```

**EduFlow subscription plans (from Financial Questionnaire):**

| Plan | School Size | Implementation | Subscription /month | Included Tokens /month | Client Manual Cost /yr | Client Saves /yr |
|------|-------------|----------------|---------------------|------------------------|------------------------|------------------|
| **Starter** | < 500 students | ₹40,000 | ₹6,400 | 500K | ~₹1,80,000 | ~₹64,000 (35%) |
| **Growth** | 500–1,000 students | ₹75,000 | ₹17,000 | 2M | ~₹4,32,000 | ~₹1,53,000 (35%) |
| **Premium** | 1,000–2,500 students | ₹1,25,000 | ₹28,500 | 5M | ~₹7,20,000 | ~₹2,53,000 (35%) |
| **Enterprise** | 2,500+ / multi-campus | ₹3–4 Lakhs | ₹35,000+ (custom) | Custom | ₹15L+ /yr | Custom |

**Gross margin on subscription: 65-70%** (from Financial Questionnaire)
**Net margin target: 30-35%** (after all operating costs)

### Pay-As-You-Go Token Pricing (Hybrid: Base included + Usage overage)

When a school exhausts their plan's included tokens, individual users can recharge on a pay-as-you-go basis. This is the usage-based component of the hybrid model.

**Cost basis (from Financial Questionnaire):**
```
AI API overage: pass-through at ₹2-5 per 1K tokens; 20-30% margin retained

Actual LLM cost (Gemini 2.5 Flash): ~₹0.5-1.5 per 1K tokens
Layaa AI markup: 30-35% commission on top
End-user price: ₹2-5 per 1K tokens (varies by pack size — volume discount)
```

**Token packs (pay-as-you-go, purchasable by any user):**

| Pack | Tokens | Price (INR) | Per 1K Token Rate | LLM Cost (est.) | Layaa Commission | Margin |
|------|--------|-------------|-------------------|------------------|------------------|--------|
| Micro | 50K | ₹49 | ₹0.98/1K | ₹30 | ₹19 (39%) | 39% |
| Basic | 200K | ₹149 | ₹0.75/1K | ₹100 | ₹49 (33%) | 33% |
| Standard | 500K | ₹349 | ₹0.70/1K | ₹230 | ₹119 (34%) | 34% |
| Power | 1.2M | ₹699 | ₹0.58/1K | ₹450 | ₹249 (36%) | 36% |
| School Pack | 3M | ₹1,499 | ₹0.50/1K | ₹1,000 | ₹499 (33%) | 33% |

**Why these prices work:**
- ₹49 Micro pack = impulse buy for a teacher who needs more AI help this month
- ₹149 Basic = price of a coffee outing — low barrier for students/parents
- ₹1,499 School Pack = owner-level bulk buy — best per-token rate
- Commission averages 33-36% (within your 30-40% target range)
- Volume discount: Micro is ₹0.98/1K, School Pack is ₹0.50/1K → 2x value → encourages bulk

**Per-user token allocation (set by owner):**

Owner configures in Settings how plan tokens are distributed:

| Role | Default Monthly Allocation | Owner Can Change |
|------|---------------------------|------------------|
| Owner | Unlimited (from plan pool) | N/A |
| Admin / Principal | 100K | Yes |
| Accounts | 30K | Yes |
| Teachers | 50K | Yes |
| Students | 20K | Yes |
| Transport Head | 15K | Yes |

When a user exhausts their allocation:
1. First: "You've used your monthly AI quota. Ask your school admin to increase your limit."
2. If owner enables self-recharge: user sees "Recharge" button → buys a token pack → tokens credited to their personal balance (separate from school pool)
3. Personal token purchases don't count against school plan — they're additional

### Token System Collections

**`token_usage` collection:**
```json
{
  "id": "tu-001",
  "branch_id": "branch-aaryans-joya",
  "user_id": "user-teacher-001",
  "user_role": "teacher",
  "conversation_id": "conv-xxx",
  "tool_called": "get_attendance_overview",
  "tokens_used": 1250,
  "model": "gemini-2.5-flash",
  "source": "plan",                  // "plan" | "personal_topup"
  "timestamp": "2026-04-09T10:30:00Z"
}
```

**`token_balance` collection (per school/branch):**
```json
{
  "branch_id": "branch-aaryans-joya",
  "plan_id": "growth",
  "plan_name": "Growth",
  "monthly_included": 2000000,
  "monthly_used": 850000,
  "purchased_topup": 500000,
  "topup_used": 120000,
  "billing_cycle_start": "2026-04-01",
  "billing_cycle_end": "2026-04-30",
  "per_role_limits": {
    "owner": -1,                     // -1 = unlimited
    "admin": 100000,
    "teacher": 50000,
    "student": 20000,
    "transport_head": 15000,
    "accounts": 30000
  },
  "self_recharge_enabled": true      // can individual users buy their own packs?
}
```

**`token_recharges` collection (purchases):**
```json
{
  "id": "tr-001",
  "branch_id": "branch-aaryans-joya",
  "purchased_by_user_id": "user-teacher-001",
  "purchase_type": "personal",        // "school" (owner buys for school) | "personal" (user buys for self)
  "pack_id": "basic",
  "token_amount": 200000,
  "price_inr": 149,
  "layaa_commission_percent": 33,
  "layaa_commission_inr": 49,
  "llm_cost_inr": 100,
  "payment_gateway": "razorpay",
  "payment_id": "pay_xxx",
  "payment_status": "completed",
  "purchased_at": "2026-04-09T14:30:00Z"
}
```

### Token Enforcement Logic

```python
async def check_and_deduct_tokens(user: dict, branch_id: str, estimated_tokens: int, db) -> dict:
    """Called before every LLM call. Returns {allowed, source, remaining}."""
    
    balance = await db.token_balance.find_one({"branch_id": branch_id})
    role = user.get("role", "student")
    user_id = user.get("id")
    
    # 1. Check per-user role limit
    role_limit = balance.get("per_role_limits", {}).get(role, 20000)
    if role_limit != -1:  # -1 = unlimited
        # Count this user's usage this month
        month_start = balance.get("billing_cycle_start")
        user_used = await db.token_usage.count_documents({
            "user_id": user_id, 
            "timestamp": {"$gte": month_start},
            "source": "plan"
        })
        # Sum tokens
        pipeline = [
            {"$match": {"user_id": user_id, "timestamp": {"$gte": month_start}, "source": "plan"}},
            {"$group": {"_id": None, "total": {"$sum": "$tokens_used"}}}
        ]
        result = await db.token_usage.aggregate(pipeline).to_list(1)
        user_total = result[0]["total"] if result else 0
        
        if user_total + estimated_tokens > role_limit:
            # Check personal top-up balance
            personal_balance = await get_personal_balance(user_id, db)
            if personal_balance >= estimated_tokens:
                return {"allowed": True, "source": "personal_topup", "remaining": personal_balance - estimated_tokens}
            
            return {
                "allowed": False, 
                "source": "none",
                "message": f"Monthly AI limit reached ({user_total:,}/{role_limit:,} tokens). "
                          + ("Recharge with a token pack to continue." if balance.get("self_recharge_enabled") else "Ask your school admin to increase your limit."),
                "can_recharge": balance.get("self_recharge_enabled", False)
            }
    
    # 2. Check school plan pool
    plan_remaining = balance["monthly_included"] - balance["monthly_used"]
    topup_remaining = balance.get("purchased_topup", 0) - balance.get("topup_used", 0)
    total_available = plan_remaining + topup_remaining
    
    if total_available < estimated_tokens:
        return {
            "allowed": False,
            "source": "none", 
            "message": "School's monthly token quota exhausted. The school owner can purchase additional tokens.",
            "can_recharge": role == "owner"
        }
    
    # 3. Deduct — prefer plan tokens first, then school top-up
    source = "plan" if plan_remaining >= estimated_tokens else "school_topup"
    return {"allowed": True, "source": source, "remaining": total_available - estimated_tokens}
```

### Recharge UI

**For owners (Settings → Billing & Tokens):**
- Usage dashboard: total used / included, breakdown by user, by role, by day (recharts graphs)
- Per-role limit configuration (sliders)
- Self-recharge toggle for individual users
- "Buy Token Pack" → Razorpay flow → school pool credited
- Subscription plan display + upgrade path

**For individual users (if self-recharge enabled):**
- Small "AI Credits" indicator in chat footer: "47K tokens remaining"
- When approaching limit: yellow warning banner
- When exhausted: "Recharge" button → Razorpay → personal balance credited
- Personal balance shown separately: "School: 0 remaining | Personal: 200K remaining"

### Revenue Tracking (Layaa AI Admin)

Every token recharge generates revenue for Layaa AI:

```
Monthly subscription revenue: sum(all active subscriptions)
PAYG revenue: sum(all token_recharges.layaa_commission_inr) this month
Total MRR: subscription + PAYG

Example (10 Growth clients + moderate PAYG):
  Subscription: 10 × ₹17,000 = ₹1,70,000/month
  PAYG (avg 5 recharges/client/month × ₹149 × 33%): ~₹2,500/month
  Total: ~₹1,72,500/month → ₹20.7L/year
```

This aligns with the Financial Questionnaire's Yr 1 target of ₹8-12L (starting with 2-3 clients) and Yr 2 target of ₹30-40L (scaling to 10+).

---

## PHASE 0-M: PLATFORM HEALTH MONITORING & SUPPORT TICKETING

### For Layaa AI Team (Abhimanyu + Shubham) — Admin Dashboard

Separate from EduFlow UI. Accessible at `admin.eduflow.layaa.ai` (or similar).

**`platform_health` collection:**
```json
{
  "branch_id": "branch-aaryans-joya",
  "timestamp": "2026-04-09T10:00:00Z",
  "metrics": {
    "db_size_mb": 245,
    "db_collections": 35,
    "total_documents": 125000,
    "api_response_time_ms_avg": 180,
    "api_error_rate_percent": 0.3,
    "active_users_today": 42,
    "llm_calls_today": 380,
    "llm_avg_latency_ms": 1200,
    "llm_error_count": 2,
    "token_usage_today": 450000,
    "storage_used_mb": 120,
    "uptime_percent": 99.8
  }
}
```

**Health monitoring features (for Layaa AI admin):**
- Real-time dashboard: all client branches + their health metrics
- Alerts: API error rate > 5%, DB size > 80% of limit, token usage > 90% of plan, LLM errors > 10/hour
- Client-by-client breakdown: who's using how much, which branches are active
- Revenue tracking: subscriptions + token recharges + commission earned

### For School Users — Support Ticketing

**`support_tickets` collection:**
```json
{
  "id": "ticket-001",
  "branch_id": "branch-aaryans-joya",
  "created_by_user_id": "user-owner-001",
  "created_by_name": "Aman Sharma",
  "created_by_role": "owner",
  "category": "bug",                // "bug" | "feature_request" | "help" | "billing" | "data_issue" | "urgent"
  "priority": "high",               // "low" | "medium" | "high" | "urgent"
  "subject": "Attendance not saving for Class 4B",
  "description": "When I try to mark attendance for Class 4-B, the save button shows loading but nothing saves. This started today morning.",
  "status": "open",                  // "open" | "in_progress" | "waiting_on_client" | "resolved" | "closed"
  "assigned_to": "shubham",         // Layaa AI team member
  "messages": [
    {"from": "client", "name": "Aman Sharma", "text": "Please fix ASAP, attendance is pending.", "timestamp": "2026-04-09T11:00:00Z"},
    {"from": "support", "name": "Shubham", "text": "Investigating now. Found the issue — DB write timeout. Fixing.", "timestamp": "2026-04-09T11:30:00Z"},
    {"from": "support", "name": "Shubham", "text": "Fixed. Please try now and confirm.", "timestamp": "2026-04-09T12:00:00Z"},
    {"from": "client", "name": "Aman Sharma", "text": "Working now. Thanks!", "timestamp": "2026-04-09T12:15:00Z"}
  ],
  "resolved_at": "2026-04-09T12:15:00Z",
  "resolution_time_hours": 1.25,
  "created_at": "2026-04-09T11:00:00Z"
}
```

**Ticketing UI for schools:**
- Settings → Help & Support → "Raise a Ticket" button
- Ticket form: category, priority, subject, description, optional screenshot upload
- Ticket list: see all past tickets + status
- In-ticket chat: back-and-forth messages with Layaa AI support
- SLA display: "Average response time: 2 hours" (calculated from past tickets)

**Layaa AI admin sees:**
- All tickets across all clients
- Filter: by client, status, priority, category
- Assign to team member
- SLA tracking: time to first response, time to resolution
- Client satisfaction (optional: thumbs up/down after resolution)

---

## PHASE 0-N: CAREER ADVISOR (Student Profile — Uplifting & Exploratory)

### Principle: Open Exploration, Zero Negativity

The career advisor never says "you can't do X." It always says "here's how you CAN explore X."

**Rules:**
1. Any student can explore ANY career field regardless of their current stream/subject
2. Science student asks about law → encourage, explain path (CLAT, 5-year LLB, etc.)
3. Arts student asks about engineering → encourage, explain path (lateral entry, bridge courses)
4. Never discourage based on marks: "Your current marks are a starting point, not a limit"
5. Always show multiple paths to the same goal (traditional + alternative)
6. India-specific: know about NTA, JEE, NEET, CLAT, CUET, CAT, UPSC, state PSC, polytechnic, ITI, skill development programs, Startup India
7. Global awareness: mention international options (SAT, GRE, IELTS) but don't push
8. Trades and vocational paths are presented with EQUAL respect as professional degrees
9. Explicit content banned (same rules as AI Tutor)
10. Mental health sensitivity: if student expresses stress about career pressure → supportive message + suggest talking to school counselor/parents

**Career data in knowledge base:**

```json
// career_paths (static KB, not MongoDB — loaded into LLM context)
{
  "engineering": {
    "streams": ["computer_science", "mechanical", "electrical", "civil", "chemical", ...],
    "entry_exams": ["JEE Main", "JEE Advanced", "state CETs", "BITSAT"],
    "after_10th": "Science stream with PCM",
    "after_12th": "B.Tech/BE (4 years)",
    "alternative_paths": ["Polytechnic diploma → lateral entry to B.Tech", "BCA → MCA", "Online certifications"],
    "salary_range": "₹3L-30L+ (varies by specialization)",
    "growth_areas_2026": ["AI/ML", "Robotics", "Green Energy", "Semiconductor"]
  },
  "medicine": { ... },
  "law": { ... },
  "commerce_finance": { ... },
  "arts_humanities": { ... },
  "design": { ... },
  "sports": { ... },
  "armed_forces": { ... },
  "civil_services": { ... },
  "entrepreneurship": { ... },
  "vocational_trades": { ... },
  "creative_arts": { ... }
}
```

---

## THINGS COVERED (comprehensive checklist)

1. Multi-branch architecture (single DB, branch-scoped)
2. House system (4 houses, points, captains)
3. Student positions (school/house/class/special duty)
4. Staff sub-categories (20 types with hierarchy)
5. Transport system (vehicles, routes, stops, driver/conductor data)
6. Library system (books, issue/return, fines, overdue tracking)
7. Inventory management (11 categories, stock tracking, audit)
8. Vendor management (directory, purchase orders, payments)
9. Fee structure with dynamic discounts (sibling, staff child, merit, custom)
10. Events calendar (national, annual, cultural, sports, academic)
11. Sports teams + co-curricular clubs
12. Accounts/payroll (salary structures, disbursements, expenses)
13. Student AI safety (11 strict content rules + blocked topics filter)
14. Curriculum knowledge base (CBSE, ICSE, UP Board, Bihar Board)
15. Hierarchical personal info visibility (only direct superior sees personal data)
16. Financial data special access (owner + accounts only)
17. Student collective analytics (anonymized comparisons, no names)
18. Career advisor (uplifting, exploratory, zero negativity)
19. Token recharge system (pay-as-you-go, 35% commission, Razorpay)
20. Subscription plans (Starter/Growth/Enterprise)
21. Per-user token limits (owner-configurable)
22. Platform health monitoring (Layaa AI admin dashboard)
23. Support ticketing system (school raises tickets, Layaa team resolves)
24. Tool conflict prevention (assignment vs AI tutor, duplicate attendance, etc.)
25. Chat-first design (50+ query types via chat, only 10 tool panels)
26. Thinking/process visualization (SSE events)
27. Confirm action flow (write operations need user confirmation)
28. Navigate events (chat → tool panel switching)
29. Multi-tool chaining (complex queries = multiple tools in sequence)
30. Decision transparency log
31. Purchase order approval workflow
32. Vehicle insurance/fitness expiry alerts
33. Sibling auto-linking + discount
34. Exam schedule integration (blocks AI Tutor during exams)
35. Staff substitute tracking
36. Parent communication log
37. Visitor register
38. Transfer certificates
39. Report card generation
40. Alumni tracking
41. Fee receipt sequential numbering
42. Holiday calendar (Delhi NCR, UP, Bihar regional + national)
43. Homework diary / daily schedule for students

### Do we miss anything?

Reviewing against a typical Indian school ERP feature list, here's what I'd add:

44. **Exam management** — Create exams, set date/subject/marks, enter results, generate report cards. Partially exists (exam_results collection) but needs full CRUD + UI.
45. **SMS/WhatsApp parent alerts** — "Your child was absent today", "Fee reminder", "PTM tomorrow". Routes/sms.py exists but incomplete. Critical for parent engagement.
46. **Student health records** — Blood group, allergies, medical conditions, vaccination records, emergency contact. Important for medical room staff.
47. **Admission workflow** — Full pipeline: enquiry → form fill → document upload → fee payment → enrollment → class assignment. Partially exists via enquiries.
48. **Certificate generation** — Bonafide, Character, Migration, TC — templated PDFs with school header.
49. **Circular/Notice management** — Draft → approve → publish → distribute (to specific classes/roles). Different from announcements (which are already there) — circulars are formal, dated, numbered.
50. **Dress code / uniform tracking** — Which students received uniforms, sizes, replacement requests (optional, low priority).
51. **Complaint/grievance box** — Anonymous student complaints (anti-bullying). Low priority but valuable.

Items 44-48 should be added. 49-51 are optional/future.

---

## UPDATED EXECUTION ORDER (Final — 22 Steps)

| Step | Phase | What | Priority | Effort |
|------|-------|------|----------|--------|
| 1 | 0-A | Multi-branch architecture | P0 | L |
| 2 | 0-B | Houses + student positions | P0 | M |
| 3 | 0-Staff | Staff schema + sub-categories | P0 | L |
| 4 | 0-C | Transport system | P0 | M |
| 5 | 0-D | Library system | P0 | M |
| 6 | 0-E | Inventory + vendors | P1 | M |
| 7 | 0-F | Fee discounts + student fee profiles | P0 | M |
| 8 | 0-G | Events + sports teams + clubs | P1 | M |
| 9 | 0-H | Accounts + payroll | P0 | L |
| 10 | 0-I | Student AI safety (content filter) | P0 | S |
| 11 | 0-J | Curriculum KB (4 boards) | P1 | L |
| 12 | 0-K | Personal info hierarchical visibility | P0 | M |
| 13 | 0-L | Token recharge + subscription system | P1 | L |
| 14 | 0-M | Platform health + support ticketing | P1 | M |
| 15 | 0-N | Career advisor (student mode) | P1 | M |
| 16 | Bug fixes | 8 known issues | P0 | M |
| 17 | Scope | Scope resolver (branch + sub-cat + personal info + financials) | P0 | L |
| 18 | Prompts | System prompt rewrite (all tools + all rules) | P0 | L |
| 19 | Tools | All chat-callable tools (30+) | P0 | XL |
| 20 | Params | LLM parameter extraction for all entities | P0 | M |
| 21 | SSE | Thinking events + ThinkingProcess.js | P0 | M |
| 22 | Extras | Confirm actions, navigate, multi-tool, frontend polish | P1 | L |

**Demo-critical:** Steps 3, 10, 12, 16-21
**SSA delivery:** All 22 steps
**Revenue-critical:** Step 13 (token recharges = Layaa AI income)

---

*Plan created: 9 April 2026 | Final v2 | Awaiting approval before execution*

Sources:
- [DPS House System](https://www.dpsbdn.org/house-system.php)
- [Navrachana Student Council](https://nisvcbse.in/school-life/student-council/)
- [CBSE Curriculum 2025-26](https://cbseacademic.nic.in/curriculum_2026.html)
- [Multi-Branch School ERP](https://www.theedupartner.com/best-school-erp-for-multi-branch-institutions/)
- [School Transport Tracking](https://uffizio-commute.com/blog/why-india-needs-school-bus-tracking-system/)
- [CBSE Library Norms](https://www.cbse.gov.in/LIBRARY-1-99.pdf)
- [School Inventory Management](https://codepex.com/knowledge-base/school-inventory-management-system-digital-student-health-record-mangement-for-schools)
