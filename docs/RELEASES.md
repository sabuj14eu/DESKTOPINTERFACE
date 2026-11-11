# SignalMesh Terminal — release history

The newest release is first. Its number is the one in `VERSION`; a test fails if the two differ
(`adapter/tests/test_build_identity.py`). The terminal shows this number together with the build number,
git commit, environment and deployment time, all read from the build itself — see "Version identification"
in `README.md`. The same history is shown inside the terminal: click the version in the toolbar.

## 2.7.1 — 2026-11-11

Verification release after Shyam's review of 2.7.0 on production. No new study, no new feature: fixes, clearer words, and tests.

### Changes
- **Elliott: three separate lines instead of one word.** PIVOTS (confirmed = final), COUNT (PARTIAL until five waves have printed and all four impulse rules have passed, then COMPLETE), TRADE SETUP (none, triggered, or recorded). A partial count is never called confirmed.
- **Elliott in the Forecast Journal records trade setups only** (method `elliott-setups-v2`): a wave-3 setup on the bar that TRIGGERS it — the first close beyond the wave-1 end while the 1-2 count is alive — and a finished five-wave impulse. A 1-2 count that has not triggered, the wave-4 pullback and the wave-5 "do not add late" stage are not setups and are not recorded.
- **A changed method never shares a hit rate with the one it replaced.** Hit rates are now grouped by method version as well. The Elliott rows 2.7.0 recorded (stages, including untriggered ones) stay in the journal — it is append-only — under their own method name, apart from the new ones.
- **The pattern report says when its data is not live**: a red line "DATA STALE — the newest closed bar ended …; this is the last known picture, not a live market".
- **Market Watch says why a price is not live**: MARKET QUIET (this instrument is silent while the same feed is delivering others: closed or on its daily break — inferred, the terminal has no trading calendar), FEED STALE (nothing is updating: the collector or its connection), DISCONNECTED (the read failed). The engine's own freshness word is unchanged beside it.
- **Acceptance checks GOLD and SILVER on 15m, 1h, 4h and 1d** for all five studies, checks the Wolfe / Elliott journal rows, and ends with a RELEASE GATES table: PASS / FAIL per gate and a NOT TESTED list. An untested thing is listed, never counted as a pass.

### Fixed bugs
- 2.7.0 showed "BEAR WAVE 3 setup · CONFIRMED" beside "1 of 4 impulse checks passed" (GOLD 15m). "Confirmed" there meant only "price closed beyond the wave-1 end"; it read as a confirmed Elliott count, which it was not.
- 2.7.0 recorded Elliott stages in the journal on the bar the stage appeared, whether or not the setup had triggered, and recorded the wave-5 stage that the study itself labels "do not add late".

### Outstanding issues
- **MARKET CLOSED is inferred, not known.** SignalMesh gives the terminal no trading hours. Telling a closed market from a failed collector with certainty needs the platform to expose each instrument's session hours — a SignalMesh change, not made here. DELAYED is not a separate state.
- **No Wolfe or Elliott forecast has yet been recorded LIVE and scored to its end on production.** The rows so far are BACKFILL. This needs time to pass.
- Journal restore from a backup file has not been rehearsed.
- Pattern studies are checked on GOLD and SILVER only. They draw on every instrument, but no other instrument's calculation has been verified.
- Chart interaction (zoom, scroll, crosshair, full screen, layout) is tested by the automated browser run on test data, not on production.

## 2.7.0 — 2026-11-11

