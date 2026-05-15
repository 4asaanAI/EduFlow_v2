---
workflowType: 'epics'
project_name: 'EduFlow Platform Quality Sweep — Part 5'
user_name: 'Abhimanyu'
date: '2026-05-15'
status: 'ready-for-implementation'
part: 5
part_name: 'Notifications + Real-time (SSE)'
source_parts: ['Part 1 Auth+RBAC', 'Part 2 AI Layer', 'Part 3 Owner role', 'Part 4 Multi-tenancy']
test_baseline: '387 backend tests passing, 0 skipped'
---

# EduFlow Quality Sweep — Part 5: Notifications + Real-time (SSE)

## Context

Part 5 addresses correctness, resilience, and observability gaps in the in-app notification system and the SSE (Server-Sent Events) delivery layer. Items were identified by auditing `backend/services/sse.py`, `backend/routes/notifications.py`, `backend/routes/chat.py` (SSE section), and `frontend/src/lib/api.js`.

Key discoveries from the code audit:

1. **SSE keepalive format mismatch**: `keepalive_event()` in `chat.py` returns `":keepalive\n\n"` — an SSE comment. The frontend's `sendMessageStream` in `api.js` only parses `data: ` prefixed lines; it ignores SSE comments entirely. This means the keepalive never propagates to `onEvent`. A named data event `{"type":"keepalive"}` would be needed to match the existing `event.type === 'keepalive'` handler in `ChatInterface.js`. There are two keepalive mechanisms that disagree on format.
2. **SSE service has no keepalive**: `services/sse.py` (the pub/sub channel layer used by non-chat SSE) has `KEEPALIVE_SECONDS = 30` defined but no code that actually sends keepalive pings. The constant is unused.
3. **Frontend reconnect is partial**: `subscribeSSE()` in `api.js` reconnects after 3 s on error, but `sendMessageStream()` (used for chat) does NOT reconnect — the fetch is one-shot. A backend restart mid-conversation is unrecoverable without a UI retry prompt.
4. **Notification fan-out is duplicated**: `_notify()` helper is defined independently in both `operations.py` and `issues.py` with slightly different implementations (issues.py guards `if not user_id: return`, operations.py does not). No shared utility exists.
5. **Notification delivery failure silently drops**: `_notify()` in both routes is `await`ed inline in the request path. If the MongoDB write fails, the triggering action still proceeds but the notification is silently lost (no try/except around `_notify` calls at the call sites).
6. **Unread count does use count_documents**: `GET /api/notifications/unread-count` correctly uses `count_documents` — this is fine. But `GET /api/notifications` fetches `total` via `count_documents` then issues a separate `.find()`. On page > 1 with an empty persistent set, digest items are not added, resulting in a misleading total.
7. **No connection leak guard in sse.py**: `disconnect()` removes the queue by identity check, but `publish()` iterates over `list(_connections[channel].values())` — a snapshot. If a client disconnects during a publish burst, the entry is cleaned by `disconnect()` eventually, but only when the SSE route catches the disconnect. There is no generator-level timeout if the client disappears silently (TCP reset without FIN).
8. **mark-all-read race**: `PATCH /mark-all-read` issues `update_many` with `{"read": False}`. Two concurrent calls can both match the same documents. The second `update_many` will match 0 documents (already updated) — this is safe and idempotent by coincidence, but there is no idempotency key or ETag guard to prevent duplicated audit trail entries.
9. **Zero notification tests**: Searching `tests/backend/` for notification-specific test files returns nothing. Notification reads, concurrent mark-read, fan-out behavior, and delivery failure paths have zero unit or integration coverage.

**Entering baseline:** 387 backend tests, 0 skipped.

---

## Functional Requirements

**FR5.1 — Keepalive format unification**: The SSE generator in `chat.py` MUST send keepalive events as `data: {"type":"keepalive"}\n\n` (JSON data events) to match the frontend's `onEvent` handler, not as SSE comment lines.

**FR5.2 — SSE service keepalive loop**: `services/sse.py` MUST implement a background keepalive loop that publishes a `{"type":"ping"}` event to all active channels every `KEEPALIVE_SECONDS` seconds. The loop must be started at app startup and must not block or suppress connection cleanup.

