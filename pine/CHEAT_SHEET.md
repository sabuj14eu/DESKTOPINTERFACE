# SMC Metal Hunter V15.0 — Trading Cheat Sheet

Made for **gold and silver (XAUUSD / XAGUSD)** on **15m** (5m for the trap engine).
This is a checklist, not a guarantee. Not financial advice.

---

## 1. One-time setup

| Step | Where | What |
|---|---|---|
| 1 | Chart | XAUUSD or XAGUSD (quoted in USD), 15m |
| 2 | Settings group **06B XTB Lot Sizing** | Your XTB balance, account currency, currency per 1 USD (e.g. PLN ≈ 3.7) |
| 3 | xStation → instrument specification | Check GOLD = 100 oz/lot, SILVER = 5000 oz/lot. Change 06B if different |
| 4 | Settings group **13 Trade Monitor** | Auto-Cancel Pending = ON. Auto-Close on EXIT NOW = your choice (OFF = advice only) |
| 5 | Alerts | Delete old alerts → new alert → condition **"Any alert() function call"** |
| 6 | Weekly plan → EVENTS | Type this week's news (CPI, PPI, FOMC, NFP) |

The RISK row of the weekly plan must say **XTB GOLD 100 per lot** or **XTB SILVER 5000 per lot**.
If it says **OTHER** or **⚠ chart not quoted in USD**, the lot numbers are wrong for metals.

---

## 2. Before each session (2 minutes)

1. **Dashboard (top right):** WEEKLY, DAILY + 4H, HTF STRUCTURE.
   * Mostly BULL → prefer buys. Mostly BEAR → prefer sells. MIXED → only A-grade trades, or wait.
2. **DAY FORECAST / ADR STATUS:** if it says **TOP IN** or **BOTTOM IN (ADR FULL)**, do not chase in that direction.
3. **EVENTS / EVENT MODE:** news is not a block any more (V15). Read the EVENT MODE row and section 9. The old cautious rule (no new trade 30 min before news) is still a valid personal choice.
4. **Session table:** best windows are London and the **NY kill zone (08:00–11:00 ET)**. Friday: no new trades after 12:00 ET.
5. **INTERMARKET row:** read the oil text. "DISINFLATION (bear)" or "INFLATION (bull)" counts. "GROWTH (no vote)" is context only.

---

## 3. Smart Scalp entry checklist — ALL must be YES

| # | Check | Where |
|---|---|---|
| 1 | Status is **● LIVE** (not EXPIRED / STOPPED / TP2 HIT) | Smart Scalp, row 2 |
| 2 | **GRADE A or B** | GRADE |
| 3 | **R:R TO NEXT LEVEL ≥ 1.5** (no "LOW") | R:R row |
| 4 | **No "⚠ OPPOSITE TO OPEN …"** | SOURCE |
| 5 | Source is **not** "(manual, not strategy-approved)" unless you choose it on purpose | SOURCE |
| 6 | Direction agrees with the dashboard bias, or grade is A | Dashboard |
| 7 | **XTB lots is a number** (not "< min" or "n/a") | SCORE \| XTB LOTS |
| 8 | No news in the next 30 min, today's trades < 3 | Events / TODAY row |
| 9 | Max **1 gold + 1 silver** trade open | Your account |

Then place in XTB: **limit at ENTRY, SL, TP1 (half the lots), TP2 (other half)**, using the XTB lots shown.

---

## 4. Weekly plan pending orders

| Row | Use it only when STATUS says | Never when |
|---|---|---|
| BUY LIMIT / DEEP BUY / SELL LIMIT | **CONFIRMED 15m: ENTER** | VALID or NEAR alone (it is a level, not a signal) · LOW RR: SKIP |
| BUY STOP / SELL STOP | **4H CLOSE OK: ENTER/RETEST** | WAIT BREAK · ARMED |

* Lots: use the **XTB LOTS** column.
* Do not hold a weekly-plan order and a Smart Scalp trade in **opposite** directions on the same metal.
* The weekly-plan orders are **not** backtested by the strategy. Treat them as a map until your own journal proves them.

---

## 5. Managing an open trade

| Event | Action |
|---|---|
| TP1 hit | Half closes. Move SL to **breakeven + buffer** (the script does this in the backtest; do the same in XTB) |
| TP2 hit | Trade done |
| Monitor **HOLD** | Do nothing |
| Monitor **CAUTION** | Watch, do nothing yet |
| Monitor **EXIT WARNING** | Tighten SL or take a partial |
| Monitor **EXIT NOW** | Close (if Auto-Close is OFF it is advice; the position is still open until you close it) |
| Monitor **CANCELLED BY MONITOR** | Strategy order cancelled. Cancel your XTB pending order too |
| Monitor **CANCEL ADVISED – ORDER STILL LIVE** | Auto-Cancel is OFF. Cancel it yourself in XTB if you agree |

