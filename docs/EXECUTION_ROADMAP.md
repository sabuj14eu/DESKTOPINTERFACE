# Execution roadmap (Phase 6 — NOT in this phase)

The seam exists (`adapter/signalmesh_terminal/brokers/`); every implementation
is dark. Nothing below may be built until Phases 3–5 have passed.

## Modes

| Mode | Adapter | Today | Phase 6 |
|---|---|---|---|
| A — Manual | `ManualBroker` | prints the pending-order ticket from a READY plan; sends nothing | unchanged |
| B — MT5 | `MT5Broker` | DISABLED | approve → place a pending order through the **existing** SignalMesh MT5 integration (reporter/executor on the Windows box); the terminal never speaks to MT5 directly |
| C — cTrader | `CTraderBroker` | NOT_CONFIGURED | cTrader Open API (OAuth, Protobuf over TLS) pending orders |

The same signal feeds every adapter; signal generation stays broker-agnostic:

```
SignalMesh signal / READY plan
        │  intent_from_signal() / intent_from_plan()
        ▼
   OrderIntent            broker-neutral: signal_id, canonical symbol, side, order kind, entry, SL, TP
        │                 (no broker symbol, no volume — those come from the broker's symbol table
        ├── MT5Broker.translate()      -> MqlTradeRequest-shaped dict        and SignalMesh's risk checks)
        └── CTraderBroker.translate()  -> ProtoOANewOrderReq-shaped dict
```

`translate()` is a pure function that returns a dictionary marked `sent_to_broker: false`
with the fields still `unresolved`. `preflight()` lists the gates below, all NOT BUILT,
`allowed: false`. `place()` refuses. The `brokers/` package imports no network library
(`test_broker_package_opens_no_connection`), holds no credential and changes no MT5
permission. Account types each adapter will serve: MT5 Demo / MT5 Live, cTrader Demo /
cTrader Live — an account appears in the terminal only when it is genuinely connected.

## Gates every `place()` must pass, in order

1. **Engine says READY** for this symbol at this instant (fresh snapshot, not cached).
2. **Explicit approval**: the user confirms the exact ticket text; the approval carries the plan fingerprint, and a changed plan voids it.
3. **Duplicate protection**: one order per `signal_id` per account, checked against the broker's open/pending orders AND the terminal's own ledger.
4. **Position reconciliation**: the broker's positions/orders for the symbol are read first; an existing position or pending order in the same direction blocks.
5. **Risk checks**: SignalMesh's own risk limits (`RiskLimits`, emergency stop) are read and honoured; the terminal never widens them.
6. **Audit**: every attempt (approved, blocked, placed, failed) is journaled with actor, time, plan fingerprint, broker reply.

No automatic trading, ever: no order without a human approval event for that exact ticket.

## Noted, not done: a second candle source

A direct MT5 feed on the Linux server (MT5 under Wine, or a Linux bridge) would
add the forming bar and bid/ask and shorten the 60 s reporter cadence. It is a
new provider behind `providers/base.py`, to be added only after Phases 3–5, so
the comparison period has one source of truth (SignalMesh's stored closed bars).
