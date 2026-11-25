# SignalMesh Terminal — release history

The newest release is first. Its number is the one in `VERSION`; a test fails if the two differ
(`adapter/tests/test_build_identity.py`). The terminal shows this number together with the build number,
git commit, environment and deployment time, all read from the build itself — see "Version identification"
in `README.md`. The same history is shown inside the terminal: click the version in the toolbar.

## 2.13.3 — 2026-11-25

Two places where the screen made a sentence out of silence. One was found while answering SignalMesh's question about a slow route; the other Shyam saw himself on US10Y.

### Changes
- **A new word in the Market Watch: NO NEW BARS.** When an instrument's newest bar is more than 7 days old, the row reads "NO NEW BARS · old price, not live". Seven days is the terminal's own rule: longer than any weekend or holiday, far shorter than a series that has stopped. The tooltip gives the number of days and the date of the last bar.
- **The line under a Market Watch price no longer makes the list wide.** "MARKET QUIET (inferred) · last price, not live" and the MARKET CLOSED line now wrap inside their column. Measured in the test build: the list was 476 px wide with the quiet line, and is 371 px now — the same as with no such line.
- **The box's check reads both.** Acceptance checks that a row older than 7 days reads NO NEW BARS and no other row does, and prints how the terminal's own desk reads ended (OK or NOT READ) for every instrument.

### Fixed bugs
- **US10Y read "MARKET QUIET" every day. It is not quiet: nothing sends it.** SignalMesh retired US10Y on 27 August 2026 (the broker's contract ended with no successor), so its last bar is from that day and the engine calls it STALE — correctly. The terminal then guessed "the market is on a break", because other instruments were live. On a weekend it would have said "MARKET CLOSED · reopens in …" for it. Both are wrong for a series that has been silent for three months, and both are gone for it.
- **A desk that could not be read was shown as a desk that found nothing.** When SignalMesh's desk answer did not arrive (the terminal waits 20 seconds), the chart's foot line read "no actionable structure → NO SETUP", the Validation line read "NO SETUP" and the Desk lanes box read "the desk returned no lanes". Those are sentences about the market, made from a read that failed. They now read "the desk could not be read from SignalMesh — nothing is said about the market → NOT AVAILABLE" and "NOT READ", with the read's own failure word. The engine's verdict, levels and BUY / SELL states beside them come from another read and are unchanged — a test compares them one by one.

### Outstanding issues
- **The terminal cannot say RETIRED.** SignalMesh records a retirement in its own engineering file; its read API does not send it. Until it does, the terminal can only say how long a series has been silent. Asked of the platform window in `docs/MESSAGE_TO_PLATFORM_2026-11-25.md`.
- **US10Y stays in the list.** Hiding it is possible once SignalMesh sends the retirement, on Shyam's word.
- **The Market Watch is still a little wider than its panel at the default width** (371 px in a 300 px panel in the test build): the BUY / SELL column is reached by dragging the border or scrolling. It was so before this release; not changed here.
- **While the desk is slow the Decision panel refreshes slowly**, because it waits for the desk before it shows the engine's verdict (up to 20 seconds per refresh). Not changed here: SignalMesh asked that no timeout be moved until it has measured its own repair.
- **NOT READ has not been seen on production.** It is produced and tested with a test adapter; the box's check prints whether any desk read failed during its run.
- Everything listed under 2.7.1 to 2.13.2 still applies.

## 2.13.2 — 2026-11-22

After the first 2.13.1 run on production: 4296 checks, 2 FAIL, both in the new Limit Checklist check (DOT and OIL). Everything else passed; the terminal itself was running normally.

### Changes
- **The terminal's own series check now also covers short series.** It used to say "too few bars" before it looked for doubled bars, so VIX and ANT were not checked. It now looks for doubled bars first.
- **A trade's sender named only by its route is shown as "route …"** instead of "not stated". SignalMesh now sends a sender on trades, and some rows carry a route with no sensor or engine.

### Fixed bugs
- **The two FAIL lines were a fault in the new acceptance check, not in what the screen shows.** The check required TP1 to be below the price now (for a sell). On DOT and OIL price was sitting on a support, so "just above the support" was a little over the current price. That is still a target once the limit above has filled. The check now measures from the entry, as the checklist does.
- **A target that is not beyond the entry can no longer read as a normal target:** step 5 then reads FAIL with the reason. It did not happen in that run; the study now refuses it by rule.

### Outstanding issues
- **US10Y reads SERIES FAULT in the terminal's own check** (about a hundred places with two daily bars in one slot). SignalMesh already says US10Y holds two instruments under one name; this is the same fact seen independently. Every other daily and 4h series read clean in the newest 1000 daily and 500 4h bars.
- Everything listed under 2.7.1 to 2.13.1 still applies.

## 2.13.1 — 2026-11-22

### Changes
- **The box's check now runs the Limit Checklist on every instrument.** It was built in 2.13.0 and had only met test data. Acceptance now reads it for all instruments on real bars and checks its own arithmetic: seven steps, the limit inside its zone, the stop beyond it, the targets on the right side of price, the reward equal to distance over risk, and never "CHECKLIST HOLDS" beside a step that does not hold.
- **The terminal's own series check, printed once per run.** SignalMesh and the bot side asked for an independent witness of the candle repair. The checklist refuses any daily or 4h series with two bars in one slot, by its own rule (not SignalMesh's). Acceptance now prints which instruments it refuses, or "no daily or 4h series faults".

