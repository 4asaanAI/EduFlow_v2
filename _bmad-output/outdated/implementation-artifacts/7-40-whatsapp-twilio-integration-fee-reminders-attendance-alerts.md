---
story_id: "7.40"
story_key: 7-40-whatsapp-twilio-integration-fee-reminders-attendance-alerts
epic: 7
story: 40
status: ready-for-dev
priority: high
effort: large
created: "2026-05-19"
baseline_tests: 796
---

# Story 7.40: WhatsApp/Twilio Integration — Fee Reminders + Attendance Alerts

## User Story

**As** the school owner or accountant,
**I want** to send pre-approved WhatsApp messages to parents of fee defaulters directly from the fee panel,
**and as** the school owner or principal,
**I want** to send pre-approved WhatsApp attendance alert messages to parents of students below 75% attendance,
**so that** parents receive official school communication on WhatsApp without requiring manual copy-paste or a separate messaging app.

---

## Business Context

The Aaryans currently sends fee reminders and attendance alerts via personal WhatsApp — individual messages typed manually. This is untracked, unsystematic, and disappears from institutional memory. This story integrates Twilio's WhatsApp Business API to send templated messages in bulk, logged to `sms_logs`, triggered directly from existing tool panels.

**Critical constraint:** WhatsApp Business messages to parents are **business-initiated conversations** and MUST use Twilio pre-approved Content Templates. The system cannot send arbitrary message text to WhatsApp — only template variables can vary. The Twilio SDK sends these via `content_sid` + `content_variables`, not `body=`.

---

## Acceptance Criteria

### AC1 — Fee Defaulter WhatsApp Reminder (backend)
`POST /api/sms/whatsapp-fee-reminders` (owner or admin+accountant only):
- Accepts optional `{"branch_id": "...", "student_ids": [...]}`. If `student_ids` is omitted, auto-queries all fee defaulters in the branch (outstanding_balance > 0).
- For each student: resolves primary guardian's `whatsapp_phone` (falling back to `phone`) — skip students with no phone.
- Sends WhatsApp message using `TWILIO_WA_FEE_TEMPLATE_SID` with variables: `{"1": guardian_name, "2": student_name, "3": class_section, "4": outstanding_amount_str}`.
- Logs every attempt (sent / failed / no_phone / not_configured) to `sms_logs` with `channel: "whatsapp"`.
- Returns `{"success": true, "data": {"sent": N, "failed": N, "no_phone": N, "not_configured": N, "logs": [...]}}`.
- Returns 503 if `TWILIO_WA_FEE_TEMPLATE_SID` or `TWILIO_WHATSAPP_FROM` env vars are missing.

### AC2 — Attendance Defaulter WhatsApp Alert (backend)
`POST /api/sms/whatsapp-attendance-alerts` (owner or admin+principal only):
- Accepts optional `{"branch_id": "...", "student_ids": [...], "threshold": 75}`. If `student_ids` is omitted, auto-queries students with attendance < `threshold` (default 75%) for the current calendar month.
- For each student: resolves primary guardian's `whatsapp_phone` (falling back to `phone`).
- Sends WhatsApp message using `TWILIO_WA_ATTENDANCE_TEMPLATE_SID` with variables: `{"1": guardian_name, "2": student_name, "3": class_section, "4": attendance_pct_str}` (e.g. `"62%"`).
- Logs every attempt to `sms_logs` with `channel: "whatsapp"`.
- Returns same shape as AC1.
- Returns 503 if `TWILIO_WA_ATTENDANCE_TEMPLATE_SID` or `TWILIO_WHATSAPP_FROM` env vars are missing.

### AC3 — Defaulter Query Endpoint (backend)
`GET /api/sms/whatsapp-defaulters?type=fee|attendance&branch_id=...&threshold=75` (owner or admin — any sub_category):
- Returns `{"success": true, "data": {"type": "fee"|"attendance", "count": N, "students": [...]}}`.
- Each student entry: `{student_id, student_name, class_section, guardian_name, whatsapp_phone, amount_due (fee) | attendance_pct (attendance)}`.
- Used by frontend to preview the list before sending.

### AC4 — RBAC gates
- Fee endpoint (`POST .../whatsapp-fee-reminders`): owner OR admin with `sub_category="accountant"`.
- Attendance endpoint (`POST .../whatsapp-attendance-alerts`): owner OR admin with `sub_category="principal"`.
- Defaulters query (`GET .../whatsapp-defaulters`): any role with `require_role("owner", "admin")`.
- A new auth helper `require_owner_or_accountant` is added to `middleware/auth.py` mirroring the existing `require_owner_or_principal`.

