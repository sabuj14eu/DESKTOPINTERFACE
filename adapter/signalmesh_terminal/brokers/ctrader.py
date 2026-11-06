"""MODE C — CTRADER EXECUTION (Phase 6). Stub: NOT_CONFIGURED."""
from __future__ import annotations

from .base import BrokerAdapter


class CTraderBroker(BrokerAdapter):
    mode = "CTRADER"
    label = "cTrader (Open API)"

    def describe(self) -> dict:
        return {"mode": self.mode, "label": self.label, "state": "NOT_CONFIGURED",
                "note": "Phase 6: cTrader Open API pending orders with explicit approval. Not built; nothing can be sent."}
