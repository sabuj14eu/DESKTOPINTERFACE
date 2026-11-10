"""MODE C — CTRADER EXECUTION (Phase 6). NOT_CONFIGURED.

When built: cTrader Open API (OAuth, Protobuf over TLS). Today it holds no
application id, no token and opens no connection."""
from __future__ import annotations

from .base import BrokerAdapter, OrderIntent


class CTraderBroker(BrokerAdapter):
    mode = "CTRADER"
    label = "cTrader (Open API)"
    platform = "CTRADER"
    account_types = ("cTrader Demo", "cTrader Live")

    def describe(self) -> dict:
        return self._describe("NOT_CONFIGURED", "Phase 6: cTrader Open API pending orders with explicit approval. "
                                                "Not built; nothing can be sent.")

    def translate(self, intent: OrderIntent) -> dict:
        """ProtoOANewOrderReq-shaped dictionary (cTrader Open API field names). Never sent."""
        kind = intent.order_kind if intent.order_kind in ("LIMIT", "STOP", "MARKET") else None
        return {"adapter": self.mode, "sent_to_broker": False, "dry_run": True, "request": {
            "payloadType": "ProtoOANewOrderReq", "ctidTraderAccountId": intent.account_id or None,
            "symbolId": None, "symbol_canonical": intent.symbol, "orderType": kind, "tradeSide": intent.side,
            "limitPrice": intent.entry if kind == "LIMIT" else None, "stopPrice": intent.entry if kind == "STOP" else None,
            "stopLoss": intent.sl, "takeProfit": intent.tp, "volume": intent.volume_lots, "label": intent.signal_id},
            "unresolved": [w for w, missing in (
                ("symbolId — from the account's own symbol list", True),
                ("volume — from SignalMesh risk checks", intent.volume_lots is None),
                ("order type — LIMIT or STOP needs the live price at approval time", kind is None)) if missing]}
