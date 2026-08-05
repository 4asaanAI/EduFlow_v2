# Quick Spec: Responsive Role Tool Panels

**Status:** done  
**Scope:** frontend layout hardening only

## Goal

Make every fixed multi-column EduFlow role panel usable from 320px phones through desktop widths without changing branding, theme tokens, copy, data, routes, or business behavior.

## Constraints

- Preserve the existing visual design and all theme variables.
- Use CSS classes to override inline grid columns at narrow viewports.
- Do not alter live data, API behavior, role visibility, or navigation.
- Keep naturally responsive `auto-fit` and `auto-fill` grids unless their minimum width can overflow a 320px viewport.

## Acceptance Criteria

1. Fixed two, three, and four-column forms/stat groups use shared responsive classes.
2. At 640px and below, form/split layouts become one column; stat groups remain compact where appropriate.
3. Grid children can shrink instead of forcing horizontal page overflow.
4. Tables and wide timetable regions retain intentional horizontal scrolling rather than clipping.
5. Frontend unit tests and production build pass with zero failures.
6. A static regression test protects the shared responsive CSS contract and the highest-risk role panels.

## Files Expected to Change

- `frontend/src/App.css`
- Fixed-grid component files under `frontend/src/components/`
- Fixed-grid role panels under `frontend/src/components/tools/`
- A focused frontend regression test

## Suggested Review Order

1. Shared responsive CSS utilities.
2. Class additions only in fixed-grid JSX.
3. Regression test and build results.
