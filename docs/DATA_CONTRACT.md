# Terminal data contract (`/api/terminal/*`)

All routes are GET except the two execution POSTs, which never reach a broker.
Every payload carries `as_of` (adapter clock) and, where a price appears,
`provenance` {provider, source, engine_as_of} and `freshness` {state, age_min,
limit_min, detail} exactly as the engine reported them.

| Route | Returns | Source |
|---|---|---|
| `GET /health` | adapter version, provider (name, is_fixture), upstream `/readyz`, execution flags, symbols, timeframes | — |
| `GET /instruments` | DISCOVERED instruments: SignalMesh `DEFAULT_SYMBOLS` (via `/api/v1/news/state`, no filter) ∪ symbols seen in `/api/v1/signals` ∪ the platform's own symbol table (precision + macro constants) ∪ `SMT_SYMBOLS` pins; per instrument: category, decimals, `available`, `timeframes` actually stored (measured via `/api/v1/market/candles`), origins. `watch` = available instruments (pins restrict, never add) | news/state, signals, candles |
| `GET /coverage?symbol` | per timeframe: stored, newest bar, freshness | candles |
| `GET /market-watch` | rows: price (last closed 1m close), ts, age, freshness, change_pct (engine session change), bias, engine_status, summary, direction, lane_decision; portfolio | candles 1m, snapshot, desk, portfolio |
| `GET /candles?symbol&tf&n` | `CandleSeries` {time (epoch s, bar open), o/h/l/c, volume (tick), spread, source}, freshness, closed_only=true | market/candles |
| `GET /decision?symbol` | `DecisionView` — see below | snapshot, desk, signals, news/state |
| `GET /signals?bucket=all\|active\|pending\|history&symbol` | `SignalRef[]` + the bucket rule | signals |
| `GET /signals/{signal_id}` | **signal information**: `origin` (each value with the field it was read from, `UNKNOWN` otherwise), `validation`, `invalidation`, `lifecycle` (six stage rows), `execution`, `is_broker_execution` | signals, trades |
| `GET /trades?status=all\|open\|closed` | `TradeRow[]` (+ `signal_id`, `account_masked`, `ticket` when the journal row carries them) | trades |
| `GET /accounts` | **account-contract-v1**: `accounts` (connected, selectable), `disconnected`, `mode` (`PER_ACCOUNT` \| `PORTFOLIO_TOTAL`), `note`, `default` | `SMT_ACCOUNTS_PATH` (default `/api/v1/accounts`), else portfolio |
| `GET /account?id` | one account: `account`, `positions`, `orders`, `closed`, each with its `*_source` | accounts row, trades |
| `GET /performance` | stats, portfolio, ea_performance (verbatim) | stats, portfolio, ea/performance |
| `GET /news?symbol` | news-state board, facts, macro scorecard summary, events next 12 h | news/state, news/facts, macro/scorecard, snapshot |
| `GET /sources` | per symbol × tf feed freshness, evidence sources, price_source words | candles, sources/evidence |
| `GET /system` | adapter, upstream readiness, portfolio, macro engine state, execution flags | readyz, portfolio, macro/engine |
| `GET /execution/modes` | Manual AVAILABLE · MT5 DISABLED · cTrader NOT_CONFIGURED, each with its account types; the gates (all NOT BUILT); the Phase 6 rules | — |
| `POST /execution/ticket {symbol, mode}` | Mode A: pending-order text when the engine says READY, else `available:false` with the engine's word | snapshot |
| `POST /execution/place` | **always 403** in this phase | — |

## Instruments

Every instrument SignalMesh stores is drawable; the list and the venue are SignalMesh's, the terminal adds none of its own. Discovery probes SignalMesh's own symbol names for stored candles; a name the reporter sends that SignalMesh has no alias for is stored under that raw name and stays invisible here until SignalMesh maps it (its `canonical_symbol` table).

## price-contract-v1 — which price is which

