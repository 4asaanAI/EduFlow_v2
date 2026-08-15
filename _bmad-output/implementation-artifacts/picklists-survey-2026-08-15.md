# Every pick-list on EduFlow, and which ones should be type-to-search

Asked for by Abhimanyu on 2026-08-15: make the lists searchable by typing, and list them
all first so none is missed. **Nothing in this file has been changed yet.** It is the map.

## The thing to know before reading the list

**A searchable box already exists and is used in exactly ONE file.**
`frontend/src/components/ui/SearchablePicker.js` was written on 2026-08-07 from the
school owner's own words: "there should be a search option for the name among the
list... and try to find other places as well like these over the platform." The second
half of that instruction was never carried out. This sweep is that unfinished half, not
a new idea.

**A search box over a TRUNCATED list is worse than the scroll it replaces**, because a
name that is missing looks like a person who is not there. That warning is in the
picker's own notes. So every list below is judged on two things: is it long, and is it
complete.

**Not every drop-down should become searchable, and saying so is part of the job.** A
box asking you to type over six choices is slower than six choices. The rule used below:
**search when the list is filled from school data that grows; leave it alone when the
list is a fixed set of words the platform itself defines.**

There are **81 drop-downs across 29 files.**

---

## A. Should be type-to-search: fed by school data that grows

| Where | The list | Why |
|---|---|---|
| `FeeCollection.js` (17 lists, the worst file) | students to take a payment from, students to correct, students for a discount, the transaction to correct, classes, discount types | Up to 500 children fetched per class. Choosing a child to take money from by scrolling is the exact complaint of 2026-08-07 |
| `AdminTools.js` | classes in 8 separate places, exams | Already imports the searchable picker for some lists and not these |
| `StudentDatabase.js` | classes in 2 places | |
| `AttendanceRecorder.js` | classes, and the child within a register | |
| `TeacherTools.js` | classes in 2 places | |
| `AdmissionsWorkflow.js` | classes | |
| `AcademicStructure.js` | the teacher for a class | Whole staff list, ~96 people, correctly paged so it is complete |
| `StaffTracker.js` | colleagues | |
| `SchoolDirectory.js` | classes and staff filters | |
| `ParentTools.js` | which of your children | Short for most families, but the same control; low priority |
| `CommercialOperations.js` (2) | the legal entity | Grows as the trust adds entities |
| `FeeScheduleManager.js` | the fee structure | |
| `TimetableBuilder.js`, `ExamManager.js`, `SchoolActivities.js` (3), `StudentTools.js` | classes, subjects, exams | |
| `ToolPage.js`, `DataTable.js` | the generic filter drop-down behind ~70 tool tables | **The highest-value single change in this list.** One control, every tool table |
| `ApprovalsQueue.js` | who to bring into a conversation | **Already done, 2026-08-15.** The pattern the rest should follow |

## B. Should stay a plain drop-down: a fixed set of words

Changing these would make them slower, not better.

`ReportProblemModal.js` (kind of problem) · `StudentDatabase.js` (house, blood group) ·
`AttendanceRecorder.js` (present / absent / late) · `MaintenanceTools.js` (job status) ·
`OwnerTools.js` (7, 14, 30, 60, 90 days) · `StaffTracker.js` (job title for a role) ·
`AdminTools.js` (the six document types) · `SettingsModal.js` (session timeout) ·
`IncidentTracker.js`, `QuerySection.js`, `AllChats.js`, `ProfileDocuments.js`,
`EnrolmentControls.js`, `StudentProfileEditor.js` (short fixed lists) ·
`ApprovalsQueue.js` (kind filter, who decides it)

## C. Two things to check while doing it, NOT assumed

1. **`FeeCollection.js` line 223 asks for 20 students** and keeps them in a `students`
   list. The pickers on that screen use their own per-class lists, so this may only feed
   a name lookup. **If it feeds anything a person chooses from, it is a truncated list
   and must be fixed in the same change**, or the search box makes it worse.
2. **`AcademicStructure.js` is fine and should not be "fixed".** It looks truncated at a
   glance (`limit: 20`) and is not: it pages through every member of staff. Checked.

## Suggested order

1. `ToolPage.js` / `DataTable.js` first. One control, ~70 tables, biggest gain.
2. `FeeCollection.js`. Most lists, longest lists, and money is on the other end.
3. The class pickers, which are the same three lines repeated across ten files.
4. The rest of group A.

Group B is deliberately left alone, and this file is the record of that decision so
nobody does it later thinking it was missed.