### Changes
- **Five pattern studies in the chart's "indicators" menu**, under "Pattern studies" (steps 3, 4 and 5 of the forecasting plan in one release, on Shyam's word). Each is its own ON/OFF switch, off by default, remembered in the workspace. Each draws on the chart and has its own table in the report on the chart.
- **Fibonacci extension**: the last three confirmed swings are A, B, C; target levels 0.618, 1, 1.272, 1.618, 2 and 2.618 of A-B from C. The table says which levels are reached and which is next; the set reads INVALIDATED when a bar closes beyond C.
- **Anchored VWAP**: three lines — from the highest confirmed swing high, from the lowest confirmed swing low, and from the start of the broker day. The table gives each VWAP, its one-deviation band, and whether price is above or below it and by how much.
- **Wolfe wave**: the five-point wedge with points 1 to 5, lines 1-3, 2-4 and the 1-4 target line to the EPA; entry, SL, TP1, TP2, R:R and expiry in the table. Rules and thresholds start from the Metal Hunter V15 Pine script. Added by the terminal: a wedge with only four points reads **DEVELOPING — not confirmed**, shows where point 5 has to print, and carries no entry, stop or target.
- **Elliott wave**: the impulse count on confirmed pivots, stage by stage (wave 3 setup, wave 4 pullback, wave 5 running, five waves done), with invalidation and two targets. Rules start from the MH15 PLUS Pine script. Added by the terminal: an **alternative count** in the other direction when the same rules allow one, wave ratios, and A / B / C labels after a finished five. No valid count reads **UNKNOWN**.
- **Volume profile**: activity by price over the loaded bars, drawn as bars on the right of the chart, with POC, value area high and low, and high / low activity nodes. It is **MT5 tick volume, not traded volume**, and says so on the chart and in the table.
- **Wolfe and Elliott are recorded in the Forecast Journal** (Shyam, before the merge): every CONFIRMED Wolfe wave and every VALID Elliott stage that names an entry, a stop and two targets is recorded by the terminal's own recorder at each closed bar, on 15m, 1h and 4h, for every instrument — whether or not anyone is looking at the chart. Recorded: direction, entry, SL, TP1, TP2, invalidation, timeframe, the bar and time it was made, expiry. The scorer then marks the outcome from closed bars. Same journal, same rules: append-only, nothing edited, no lookahead. Elliott stages recorded: wave 3 setup, wave 5 running, five waves done (a trade against the impulse). 
- **Never recorded as a forecast**: a developing Wolfe (four points), an unknown, failed or alternative Elliott count, the Elliott wave-4 "wait for the pullback" stage (it names no entry), a setup whose entry is not between its stop and first target, and Fibonacci extension, anchored VWAP and the volume profile — those three stay context tools with no hit rate.
- **Result in R** in the Forecast Journal: a new R column per forecast and an average R per module / symbol / timeframe. TP2 reached = its R:R, TP1 reached = its R:R, stop first = −1R; expired or never entered = not measured. It is calculated from the recorded events when the page is read; nothing already recorded is changed.
- The Wolfe and Elliott tables on the chart show their record for that symbol and timeframe; confidence reads UNKNOWN until 20 forecasts are finished.
- **`scripts/update.sh`: the update checks first.** It compares what `git pull` fetched with what the running terminal was built from. Nothing new = it says so and stops in a second, with no rebuild, no restart and no ten-minute acceptance. The update line is now `git pull && scripts/update.sh`.
- Method panel (ⓘ patterns): how each study is calculated, from which closed bars, when, and what is Pine's and what is the terminal's own.
- Acceptance looks up every pivot the studies use in the engine's own closed candles and redoes the anchored VWAP and volume sums from them.
- `scripts/export_history.sh` also runs the no-lookahead check of the five studies and of the two journal modules on the recorded Gold and Silver bars. It is needed once after a release that changes a study, not on every update: `scripts/update.sh --history`.

### Fixed bugs
- A unit test of the daily forecast failed between 22:00 and 22:15 UTC, the first quarter-hour of the test data's broker day, when no bar of the new day has closed. The study was right to say NOT AVAILABLE; the test now expects exactly that in that window.
- Acceptance reported `instrument US500 1m availability: engine=True terminal=False` once on 2.5.1, right after a restart (it did not show on the 2.6.0 run: 2044 checks, 0 FAIL). Cause found in the code: when one read of SignalMesh failed or timed out while the instrument list was being built, that timeframe was listed as "not stored" and the whole list was kept for 5 minutes. A failed read is not "no candles": the list now says it is incomplete (`complete`, `failed_reads` in `/api/terminal/instruments`), is kept for 15 seconds only, and the next read asks SignalMesh again for just the missing parts. Acceptance waits for the complete list. Not yet confirmed on the box that this was the cause of that one FAIL.