### AC5 — Frontend: Fee panel WhatsApp button
In `frontend/src/components/tools/FeeCollection.js`:
- A new "Send WhatsApp Reminders" button appears when the user is owner or admin+accountant.
- Clicking it: (1) calls `GET /api/sms/whatsapp-defaulters?type=fee` to preview the list, (2) shows count + a `ConfirmActionCard`-style confirmation, (3) on confirm calls `POST /api/sms/whatsapp-fee-reminders`, (4) shows success/failure toast.
- If defaulters count is 0, button is disabled with tooltip "No fee defaulters found".
- If `TWILIO_WA_FEE_TEMPLATE_SID` is not configured, button shows "WhatsApp not configured" and is disabled.

### AC6 — Frontend: Attendance panel WhatsApp button
In `frontend/src/components/tools/AdminTools.js` (the attendance section) or wherever the owner/principal sees attendance:
- A "Send Attendance Alerts" button for users who are owner or admin+principal.
- Same UX flow: preview defaulters → confirm → send → toast.
- If attendance defaulters count is 0, button is disabled.

### AC7 — WhatsApp config status included in existing health check
`GET /api/sms/config-status` already exists — extend its response to include WhatsApp:
```json
{
  "sms_configured": true,
  "whatsapp_configured": true,
  "whatsapp_fee_template": true,
  "whatsapp_attendance_template": true
}
```

### AC8 — Logging: `channel` field on all new WhatsApp entries
All WhatsApp sends log to `sms_logs` with `"channel": "whatsapp"`. Existing SMS logs have no `channel` field (backward-compatible — treat missing as `"sms"`).

### AC9 — Security: 401 + 403 tests
- Unauthenticated request to each new endpoint → 401.
- Wrong-role request (e.g., teacher calling fee-reminders) → 403.

### AC10 — Template variables not configurable at runtime
Template SIDs and variable positions are fixed by the approved Twilio template. Variable values are populated from live DB data. No UI for configuring templates — only env vars.

---

## Scope Exclusions

- No automatic/scheduled WhatsApp sending (cron jobs) — manual trigger only in this story.
- No WhatsApp reply handling or inbound message processing.
- No new Twilio template creation via API — operator creates templates in Twilio Console manually.
- No per-student opt-out management.
- No SMS fallback if WhatsApp delivery fails (separate future story).
- `customer.subscription.updated` webhook handling deferred (tracked in deferred-work.md from 7-42).

---

## Dev Notes

### Twilio WhatsApp API — CRITICAL: This is NOT the same as regular SMS

The existing `sms.py` uses:
```python
client.messages.create(body=msg_text, from_=twilio_phone, to=normalized_phone)
```

**WhatsApp template messages use a completely different call:**
```python
import json

client.messages.create(
    from_=f"whatsapp:{twilio_whatsapp_from}",   # e.g. "whatsapp:+14155238886"
    to=f"whatsapp:{normalized_phone}",           # e.g. "whatsapp:+919876543210"
    content_sid=template_sid,                    # e.g. "HX1234abc..."
    content_variables=json.dumps({
        "1": guardian_name,
        "2": student_name,
        "3": class_section,
        "4": amount_or_pct,
    }),
)
```

**Do NOT use `body=` for WhatsApp template messages** — it will fail or send a plain freeform message (only allowed in 24h service conversations, not business-initiated).

`TWILIO_WHATSAPP_FROM` should be stored WITHOUT the `whatsapp:` prefix — the code prepends it.

### New env vars (add to `.env.example`)

```bash
# WhatsApp Business (Twilio Content Templates)
TWILIO_WHATSAPP_FROM=+14155238886          # Twilio WhatsApp-enabled sender number (no whatsapp: prefix)
TWILIO_WA_FEE_TEMPLATE_SID=HXabc123...    # Twilio Content SID for fee reminder template
TWILIO_WA_ATTENDANCE_TEMPLATE_SID=HXdef456... # Twilio Content SID for attendance alert template
```

### Template variable mapping (must match Twilio Console template)

**Fee Reminder Template:**
The template text in Twilio Console should read something like:
> "Dear {{1}}, this is a reminder that fee for {{2}} ({{3}}) is outstanding. Amount due: ₹{{4}}. Please visit the school office. - The Aaryans"

Variable binding in code:
```python
content_variables=json.dumps({
    "1": guardian_name,       # e.g. "Ramesh Kumar"
    "2": student_name,        # e.g. "Priya Kumar"
    "3": class_section,       # e.g. "Class 8 B"
    "4": str(outstanding_amt) # e.g. "4500"
})
```

