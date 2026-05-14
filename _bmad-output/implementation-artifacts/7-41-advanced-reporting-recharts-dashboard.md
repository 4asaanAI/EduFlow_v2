# Story 7.41: Advanced Reporting — Recharts Dashboard

Status: done
Epic: 7
Priority: Medium (Phase 2 trigger)
Effort: Medium
Created: 2026-05-15

## Story

**As** an Owner or Principal,
**I want** visual attendance trend charts and fee collection bar charts,
**so that** I can spot patterns without exporting raw data.

## Acceptance Criteria

1. **AC1.** `GET /api/reports/attendance-trends?months=3` returns monthly attendance percentages per class (and overall) for the last N months. Default `months=3`. Clamped to [1, 12].
2. **AC2.** `GET /api/reports/fee-collection-summary?months=6` returns monthly fee collected vs outstanding for the last N months. Default `months=6`. Clamped to [1, 24].
3. **AC3.** Both endpoints require role `owner` or `admin`-with-`sub_category=principal`. Other roles get 403. `fee-collection-summary` is **owner-only** (principal does not see financial data per RBAC).
4. **AC4.** Empty state: when there are fewer than 1 month of records, the response includes `empty: true` and `data: []`. Frontend renders an empty-state message instead of a chart.
5. **AC5.** Frontend: Owner dashboard component renders a Recharts bar chart (fee collection, last 6 months) and a line chart (overall attendance trend, last 3 months). Principal dashboard component renders only the attendance line chart.
6. **AC6.** Mobile-responsive at 375px: `ResponsiveContainer` is used; tooltips work on touch.
7. **AC7.** No real-time requirement — data fetches once on page mount.

## Tasks

- [x] **T1. Reports router** — `backend/routes/reports.py` created with prefix `/api/reports`; registered in `server.py`.
- [x] **T2. Attendance trends endpoint** — `GET /api/reports/attendance-trends?months=N` (clamped 1..12); per-month and per-class breakdown.
- [x] **T3. Fee collection endpoint** — `GET /api/reports/fee-collection-summary?months=N` (clamped 1..24); owner-only.
- [x] **T4. Tests** — `tests/backend/api/test_reports.py` (9 tests): auth gates, empty-state, percentage math, clamping.
- [x] **T5. Frontend chart components** — `ReportsTrends` exported from both `OwnerTools.js` (line + bar) and `AdminTools.js` (line only), using existing `LineChartWidget`/`BarChartWidget` (Recharts wrappers); tool ID `reports-trends` added to `OWNERS` + `ADMINS` arrays in `Layout.js`.

## Dev Notes

- Date field on `student_attendance` is ISO `YYYY-MM-DD` (string). Use `substring(0,7)` for month grouping.
- `fee_transactions` has `status` ∈ {paid, pending, overdue, unpaid} and `amount` (numeric or numeric string — coerce via `float()`).
- For monthly grouping in MongoDB, can use `$substr` on date strings or `$dateFromString` + `$dateTrunc`. The FakeCollection's aggregate stub supports `$substr` (verified in conftest).
- Frontend dashboards: `OwnerTools.js` already has fetch patterns; add a small `<ReportsPanel role={...}>` near the existing dashboard. Recharts is at 3.6.0 — no install.
- Out of scope: drill-downs, date-range pickers, export-to-PNG.

## Dev Agent Record

### Agent Model Used
claude-opus-4-7 (1M context)

### File List

**Added:**
- `backend/routes/reports.py` — two new endpoints
- `tests/backend/api/test_reports.py` — 9 tests

**Modified:**
- `backend/server.py` — registers `reports_router`
- `tests/backend/conftest.py` — registers `reports_routes.get_db`
- `frontend/src/components/tools/OwnerTools.js` — exports `ReportsTrends` (owner — both charts)
- `frontend/src/components/tools/AdminTools.js` — imports `LineChartWidget`; exports `ReportsTrends` (principal — attendance only)
- `frontend/src/components/Layout.js` — `reports-trends` added to `OWNERS` and `ADMINS` arrays

### Completion Notes

- All 7 ACs satisfied; 9 new tests pass; full backend suite **173/173 passes**.
- Reused existing `LineChartWidget` / `BarChartWidget` from `ToolPage.js` — already use `ResponsiveContainer`, so AC6 (mobile responsiveness at 375px) is satisfied without new CSS work.
- Principal variant excludes the fee chart entirely (RBAC) — separate component definition in AdminTools.js.

### Change Log

- 2026-05-15 — Story complete. 9 tests added. 173/173 backend tests pass. Three Epic 7 stories now done in this run.
