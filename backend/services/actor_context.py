"""Pinned `actor_ctx` contract for the shared service layer (AI Layer Hardening, AD14).

`ActorContext` is the *exact* set of caller facts a `services/<domain>_service.py`
write function may consume. It is synthesized identically by the REST adapter
(from the JWT `user` dict) and the AI-tool adapter (from the chat `user` + `scope`),
so an AI write and a UI write reach the service with the same authority context.

Hard rule: a service NEVER reads `Request`/`Depends`. If a service needs more than
this contract carries, EXTEND this dataclass — do not reach back into FastAPI.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

from tenant import get_school_id


def _now() -> datetime:
    # R15.4 (P-L1): return tz-aware UTC. The service layer persists `now_iso()`
    # into ~40 collections; a naive stamp made BSON date comparisons ambiguous
    # (naive vs aware mix). On our servers (UTC) this preserves the same instant
    # and only tags the timezone, so `now()` and `now_utc()` now agree.
    return datetime.now(timezone.utc)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ActorContext:
    user_id: Optional[str]
    role: Optional[str]
    sub_category: Optional[str]
    school_id: str
    branch_id: Optional[str]
    actor_name: str = ""
    # Injectable clock for deterministic tests. Per project-context.md, never bind
    # `datetime.now` as a default value — resolve via `(now_fn or _now)()` at call time.
    now_fn: Optional[Callable[[], datetime]] = None

    def now(self) -> datetime:
        return (self.now_fn or _now)()

    def now_iso(self) -> str:
        return self.now().isoformat()

    def now_utc(self) -> datetime:
        return (self.now_fn or _now_utc)()

    def now_utc_iso(self) -> str:
        return self.now_utc().isoformat()


def actor_ctx_from_user(
    user: Optional[dict],
    *,
    school_id: Optional[str] = None,
    branch_id: Optional[str] = None,
    now_fn: Optional[Callable[[], datetime]] = None,
) -> ActorContext:
    """Build the contract identically for both adapters.

    REST adapter: `actor_ctx_from_user(user)` — branch_id comes from the JWT dict.
    AI adapter:   `actor_ctx_from_user(user, branch_id=_branch_id(user, scope))` —
                  branch_id is resolved from the chat scope first.
    """
    user = user or {}
    return ActorContext(
        user_id=user.get("id"),
        role=user.get("role"),
        sub_category=user.get("sub_category"),
        school_id=school_id or get_school_id(),
        branch_id=branch_id if branch_id is not None else user.get("branch_id"),
        actor_name=user.get("name") or "",
        now_fn=now_fn,
    )
