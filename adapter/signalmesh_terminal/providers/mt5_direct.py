"""FUTURE: direct broker market data through MT5 (Phase 6+).

Today SignalMesh's own candles ARE broker data (MT5 via mt5_reporter, stored
closed bars), so the terminal already shows MT5 prices through the
platform. A direct MT5 feed would add the forming bar and bid/ask. It is
a stub so the provider seam exists; it reports NOT_CONFIGURED and is never
selected by default.
"""
from __future__ import annotations

from .base import ProviderError


class MT5DirectProvider:
    name = "mt5_direct"
    is_fixture = False
    configured = False

    def readiness(self) -> dict:
        return {"reachable": False, "ok": False, "state": "NOT_CONFIGURED",
                "note": "direct MT5 market data is a Phase 6 item; SignalMesh's MT5-sourced candles are used instead"}

    def __getattr__(self, item):
        def _refuse(*_a, **_k):
            raise ProviderError("MT5 direct provider is not configured (Phase 6)", state="NOT_CONFIGURED")
        return _refuse
