# Forecasting studies — the plan (saved 2026-11-11, terminal 2.4.0)

Shyam's brief for the forecasting job, kept here so every later window works from the same text, followed by
what was found in the repository and the decisions taken before step 1. Nothing in this file is built yet.

## 1. State when the job started

- Deployed branch `claude/vibrant-albattani-kxhfwv`, on the box at `/srv/signalmesh-terminal`, served at
  `https://app.signalmesh.dev/terminal/`. Version 2.4.0, build 42; acceptance 29 instruments, 2022 checks,
  0 FAIL (witnessed by Shyam on the box, 2026-11-11). Platform (`sabuj14eu/Sniper-System`) prints 5.201.
- Work on a `claude/<name>` branch cut from the deployed branch; draft PRs INTO the deployed branch. A change
  reaches the box only after its PR is merged and the update line has been pasted.
- Shyam's own TradingView logic: branch `claude/brave-cannon-k75ujr` (PR #3), `pine/SMC_Metal_Hunter_V15_0.pine`,
  `pine/SMC_MH15_Plus.pine`, `pine/V15_NOTES.md`. Port that logic where it exists so the terminal agrees with
  his indicator; where the terminal must differ, say so and why. The Pine files are not changed.

## 2. The job

Forecasting studies in the chart's "indicators" drop-down. Every item is a separate ON/OFF entry, off by
default, remembered in the workspace, with its own analysis timeframe where that applies, bullish-only /
bearish-only / history options, and a method panel (how it is calculated, from which closed bars, when).

**One release per step. Each is merged, deployed and looked at by Shyam on production data before the next starts.**

1. **Forecast journal and scoring** — first, because everything else is judged by it.
   The terminal's OWN small store in a Docker volume of the terminal container; never SignalMesh's database,
   never a write to SignalMesh. Every forecast is recorded when it is first made: id, symbol, timeframe, module,
   direction, pattern, status, entry zone, SL, TP1, TP2, invalidation, horizon, the closed bar it was made on,
   method version. Append-only: a forecast is never edited after the fact. A scorer later marks each one from
   closed candles only — TP1 hit, TP2 hit, SL hit, invalidated, expired — with the bar that decided it. A Toolbox
   tab shows the record and hit rates per module / symbol / timeframe WITH sample size; under 20 is labelled
   luck, about 100 to judge. Backup and redeploy behaviour decided and documented (§5).
2. **Asset ranking table** and **daily forecast top / bottom lines.** The table like the rotation ladder: rank,
   asset, ADR used %, day move in % of ADR, state (moving up / down), what to do, and a "go trade" line naming
   the asset with most room. Forecast top and bottom as two lines on the chart, with how they are derived.
3. **Fibonacci extensions** and **anchored VWAP.**
4. **Wolfe wave**: five points, bullish and bearish, point-5 reversal zone, EPA and target line, invalidation,
   confirmation status. An incomplete pattern is never shown as confirmed.
5. **Elliott wave** and **volume profile.** Elliott: impulse 1-5, corrective A-B-C, extensions, Fibonacci
   retracement / extension targets, a bullish count AND a bearish alternative, invalidation level per count.
   When the count is unclear it says UNKNOWN; never force one. Volume profile: SignalMesh stores MT5 TICK
   volume, not traded volume — labelled as tick-volume activity everywhere it appears.

### Forecast panel (grows with each step)

Per module, separate bullish and bearish scenarios: direction, pattern, entry, SL, TP1, TP2, risk/reward,
invalidation, expected horizon, confidence, status (developing / confirmed / invalidated). Outlooks: daily,
weekly, monthly, 3-month, 6-month ONLY where enough higher-timeframe history is stored; otherwise UNKNOWN.
Long-term targets come from higher-timeframe structure. Price levels are marked CALCULATED and time horizons
ESTIMATES. Confidence is never an invented number: it is either a stated rule (e.g. how many conditions of the
pattern are met) or, once the journal has enough history, the measured hit rate with its sample size. Until
then it reads UNKNOWN.

## 3. Laws (binding)

- **Read-only toward SignalMesh**: GET only. No change to its engine, signals, database, MT5 reporter, Telegram
  or execution. Nothing in Sniper-System changes in this job.
- **Display-only studies**: they generate no production BUY/SELL signal, change no SignalMesh decision, entry,
  SL, TP or statistic, and place no order. Every entry / SL / TP they show is labelled HYPOTHETICAL ANALYSIS
  LEVEL. Execution stays disabled.
- **Closed candles only. No lookahead. Confirmed patterns do not repaint**: each module gets a prefix test like
  `adapter/tests/test_smc.py`, run on seeded series AND on recorded Gold and Silver history. Status only moves
  forward and names its bar.
- Missing data or an unclear pattern is UNKNOWN / NOT AVAILABLE, never a guess.
- Engine facts and terminal studies are always labelled as different things.
- Any future link to the SignalMesh engine needs months of journal evidence and Shyam's explicit approval. It
  is not proposed in this job.

