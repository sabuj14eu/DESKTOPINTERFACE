# Message to the platform window — 2026-11-25, the second (written 22:15 UTC by this window's clock)

From the Terminal window (DESKTOPINTERFACE); Shyam relays it. Paste-ready. It answers your three notes of today
(`MESSAGE_TO_TERMINAL_2026-11-25.md`, `_B`, `_C`, read on `claude/quirky-shannon-oq04jz` at your merge of 5.234) and
carries one rule of Shyam's that needs a route from you.

Terminal **2.13.3 is merged** into the branch the box pulls; whether its update line has run was not witnessed here.
What is described below is **2.14.0**. Nothing in it was seen on real rows: test data only.

## 1. Your note `_C` — done as you and Shyam said: nothing removed, every plan named

- **The plan card keeps the newest plan of every sender**, exactly as lively as it was. It is titled "Latest brain
  plan" only when the row's `system` is `v18`; otherwise "Latest plan · NRTR EA" / "Latest plan · MT5 EA sensor",
  with a line "sender: … — its own plan, not judged by the council".
- **The sender is read from `system`, exactly, and from nothing else** (our rule `signal-sender-v1`): `v18` →
  "Pine v18 · council"; `v18` with an id beginning `SC-` → "session caller · v18", and no PAPER beside it;
  `NQ-EA` → "NRTR EA"; `mt5` → "MT5 EA sensor"; any other word printed as sent; empty → "sender not stated".
  The id names nobody: a `PB-` id under system `mt5` is the EA sensor's.
- **No council word beside an EA's row.** The signal information read "approved by the brain council" for any
  approved row; for a row that is not `v18` that stage now reads NOT RECORDED — "not judged by the council — this
  is the NRTR EA's own post".
- **Reward ÷ risk to TP1** is printed on the plan card from the row's own `entry`, `sl` and `tp1`.
- **The signal tables have a Sender column**, and the chart's Entry / SL / TP lines name the sender of the signal
  they are drawn from.
- **Not done:** we did not add `?system=v18` to our read. With one list of 200 rows and the EAs posting several
  hundred plans a day, the brain's rows can fall off our list entirely, and then no brain plan is shown at all —
  the card says whose plan it shows, it cannot show one it did not receive. If Shyam wants the brain's newest plan
  always on the screen beside the EA's, we will read both lists once 5.234 is on the box. His word.
- **Your point 6** (a "win" on an EA row is "price reached TP1", not money) is printed on the EA's sender card, in
  the words your card carries in `outcome_is`.

## 2. The Performance tab — your cards replace the pooled win rate

Built against `GET /api/v1/sources/senders` as your `_B` describes it and as `signal_senders.py` writes it. The
cards, tables and lines are handed over untouched; the terminal adds no rate, total, rank or colour, prints
`planned_be` with the word "planned", `null` as UNKNOWN, and names four states that are not "no sender has posted":
NOT BUILT (404), STILL BEING COUNTED (`loaded` not true), your own `fault`, and NOT READ. The pooled "Win rate %"
from `/api/v1/stats` is gone from the tab whether or not your route is on the box.

## 3. `retired` — read

When a market answer carries `retired {since, reason}` the Market Watch row reads RETIRED with your date, and your
reason in its tooltip. `null` or no key retires nothing; our seven-day NO NEW BARS stays as the fallback.

## 4. A fault of ours, found by Shyam — for your record only

The Limit Checklist printed "Price now" from the last closed **4h** bar. At about 21:50 UTC it showed SILVER at
39.858 (the 18:00 close) while the market was at 41.351 — above the checklist's own stop — and still offered a sell
limit below the market. It now measures from the newest closed 1m bar. One word ("now") was carrying a four-hour-old
fact.

## 5. ACCOUNTS — Shyam's rule of today, and what we need from you

His words: **"If user do not add account then this account show — ok because demo account. If user add account
then only user account should show."**

As we read it: a visitor who has added no account of their own may see the demonstration account (acceptable only
because it is a DEMO account); a visitor who has added an account sees only their own accounts.

**The Terminal cannot apply this today.** It knows one thing about a visitor — that your `/chart/levels.json`
answered 200 for their cookie — and it reads accounts, trades, portfolio and statistics with ONE API key. So every
approved visitor sees the key owner's accounts, and we cannot tell the key owner from anyone else.

What would let us apply it, in the smallest form we can think of — the design is yours:

1. **One read route for the visitor's own session** (on your standard allow list, like the two chart routes), for
   example `GET /chart/accounts.json`: the rows of `/api/v1/accounts`, same shape, for the user the SESSION belongs
   to. An empty list is "this user has added no account".
2. **The same for the records the account tabs show**: that user's trades (the `/api/v1/trades` shape, with
   `status`), and their portfolio and statistics — or a statement from you that a standard user has none of these
   and the tabs should say so.

With them the Terminal's rule would be: visitor has own accounts → only theirs, everywhere; visitor has none →
the key owner's accounts **whose `trade_mode` is 0 (demo) only**, labelled "DEMONSTRATION ACCOUNT — not yours";
a key-owner account that is not demo is never shown to a visitor who does not own it.

**One thing to check on your side before then:** is any account under the Terminal's key owner a REAL one
(`trade_mode` 2)? Your note says the NRTR EAs run on a real account. If that account is among the key owner's rows,
every approved user can read its balance in the Terminal today.

## 6. Not in 2.14.0 — next, in this order

1. **The 60-second desk cache**, counted from when your answer arrived, with your `as_of` on the screen. It changes
   our acceptance run too (it re-reads a pair after 17 s today), so it gets its own release.
2. **The position card per asset** (`/api/v1/market/position`), printed with your `not_a_forecast` sentence, each
   row as it is, no score and no colour.

## 7. Unchanged

The chart label for the clock-change weeks: Shyam's word. The Limit Checklist guard on 1d and 4h: nothing new.
