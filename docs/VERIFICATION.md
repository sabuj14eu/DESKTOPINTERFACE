# Verification plan (Phases 3–5) and acceptance criteria

## Automated

| Check | Command | Proves |
|---|---|---|
| Read-only by construction | `cd adapter && pytest -q` (`test_read_only.py`) | the production provider has no write verb; no SignalMesh import; no DB; every broker `place()` refuses |
| Reshape fidelity | `pytest` (`test_normalize.py`) | candles, signals, levels rule, summary mapping, lane wording, freshness pass-through, against recorded engine responses |
| Route contract | `pytest` (`test_routes.py`) | every route answers, place() is 403, token gate works, fixture refused in production |
| UI builds | `cd web && npx tsc -b --noEmit && npm run build` | strict TypeScript, production bundle |
| **Parity** | `scripts/verify_parity.py` | every candle (ts, o, h, l, c), decision field, market field, freshness state, chart level, market-watch price, signal, trade and stat equals the engine's; price-contract fields; expired plans never current; BUY/SELL states follow the engine status |
| **Source audit** | same script | every candle's per-candle `source` is an MT5 reporter feed (`mt5:<login>`); fixture or bridge data FAILS unless `ALLOW_FIXTURE_SOURCE=1` (local sandbox only) |
| **Old dashboard vs new terminal** | same script with `SM_SESSION_COOKIE` | the dashboard's own `/chart/candles.json` and `/chart/levels.json` (what `/chart` draws) vs the terminal, same symbol / timeframe / bar timestamps: OHLC identical on every shared bar; levels identical, and expired ones shown as history |
| Instrument discovery | `scripts/verify_parity.py` (section `instruments`) | every instrument the terminal lists is one SignalMesh knows (DEFAULT_SYMBOLS via `/api/v1/news/state`, or signalled); per timeframe, `available` equals "the engine stores candles"; the market watch equals the available set; with no symbol argument the whole run covers every available instrument |
| Stale-price race | `cd web && npx vitest run` (`usePoll.test.tsx`) | GOLD → BTC → SILVER → GOLD with deliberately slow answers: switching clears the old price at once and a late answer for the previous symbol is dropped |
| Symbol switching, end to end | `web/e2e/switch.mjs` (Playwright, in `check.sh`) | in the real UI, for GOLD → BTC → SILVER → GOLD: the header price equals the engine's newest 1m close of the selected symbol, the chart's newest bar equals the symbol's own 15m close, and the chart and decision panel name the symbol |
| All of the above | `scripts/check.sh [--parity]` | one command; CI runs it on every push |

Result on 2026-11-06 against a local SignalMesh instance (seeded, synthetic candles
pushed through SignalMesh's own reporter endpoint, `ALLOW_FIXTURE_SOURCE=1`):
**348 checks, 0 FAIL** over every discovered instrument (12 found, 4 with candles),
including the old-dashboard comparison (100 shared bars per timeframe identical).
Against production (real MT5 reporter data) the engine-side run passed on GOLD,
SILVER and BTC with `source audit: ['mt5']`.

**This has not yet been run against production.** The sandbox has no production
URL or key, by design. Run step 5 of `docs/DEPLOYMENT.md` on the server; the
source audit there must report `kinds ['mt5']` with no `ALLOW_FIXTURE_SOURCE`.

### How to get the dashboard cookie for the comparison
Log in to SignalMesh in a browser → DevTools → Application → Cookies → copy the
value of `bb_session` → `SM_SESSION_COOKIE=<value>`. It is read-only use of your
own session; revoke it afterwards from Security → sessions if you wish.

## Phase 4 — two weeks side by side

Run `scripts/verify_parity.py` from cron every hour on the server and keep the
output:

```
0 * * * * cd /srv/signalmesh-terminal && SM_URL=... SM_KEY=... TERM_URL=http://127.0.0.1:8090 TERM_TOKEN=... python3 scripts/verify_parity.py >> /var/log/signalmesh-terminal-parity.log 2>&1
```

A day with any FAIL line is a finding to read, not a number to average.

## Phase 5 — what to compare

* **Reliability**: adapter restarts (`docker compose ps`), 5xx count in its logs, parity FAIL count.
* **Signal visibility**: time from a signal's `created_at` to its first appearance on the terminal (≤ one poll interval + cache TTL = 30 s by default).
* **Data freshness**: the terminal's freshness word must always equal the engine's for the same bar (parity checks it).
* **Usability**: can the operator see entry/SL/TP, the decision word and the invalidation on one screen without scrolling.

## Acceptance criteria → evidence

| Criterion | Evidence |
|---|---|
| 1. Zero changes to SignalMesh | separate repo; no PR to Sniper-System; the Caddyfile gains one hostname block only |
| 2. Accurate engine outputs | parity 0 FAIL |
| 3. Correct candle/price updates | parity candle section; UI polls closed bars with the engine's freshness |
| 4. Correct signal lifecycle | buckets mirror status + 12 h TTL (planner.SIGNAL_FRESH_H); expired plans greyed |
| 5. Correct entry/SL/TP | parity chart-level section |
| 6. No fabricated / duplicated signals | signals are the engine's rows by `signal_id`; parity asserts identical id sets |
| 7. No paid TradingView | Lightweight Charts (Apache-2.0) only |
| 8. Simultaneous operation | separate container; SignalMesh dashboard unchanged |
| 9. No accidental execution | `place()` 403 for every mode; `test_broker_place_always_refuses` |
