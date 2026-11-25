# What SignalMesh must expose for per-account data and signal→trade tracking

Investigated 2026-11-11 by reading `sabuj14eu/Sniper-System` at branch `claude/handoff-5200`
(commit `7e7d413`, `app/version.py` = 5.200 — the version production prints). Nothing in that
repository was changed. This file is the finding and the proposed change, for the platform window.

## 1. Findings

| Question | Answer in the 5.200 code | Where |
|---|---|---|
| Does `GET /api/v1/accounts` exist? | **No.** The read routes are `/me /portfolio /stats /trades /signals /ea/performance /news/* /market/* /outlook /macro/* /sources/*`. | `app/routers/api_v1.py` |
| What is `/api/v1/portfolio`? | A **sum over every MT5 account of the user** (`balance, equity, free_margin, floating_pnl`, plus `accounts`, `online`). | `app/services/analytics.py` `portfolio_totals` |
| Does SignalMesh store accounts separately? | **Yes.** One `mt5_accounts` row per account: `broker, server, login, currency, status, balance, equity, free_margin, floating_pnl, last_heartbeat_at`; `is_online` = heartbeat younger than 300 s. | `app/models/trading.py` `MT5Account` |
| DEMO or LIVE per account? | **Not stored.** No column says it. | same |
| Used margin, margin level? | **Not stored and not sent.** The reporter reads `mt5.account_info()` (which has `margin`, `margin_level`, `trade_mode`) but posts only balance, equity, `margin_free`, `profit`, `server`. | `agents/mt5_reporter/mt5_reporter.py` `report_account` |
| Open positions and pending orders? | **Stored**, per account and per broker ticket: the reporter posts every position (`status open`) and every order (`status pending`). | `report_open_positions`, `Trade` |
| Is a trade linked to its signal? | **Yes, in the database.** `trades.signal_id` → `signals.id`, set by `attribution-v1` (v18 by `account:ticket`, v7 by the position comment) and never guessed from symbol or direction. Each link also writes a `signal_events` row (`stage = mt5_execution`). | `app/services/attribution.py`, `trade_report` |
| Is that link readable through the API? | **No.** `GET /api/v1/trades` returns `id, symbol, direction, lots, entry, exit, sl, tp, status, profit, session, open_time, close_time` — no ticket, no account, no signal. | `api_v1.py` `trades` |
| Is the signal's own timeline readable? | **No.** `signal_events` (`alert_received, council_decision, status_change, mt5_execution, telegram_sent, outcome`) has no read route; `GET /signals` also omits `reason`, `market_structure`, `raw_payload`. | `api_v1.py` `signals` |

So today, in production, the terminal can only show the combined portfolio, and every signal reads
"no broker order linked" — not because the facts are missing, but because the read API does not carry them.

## 2. Proposed platform change A — read-only, no schema change, no reporter change

Three additions to `app/routers/api_v1.py`, all `GET`, all behind the existing read key (`api_user`),
all append-only (existing keys and consumers unchanged). The terminal already reads exactly these keys.

```python
@router.get("/accounts")
def accounts(db: Session = Depends(get_db), user: User = Depends(api_user)):
    """One row per MT5 account, as the reporter heartbeats left it. Read-only; never summed."""
    rows = db.query(MT5Account).filter_by(user_id=user.id).order_by(MT5Account.id).all()
    return [{
        "login": a.login, "broker": a.broker, "server": a.server, "platform": "mt5", "currency": a.currency,
        "status": a.status, "online": a.is_online,
        "last_heartbeat": a.last_heartbeat_at.isoformat() if a.last_heartbeat_at else None,
        "balance": a.balance, "equity": a.equity, "free_margin": a.free_margin, "floating_pnl": a.floating_pnl,
    } for a in rows]
```

In `trades()` — four more keys per row (the row already has them; `Signal` is imported in that file):

```python
            "ticket": t.ticket or None,
            "account_login": t.account.login if t.account else None,
            "signal_id": sig_ids.get(t.signal_id),      # the signal's public id, e.g. "NQ:XAUUSD:NQ-P1794360300"
            "comment": t.comment or None,
```
with, before the list is built:
```python
    ids = {t.signal_id for t in rows if t.signal_id}
    sig_ids = dict(db.query(Signal.id, Signal.signal_id).filter(Signal.id.in_(ids)).all()) if ids else {}
```

In `signals()` — three more keys per row: `"reason": s.reason, "market_structure": s.market_structure,
"outcome": s.outcome`. (`raw_payload` is deliberately left out of the list; it can be large.)

What the terminal shows once A is deployed, with no terminal change:

* the account selector lists each connected account separately, with broker, server, masked number,
  heartbeat time; balance / equity / free margin / floating P/L per account, never summed;
* Open Positions and Pending Orders per account (journal rows matched on `account_login`);
* a signal whose trade is linked reads "ORDER SUBMITTED / FILLED / POSITION CLOSED at the broker" with the
  journal row, masked account, execution price, exit and P/L; Trade History shows the linked signal id.

Still NOT AVAILABLE after A: **DEMO / LIVE, used margin, margin level**.

## 3. Proposed platform change B — needs your explicit approval (it touches the MT5 reporter)

To label accounts DEMO or LIVE and show used margin and margin level, the reporter has to send three more
values it already reads, and the platform has to keep them:

