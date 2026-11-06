"""BROKER ADAPTER CONTRACT — Phase 6 architecture, shipped DARK.

The same SignalMesh signal must be placeable through any broker, so the
seam is defined now and every implementation is disabled. In this phase:

  * `describe()` says what the adapter is and whether it could work.
  * `ticket()` turns a READY engine plan into a pending-order ticket the
    USER reads. Mode A (manual) is the only one that returns anything.
  * `place()` ALWAYS refuses. There is no code path that sends an order.

Phase 6 rules (binding, see docs/EXECUTION_ROADMAP.md): explicit user
approval per order, duplicate-order protection keyed on signal_id,
position reconciliation against the broker before placing, and the risk
checks SignalMesh already owns. None of that exists yet, so nothing may
place.
"""
from __future__ import annotations

from dataclasses import dataclass


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


class BrokerAdapter:
    mode = "MANUAL"
    label = "Manual"

    def describe(self) -> dict:
        raise NotImplementedError

    def ticket(self, plan: PlanForTicket, decimals: int) -> dict:
        raise ExecutionRefused(f"{self.mode}: ticket generation is not available in this phase")

    def place(self, plan: PlanForTicket, approval: str) -> dict:
        # ONE refusal for every adapter. Phase 6 replaces this method body
        # behind explicit approval + duplicate + reconciliation + risk gates.
        raise ExecutionRefused(
            f"{self.mode}: live order placement is DISABLED in this development phase "
            "(Phases 1-5 are display-only; see docs/EXECUTION_ROADMAP.md)")
