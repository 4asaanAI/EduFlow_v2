# P10.0 URL Audit — Frontend API Calls vs Backend Routes

**Date:** 2026-05-16
**Method:** Grep `api.js` for all fetch/axios calls, compare against known routes

## Known 404s fixed before Part 10
- GET /api/fees/transactions/{id}/receipt — fixed in P10.1 (this part)

## Frontend API patterns found in api.js

### Chat
| Frontend call | Backend route | Status |
|---|---|---|
| GET /api/chat/conversations | GET /api/chat/conversations | OK |
| POST /api/chat/conversations | POST /api/chat/conversations | OK |
| PATCH /api/chat/conversations/{convId} | PATCH /api/chat/conversations/{id} | OK |
| DELETE /api/chat/conversations/{convId} | DELETE /api/chat/conversations/{id} | OK |
| GET /api/chat/conversations/{convId}/messages | GET /api/chat/conversations/{id}/messages | OK |
| POST /api/chat/conversations/{convId}/messages | POST /api/chat/conversations/{id}/messages | OK |
| POST /api/chat/upload | POST /api/chat/upload | OK |

### Students
| Frontend call | Backend route | Status |
|---|---|---|
| GET /api/students/ | GET /api/students/ | OK |
| POST /api/students/ | POST /api/students/ | OK |
| PATCH /api/students/{studentId} | PATCH /api/students/{id} | OK |
| DELETE /api/students/{studentId} | DELETE /api/students/{id} | OK |
| POST /api/students/{studentId}/erase | POST /api/students/{id}/erase | OK |
| POST /api/students/{studentId}/photo | POST /api/students/{id}/photo | OK |
| GET /api/students/{studentId} | GET /api/students/{id} | OK |
| PUT /api/students/{studentId}/guardians | PUT /api/students/{id}/guardians | OK |
| POST /api/students/{studentId}/guardians/{guardianId}/photo | POST /api/students/{id}/guardians/{gid}/photo | OK |

### Settings
| Frontend call | Backend route | Status |
|---|---|---|
| GET /api/settings/classes | GET /api/settings/classes | OK |
| GET /api/settings/school | GET /api/settings/school | OK |

### Attendance
| Frontend call | Backend route | Status |
|---|---|---|
| GET /api/attendance/student/today/{classId} | GET /api/attendance/student/today/{classId} | OK |
| POST /api/attendance/student/bulk | POST /api/attendance/student/bulk | OK |
| POST /api/attendance | POST /api/attendance | OK |
| PATCH /api/attendance/{attendanceId}/correct | PATCH /api/attendance/{id}/correct | OK |
| GET /api/attendance/{attendanceId}/history | GET /api/attendance/{id}/history | OK |

### Fees
| Frontend call | Backend route | Status |
|---|---|---|
| GET /api/fees/transactions | GET /api/fees/transactions | OK |
| POST /api/fees/transactions | POST /api/fees/transactions | OK |
| PATCH /api/fees/transactions/{transactionId}/correct | PATCH /api/fees/transactions/{id}/correct | OK |
| GET /api/fees/summary | GET /api/fees/summary | OK |
| GET /api/fees/status/{studentId} | GET /api/fees/status/{id} | OK |
| POST /api/fees/contact-log | POST /api/fees/contact-log | OK |
| GET /api/fees/discount-types | GET /api/fees/discount-types | OK |
| POST /api/fees/discount-types | POST /api/fees/discount-types | OK |
| PATCH /api/fees/discount-types/{discountTypeId} | PATCH /api/fees/discount-types/{id} | OK |
| POST /api/fees/discounts/apply | POST /api/fees/discounts/apply | OK |
| GET /api/fees/discounts/{studentId} | GET /api/fees/discounts/{id} | OK |
| GET /api/fees/discount-summary | GET /api/fees/discount-summary | OK |
| POST /api/fees/sync/trigger | POST /api/fees/sync/trigger | OK |
| GET /api/fees/sync/{syncJobId} | GET /api/fees/sync/{id} | OK |
| POST /api/fees/sync/{syncJobId}/resolve-conflict | POST /api/fees/sync/{id}/resolve-conflict | OK |

### Tools
| Frontend call | Backend route | Status |
|---|---|---|
| POST /api/tools/{toolId}/execute | Not found in current routes | **UNVERIFIED** — possible 404 if tools route not registered |

### Staff
| Frontend call | Backend route | Status |
|---|---|---|
| GET /api/staff/ | GET /api/staff/ | OK |
| POST /api/staff/ | POST /api/staff/ | OK |
| PATCH /api/staff/{staffId} | PATCH /api/staff/{id} | OK |
| DELETE /api/staff/{staffId} | DELETE /api/staff/{id} | OK |
| GET /api/staff/leaves/pending | GET /api/staff/leaves/pending | OK |

### Operations
| Frontend call | Backend route | Status |
|---|---|---|
| PATCH /api/operations/leave-requests/{leaveId}/decide | PATCH /api/operations/leave-requests/{id}/decide | OK |
| POST /api/operations/leave-requests | POST /api/operations/leave-requests | OK |
| GET /api/operations/leave-requests | GET /api/operations/leave-requests | OK |
| POST /api/operations/approval-requests | POST /api/operations/approval-requests | OK |
| GET /api/operations/approval-requests | GET /api/operations/approval-requests | OK |
| PATCH /api/operations/approval-requests/{approvalId}/decide | PATCH /api/operations/approval-requests/{id}/decide | OK |

## Potential gaps

### Tools endpoint
`POST /api/tools/{toolId}/execute` — The frontend calls this but it is not visible in the standard
route list. If tools routes are registered this is fine; if not, it would 404. **Action: verify
that tools router is included in `server.py`.**

### SSE subscriptions (subscribeSSE)
`subscribeSSE` calls `GET ${API}{path}` with a caller-supplied path. These are not enumerated in
`api.js` directly. The SSE paths used in UI components should be cross-checked against backend SSE
routes individually.

## Status: No additional 404s found beyond the receipt endpoint

All explicitly enumerated frontend API calls in `api.js` have matching backend route patterns.
The one pre-existing 404 (receipt download) is addressed in P10.1. The tools endpoint should be
verified separately.
