# EduFlow Staff Onboarding Guide

**Version:** 1.0 | **Platform:** EduFlow | Layaa AI  
**Support:** Contact the school operator for account issues.

---

## Getting Started

### Step 1 - Log in

1. Open the EduFlow URL provided by your administrator.
2. Enter your email address and password.
3. If you have forgotten your password, click **Forgot password** on the login screen - a reset link will be sent to your email.

> Your account is created by the Owner or Administrator. You cannot self-register.

> **Admin sub-role guide:** For a detailed, beginner-friendly breakdown of all six admin sub-roles (Principal, Accountant, Receptionist, Transport Head, Maintenance, IT/Tech), their tools, and how they connect - see **[docs/admin-role-guide.md](admin-role-guide.md)**.

---

## Role-by-Role Guide

### Owner

The Owner has full access to all school data and AI tools.

**Key capabilities:**
- **School Pulse** - Morning dashboard: attendance summary, fee collection, active alerts.
- **Student Database** - Add, edit, view, and export student records.
- **Fee Collection** - Record payments, print receipts, view defaulters.
- **Staff Tracker** - Manage all staff profiles, attendance, and leave requests.
- **Leave Manager** - Approve or reject staff leave requests.
- **Announcements** - Broadcast messages to all staff, teachers, or students.
- **File Upload** - Upload documents (PDFs, images up to 10 MB).
- **Audit Log** - View every action taken on the platform.
- **AI Chat** - Natural-language interface to all tools. Ask questions like:
  - *"How many students are absent today?"*
  - *"Show me fee defaulters in Class 5"*
  - *"Approve Rajesh Kumar's leave request"*

**Tips:**
- The AI will ask for confirmation before making any changes (e.g., recording a payment or updating a record). Review the confirmation card before clicking **Confirm**.
- Use the command palette (Cmd/Ctrl + K) to jump to any tool quickly.

---

### Principal

The Principal manages academic and operational oversight.

**Key capabilities:**
- **Principal Daily Ops** - Attendance overview, disciplinary incidents, class schedules.
- **Timetable Builder** - Create and update weekly timetables per class/section.
- **Incident Tracker** - Log disciplinary incidents and visitor records.
- **Leave Manager** - Approve staff leave.
- **Announcements** - Send school-wide announcements.
- **AI Chat** - Ask about attendance patterns, staff leaves, daily schedules.

---

### Accountant / Finance Admin

**Key capabilities:**
- **Fee Collection** - Record cash/online/cheque payments; print receipts.
- **Fee Sync** - Sync with external fee software (if configured).
- **Discount Policy** - Apply fee discounts to specific students.
- **AI Chat** - *"How much fee was collected today?"*, *"Show outstanding fees for Class 8"*.

> The AI will never modify fee records without an explicit confirmation step.

---

### Receptionist / Operations Admin

**Key capabilities:**
- **Announcements** - Create school notices.
- **Incident Tracker** - Log visitor entries and complaints.
- **Admissions** - Enquiries, the day's follow-up calls, and applications, on one screen since 2026-08-14. Start an application from an enquiry row and the family carries across. Marking a family "enrolled" is not something anybody does by hand; the child joins the roll through their application. See the Admin Role Guide.
- **AI Chat** - Quick look-ups and draft announcements.

---

### Teacher

**Key capabilities:**
- **Attendance Recorder** - Mark daily attendance for your assigned class(es). Select class → mark Present/Absent/Late for each student → Submit.
- **Question Paper Creator** - Generate AI-assisted question papers. Choose subject, chapters, difficulty split → Generate → Edit in the rich-text editor → Export as PDF or Word.
- **AI Chat** - Ask about student attendance, assignment submissions, timetable.

**Marking attendance:**
1. Open **Attendance Recorder**.
2. Select the class and date (defaults to today).
3. Toggle each student's status.
4. Click **Submit Attendance**.

> Attendance corrections for past dates require an Admin or Principal to approve.

---

### Maintenance Admin

**Key capabilities:**
- **Maintenance Tools** - Log and track maintenance tasks, escalate unresolved issues.
- **AI Chat** - *"Show open maintenance tasks"*, *"Mark task #12 as resolved"*.

---

### IT / Tech Admin

**Key capabilities:**
- **IT Issue Tracker** - Log, assign, and resolve IT support tickets scoped to your school.
- **AI Chat** - Query open tickets, update status.

---

## Common Questions

**Q: The AI is not responding. What do I do?**  
A: Wait 10 to 15 seconds and try again. If the issue persists, refresh the page. The AI system has automatic fallback - it will inform you if it is temporarily unavailable.

**Q: I made a mistake - can I undo an AI action?**  
A: AI-executed changes (fee records, attendance corrections, leave approvals) are logged in the **Audit Log**. Contact your Administrator to reverse a mistaken change.

**Q: Can I see data from other staff members?**  
A: Your access is scoped to your role. Teachers can only see their own class data. Admins see their department. Owners see everything.

**Q: Does it work on my phone or a tablet?**  
A: Yes, for every role, since 12 August 2026. Buttons and form fields are sized for a
finger, tables scroll rather than squashing, and the app is tested on a real phone and a
real tablet profile rather than a narrow desktop window. _This answer used to say mobile
was only supported for the Owner and Principal and that you should use a laptop. That has
not been true since Release 3._ If a screen still looks wrong on your device, report it,
because that is a fault and not the expected state.

**Q: How do I change my password?**  
A: Click your profile avatar in the sidebar → **Settings** → **Change Password**.

---

## Data & Privacy

_Two statements here were corrected on 14 August 2026 because they were not true, and a
privacy promise that is not kept is worse than no promise at all._

- All school data is stored on MongoDB Atlas (cloud database) with encryption at rest.
- File uploads are stored in a private AWS S3 bucket. No file is publicly accessible.
- **Your chat conversations ARE saved.** They are kept against your account so you can
  reopen an earlier conversation and so the assistant can refer back to what you asked
  before. _This used to say conversation content was not stored beyond your session, which
  was simply wrong._ Treat the chat as a record, the same as anything else you type into
  the platform.
- **Names and phone numbers DO reach the AI**, because the assistant cannot answer "call
  Aarav's mother" without them. _This used to claim they never do._ What is held back is
  narrower and deliberate: home addresses, dates of birth, Aadhaar and other government
  numbers, health records and anything secret are replaced with "[restricted in chat]"
  before anything is sent to the AI provider, and are not written into the saved trace
  either.
- Every change made through the platform, by a person or by the assistant, is written to
  the Audit Log with who made it and when.

---

## Support Contacts

| Issue | Contact |
|-------|---------|
| Account access / password reset | School Administrator |
| Platform bug or feature request | Operator (Abhimanyu Singh) |
| AI accuracy / wrong answer | Operator - describe the query and the incorrect response |
| Data correction request | Principal or Owner |
