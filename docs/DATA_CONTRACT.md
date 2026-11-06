# Terminal data contract (`/api/terminal/*`)

All routes are GET except the two execution POSTs, which never reach a broker.
Every payload carries `as_of` (adapter clock) and, where a price appears,
`provenance` {provider, source, engine_as_of} and `freshness` {state, age_min,
limit_min, detail} exactly as the engine reported them.

| Route | Returns | Source |
|---|---|---|
| `GET /health` | adapter version, provider (name, is_fixture), upstream `/readyz`, execution flags, symbols, timeframes | — |
| `GET /instruments` | watch list + symbols seen in signals, decimals per symbol (platform precision table) | signals |
| `GET /market-watch` | rows: price (last closed 1m close), ts, age, freshness, change_pct (engine session change), bias, engine_status, summary, direction, lane_decision; portfolio | candles 1m, snapshot, desk, portfolio |
| `GET /candles?symbol&tf&n` | `CandleSeries` {time (epoch s, bar open), o/h/l/c, volume (tick), spread, source}, freshness, closed_only=true | market/candles |
| `GET /decision?symbol` | `DecisionView` — see below | snapshot, desk, signals, news/state |
| `GET /signals?bucket=all\|active\|pending\|history&symbol` | `SignalRef[]` + the bucket rule | signals |
| `GET /trades?status=all\|open\|closed` | `TradeRow[]` | trades |
| `GET /performance` | stats, portfolio, ea_performance (verbatim) | stats, portfolio, ea/performance |
| `GET /news?symbol` | news-state board, facts, macro scorecard summary, events next 12 h | news/state, news/facts, macro/scorecard, snapshot |
| `GET /sources` | per symbol × tf feed freshness, evidence sources, price_source words | candles, sources/evidence |
| `GET /system` | adapter, upstream readiness, portfolio, macro engine state, execution flags | readyz, portfolio, macro/engine |
| `GET /execution/modes` | Manual AVAILABLE · MT5 DISABLED · cTrader NOT_CONFIGURED; the Phase 6 rules | — |
| `POST /execution/ticket {symbol, mode}` | Mode A: pending-order text when the engine says READY, else `available:false` with the engine's word | snapshot |
| `POST /execution/place` | **always 403** in this phase | — |

## DecisionView

* `engine_status` — `planner.build_plan` status verbatim: READY / WAIT / NO TRADE.
* `summary` — the three-word display: READY → READY, WAIT → WAIT, NO TRADE → INVALIDATED.
* `order_type, entry, sl, tp1, tp2, rr1, rr2, grade, score, reason, why[], conflicts[], lifecycle, distance_atr, gates[]` — plan verbatim.
* `bias, structure, regime, atr, last_close, last_bar_ts, tradeability, session_change_pct, recent_high/low, session_high/low, levels_ladder` — snapshot market block.
* `news_risk, news_events[], news_state` — snapshot news + news-state-v1 row.
* `macro{}` — gated macro biases with their state.
* `freshness{candles,bias,news,plan}` — unified FreshnessStatus, never upgraded.
* `exposure` — MT5 positions/orders for the symbol (heartbeat truth).
* `signal` — the signal behind the levels (id, system, status, age_h, stale, council).
* `levels[]` — chart lines {key, label, kind, value, stale, origin}; `levels_rule` names the selection rule.
* `lane` — desk intraday candidate: engine, decision, reasons, confirmation wording (chart._WAIT_CONF), stage.
* `invalidation[]` — the engine's own NO TRADE reason, conflicts, stale plan/candles, and the SL life rule.

## Freshness vocabulary

LIVE (usable) · STALE (exists, too old — INVALID for decisions, never neutral) ·
UNKNOWN (no data, proves nothing) · INVALID (failed validation). Thresholds are the
engine's (`limit_min`); the adapter copies them.