**FR5.3 — Chat SSE reconnect guidance**: When `sendMessageStream()` encounters a network error or the backend closes the stream unexpectedly (not due to `done` event), the frontend MUST emit a user-visible retry option or call `onEvent({type: 'stream_error', retryable: true})`. A silent failure is not acceptable.

**FR5.4 — Shared notification utility**: A single `services/notification_service.py` module MUST export a `create_notification(db, *, user_id, type, message, source_id, source_type, school_id)` async function. Both `operations.py` and `issues.py` must be migrated to use it, removing the duplicated `_notify()` definitions.

**FR5.5 — Notification delivery fail-open with logging**: Call sites in `operations.py` and `issues.py` that call `_notify()` (or the new shared utility) MUST wrap the call in `try/except Exception` and log a `logger.warning` with `notification_delivery_failed: true` when the write fails. The parent action must still succeed.

**FR5.6 — Notification `title` field standardization**: `POST /api/notifications` body accepts `message` but the GET response shape from direct DB inserts in `_notify()` (operations/issues) has no `title` field, while the GET endpoint enriches responses with digest items that DO have `title`. The direct `_notify` inserts must include a `title` field so all notification documents have a consistent shape.

**FR5.7 — SSE connection leak guard**: The SSE generator in `chat.py` MUST detect client disconnects within `KEEPALIVE_INTERVAL + 1` seconds. When `request.is_disconnected()` returns True (FastAPI/Starlette), the generator must break its loop and call `sse.disconnect()`. Test: generator exits within 6 s of simulated disconnect.

**FR5.8 — Unread count pagination consistency**: `GET /api/notifications` MUST return `total` that reflects only persistent notifications (not digest items) in the `meta` block so that frontend pagination logic can correctly determine if more pages exist. Digest items must be marked `is_digest: true` (already done) and excluded from `total`.

---

## Non-Functional Requirements

**NFR5.1 — SSE keepalive latency**: A keepalive event must be sent to any idle SSE connection within 30 seconds of the last data event. This prevents load balancers (ALB/Nginx) with 60 s idle timeouts from terminating silent connections.

**NFR5.2 — Notification write latency**: The shared `create_notification()` call must not add more than 50 ms to the parent request's P99 latency. If the write cannot complete within 200 ms (configurable), it must be logged and skipped (fail-open).

**NFR5.3 — SSE generator memory**: A single SSE generator must not hold more than 100 pending events in its queue (already enforced by `asyncio.Queue(maxsize=100)` with eviction). This constraint must be documented and tested.

**NFR5.4 — Fan-out scale**: The notification fan-out for high-severity incidents (notifies all owners/principals) must handle up to 50 recipients without blocking the request for more than 2 s total. Parallel `asyncio.gather` with a semaphore limit must replace the sequential loop.

---

## Architecture Requirements

**AR5.1 — SSE service in-process vs pub/sub**: `services/sse.py` uses an in-process `defaultdict` of queues. This works only for single-process deployments. The in-process constraint MUST be documented in a comment at the top of `sse.py`. A future migration path to Redis pub/sub MUST be noted. For Part 5, in-process is acceptable.

**AR5.2 — Notification collection indexing**: The `notifications` collection MUST have compound indexes on `(schoolId, user_id, read, created_at DESC)` for `unread-count` and `GET /notifications`. Without this, queries do a collection scan at scale. Verify in `database.py` index creation, add if missing, add migration.

**AR5.3 — SSE session isolation**: Each chat SSE stream is keyed by `X-SSE-Session-ID` header (from `chat.py` / `api.js`). The session ID must be validated as a non-empty string at the server. An empty or missing session ID must fall back to a UUID generated server-side, with a `logger.warning` emitted.

---

## FR Coverage Map

| FR | Story | Notes |
|----|-------|-------|
| FR5.1 | P5.1 | keepalive format fix |
| FR5.2 | P5.2 | sse.py keepalive loop |
| FR5.3 | P5.3 | frontend stream error |
| FR5.4 | P5.4 | shared notification service |
| FR5.5 | P5.4 | fail-open delivery |
| FR5.6 | P5.4 | title field standardization |
| FR5.7 | P5.5 | disconnect detection |
| FR5.8 | P5.6 | pagination meta accuracy |
| NFR5.1 | P5.1 + P5.2 | keepalive timing |
| NFR5.4 | P5.7 | fan-out parallelism |
| AR5.2 | P5.8 | index audit |