* reporter `report_account`: add `"margin": info.margin, "margin_level": info.margin_level,
  "trade_mode": info.trade_mode` (0 demo · 1 contest · 2 real) — append-only fields on an existing POST;
* platform `AccountHeartbeat` + `MT5Account`: three nullable columns (`used_margin`, `margin_level`,
  `trade_mode`) and three `ALTER TABLE … ADD COLUMN`;
* `GET /accounts` then also returns `"margin"`, `"margin_level"`, `"trade_mode"`.

This changes an existing broker integration (the reporter) and the database schema, which the V2 brief
ruled out. It is additive and read-only toward the broker, but it is a decision, not a detail.

## 4. Optional change C — the signal's own timeline

`GET /api/v1/signals/{signal_id}/events` returning the `signal_events` rows (`stage, detail, created_at`)
would let the terminal put real timestamps on each lifecycle stage (council decision, MT5 execution,
outcome) instead of deriving the stage from the status word and the linked journal row.

## 5. How to confirm on the box (production, not the sandbox)

After the V2 terminal is deployed, `scripts/acceptance.sh` prints one of:

    NOTE engine has no per-account route at /api/v1/accounts (HTTP 404) — the terminal must show the portfolio total, labelled
    NOTE engine per-account route /api/v1/accounts: N row(s), keys: …

and `NOTE engine trade rows carry: …` listing whether `ticket`, `account_login`, `signal_id` are present.
Keys only — no account number or balance is printed.

## 6. Proposed change D — trading hours for each instrument (asked for by the terminal, 2026-11-12)

**For the SignalMesh / platform window and the MT5 reporter on the Windows VPS. Nothing in this section is done from the
terminal repository. Each item needs Shyam's explicit approval before the platform window starts.**

**What the terminal cannot know today.** When an instrument stops updating, the terminal sees only that its newest bar is
old (`freshness.state = STALE`). It cannot tell "the market is closed" from "the reporter stopped". It therefore writes
`MARKET QUIET (inferred)` when the same feed is still delivering other instruments, and `FEED STALE` when nothing is
updating — and it never writes MARKET CLOSED. Seen on production 2026-11-09 to 2026-11-11: GOLD and SILVER have no bar from
22:00 to 23:00 UTC every day (the broker's daily break); DXY and US10Y were quiet while 27 other instruments were live.

**What would make it certain** — any one of these, in order of preference:

1. **The reporter sends each symbol's session table.** MT5 has it: `SymbolInfoSessionTrade(symbol, day_of_week, session_index, from, to)`
   gives every trading session of every weekday in broker server time, and `SymbolInfoInteger(symbol, SYMBOL_TRADE_MODE)` says
   whether trading is enabled at all. Sent once at start and again when it changes, with the broker server's UTC offset.
2. **The platform stores it and serves it read-only**, for example `GET /api/v1/market/sessions?symbol=` →
   `{symbol, server_utc_offset_min, sessions: [{dow, from_min, to_min}], trade_mode, as_of}`; or adds two keys to the
   existing candle payload's `freshness` block: `market_open` (true / false / null = not known) and `next_open_utc`.
3. **The engine's freshness word gains a state**, `CLOSED`, when the bar is old because the session table says the market
   is shut. The terminal copies that word verbatim, as it does LIVE / STALE / UNKNOWN / INVALID today.

**What the terminal will do with it, and what it will not.** It will show MARKET CLOSED with the source and the next
opening time, in place of the inferred label. It will not build a calendar of its own, and it will not treat a closed
market as live: a decision on a closed market stays not-ready.

**How to confirm afterwards, on the box:** `scripts/acceptance.sh`, section "data state and safety" — the line
`NOTE data state now: …` lists every state seen; MARKET QUIET should then appear only for instruments the calendar
says are open.

## 7. Finding E — the last bar before a break reaches the platform late (MT5 reporter)

**Seen on production, 2026-11-11, GOLD and SILVER.** At 22:46 UTC, during the daily break, the newest stored 15m bar was
21:30–21:45, while the newest stored 1m bar was 21:57–21:58. The 15m bar 21:45–22:00 was stored only after the market
reopened at 23:00. During the break the chart therefore ended one bar early and the header price (the 1m close) was
newer than the chart's last candle. The same must hold for the last 1m bar (21:58–21:59) and for every timeframe.

**Likely cause — not confirmed, the reporter's code was not read from this repository.** A reporter that sends "closed
bars" usually decides a bar is closed when the NEXT bar of that timeframe appears. Across a break the next bar appears
only at the reopening, so the last bar before the break waits a whole break (an hour for metals, a weekend on Fridays).

**What would fix it, on the Windows VPS, in the reporter:** decide that a bar is closed by the broker SERVER CLOCK —
`TimeTradeServer() >= bar_open + PeriodSeconds(timeframe)` — as well as by the arrival of the next bar, and send it then.
The values of a bar whose period is over do not change afterwards, so sending it on the clock is safe. On Friday's close
this also delivers the week's last bar before the weekend.

**What it changes for the engine.** The engine would see the last bar of the session about an hour earlier (two days
earlier on a weekend). Whether any strategy should act on a bar that closes into a shut market is the platform window's
decision, with Shyam — it is a change to what the engine sees, so it is not a terminal matter.

**How to confirm afterwards, on the box:** `scripts/acceptance.sh`, section "candle coverage (GOLD, SILVER)". During a
break it must read "The 15m series reaches as far as the closed 1m bars cover", not "is OVER but NOT stored".

