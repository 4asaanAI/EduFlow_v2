# ADR-002: Audit Write-ahead Gate — synchronous vs fail-open

**Date:** 2026-05-15
**Status:** Accepted
**Part:** 4 — Multi-tenancy + Data Layer

## Decision

**Fail-open with warning log (Option B).** Audit pre-write failures are logged but do not block AI responses.

## Context

The AI dispatch path writes a pre-write audit record to MongoDB before calling the LLM. If this write fails (DB slow, network hiccup), the entire AI request fails. For attendance recording at 7:30am or fee collection during peak hours, this is a poor availability trade-off.

## Consequences

**Positive:**
- DB hiccups (even Atlas M10 99.995% SLA has occasional latency spikes) no longer cascade to teacher/principal UI failures
- Simpler than async queue (no Redis/SQS dependency)

**Negative:**
- Rare audit gaps during DB stress events
- Audit log is no longer a 100% complete record

## Acceptable at current scale?

Yes. Reasons:
1. Audit log is operational (not compliance/legal)
2. MongoDB Atlas M10 outages are rare (<1hr/year)
3. Gap rate expected <0.01% of AI requests
4. Re-evaluation trigger: if gap rate exceeds 0.1% in production, escalate to async queue

## Implementation

```python
# In AI dispatch path (routes/chat.py or wherever pre-write audit lives):
try:
    await db.audit_log.insert_one({
        "action": action_name,
        "user_id": user["id"],
        "status": "pending",
        "timestamp": datetime.now(timezone.utc),
    })
except Exception:
    logger.warning(
        "audit_pre_write_failed",
        exc_info=True,
        extra={"action": action_name, "user_id": user.get("id")},
    )
    # Proceed — do not re-raise

# Continue with AI dispatch...
```

## Re-evaluation triggers

- Audit failure rate > 0.1% over any 7-day window
- Legal/compliance requirement added requiring complete audit trail
- Migration to async architecture for other reasons (e.g. job queue for email)
