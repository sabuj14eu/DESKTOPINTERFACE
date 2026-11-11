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