---

## Epic P5: Notifications + Real-time (SSE) Hardening

### Story P5.1: Fix SSE keepalive format in chat.py

**Problem:** `keepalive_event()` in `chat.py` returns `":keepalive\n\n"` — an SSE comment line (lines starting with `:` are comments in the SSE spec). The `sendMessageStream()` function in `frontend/src/lib/api.js` only processes lines starting with `data: `. SSE comment lines are silently skipped by the buffer-splitting logic. Meanwhile, `ChatInterface.js` contains an explicit handler `event.type === 'keepalive'` that expects a JSON data event. The result: keepalive events sent from the server do NOT reach the frontend handler. The 60 s idle-timeout protection the keepalives were meant to provide is ineffective.

**Scope:**
- Change `keepalive_event()` in `backend/routes/chat.py` to return `'data: {"type":"keepalive"}\n\n'`
- Verify `ChatInterface.js` `event.type === 'keepalive'` handler comment says "just prevents SSE timeout" — this is the intended behavior, no change needed on frontend
- Add unit test: `keepalive_event()` output parses as JSON with `type == "keepalive"`
- Add unit test: keepalive is sent to queue within `KEEPALIVE_INTERVAL` seconds of last data event (integration smoke test using asyncio)
- Update `test_p5_sse_robustness.py` to cover the data format

**Acceptance Criteria:**

Given a chat SSE stream that has been idle for `KEEPALIVE_INTERVAL` seconds,
When the keepalive timer fires,
Then the event yielded by the generator starts with `data: ` and deserializes to `{"type": "keepalive"}`.

Given the frontend receives a keepalive event,
When `onEvent` is called with `{type: "keepalive"}`,
Then no UI state changes occur and no error is thrown.

Given the `keepalive_event()` function,
When called with no arguments,
Then the return value starts with `"data: "` and does NOT start with `":"`.

- `test_p5_sse_robustness.py` updated: keepalive format test passes
- All 387 existing tests still pass

---

### Story P5.2: Implement keepalive loop in services/sse.py

**Problem:** `services/sse.py` defines `KEEPALIVE_SECONDS = 30` but never uses it. The module has no background loop that pings idle channels. SSE connections that are subscribed via `subscribeSSE()` (the non-chat push channel) will be silently dropped by load balancers after 60 s of inactivity. This affects the notification push path used for real-time badge updates.

**Scope:**
- Add a `keepalive_loop()` async coroutine in `services/sse.py`:
  - Runs forever (until cancelled)
  - Every `KEEPALIVE_SECONDS` seconds, calls `publish(channel, {"type": "ping"})` for every active channel
  - Uses `asyncio.sleep(KEEPALIVE_SECONDS)` not a blocking sleep
  - Handles `asyncio.CancelledError` cleanly
- Start the loop as a background task in `server.py` `startup()` event, store in `app.state.sse_keepalive_task`
- Cancel the task in `shutdown()` event
- Add unit tests for `keepalive_loop()`:
  - After `KEEPALIVE_SECONDS`, a ping event appears in a subscribed queue
  - CancelledError causes clean exit
- Add test: if no channels are active, keepalive loop does not error

**Acceptance Criteria:**

Given one active SSE channel with one connected client,
When `KEEPALIVE_SECONDS` seconds elapse without any other publish,
Then a `{"type": "ping"}` event is placed in the client's queue.

Given the keepalive task is running,
When the application shuts down,
Then the task is cancelled and exits cleanly without logging an unhandled exception.

Given no active channels,
When the keepalive loop fires,
Then no error is raised and nothing is published.

- `services/sse.py` `KEEPALIVE_SECONDS` is used by the loop (not a dead constant)
- `server.py` starts and stops the keepalive task
- At least 3 unit tests in `tests/backend/unit/test_sse_service.py`
- All 387 existing tests still pass

---

### Story P5.3: Frontend chat SSE stream error recovery

