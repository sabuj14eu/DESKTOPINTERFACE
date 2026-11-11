# SignalMesh Terminal — release history

The newest release is first. Its number is the one in `VERSION`; a test fails if the two differ
(`adapter/tests/test_build_identity.py`). The terminal shows this number together with the build number,
git commit, environment and deployment time, all read from the build itself — see "Version identification"
in `README.md`. The same history is shown inside the terminal: click the version in the toolbar.

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
