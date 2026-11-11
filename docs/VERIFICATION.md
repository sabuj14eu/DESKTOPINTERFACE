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

## Terminal V2 — acceptance tests → evidence

Automated in `web/e2e/workspace.mjs` (Playwright, real UI; runs in `scripts/check.sh` and CI against the fixture adapter, and against any adapter with `TERM_URL=… [TERM_KEY=…] node e2e/workspace.mjs`), `adapter/tests/test_v2.py`, and sections 6–7 of `scripts/verify_parity.py` (which is what `scripts/acceptance.sh` runs on the box).

| # | Acceptance test | Evidence |
|---|---|---|
| 1 | Full-screen chart | e2e: every panel hidden, chart = window width and ≥ 82 % of its height, newest bar in view; `Esc` restores |
| 2 | Hide and restore both side panels | e2e: chart width becomes the window width; panels return at their previous widths |
| 3 | Panel resizing | e2e: each border dragged, the three sizes change independently |
| 4 | Workspace persistence | e2e: reload keeps sizes, hidden panels and the Toolbox tab; Reset layout restores defaults |
| 5 | Open a signal, identify engine and strategy | e2e: the drawer's origin rows equal `/signals/{id}`; `UNKNOWN` where SignalMesh sent nothing |
| 6 | Switch between two connected accounts | e2e on the fixture's two accounts; **in production this needs two accounts reporting AND a per-account route** — see below |
| 7 | MT5 balance and equity against the broker | `verify_parity.py` §6: terminal = SignalMesh's stored broker figures. **Against the broker itself: a human compares the Account Information tab with the MT5 terminal** |
| 8 | Open positions and pending orders | `verify_parity.py` §6 (counts vs the journal); same human comparison with MT5's Trade tab |
| 9 | Signals not confused with executions | e2e + `test_v2.py`: a signal is an execution only with a journal row naming its `signal_id`; `verify_parity.py` §7 on 25 live signals |
| 10 | Production behaves exactly as before | nothing in `Sniper-System` changed; adapter still GET-only (`test_read_only.py`); `place()` 403; the full parity run still ends `0 FAIL` |

Result in the sandbox on 2026-11-10 (fixture adapter): adapter tests pass, `workspace.mjs` all checks passed, `switch.mjs` consistent.

**Not yet witnessed in production** (the sandbox has no production access): tests 6–8 and the parity run with the new sections. What production will show depends on SignalMesh's read API:
* if it has no per-account route, the terminal shows SignalMesh's portfolio total — exact for one account, labelled COMBINED for several — with broker, server, DEMO/LIVE, used margin, margin level and heartbeat time as NOT AVAILABLE;
* per-account switching (test 6) and those fields need SignalMesh to expose a read-only per-account route (the shape is in `DATA_CONTRACT.md`, account-contract-v1). That is a platform change and was deliberately not made here.

## Version identification and screenshots (2.1.0)

| Requirement | Evidence |
|---|---|
| The version on screen is the deployed build's | `test_build_identity.py`: `VERSION` = newest `RELEASES.md` heading; the number appears nowhere in the code; `/health` and `/version` carry version, commit, build, environment, data kind. `e2e/workspace.mjs`: the toolbar shows exactly what the server reports, and the browser bundle is the same build |
| Screenshots come from the real application | `scripts/screenshots.sh` photographs the terminal running on the box; `manifest.txt` records version, commit, environment and data kind, and each picture shows them in its toolbar |
| Release history | `docs/RELEASES.md`, shown in the terminal's version panel |

The Docker image itself (including the `meta` stage that computes `build.json`) is built by CI on every push. `scripts/screenshots.sh` has not been run on the box yet.

## Forecast journal (2.5.0)

| Requirement | Evidence |
|---|---|
| Journal writes are isolated from SignalMesh | `test_read_only.py`: only `journal.py` opens a database, it is a local SQLite file from `SMT_JOURNAL_PATH`, no database-server driver anywhere, no write route. `test_journal.py`: `journal.py` imports no network code |
| A forecast is never changed afterwards | `test_journal.py`: a second connection's UPDATE / DELETE is aborted by the database; re-recording the same forecast with "better" levels leaves the first record; ids and outcome history survive a reopen |
| Targets, invalidation and expiry are fixed before recording | `test_journal.py`: thirteen incomplete or inconsistent forecasts are refused whole |
| Every forecast is recorded, losses included | recorder test: every forecast the module reports is written; SL results are present; e2e checks SL rows are listed |
| Scoring: closed bars only, no lookahead, forward only | `test_journal.py`: rule-by-rule cases; every prefix of four seeded series gives exactly the first events of the full series; stored outcomes only grow between passes; a forming bar is dropped. **Recorded Gold / Silver history is never committed (public repository): the same check runs on the box, inside the container — `scripts/export_history.sh` → `scripts/history_check.py` — and prints one OK / FAIL line per file. Not yet run** |
| No production data in the repository; the box never uses git | `test_journal.py`: no history, backup or journal file is tracked; the box scripts contain no git or GitHub command |
| Gold and Silver statistics are separate; sample size always shown | stats test and e2e: one group per module / symbol / timeframe / origin; LUCK under 20 |
| Backup before every deployment | `scripts/setup.sh` runs `scripts/journal_backup.sh` before `docker compose up --build` and stops if an existing journal cannot be copied. **Not yet run on the box** |
| Production | `scripts/acceptance.sh` section "forecast journal": store READY, append-only, recorder running, no fixture module, groups add up. **Not yet witnessed** |

## Forecasting studies, step 2 (2.6.0)

| Requirement | Evidence |
|---|---|
| Ported formulas | `test_forecast.py`: top = low + ADR, bottom = high − ADR, ADR from the last 14 completed days only, snap within tolerance only, status words, ladder states / actions / score, GO TRADE wording |
| Closed bars, no lookahead, no repaint | `test_forecast.py`: the journal module on every prefix of four seeded 15m series (with only the daily bars closed by then) reports the same forecasts as the full series; changing a day's own daily bar moves no forecast of that day. On the box: `scripts/export_history.sh` runs the same audit on recorded Gold and Silver bars. **Not yet run** |
| Missing data is said, not guessed | too few daily bars, no bar in the new day, daily bars behind → NOT AVAILABLE with no levels; 6-month outlook UNKNOWN; an instrument without history is unranked |
| Each study is its own switch, off by default, remembered | `e2e/workspace.mjs`: off by default; menu lists them; lines and report appear; top-only draws one line; history adds lines; survives a reload; switched off leaves nothing |
| Labels | e2e + tests: TERMINAL STUDY · NOT SIGNALMESH; HYPOTHETICAL ANALYSIS LEVEL on every scenario; confidence UNKNOWN |
| Agrees with the engine's candles | `scripts/acceptance.sh` section "forecasting studies": ADR and today's high / low recomputed from the engine's closed candles for Gold and Silver. **Not yet witnessed** |