### Fixed bugs
- None.

### Outstanding issues
- **The terminal's series check reads the newest 1000 daily and 500 4h bars only**, not the whole stored history, and not 1h or smaller timeframes. It can confirm the recent part of a repair, not all of it.
- GOLD 4h now reaches back to 1998 (it began in 2004). No terminal study counts bars from the first one — each reads the newest bars — so nothing here moved.
- Everything listed under 2.7.1 to 2.13.0 still applies.

## 2.13.0 — 2026-11-22

A new study Shyam asked for: his seven-step checklist for a pending limit order, shown for the instrument on the chart. "Show only, also this is not a trade signal."

### Changes
- **A new tab in the Toolbox: "Limit Checklist".** It runs the seven steps on the stored closed daily and 4h bars and prints one line per step: PASS (the step holds), WAIT (not yet), FAIL (the checklist says skip), or BY HAND for the two steps a person applies. It works for a pending sell limit in a downtrend and, mirrored, a buy limit in an uptrend.
  1. **Trend (daily):** price against the 50, 100 and 200-day averages, and the last daily swing high and low. A mixed picture reads NO TRADE and nothing else is calculated.
  2. **Bounce (4h):** how far price has come back against the trend, against the checklist's 3–8%.
  3. **Entry zone:** where two or more different kinds of level overlap — a swing high, a broken support, the 50 or 100-day average, a round number, a pivot. The limit is the middle of the zone and must be at least 1R from price.
  4. **Stop:** beyond the furthest level of the zone plus 0.4%. If an average or another level sits just past it, the stop is moved beyond that too, and the line says which — the lesson of 62,000 under the average at 62,102.
  5. **Targets:** TP1 just before the nearest support, TP2 just before the next. Under 1:2 on TP2 the step reads FAIL: skip the trade.
  6. **Size:** the risk per unit and the 1% rule. Lots are NOT AVAILABLE: the terminal does not know the broker's contract size.
  7. **Cancel conditions:** the two rules, with the stop price in them.
- **The levels it gives are shown as numbers** — entry, stop, TP1, TP2, the reward of each — every one labelled a HYPOTHETICAL ANALYSIS LEVEL.
- **Three more averages for the chart:** EMA 20, EMA 100 and EMA 200 join SMA 20 and EMA 50 in the indicators menu. To see the same "day" averages the checklist uses, switch the chart to D1.
- **It is a display, not a signal.** Nothing in the tab can be pressed. It is not recorded in the Forecast Journal, is not SignalMesh engine output, changes no decision and places no order.
- **It refuses rather than guesses:** fewer than 200 daily bars (ANT, for weeks) or a daily series with two bars on one day reads NOT AVAILABLE or SERIES FAULT, with the reason. On a closed market it says MARKET CLOSED above the last stored picture.

### Fixed bugs
- None.

### Outstanding issues
- **It was not tested against results.** It is the checklist made visible. Whether trades taken this way win is not known here, and the tab says so.
- **The 3–8% bounce was written for crypto-sized moves.** A currency pair may never reach it, so step 2 will often read WAIT there. That is the checklist's own number, not changed.
- **Some choices are the terminal's and can be argued with:** levels "overlap" within one 4h ATR; the buffer is 0.4% (the checklist says 0.3–0.5%); "just above" a support is a tenth of a 4h ATR; a round number is the next multiple of one tenth of the price's power of ten (60,143 → 61,000). They are listed under "how each step is read".
- **Nothing is drawn on the chart for it yet** (zone, entry, stop, targets): numbers only.
- **A daily or 4h series with two bars in one slot reads SERIES FAULT here**, by the terminal's own check. (Corrected 22 November: this line first said GOLD, SILVER and others still read it. SignalMesh reports that it repaired their daily and 4h series on 22 November and that no daily series faults now. The terminal's own check on the box has not confirmed that yet.)
- The averages on the chart are computed from the candles loaded (500 by default), so the 200 line starts 200 bars in.
- Not yet seen on production data.
- Everything listed under 2.7.1 to 2.12.1 still applies.

## 2.12.1 — 2026-11-21

The bot side armed a new v7 engine on the demo account: sensor LANELIVE, engine `lane-live-v3`. It asked that the terminal names the sender on its trades.

