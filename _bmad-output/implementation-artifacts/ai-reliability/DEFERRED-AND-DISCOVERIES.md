# AI Layer Reliability — Deferred Items & Mid-Run Discoveries (running log)

One running file for the whole initiative (protocol rule 6). Every mid-run discovery not fixed in-run gets a row. Review at the START of every run; handle rows belonging to the current epic.

| Date | Epic | What was found | Status | Why deferred / where it gets fixed |
|------|------|----------------|--------|-------------------------------------|
| 2026-07-08 | (pre-run, audit) | Residual unaudited areas: `ai_rate_limiter.py`, `ai_metrics.py`, `ai_shadow_mode.py`, `actor_context.py`, `txn_context.py`, `idempotency.py`, `services/sse.py`, domain service write paths dispatched by AI tools | DEFERRED | Scheduled as story R11.6 (residual audit sweep) |
| 2026-07-08 | (pre-run, standing) | 25 pinned pre-existing test failures | DEFERRED | Standing directive: fix LAST, after all epics ship |
