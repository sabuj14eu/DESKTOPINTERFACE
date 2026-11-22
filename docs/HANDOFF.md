# HANDOFF — the SignalMesh Terminal window (V2 written 2026-11-10; forecasting state added 2026-11-11, platform 5.201)

Read `README.md` and `docs/DATA_CONTRACT.md` first. This file says where things ARE, what was learned, and
what is still unproven — not how the code works. The platform's own handoff is
`docs/HANDOFF_PLATFORM_SESSION.md` §15–§16 in `sabuj14eu/Sniper-System`; it names this file.

## 1. What this is, and what it never does

A read-only desktop trading terminal for SignalMesh (the Brother Bot platform), in the manner of cTrader and
MT5 desktop, usable on a phone. It shows what the engine already computed and what the broker already
reported, and adds nothing of its own.

- **GET-only.** `adapter/tests/test_read_only.py`: no write verb in the provider or auth code, nothing imports
  SignalMesh, every broker `place()` refuses.
- **Recalculates nothing.** `normalize.py` reshapes; each display rule is named in the payload.
- **Freshness travels with every number** (LIVE / STALE / UNKNOWN / INVALID, never upgraded). Fixture data is
  refused in production and never labelled live.
- **A signal is not a trade.** SignalMesh recommendations and broker records are in separate tabs, and a
  signal is called an execution only when a broker journal row names its `signal_id`.
- **Broker figures are the broker's**, one account at a time, never summed or derived; missing = NOT AVAILABLE.
- **Execution is DISABLED.** `brokers/{manual,mt5,ctrader}.py` can translate an order intent and nothing
  else; `POST execution/place` is always 403. Gates: `docs/EXECUTION_ROADMAP.md`.
- **Every instrument SignalMesh stores is drawable; the list and the venue are SignalMesh's, the terminal adds
  none of its own.**

## 2. Where it runs

