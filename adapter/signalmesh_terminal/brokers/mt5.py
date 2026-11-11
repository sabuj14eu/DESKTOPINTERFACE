"""MODE B — MT5 EXECUTION (Phase 6). DISABLED.

When built, this adapter will talk to the EXISTING SignalMesh MT5
integration (the reporter / executor on the Windows box), never to MT5
directly from the terminal, and only after Phase 6's gates exist. It changes
no MT5 permission today: it holds no credentials and opens no connection.
"""
from __future__ import annotations

from .base import BrokerAdapter, OrderIntent

_TYPE = {("BUY", "LIMIT"): "ORDER_TYPE_BUY_LIMIT", ("SELL", "LIMIT"): "ORDER_TYPE_SELL_LIMIT",
         ("BUY", "STOP"): "ORDER_TYPE_BUY_STOP", ("SELL", "STOP"): "ORDER_TYPE_SELL_STOP",
         ("BUY", "MARKET"): "ORDER_TYPE_BUY", ("SELL", "MARKET"): "ORDER_TYPE_SELL"}


class MT5Broker(BrokerAdapter):
    mode = "MT5"
    label = "MT5 (via existing SignalMesh integration)"
    platform = "MT5"
    account_types = ("MT5 Demo", "MT5 Live")

    def describe(self) -> dict:
        return self._describe("DISABLED", "Phase 6: approve-and-place pending orders through the existing MT5 integration. "
                                          "Not built; nothing can be sent.")

    def translate(self, intent: OrderIntent) -> dict:
        """MqlTradeRequest-shaped dictionary (MetaTrader 5 order_send fields). Never sent."""
        return {"adapter": self.mode, "sent_to_broker": False, "dry_run": True, "request": {
            "action": "TRADE_ACTION_DEAL" if intent.order_kind == "MARKET" else "TRADE_ACTION_PENDING",
            "symbol": None, "symbol_canonical": intent.symbol,
            "type": _TYPE.get((intent.side, intent.order_kind)), "price": intent.entry, "sl": intent.sl, "tp": intent.tp,
            "volume": intent.volume_lots, "comment": intent.signal_id, "login": intent.account_id or None},
            "unresolved": [w for w, missing in (
                ("broker symbol — from the account's own symbol table", True),
                ("volume — from SignalMesh risk checks", intent.volume_lots is None),
                ("order type — LIMIT or STOP needs the live price at approval time", intent.order_kind == "UNRESOLVED")) if missing]}
