"""Ambient transaction-session propagation for the shared service layer
(AI Layer Hardening, AD4 / Story D.2).

The atomic executor (`ai/plan_executor.py`) opens ONE Motor transaction per confirmed
plan and must thread that `session=` through every write the step performs. The
existing write tools (Epic A–C) call their services with **no** explicit session, so
rather than rewrite every tool/service signature, the executor binds the active session
into a `contextvars.ContextVar` for the duration of the transaction. Each service's
``_session_kwargs(session)`` consults this contextvar when no explicit session is
passed — so a service called anywhere inside the executor's transaction automatically
enlists in it.

Why a contextvar is safe here: it propagates across `await` within the SAME asyncio
task (the `/confirm` request task), and the executor `reset()`s it in a `finally`, so a
session never leaks into an unrelated request. Outside a transaction the contextvar is
``None`` and ``session_kwargs()`` returns ``{}`` — identical to the pre-D.2 behavior.
"""

from __future__ import annotations

import contextvars
from typing import Any, Optional

_current_session: contextvars.ContextVar[Optional[Any]] = contextvars.ContextVar(
    "ai_txn_session", default=None
)


def get_current_session() -> Optional[Any]:
    return _current_session.get()


def set_current_session(session: Optional[Any]):
    """Bind the active transaction session; returns a token for ``reset``."""
    return _current_session.set(session)


def reset_current_session(token) -> None:
    _current_session.reset(token)


def session_kwargs(session: Optional[Any] = None) -> dict:
    """Resolve the effective session: explicit arg wins, else the ambient one.

    Returns ``{"session": <s>}`` when a session is in force, else ``{}`` so callers
    can splat it into a Motor op without passing ``session=None`` to FakeDb.
    """
    effective = session if session is not None else _current_session.get()
    return {"session": effective} if effective is not None else {}
