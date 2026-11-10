# Handoff brief for Fable 5.1 — SMC Metal Hunter V15

Copy everything below the line into a new Claude Code session running Fable 5.1,
with the repository `sabuj14eu/DESKTOPINTERFACE` attached.

---

## Who you are working for

A discretionary trader of **gold and silver CFDs at XTB** (Poland, PL time = ET + 6h in winter).
They chart on TradingView, mostly **15m** (5m for traps), and send screenshots of the chart and tables.
Write to them in **short, simple English**. They are not a programmer.

## Hard rule from the user

**Do not delete or reduce anything.** No feature, input, table, table row, alert, alertcondition,
drawing, label, panel, or default behaviour may be removed or weakened.
You may only **add**, or **fix a proven bug** (state the bug and the evidence first).
Before you finish, prove nothing was removed (see "No-reduction check" below).

## Where everything is

| What | Path (branch `claude/magical-bell-4n9g6y`) |
|---|---|
| Current script (Pine v6 strategy) | `pine/SMC_Metal_Hunter_V14_7.pine` (~2,900 lines) |
| Full change history + every finding | `pine/V14.1_REVIEW_NOTES.md` |
| How the user trades it | `pine/CHEAT_SHEET.md` |
| Python logic tests (22, all passing) | `pine/tests/test_v146_logic.py`, `pine/tests/test_v147_tables.py` |
| Static checker (run before every delivery) | `pine/tests/pine_static_checks.py` |
| Original V13/V14 source | repo `sabuj14eu/pinev18.6`, file `SMC_Metal_Hunter_V13.pine` (read-only) |
| Open draft PR | sabuj14eu/DESKTOPINTERFACE#2 |

Run: `python3 -m unittest discover -s pine/tests -v` and `python3 pine/tests/pine_static_checks.py <file>`.
There is **no Pine compiler** in the cloud session. Every delivery must be compiled by the user in TradingView;
ask them for the exact error text and the bar number.

## Update: V15.0 delivered as TWO scripts (see `pine/V15_NOTES.md`)

Branch `claude/brave-cannon-k75ujr`. A single-script V15 failed with `CE10117 too many tokens: 123567, limit 100256`,
which shows **V14.7 is already at the token limit**. Rule from now on: the main strategy must not grow
(`test_main_script_is_not_bigger_than_v147`); new features go into `pine/SMC_MH15_Plus.pine` (companion indicator).
Second rule: **never add, remove or reorder an input in the main script** (`test_input_list_is_identical_to_v147`);
saved settings are positional and a shifted list switched every table off for the user.
Neither script is compiled here and no backtest exists. Still open: the 12 setup toggles and every data-based test.

## Current status (step 0 — do this first)

1. The user's last runtime error (`historical offset 1304 beyond buffer limit 1303 at f_uiWolfe():2655, #main():2673`)
   came from **V14.6** (those line numbers match V14.6, not V14.7). V14.7 already draws the Wolfe wave and weekend gap
   with `xloc.bar_time`, caps other drawings at 1,000 bars back, and sets `max_bars_back=5000`.
2. Ask the user to paste **V14.7** on **XAUUSD and XAGUSD, 5m and 15m**, and confirm the dashboard says **V14.7 TERMINAL**.
3. Only start V15 after V14.7 runs on both metals without errors. If it still errors, fix that first.

## What is already done (do not redo, do not undo)

V14.1–V14.7 (details in the review notes):
* 50/50 TP1/TP2 exits with breakeven + fee buffer; TP1 detection bug fixed.
* Drawing budget: every historical drawing in a capped per-kind FIFO (500 labels/lines/boxes limit).
* Trap engine: minutes-based fail-back window for 5m; forecast and weekend-gap trap levels (default off).
* Daily forecast top/bottom (ADR), weekend open gap, Smart Scalp panel, PDH/PDL/PWH/PWL/pivots, Wolfe wave (TP1 = point 4, TP2 = EPA).
* Trade monitor at top center; warnings clear on recovery / expire.
* Trade-level stats row (W/L/BE, win % ex-BE, average R).
* **The five audit fixes (V14.6):**
  1. Oil votes for metals only when 10Y breakevens agree (inflation / disinflation); oil alone = growth, no vote.
  2. Trap detection is info-only; only approved setups produce trade-worded alerts.
  3. Explicit entry gates (COMMON / STANDARD / TRAP) and three opt-in trap filters; default decisions proven identical by a truth-table test.
  4. Monitor cancel really cancels the pending order (Auto-Cancel, default ON) or says "ORDER STILL LIVE".
  5. XTB broker-lot sizing (group 06B) separate from the backtest qty. GOLD 100 oz/lot and SILVER 5000 oz/lot are **defaults to be verified** in xStation — they were not confirmed from an XTB page.