## 4. Workflow

- `scripts/check.sh` before every push. `VERSION` and `docs/RELEASES.md` bumped together (tests enforce it).
- Draft PR into the deployed branch; when CI is green tell Shyam and wait for his "merge it"; after the merge:

      cd /srv/signalmesh-terminal && git pull && scripts/setup.sh && scripts/acceptance.sh && scripts/screenshots.sh

  It must end with `0 FAIL`, and the toolbar must show the new version. A merged PR is not a deployed release.
- Screenshots shown to Shyam say what they are: PRODUCTION DATA only from the box's `screenshots.sh`; anything
  from a sandbox says LOCAL / TEST FIXTURES.
- Each new study is added to `web/e2e/workspace.mjs` and to `scripts/screenshots.sh`.
- Token economy: nothing happens unless Shyam has written; no scheduled check-ins; a PR is subscribed to only
  while its CI runs; small steps, short replies in plain English, one command block per step.

## 5. Decisions taken before step 1 (approved by Shyam, 2026-11-11)

Shyam approved: the read-only Gold and Silver export (M15, H1, H4, D1; account numbers removed; broker candle
boundaries kept), server-side recording at every closed bar for every instrument, and starting with an empty
journal. His seven journal requirements — record every eligible forecast including losses; targets, invalidation
and expiry fixed before recording; never change a forecast afterwards; separate Gold and Silver statistics;
forecast ids and the complete outcome history preserved; backup before every deployment; journal writes isolated
from the SignalMesh database — are each tied to a test in `docs/VERIFICATION.md`, "Forecast journal".
Built in release 2.5.0; the exact rules as built are in `docs/DATA_CONTRACT.md`, "journal-v1 / score-v1".

One thing was added while building: a forecast recorded later than its own bar (the terminal was down, or a
new study reads stored history on its first day) is kept and labelled BACKFILL, and its hit rate is shown
apart from the LIVE one. Nothing is dropped and the two are never mixed.

**The journal's home.** One SQLite file, `/data/journal.sqlite`, in a named Docker volume (`terminal_journal`)
mounted only into the `signalmesh-terminal` container. SQLite rather than JSONL because the scorer and the
hit-rate tab need queries, and because the database itself can refuse edits: `forecasts` and `outcomes` are two
tables with triggers that reject every UPDATE and DELETE. A forecast row is written once; its result is a
separate row in `outcomes` naming the deciding bar. Python's built-in `sqlite3` — no new dependency, no
connection string, no network. One uvicorn worker is the only writer (already a law).

**Why it cannot touch SignalMesh.** The store is a local file path, not a URL; the SignalMesh provider stays
GET-only and `test_read_only.py` keeps proving it. That test today also says "no database at all": it will be
narrowed in step 1 to "no SignalMesh database, no ORM, no write verb; the journal module is the only code that
opens a file for writing, and only under the journal directory".

**Redeploy.** `docker compose up -d --build` (what `setup.sh` does) replaces the container and keeps the named
volume, so the journal survives every release. Only `docker compose down -v` or `docker volume rm` deletes it;
neither is in any script. A schema change is an added table or column, never a rewrite of old rows.

**Backup.** `setup.sh` takes a consistent copy (SQLite's own backup call) into
`/srv/signalmesh-terminal/backups/journal-<UTC time>-v<version>.sqlite` before each rebuild, refuses to
rebuild if that copy fails, and keeps the last 30. `scripts/journal_backup.sh` does the same on demand. The folder is git-ignored. Copying it off the box is
Shyam's choice.

**Who records.** A forecast must be recorded whether or not anyone is looking at the chart, otherwise the
record only holds the patterns someone chose to watch and the hit rate is flattered. So the adapter records
server-side at each bar close, for every instrument SignalMesh stores, on a fixed list of timeframes per
module — not from the browser. Step 1 ships the store, the scorer and the tab with no module writing to it
yet: the tab will read "0 forecasts" on production until step 2. The scorer is proven by tests in step 1.

**Scoring rules** (fixed in step 1, versioned as `score-v1`): only bars that closed after the forecast's own
bar count; entry must be touched before SL/TP count; a bar that touches both SL and TP is scored SL (the worse
case — the order inside a bar is unknown); TP2 implies TP1; a close beyond the invalidation level before entry
is INVALIDATED; past the horizon with no result is EXPIRED. Status only moves forward.

**Confidence before there is evidence.** UNKNOWN, with the rule count beside it where a module has one
("4 of 5 conditions met" is a count, not a probability). The measured hit rate replaces UNKNOWN per
module / symbol / timeframe only from 20 scored forecasts (labelled "small sample — could be luck") and is
called judgeable from about 100.

## 6. What the V15 Pine files contain, and what they do not

| Study | In Pine | Port |
|---|---|---|
| Rotation ladder | `SMC_MH15_Plus.pine` §13H: ADR = mean range of the last 14 COMPLETED days; used % = today's range / ADR; move = (close − yesterday's close) / ADR; states FRESH < 35 % ≤ MOVING UP/DOWN < 85 % ≤ NEAR FULL < 100 % ≤ DONE; action text per state; score = (room × 0.5 + min(\|move\|, 60)) × (1 in its session, else 0.5); GO TRADE = highest score | As written, same thresholds and wording |
| Daily forecast top / bottom | `SMC_Metal_Hunter_V15_0.pine` §13D: top = day low + ADR, bottom = day high − ADR, snapped to HTF resistance / previous-day high (support / low) within an ATR tolerance; a side already exceeded becomes the day's extreme and reads "TOP IN / BOTTOM IN (ADR FULL)" | As written |
| Wolfe wave | main script §27: last 5 alternating pivots (strength 10), wedge rules for bull and bear, point 5 within 15 % of pattern height of line 1-3, apex = where 1-3 and 2-4 meet, TP1 = point 4, TP2 = EPA (line 1→4 at the apex), SL = point 5 ∓ 0.5 ATR, expiry after the apex | As written, plus the developing / confirmed states the brief asks for |
| Elliott wave | PLUS §27B: impulse count on the last 6 alternating pivots (strength 8), the four impulse rules, stages wave-3 setup / wave-4 zone / wave-5 targets / 5 done with 38.2 % and 61.8 % correction levels, invalidation per stage | The impulse rules and targets as written |
| My key levels, event mode | PLUS §13G, §13F | Not in the five steps; key levels are hand-typed inputs |