### Changes
- **A "Sender" column** in Trade History, Open Positions and Pending Orders. It prints the sensor and its engine — for example **LANELIVE · lane-live-v3** — exactly as SignalMesh names them on the trade row.
- **Today the column reads "not stated" for every v7 trade, the new engine included.** SignalMesh's trade rows carry no sender yet, for any v7 engine. SignalMesh offered to add one (`sender`, from its ticket join); the terminal is built for exactly that shape, so the names appear by themselves the day SignalMesh sends them, with no further terminal release.
- **Nothing is guessed.** The terminal does not name a sender from a comment, a signal id, the account or the symbol.
- Acceptance checks that every sender on screen is SignalMesh's own word, and prints how many trades each sender has.

### Fixed bugs
- None.

### Outstanding issues
- **The sender names depend on SignalMesh.** Until it adds `sender` to `GET /api/v1/trades`, the column says "not stated". That is Shyam's decision on the platform side.
- The new engine's trades are NOT the paper lanes' trades: it enters at market after the touching bar closes. The terminal does not show the two side by side, and must say so if it ever does.
- The terminal prints no engine state (armed, paused, registered): no field it reads says it.
- Everything listed under 2.7.1 to 2.12.0 still applies.

## 2.12.0 — 2026-11-21

Follows platform 5.214 and 5.215. Two things: the terminal no longer says LIVE on a closed market, and the lanes' history is shown counted by plans. Nothing is calculated here; every word is SignalMesh's.

### Changes
- **Never LIVE on a closed market.** On Saturday 21 November the terminal showed US100, US30, VIX and DXY as LIVE. The reason: SignalMesh's freshness word for their newest bar was LIVE (it is the newest bar there can be), the terminal copies that word, and no read route said the market was closed. SignalMesh now sends its own market clock with every market answer, and the terminal uses it: when the clock says closed, the instrument reads **CLOSED** and **MARKET CLOSED · reopens in 26h 45m · last price, not live**, with SignalMesh's reason. This holds everywhere the word appears: Market Watch, the chart header, the decision panel's bar freshness, the coverage table, Data Sources and the studies.
- **No forming bar on a closed market.** The chart draws no live or forming bar while SignalMesh says the market is closed; it reads "NO LIVE BAR · MARKET_CLOSED".
- **A closed market cannot be READY.** A decision on a closed market is shown as not ready, by the same rule that already held for stale data.
- **The clock only takes LIVE away; it never gives it.** Inside an open market the bar's own age still decides. MARKET QUIET (inferred) stays for what the clock does not know: the daily break and holidays.
- **Lane history counted by plans, shown first.** The old count took every bar, so one plan held across many bars counted many times, and the verdict words were too confident. SignalMesh now sends the same history counted once per plan. Each lane shows SignalMesh's own sentence first, for example "by plans: UNKNOWN ? — 31 plan(s) on 9 day(s), standing for 412 bar(s)". The old line stays beside it, labelled **by bars (an upper bound)**. The box "Evidence verdict — V1 beside V2" shows the plan counts and SignalMesh's note first, each row's plan sentence, and labels the old columns "by bars".
- **"Not enough days" is said, not hidden.** When there are enough plans but they were born on fewer than 20 days, SignalMesh's verdict is UNKNOWN with its reason; the terminal prints that reason.
- **Acceptance** checks, for every instrument, that the market clock on the terminal is SignalMesh's own and that nothing on a closed market reads LIVE or READY, and compares every plan count, verdict and sentence with SignalMesh's.

### Fixed bugs
- **LIVE shown on a closed market** (seen by Shyam on 21 November: US100, US30, VIX, DXY). Fixed as described above.