## The V15 task (user's specification, unchanged)

After confirming the five fixes are correct, add:

* **Independent setup toggles** for: SMC Reversal, Trend Pullback, Liquidity Sweep, BOS/CHoCH, Order Block, FVG,
  Breakout, Wolfe Wave, NY Trap, Smart Scalp, Macro Hunter, Swing Hunter.
* **Independent performance tracking per setup** (trades, wins, losses, BE, win % ex-BE, average R, profit factor),
  separately for **gold** and **silver**.
* **Do not combine all signals into one misleading BUY/SELL score.** The existing 9-factor score may stay visible
  (no-reduction rule) but must not be the only decision basis; each setup gets its own approval.
* For **every signal** show: reason, conflicting factors, confidence grade, entry, SL, TP1, TP2, **invalidation** level/condition.
* Preserve all existing functionality.

### Required before V15 can be merged

* Unit tests (Python mirrors of the Pine rules, like the existing ones).
* Historical backtests per setup.
* Out-of-sample results (train/test split by date; report both).
* Repainting tests (TradingView Bar Replay vs. historical; signals must not change after bar close).
* Pending-order lifecycle tests (place → fill / expire / invalidate / monitor-cancel → exits → BE).
* XTB sizing validation against the user's xStation specification screenshots.
* Separate gold and silver performance reports.
* **No claim of improved profitability without statistically credible evidence** (state sample size, confidence interval or bootstrap, and compare against V14.7 on the same data).

### What you need from the user (ask once, early)

1. CSV exports of XAUUSD and XAGUSD at 5m, 15m and 1H, at least 1–2 years.
2. Screenshots of XTB's GOLD and SILVER instrument specification (contract size, min lot, lot step) and their account currency.
3. TradingView Strategy Tester "List of Trades" exports for V14.7 on the same period (baseline).

Without these, deliver code + unit tests, and say plainly that backtests/OOS/repaint results are not produced yet.

## Pine constraints learned the hard way (follow them)

| Problem seen | Rule |
|---|---|
| `CE10295 main body of the script is too long` | Keep display code (tables, last-bar redraws) inside functions `f_ui*()`. V15 will likely need a **second script** (e.g. "V15 Research" for per-setup tracking) or a Pine `library()` for helpers. Splitting is adding, not reducing. |
| `SHORT_TITLE_TOO_LONG` | `shorttitle` ≤ 10 characters (currently `SMC MH14.7`). |
| `CW10013 shadowing` | Never reuse a global name for a local or parameter (`p1`/`p2` are trade-plan lines). Run the static checker. |
| `historical offset beyond the historical buffer's limit` | Never draw from a stored bar index that can be far back. Use `xloc.bar_time` with stored `time`, or clamp `math.max(x, bar_index - 1000)`. `max_bars_back=5000` is set. |
| 500 labels/lines/boxes | Route every historical drawing through `f_keepLbl/f_keepLine/f_keepBox` with a cap; recount the worst case. |
| Repainting | `request.security` HTF data only as `expr[1]` with `lookahead_on`; signals only on `barstate.isconfirmed`. |
| Number formats | Use `"0.00"`, not `"#.00"` (leading zero). |
| Wide tables | Values go through `f_cut(v, cellMax)` with `tooltip=v`. |
| Tabs | Pine rejects tab characters. |

## No-reduction check (do this before every delivery)

1. Count in old vs new file: `input.`, `alertcondition(`, `alert(`, `f_row(`, `f_pc(`, `f_sc(`, `f_mc(`, `f_scr(`, `label.new(`, `line.new(`, `box.new(`, `plotshape(`, `strategy.entry(`, `strategy.exit(`. New counts must be ≥ old counts. Explain any difference.
2. Every input title in the old file must still exist (diff the list of input titles).
3. Default values of existing inputs unchanged unless a documented bug fix requires it.
4. All tests pass; static checker says `RESULT: OK`.

## Delivery format the user expects

* One complete `.pine` file (new version number in title, short title and dashboard row 0), pushed to the branch,
  plus the raw GitHub link.
* A short update in `pine/V14.1_REVIEW_NOTES.md` (or a new `V15_NOTES.md`).
* A short, plain-English summary for the user: what changed, what they must set, what is not done yet and why.
* Nothing here is financial advice; never promise profit.
