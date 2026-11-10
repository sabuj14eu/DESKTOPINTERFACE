# HANDOFF — the SignalMesh Terminal window (written 2026-11-10, platform 5.200)

Read `README.md` and `docs/DATA_CONTRACT.md` first; this file says where things ARE and what was learned,
not how the code works. The platform's own handoff is `docs/HANDOFF_PLATFORM_SESSION.md` §15–§16 in
`sabuj14eu/Sniper-System`; it names this file.

## 1. What this is, and what it never does

A cTrader-style, read-only desktop interface for SignalMesh (the Brother Bot platform). It displays what the
engine already computed — prices, candles, structure, bias, signals, Entry/SL/TP1/TP2, R:R, ATR, news, macro,
freshness, trades, performance, data sources, system health — and nothing of its own.

- GET-only. `adapter/tests/test_read_only.py` asserts no write verb exists in the provider or auth code, that
  nothing imports SignalMesh, and that every broker `place()` refuses.
- Recalculates nothing. `normalize.py` reshapes; each display rule is named in the payload and mirrors
  SignalMesh's own chart page.
- Freshness travels with every number (LIVE / STALE / UNKNOWN / INVALID, never upgraded). Fixture data is
  refused in production (`SMT_ENV=production`) and never labelled live.
- Execution (Phase 6) is DISABLED. `brokers/{manual,mt5,ctrader}.py` are a dark seam; `POST execution/place`
  is always 403. A two-week side-by-side period against the dashboard precedes any execution work, and the
  gates are in `docs/EXECUTION_ROADMAP.md`.
- **Every instrument SignalMesh stores is drawable; the list and the venue are SignalMesh's, the terminal adds
  none of its own.** (README, DATA_CONTRACT, the market-watch footer, `/api/terminal/market-watch`
  `instrument_rule`.)

## 2. Where it runs (witnessed 2026-11-10)