| Thing | Where |
|---|---|
| Repository | `sabuj14eu/DESKTOPINTERFACE` |
| Deployed branch | `claude/vibrant-albattani-kxhfwv` (draft PR #1 to `main`) — the box pulls this |
| Work branch | a `claude/<name>` branch cut from the deployed branch (forecasting window: `claude/keen-keller-bb7pbw`), PRs **into the deployed branch**; a change reaches the box only after its PR is merged AND the update line is run |
| Box checkout | `/srv/signalmesh-terminal` on the SignalMesh Linux box |
| Container | `signalmesh-terminal`, `127.0.0.1:8090`, joined to `brotherbot_default`, **one** uvicorn worker (one cache) |
| Upstream | `SMT_SIGNALMESH_URL=http://app:8000` (read API key `bb_…` in `.env`, never printed) |
| Public URL | `https://app.signalmesh.dev/terminal/` — nginx `location /terminal/` → `127.0.0.1:8090`, inserted by `scripts/setup.sh`; no new DNS |
| Sign-in | `SMT_AUTH=signalmesh`: the SignalMesh session cookie `bb_session` is verified against `/chart/levels.json`; 401 carries `login_url=/login?next=/terminal/` |
| Operator bypass | header `X-Terminal-Key` = the read API key (what `acceptance.sh` uses inside the container) |
| Menu | one TERMINAL group in the dashboard nav (Sniper-System PRs #96/#97) — unchanged by V2 |

Update line (Shyam pastes it AFTER the PR is merged — pasting it before changes nothing; it must end with `0 FAIL`):

    cd /srv/signalmesh-terminal && git pull && scripts/setup.sh && scripts/acceptance.sh && scripts/screenshots.sh

`setup.sh` copies the forecast journal to `backups/` before it rebuilds, and stops if that copy fails.

No new setting is required. `SMT_ACCOUNTS_PATH` defaults to `/api/v1/accounts`; a 404 there is handled.

Which version is running is in the toolbar (`SIGNALMESH TERMINAL | V2.1.0  PRODUCTION  build N · commit`), read from
the build, never typed (`VERSION`, the Dockerfile `meta` stage, `adapter/…/build.py`). Releases: `docs/RELEASES.md`
— add a section and bump `VERSION` in the same commit, or the tests fail. Screenshots of the deployed terminal:

    cd /srv/signalmesh-terminal && scripts/screenshots.sh

(a throw-away Playwright container, read-only; the pictures stay on the box in `screenshots/`). A screenshot
from anywhere else must show LOCAL or TEST FIXTURES in its toolbar — never present one as production.

## 3. What V2 added

| Area | What | Where |
|---|---|---|
| Workspace | hide/show Market Watch, Decision, Toolbox; draggable borders; full-screen chart (`F`/`Esc`); saved in the browser (`smt_workspace_v2`); Reset layout | `web/src/workspace.ts`, `Splitter.tsx`, `App.tsx` |
| Look | MT5 habits: M1…D1 buttons, Toolbox tabs along the bottom edge, status bar with the account figures | `TopBar.tsx`, `StatusBar.tsx`, `styles.css` |
| Phone | one view at a time + bottom bar (Quotes · Chart · Signal · Trade · Account); touch drag and pinch | `App.tsx` (`mobile`), `styles.css` @860px |
| Chart | scale and scroll controls, fit all, 300/500/1000 bars, UTC bar timestamps, clickable signal markers, indicator slot | `ChartPanel.tsx`, `indicators.ts` |
| Signal information | origin field by field, validation, invalidation, the five stages | `adapter/…/transparency.py`, `SignalDetail.tsx`, `GET /signals/{id}` |
| Accounts | selector (connected only), Account Information, Open Positions, Pending Orders | `adapter/…/accounts.py`, `AccountSelector.tsx`, `GET /accounts`, `GET /account` |
| Forecast journal (2.5.0) | the terminal's own append-only SQLite file on the volume `signalmesh_terminal_journal` (`/data/journal.sqlite`); server-side recorder and scorer; Toolbox tab; backup before every rebuild | `adapter/…/journal.py`, `recorder.py`, `GET /journal`, `JournalTab.tsx`, `scripts/journal_backup.sh` |
| Forecasting studies, step 2 (2.6.0) | "indicators" menu → Daily forecast top / bottom (chart lines) and Asset ranking table; on-chart read-only report with scenario, outlooks, method; journal module `daily-forecast` | `adapter/…/forecast.py`, `audit.py`, `GET /forecast/daily`, `/forecast/ranking`, `web/src/forecast.ts`, `StudyReport.tsx`, `ChartPanel.tsx` |
| Execution seam | `OrderIntent` → `MT5Broker.translate()` / `CTraderBroker.translate()`; nothing sends | `adapter/…/brokers/` |

## 4. What is proven, and what is not

Proven in the sandbox (fixture adapter, `scripts/check.sh`): adapter tests, typecheck, build, the write-verb
audit, `e2e/switch.mjs`, and `e2e/workspace.mjs` — acceptance tests 1–5 and 9 in the real UI, 6–8 on the
fixture's two accounts, and the phone layout. Table: `docs/VERIFICATION.md`, "Terminal V2".

**Witnessed in production on 2026-11-11 (2.1.0, build 33, commit 096b715, PRODUCTION DATA):**
acceptance **29 instruments, 2025 checks, 0 FAIL**; `scripts/screenshots.sh` produced the nine pictures on the box;
the toolbar read `V2.1.0 · PRODUCTION · build 33 · 096b715`. The run also printed, from the live engine:
`no per-account route at /api/v1/accounts (HTTP 404)` and `trade rows carry: ticket (ABSENT), account_login
(ABSENT), signal_id (ABSENT)`. The account menu showed **2 MT5 accounts · COMBINED**.

**Still not proven:**

1. **Every later release.** A PR merged is not a release deployed: read the toolbar after the update line.
2. **Per-account data — investigated 2026-11-11, see `docs/PLATFORM_READ_ROUTES.md`.** SignalMesh 5.200 has
   NO `GET /api/v1/accounts`; `/api/v1/portfolio` is a sum over every account. So production shows the
   portfolio total (exact for one account, COMBINED for several). The accounts ARE stored separately
   (`mt5_accounts`), so a read-only route fixes it with no schema change (change A). DEMO/LIVE, used margin and
   margin level are not stored and not sent by the reporter: they need a reporter + schema change (change B,
   needs Shyam's explicit approval). **Platform work, not done here.** The acceptance run prints which case the
   box is in.
3. **Balance and equity against the broker (acceptance 7–8).** The script proves terminal = SignalMesh. Only a
   person can compare the Account Information tab with the MT5 terminal's own Trade tab.
4. **Signal → trade links.** The platform already links trades to signals in its database
   (`trades.signal_id`, attribution-v1) but `GET /api/v1/trades` does not return the ticket, the account or
   the signal id. Until change A adds those keys, every signal reads "no broker order linked". The terminal
   already reads them and needs no change.

## 5. Laws (each one cost a user-visible fault, or prevents one)

- **Per-candle `source` is the authority.** A static "MT5 via mt5_reporter" label once sat over fixture bars.
- **Two clocks, both shown.** Header = last closed 1m bar; chart's last bar = the timeframe's; drift is in the payload.
- **Expired is not current.** A 12h-expired plan lives in `expired_plan` and Trade History, never in `levels`.
- **One worker, one cache.** Two uvicorn workers gave a header that disagreed with the list.
- **A poller has a run id.** Switching symbol — and now account — drops the previous answer (`usePoll`).
- **Discovery probes never poison live keys.** Own cache keys (`disc:`/`cov:`/`src:`).
- **Pins restrict, never add.**
- **Join on the bar timestamp.** Newest-vs-newest fails at the minute edge.
- **Auto-scale on every switch.** `focusLatest` re-enables it; the newest bar sits at ~68 % width.
- **Engine facts and terminal studies are two things, and each is labelled.** The engine's levels, structure word,
  ladder and signal markers are SignalMesh's. Since 2.4.0 the chart can ALSO draw Smart Money Concepts overlays
  (S/R, FVG, BOS, CHoCH, order blocks, liquidity, inducement): the terminal's own display-only studies, asked for by
  Shyam, calculated in `smc.py` from stored closed candles (smc-v1). They are never presented as the engine's or as
  Pine's, and are an input to nothing. Connecting them to the engine needs separate testing and Shyam's explicit approval.
- **2.4 — a study must not look ahead or repaint.** `tests/test_smc.py` analyses every prefix of a series; it caught
  order blocks being re-dated by a later break before the first release. A close breaks, a wick sweeps.
- **2.5 — the journal is the terminal's own file, append-only, and the only thing the terminal writes.** Not SignalMesh's database, no write route, edits and deletions refused by the database. A forecast is recorded once with every level fixed, losses included; results are separate rows naming their bar. Never `docker compose down -v` and never `docker volume rm signalmesh_terminal_journal`: that is the record.
- **2.5.1 — the box only pulls.** `/srv/signalmesh-terminal` has no GitHub credentials and never commits or pushes; every commit and push comes from the development session. No script on the box may use git beyond Shyam's own `git pull`, and none may ask for a password, token or key (2.5.0's export did, and was cancelled).
- **2.5.1 — this repository is PUBLIC: production data never goes into it.** No trades, balances, account numbers, candle history, journal or backup — not as fixtures, not on a side branch. Tests that need real history run on the box (`scripts/export_history.sh` → `history_check.py`) and print a summary; if the files themselves are needed, Shyam copies them with scp and uploads them to the chat, and they are still not committed.
- **2.6 — a forecasting study is ported from Shyam's Pine where Pine has the logic, and says where it differs.** Anything the terminal adds (the fade scenario's stop and targets, the longer outlooks) is labelled as the terminal's own rule. The day is the broker's day. Confidence is UNKNOWN or the journal's measured rate — never a typed number.
- **2.5 — a hit rate is never shown without its sample size**, never pooled across symbols, and LIVE is never mixed with BACKFILL.
- **V2 — never link by resemblance.** Same symbol, price and minute is not evidence that a trade came from a signal.
- **V2 — `approved` is the brain's word, not the user's.** The user-approval stage is NOT RECORDED until the terminal has one.
- **V2 — never split or derive a broker figure.** A total over several accounts stays one COMBINED entry; used
  margin is not equity minus free margin.
- **V2 — the account number stays on the server.** The browser gets a mask and an opaque key.
- **2.3 — the forming bar is display-only.** It comes from `/live` (bridge, else closed 1m bars), is drawn after the
  closed series and never joins it; a dead or stale bridge is a named state, never a quiet fallback that looks live.
- **V2 — an indicator is display-only.** Computed in the browser from the bars shown, off by default, and never
  an input to a decision, a level or a signal (`indicators.ts`).

## 6. Open, and in whose hands

- Merge the V2 PR into the V1 branch, paste the update line, read the acceptance output (Shyam).
- Compare Account Information with MT5 itself (Shyam).
- Platform change A in `docs/PLATFORM_READ_ROUTES.md` (read-only `/accounts`, three keys on `/trades`) — platform window, on Shyam's word.
- Platform change B (reporter sends margin, margin level, trade_mode) — only with Shyam's explicit approval.
- The two-week side-by-side period; nothing about execution before it ends.
- **Forecasting studies (journal and scoring, asset ranking and daily forecast, Fibonacci and anchored VWAP, Wolfe, Elliott and volume profile): the plan, laws and decisions are in `docs/FORECASTING_PLAN.md`. One release per step. Step 1 (journal and scoring) is release 2.5.0, witnessed on production in 2.5.1; step 2 (daily forecast, asset ranking) is release 2.6.0; steps 3–5 are releases 2.7.0 to 2.7.3 as display-only pattern studies; Wolfe and Elliott are journalled, the other three are not (plan §5c). The scope was accepted on production at 2.7.3.**
- More indicators, separate indicator panes, saved chart templates, several charts side by side (terminal window, on request).
- Engine-side swing-points route if Pine-like structure drawing is wanted (platform window, after the comparison period).

## 7. State on 2026-11-19 — 2.9.0 on the box. Read this before the opening prompt

**2026-11-22 15:42 UTC — 2.13.1 IS ON THE BOX (build 97, `4581573`); its acceptance ended 4296 checks, 2 FAIL; 2.13.2 fixes the check.** Shyam's paste of the whole run. Both FAILs were the new limit-checklist check on DOT and OIL ("TP1 lies in the trend's direction from price"): the check measured TP1 against the price now, and price sat on a support, so "just above it" was over the price. The study was coherent (TP1 below the entry); the CHECK was too strict, and so was the unit test that had only met seeded bars. **Lesson, the third time in this repository: a check that has only met seeded data proves the seed.** What the run showed besides: Market Outlook "no series fault" on 31 of 31 by the platform's rule (DOWN 17, UP 6, NO CLEAR TREND 6, UNKNOWN 2); the terminal's OWN check: SERIES FAULT on US10Y daily only (101 places — the platform's known "two instruments under one name"), VIX and ANT unchecked because thin (fixed in 2.13.2: the series check now runs first); limit checklist OK on 28 (CHECKLIST HOLDS 2, WAIT 14, NO TRADE 12); the platform now sends `sender` on trades (AUTOLIVE / auto-live-v1 on 61 of the newest 195, 58 with a sender that names neither sensor nor engine, 76 none); market clock closed for 23, open for 8; journal 1,926 forecasts.

**2026-11-22 15:20 UTC — the last 22 old rows are gone (platform 5.222), and both sides ask for the terminal's own series check.** The platform printed REPAIRED for every 1d and 4h series it holds (BTC 4h and GOLD 4h at about 14:50 UTC); the bot side released its last unfit series. GOLD 4h now starts 1998-04-22: no terminal study counts from the first bar (each reads the newest N), so nothing here moved. 2.13.1 adds the checklist to the box's acceptance and prints the terminal's OWN series check per run — newest 1000 daily and 500 4h bars only, so it witnesses the recent part of the repair and nothing older, and nothing on 1h and below. Open between the other two sides, not ours: VIX_Z6 and DXY_Z6 roll dates (week of 7 Dec), a plan for 1h and below, the Strategy Factory's holdout cut by count.

**2026-11-22 14:10 UTC — the platform says its daily and 4h repair is complete; two lines of our release notes were corrected.** Its own rule on the box at 14:09 UTC: SERIES FAULT on 0 of 32 daily series; 3 read UNKNOWN for too few daily bars (ANT 17, US02Y 55, US10Y 55); 29 read a state; left over are 22 single 4h bars from 2003 (GOLD) and 2011–12 (BTC). Still unrepaired by its own word: every 1h-and-below series, and US10Y holds two instruments. NOT confirmed by the terminal's own check: no update run after the repair has been pasted here — the "outlook views" NOTE of the next run is the confirmation. 2.13.0 was merged on Shyam's word ("always merge and give the update command" is his standing instruction from 22 November); whether he ran its update line was not witnessed.

**2026-11-22 — 2.13.0 BUILT: the Limit Checklist tab and EMA 20 / 100 / 200.** Shyam asked in his own words for "a new indicator for this condition, show only, not a trade signal", with his seven-step checklist for a pending sell limit (flip for a buy), and "draw all EMA". Built as a terminal study (`limitplan.py`, `limit-checklist-v1`, `docs/DATA_CONTRACT.md`): a Toolbox tab with one line per step and the hypothetical levels, nothing to press, not recorded. The terminal's own choices (overlap = one 4h ATR, buffer 0.4%, the round-number step, "just above" = 0.1 ATR) are named in its method text; the 3–8% bounce is his number and will rarely pass on FX. Not drawn on the chart. Tested on seeded up, down and flat series; NOT seen on production. The platform also reported its repair finished except BTC 4h and GOLD 4h (old 2003–2012 rows) and asked which series still read `series_fault` after Market Outlook's next sweep: the update run prints that list.

**2026-11-21 23:36 UTC — 2.12.1 IS ON THE BOX** (build 88, commit `b4733fe`, PRODUCTION DATA; Shyam's paste of the whole run; platform 5.215 or later). 2.12.0 ran before it on his word ("running v2.12.0"); its own output was not pasted.

- **Acceptance on production: 4139 checks, 0 FAIL.** All three gates PASS (gate 1: 2178; gate 2: 138; gate 3: 15; per-instrument parity 1591). Restore rehearsal all OK, seven chart checks PASS.
- **The Saturday LIVE fault is gone on production:** SignalMesh's clock read closed for 23 instruments and open for 8; the terminal showed MARKET CLOSED on those 23 and LIVE on the 8 (crypto). The forming bar read MARKET_CLOSED.
- **Seen on production for the first time:** `/api/v1/accounts` carrying `margin`, `margin_level`, `trade_mode`; every history cell FRESH (248); the platform's Finding E line passing ("The 15m series reaches as far as the closed 1m bars cover"); the Call Ledger with finished calls (6 calls: 4 PENDING, 1 TARGET HIT, 1 INVALIDATED, verdict UNPROVEN, every outcome stored).
- **Trade senders:** 195 of the newest 200 trades read "not stated"; `/api/v1/trades` carries no `sender` key yet. The column waits for the platform.
- **FINDING for the platform window (sent through Shyam): SERIES FAULT moved, it did not shrink.** The twelve repaired instruments read clean (US100, US30, the six majors, LTC, SOL, XRP) and DXY still faults, all as the platform said. But 16 instruments that were CLEAN on 2026-11-20 now read SERIES FAULT on their daily series: GOLD, SILVER, GER40, US500, VIX, EURGBP, EURJPY, GBPJPY, ADA, BNB, BTC, DOT, ETH, OIL, AAPL, NVDA. Market Outlook reads UNKNOWN on 19 of 31 and writes no call for them. Not established here: the cause (the corrected reporter re-sending right-stamp daily bars beside the old ones is the platform's own description of what happened to the thirteen) or the two timestamps of any pair — the terminal sees only the platform's sentence.
- **Seen by eye on production (Shyam's screenshot, BTC M15, 2026-11-21 23:56 UTC):** the Outlook button in the top bar; the Market Outlook tab open in the Toolbox, reading "SERIES FAULT — 7 date(s) carry TWO daily bars in the last 262" for BTC in the neutral colour, with no question answered; the counted record "UNPROVEN — 2 call(s) resolved …", uncoloured; Market Watch rows reading "MARKET CLOSED · reopens in 22h 03m · last price, not live" (GOLD, SILVER) and CLOSED where the engine had said LIVE (DXY, US100, US30, VIX); the account line reading DEMO with margin 1.37 USD and margin level 824,764.23 % (the broker's own number: a very small margin).
- **Market Outlook on a clean series, seen on production (Shyam's paste of the US100 tab, 2026-11-21 23:58 UTC):** DOWN so far, the two "interesting" levels with their bars and distances, "a daily close above 28600.3", the open system call (BEARISH from 25209.9, continues at 24149.5, turned at 26270.3: both distances equal the daily ATR shown, 1060.4), every level above and below, and the nine-row overview.
- **A clue for the platform, from that overview (suggestive, not established):** the faulted weekday instruments each read "5 date(s) carry TWO daily bars" (GOLD, SILVER, NVDA) and the crypto ones "7 date(s)" (BTC, ETH) — exactly one week of trading days for each kind. If those are the newest dates, the twins are being made now and not in the old gap weeks.
- **Still NOT seen on production:** the Call Ledger and Turning Point tabs, the Sender column and the "by plans" lines, by eye or by picture (the screenshot run takes no picture of them); a NOT LOADED YET cell; a board FAULT; MARKET QUIET on a weekday break; a real `sender`.

**2026-11-21 (evening) — 2.12.1: a Sender column, waiting for the platform's field.** The bot side armed `LANELIVE` / `lane-live-v3` on demo account 52834417 and asked for the sender to be named on its trades (platform repo, `docs/MESSAGE_TO_TERMINAL_2026-11-21_H.md`). The platform's own note says its trade rows carry no sender for ANY v7 trade today (`signal_id` null on 0 of 121 linked) and offers `sender {sensor_system, route, engine, rule}` on `GET /api/v1/trades`, on Shyam's word. The terminal names no sender on v7 trades today and never did; a signal's sender comes from the signal row (`system`). 2.12.1 reads the offered shape exactly and prints "not stated" until it arrives. Whether Shyam ran the 2.12.0 update was not witnessed here.

**2026-11-21 — 2.11.1 and 2.12.0 (after six notes from the platform window; platform 5.215 on the box).**

- **2.11.1:** an "Outlook" button in the top bar (Shyam had not found the three tabs: his Toolbox was hidden), and a test that the account fields of platform 5.213 (`margin`, `margin_level`, `trade_mode`; 0 = demo is a value) are read with no code change. Merged on his word; whether he ran its update line was not witnessed here.
- **2.12.0:** `market-status-v1` — never LIVE on a closed market — and the lane history counted by plans, shown first. See `docs/DATA_CONTRACT.md`.
- **Answer owed to the platform window, and given to Shyam to paste:** the field that painted US100, US30, VIX and DXY "live" on Saturday was `freshness.state` of `GET /api/v1/market/candles` (also `snapshot.freshness.candles.state`). It read LIVE while `market_status.open` was false; reproduced on a local copy of platform 5.215 on Saturday 2026-11-21 (GOLD 1m: freshness LIVE, market_status open=false). The terminal copied it. The platform may want its own freshness word to stop saying LIVE on a closed market; until then the terminal downgrades it.
- **Tested:** `scripts/check.sh` green; `scripts/verify_parity.py` against a local copy of platform 5.215 on a real Saturday: 975 checks, 0 FAIL, with three instruments on a closed market and BTC open. NOT tested: the plan counts with real numbers (the local copy's plan cells were not loaded), and anything on the box.
- **Not the terminal's to fix, and left alone on the platform's word:** stored candles of the four gap weeks one hour late; duplicates (never removed here); DXY still SERIES FAULT.

**2026-11-20 23:27 UTC — 2.11.0 IS ON THE BOX.** Pull request #21 (2.10.0 and 2.11.0) was merged on Shyam's word and he ran the update line. Witnessed by his paste of the whole run:

- **The box:** V2.11.0, build 79, commit `912897d`, PRODUCTION, PRODUCTION DATA, deployed 2026-11-20T23:27:45Z. Platform 5.211. Journal backed up before the rebuild (1,848 forecasts) and after (1,852); restore rehearsal all OK.
- **Acceptance on production: 3602 checks, 0 FAIL.** All three release gates PASS (gate 1: 1595 checks; gate 2: 158; gate 3: 15; per-instrument parity 1617). Seven chart-behaviour checks PASS.
- **AAPL and ANT have bars.** Both read AVAILABLE with closed candles on all seven timeframes (the platform prompt had said none were sent yet). 31 instruments are drawable.
- **Desk evidence on production:** compared on 31 instruments, 248 board cells; `lane-history-v2` on 76 lanes; 70 lanes with a v2 verdict; 8 stale lanes with a break word. So a lane holding a setup under v2 and a break word ARE now seen on production. NOT seen: a NOT LOADED YET cell, a board FAULT, a board NOT_AVAILABLE.
- **Outlook views on production:** Market Outlook compared on 31 of 31 instruments (DOWN 9, UP 4, NO CLEAR TREND 3, UNKNOWN 15); Call Ledger 3 calls, all PENDING, verdict "NO RESOLVED CALL YET"; Turning Point NO ROBUST EDGE, 15 cells. These compared the adapter's answers with the platform's. **The three tabs themselves have not been seen on production by eye or by picture:** `e2e/screenshots.mjs` takes no picture of them, and the tab checks in `e2e/workspace.mjs` ran on test data. Owed: Shyam's eye, and three pictures added to the screenshot run.
- **Two platform findings from this run — the platform window's, not the terminal's:**
  1. **SERIES FAULT on 13 instruments, not 4:** DXY, US100, US30, AUDUSD, EURUSD, GBPUSD, NZDUSD, USDCAD, USDCHF, USDJPY, LTC, SOL, XRP. The platform's notes of 2026-11-20 name four (US100, US30, EURUSD, USDJPY); its overview covers only the core assets, and this run asked every instrument. The terminal shows each as SERIES FAULT and reads nothing from it, which is correct.
  2. **Every history cell read STALE (248 of 248)** at about 23:30 UTC. STALE is a loaded state and the terminal shows the numbers with the platform's note. Shyam's screenshot at 23:48 UTC answers the worry: the note read "history cells computed 10 min ago … refreshed about every 10 minutes", so the refresh IS running. What is left is a question for the platform window, sent to it: whether STALE is the intended word at ten minutes when the refresh interval is also ten.
- **Seen by eye on production (Shyam's screenshot, ANT M15, 23:48 UTC):** AAPL and ANT under STOCKS with two decimals; the lane line "own history: UNKNOWN (n=0) · scalp-v1 × ANT × HH/HL-BUY — n=0, under 20; a single stock is never pooled with other assets"; the platform's cells note above the verdict board. The Toolbox was hidden in that picture, so the three new tabs are still unseen on production.
- **Sent to the other windows on 2026-11-20 (Shyam pastes them):** to the bot side — the ANT 15m chart loads about 100 bars against 500 asked for (was that backfill depth intended?), and the 13 faulted series as the scope of its depth probe; to the platform window — the 13 series faults, the STALE question, and ANT's Swing 4h lane holding a BUY LIMIT (TP1 114.68 against a price of 88.18) although CHANGELOG 5.211 says its 4h lane reads NO_HISTORY for weeks. None of the three is a terminal fault; none was answered when this was written.

**The text below was written before the merge and is kept for what it says about the build and how it was tested.**

**Added 2026-11-20 (late) — 2.10.0 and 2.11.0 BUILT in one pull request (#21).**

- **Witnessed on the box (Shyam's paste, 2026-11-20):** branch `claude/vibrant-albattani-kxhfwv`, head `954bae5`, `VERSION` 2.9.0; platform printing **5.211**. The box is one commit behind the branch (`c6daa1d`, a handoff text only).
- **2.10.0** (platform prompt §F): AAPL and ANT beside NVDA (stocks, two decimals; UNAVAILABLE until the bot side's reporter sends bars — it had sent none); a history cell that is not loaded reads NOT LOADED YET, never n=0, with the platform's `cells_note` above the verdict board; the lane-history rule name is printed from the payload (`lane-history-v2` since 5.211) and a cell under 20 prints the platform's `level` sentence.
- **2.11.0** (platform prompt §E): three Toolbox tabs — **Market Outlook**, **Call Ledger**, **Turning Point** — from the platform's three read routes of 5.210. Reshape only (`outlook.py`, `outlook-views-v1`); the tabs' laws are in `docs/DATA_CONTRACT.md`: HAS BEEN never WILL, UNKNOWN is not a direction, UNPROVEN stays uncoloured, nothing to press, a 404 reads NOT BUILT. Shyam did not choose where the views go; three Toolbox tabs were this window's proposal — ask him by eye after the deploy.
- **How it was tested, and what was not:** `scripts/check.sh` green. `scripts/verify_parity.py` was run against a LOCAL copy of SignalMesh at 5.211 (its own code, seeded candles, a read key): 896 checks, 0 FAIL, all gates PASS. That proves the two sides agree on the platform's real payload shapes. It is NOT production: nothing here has met the box's data. NOT LOADED YET, NOT BUILT, a lane holding a setup under v2 and a stale lane were exercised on test data only.
- **To repeat that local run** (it found nothing, but it is the only test that meets real platform code before a deploy): in a Sniper-System checkout build the test database as `tests/conftest.py` does, seed daily candles with `tests/test_market_outlook_5209._seed`, add an `ApiKey` row, start `uvicorn app.main:app`, start the adapter with `SMT_PROVIDER=signalmesh` pointing at it, and run `verify_parity.py`.
- **After the merge:** the update line, then read the version on screen, then by eye: the three tabs against `https://app.signalmesh.dev/market-outlook?symbol=GOLD`, `/analyst-ledger` and `/turning-points`. Then the platform window's waiting week (its prompt §D): the Call Ledger tab is where the system's calls can be read from the terminal.
- **Small things seen and left alone:** unavailable instruments (AAPL and ANT today) sit behind Market Watch's "show … instruments without stored candles" line, as NVDA-like symbols always have; the terminal still shows nothing of the platform's liquidity tier for a single stock, for NVDA either.

| Thing | State |
|---|---|
| On the box | **2.9.0**, build 74, commit `954bae5`, PRODUCTION DATA, deployed 2026-11-19 10:34 UTC — witnessed by Shyam's screenshot and his paste: "every step ended without a failure", "history check: all OK". Platform (`sabuj14eu/Sniper-System`, branch `claude/quirky-davinci-8wvfxd`, `/srv/brotherbot`) printed **5.203** on 2026-11-19 |
| Release gates (Shyam's, set on 2.7.0) | All three passed on production at 2.7.3, when he declared the then-current scope complete. Each later release ran the same acceptance: 2.8.0 found one fault (fixed in 2.8.1), 2.8.1 and 2.9.0 ended without a failure. The gate table of the 2.9.0 run itself was not pasted — only its last line |
| Studies on the chart | Journalled: daily forecast, Wolfe wave, Elliott setups (`elliott-setups-v2`). Context only: Fibonacci extension, anchored VWAP, volume profile, asset ranking. A read, not a signal and not recorded: **Chart read** (2.9.0). Platform evidence, reshaped only: desk lanes' own history, break word, verdict board (2.8.0) |
| Journal | 1,740 forecasts on 2026-11-19: 1,462 BACKFILL, 278 LIVE; 1,689 finished, 51 open. Elliott rows of 2.7.0's first method (`pattern-studies-v1`) are kept, apart. Every Gold / Silver group still has under 20 finished forecasts: every hit rate reads LUCK |
| Open pull requests of this work | None. #11 to #19 are merged (plus this handoff). (#1 to #3 are older and not this window's) |

**What 2.8.0 to 2.9.0 added (2026-11-19), all deployed:**

- **2.8.0 — the platform's desk evidence** (platform 5.202 / 5.203): a break word beside DATA_STALE, each lane's own history with both evidence verdicts, and the box "Evidence verdict — V1 beside V2". Reshape only (`desk-evidence-v1`); the terminal calculates none of it; PAPER evidence, never a signal. The job came from the platform window's prompt, `docs/NEXT_WINDOW_PROMPTS.md` §C in Sniper-System. On production it compared equal to the platform on all 29 instruments (232 board cells).
- **2.8.1 — a cache key.** The decision panel was served the market watch's 60-second engine snapshot (same key, two lifetimes), so it could lag the engine by a bar at a bar edge (US100, 7 FAIL on the 2.8.0 run). Market watch now has its own key. **Two readers with different lifetimes never share a cache key** — the same law as the discovery probes.
- **2.9.0 — Chart read** (`chartread.py`, chart-read-v1). Shyam asked for what his Metal Hunter indicator shows him on TradingView, "no need to make new signal, just show this on chart with on/off switch". One switch: swing labels (HH / HL / LH / LL), rejection and engulfing candles, and one table that gathers the Smart Money study, the daily forecast, the engine's bias and the newest signal, plus momentum, volatility, price zone, volume and a six-condition count per side with reasons. It is a read: not a signal, not recorded, not a port of the Pine script. He first asked for a "BUY/SELL condition detector" with stages (WATCH → READY → CONFIRMED) and then replaced that with this; the stages were NOT built.

**Small things Shyam has seen and not asked to change:** the study report stays folded if his browser remembered it folded, so a newly ticked study's table is hidden behind the ▸ at the bottom-left of the chart (he missed the Chart read table this way; opening it automatically when a study is ticked was offered, not answered). The candle-pattern thresholds are constants in `chartread.py`, not settings on screen.

**What was fixed after 2.7.0, and why it matters to the next change** (each was found by a check, not by eye):

- 2.7.1 — Elliott said "CONFIRMED" beside "1 of 4 impulse checks": pivots / count / trade setup are three separate lines; only a TRIGGERED wave-3 setup and a finished five are journalled; hit rates are split by method version.
- 2.7.2 — the terminal copied an engine READY even on candles that were not live: it now downgrades (never upgrades) to INVALIDATED. A dead upstream is named DISCONNECTED. Journal audit. `update.sh` runs every check even after one fails.
- 2.7.3 — a Wolfe wave's apex / expiry TIMES moved when the series crossed a daily break: they are bar counts, their clock times are estimates fixed at detection. **The seeded test series had no time gaps, so the tests could not see it; the recorded-history check on the box did.** Any new study needs a test on a series with gaps (`gapped()` in `tests/test_studies.py`).

**Not done, and whose it is:**

- Trading calendar and the late last bar before the daily break: SignalMesh side — written up for the platform window in `docs/PLATFORM_READ_ROUTES.md` §6 and §7. Until then the terminal writes "MARKET QUIET (inferred)" and never "MARKET CLOSED".
- Performance: a separate milestone (Shyam). Leave the terminal running; judge a module only from about 100 finished LIVE forecasts, never from BACKFILL alone.
- The asset ranking and the daily forecast do not mark a row whose instrument is not LIVE (low; not changed on Shyam's "no more changes").
- Chart read is verified on GOLD and SILVER (15m, 1h) only, and its definitions are the terminal's own; where Shyam's Pine has an exact rule he may want it ported — ask which rows matter before porting anything.
- Pattern studies are verified on GOLD and SILVER only. Feed-stale and disconnected are tested by simulation only. Layout persistence is tested on test data only.
- GitHub Actions did not start for about an hour on 2026-11-11 (runs sat queued with no job); it recovered by itself. If it happens again: wait, do not push empty commits.

How Shyam works (each line cost time):

- **He merges by word, and often pastes the update line before the merge.** `scripts/update.sh` now answers that in one second ("NOTHING NEW … the pull request is not merged yet"). Say plainly "reply merge #N". "Agreed", "complete or merge then give me the command" and "fix it and rerun" have been his go-ahead; a pasted terminal output alone has not — ask once, with one click.
- **The box only pulls.** No git beyond his own `git pull`, no credentials, never a password / token / key prompt. Tests enforce it for the box scripts.
- **The repository is public.** No production data in it, ever. Real-history checks run on the box and he pastes the summary.
- **One command block per step**; say how long it takes. The update line is `cd /srv/signalmesh-terminal && git pull && scripts/update.sh` — add `--history` only after a release that changes a study.
- **He wants evidence, not assurance:** PASS / FAIL / NOT TESTED per item, an untested thing never counted as a pass, production evidence told apart from test data. He reads the whole report.
- **"I want a reliable terminal, not a bigger terminal."** No new indicator, redesign or strategy change unless he asks in his own words.
- Token economy: act only when he writes; subscribe to a pull request only while its CI runs.

## 8. Paste this as the first message of a new terminal window

> You are continuing the SIGNALMESH TERMINAL for Shyam: repository `sabuj14eu/DESKTOPINTERFACE` (PUBLIC). Deployed branch `claude/vibrant-albattani-kxhfwv`, on the box at `/srv/signalmesh-terminal`, served at https://app.signalmesh.dev/terminal/. The toolbar says which version runs; a merged pull request is not a deployed release. The scope was declared complete at 2.7.3 after three production gates passed; 2.8.0 to 2.9.0 (desk evidence from the platform, a cache fix, and Chart read) were added on 2026-11-19 at Shyam's request and are deployed. Read, in this order: `docs/HANDOFF.md` (start with §7: the state, what is not done and whose it is, and how Shyam works), `docs/RELEASES.md` (2.7.0 to 2.9.0), `docs/FORECASTING_PLAN.md` (§5c), `docs/DATA_CONTRACT.md` (journal-v1, pattern-studies-v1, r-v1, desk-evidence-v1, outlook-views-v1, chart-read-v1), `docs/PLATFORM_READ_ROUTES.md` (§6, §7: what is asked of the SignalMesh side), then the code you touch. Laws: GET-only toward SignalMesh; nothing in Sniper-System, the MT5 reporter, Telegram or execution changes from this repository; studies are display only, no signal, no order; every entry / SL / TP is a HYPOTHETICAL ANALYSIS LEVEL; closed candles only, no lookahead, no repaint, proven by a prefix audit on seeded series WITH TIME GAPS in the tests and on recorded Gold / Silver on the box; missing or unclear is UNKNOWN / NOT AVAILABLE; a verdict is never upgraded and READY is never shown on data that is not live; the terminal never writes MARKET CLOSED without a calendar; confidence is UNKNOWN or the journal's measured rate with its sample size; the journal is append-only, the only thing the terminal writes, and a changed method never shares a hit rate with the one it replaced; the box only pulls and never asks for a credential; no production data in the repository; two readers with different lifetimes never share a cache key; what the platform sends is reshaped, never recalculated; Market Outlook says what price HAS done, never what it will do, and nothing in the three outlook tabs can be pressed; UNKNOWN is not a direction and UNPROVEN is never coloured; Chart read is a read, never a signal. LIVE BEFORE COMMAND: before giving any update line, ask Shyam for a read-only paste of the box's branch, head and version, and read it back. Workflow: work on a `claude/<name>` branch cut from the deployed branch; `scripts/check.sh` before every push; bump `VERSION` and `docs/RELEASES.md` together; draft pull request into the deployed branch; when CI is green tell Shyam and wait for his word; after the merge give ONE command block: `cd /srv/signalmesh-terminal && git pull && scripts/update.sh` (add `--history` after a release that changes a study). It ends with a RELEASE GATES table, a NOT TESTED list and a matrix: report them as they are. Do nothing unless Shyam has written, and add no feature he did not ask for. First reply, in five short lines: which version is on the box and how you know; what is on the chart today and which of it is journalled, which is context, which is a read and which is the platform's own evidence; what is still open and whose it is; what stays UNKNOWN (performance, until the journal has LIVE evidence); and the one thing you need from Shyam next. Then wait.
