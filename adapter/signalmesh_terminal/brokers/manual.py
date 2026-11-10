"""MODE A — MANUAL. The terminal shows the pending order; the user places
it in their own platform by hand. Nothing leaves this process."""
from __future__ import annotations

from .base import BrokerAdapter, PlanForTicket


def _px(v, d):
    return "—" if v is None else f"{float(v):.{d}f}"


class ManualBroker(BrokerAdapter):
    mode = "MANUAL"
    label = "Manual (you place the order)"

    def describe(self) -> dict:
        return self._describe("AVAILABLE", "the terminal prints the pending order; you place it yourself — nothing is sent")

    def ticket(self, plan: PlanForTicket, decimals: int) -> dict:
        if plan.engine_status != "READY":
            return {"mode": self.mode, "sent_to_broker": False, "available": False,
                    "note": f"no ticket — the engine says {plan.engine_status}, not READY"}
        lines = [
            f"{plan.symbol} · {plan.order_type}",
            f"Entry {_px(plan.entry, decimals)}",
            f"SL    {_px(plan.sl, decimals)}",
            f"TP1   {_px(plan.tp1, decimals)}" + (f" · R:R {plan.rr1}" if plan.rr1 is not None else ""),
        ]
        if plan.tp2 is not None:
            lines.append(f"TP2   {_px(plan.tp2, decimals)}")
        lines.append(f"signal {plan.signal_id or '?'} · SignalMesh READY · place manually")
        return {"mode": self.mode, "symbol": plan.symbol, "direction": plan.direction,
                "order_type": plan.order_type, "entry": plan.entry, "sl": plan.sl, "tp1": plan.tp1,
                "tp2": plan.tp2, "rr1": plan.rr1, "signal_id": plan.signal_id,
                "engine_status": plan.engine_status, "text": "\n".join(lines),
                "sent_to_broker": False, "available": True,
                "note": "MANUAL MODE — copy these levels into your own order ticket. The terminal sent nothing."}
