"""
In-process concurrency gate for AI chat requests.

Problem: the backend runs as a single gunicorn/uvicorn worker (see Procfile) on
whatever EC2 instance type the environment is sized to. Bedrock/LLM calls are
dispatched via `asyncio.to_thread`, which borrows from Python's default
ThreadPoolExecutor - sized `min(32, cpu_count + 4)`. Past that many
simultaneous AI calls, new requests don't fail, they silently queue and every
user's response gets slower with no explanation.

This module caps how many AI chat turns can be "in flight" at once, sized off
the instance's actual vCPU count (so it scales automatically if the instance
type changes - no hardcoded number to update per environment), and rejects
the (limit + 1)-th concurrent request immediately with a clear message
instead of letting it queue invisibly.

Single-process only: the counter lives in this process's memory. If gunicorn
is ever scaled to more than one worker, or the app runs on more than one
instance, this needs to move to a shared store (e.g. Redis) to stay accurate
across processes - each process would otherwise enforce its own separate cap.
"""

from __future__ import annotations

import os
import asyncio
import logging

logger = logging.getLogger(__name__)

# How many concurrent AI requests one vCPU can carry before responses start
# lagging. Tuned to match asyncio.to_thread's default executor sizing
# (min(32, cpu_count + 4)) rather than picked arbitrarily.
_DEFAULT_CONCURRENCY_PER_CPU = 3
_MIN_CONCURRENT_REQUESTS = 2


def _resolve_max_concurrent() -> int:
    """
    Resolve the concurrent-AI-request ceiling for this instance.

    Priority:
      1. AI_MAX_CONCURRENT_REQUESTS env var - explicit override, set this if
         you want a fixed number regardless of instance size.
      2. AI_CONCURRENCY_PER_CPU env var (default 3) x detected vCPU count -
         scales automatically with instance type (t3a.small's 2 vCPUs vs.
         a bigger box's more vCPUs) with no code change needed.
    """
    override = os.environ.get("AI_MAX_CONCURRENT_REQUESTS", "").strip()
    if override:
        try:
            return max(1, int(override))
        except ValueError:
            logger.warning("Invalid AI_MAX_CONCURRENT_REQUESTS=%r; falling back to per-CPU sizing", override)

    per_cpu_raw = os.environ.get("AI_CONCURRENCY_PER_CPU", "").strip()
    try:
        per_cpu = int(per_cpu_raw) if per_cpu_raw else _DEFAULT_CONCURRENCY_PER_CPU
    except ValueError:
        per_cpu = _DEFAULT_CONCURRENCY_PER_CPU

    cpu_count = os.cpu_count() or 1
    return max(_MIN_CONCURRENT_REQUESTS, cpu_count * per_cpu)


MAX_CONCURRENT_AI_REQUESTS = _resolve_max_concurrent()

HEAVY_USAGE_MESSAGE = (
    "AI is under heavy use right now - too many people are chatting at the same "
    "time. Please wait a few seconds and try again."
)

_lock = asyncio.Lock()
_in_flight = 0


async def try_acquire_slot() -> bool:
    """
    Non-blocking: claim one of the limited AI-request slots.

    Returns True if a slot was claimed (caller must call release_slot() when
    done, in a finally block). Returns False immediately - never waits - if
    the instance is already at capacity, so the caller can show the
    heavy-usage message right away instead of queuing silently.
    """
    global _in_flight
    async with _lock:
        if _in_flight >= MAX_CONCURRENT_AI_REQUESTS:
            return False
        _in_flight += 1
        return True


async def release_slot() -> None:
    """Release a slot claimed by try_acquire_slot(). Floors at 0."""
    global _in_flight
    async with _lock:
        _in_flight = max(0, _in_flight - 1)


def current_in_flight() -> int:
    """Read-only snapshot for dashboards/health checks - not lock-guarded, advisory only."""
    return _in_flight