Every price the terminal shows is exactly one of these, labelled, never blended:

| Kind | Where shown | Engine source | Timestamp shown |
|---|---|---|---|
| `tick` | header, "tick: n/a" | none — SignalMesh stores no bid/ask/tick | — |
| `last_closed_1m` | header price, market watch | `/api/v1/market/candles?tf=1m` newest bar `close` | bar open–close span, "closed N ago" |
| `chart_last_bar` | chart header | newest closed bar of the chart's timeframe | bar span, "closed N ago" |
| `engine_reference` | decision panel, chart footer | `snapshot.market.last_close` on `last_bar_ts` (the 15m bar the decision, ATR and structure were measured on) | 15m bar span |
| `drift` | chart footer | desk `ref-drift-v1`: engine_reference vs the newest 1m bar, in ATR | engine's own |

Freshness ages carry their basis: the engine's gate counts **since bar open**
(`bar-clock-v1`, basis `since_open`); the UI also prints **since close**, so a
15m bar 39 min since open is shown as 24 min since close.

## Provenance — the per-candle `source` is the authority

SignalMesh returns a static `price_source` line ("MT5 via mt5_reporter …") on
every market response. The terminal shows it as **platform label** only. The
authority is each candle's own `source` field (`mt5:<login>` from the reporter).
`source_kind` classifies it: `mt5_reporter` · `bridge` · `fixture` · `unstated` ·
`other`, with a `source_warning` for anything that is not the reporter feed.
`/sources` gives a one-line `verdict` ("ALL MT5 REPORTER" or "NOT ALL BROKER DATA — kinds seen: …").

## BUY / SELL side states (`sides`, rule in `side_rule`)

Derived from the engine plan only: READY = plan READY and its order type is this
side · INVALID = plan NO TRADE (both sides), or plan WAIT because this side's own
plan expired or conflicts with bias · WAIT = otherwise. The reason is the engine's.

## Expired plans

A signal past the engine's 12h lifecycle (`planner.SIGNAL_FRESH_H`) is returned
as `expired_plan` (signal + levels + note) and **never** in `levels`. The chart
draws it only when the "expired plan" toggle is on, dotted grey, labelled
"(history)". Trade History → "expired & rejected plans" lists them.

## DecisionView

* `engine_status` — `planner.build_plan` status verbatim: READY / WAIT / NO TRADE.
* `summary` — the three-word display: READY → READY, WAIT → WAIT, NO TRADE → INVALIDATED.
* `order_type, entry, sl, tp1, tp2, rr1, rr2, grade, score, reason, why[], conflicts[], lifecycle, distance_atr, gates[]` — plan verbatim.
* `bias, structure, regime, atr, last_close, last_bar_ts, tradeability, session_change_pct, recent_high/low, session_high/low, levels_ladder` — snapshot market block.
* `news_risk, news_events[], news_state` — snapshot news + news-state-v1 row.
* `macro{}` — gated macro biases with their state.
* `freshness{candles,bias,news,plan}` — unified FreshnessStatus, never upgraded.
* `exposure` — MT5 positions/orders for the symbol (heartbeat truth).
* `signal` — the signal behind the levels (id, system, status, age_h, stale, council, `market_structure`, and `pine`: the sensor's own alert fields verbatim from `Signal.raw_payload` — trend, choch, inducement, sweep, trap_bias, loc_zone, killzone, htf_align, level_src, ny_regime … only the keys it sent).
* `levels[]` — CURRENT chart lines only {key, label, kind, value, stale=false, origin}; `levels_rule` names the selection rule.
* `expired_plan` — the expired signal and its levels, history only.
* `price` — price-contract-v1 block. `sides` — BUY/SELL states. `side_rule` — the rule text.
* `lane` — desk intraday candidate: engine, decision, reasons, confirmation wording (chart._WAIT_CONF), stage.
* `invalidation[]` — the engine's own NO TRADE reason, conflicts, stale plan/candles, and the SL life rule.

## Freshness vocabulary

LIVE (usable) · STALE (exists, too old — INVALID for decisions, never neutral) ·
UNKNOWN (no data, proves nothing) · INVALID (failed validation). Thresholds are the
engine's (`limit_min`); the adapter copies them.

## What the chart draws from SignalMesh, and what it cannot

Drawn, all from engine output: the current plan's Entry / SL / TP1 / TP2; the
expired plan (toggle, history); the structural level ladder with its names and
timeframes (session high/low, recent high/low, 1h/4h highs and lows — closed-bar
facts from `brief.level_ladder`); the engine's 15m structure word (HH/HL · LH/LL ·
MIXED · UNKNOWN) with bias and regime; and the sensor's own words on the latest
signal (Pine's `trend`, `choch`, `inducement`, `sweep`, `trap_bias`, `loc_zone`,
`killzone`, `htf_align` …) with the signal's age.