**Problem:** `sendMessageStream()` in `frontend/src/lib/api.js` uses a raw `fetch` + `ReadableStream` reader. If the backend restarts mid-conversation, the reader's `done` flag becomes `true` without a `{"type":"done"}` event having been received. The `await sendMessageStream(...)` call resolves silently — no error is thrown, no UI feedback is given. The user sees a frozen "streaming..." state with no way to retry. `subscribeSSE()` has a 3 s reconnect loop but `sendMessageStream` has no equivalent.

**Scope:**
- Modify `sendMessageStream()` in `frontend/src/lib/api.js`:
  - Track whether a `{"type":"done"}` event was received during the stream
  - If the reader reaches `done: true` (stream closed) WITHOUT a prior `done` event, call `onEvent({type: 'stream_error', retryable: true, reason: 'stream_closed_without_done'})`
  - Do NOT auto-reconnect for chat (the server has already created the message context; a reconnect would create a duplicate AI call) — surface a user-visible retry button instead
- Modify `ChatInterface.js` to handle `event.type === 'stream_error'`:
  - Clear streaming state
  - Display an inline error message: "Connection lost. Tap to retry." with a retry button that re-submits the last message
- Add a `stream_error` entry to `ChatInterface.js`'s existing event type handlers

**Acceptance Criteria:**

Given a chat stream where the backend closes the connection before sending `{"type":"done"}`,
When the reader exhausts,
Then `onEvent` is called with `{type: "stream_error", retryable: true}`.

Given a `stream_error` event is received,
When `ChatInterface.js` processes it,
Then the streaming spinner is hidden, the message input is re-enabled, and a "Connection lost. Retry?" message appears.

Given the user taps "Retry",
When the retry action fires,
Then the last user message text is re-submitted as a new stream request.

- Frontend `api.js` has done-tracking logic
- `ChatInterface.js` handles `stream_error`
- No regression on normal happy-path streams

---

### Story P5.4: Shared notification service + fail-open delivery

**Problem:** `_notify()` is defined independently in `backend/routes/operations.py` (lines 61–73) and `backend/routes/issues.py` (lines 57–70) with different behavior: `issues.py` guards `if not user_id: return` while `operations.py` does not. Neither has try/except — a MongoDB write failure will propagate as an unhandled exception and roll back the parent action. The `POST /api/notifications` endpoint (`notifications.py`) uses `add_school_id()` while the inline `_notify()` helpers manually set `schoolId`. There is no `title` field in `_notify()` inserts, creating a schema inconsistency with digest items and manually created notifications.

**Scope:**
- Create `backend/services/notification_service.py`:
  ```python
  async def create_notification(
      db, *, user_id: str, notification_type: str,
      title: str = "", message: str,
      source_id: str = "", source_type: str = "",
      school_id: str
  ) -> bool:
      """Create a persistent notification. Returns True on success, False on failure (fail-open)."""
  ```
  - Guards `if not user_id: return False`
  - Uses `add_school_id()` for tenant field
  - Includes `title` field in the inserted document
  - Wraps `insert_one` in try/except, logs `logger.warning("notification_write_failed", ...)` on error, returns False
- Remove `_notify()` from `operations.py` and `issues.py`
- Import and use `create_notification()` at all 8 call sites (3 in issues.py, 5 in operations.py)
- Update `POST /api/notifications` endpoint in `notifications.py` to also require `title` field
- Add unit tests in `tests/backend/unit/test_notification_service.py`:
  - Happy path: notification inserted, True returned
  - Missing user_id: returns False, no insert
  - DB error: returns False, warning logged, no exception raised

**Acceptance Criteria:**

Given a leave approval action that triggers notification delivery,
When the MongoDB `insert_one` raises an exception,
Then the leave approval response still returns 200 OK and a `logger.warning` is emitted with `notification_write_failed: true`.

Given `create_notification(db, user_id="", ...)` is called with an empty user_id,
When the function executes,
Then it returns False immediately without touching the database.

Given a successful notification write,
When the document is inserted,
Then it has `schoolId`, `user_id`, `type`, `title`, `message`, `source_record_id`, `source_record_type`, `read`, and `created_at` fields.