**Attendance Alert Template:**
> "Dear {{1}}, {{2}} ({{3}}) has {{4}} attendance this month, which is below the required 75%. Please ensure regular attendance. - The Aaryans"

Variable binding:
```python
content_variables=json.dumps({
    "1": guardian_name,           # "Ramesh Kumar"
    "2": student_name,            # "Priya Kumar"
    "3": class_section,           # "Class 8 B"
    "4": f"{attendance_pct:.0f}%" # "62%"
})
```

### Phone number normalization (reuse existing pattern from sms.py)

```python
def _normalize_whatsapp_phone(raw_phone: str) -> str:
    """Return E.164 format prefixed with whatsapp: for Twilio."""
    phone = raw_phone.strip()
    if not phone.startswith("+"):
        phone = "+91" + phone.lstrip("0")
    return f"whatsapp:{phone}"
```

### Fee defaulter query

Fee data in EduFlow is in `fee_transactions` (individual payments) and `student_fees` or computed via summary endpoints. The simplest approach is to query `students` and for each, check their fee balance. However, to avoid N+1:

```python
# Pattern: aggregate fee_transactions grouped by student_id
# Sum of type="debit" (fees charged) minus sum of type="credit" (payments made)
# OR: check for students where fee_paid < fee_due from student_fees collection
```

Inspect existing `GET /api/fees/summary` route (`backend/routes/fees.py`) — it already computes `defaulters`. Extract the defaulter query logic from there rather than duplicating it.

If `student_fees` collection exists with `{student_id, fees_due, fees_paid, schoolId, branch_id}`, use:
```python
fee_docs = await db.student_fees.find(
    scoped_query({"is_active": {"$ne": False}}, branch_id=bid)
).to_list(5000)
defaulters = [f for f in fee_docs if (f.get("fees_due", 0) - f.get("fees_paid", 0)) > 0]
```

Then enrich with student + guardian data via `{"id": {"$in": [...]}}` batch query.

### Attendance defaulter query

```python
from datetime import date, timezone
import calendar

today = date.today()
month_start = today.replace(day=1).isoformat()
month_end = today.isoformat()

# Working days this month (simplified: count records that exist)
att_records = await db.student_attendance.find(
    scoped_query({"date": {"$gte": month_start, "$lte": month_end}}, branch_id=bid)
).to_list(None)

# Group by student_id
from collections import defaultdict
by_student = defaultdict(lambda: {"present": 0, "total": 0})
for r in att_records:
    sid = r.get("student_id")
    if not sid:
        continue
    by_student[sid]["total"] += 1
    if r.get("status") == "present":
        by_student[sid]["present"] += 1

# Filter below threshold
threshold_pct = threshold / 100.0
defaulters = [
    sid for sid, counts in by_student.items()
    if counts["total"] > 0 and (counts["present"] / counts["total"]) < threshold_pct
]
```

Then batch-fetch students + guardians for enrichment.

### New auth helper — add to `middleware/auth.py`

```python
def require_owner_or_accountant(current_user: dict = Depends(get_current_user)) -> dict:
    role = current_user.get("role")
    sub_category = current_user.get("sub_category", "")
    if role == "owner":
        return current_user
    if role == "admin" and sub_category == "accountant":
        return current_user
    raise HTTPException(status_code=403, detail="Owner or accountant access required")
```

The existing `require_owner_or_principal` in `middleware/auth.py` is the exact pattern to mirror.

### Guardian phone resolution (reuse pattern from tool_draft_parent_message)

Students have a `guardians` array (from Story 8C):
```python
guardians = student.get("guardians", [])
primary = next((g for g in guardians if g.get("is_primary")), guardians[0] if guardians else {})
phone = primary.get("whatsapp_phone") or primary.get("phone") or ""
guardian_name = primary.get("name", "Parent/Guardian")
```

If no guardian data, fall back to `student.get("phone", "")`.

### sms_logs schema extension

Add `channel` field to new log entries. Existing entries without `channel` default to `"sms"`. No migration needed (fail-open on missing field).

```python
log = {
    "schoolId": get_school_id(),
    "branch_id": bid,
    "id": str(uuid.uuid4()),
    "student_id": student_id,
    "student_name": student_name,
    "phone": raw_phone,
    "channel": "whatsapp",           # ← new field
    "template_sid": template_sid,    # ← new field for traceability
    "content_variables": variables,  # ← new field (JSON string)
    "sent_by": user["id"],
    "sent_by_name": user.get("name", ""),
    "status": status,
    "sms_sid": sms_sid,
    "error": error_msg,
    "sent_at": datetime.now(timezone.utc).isoformat(),
    "created_at": datetime.now(timezone.utc),  # ← native datetime for TTL index
}
```