---

## 6. Never

* Trade **grade D**, or R:R marked **LOW**.
* Trade an alert that says **"DETECTED (info only, NOT a trade)"** or **"watch only"**.
* Copy the **backtest qty** into XTB. Only use **XTB lots**.
* Chase after **ADR FULL**.
* Move the SL further away.
* Judge a setting on fewer than ~100 trades.

---

## 7. Alerts — what they mean

| Alert starts with | Meaning | Trade it? |
|---|---|---|
| `V10 BUY LIMIT` / `V10 SELL LIMIT` | Strategy placed an approved order (has E/SL/TP + XTB lots) | Yes, after the checklist |
| `V14 SMART SCALP` | Approved setup, also when the strategy can't place it | Yes, after the checklist |
| `… TRAP DETECTED (info only, NOT a trade)` | A fake break happened | No — wait for an order alert |
| `… NY BUY/SELL SETUP (manual plan, NOT a strategy order)` | NY sweep + structure | Only by your own decision |
| `V14 MONITOR …` | Trade monitor changed its decision | Follow section 5 |
| `PLAN … CONFIRMED` / `… ARMED` | Weekly-plan level confirmed | Section 4 |
| `FORECAST TOP/BOTTOM REACHED` | Day's expected range done | Stop chasing that way |
| `WEEKEND GAP` / `GAP FILLED` | Weekly open gap info | Context |
| `WOLFE WAVE` | Wolfe pattern (best on 4H/D) | Context / swing idea |

---

## 8. Weekly review (10 minutes)

Write every trade in a journal: **date, metal, source (TREND-PB / MODEL / NY TRAP / weekly plan), grade, R result**.
After about 100 trades, compare **average R per grade and per source**. Keep what earns, drop what doesn't.
The dashboard row **TRADES W/L/BE | AVG R** shows the strategy's own result on the chart symbol.

---

## 9. V15 additions (companion script **MH15 PLUS**, add it to the same chart)

All rows below are in the MH15 PLUS panel (default bottom right).

### Event day (CPI, NFP, FOMC, or news moved / cancelled)

| Phase | What the EVENT MODE row says | What to do |
|---|---|---|
| Before | `EVENT IN xx m` + pre-range high / low | Keep the plan. Half size. Plan both sides |
| First 30 min | `SPIKE` | First move is often fake. Take the sweep that **closes back inside** the pre-range (trap), or wait for **2 closes beyond** it |
| Next hours | `FOLLOW-THROUGH` + ADR 1.5x / 2x | Trade the first pullback in the break direction. ADR FULL is not a stop sign today |
| Any day | `VOLATILITY EVENT (auto)` | Same as follow-through. Lots are smaller because the stop is wider |

Setup: PLUS group **20**, tick **Scheduled Event Today**, set hour and minute in New York time.

### My key levels (PLUS group 19)

Type your line in the sand, targets and supports. The MY LEVELS row reads them for you, for example:
`ABOVE 4020: scenario ALIVE | next up 4200 then 4280 | support 4083 then 4055`.
A close below the line sends the alert **KEY LEVEL LOST**.

### Money rotation ladder

| State | Meaning | Action |
|---|---|---|
| DONE - sleep | Day range is at or above the normal range (ADR) | No chase. Only fades / traps. Look at the GO TRADE row |
| NEAR FULL | 85 % or more used | Late. Small targets |
| MOVING UP / DOWN | Awake with room left | Buy pullbacks / sell rallies |
| FRESH (quiet) | Has not moved yet | Wait for the break or its session open |
| EXPANSION (event) | Over ADR on an event day | Pullbacks and traps only |

**GO TRADE** names the asset with the most room, e.g. `GOLD move DONE (112% ADR): let it sleep -> GO TRADE US100`.
It ranks room left. It is not a signal: open that chart and use the normal checklist there.

### Elliott wave

| Text | Use |
|---|---|
| WAVE 3 setup ... CONFIRMED | Strongest wave. Trade with it. Targets T1 / T2, wrong below "invalid" |
| WAVE 4 pullback | Wait for price in the zone, then look for a signal with the trend |
| WAVE 5 running | Last push. Do not add late. Take profit at T1 / T2 |
| 5 WAVES DONE | No chase. Expect a pullback to the ABC 38.2 % / 61.8 % levels |

Before taking a Smart Scalp signal, check it does not fight the Elliott row or your key level.

### Other assets

US100, EURUSD, USDJPY, copper and crypto charts work with the same rules. For XTB lots outside gold and silver set
"Other Symbols: units per 1 lot" in group 06B from xStation. On US100 set NY Opening Range to `0930-0945`.