### Outstanding issues
- **SignalMesh's clock is the approximate week** (Friday 22:00 UTC to Sunday 22:00 UTC; crypto always open). It does not know the daily metals break or a holiday. In those hours the terminal still infers MARKET QUIET from the feed.
- **Candles of four weeks a year are stored one hour late on 1h and smaller timeframes** (the broker's clock follows New York); SignalMesh has no repair plan for those yet. The terminal corrects nothing and removes no bar by itself. Trade times are right. (Corrected 22 November: SignalMesh reports the daily and 4h series repaired on 21 and 22 November, GOLD, SILVER, DXY and VIX included; what it says is left are 22 single 4h bars from 2003 (GOLD) and 2011–12 (BTC), which nothing recent reads. US10Y still holds two instruments under one name.)
- With a platform older than 5.214 none of the new words appear and the terminal reads as 2.11.1 did.
- Everything listed under 2.7.1 to 2.11.1 still applies.

## 2.11.1 — 2026-11-21

### Changes
- **A button "Outlook" in the top bar**, beside Market Watch, Decision and Toolbox. It opens the Toolbox at the bottom on the Market Outlook tab; the Call Ledger and Turning Point tabs are beside it. Shyam did not find the three new tabs of 2.11.0: they are inside the Toolbox, and his Toolbox was hidden.
- **Ready for the platform's account fields (platform 5.213, reporter 1.12.0).** When SignalMesh starts sending used margin, margin level and the account type, the terminal shows them without another release: DEMO or LIVE instead of "DEMO/LIVE UNKNOWN", and the two margin figures instead of NOT AVAILABLE. No code changed for this; a test now proves it, including that the broker's number 0 (demo) is read as a value and an empty field stays NOT AVAILABLE.

### Fixed bugs
- None.

### Outstanding issues
- Until platform 5.213 and reporter 1.12.0 are both running, the account line still reads DEMO/LIVE UNKNOWN and margin NOT AVAILABLE. That is correct: nothing is guessed.
- **Stored bar and trade times can be one hour late for about four weeks a year** (last: 25 October to 1 November 2026), because the broker's clock follows New York. SignalMesh will repair its history; the terminal shows what SignalMesh stores and corrects nothing by itself.
- **The lanes' history counts (n) and the V2 verdict word are too confident**: SignalMesh counts one result per bar. The terminal keeps showing what SignalMesh sends, with its rule name; a corrected count will arrive from SignalMesh as a new rule.
- The phone layout has no Outlook button; the three tabs are under "Trade" there.
- Everything listed under 2.7.1 to 2.11.0 still applies.

## 2.11.0 — 2026-11-20

Three SignalMesh pages can now be read inside the terminal: **Market Outlook**, the **Call Ledger** and the **Turning Point** record (platform 5.210 opened a read route for each). They are three new tabs in the Toolbox at the bottom. The terminal shows what SignalMesh sends and calculates none of it. The job came from the platform window's prompt (`docs/NEXT_WINDOW_PROMPTS.md` §E in Sniper-System), on Shyam's go. Each tab opens with one plain sentence from SignalMesh and a short "In plain words" box, explains each special word once, and shows real prices.

### Changes
- **Market Outlook tab — three questions about the instrument on the chart, from its closed daily candles.** 1 "Where has price been heading?" — UP so far, DOWN so far, or NO CLEAR TREND, with the reason. 2 "At which level does it get interesting?" — the nearest measured levels, each with its price, its name, the daily bar it comes from and how far away it is. 3 "What would prove this wrong?" — the daily close that would break the reading. Under them: every measured level above and below price, and one row for every core asset.
- **It says what price HAS done, never what it will do.** There is no arrow, no percentage of likelihood and no certainty word. SignalMesh tested on these candles whether patterns predict the next move, and none did; the tab says so beside question one.
- **"How often has the daily trend continued?"** — a small box with the system's own counted record: the verdict in SignalMesh's words, the counts for all assets and for this one, and the call that is open on this instrument now with its two prices.
- **Call Ledger tab — the system's own calls.** Nobody types these: when an asset's daily trend reads UP or DOWN, SignalMesh writes down one call by itself, and the candles score it later. The tab shows the scoreboard and every call: asset, direction, start price, target, invalidation, when it was written, when it expires, the outcome and the result in R. A finished call whose outcome SignalMesh has not stored on its row yet says "not stored yet".
- **Turning Point tab — the score of an old exam, not today's price.** The overall word (for example NO ROBUST EDGE), why there is no forecast card with each step marked ✓ or ✗, and one box per tested cell: what the model said, how often it came true, how often that happens anyway, and the real prices its question was about.
- **UNKNOWN is not a direction.** UNKNOWN, NO CLEAR TREND and SERIES FAULT are printed as what they are, in a neutral colour, with SignalMesh's reason. When a daily series is broken (two daily bars on one date) the tab says SERIES FAULT and reads nothing from it.
- **UNPROVEN stays UNPROVEN.** Counts and the share that continued are printed without green or red, in all three tabs. A handful of results is not a trend.
- **Nothing trades on this.** No button, order ticket or alert is wired to any of the three tabs, and nothing in them reaches the decision panel or the Forecast Journal.
- **NOT BUILT, never an empty panel.** If a SignalMesh build does not have one of the three routes, the tab says NOT BUILT and names the route.
- **Every figure has its date.** Each level names its daily bar; the reading names the bar it was made on; each tab's last line gives the time SignalMesh made the read and the time the terminal fetched it.
- **Acceptance compares all three with SignalMesh, field by field**: for every instrument the whole Market Outlook reading, its levels, the overview rows and the counted record; every Call Ledger row and the scoreboard; the Turning Point overall word, its gate and every cell. It prints how many instruments read UP, DOWN, NO CLEAR TREND or UNKNOWN, which carry a SERIES FAULT, and whether any finished call is not stored yet.

### Fixed bugs
- None.

### Outstanding issues
- **Not yet seen on production data.** On test data the three tabs were checked in a browser on a desktop and a phone screen, and the comparison script was run against a local copy of SignalMesh 5.211 with seeded candles (896 checks, 0 FAIL). The box has not run it.
- **A week of calls is not a verdict.** Both distances of a call are equal, so about half continue by chance. The scoreboard reads UNPROVEN until 20 calls have finished, and it is right to.
- **US100, US30, EURUSD and USDJPY read SERIES FAULT on SignalMesh on 2026-11-20** (doubled daily bars). That is SignalMesh's correct answer until its candle repair, not a terminal fault; those assets also get no call.
- **The Turning Point tab does not list the hundreds of stored test rows** behind each cell; SignalMesh's own `/turning-points` page does.
- **The plain-words boxes are the terminal's own sentences.** They explain; every number, state, level and verdict beside them is SignalMesh's. Where the tab is laid out (three Toolbox tabs) was the terminal window's choice and is easy to move.
- Market Outlook and the Call Ledger are re-read every minute, the Turning Point record every five minutes; a new daily bar or a new call can be up to a minute old on screen.
- Everything listed under 2.7.1 to 2.10.0 still applies.

## 2.10.0 — 2026-11-20

The platform changed three things the terminal mirrors or prints (platform 5.206 and 5.211). This release follows them. Nothing new is calculated; every word and number is still the platform's. The job came from the platform window's prompt (`docs/NEXT_WINDOW_PROMPTS.md` §F in Sniper-System), on Shyam's go.

### Changes
- **Apple (AAPL) and Anthropic (ANT) are in the instrument list, beside NVDA**, in the group "stocks", with two decimals — copied from the platform's own two tables (`market_time.SINGLE_STOCKS`, `precision.SYMBOL_DECIMALS`). Until the bot side's reporter sends their first bars they read UNAVAILABLE: SignalMesh stores no candle for them yet. That is a measurement, not a fault. They are listed — in Market Watch, under the line "show … instruments without stored candles" — not hidden, and nothing is drawn for them. The names are AAPL and ANT only; no broker spelling (AAPL.NAS, AAPL.NAS-24) is ever added.
- **"NOT LOADED YET" is not "no history".** The platform now works out the lanes' history numbers in the background. For up to a minute after a platform restart they are empty, and the platform says so. The terminal now says so too: a lane's line reads "own history: NOT LOADED YET" with the platform's own sentence — never "n=0" — and the box "Evidence verdict — V1 beside V2" prints the platform's note in the warning colour, above its rows and while it is still folded. Each row then reads "UNDER THE FLOOR — history cells COMPUTING: NOT LOADED YET", so nobody reads an empty minute as a lane without history. When the cells are loaded the note is printed quietly ("history cells computed 4 min ago …").
- **The rule name is the platform's, whichever it sends.** The lane-history rule is `lane-history-v2` since platform 5.211 (it was v1). The terminal no longer carries either name of its own: it prints the string in the payload, and the acceptance check labels its comparison with it.
- **A small cell explains itself.** In v2 a single stock (NVDA, AAPL, ANT) is never pooled with other assets, so its history can be very small without being "answered from all symbols". The lane's line now prints the platform's own sentence whenever the cell holds fewer than 20 results — for example "n=3, under 20; a single stock is never pooled with other assets" — not only when the platform borrowed from all symbols.
- **Acceptance compares the new fields with the platform**, field by field, for every instrument: each lane's history cell with its rule and state, the board's ready flag and its note word for word, and each row's cell state. It also checks that AAPL and ANT are in the list as stocks with two decimals, and prints whether each is AVAILABLE or UNAVAILABLE.

### Fixed bugs
- None.

### Outstanding issues
- **AAPL and ANT cannot be seen on a chart until bars arrive.** When this was written the bot side had sent none. After they arrive the two instruments become drawable without a terminal release (the instrument list is re-read every five minutes).
- **ANT began trading on 2026-11-04.** Its 4h and daily lanes will read WAIT with NO_HISTORY for weeks. The terminal prints the platform's own reason. Nothing is padded and nothing is borrowed from another instrument.
- **The "not loaded yet" state lasts about a minute after a platform restart**, so the acceptance run will usually not meet it on production; it then lists it under NOT TESTED. The shape is covered by tests on test data only.
- The cells' age (`cells_age_s`) is carried but not compared in acceptance: it grows between the platform's read and the terminal's.
- With a platform older than 5.206 the new keys are absent and the terminal reads exactly as 2.9.0 did.
- Everything listed under 2.7.1 to 2.9.0 still applies.

## 2.9.0 — 2026-11-19

### Changes
- **Chart read: one switch in the indicators menu** ("Chart read — structure table and labels"), off by default and remembered. Shyam asked for what his TradingView indicator shows him — the swing labels on the candles and the information table — on the terminal's own chart, without a new signal. It is a READ of closed bars: not a signal, not recorded in the Forecast Journal, never an input to SignalMesh, no order.
- **On the chart**: HH / HL / LH / LL on confirmed swings, and ▼ REJ / ▲ REJ / ▼ ENG / ▲ ENG on rejection and engulfing candles. Only the newest are drawn, so the chart stays readable.
- **The table**, in the order of his indicator's: weekly, daily, 4H and 1H trend with the newest break of structure; swing structure; last confirmed break; nearest resistance and support; momentum (RSI, MACD); volatility (ATR against its own average); price zone (premium / discount); volume against its average; the engine's own bias; SELL and BUY conditions; fair value gaps, order blocks, liquidity and inducement; the day forecast and ADR status; the newest signal SignalMesh holds for the symbol.
- **Each row names its source.** Structure rows are read from the existing Smart Money study, the day rows from the existing daily forecast, the bias from the SignalMesh engine word for word. Only momentum, volatility, volume, price zone, the labels and the condition count are calculated by the chart read itself. Hover a row for how it was read.
- **Conditions, six per side**: rejection, engulfing, lower high / higher low, BOS, CHoCH, EMA20 against EMA50. Each is CONFIRMED, WAITING, FAILED or NOT APPLICABLE with its reason and its bar. BOS, CHoCH and rejection weigh 3, engulfing and the swing 2, the moving averages 1. The table shows "SELL 3/6 · weight 6/14"; it is a count of conditions on closed bars, never an instruction to trade.
- **NOT AVAILABLE where it is not known**: a timeframe SignalMesh does not store, and TradingView's strategy-tester numbers (trades, win rate, average R), which do not exist outside TradingView and are not imitated.
- When the data is not live the table says "DATA STALE" above everything.
- Acceptance looks up every label in the engine's own bars and checks the rows that repeat another study against that study. `scripts/update.sh --history` checks on the recorded Gold and Silver bars that no label is ever restated. Two box screenshots per metal.

### Fixed bugs
- None.

### Outstanding issues
- **The values will not always equal TradingView's.** The Pine script runs on TradingView's bars and day boundary; the chart read uses SignalMesh's stored broker bars and the terminal's own definitions, given in the method panel. It is not a port of the Metal Hunter script: Pine's trade models (NY trap, reversal origin), its 9-factor score and its macro / intermarket rows are not reproduced.
- **The definitions are the terminal's own** and can be argued with: a rejection is a wick at least twice the body, closing in the far 40% of the range, at the extreme of the last 10 bars, at least 0.6 ATR tall. They are constants in `chartread.py`, not yet settings on screen.
- Not seen on production data. Verified on GOLD and SILVER fixtures only; it draws on every instrument, unverified.
- A condition count is not evidence. Nothing here is measured against outcomes, because nothing is recorded.
- Everything listed under 2.7.1 to 2.8.1 still applies.

## 2.8.1 — 2026-11-19

After the first 2.8.0 run on production: 3066 checks, 7 FAIL, all seven on one instrument (US100). The new desk evidence compared equal on all 29 instruments.

### Changes
- None beyond the fix.

### Fixed bugs
- **The decision panel could show the engine's verdict and bar up to a minute old.** Market Watch keeps each instrument's engine snapshot for 60 seconds, and stored it under the same key the decision panel reads with a 15-second lifetime, so the panel was handed the list's older copy. Seen on US100: the engine's newest 15m bar was 01:30, the terminal still showed 01:15 with that bar's close, ATR and VWAP distance, after the acceptance script had already waited out the 15 seconds. The values were the engine's own from up to a minute earlier, not invented ones. Market Watch now has its own copy; the selected instrument's panel is at most 15 seconds old, as it always said.
- Acceptance waited 15 seconds before its second read although the market-watch row it also compares is kept for 60; it now waits out the longest cache. The gate table counted a re-read instrument's first read as well (it printed 14 FAIL beside a total of 7).

### Outstanding issues
- Everything listed under 2.7.1 to 2.8.0 still applies.

## 2.8.0 — 2026-11-19

The platform's Trade Desk gained evidence the terminal did not show (platform 5.202 and 5.203). This release shows it. Everything is read from `GET /api/v1/market/desk`, which the terminal already read; the terminal calculates none of it. Asked for by Shyam through the platform window's prompt (`docs/NEXT_WINDOW_PROMPTS.md` §C in Sniper-System).

### Changes
- **Desk lanes: a word beside DATA_STALE.** When the platform says why a stale lane is silent — SCHEDULED BREAK, NOT A BREAK or BREAK UNKNOWN — that word is printed beside the reason, with the platform's note in the tooltip. The lane is still WAIT; a break word never makes a lane fresh.
- **Desk lanes: the lane's own history.** A lane that holds a setup gets one line under its levels, for example "own history: n=47 · +0.118R · CANNOT SEPARATE ? · v1 POSITIVE ✓": the number of resolved paper fills of that lane's own engine, their expectancy, and the platform's two evidence verdicts. When the platform answered from all symbols because this symbol's own cell was under 20, the line says so. A lane with no setup shows no line; n = 0 reads UNKNOWN (n=0).
- **The comparison lab's number is never shown as a lane's history.** The older `history` value belongs to another engine unless the platform says it applies to the lane; the terminal does not carry it.
- **A new box, "Evidence verdict — V1 beside V2"**, under the Desk lanes, labelled PAPER and folded until opened. Eight rows from the platform's verdict board — the four lanes × the two setup classes — with n, expectancy, the 90% interval, V2's word, V1's word and what V2 changes (SAME WORD, TICK WITHDRAWN, CROSS WITHDRAWN, DIFFERENT WORD, UNDER THE FLOOR). The row that is a lane's live setup is marked. The summary line, and the platform's own "what this is NOT" and authority sentences, are printed word for word.
- **Three named states for the box**: the board; FAULT with the platform's own fault when it could not be built; NOT AVAILABLE on a platform build that does not send it.
- **Acceptance compares it with the platform field by field**, for every instrument: each lane's own history, break word, both verdict words, and every verdict-board cell, summary and sentence. A lane's decision is checked to be the platform's own, whatever its break word.

### Fixed bugs
- None.

### Outstanding issues
- **This is PAPER research evidence**: a hypothesis generator, never a signal, never an input to a decision, never an executable plan. The box compares two WORDS on the same numbers. It does not say which rule performs better.
- Not yet seen on production data. On the box, by eye: the rows must match "Evidence verdict — V1 beside V2" on the platform's own `/desk?symbol=` page for the same symbol.
- The break word is the platform's, learned from the instrument's own bars. Market Watch still writes "MARKET QUIET (inferred)": the terminal still has no trading calendar of its own, and the two are not merged.
- Everything listed under 2.7.1 to 2.7.3 still applies.

## 2.7.3 — 2026-11-12

After the first complete 2.7.2 run on production: acceptance 2159 checks, 0 FAIL, all three gates PASS, restore rehearsal all OK, six chart checks PASS — and two steps that reported a failure. Both are fixed here. No new study, no new feature.

### Changes
- None beyond the two fixes.

### Fixed bugs
- **A Wolfe wave's apex and expiry TIMES could change after it was detected** (history check on recorded bars: FAIL on Gold 1h, 4h, 1d and Silver 1d — every series that held a Wolfe pattern). The apex and the expiry are bar counts; their clock times were estimated while the bars did not exist yet and read from the real bars later, and a daily break or a weekend lies between the two. Entry, stop, targets, the point prices and the status were never affected, and the journal's levels and outcomes were not affected. The times are now estimates fixed on the detecting bar and never restated; the lines to the apex use prices calculated by the adapter. The seeded test series had no breaks, so the tests could not see this: a test on a series with daily breaks is added.
- **The screenshot run stopped after the second picture on production** ("Timeout … waiting for navigation until networkidle"). A terminal on live data polls all the time, so its network is never idle. The script now waits for the page itself. The six chart checks had already run and passed; the pictures per Gold / Silver timeframe and the Elliott status check had not.

### Outstanding issues
- The asset ranking and the daily forecast do not mark a row whose instrument is not LIVE (seen on production: DXY, MARKET QUIET, ranked "DONE - sleep" from its last stored bars). The row is not a signal and scores 0, but it should say its data is old. Not changed in this release.
- Everything listed under 2.7.1 and 2.7.2 still applies.

## 2.7.2 — 2026-11-11

After the first 2.7.1 acceptance run on production (2149 checks, 1 FAIL): the script fault behind that FAIL, and the last verification items Shyam asked for before approving the current scope. No new study, no new feature.

### Changes
- **Stale-data guard.** The decision is the engine's own word and is never upgraded. It is now downgraded in one case: the engine says READY while its candles are not LIVE (or the instrument cannot be read). Then the panel and Market Watch show INVALIDATED, both sides INVALID, with the line "TERMINAL GUARD". The engine's word stays visible beside it. On production the engine already answered NO TRADE on stale candles; the guard covers the case where it would not.
- **A dead upstream is named.** When SignalMesh cannot be read at all, Market Watch says DISCONNECTED with the reason, where it used to show an empty list reading "discovering instruments…". When every instrument is silent it says FEED STALE.
- **Journal audit** in the Forecast Journal data and in acceptance: totals counted by the database over the whole store — LIVE and BACKFILL, finished, never entered, open, by method and timeframe — and three integrity counts (an outcome mark without a forecast, a mark recorded twice, a forecast id twice) that must all be zero.
- **Disconnected and feed-stale are tested by simulation** (`adapter/tests/test_data_states.py`): the test provider answers as a stale or a dead SignalMesh would while the engine is made to say READY. Nothing is shown READY, no decision and no study is served for an unreadable instrument, the recorder records nothing new, execution stays disabled. The production MT5 feed is not touched.

### Fixed bugs
- Acceptance reported `signal ids identical` FAIL on 2.7.1: one id only in the engine's list (a signal created seconds earlier) and one only in the terminal's (the oldest of the 200, pushed off the engine's list by the new one). The terminal was showing the engine's own list from a few seconds before. The script now reads both sides again after the cache lifetime when the lists differ, as it already did for a status that moves, and prints only the ids that are on one side.
- `scripts/update.sh` stopped at the first step that reported a failure, so the one acceptance FAIL on 2.7.1 kept the restore rehearsal, the chart checks and the history check from running at all. Every step now runs, and the last lines say which reported a failure.
- The candle-coverage note said a 15m bar was "NOT stored" while that bar was simply still forming. It now tells a forming bar from a finished bar that has not been sent.

### Outstanding issues
- **What the first production run showed about the missing candle:** Gold and Silver have no stored bars from 22:00 to 23:00 UTC on each of the last three days (the daily break), and the last 15m bar before the break (21:45) reached the engine only after the market reopened at 23:00. During the break the chart therefore ends at 21:30 while the 1m price is from 21:58. Why the reporter sends that bar late is a SignalMesh-side question; the terminal draws what the engine holds.
- Everything listed under 2.7.1 still applies.

## 2.7.1 — 2026-11-11

Verification release after Shyam's review of 2.7.0 on production. No new study, no new feature: fixes, clearer words, and tests.

### Changes
- **Elliott: three separate lines instead of one word.** PIVOTS (confirmed = final), COUNT (PARTIAL until five waves have printed and all four impulse rules have passed, then COMPLETE), TRADE SETUP (none, triggered, or recorded). A partial count is never called confirmed.
- **Elliott in the Forecast Journal records trade setups only** (method `elliott-setups-v2`): a wave-3 setup on the bar that TRIGGERS it — the first close beyond the wave-1 end while the 1-2 count is alive — and a finished five-wave impulse. A 1-2 count that has not triggered, the wave-4 pullback and the wave-5 "do not add late" stage are not setups and are not recorded.
- **A changed method never shares a hit rate with the one it replaced.** Hit rates are now grouped by method version as well. The Elliott rows 2.7.0 recorded (stages, including untriggered ones) stay in the journal — it is append-only — under their own method name, apart from the new ones.
- **The pattern report says when its data is not live**: a red line "DATA STALE — the newest closed bar ended …; this is the last known picture, not a live market".
- **Market Watch says why a price is not live**: MARKET QUIET (this instrument is silent while the same feed is delivering others: closed or on its daily break — inferred, the terminal has no trading calendar), FEED STALE (nothing is updating: the collector or its connection), DISCONNECTED (the read failed). The engine's own freshness word is unchanged beside it.
- **Acceptance checks GOLD and SILVER on 15m, 1h, 4h and 1d** for all five studies, checks the Wolfe / Elliott journal rows, and ends with a RELEASE GATES table: PASS / FAIL per gate and a NOT TESTED list. An untested thing is listed, never counted as a pass.

- **Acceptance prints a matrix**: GOLD and SILVER × M15, H1, H4, D1 × the five studies, each PASS, FAIL or NOT TESTED; a candle-coverage note (where the engine's 1m and 15m bars stop, and any gaps); and the evidence for the US500 fix.
- **`scripts/journal_restore_test.sh`: a restore rehearsal.** It takes a backup, opens the newest and the oldest kept backup file exactly as the terminal would open a restored journal, and checks that every backed-up row is in the live journal unchanged and that edits and deletions are refused. The live journal is only read. `scripts/update.sh` runs it after acceptance.
- **`scripts/screenshots.sh` also tests the chart on the running terminal**: crosshair, zoom, scroll, "latest", full screen and Escape, each PASS or FAIL in the output and in `manifest.txt`; and it takes one picture per GOLD / SILVER timeframe with the five studies on.
- Market Watch writes "MARKET QUIET (inferred)". The terminal never writes MARKET CLOSED: it has no trading calendar.

### Fixed bugs
- 2.7.0 showed "BEAR WAVE 3 setup · CONFIRMED" beside "1 of 4 impulse checks passed" (GOLD 15m). "Confirmed" there meant only "price closed beyond the wave-1 end"; it read as a confirmed Elliott count, which it was not.
- 2.7.0 recorded Elliott stages in the journal on the bar the stage appeared, whether or not the setup had triggered, and recorded the wave-5 stage that the study itself labels "do not add late".

### Outstanding issues
- **MARKET CLOSED is inferred, not known.** SignalMesh gives the terminal no trading hours. Telling a closed market from a failed collector with certainty needs the platform to expose each instrument's session hours — a SignalMesh change, not made here. DELAYED is not a separate state.
- **No Wolfe or Elliott forecast has yet been recorded LIVE and scored to its end on production.** The rows so far are BACKFILL. This needs time to pass.
- Pattern studies are checked on GOLD and SILVER only. They draw on every instrument, but no other instrument's calculation has been verified.
- Layout persistence and panel hide / show are tested by the automated browser run on test data only; zoom, scroll, crosshair and full screen are now also tested on the running terminal by `scripts/screenshots.sh`.

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
