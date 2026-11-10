# SMC Metal Hunter V15.0 — notes

V15 is **two scripts on the same chart**:

| Script | File | What it is |
|---|---|---|
| Main strategy | `pine/SMC_Metal_Hunter_V15_0.pine` | V14.7 + fixes + new colors. Dashboard row 0 says **V15.0 TERMINAL** |
| Companion indicator | `pine/SMC_MH15_Plus.pine` | Elliott wave, money rotation ladder, event mode, my key levels. Shows as **MH15 PLUS** |

`pine/SMC_Metal_Hunter_V14_7.pine` is kept unchanged as the fallback.

## Why two scripts

The first V15.0 put everything in one script and TradingView refused it:
`Compiled code contains too many tokens: 123567. The limit is 100256 (CE10117)`.
That number shows V14.7 already used almost the whole limit, so nothing sizeable can be added to the main script.
The main script is now slightly **smaller** than V14.7 (a test checks this), and every new feature lives in the companion.

**Still not compiled here.** There is no Pine compiler in the cloud session. If TradingView shows an error, send the exact text, line and bar number.
No backtest was run, so there is **no claim that V15 is more profitable** than V14.7.

## Main strategy: what changed against V14.7

| Change | Evidence / reason |
|---|---|
| **Colors**: calmer, higher-contrast palette on all tables and chart marks. Monitor decision cells are dark enough for white text | You asked for better colors. White on yellow (CAUTION) was hard to read |
| **News is not a block**: very high volatility no longer removes score factor V. A dead market (ATR below 0.7x normal) still does | V14.7 dropped factor V when ATR was above 2.5x normal. There is no switch for this: use the V14.7 file for the old rule |
| **SMT divergence only on gold and silver** | `pairSym = isSilverChart ? goldSymbol : silverSymbol` compared US100, EURUSD, BTC with silver and raised trap grades for no reason |
| **USDJPY-type charts**: backtest size, R results and XTB lots converted with 1 / price | `riskCash / (stopDistance * pointValue)` mixed USD risk with a JPY stop distance (about 150x too small) |
| News Rule default text now says "No block on news..." | Your request. Your saved text is not touched |
| **Tables fill right after loading**: all last-bar drawing also runs on the last closed candle (`lastBar`) | Screenshot: only empty table frames while a candle was still open. A strategy does not run on the open candle until it closes, so `barstate.islast` alone left the tables empty until then |
| **Dashboard rows 21-25** now show FVG, order block + strength, liquidity, inducement and volume instead of SIGNAL / SETUP STATUS / ENTRY / STOP LOSS / TP1-TP2 (build d) | Your request: those five are already in Smart Scalp and the Trade Monitor. The internal setup-status text was removed to pay for the new rows in tokens |
| **Smart Scalp header says WAIT** (grey) when the last signal is finished | A stopped BUY from 93 bars ago still showed a big green BUY |
| Three unused variables removed (`gapBar`, `wfEPA`, `scLots`) | Never read anywhere. Removed only to free tokens. Nothing visible changes |

On gold and silver the trading logic is the same as V14.7, except the news rule above.

**The input list is identical to V14.7** (same inputs, same order; a test checks it). TradingView stores settings by position,
so one input added in the middle shifts every saved setting after it when you paste over the old script. An earlier V15 build did that
and all tables switched off. If settings ever look scrambled: Settings > Defaults > Reset settings.
No input, table row, alert, alertcondition or drawing was removed (`TestNoReduction` checks this automatically).

Not in the main script, because there is no token room: results split by setup type, conflict rows in Smart Scalp,
mirrored macro votes for USDJPY, XTB contract inputs for index / FX / copper (use "Other Symbols: units per 1 lot").

## Companion indicator MH15 PLUS

| Feature | What it does | Settings group |
|---|---|---|
| **Elliott wave** | Impulse count on chart pivots: wave 3 setup, wave 4 pullback zone, wave 5 targets, "5 waves done" correction levels, invalidation level. Purple `0, W1..W5` on the chart | 21 |
| **Money rotation ladder** | Gold, silver, copper, US100, EURUSD, USDJPY, BTC ranked by unused daily range (ADR) + momentum + session. **GO TRADE** row names the asset with the most room when this chart is done | 18 |
| **Event mode** | Pre-event range, spike window, follow-through window, ADR extension 1.5x / 2x. "Auto" also switches on when volatility is far above normal | 20 |
| **My key levels** | Line in the sand, targets, supports, scenario sentence, alerts on a close across the line. Pre-filled with the gold example (4020 / 4150, 4200, 4280 / 4083, 4055, 3875, 3700), shown only on gold charts | 19 |

It places no orders and does not change the strategy. One panel, default bottom right (group 00 to move or resize it).

## What you must do

1. Paste **both** files into TradingView as two scripts and add both to the chart.
2. Compile on XAUUSD and XAGUSD, 5m and 15m. Then US100, EURUSD, USDJPY, copper.
3. Rotation symbols (PLUS, group 18): a row showing `n/a` means that feed is not on your TradingView plan. Pick another.
4. Event clock (PLUS, group 20): on news days tick "Scheduled Event Today" and set the hour / minute in New York time.
5. Key levels (PLUS, group 19): update when your analysis changes. Line = 0 switches it off.
6. If you changed sessions or timezone in the main script, set the same in PLUS group 01.
7. Alerts from PLUS need their own alert: condition **MH15 PLUS > Any alert() function call**.
8. US100 chart: in the main script set NY Opening Range to `0930-0945`.

## Limits (plain)

* The Elliott count is an interpretation of the last 6 pivots on the chart timeframe. It can be wrong and changes when a new pivot prints. Context only, like the Wolfe wave.
* The rotation ladder ranks **room left**. It does not predict where money will go.
* The main script cannot grow. Any future feature goes into PLUS or replaces something.
* Still not done from the old V15 list: 12 separate setup toggles, per-setup tracking, historical / out-of-sample backtests, Bar Replay repaint tests, gold versus silver reports. The backtests need your CSV exports and Strategy Tester trade lists.

Not financial advice. Nothing here promises profit.
