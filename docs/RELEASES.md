# SignalMesh Terminal — release history

The newest release is first. Its number is the one in `VERSION`; a test fails if the two differ
(`adapter/tests/test_build_identity.py`). The terminal shows this number together with the build number,
git commit, environment and deployment time, all read from the build itself — see "Version identification"
in `README.md`. The same history is shown inside the terminal: click the version in the toolbar.

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
- Not yet deployed or verified in production.
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