### Not-configured guard (503, not 400)

```python
whatsapp_from = os.environ.get("TWILIO_WHATSAPP_FROM", "").strip()
template_sid = os.environ.get("TWILIO_WA_FEE_TEMPLATE_SID", "").strip()
if not whatsapp_from or not template_sid:
    raise HTTPException(status_code=503, detail="WhatsApp not configured. Set TWILIO_WHATSAPP_FROM and TWILIO_WA_FEE_TEMPLATE_SID.")
```

Use 503 (service unavailable) not 400 (bad request) — it's a server-side config gap, not a client error.

### Rate limiting: bulk WhatsApp cap

Cap bulk sends at 200 students per request (Twilio has per-template rate limits). Return 400 if `len(student_ids) > 200`.

### Frontend: Role-gating the button

```js
const { user } = useContext(UserContext)
const canSendFeeWA = user?.role === 'owner' || (user?.role === 'admin' && user?.sub_category === 'accountant')
const canSendAttWA = user?.role === 'owner' || (user?.role === 'admin' && user?.sub_category === 'principal')
```

### Frontend: API wiring (add to `frontend/src/lib/api.js`)

```js
export const getWhatsappDefaulters = (type, params = {}) =>
  apiGet(`/api/sms/whatsapp-defaulters?type=${type}${params.branch_id ? `&branch_id=${params.branch_id}` : ''}`)

export const sendFeeReminders = (body) => apiPost('/api/sms/whatsapp-fee-reminders', body)
export const sendAttendanceAlerts = (body) => apiPost('/api/sms/whatsapp-attendance-alerts', body)
```

Use native `fetch` (not axios) — file uploads use axios, everything else uses fetch per project conventions.

### Files to CREATE

| File | Notes |
|---|---|
| (none new) | All changes extend existing files |

### Files to MODIFY

| File | What changes |
|---|---|
| `backend/routes/sms.py` | Add 3 new endpoints + `_normalize_whatsapp_phone` helper + `_send_whatsapp_template` inner function |
| `backend/middleware/auth.py` | Add `require_owner_or_accountant` helper |
| `backend/routes/fees.py` | Check: does the fee defaulters query already exist? Extract and reuse it |
| `backend/.env.example` | Add 3 new WhatsApp env vars |
| `frontend/src/lib/api.js` | Add 3 new API functions |
| `frontend/src/components/tools/FeeCollection.js` | Add "Send WhatsApp Reminders" button + state + handler |
| `frontend/src/components/tools/AdminTools.js` | Add "Send Attendance Alerts" button for owner/principal |

### Python 3.9 compat

`sms.py` already has `from __future__ import annotations` — verify and keep it as the first import.

---

## Testing Requirements

### Every test file needs
```python
from __future__ import annotations
import pytest
pytestmark = pytest.mark.asyncio
```

### Test file: `tests/backend/unit/test_whatsapp_reminders.py`

