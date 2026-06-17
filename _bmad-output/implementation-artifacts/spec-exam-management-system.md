---
title: 'Exam Management System'
type: 'feature'
created: '2026-06-17'
status: 'draft'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Exam creation is locked to owner/admin only, there is no UI for creating/editing exams or scheduling them per class/subject, and there is no class-level or student-level performance drill-down panel accessible to the right roles.

**Approach:** Open exam CRUD to teacher + admin(principal/management) + owner; add `class_id`/`subject_id` scheduling fields to exams; build a new `ExamManager` component with role-differentiated views (owner = read drill-down, principal/management = full CRUD + scheduling, teacher = create exam scoped to their classes/subjects); wire into sidebar and Layout lazy-loader.

## Boundaries & Constraints

**Always:**
- `from __future__ import annotations` first line in any edited Python file
- Motor async/await for all DB ops; `.to_list(N)` on cursors — never await cursor directly
- New backend helper `require_exam_manager` in `middleware/auth.py` (owner + teacher + admin+principal + admin+management)
- Teacher creating an exam: `class_id` must be in their `compute_teacher_scope` `all_class_ids`; enforce server-side with 403 if not
- No TypeScript — all `.js` files; Lucide icons only
- Multi-tenancy: all DB writes include `schoolId = get_school_id()`; all reads use `_academic_query()`
- Exam doc fields: `id, name, exam_type, class_id (optional), subject_id (optional), start_date, end_date, academic_year_id, schoolId, created_by, created_at`
- Student view: already handled by existing `ResultViewer` in `StudentTools.js` — do NOT modify

**Ask First:** None identified — requirements are unambiguous.

**Never:**
- Never allow teacher to create exam for a class outside their `all_class_ids`
- Never expose `_id` in API responses
- Never use ObjectId — IDs are string UUID4
- Never modify `ResultViewer` in `StudentTools.js`
- Never add TypeScript files

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Owner views exam list | GET /api/academics/exams | All school exams, sorted newest-first | Empty state message |
| Principal creates exam | POST with name, exam_type, class_id, subject_id, dates | 201 exam doc returned | 400 if name missing |
| Teacher creates exam outside scope | POST with class_id not in their scope | 403 Forbidden | Error shown in UI |
| Teacher creates exam in scope | POST with valid class_id + subject_id | 201 exam doc | — |
| Update exam | PATCH /exams/{id} with changed fields | Updated doc | 404 if not found |
| Delete exam | DELETE /exams/{id} by principal/management/owner | 200 success | 403 for teacher |
| Class drill-down | GET /api/academics/results?exam_id=X | Results grouped by class | Empty message if no results |
| Student drill-down | GET /api/academics/results?exam_id=X&class_id=Y | Per-student per-subject marks | Empty message |

</frozen-after-approval>

## Code Map

- `backend/middleware/auth.py:249` -- add `require_exam_manager` helper after `require_owner_principal_or_management`
- `backend/routes/academics.py:149` -- POST /exams permission + new fields; add PATCH + DELETE endpoints
- `frontend/src/lib/api.js:630` -- add exam CRUD API functions
- `frontend/src/components/tools/ExamManager.js` -- NEW: role-differentiated exam management component
- `frontend/src/components/Layout.js:15` -- add `exam-manager` lazy import entry
- `frontend/src/components/Sidebar.js:15` -- add exam-manager to TOOLS_BY_ROLE + TOOL_GROUPS

## Tasks & Acceptance

**Execution:**
- [ ] `backend/middleware/auth.py` -- add `require_exam_manager` (owner | teacher | admin+principal | admin+management) -- new permission tier needed for all exam write endpoints
- [ ] `backend/routes/academics.py` -- (a) POST /exams: swap to `require_exam_manager`, add `class_id`/`subject_id`/`created_by` fields, teacher scope gate; (b) add `PATCH /exams/{id}` (require_exam_manager, teacher can only edit own exams); (c) add `DELETE /exams/{id}` (require_owner_principal_or_management only — teachers cannot delete)
- [ ] `frontend/src/lib/api.js` -- add `createExam`, `updateExam`, `deleteExam`, `listExams`, `getExamClassPerformance` functions
- [ ] `frontend/src/components/tools/ExamManager.js` -- NEW file: three view modes determined by `currentUser.role` + `sub_category`; Owner view = read-only drill-down (exam list → class avg table → student+subject marks); Principal/Management view = full CRUD form + same drill-down; Teacher view = create/edit own exams scoped to their assigned classes/subjects
- [ ] `frontend/src/components/Layout.js` -- add `if (toolId === 'exam-manager') return (await import('./tools/ExamManager')).default;`
- [ ] `frontend/src/components/Sidebar.js` -- (a) add `{id:'exam-manager', name:'Exams', subtitle:'Schedule & results', icon:ClipboardList, color:'#a78bfa'}` to TOOLS_BY_ROLE.owner, TOOLS_BY_ROLE.admin, TOOLS_BY_ROLE.teacher; (b) push `'exam-manager'` into `TOOL_GROUPS.owner.internals.tools`; (c) push `'exam-manager'` into `TOOL_GROUPS.principal.operations.tools`; (d) push `'exam-manager'` into teacher `planning` group tools
- [ ] `tests/backend/api/test_exam_management.py` -- NEW: unauthenticated → 401, wrong role (accountant) → 403, teacher outside scope → 403, teacher in scope → 201, owner → 200, PATCH/DELETE happy paths

**Acceptance Criteria:**
- Given owner is logged in, when they open Exams tool, then they see all school exams and can drill into class → student performance without any create/edit/delete controls
- Given principal/management admin, when they open Exams, then they see full CRUD controls + same drill-down + exam scheduling (class + subject fields)
- Given teacher, when they open Exams, then they see only a "Schedule Exam" form limited to their assigned classes/subjects and a list of exams they created
- Given teacher, when they POST /api/academics/exams with a class_id not in their scope, then they receive 403
- Given accountant admin, when they access any exam write endpoint, then they receive 403
- Given unauthenticated request to POST /api/academics/exams, then 401 is returned
- Given exam exists, when principal PATCHes it, then updated fields are persisted and returned

## Design Notes

**Role detection in ExamManager:**
```js
const isOwner = currentUser.role === 'owner';
const canManage = isOwner || (currentUser.role === 'admin' && ['principal','management'].includes(currentUser.sub_category));
const isTeacher = currentUser.role === 'teacher';
// Owner: read drill-down only. canManage: full CRUD + drill-down. Teacher: create form + own list.
```

**Drill-down aggregation (frontend-side):**
GET results for exam → group by `class_id` → compute avg `marks_obtained` per class → on class click filter by `class_id` → group by `student_id` showing all subjects.

**Teacher exam create constraint:**
POST body includes `class_id` (required for teachers). Backend calls `compute_teacher_scope` and checks `class_id in scope["all_class_ids"]`; raises 403 if not.

## Spec Change Log

## Verification

**Commands:**
- `python -m pytest tests/backend/api/test_exam_management.py -q` -- expected: all pass, 0 skipped
- `python -m pytest tests/backend/ -q --ignore=tests/backend/unit/test_school_onboarding.py --ignore=tests/backend/unit/test_whatsapp_reminders.py` -- expected: no new failures vs baseline

**Manual checks (if no CLI):**
- Open Exams as owner: drill-down works, no create button visible
- Open Exams as principal: create form present, can save and see new exam in list
- Open Exams as teacher: only see their assigned classes in class dropdown, cannot delete
