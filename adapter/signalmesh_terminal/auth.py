"""SAME LOGIN AS SIGNALMESH — no second password.

The terminal is served under the SignalMesh site (/terminal/), so the browser sends
SignalMesh's own `bb_session` cookie with every terminal request. This module asks
SignalMesh whether that cookie is a live session, by calling one of its own
session-protected, read-only JSON routes with the cookie and NOT following
redirects: 200 + JSON = logged in; a redirect to /login = not logged in.

Nothing is decoded or trusted locally: SignalMesh remains the only authority on
who is logged in (its own revocation, ban and expiry rules apply unchanged).
The verdict is cached per cookie for `auth_cache_s` so one page does not become
dozens of calls to the platform. Read-only: GET only.
"""
from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass

import httpx

from .config import get_settings

PROBE = "/chart/levels.json"      # session-protected JSON, cheap, read-only


@dataclass(frozen=True)
class Verdict:
    ok: bool
    why: str = ""


_cache: dict[str, tuple[float, Verdict]] = {}
_lock = threading.Lock()
_client: httpx.Client | None = None


def _c() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(timeout=get_settings().signalmesh_timeout_s, follow_redirects=False)
    return _client


def session_gate(cookie: str) -> Verdict:
    if not cookie:
        return Verdict(False, "no bb_session cookie — not logged in to SignalMesh")
    s = get_settings()
    key = hashlib.sha256(cookie.encode()).hexdigest()
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
        if hit and hit[0] > now:
            return hit[1]
    try:
        r = _c().get(s.signalmesh_url.rstrip("/") + PROBE, params={"symbol": s.default_symbol},
                     cookies={"bb_session": cookie}, headers={"Accept": "application/json"})
        if r.status_code == 200 and "json" in r.headers.get("content-type", ""):
            v = Verdict(True)
        elif r.status_code in (301, 302, 303, 307, 308):
            v = Verdict(False, "SignalMesh session expired or logged out")
        else:
            v = Verdict(False, f"SignalMesh answered {r.status_code} to the session check")
    except httpx.HTTPError as exc:
        v = Verdict(False, f"SignalMesh unreachable for the session check: {type(exc).__name__}")
    with _lock:
        _cache[key] = (now + (s.auth_cache_s if v.ok else 5.0), v)
    return v


def reset_for_tests() -> None:
    global _client
    with _lock:
        _cache.clear()
    _client = None
