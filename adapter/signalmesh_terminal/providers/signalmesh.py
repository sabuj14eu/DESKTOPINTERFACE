"""The production provider: GET-only reads of SignalMesh /api/v1.

THE ONLY HTTP VERB IN THIS FILE IS GET. tests/test_read_only.py asserts it
by inspection, so a write cannot be added by accident.
"""
from __future__ import annotations

import httpx

from .base import ProviderError


class SignalMeshProvider:
    name = "signalmesh"
    is_fixture = False

    def __init__(self, base_url: str, api_key: str, timeout_s: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "signalmesh-terminal/0.1 (read-only)"}
        self._client = httpx.Client(timeout=timeout_s)
        self.configured = bool(api_key)

    def _get(self, path: str, params: dict | None = None):
        if not self.configured:
            raise ProviderError("SMT_SIGNALMESH_API_KEY is empty — the adapter has no read key", state="NOT_CONFIGURED")
        try:
            r = self._client.get(self.base_url + path, params=params, headers=self._headers)
        except httpx.HTTPError as exc:
            raise ProviderError(f"SignalMesh unreachable: {type(exc).__name__}: {exc}", state="DOWN") from exc
        if r.status_code in (401, 403):
            raise ProviderError(f"SignalMesh refused the API key ({r.status_code})", state="UNAUTHORIZED", status=r.status_code)
        if r.status_code >= 400:
            detail = ""
            try:
                detail = str(r.json().get("detail", ""))[:200]
            except Exception:  # noqa: BLE001
                detail = r.text[:200]
            raise ProviderError(f"SignalMesh answered {r.status_code} for {path}: {detail}", state="ERROR", status=r.status_code)
        try:
            return r.json()
        except ValueError as exc:
            raise ProviderError(f"SignalMesh answered non-JSON for {path}", state="ERROR") from exc

    # --- readiness (public, no key) -------------------------------------
    def readiness(self) -> dict:
        try:
            r = self._client.get(self.base_url + "/readyz")
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            return {"reachable": True, "http": r.status_code, **(body if isinstance(body, dict) else {})}
        except httpx.HTTPError as exc:
            return {"reachable": False, "ok": False, "error": f"{type(exc).__name__}: {exc}"}

    # --- market mirror ---------------------------------------------------
    def candles(self, symbol: str, tf: str, n: int) -> dict:
        return self._get("/api/v1/market/candles", {"symbol": symbol, "tf": tf, "n": n})

    def snapshot(self, symbol: str) -> dict:
        return self._get("/api/v1/market/snapshot", {"symbol": symbol})

    def desk(self, symbol: str) -> dict:
        return self._get("/api/v1/market/desk", {"symbol": symbol})

    # --- records ---------------------------------------------------------
    def signals(self, limit: int = 200) -> list[dict]:
        return self._get("/api/v1/signals", {"limit": limit})

    def trades(self, limit: int = 200, status: str = "") -> list[dict]:
        return self._get("/api/v1/trades", {"limit": limit, **({"status": status} if status else {})})

    def stats(self) -> dict:
        return self._get("/api/v1/stats")

    def portfolio(self) -> dict:
        return self._get("/api/v1/portfolio")

    # --- news / macro / sources -----------------------------------------
    def news_state(self, symbols: list[str]) -> dict:
        return self._get("/api/v1/news/state", {"symbols": ",".join(symbols)})

    def news_facts(self, symbol: str) -> dict:
        return self._get("/api/v1/news/facts", {"symbol": symbol})

    def macro_scorecard(self) -> dict:
        return self._get("/api/v1/macro/scorecard")

    def macro_engine(self) -> dict:
        return self._get("/api/v1/macro/engine")

    def sources_evidence(self) -> dict:
        return self._get("/api/v1/sources/evidence")

    def ea_performance(self) -> dict:
        return self._get("/api/v1/ea/performance")

    # --- broker accounts (read) ------------------------------------------
    def accounts(self, path: str):
        """Per-account broker rows, if this SignalMesh version has the route (SMT_ACCOUNTS_PATH).
        A 404 raises ProviderError(status=404); the caller then shows the portfolio total."""
        return self._get(path)
