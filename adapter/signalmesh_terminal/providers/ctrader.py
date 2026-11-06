"""FUTURE: cTrader Open API market data (Phase 6+). Stub — NOT_CONFIGURED."""
from __future__ import annotations

from .base import ProviderError


class CTraderProvider:
    name = "ctrader"
    is_fixture = False
    configured = False

    def readiness(self) -> dict:
        return {"reachable": False, "ok": False, "state": "NOT_CONFIGURED",
                "note": "cTrader Open API market data is a Phase 6 item"}

    def __getattr__(self, item):
        def _refuse(*_a, **_k):
            raise ProviderError("cTrader provider is not configured (Phase 6)", state="NOT_CONFIGURED")
        return _refuse