### Outstanding issues
- **Not yet seen on production data.** Checked on test data and seeded series only.
- **The first Wolfe and Elliott rows will be BACKFILL.** On its first pass the recorder reads the stored bars and records the setups already in them; they are labelled BACKFILL and their hit rate is shown apart from LIVE, as for the daily forecast. Setups made in the first 120 loaded bars are not recorded (the walk has not settled there).
- **Elliott's entry and horizon are the terminal's own rule** (Pine names neither): entry at the close of the bar that made the stage, horizon twice the bars the count has taken. The journal will show whether they are any good.
- **R is a simple measure**: the first target counts as banked, and a forecast that expires after entry has no R because the scorer records no exit price at expiry.
- The recorder now also reads 1h and 4h bars of every instrument, every five minutes — about 60 more read-only requests to SignalMesh per five minutes.
- **A pattern is an interpretation.** Pivots are confirmed 5 (Fibonacci, VWAP anchors), 8 (Elliott) or 10 (Wolfe) bars late; the newest pivot can be replaced by a more extreme one, which makes a new entry and never edits an old one.
- **Volume is tick volume.** Anchored VWAP and the volume profile show activity, not traded size; on instruments without tick volume they read NOT AVAILABLE.
- The studies use the chart's own timeframe and the 500 newest closed bars; a separate analysis timeframe per study, bullish-only / bearish-only filters and history of finished patterns on the chart are not built.
- Elliott's alternative count is a second reading of the same pivots, not a ranked probability. Wave extensions are shown as ratios only.
- GitHub's automatic check did not start on any commit since 2.6.0's feature commit; the full check passed in the development sandbox.

## 2.6.0 — 2026-11-11