```python
# AC9 — Security tests (MANDATORY for every new endpoint)
def test_whatsapp_fee_reminders_unauthenticated_returns_401(client):
    resp = client.post("/api/sms/whatsapp-fee-reminders", json={})
    assert resp.status_code == 401

def test_whatsapp_fee_reminders_wrong_role_returns_403(client):
    headers = _bearer({"user_id": "u1", "role": "teacher", "name": "T"})
    resp = client.post("/api/sms/whatsapp-fee-reminders", json={}, headers=headers)
    assert resp.status_code == 403

def test_whatsapp_attendance_alerts_unauthenticated_returns_401(client):
    resp = client.post("/api/sms/whatsapp-attendance-alerts", json={})
    assert resp.status_code == 401

def test_whatsapp_attendance_alerts_wrong_role_returns_403(client):
    headers = _bearer({"user_id": "u1", "role": "admin", "sub_category": "accountant", "name": "A"})
    resp = client.post("/api/sms/whatsapp-attendance-alerts", json={}, headers=headers)
    assert resp.status_code == 403  # accountant cannot send attendance alerts

# AC1 — Fee reminders: not_configured path (no env vars set)
async def test_fee_reminders_returns_503_when_not_configured(client, monkeypatch):
    monkeypatch.delenv("TWILIO_WA_FEE_TEMPLATE_SID", raising=False)
    monkeypatch.delenv("TWILIO_WHATSAPP_FROM", raising=False)
    headers = _bearer({"user_id": "u1", "role": "owner", "name": "O"})
    resp = client.post("/api/sms/whatsapp-fee-reminders", json={}, headers=headers)
    assert resp.status_code == 503

# AC1 — Fee reminders: sends WhatsApp via Twilio mock
async def test_fee_reminders_sends_whatsapp_messages(client, monkeypatch):
    monkeypatch.setenv("TWILIO_WA_FEE_TEMPLATE_SID", "HXtest123")
    monkeypatch.setenv("TWILIO_WHATSAPP_FROM", "+14155238886")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token")
    # Mock Twilio client
    sent = []
    class MockMsg:
        sid = "SM123"
    class MockMessages:
        def create(self, **kwargs):
            sent.append(kwargs)
            return MockMsg()
    class MockClient:
        messages = MockMessages()
    monkeypatch.setattr("routes.sms.get_twilio_client", lambda: MockClient())
    # ... setup FakeCollection with fee defaulter data ...
    headers = _bearer({"user_id": "u1", "role": "owner", "name": "O"})
    resp = client.post("/api/sms/whatsapp-fee-reminders",
                       json={"student_ids": ["s1"]}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["sent"] == 1
    assert sent[0]["from_"].startswith("whatsapp:")
    assert sent[0]["content_sid"] == "HXtest123"
    assert "body" not in sent[0]  # must NOT use body= for template messages

# AC2 — Attendance alerts: accountant blocked, principal allowed
def test_attendance_alerts_principal_allowed(client, monkeypatch):
    # monkeypatch twilio + env, then verify principal (admin+principal) gets 200
    ...

# AC3 — Defaulters query returns correct structure
async def test_whatsapp_defaulters_fee_type_returns_list(client):
    headers = _bearer({"user_id": "u1", "role": "owner", "name": "O"})
    resp = client.get("/api/sms/whatsapp-defaulters?type=fee", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "type" in data
    assert "students" in data
    assert data["type"] == "fee"

# AC4 — require_owner_or_accountant: teacher blocked, accountant allowed
def test_require_owner_or_accountant_blocks_teacher():
    from middleware.auth import require_owner_or_accountant
    # test the dependency directly
    ...

# AC8 — WhatsApp log has channel="whatsapp" field
async def test_whatsapp_log_has_channel_field(client, ...):
    # after send, check sms_logs collection for channel="whatsapp"
    ...
```

Use `FakeCollection` from `tests/backend/conftest.py` and shared factories from `tests/backend/factories.py`.

---

## Implementation Tasks

- [ ] **T1** — `middleware/auth.py`: Add `require_owner_or_accountant` helper (mirror `require_owner_or_principal`)
- [ ] **T2** — `backend/routes/sms.py`: Add `_normalize_whatsapp_phone()` and `_send_whatsapp_template()` internal helpers
- [ ] **T3** — `backend/routes/sms.py`: Add `GET /api/sms/whatsapp-defaulters` endpoint (fee + attendance query logic)
- [ ] **T4** — `backend/routes/sms.py`: Add `POST /api/sms/whatsapp-fee-reminders` endpoint
- [ ] **T5** — `backend/routes/sms.py`: Add `POST /api/sms/whatsapp-attendance-alerts` endpoint
- [ ] **T6** — `backend/routes/sms.py`: Extend `GET /api/sms/config-status` to include WhatsApp fields
- [ ] **T7** — `backend/.env.example`: Add 3 new WhatsApp env vars with comments
- [ ] **T8** — `frontend/src/lib/api.js`: Add `getWhatsappDefaulters`, `sendFeeReminders`, `sendAttendanceAlerts`
- [ ] **T9** — `frontend/src/components/tools/FeeCollection.js`: Add "Send WhatsApp Reminders" button with preview + confirm flow
- [ ] **T10** — `frontend/src/components/tools/AdminTools.js`: Add "Send Attendance Alerts" button for owner/principal
- [ ] **T11** — `tests/backend/unit/test_whatsapp_reminders.py`: Write all required tests (security, happy path, not-configured, no_phone)
- [ ] **T12** — Run `python -m pytest tests/backend/ -x -q` → must show ≥ 796 + new tests passing, 0 skipped

---

## Dev Agent Record

### Agent Model Used
(to be filled by dev agent)

### Completion Notes
(to be filled by dev agent)

### File List
(to be filled by dev agent)

### Change Log
- 2026-05-19 — Story created from /bmad-create-story with Abhimanyu's answers:
  - Template SIDs via env vars
  - RBAC: Accountant → fee, Principal → attendance, Owner → both
  - Fee defaulter: outstanding_balance > 0
  - Attendance defaulter: < 75% this month
  - UI: Existing FeeCollection + AdminTools panels
