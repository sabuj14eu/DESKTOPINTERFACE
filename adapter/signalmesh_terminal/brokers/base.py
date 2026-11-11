"""EXECUTION ADAPTER CONTRACT — Phase 6 architecture, shipped DARK.

One SignalMesh signal, any broker: the signal becomes a broker-neutral
`OrderIntent`; each adapter (MT5, cTrader) can TRANSLATE that same intent
into its broker's own request shape. Translation is a pure function — it
builds a dictionary and returns it. Nothing in this package opens a socket
to a broker, and `place()` refuses for every adapter.

In this phase:

  * `describe()`  what the adapter is, which account types it will serve,
                  and that it is disabled.
  * `ticket()`    Mode A only: the pending-order text the USER places by hand.
  * `translate()` the request the adapter WOULD build — returned, never sent.
  * `preflight()` the Phase 6 gates, every one reported NOT BUILT, allowed=False.
  * `place()`     ALWAYS refuses. There is no code path that sends an order.

Phase 6 rules (binding, see docs/EXECUTION_ROADMAP.md): explicit user
approval per order, duplicate-order protection keyed on signal_id,
position reconciliation against the broker before placing, and the risk
checks SignalMesh already owns. None of that exists yet, so nothing may
place.
"""
from __future__ import annotations

from dataclasses import dataclass

GATES = ("engine READY (fresh snapshot)", "explicit user approval of this exact ticket",
         "duplicate protection on signal_id per account", "position reconciliation against the broker",
         "SignalMesh risk limits and emergency stop", "audit journal entry")


class ExecutionRefused(Exception):
    pass


@dataclass(frozen=True)
class PlanForTicket:
    symbol: str
    direction: str
    order_type: str
    entry: float
    sl: float
    tp1: float | None
    tp2: float | None
    rr1: float | None
    signal_id: str
    engine_status: str


@dataclass(frozen=True)
class OrderIntent:
    """Broker-neutral: what SignalMesh recommends, in SignalMesh's own names. No broker
    symbol, no volume — the broker symbol comes from the broker's symbol table and the
    size from SignalMesh's risk checks, both Phase 6."""
    signal_id: str
    symbol: str                    # SignalMesh canonical (GOLD, US100, ...)
    side: str                      # BUY | SELL
    order_kind: str                # LIMIT | STOP | MARKET | UNRESOLVED (needs a live price to tell LIMIT from STOP)
    entry: float | None
    sl: float | None
    tp: float | None
    volume_lots: float | None = None
    account_id: str = ""


def intent_from_plan(plan: PlanForTicket, account_id: str = "") -> OrderIntent:
    words = (plan.order_type or "").upper().split()
    kind = next((w for w in words if w in ("LIMIT", "STOP", "MARKET")), "UNRESOLVED")
    return OrderIntent(signal_id=plan.signal_id, symbol=plan.symbol, side=(plan.direction or (words[0] if words else "")).upper(),
                       order_kind=kind, entry=plan.entry, sl=plan.sl, tp=plan.tp1, account_id=account_id)


def intent_from_signal(sig, account_id: str = "") -> OrderIntent:
    """From a SignalRef. A signal row names no order kind, so it stays UNRESOLVED."""
    return OrderIntent(signal_id=sig.signal_id, symbol=sig.symbol, side=sig.direction, order_kind="UNRESOLVED",
                       entry=sig.entry, sl=sig.sl, tp=sig.tp1, account_id=account_id)


class BrokerAdapter:
    mode = "MANUAL"
    label = "Manual"
    platform = ""                  # MT5 | CTRADER | "" (manual)
    account_types: tuple[str, ...] = ()

    def describe(self) -> dict:
        raise NotImplementedError

    def _describe(self, state: str, note: str) -> dict:
        return {"mode": self.mode, "label": self.label, "state": state, "note": note, "platform": self.platform,
                "account_types": list(self.account_types), "can_place": False}

    def ticket(self, plan: PlanForTicket, decimals: int) -> dict:
        raise ExecutionRefused(f"{self.mode}: ticket generation is not available in this phase")

    def translate(self, intent: OrderIntent) -> dict:
        """The broker-native request this adapter WOULD build. Pure; returned, never sent."""
        raise ExecutionRefused(f"{self.mode}: nothing to translate — the user places the order by hand")

    def preflight(self, intent: OrderIntent) -> dict:
        return {"mode": self.mode, "allowed": False, "sent_to_broker": False,
                "gates": [{"gate": g, "state": "NOT BUILT"} for g in GATES],
                "note": "execution is disabled in this phase; every gate must exist and pass before place() may do anything"}

    def place(self, plan: PlanForTicket, approval: str) -> dict:
        # ONE refusal for every adapter. Phase 6 replaces this method body
        # behind explicit approval + duplicate + reconciliation + risk gates.
        raise ExecutionRefused(
            f"{self.mode}: live order placement is DISABLED in this development phase "
            "(Phases 1-5 are display-only; see docs/EXECUTION_ROADMAP.md)")