**Not in Pine, so the terminal's own method (and labelled as such):** Fibonacci extension tool, anchored VWAP,
volume profile; for Elliott — labelled A-B-C legs, wave extensions, and a bearish alternative shown beside the
bullish count (Pine keeps one count at a time and says "no clear count" otherwise).

**Where the terminal must differ from Pine, and why:**

- **The day.** TradingView's OANDA day starts 17:00 New York. The terminal uses SignalMesh's stored daily
  bars, which are the broker's MT5 server day. ADR, "today's range" and previous-day levels can differ by the
  hours between the two day starts. The method panel states which day is used.
- **Today's range.** Pine reads the running daily bar. The terminal has closed bars only, so today's high and
  low are built from closed intraday bars since the stored day opened, and say through which bar.
- **Elliott's newest pivot.** Pine replaces the newest pivot when a more extreme one of the same kind prints.
  That is causal, but the count's last point moves. The terminal keeps that and shows such a count as
  DEVELOPING; only a count whose pivots are all final is CONFIRMED and journalled as such.
- **Symbols.** Pine's ladder is seven fixed TradingView symbols. The terminal ranks the instruments SignalMesh
  stores (the terminal adds none); one without enough daily history reads NOT AVAILABLE.
- **Entries.** Pine's Wolfe entry is the close of the detecting bar. Same here, labelled HYPOTHETICAL ANALYSIS
  LEVEL, and it is an input to nothing.

## 7. How "no lookahead, no repaint" is proven

The pattern of `adapter/tests/test_smc.py`, per module: analyse every prefix of a series; each structure the
prefix reports as confirmed must appear unchanged in the full analysis, and the full analysis must contain no
confirmed structure dated inside the prefix that the prefix did not report. Status may only move forward, and
each move names its bar. Run on seeded random series and on recorded Gold and Silver history. For the journal
the same idea is stronger: a row is written once at the bar it names and the database refuses to change it.

**Open at the time of writing:** the repository holds no recorded market history — `candles_gold_15m.json` is
five synthetic bars and there is no Silver file. The recorded-history half of the test needs real closed bars
exported from the box, read-only, with the account number removed from each candle's `source`:
`scripts/export_history.sh`.

**Changed in 2.5.1 (Shyam's rule):** the repository is public and the box only pulls, so recorded history is
never committed and never sent. The export stays in the git-ignored `history-export/` on the box; each
module's recorded-history prefix check runs there, inside the terminal container (`scripts/history_check.py`),
and prints a summary Shyam pastes back. Seeded-series prefix tests stay in the repository and CI.

## 8. What stays UNKNOWN / NOT AVAILABLE

- Confidence, until a module has 20 scored forecasts (then "small sample"), judgeable from about 100.
- Weekly, monthly, 3-month and 6-month outlooks wherever the stored daily history is too short to carry the
  structure they need; SignalMesh stores no weekly or monthly bars, they are aggregated from closed daily bars.
- An Elliott count that fails a rule or fits two ways; a Wolfe wedge with fewer than five confirmed points.
- Traded volume: never available. Only MT5 tick volume, always labelled tick-volume activity.
- Anything on a timeframe SignalMesh does not store for that symbol.
- Whether any of this is profitable: unknown until the journal says so, with its sample size.