### Changes
- **Forecasting studies in the chart's "indicators" menu** (step 2 of the forecasting plan). Click *indicators*: the list now has a "Forecasting studies" section. Each entry is its own ON/OFF switch, off by default, remembered in the workspace.
- **Daily forecast — top / bottom (ADR)**: two dashed lines on the chart, today's projected top and bottom, ported from the Metal Hunter V15 Pine script. ADR is the mean range of the last 14 completed days; top = today's low + ADR, bottom = today's high − ADR, snapped to a nearby 4h swing or the previous day's high / low. Options: top + bottom, top only, bottom only, and history (the finished days' lines).
- **Asset ranking table — room left today**: every instrument SignalMesh stores, ranked like the MH15 PLUS rotation ladder: rank, asset, ADR used %, day move in % of ADR, state (FRESH / MOVING UP / MOVING DOWN / NEAR FULL / DONE), what to do, score, and a GO TRADE line naming the asset with most room. Click a row to open that chart.
- **A read-only report on the chart**, like an indicator's table: forecast top and bottom with how they were derived, ADR, used %, status, room left, confidence, and outlooks for the day, week, month and 3 months (6 months reads UNKNOWN: not enough stored history). It folds away; the lines stay.
- **A measurable scenario**: when the day's range first reaches ADR on a closed 15m bar, the report shows one fade scenario with entry, SL, TP1, TP2, R:R, invalidation and horizon, each labelled HYPOTHETICAL ANALYSIS LEVEL, and it is recorded in the Forecast Journal and scored. This is the first study that writes to the journal.
- **Method panel** (ⓘ method): how each value is calculated, from which closed bars, and when.
- Confidence reads UNKNOWN until the journal holds 20 scored forecasts for that symbol; then the measured hit rate with its sample size.
- The price axis makes room for the two forecast lines while the study is on.
- Acceptance recomputes ADR and today's high / low from the engine's own closed candles and compares them with the study.

### Fixed bugs
- Acceptance reported 28 FAIL on 2.5.1 (ETH, LTC, SOL, XRP: `market.last_bar_ts engine=20:00 terminal=19:45` and the values measured on that bar). Cause: a 15m bar closed between the script's read of the engine and its read of the terminal, which reuses one upstream answer for 15 seconds. The terminal was showing the engine's own values from seconds earlier, not wrong ones. The script now reads a symbol that differs a second time, both sides, after the cache lifetime, and fails only if the difference survives (the same rule 2.2.1 introduced for signals).
- The indicators menu now closes with Esc.

### Outstanding issues
- **Not yet seen on production data.** Checked on test data and seeded series only; the recorded Gold / Silver check runs on the box with `scripts/export_history.sh`.
- **The day is the broker's (the stored daily bars open about 22:00 UTC), not TradingView's 17:00 New York day.** ADR, "today" and the previous day can differ from the Pine script by those hours.
- **Found in the Pine script:** its "top done" and "bottom done" tests are the same condition, so its "TOP IN" and "BOTTOM IN" texts can never appear — it always says "BOTH SIDES DONE". The terminal keeps Pine's status and adds which extreme completed the range. The Pine file is unchanged.
- **The fade scenario's stop and targets are the terminal's own rule** (Pine names none): stop a quarter ADR beyond the day's extreme, targets a quarter and a half ADR back, expiry at the end of the broker day. They exist so the statement can be measured; they are not advice.
- Pine's event mode (hand-set event clock) is not ported: a full day reads DONE, never EXPANSION.
- The ranking is not a forecast and is not journalled. Sessions use fixed New York hours.
- On the two days a year the broker's day start shifts by an hour, a day's scenario may be recorded a second time as BACKFILL.
- The first pass after deployment records the scenarios of the days already in the stored 15m bars as BACKFILL; LIVE records start with the next full day.
- Fibonacci extensions, anchored VWAP, Wolfe wave, Elliott wave and volume profile are steps 3 to 5.

## 2.5.1 — 2026-11-11

### Changes
- `scripts/export_history.sh` now only writes the Gold and Silver candle files into the git-ignored `history-export/` folder on the box, runs the scorer's no-lookahead check on those real bars inside the terminal container, and prints a short summary to paste back. The files never leave the box.
- New rule, enforced by a test: the box scripts never use git, never contact GitHub and never ask for a password, token or key. The box only pulls.
- New rule, enforced by a test: no production data (candle history, journal, backups) is ever committed — this repository is public. The recorded-history check therefore runs on the box, not in the repository's test suite.

### Fixed bugs
- 2.5.0's export script tried to send the exported files to GitHub from the box and asked for a GitHub password. It was cancelled before anything was sent; nothing was committed or pushed. That step is removed.

### Outstanding issues
- The journal is empty on production until the first forecasting study is released (step 2); every hit rate and confidence reads UNKNOWN.
- The export and its on-box check have not been run on the box yet.
- Unchanged from 2.5.0 otherwise.

## 2.5.0 — 2026-11-11

### Changes
- **Forecast Journal** — a new Toolbox tab and the terminal's first own store. Every forecast a terminal study makes is recorded once, at the closed bar it was made on, with its entry zone, stop-loss, TP1, TP2, invalidation and expiry already fixed. The record is append-only: the database itself refuses every edit and every deletion.
- **Scoring from closed candles only** (score-v1): each forecast is later marked TP1 hit, TP2 hit, SL hit, invalidated or expired, with the bar that decided it. A bar that touches both the stop and a target is scored as the stop.
- **Hit rates with the sample size**, separate per module, symbol and timeframe (Gold and Silver are never pooled): under 20 finished forecasts is labelled LUCK, 20–99 SMALL SAMPLE, 100 or more JUDGEABLE. Forecasts recorded live and forecasts calculated later from stored bars (BACKFILL) are counted apart.
- **Recording happens on the server** at every closed bar, for every instrument, whether or not its chart is open — losses exactly like wins.
- The journal is one file on the terminal container's own Docker volume. It is not SignalMesh's database and nothing is written to SignalMesh. It survives every redeploy and is copied to `backups/` on the box before each one (`scripts/journal_backup.sh`, run by `scripts/setup.sh`).
- `scripts/export_history.sh`: a read-only export of closed Gold and Silver candles (M15, H1, H4, D1) for the tests, with account numbers removed.
- `docs/FORECASTING_PLAN.md`: the plan for the forecasting studies and the decisions taken.

### Fixed bugs
- None.

### Outstanding issues
- **The journal is empty on production and stays empty until the first forecasting study is released (step 2).** No study records yet, so every hit rate and every confidence reads UNKNOWN. The scorer has been checked on test data only.
- The scorer's no-lookahead test has run on seeded series only. Its run on recorded Gold and Silver history waits for `scripts/export_history.sh` to be run on the box.
- Backups stay on the box; copying them elsewhere is manual.
- If the terminal is stopped for longer than SignalMesh's stored history of a timeframe reaches back, an open forecast from before the gap cannot be scored and stays open, labelled as not covered.
- Unchanged from 2.4.0: Smart Money Concepts not adjustable; DEMO / LIVE, used margin and margin level wait for platform change B.

## 2.4.0 — 2026-11-11

### Changes
- **Smart Money Concepts overlays on the chart**, each with its own ON/OFF switch and its own analysis timeframe (M5, M15, M30, H1, H4, D1, W1 — the chart's own or a higher one): Support & Resistance, Fair Value Gaps, Break of Structure, Change of Character, Order Blocks, Liquidity (buy-side / sell-side, equal highs and lows, previous day, week and session extremes, sweeps), Inducement.
- Toolbar "SMART MONEY CONCEPTS": show all, hide all, reset, bullish only / bearish only, history (resolved structures), zone opacity, and a method panel listing how each overlay is calculated, from which closed bars, and when. Choices are remembered.
- Every overlay carries its timeframe label and its state: FVG fresh / partly mitigated / mitigated; order block fresh / tested / invalidated with strength in ATR; liquidity unswept / swept (wick) / broken (close); BOS and CHoCH confirmed, with the next unconfirmed level dotted; internal structure marked `i`.
- These are the terminal's own display-only studies (smc-v1), calculated from SignalMesh's stored closed candles. They are not SignalMesh engine output and not the Pine sensor's structure, and they change no recommendation, entry, stop-loss, take-profit, confidence, order or statistic.

### Fixed bugs
- None.

### Outstanding issues
- Not yet seen on production data; the overlays have been checked on test data and seeded random series only.
- Weekly structures are built from closed daily bars (SignalMesh stores no weekly bars). A timeframe SignalMesh does not store for a symbol shows no overlay and says so.
- Swing detection uses fixed lengths (external 5 bars, internal 2); they are not adjustable yet.
- S/R zones and equal-high / equal-low grouping are re-clustered at each bar close from confirmed swings; the swings, breaks, gaps and blocks themselves do not repaint (tested).
- DEMO / LIVE, used margin and margin level still wait for platform change B.

## 2.3.0 — 2026-11-11

### Changes
- **The chart now moves between bar closes.** The bar that is still forming is drawn after the newest closed bar and refreshed every 2 seconds, with a live price in the toolbar. Source 1: SignalMesh's own live chart feed (the bot box bridge behind `/chart/candles.json`, forming bar plus bid/ask), read with your own SignalMesh login. Source 2, when that feed is not LIVE: the forming bar is built from stored closed 1m bars and moves once a minute. The chart header says which source is in use, or why there is none.
- The forming bar is display only: a lighter-coloured bar, switchable with the "live bar" box, never part of the closed series, the indicators, the decision, the levels or acceptance.

### Fixed bugs
- None beyond 2.2.1.

### Outstanding issues
- Not yet seen in production: whether the live bridge answers LIVE on the box, and how it compares with MT5 side by side.
- With the bridge the bar updates every 2 seconds, not tick by tick; without it, once a minute. MT5's own tick speed needs a streaming quote feed, which SignalMesh does not have.
- No live bar through the operator key (acceptance runs without a browser login, so it reports NO_SESSION for the live feed).
- Separate accounts and signal-to-trade links wait for platform 5.201; DEMO / LIVE, used margin and margin level wait for platform change B.

## 2.2.1 — 2026-11-11

### Changes
- Signal information understands the statuses `closed` and `cancelled` (SignalMesh's own words): a closed signal reads "SignalMesh reports CLOSED — no broker trade is linked", with stages C and E marked REPORTED BY SIGNALMESH, never as a broker fact.

### Fixed bugs
- Acceptance reported 2 FAIL on the 2.2.0 deployment (`signal ….status: engine='closed' terminal='executed'`). Cause: two signals changed status between the script's read of the engine and its read of the terminal, which reuses one upstream answer for 15 seconds. The terminal was showing the engine's value from seconds earlier, not a wrong one. The script now re-reads both sides after the cache lifetime when a signal differs and fails only if the difference survives.

### Outstanding issues
- Unchanged from 2.2.0.

## 2.2.0 — 2026-11-11

### Changes
- Decision panel: **Latest brain plan** — the same plan the SignalMesh /brain-view page shows (newest pending / approved / executed signal for the symbol): direction, grade, Entry, SL, TP1, TP2, signal id, origin, timeframe, age, LIVE or STALE. Click the id for the full signal information.
- Decision panel: **Desk lanes** — Scalp, Intraday, Session and Swing from the SignalMesh /desk page, reduced to the plan: order type and Entry / SL / TP1 / TP2, or what blocks the lane. Marked PAPER.

### Fixed bugs
- None.

### Outstanding issues
- The brain plan's age is counted from when SignalMesh stored the signal; the /brain-view page counts from the sensor's own fire time, which the read API does not return, so the two ages can differ.
- Separate accounts and signal-to-trade links wait for platform change A; DEMO / LIVE, used margin and margin level wait for platform change B.
- Balance, equity, positions and orders have not been compared with the MT5 terminal by a person.

## 2.1.1 — 2026-11-11

### Changes
- Narrow desktop windows: the side panels give way so the chart keeps its room, and the structure badge and legend step aside when the chart is narrow.
- Production verification of 2.1.0 recorded (see `docs/HANDOFF.md` §4): deployed as build 33, commit 096b715; acceptance 2025 checks, 0 FAIL; screenshots taken on the box.

### Fixed bugs
- The account menu marked both "MT5 Demo" and "MT5 Live" as connected when SignalMesh does not say which an account is. Neither is marked now, and the menu says the type is unknown.

### Outstanding issues
- Production confirmed: SignalMesh has no per-account read route (404), and two MT5 accounts report, so the terminal shows one COMBINED total. Separate accounts need platform change A.
- Production confirmed: trade rows carry no ticket, account or signal id, so no signal can be tied to its broker trade. Needs platform change A.
- DEMO / LIVE, used margin and margin level are not stored by SignalMesh: NOT AVAILABLE until platform change B is approved.
- Balance, equity, positions and orders have not been compared with the MT5 terminal by a person (and cannot be, per account, while the total is combined).

## 2.1.0 — 2026-11-11

### Changes
- Version identification in the toolbar and status bar: `SIGNALMESH TERMINAL | V2.1.0`, build number, git commit, environment (PRODUCTION / STAGING / LOCAL), data kind, build time and deployment time. Click it for the full build details and this history.
- The build identity is computed from the git checkout while the image is built; nothing is typed by hand. The browser bundle carries its own copy and warns if it differs from the server's.
- `scripts/screenshots.sh`: takes the standard screenshot set from the running terminal itself (desktop, full-screen chart, Account Information, Active Signals, Trade History). Every screenshot shows the version, commit, environment and data kind in the toolbar.
- Lifecycle wording: B1 is the engine council's approval; B2 is your own order approval.
- `docs/PLATFORM_READ_ROUTES.md`: what SignalMesh 5.200 stores and what its read API returns, with the proposed read-only platform change.

### Fixed bugs
- Open positions and pending orders are asked for by status, so an old position that is still open cannot fall off the newest-200 journal list.

### Outstanding issues
- Carried into 2.1.1 (deployed and verified in production on 2026-11-11, build 33, commit 096b715).
- SignalMesh 5.200 has no per-account read route: the terminal shows the portfolio total (COMBINED when several accounts report). Needs platform change A.
- DEMO / LIVE, used margin and margin level are not stored by SignalMesh: NOT AVAILABLE until platform change B is approved.
- A signal cannot be tied to its broker trade until `GET /api/v1/trades` returns the signal id (platform change A).
- Balance, equity, positions and orders have not been compared with the MT5 terminal by a person.

## 2.0.0 — 2026-11-10

### Changes
- Flexible workspace: Market Watch, Decision panel and Toolbox hide, show and resize; full-screen chart; layout saved in the browser; Reset layout.
- MT5-style look: M1…D1 buttons, Toolbox tabs along the bottom edge, status bar.
- Phone layout with a bottom navigation bar.
- Chart: scale and scroll controls, fit all, 300/500/1000 bars, UTC bar timestamps, clickable signal markers, indicator slot (two moving averages, off by default).
- Signal information: origin field by field, validation, invalidation, five lifecycle stages.
- Account selector, Account Information, Open Positions, Pending Orders.
- Ten Toolbox tabs; SignalMesh recommendations kept apart from broker records.
- Execution adapters for MT5 and cTrader prepared and disabled.

### Fixed bugs
- None (first V2 release).

### Outstanding issues
- Never deployed on its own; superseded by 2.1.0.

## 1.0.0 — 2026-11-10

### Changes
- First terminal: read-only adapter, Market Watch, chart, SignalMesh decision panel, seven bottom tabs, automatic instrument discovery, same login as SignalMesh, acceptance script.

### Fixed bugs
- See `docs/HANDOFF.md` §5 (the laws each cost a user-visible fault).

### Outstanding issues
- Fixed-width dashboard layout; no signal origin view; no account panel; no version shown.
