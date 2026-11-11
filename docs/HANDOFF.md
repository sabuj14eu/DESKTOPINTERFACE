# HANDOFF — the SignalMesh Terminal window (V2 written 2026-11-10, platform 5.200)

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
| Work branch | `claude/terminal-v2-ui-redesign-qjkzig`, PRs **into the deployed branch**; a change reaches the box only after its PR is merged (2.1.0 = PR #4, merged 2026-11-11) |
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
- **Forecasting studies (journal and scoring, asset ranking and daily forecast, Fibonacci and anchored VWAP, Wolfe, Elliott and volume profile): the plan, laws and decisions are in `docs/FORECASTING_PLAN.md`. One release per step. Step 1 (journal and scoring) is release 2.5.0; steps 2–5 are not built.**
- More indicators, separate indicator panes, saved chart templates, several charts side by side (terminal window, on request).
- Engine-side swing-points route if Pine-like structure drawing is wanted (platform window, after the comparison period).

## 7. Paste this as the first message of a new terminal window

> You are continuing the SignalMesh TERMINAL window: repository `sabuj14eu/DESKTOPINTERFACE`. V1 is branch
> `claude/vibrant-albattani-kxhfwv` (draft PR #1), deployed at `/srv/signalmesh-terminal` and served at
> https://app.signalmesh.dev/terminal/ behind the SignalMesh login. V2 (flexible workspace, MT5 look, phone
> layout, signal information, broker accounts, dark execution adapters) is branch
> `claude/terminal-v2-ui-redesign-qjkzig`, with PRs into the V1 branch; 2.1.0 was merged and witnessed in
> production on 2026-11-11. The toolbar says which version runs; a merged PR is not a deployed release. Read, in this order: `docs/HANDOFF.md`, `README.md`,
> `docs/DATA_CONTRACT.md`, `docs/VERIFICATION.md`, `docs/PLATFORM_READ_ROUTES.md`, `docs/EXECUTION_ROADMAP.md`, and in `sabuj14eu/Sniper-System`
> `CLAUDE.md` and `docs/HANDOFF_PLATFORM_SESSION.md` §15. Laws: GET-only, nothing recalculated, freshness
> carried, per-candle source is the authority, two clocks shown, expired never current, one worker one cache,
> pins restrict never add, discovery never poisons live keys, the terminal adds no instrument, a signal is not
> a trade and is never linked to one by resemblance, broker figures are the broker's and are never summed,
> split or derived, missing means NOT AVAILABLE or UNKNOWN, the account number stays on the server, indicators
> are display-only, execution disabled until the roadmap's gates. Workflow: `scripts/check.sh` before every
> push (adapter pytest, tsc, vitest, build, write-verb audit, Playwright `switch.mjs` and `workspace.mjs`
> against the fixture adapter), push the branch, let CI wake you; Shyam pastes ONE update line on the box —
> `cd /srv/signalmesh-terminal && git pull && scripts/setup.sh && scripts/acceptance.sh` — and it must end with
> 0 FAIL. No prompts, no pasted keys, nothing complex. Confirm by telling me in seven lines: where the terminal
> runs and how it signs in; whether V2 is merged and deployed; what acceptance proves and its last counts; the
> first thing to witness; what the account panel shows when SignalMesh has no per-account route and what would
> change that; the one chart feature deliberately not drawn and why; and the phase that stays off. Then wait
> for my first task.
