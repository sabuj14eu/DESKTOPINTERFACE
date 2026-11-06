# Architecture

```
┌──────────────────────── SignalMesh (production, untouched) ────────────────────────┐
│  FastAPI app · Postgres · brain webhooks · MT5 reporter · Telegram · planner/desk  │
│  /api/v1/market/{candles,snapshot,desk} /signals /trades /stats /portfolio         │
│  /news/state /news/facts /macro/* /sources/evidence /readyz        (GET, API key)  │
└──────────────────────────────────────▲─────────────────────────────────────────────┘
                                       │ HTTP GET only · read-scoped key · 15 s cache
┌──────────────────────────────────────┴─────────────────────────────────────────────┐
│  signalmesh-terminal container (this repo)                                         │
│  adapter/ (FastAPI :8090)                                                          │
│    providers/signalmesh.py   the production reader (GET only)                      │
│    providers/fixture.py      recorded shapes, dev only, loud banner                 │
│    providers/mt5_direct.py   Phase 6 stub (NOT_CONFIGURED)                         │
│    providers/ctrader.py      Phase 6 stub (NOT_CONFIGURED)                         │
│    normalize.py              reshape -> contract.py models (no recalculation)       │
│    brokers/{manual,mt5,ctrader}.py   execution seam; place() always refuses         │
│    routes.py                 /api/terminal/*                                        │
│  web/dist (React + Lightweight Charts) served by the adapter                        │
└──────────────────────────────────────▲─────────────────────────────────────────────┘
                                       │ HTTPS via the existing Caddy (new hostname)
                                   browser
```

## Why an adapter instead of calling SignalMesh from the browser

* SignalMesh's JSON routes are either session-cookie (`/chart/*.json`) or API-key
  (`/api/v1/*`). A browser cannot hold the API key safely, and SignalMesh has no
  CORS configuration — adding one would be a change to production.
* One adapter = one cache = the terminal's polling never multiplies load on the
  platform. Four symbols every 15 s is one snapshot per symbol per 15 s, however
  many terminal tabs are open.
* The adapter is where the **contract** lives, so a future provider (direct MT5,
  cTrader) or broker adapter plugs in without touching the UI.

## Data flow per screen element

| Element | SignalMesh route | Engine field |
|---|---|---|
| Market watch price | `/api/v1/market/candles?tf=1m&n=2` | last closed bar `close`, `freshness` |
| Market watch change | `/api/v1/market/snapshot` | `market.session_change_pct` |
| Chart candles | `/api/v1/market/candles` | closed bars, `freshness`, `price_source` |
| Entry / SL / TP lines | snapshot `decision.*` when READY, else newest signal from `/api/v1/signals` (chart._levels rule, 12 h TTL) | |
| Structural ladder | `/api/v1/market/snapshot` | `levels.ladder` |
| Decision panel | `/api/v1/market/snapshot` | `decision.*`, `freshness.*`, `market.*`, `news.*`, `macro`, `exposure`, `_plan.gates` |
| Confirmation line / lane | `/api/v1/market/desk` | Intraday lane `c.decision`, `c.reasons`, wording from chart._WAIT_CONF |
| Signals tabs | `/api/v1/signals` | verbatim + bucket by status and 12 h TTL |
| Trade history | `/api/v1/trades` | verbatim |
| Performance | `/api/v1/stats`, `/api/v1/portfolio`, `/api/v1/ea/performance` | verbatim |
| News & events | `/api/v1/news/state`, `/api/v1/news/facts`, `/api/v1/macro/scorecard` | verbatim |
| Data sources | candles freshness per tf, `/api/v1/sources/evidence` | verbatim |
| System health | `/readyz`, `/api/v1/portfolio`, `/api/v1/macro/engine` | verbatim |

## Why not fork OpenCharts / Superior Trade / OpenTerminal

The parts of those projects this terminal needs (a candlestick chart with
price lines and markers, a watchlist, a decision panel, tabs) are a few hundred
lines on top of Lightweight Charts — the same library OpenCharts uses. Forking a
whole terminal brings its demo trading engine, its indicator set, its own
backend contract and its upstream drift, all of which would have to be removed
or kept in sync, and every removed piece is a place a simulated number could
leak into a screen that must show only the engine's output. The adapter
pattern OpenCharts demonstrates is kept; its code base is not.

## Removability

`docker compose down` in this repository's directory removes the container; the
SignalMesh stack keeps running. The only thing left on the SignalMesh side is a
read-only API key the user created and can revoke in Dashboard → API.