- `_notify()` removed from `operations.py` and `issues.py` (grep returns zero hits)
- `notification_service.py` exists with at least 5 unit tests
- All 8 call sites migrated
- All 387 existing tests still pass

---

### Story P5.5: SSE generator disconnect detection

**Problem:** The SSE generator in `chat.py` sends keepalive events every `KEEPALIVE_INTERVAL` (5 s) seconds, but if a client drops without sending a TCP FIN (e.g. browser tab crash, mobile radio loss), the server-side generator continues running indefinitely. The generator never calls `sse.disconnect()` and the queue entry in `_connections` is never cleaned up. Over time, stale queues accumulate in memory and LLM calls continue being made for no-longer-connected clients.

**Scope:**
- In the SSE generator `_sse_generator()` in `chat.py`, add a periodic disconnect check:
  - Before each keepalive yield, call `await request.is_disconnected()`
  - If True, break the loop and ensure `sse.disconnect()` is called in the `finally` block
- Verify the generator already has a `finally` block that calls `sse.disconnect()` — if not, add one
- Add a test in `tests/backend/unit/test_sse_disconnect.py`:
  - Simulate `is_disconnected()` returning True after N keepalive cycles
  - Verify the generator terminates and queue is cleaned up
- Document the KEEPALIVE_INTERVAL value with a comment: "must be < load balancer idle timeout ÷ 2"

**Acceptance Criteria:**

Given an active SSE generator,
When `request.is_disconnected()` returns True on the next keepalive check,
Then the generator exits the loop within `KEEPALIVE_INTERVAL + 1` seconds.

Given the generator exits (either normally or on disconnect),
When execution reaches the `finally` block,
Then `sse.disconnect(channel, session_id, queue)` is called exactly once.

Given a stale session_id entry in `_connections`,
When `sse.disconnect()` is called with the correct queue reference,
Then `_connections[channel]` no longer contains the session_id key.

- Generator has disconnect check on keepalive path
- `finally` block guaranteed
- At least 3 unit tests covering exit paths
- All 387 existing tests still pass

---

### Story P5.6: Notification pagination meta accuracy

**Problem:** `GET /api/notifications` computes `total` as `db.notifications.count_documents(query)` — the count of persistent notifications only. But the response `data` array is `persistent + digest`, and the `meta.total` is `total + len(digest)`. This inflates `total` with a variable number of digest items that depend on school state (pending leaves, fees, etc.). Frontend pagination logic using `total` to determine "has more pages" will over-count on page 1 and under-count on page 2+. Additionally, when `persistent` is empty and `page == 1`, a fallback `"All Good"` item is injected but `total` stays at 0, making the response seem inconsistent.

**Scope:**
- Change `meta.total` to return only the persistent notification count (what is in MongoDB), not `total + len(digest)`
- Add a separate `meta.digest_count` field showing how many digest items were appended on page 1
- Update the "All Good" fallback: set `meta.has_fallback: true` instead of injecting into the data count
- Update `meta` response shape: `{page, limit, total, digest_count, has_fallback}`
- Add unit tests:
  - `total` does not include digest items
  - `digest_count` equals the number of digest items appended
  - `has_fallback` is True when no persistent + no digest items exist

**Acceptance Criteria:**

Given a user with 5 persistent notifications and 3 digest items,
When they request `GET /api/notifications?page=1`,
Then `meta.total` equals 5, `meta.digest_count` equals 3, and `data` has 8 items.

Given a user with 0 notifications and 0 digest items,
When they request `GET /api/notifications`,
Then `meta.total` equals 0, `meta.has_fallback` equals true, and the "All Good" item is in `data`.

Given a user on page 2,
When they request `GET /api/notifications?page=2`,
Then `meta.digest_count` equals 0 (digest only on page 1).

- `meta` shape documented in route docstring
- At least 3 unit tests in `tests/backend/unit/test_notifications.py`
- All 387 existing tests still pass

---

### Story P5.7: Parallel fan-out for high-severity notifications

**Problem:** In `operations.py`, when a high-severity incident is created, the code fetches all users with roles `owner`/`admin` and notifies them in a sequential `for` loop calling `_notify()` one at a time. For a school with 10 admins, this serializes 10 MongoDB inserts in the hot request path. At 5 ms per insert, this adds 50 ms; at peak school usage the insert latency can spike to 20 ms, adding 200 ms to a user-facing incident creation call.

