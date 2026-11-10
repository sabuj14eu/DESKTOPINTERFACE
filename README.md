# SignalMesh Terminal — cTrader-style desktop interface (read-only)

A completely separate, professional trading-terminal UI for the existing
**SignalMesh** system (the Brother Bot platform in `sabuj14eu/Sniper-System`).
It displays everything SignalMesh already calculates, detects, validates and
records — prices, candles, structure, bias, signals, entry/SL/TP, R:R, ATR,
news, macro, freshness, trades, performance — in a cTrader-like layout.

![terminal](docs/screenshots/terminal-local-signalmesh.png)

**It changes nothing in SignalMesh.** Separate repository, separate process,
separate port, separate `.env` (`SMT_*`), read-only connection through
SignalMesh's own `/api/v1` mirror with a *read*-scoped API key. Delete this
repository and SignalMesh does not notice.

## What is where

| Part | Path | Role |
|---|---|---|
| Read-only adapter | `adapter/` | FastAPI. GETs SignalMesh `/api/v1/*`, reshapes it into the terminal contract, serves the UI. The only HTTP verb it knows is GET (asserted by a test). |
| Terminal UI | `web/` | React + TypeScript + [Lightweight Charts](https://github.com/tradingview/lightweight-charts) (Apache-2.0, open source, no TradingView subscription or widget). |
| Phase 3 parity check | `scripts/verify_parity.py` | Compares every displayed price/candle/level/status with the engine, field by field. |
| Auto check | `scripts/check.sh` | Tests + typecheck + build + read-only audit in one command (also runs in CI). |
| Deploy | `Dockerfile`, `docker-compose.yml`, `Caddyfile.snippet` | One container beside the SignalMesh stack. |
| Docs | `docs/` | Architecture, data contract, deployment, verification plan, execution roadmap (Phase 6). |

## Layout

* **Top bar** — symbol, last closed price with its age and freshness, session and open exchanges, timeframe (1m…1D), data connection, MT5 accounts online, execution mode (DISABLED · MANUAL).
* **Left** — Market Watch: price, session change (engine's own number), freshness, bias, engine decision.
* **Centre** — candlestick chart (closed bars only, UTC) with the engine's Entry / SL / TP1 / TP2 lines (expired plans only behind a toggle), the named structural level ladder, the engine's structure/bias/regime badge, the sensor's own words on the latest signal (Pine's trend, CHoCH, inducement, sweep, zone …), ACTIVE/PENDING signal markers, and the engine's CONFIRMATION line underneath.
* **Right** — the SignalMesh decision: READY / WAIT / INVALIDATED (with the engine's own word next to it), bias, BUY/SELL state, validation, levels, R:R, ATR, news, macro, freshness per stream, invalidation conditions, gates, and the manual order ticket.
* **Bottom** — Active Signals · Pending Setups · Trade History · Performance · News & Events · Data Sources · System Health.

## Rules this code obeys

> Every instrument SignalMesh stores is drawable; the list and the venue are SignalMesh's, the terminal adds none of its own.

1. **Nothing is recalculated.** Every number is the engine's (`adapter/signalmesh_terminal/normalize.py` reshapes, never computes). The only logic is display selection, and each rule is named in the payload and mirrors SignalMesh's own chart page.
2. **Freshness travels with every number.** LIVE / STALE / UNKNOWN / INVALID are passed through verbatim and never upgraded. A stale price is shown as STALE with its age, never as live.
3. **One price contract.** Every price is one of: tick (n/a — SignalMesh stores none), last closed 1m bar (header), chart's last bar, engine reference (the 15m bar the decision was measured on). Each carries its bar span and age since close. See `docs/DATA_CONTRACT.md`.
4. **Provenance is the per-candle source.** SignalMesh's static "MT5 via mt5_reporter" line is shown as a platform label only; the badge next to every price comes from the candle's own `source` field (MT5 REPORTER / FIXTURE / BRIDGE / NOT MT5).
5. **Expired plans are history.** A plan past the engine's 12h lifecycle never appears as a current level; it moves to Trade History → expired & rejected plans, and is drawn on the chart only when explicitly toggled.
6. **Nothing writes.** No webhook, no database, no POST to SignalMesh. `tests/test_read_only.py` greps for write verbs.
7. **Nothing executes.** Broker adapters (Manual / MT5 / cTrader) exist as a seam; `place()` refuses with 403 for every mode in this phase. Mode A prints a ticket the user places by hand.
8. **Fixture data is loud.** `SMT_PROVIDER=fixture` paints a banner and is refused when `SMT_ENV=production`.

## Quick start (development)

```bash
# adapter against a real SignalMesh (read-only key from Dashboard -> API)
cd adapter && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
SMT_SIGNALMESH_URL=https://app.yourdomain.com SMT_SIGNALMESH_API_KEY=bb_... SMT_ENV=development \
  uvicorn signalmesh_terminal.main:app --port 8090
# UI with hot reload (proxies /api/terminal to :8090)
cd web && npm install && npm run dev
```

No SignalMesh at hand? `SMT_PROVIDER=fixture` serves recorded response shapes with a FIXTURE banner.

## Checks

```bash
scripts/check.sh              # unit tests, typecheck, build, read-only audit
scripts/check.sh --parity     # + Phase 3 parity against the engine (SM_URL, SM_KEY, TERM_URL)
```

## Deployment

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — one command on the server. The
terminal is served at `https://<SignalMesh host>/terminal/` through the existing
Caddy (no new DNS) and uses the **same login as SignalMesh**: the adapter checks
the browser's SignalMesh session cookie against SignalMesh for every request, so
there is no second password or token. The SignalMesh dashboard gets one
"Terminal" menu group. Everything else — container, config, adapter, UI — stays
independent.

## Attribution

The chart is drawn with TradingView's open-source Lightweight Charts library
(Apache License 2.0). Its attribution logo in the chart corner is kept as
the license requires. No TradingView account, widget or subscription is used.
