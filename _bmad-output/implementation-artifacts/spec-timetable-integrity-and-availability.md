# Quick Spec: Timetable Integrity and Availability

**Status:** done  
**Source gap:** Frappe Education Course Schedule validation and ERPNext scheduling conflict patterns

## Goal

Protect EduFlow timetable writes from invalid references and double bookings, and make the existing teacher-availability endpoint reachable.

## Existing Defects

1. `/timetable/availability` is shadowed by `/timetable/{class_id}` because of route order.
2. Slot create/update accepts arbitrary and invalid fields.
3. A teacher or room can be assigned to two classes in the same day/period.
4. A subject can be assigned to a class it does not belong to.
5. The timetable editor loads no subjects and asks users to type a subject ID or name.

## Acceptance Criteria

1. Static availability route is registered before the dynamic class route.
2. Create and update validate class, subject/class membership, optional teacher, day, period, and time range.
3. Teacher and non-empty room collisions return HTTP 409 and do not mutate data.
4. Patch only accepts timetable fields and returns 404 for an unknown slot.
5. Existing same-class/day/period POST replacement behavior remains backward compatible.
6. Bulk import retains its counted-result contract while skipping invalid/conflicting entries.
7. Timetable editor fetches subjects for the selected class and uses the existing select control.
8. Security tests and timetable regression tests pass.

## Non-Goals

- No hostel schedule.
- No new branch structure.
- No changes to visual branding or theme.
- No live-data migration.

## Suggested Review Order

1. Validation service.
2. Route ordering and REST integration.
3. Timetable editor subject selection.
4. Conflict, validation, and route tests.