| Thing | Where |
|---|---|
| Repository / branch | `sabuj14eu/DESKTOPINTERFACE`, `claude/vibrant-albattani-kxhfwv`, draft PR #1 (CI green) |
| Box checkout | `/srv/signalmesh-terminal` on the SignalMesh Linux box |
| Container | `signalmesh-terminal`, `127.0.0.1:8090`, joined to `brotherbot_default`, **one** uvicorn worker (one cache) |
| Upstream | `SMT_SIGNALMESH_URL=http://app:8000` (the platform container, read API key `bb_…` in `.env`, never printed) |
| Public URL | `https://app.signalmesh.dev/terminal/` — nginx `location /terminal/ { proxy_pass http://127.0.0.1:8090/; }` inserted by `scripts/setup.sh` (`nginx.terminal.snippet`); no new DNS |
| Sign-in | `SMT_AUTH=signalmesh`: the SignalMesh session cookie `bb_session` is verified against `/chart/levels.json`; 401 carries `login_url=/login?next=/terminal/`; a refresh of `/terminal/` never redirects a signed-in user |
| Operator bypass | header `X-Terminal-Key` = the read API key (what `acceptance.sh` uses inside the container) |
| Menu | one TERMINAL group in the dashboard nav (`app/templates/dash/_base.html` in Sniper-System, PRs #96/#97) |

Update line (Shyam pastes it; it must end with `0 FAIL`):

    cd /srv/signalmesh-terminal && git pull && scripts/setup.sh && scripts/acceptance.sh

`setup.sh` detects the app container, network, nginx site and public host, writes `.env`, builds, starts, checks
health and market-watch, inserts the nginx route if missing, `nginx -t`, reloads. No prompts, no pasted keys.
`acceptance.sh` runs `scripts/verify_parity.py` inside the container against `http://app:8000`.

## 3. What acceptance proves

`verify_parity.py` (engine vs terminal, field by field): instrument discovery (every instrument has a legitimate
origin in the platform's registry; availability per timeframe; watch list == available ∩ pins), every stored
instrument × 7 timeframes (counts, bars identical, per-candle source audit `mt5:…` unless
`ALLOW_FIXTURE_SOURCE=1`), decision/market/freshness fields, the price contract (1m JOINED ON BAR TIMESTAMP,
freshness lag ≤ 3 bars), expired plan not current, BUY/SELL side states, chart levels, market-watch rows,
signals/trades/stats, and optionally the old dashboard's JSON.

Last production run before 2026-11-10's new symbols: **20 instruments, 1478 checks, 0 FAIL.** The platform now
stores nine more (GER40, US500, EURGBP, EURJPY, GBPJPY, ADA, BNB, DOT, VIX); they are already in the registry
mirror (`normalize.SYMBOL_DECIMALS`, `discovery.MACRO_SYMBOLS`), so the next run should print 29 instruments.
**That run is the first thing to witness.** Discovery caches 300 s under its own keys (`disc:`/`cov:`/`src:`),
never under the live candle keys.

## 4. Laws this window learned (each one cost a user-visible fault)

- **Per-candle `source` is the authority.** A static "MT5 via mt5_reporter" label once sat over fixture bars.
- **Two clocks, both shown.** The header is the last closed 1m bar; the chart's last bar is the 15m engine
  reference; the drift between them is in the payload (`price-contract-v1`). A 39-minute-old "price" was neither.
- **Expired is not current.** A 12h-expired plan was drawn as live levels; it now lives in `expired_plan` and in
  Trade History, dotted on the chart behind a toggle.
- **One worker, one cache.** Two uvicorn workers gave two caches and a header that disagreed with the list.
- **A poller has a run id.** Switching assets raced: the old symbol's reply overwrote the new one (`usePoll`).
- **Discovery probes never poison live keys.** A probe stored under the live cache key left the chart one bar
  behind for five minutes.
- **Pins restrict, never add.** An old default pin (`GOLD,SILVER,BTC`) hid 17 stored instruments; `setup.sh`
  clears it.
- **Join on the bar timestamp.** Newest-vs-newest comparisons failed by one bar at the minute edge.
- **Auto-scale on every switch.** SOL drawn under ETH's price axis was invisible; `focusLatest` re-enables
  auto-scale and focuses the newest bar at ~70 % width, like TradingView.
- **The chart draws only what SignalMesh stores.** Structure badge, Pine's own words (trend, CHoCH, inducement,
  sweep, zone), the named level ladder, ACTIVE/PENDING markers — yes. Zone boxes, BOS/CHoCH lines, HH/HL labels
  — not stored, so NOT drawn; recommended after the comparison period as an engine-side read-only swing-points
  route, never a terminal-side recalculation.

## 5. Open, and in whose hands

- Witness the acceptance run with the 29 instruments (above).
- The two-week side-by-side period against the dashboard; nothing about execution before it ends.
- Phase 6 (execution) stays off; the roadmap's gates are in `docs/EXECUTION_ROADMAP.md`.
- Engine-side swing-points route (platform work, after the comparison period) if Pine-like structure drawing is
  wanted on the chart.

## 6. Paste this as the first message of a new terminal window

> You are continuing the SignalMesh TERMINAL window: repository `sabuj14eu/DESKTOPINTERFACE`, branch
> `claude/vibrant-albattani-kxhfwv` (draft PR #1, CI green), deployed at `/srv/signalmesh-terminal` on the
> SignalMesh box and served at https://app.signalmesh.dev/terminal/ behind the SignalMesh login. Read, in this
> order: `docs/HANDOFF.md`, `README.md`, `docs/DATA_CONTRACT.md`, `docs/VERIFICATION.md`, and in
> `sabuj14eu/Sniper-System` `CLAUDE.md` and `docs/HANDOFF_PLATFORM_SESSION.md` §15. The platform prints 5.200.
> Laws: GET-only, nothing recalculated, freshness carried, per-candle source is the authority, two clocks shown,
> expired never current, one worker one cache, pins restrict never add, discovery never poisons live keys, every
> instrument SignalMesh stores is drawable and the terminal adds none of its own, execution disabled until the
> roadmap's gates. Workflow: `scripts/check.sh` before every push (adapter pytest, tsc, vitest, build, write-verb
> audit, Playwright e2e against the fixture adapter), push the branch, let CI wake you; Shyam pastes ONE update
> line on the box — `cd /srv/signalmesh-terminal && git pull && scripts/setup.sh && scripts/acceptance.sh` — and
> it must end with 0 FAIL. No prompts, no pasted keys, nothing complex. Confirm by telling me in six lines: where
> the terminal runs and how it signs in, what acceptance proves and its last counts, the first thing to witness,
> the one chart feature deliberately not drawn and why, and the phase that stays off. Then wait for my first task.