Not drawn, because SignalMesh does not store them: supply/demand zone boxes,
premium/discount bands, BOS/CHoCH marks at specific bars, previous-day high/low.
The Pine indicator computes those on TradingView and sends only the words above
in its alert. The terminal shows nothing it cannot trace to a stored value.

## account-contract-v1 — broker accounts

Broker truth only. Two sources, in this order:

1. **Per-account route** — `GET {SMT_ACCOUNTS_PATH}` on SignalMesh (default `/api/v1/accounts`): a list (or `{"accounts": [...]}`) with one row per broker account as the MT5 reporter heartbeat describes it. Keys read, MT5's own `account_info()` names first:
   `login` · `company`/`broker` · `server` · `platform` · `trade_mode`/`mode`/`is_demo` · `currency` · `leverage` · `balance` · `equity` · `profit`/`floating_pnl` · `margin`/`used_margin` · `margin_free`/`free_margin` · `margin_level` · `online` · `last_heartbeat`/`last_seen` · `updated_at` · optional `positions[]`, `orders[]` (`ticket, symbol, direction, order_type, lots, entry, sl, tp, profit, open_time`).
2. **Fallback** — the route answers 404: SignalMesh's `/api/v1/portfolio`, which is ONE total over every reporting account (`balance, equity, free_margin, floating_pnl, accounts, online`). With one account it is that account. With several it is a single entry marked `combined: true`, attributed to no account.

Rules: a key the row does not carry is `null` and the UI prints **NOT AVAILABLE**; nothing is derived (used margin is *not* equity − free margin); DEMO / LIVE only from the broker's word (`trade_mode` 0 demo, 2 real), else UNKNOWN; the full account number never reaches the browser (masked `••••1234`, opaque `id`); `field_sources` names the upstream field per value. Only `connection == ONLINE` accounts are selectable. Journal rows are shown under an account only when they carry that account's number, or when there is exactly one account; otherwise nothing is shown rather than mixed.

## Signal information — the five stages

| Stage | DONE when | Otherwise |
|---|---|---|
| A · generated by SignalMesh | `signal.created_at` exists | UNKNOWN |
| B1 · approved by the brain council | `signal.status` approved / executed | NOT_DONE (pending) · REJECTED |
| B2 · approved by the user | never in this phase — the terminal has no approval function | NOT_RECORDED |
| C · order submitted to the broker | a journal row names this `signal_id` | REPORTED when `signal.status == executed` with no linked row · NOT_RECORDED |
| D · order filled by the broker | the linked row is open/closed with an entry price | UNKNOWN / NOT_RECORDED |
| E · position closed | the linked row is closed | UNKNOWN / NOT_RECORDED |

`origin.originating_engine` is `signal.system` (v18, v7, NQ-EA …); `strategy_name` and `strategy_version` are read from the signal row or its `raw_payload` (`strategy`, `method`, `plan_kind`, `kind` / `strategy_version`, `version`, `script_version`) and are `UNKNOWN` when SignalMesh sent none. `is_broker_execution` is true only with a linked journal row.