**Scope:**
- After migrating to `create_notification()` (from P5.4), replace sequential fan-out loops in `operations.py` with `asyncio.gather(*[create_notification(...) for target in targets], return_exceptions=True)`
- Add a semaphore limit of 10 concurrent notification writes: `asyncio.Semaphore(10)`
- Log a summary: `logger.info("fan_out_complete", notifications_sent=N, notifications_failed=F)`
- Apply the same pattern to `issues.py`'s multi-target fan-out
- Add unit test: 20 targets — all notifications attempted, partial failure (5 fail) — parent action succeeds

**Acceptance Criteria:**

Given a high-severity incident creation with 15 owner/admin users to notify,
When the endpoint is called,
Then all 15 notification inserts are attempted via `asyncio.gather` (not a sequential loop).

Given 3 of the 15 notification writes fail,
When `asyncio.gather(return_exceptions=True)` collects results,
Then the 3 failures are logged as warnings and the incident creation response is 201.

Given the gather completes,
When `logger.info` is called,
Then the log record contains `notifications_sent` and `notifications_failed` counts.

- Sequential fan-out loops replaced in both files
- Semaphore prevents > 10 concurrent writes
- At least 2 unit tests
- All 387 existing tests still pass

---

### Story P5.8: Notifications collection index audit + test coverage baseline

**Problem:** `GET /api/notifications/unread-count` queries `{schoolId, user_id, read: False}`. `GET /api/notifications` queries `{schoolId, user_id}` with a sort on `created_at`. Without a compound index covering these patterns, each query does a collection scan. A school with 10,000 notification documents across 200 users will have P99 latency above 100 ms. Additionally, there are ZERO dedicated notification tests — not a single test file covers `notifications.py` routes.

**Scope:**
- Audit `backend/database.py` `_create_indexes()` for `notifications` collection indexes
- Add compound index: `{schoolId: 1, user_id: 1, read: 1, created_at: -1}` if not present
- Add migration `019_notifications_index.py` and add to `run_all.py`
- Create `tests/backend/unit/test_notifications.py` with at least 8 tests:
  1. `GET /notifications` returns persistent + digest items
  2. `GET /notifications?page=2` returns no digest items
  3. `GET /notifications/unread-count` returns correct count
  4. `PATCH /{id}/read` marks one notification read
  5. `PATCH /{id}/read` returns 404 for wrong user_id
  6. `PATCH /mark-all-read` marks multiple unread notifications
  7. `PATCH /mark-all-read` is idempotent (second call succeeds, 0 modified is OK)
  8. `POST /` (create notification) requires owner/admin role

**Acceptance Criteria:**

Given `database.py` `_create_indexes()`,
When called on a fresh database,
Then the `notifications` collection has a compound index on `(schoolId, user_id, read, created_at)`.

Given two concurrent `PATCH /mark-all-read` calls for the same user,
When both complete,
Then all unread notifications are marked read and neither call raises an error.

Given a teacher user calls `PATCH /{id}/read` for a notification belonging to a different user,
When the request is processed,
Then a 404 is returned (user_id filter prevents cross-user reads).

- Migration 019 created and in `run_all.py`
- `database.py` has the index call
- 8+ unit tests covering all major notification paths
- All 387 + new tests pass

---

## Implementation Order Recommendation

1. **P5.4** — Create `notification_service.py` first (unblocks P5.5, P5.7, and provides test infrastructure)
2. **P5.1** — Fix keepalive format (high-impact, 2-line change, low risk)
3. **P5.5** — Disconnect detection (prevents resource leaks in production)
4. **P5.8** — Add index and test coverage (required before performance testing)
5. **P5.6** — Pagination meta fix (correctness, medium risk)
6. **P5.2** — SSE service keepalive loop (infrastructure work)
7. **P5.7** — Fan-out parallelism (depends on P5.4 completion)
8. **P5.3** — Frontend stream error recovery (last as it requires frontend + backend coordination)

---

## Epic P5: Retrospective

A retrospective entry for Part 5 to be completed after all P5.1–P5.8 stories are done.
