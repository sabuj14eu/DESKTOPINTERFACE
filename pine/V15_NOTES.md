# SMC Metal Hunter V15.0 — notes

File: `pine/SMC_Metal_Hunter_V15_0.pine` (dashboard row 0 must say **V15.0 TERMINAL**).
`pine/SMC_Metal_Hunter_V14_7.pine` is kept unchanged as the fallback.

**Not compiled.** There is no Pine compiler in the cloud session. V15.0 passed the static checker and 61 unit tests,
but TradingView is the only real compile test. If it shows an error, send the exact text, line and bar number.
No backtest was run, so there is **no claim that V15 is more profitable** than V14.7.

## What is new

| # | Feature | Where you see it | Settings group |
|---|---|---|---|
| 1 | **Elliott wave** impulse count: wave 3 setup, wave 4 pullback zone, wave 5 targets, "5 waves done" correction levels, invalidation level. Purple `0, W1..W5` on the chart. Info + alerts only, no orders. | Smart Scalp rows ELLIOTT WAVE / ELLIOTT LEVELS | 21 |
| 2 | **Money rotation ladder**: gold, silver, copper, US100, EURUSD, USDJPY, BTC ranked by how much of the normal day range (ADR) is still unused, plus momentum and session. The **GO TRADE** row names the asset with the most room when this chart is done. | Bottom of the session table | 18 |
| 3 | **Event mode**: news is traded differently, never blocked. Pre-event range, spike window, follow-through window, ADR extension targets 1.5x / 2x. "Auto" also switches on when volatility is far above normal. | Weekly plan row EVENT MODE, dashboard row ASSET \| EVENT MODE | 20 |
| 4 | **My key levels**: your own line in the sand, targets and supports, with a scenario sentence and alerts when price closes across the line. Pre-filled with the gold example (4020 / 4150, 4200, 4280 / 4083, 4055, 3875, 3700), shown only on gold charts. | Weekly plan row MY LEVELS + lines on chart | 19 |
| 5 | **Multi-asset**: asset type is detected (GOLD, SILVER, COPPER, INDEX, FX, CRYPTO). Macro and dollar votes are mirrored for USDJPY-type pairs. XTB lots for index and FX. Backtest size and R are correct on JPY-quoted charts. | Dashboard, weekly plan RISK row | 06B |
| 6 | **Colors**: new "Pro Dark" theme for every table and the chart marks. "Classic V14" brings the old colors back. Black text on the yellow CAUTION cell. | Everywhere | 09C |
| 7 | **Result by setup type**: wins / losses / breakeven / average R for TREND-PB, MODEL and TRAP separately. | Dashboard row BY SETUP | - |
| 8 | **Conflicts + invalidation** for every Smart Scalp signal (daily trend, DXY/oil, ADR full, Elliott, your key level, Wolfe). | Smart Scalp rows CONFLICTS / INVALID IF | - |

## Code review: bugs fixed (evidence first)

| Bug | Evidence | Fix |
|---|---|---|
| SMT divergence compared **every** chart with silver | `pairSym = isSilverChart ? goldSymbol : silverSymbol` — on US100, EURUSD or BTC a "divergence versus silver" raised trap grades for no reason | SMT is automatic only on gold, silver, copper. New input **SMT Pair Override** for other charts. Gold and silver: identical. |
| Macro and dollar votes were metal-only | `f_i(dxC < dxE)` = bullish. Correct for gold, wrong for USDJPY (dollar up = pair up) | Votes are mirrored on USD-base FX. The silver/gold ratio vote is off on FX, the oil-inflation vote is off on FX and indices. Metals: identical. |
| Backtest size on JPY-quoted charts | `riskCash / (stopDistance * pointValue)` mixes USD risk with a JPY stop distance: USDJPY risk was about 150x too small and R values were wrong | Stop distance is converted with `quoteUSD` (1 / price). USD-quoted charts multiply by 1.0: identical. |
| XTB lots were "n/a" on every non-USD chart and used "1 unit per lot" for index / FX | `xtbPriceOK = syminfo.currency == "USD"`, `xtbCS = ... : xtbOtherCS` | New contract inputs for index (20) and FX (100000), both marked VERIFY. Copper is 0 = n/a until you set it, because XTB quotes copper differently from most TradingView copper charts. |
| White text on yellow in the monitor | DECISION cell: `color.white` on `#ffd600` | Black text when the decision is CAUTION. |

## Behaviour that changed on purpose

1. **Event Mode = Auto (default).** While event mode is active, ATR above 2.5x normal no longer removes the score factor V.
   Set **Event Mode = Off** to get the V14.7 trading logic back on gold and silver (the score rule is checked by `test_off_is_identical_to_v147`).
2. **News Rule default text** now says "No block on news..." (your request). Your saved text is not touched; edit it in group 10.
3. Non-metal charts: SMT and macro votes as in the table above.

Everything else is additive. No input, table row, alert, alertcondition or drawing was removed
(`TestNoReduction` in `pine/tests/test_v15_logic.py` checks this automatically).

## What you must check

* **Compile** on XAUUSD and XAGUSD, 5m and 15m. Then US100, EURUSD, USDJPY, copper.
* **Rotation symbols** (group 18): defaults are OANDA / BITSTAMP feeds. A row showing `n/a` means that symbol is not available on your TradingView plan: pick another feed.
* **XTB contract sizes** (group 06B) for US100, FX and copper in xStation. Gold 100 oz and silver 5000 oz are still unverified defaults.
* **Event clock** (group 20): tick "Scheduled Event Today" and set the hour / minute in New York time on news days. The same clock applies to every day in the backtest.
* **Key levels** (group 19): update them when your analysis changes. Set the line to 0 to switch it off.
* **NY Opening Range** on US100: change it to `0930-0945` (the default 08:20 is the COMEX metals open).

## Limits (plain)

* The Elliott count is an interpretation of the last 6 pivots on the chart timeframe. It can be wrong and it changes when a new pivot prints. Use it as context, like the Wolfe wave.
* The rotation ladder ranks **room left**, it does not predict where money will go.
* Three tables grew (plan 14 rows, session 24 rows, scalp 19 rows). If they overlap on a small screen, set the sizes to Tiny or switch the rotation ladder off.
* The script is large. If TradingView reports `main body of the script is too long`, tell me: the new logic is already inside functions, so the next step would be a second companion script for the new panels.
* Still not done from the old V15 list: 12 separate setup toggles, historical / out-of-sample backtests, Bar Replay repaint tests, gold versus silver reports. These need your CSV exports and Strategy Tester trade lists.

Not financial advice. Nothing here promises profit.
