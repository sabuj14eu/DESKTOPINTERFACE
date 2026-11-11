#!/usr/bin/env python3
"""PHASE 3 — PARITY CHECK: does the terminal show exactly what the engine says?

Reads the SAME instant from both sides:
  * SignalMesh directly   (/api/v1/..., the engine's own mirror, with the API key)
  * the terminal adapter  (/api/terminal/..., what the UI renders)
and compares every displayed price, entry, SL, TP, status and freshness field by
field. Any difference is a FAIL with both values printed. Exit code 1 on any FAIL.

Usage:
  SM_URL=https://app.yourdomain.com SM_KEY=bb_... TERM_URL=http://127.0.0.1:8090 \
  [TERM_TOKEN=...] [SM_SESSION_COOKIE=<bb_session value>] python3 scripts/verify_parity.py [SYMBOL ...]

SM_SESSION_COOKIE (optional) is the value of the `bb_session` cookie of a logged-in
SignalMesh browser session. With it, the script ALSO reads the OLD DASHBOARD's own
chart JSON (/chart/candles.json, /chart/levels.json — the routes the /chart page
draws from) and compares them with the terminal: same symbol, same timeframe,
same bar timestamps. That is the acceptance test "old dashboard vs new terminal".

A SOURCE AUDIT runs too: every candle's per-candle `source` must be an MT5
reporter feed (`mt5:<login>`); anything else is a FAIL, so fixture or bridge
data can never pass as broker data.

Read-only: GET only, on both sides.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime

SM = os.environ.get("SM_URL", "http://127.0.0.1:8000").rstrip("/")
KEY = os.environ.get("SM_KEY", "")
TERM = os.environ.get("TERM_URL", "http://127.0.0.1:8090").rstrip("/")
TOKEN = os.environ.get("TERM_TOKEN", "")
COOKIE = os.environ.get("SM_SESSION_COOKIE", "")
LOGIN = os.environ.get("SM_LOGIN", "")          # dashboard email/phone: the script logs in itself (password asked, hidden)
ALLOW_FIXTURE = os.environ.get("ALLOW_FIXTURE_SOURCE", "") == "1"   # local verification only
SYMBOLS = sys.argv[1:]          # empty = every instrument the terminal discovered (see below)
TFS = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]

fails = 0
checks = 0


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def get(url: str, headers: dict) -> dict | list:
    req = urllib.request.Request(url, headers={"Accept": "application/json", **headers})
    try:
        with _opener.open(req, timeout=60) as r:
            body = r.read()
            ctype = r.headers.get("content-type", "")
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308):
            raise RuntimeError(f"redirected to {e.headers.get('Location')} — the session cookie was not accepted (log in again and copy the bb_session VALUE exactly)") from None
        raise RuntimeError(f"HTTP {e.code}: {e.read()[:120]!r}") from None
    if "json" not in ctype:
        raise RuntimeError(f"non-JSON answer ({ctype or 'no content-type'}): {body[:80]!r} — for dashboard routes this means the cookie was not accepted")
    return json.loads(body)


def sm(path: str, **q):
    return get(f"{SM}{path}?{urllib.parse.urlencode(q)}" if q else f"{SM}{path}", {"Authorization": f"Bearer {KEY}"})


def dashboard_login(identifier: str) -> str:
    """Log in to SignalMesh exactly as the browser does (POST /login) and return the
    bb_session cookie. The password is asked on the terminal, hidden, and never
    stored; the session lives only in this process. Read-only use afterwards."""
    import getpass
    import http.cookiejar

    pw = getpass.getpass(f"   SignalMesh password for {identifier} (hidden): ")
    totp = os.environ.get("SM_TOTP", "")
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPCookieProcessor(jar))
    data = urllib.parse.urlencode({"phone": identifier, "password": pw, "totp": totp}).encode()
    req = urllib.request.Request(f"{SM}/login", data=data, method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        opener.open(req, timeout=60)
    except urllib.error.HTTPError as e:
        if e.code not in (301, 302, 303, 307, 308):
            sys.exit(f"login failed: HTTP {e.code}")
        loc = e.headers.get("Location", "")
        if "login" in loc or "2fa" in loc or "totp" in loc:
            sys.exit(f"login not accepted (redirected to {loc}); if 2FA is enabled set SM_TOTP=<current code>")
    for c in jar:
        if c.name == "bb_session":
            return c.value
    sys.exit("login not accepted — no bb_session cookie came back (wrong password? if 2FA is enabled set SM_TOTP=<current code>)")


def dash(path: str, **q):
    """The OLD dashboard's own JSON routes (session cookie)."""
    return get(f"{SM}{path}?{urllib.parse.urlencode(q)}", {"Cookie": f"bb_session={COOKIE}"})


def term(path: str, **q):
    # the terminal accepts the operator's SignalMesh read key (same login as SignalMesh otherwise)
    h = {"X-Terminal-Key": KEY}
    if TOKEN:
        h["X-Terminal-Token"] = TOKEN
    return get(f"{TERM}{path}?{urllib.parse.urlencode(q)}" if q else f"{TERM}{path}", h)


AREAS: dict[str, list[int]] = {}        # section name -> [checks, fails], for the release-gate table at the end
RESULTS: list[tuple[str, bool]] = []     # every check, for the per-combination matrix
NOT_TESTED: list[str] = []              # what this run could not test, said rather than counted as a pass
_AREA = ["start"]
_print = print


def print(*a, **k):                     # noqa: A001 — a "== section ==" line names the area the following checks belong to
    if a and isinstance(a[0], str) and a[0].lstrip("\n").startswith("== "):
        _AREA[0] = a[0].strip().strip("=").strip()
    _print(*a, **k)


def check(label: str, engine, terminal, tol: float = 0.0):
    global fails, checks
    checks += 1
    AREAS.setdefault(_AREA[0], [0, 0])[0] += 1
    ok = engine == terminal
    if not ok and isinstance(engine, (int, float)) and isinstance(terminal, (int, float)):
        ok = abs(float(engine) - float(terminal)) <= tol
    print(f"  {'OK  ' if ok else 'FAIL'} {label}: engine={engine!r} terminal={terminal!r}")
    RESULTS.append((label, ok))
    if not ok:
        fails += 1
        AREAS[_AREA[0]][1] += 1


def ts_epoch(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


if LOGIN and not COOKIE:
    COOKIE = dashboard_login(LOGIN)
    print(f"   logged in to {SM} as {LOGIN}; dashboard comparison enabled")

# ── INSTRUMENT DISCOVERY: every instrument the terminal lists must be one SignalMesh knows,
#    and its per-timeframe availability must equal what the engine stores.
print("\n== instruments ==")
inst = term("/api/terminal/instruments")
for _ in range(3):
    # a read of SignalMesh that failed while the list was built is not "no candles": the terminal
    # says so (complete=false) and asks again after 15 s — wait for the complete list
    if inst.get("complete", True):
        break
    print(f"  NOTE instrument list incomplete ({'; '.join(inst.get('failed_reads') or [])[:200]}) — reading again in 16 s")
    time.sleep(16)
    inst = term("/api/terminal/instruments")
check("instrument list is complete (no failed read of SignalMesh in it)", True, inst.get("complete", True))
engine_universe = {r["symbol"] for r in (sm("/api/v1/news/state").get("rows") or [])} | {s["symbol"] for s in sm("/api/v1/signals", limit=200)}
for i in inst["instruments"]:
    # legitimate origins: SignalMesh's DEFAULT_SYMBOLS, a signalled symbol, or SignalMesh's own symbol table
    legit = i["symbol"] in engine_universe or any("platform symbol table" in o for o in i["origins"])
    check(f"instrument {i['symbol']} is known to SignalMesh (DEFAULT_SYMBOLS, signals or its symbol table)", True, legit)
    for tf in TFS:
        e = sm("/api/v1/market/candles", symbol=i["symbol"], tf=tf, n=1)
        check(f"instrument {i['symbol']} {tf} availability", e["count"] > 0, tf in i["timeframes"])
    check(f"instrument {i['symbol']} available == has any timeframe", bool(i["timeframes"]), i["available"])
check("market watch == every available instrument", sorted(inst["watch"]), sorted(r["symbol"] for r in term("/api/terminal/market-watch")["rows"]))
avail_all = [i["symbol"] for i in inst["instruments"] if i["available"]]
print(f"  NOTE instruments with stored candles: {' '.join(avail_all) or 'NONE'}")
if inst.get("pinned"):
    hidden = [s for s in avail_all if s not in inst["watch"]]
    print(f"  NOTE SMT_SYMBOLS pins restrict the market watch to: {' '.join(inst['watch'])}" + (f" — HIDDEN although they have candles: {' '.join(hidden)}" if hidden else ""))
print(f"  NOTE discovered but without candles: {' '.join(i['symbol'] for i in inst['instruments'] if not i['available']) or 'none'}")
if not SYMBOLS:
    SYMBOLS = inst["watch"]

def _symbol(sym: str) -> None:
    global checks, fails
    print(f"\n== {sym} ==")
    # 1. candles: every bar identical, same count, same freshness state
    for tf in TFS:
        e = sm("/api/v1/market/candles", symbol=sym, tf=tf, n=100)
        t = term("/api/terminal/candles", symbol=sym, tf=tf, n=100)
        check(f"candles {tf} count", e["count"], t["count"])
        if e["count"] == 0:
            print(f"  NOTE candles {tf}: SignalMesh stores none for {sym} (reporter BB_CANDLE_TFS) — terminal shows it as unavailable")
            continue
        check(f"candles {tf} freshness", e["freshness"]["state"], t["freshness"]["state"])
        for ec, tc in zip(e["candles"], t["candles"]):
            if ts_epoch(ec["ts"]) != tc["time"] or any(ec[k] != tc[k] for k in ("open", "high", "low", "close")):
                check(f"candles {tf} bar {ec['ts']}", {k: ec[k] for k in ("open", "high", "low", "close")}, {k: tc[k] for k in ("open", "high", "low", "close")})
                break
        else:
            checks += 1
            print(f"  OK   candles {tf}: all {len(t['candles'])} bars identical (ts, o, h, l, c)")
    # 1b. SOURCE AUDIT — provenance is the per-candle source, never the platform's label
    e1m = sm("/api/v1/market/candles", symbol=sym, tf="15m", n=50)
    kinds = sorted({str(c.get("source") or "").split(":")[0] or "<unstated>" for c in e1m["candles"]})
    ok_src = kinds == ["mt5"] or (ALLOW_FIXTURE and kinds and all(k in ("mt5", "fixture") for k in kinds))
    check(f"source audit 15m: per-candle sources are MT5 reporter feeds", ["mt5"], kinds) if not ALLOW_FIXTURE else print(f"  NOTE source audit 15m: kinds {kinds} (ALLOW_FIXTURE_SOURCE=1, local verification)")
    t15 = term("/api/terminal/candles", symbol=sym, tf="15m", n=50)
    check("terminal labels the source kind from the per-candle source", "mt5_reporter" if kinds == ["mt5"] else t15["source_kind"], t15["source_kind"])
    if not ok_src and not ALLOW_FIXTURE:
        print("       -> the engine's static label says MT5, but the candles themselves do not. This is NOT broker data.")
    # 2. decision: plan verbatim
    e = sm("/api/v1/market/snapshot", symbol=sym)
    t = term("/api/terminal/decision", symbol=sym)
    ed = e["snapshot"]["decision"]
    for k in ("status", "order_type", "entry", "sl", "tp1", "tp2", "rr1", "rr2", "grade", "reason", "why", "conflicts", "lifecycle", "distance_atr"):
        tk = "engine_status" if k == "status" else k
        check(f"decision.{k}", ed.get(k), t.get(tk))
    em = e["snapshot"]["market"]
    check("market.last_close", em.get("last_close"), t.get("last_close"))
    check("market.atr", em.get("atr"), t.get("atr"))
    check("market.structure", em.get("structure"), t.get("structure"))
    check("market.validated_bias", em.get("validated_bias"), t.get("bias"))
    check("market.last_bar_ts", em.get("last_bar_ts"), t.get("last_bar_ts"))
    for k, v in e["snapshot"]["freshness"].items():
        check(f"freshness.{k}", v["state"], t["freshness"][k]["state"])
    check("news.risk", e["snapshot"]["news"]["risk"], t["news_risk"])
    # 2b. price contract: header price = newest closed 1m bar; engine reference = snapshot's 15m bar
    pc = t["price"]
    if pc.get("engine_reference"):
        check("price.engine_reference = snapshot.market.last_close", em.get("last_close"), pc["engine_reference"]["price"])
        check("price.engine_reference bar = snapshot.market.last_bar_ts", em.get("last_bar_ts"), pc["engine_reference"]["bar_open_ts"])
    if pc.get("last_closed_1m"):
        # JOIN ON BAR TIMESTAMP, never newest-against-newest: the reporter lands a new 1m bar once a
        # minute and the terminal may lag the engine by its 15 s cache, so the two "newest" bars can
        # legitimately differ by one minute. Same bar -> same close is the parity claim; how far the
        # terminal's bar may trail the engine's newest is a separate freshness claim (<= 3 bars).
        e1 = sm("/api/v1/market/candles", symbol=sym, tf="1m", n=8)
        tb = pc["last_closed_1m"]
        if e1["candles"]:
            match = next((c for c in e1["candles"] if ts_epoch(c["ts"]) == ts_epoch(tb["bar_open_ts"])), None)
            check(f"price.last_closed_1m (header) bar {tb['bar_open_ts'][11:16]} exists in engine", True, match is not None)
            if match:
                check("price.last_closed_1m close = engine close of the SAME bar", match["close"], tb["price"])
            lag = (ts_epoch(e1["candles"][-1]["ts"]) - ts_epoch(tb["bar_open_ts"])) // 60
            check("price.last_closed_1m trails the engine's newest 1m bar by <= 3 bars (freshness)", True, 0 <= lag <= 3)
    # 2c. expired plans are never current levels
    if t.get("expired_plan"):
        check("expired plan is not drawn as a current level", True, all(l["origin"] != f"signal {t['expired_plan']['signal']['signal_id']}" for l in t["levels"]))
        check("expired plan is past the 12h lifecycle", True, (t["expired_plan"]["signal"]["age_h"] or 0) > 12)
    # 2d. BUY / SELL side states derive from the engine status only
    sides = t["sides"]
    if ed.get("status") == "READY":
        d0 = (ed.get("order_type") or "").split(" ")[0]
        check(f"side {d0} READY when plan READY", "READY", sides[d0]["state"])
    elif ed.get("status") == "NO TRADE":
        check("both sides INVALID on NO TRADE", ["INVALID", "INVALID"], [sides["BUY"]["state"], sides["SELL"]["state"]])
    else:
        check("no side READY unless the plan is READY", False, any(v["state"] == "READY" for v in sides.values()))
    # 3. levels drawn on the chart come from the engine's own signal
    if t["levels"]:
        origin = t["levels"][0]["origin"]
        if origin == "plan":
            for l in t["levels"]:
                check(f"chart level {l['key']} (plan)", ed.get(l["key"]), l["value"])
        else:
            sid = origin.split(" ", 1)[1]
            sig = next((s for s in sm("/api/v1/signals", limit=200) if s["signal_id"] == sid), None)
            check(f"chart levels signal {sid} exists in engine", True, sig is not None)
            if sig:
                for l in t["levels"]:
                    check(f"chart level {l['key']} ({sid})", sig.get(l["key"]), l["value"])
    # 4. market-watch price = last closed 1m bar from the engine
    mw = next((r for r in term("/api/terminal/market-watch")["rows"] if r["symbol"] == sym), None)
    e1 = sm("/api/v1/market/candles", symbol=sym, tf="1m", n=8)
    if mw and e1["candles"]:
        m2 = next((c for c in e1["candles"] if ts_epoch(c["ts"]) == ts_epoch(mw["price_ts"])), None) if mw.get("price_ts") else None
        check("market-watch bar exists in engine", True, m2 is not None)
        if m2:
            check("market-watch price = engine close of the SAME 1m bar", m2["close"], mw["price"])
        lag2 = (ts_epoch(e1["candles"][-1]["ts"]) - ts_epoch(mw["price_ts"])) // 60 if mw.get("price_ts") else 99
        check("market-watch bar trails the engine's newest by <= 3 bars (freshness)", True, 0 <= lag2 <= 3)
        check("market-watch change = engine session_change_pct", em.get("session_change_pct"), mw["change_pct"])

    # 6. OLD DASHBOARD vs NEW TERMINAL (same symbol, timeframe, bar timestamps)
    if COOKIE:
        for tf, dtf in (("15m", "15"), ("1h", "60")):
            try:
                dj = dash("/chart/candles.json", symbol=sym, tf=dtf, n=100)
            except Exception as exc:  # noqa: BLE001
                check(f"dashboard /chart/candles.json {tf} readable", True, f"{type(exc).__name__}: {exc}")
                continue
            tj = term("/api/terminal/candles", symbol=sym, tf=tf, n=400)
            tmap = {c["time"]: c for c in tj["candles"]}
            feed = dj.get("feed") or dj.get("state") or "?"
            drows = dj.get("candles") or []
            print(f"  NOTE dashboard chart {tf}: feed={feed} state={dj.get('state')} bars={len(drows)} (live bridge bars may include a FORMING bar; the terminal draws closed bars only)")
            compared = mism = 0
            for c in drows:
                ts = c.get("ts") or c.get("time") or c.get("t")
                try:
                    k = int(ts) if isinstance(ts, (int, float)) else ts_epoch(str(ts))
                except Exception:  # noqa: BLE001
                    continue
                if k in tmap:
                    compared += 1
                    o, h, l, cl = (c.get(x) for x in ("open", "high", "low", "close")) if "open" in c else (c.get(x) for x in ("o", "h", "l", "c"))
                    if any(v is not None and abs(float(v) - tmap[k][n]) > 1e-9 for v, n in ((o, "open"), (h, "high"), (l, "low"), (cl, "close"))):
                        mism += 1
            check(f"dashboard vs terminal {tf}: OHLC identical on every shared bar ({compared} compared)", 0, mism)
        try:
            dl = dash("/chart/levels.json", symbol=sym)
        except Exception as exc:  # noqa: BLE001
            check("dashboard /chart/levels.json readable", True, f"{type(exc).__name__}: {exc}")
            dl = {}
        if dl.get("has"):
            dmap = {l["key"]: l["value"] for l in dl["lines"]}
            if dl.get("stale"):
                check(f"dashboard levels EXPIRED ({dl['signal_id']}) -> terminal shows them as history, not current", True,
                      (t.get("expired_plan") or {}).get("signal", {}).get("signal_id") == dl["signal_id"] and not any(l["origin"] == f"signal {dl['signal_id']}" for l in t["levels"]))
                for l in (t.get("expired_plan") or {}).get("levels", []):
                    check(f"dashboard vs terminal expired {l['key']}", dmap.get(l["key"]), l["value"])
            else:
                for l in t["levels"]:
                    if l["origin"] != "plan":
                        check(f"dashboard vs terminal level {l['key']}", dmap.get(l["key"]), l["value"])
        elif dl:
            check("dashboard has no live signal levels -> terminal draws no signal levels", True, not any(l["origin"] != "plan" for l in t["levels"]))



# A closed bar is re-read by the engine the moment it closes, and the terminal reuses one upstream answer for its
# cache lifetime. A symbol read exactly at a bar edge can therefore show the engine one bar ahead for a few seconds:
# the terminal's values are the engine's own from seconds earlier, not wrong ones. So a symbol that differs is read
# again — both sides — after the cache lifetime, and only a difference that SURVIVES is a FAIL.
import contextlib  # noqa: E402
import io  # noqa: E402

for sym in SYMBOLS:
    for _attempt in (1, 2):
        _c0, _f0, _buf = checks, fails, io.StringIO()
        with contextlib.redirect_stdout(_buf):
            _symbol(sym)
        if fails == _f0 or _attempt == 2:
            print(_buf.getvalue(), end="")
            break
        _n = fails - _f0
        checks, fails = _c0, _f0
        _ttl = float((term("/api/terminal/health").get("adapter", {}).get("cache", {}) or {}).get("ttl_s") or 15)
        print(f"\n  NOTE {sym}: {_n} value(s) differed on the first read (a bar closing between the two reads does this) — re-reading both sides after the terminal's {_ttl:g}s cache")
        time.sleep(_ttl + 2)

# 5. signals and trades: same ids, same levels, same statuses
print("\n== signals ==")
es = {s["signal_id"]: s for s in sm("/api/v1/signals", limit=200)}
ts_ = {s["signal_id"]: s for s in term("/api/terminal/signals", bucket="all")["rows"]}
check("signal ids identical", sorted(es), sorted(ts_))
_SIG_KEYS = ("symbol", "direction", "entry", "sl", "tp1", "tp2", "rr", "grade", "status", "confidence", "system", "tf")
_moved = [sid for sid, s in es.items() if ts_.get(sid) and any(s.get(k) != ts_[sid].get(k) for k in _SIG_KEYS)]
if _moved:
    # A signal's status MOVES (pending -> approved -> executed -> closed) and the terminal reuses one upstream
    # answer for its cache lifetime, so the two reads can straddle a change. One difference is not yet a fault:
    # wait out the cache, read BOTH sides again, and judge the second pair. A difference that survives is a FAIL.
    import time
    ttl = float((term("/api/terminal/health").get("adapter", {}).get("cache", {}) or {}).get("ttl_s") or 15)
    print(f"  NOTE {len(_moved)} signal(s) differed on the first read ({', '.join(_moved[:4])}{' …' if len(_moved) > 4 else ''}) — re-reading both sides after the terminal's {ttl:g}s cache")
    time.sleep(ttl + 2)
    es = {s["signal_id"]: s for s in sm("/api/v1/signals", limit=200)}
    ts_ = {s["signal_id"]: s for s in term("/api/terminal/signals", bucket="all")["rows"]}
for sid, s in es.items():
    t = ts_.get(sid)
    if not t:
        continue
    for k in _SIG_KEYS:
        if s.get(k) != t.get(k):
            check(f"signal {sid}.{k}", s.get(k), t.get(k))
checks += 1
print(f"  OK   {len(es)} signals compared field by field (differences, if any, listed above)")
print("\n== trades ==")
et = {t["id"]: t for t in sm("/api/v1/trades", limit=200)}
tt = {t["id"]: t for t in term("/api/terminal/trades", status="all")["rows"]}
check("trade ids identical", sorted(et), sorted(tt))
for i, t in et.items():
    u = tt.get(i)
    if u:
        for k in ("symbol", "direction", "lots", "entry", "exit", "sl", "tp", "status", "profit"):
            if t.get(k) != u.get(k):
                check(f"trade {i}.{k}", t.get(k), u.get(k))
print("\n== performance ==")
e = sm("/api/v1/stats")
t = term("/api/terminal/performance")["stats"]
for k in ("count", "wins", "losses", "win_rate", "profit_factor", "expectancy", "total_profit", "max_drawdown"):
    check(f"stats.{k}", e.get(k), t.get(k))

# 6. V2 — broker accounts: the terminal shows the broker figures SignalMesh holds, per account, never summed here
print("\n== accounts (V2) ==")
ACC_PATH = os.environ.get("SM_ACCOUNTS_PATH", "/api/v1/accounts")
p1 = sm("/api/v1/portfolio")
ta = term("/api/terminal/accounts")
p2 = sm("/api/v1/portfolio")
try:
    erows = sm(ACC_PATH)
    erows = erows.get("accounts") if isinstance(erows, dict) else erows
    print(f"  NOTE engine per-account route {ACC_PATH}: {len(erows)} row(s), keys: {', '.join(sorted({k for r in erows for k in r if k not in ('positions', 'orders')})) or 'none'}")
except RuntimeError as exc:
    erows = None
    print(f"  NOTE engine has no per-account route at {ACC_PATH} ({str(exc)[:60]}) — the terminal must show the portfolio total, labelled")


def moving(label, a, b, t):
    """A broker figure that may tick between two engine reads: the terminal's must lie between them."""
    if a is None or b is None or t is None:
        return check(label, a, t)
    lo, hi = min(a, b), max(a, b)
    check(label + (f" (engine moved {a}->{b})" if a != b else ""), True, lo - 1e-9 <= t <= hi + 1e-9) if lo - 1e-9 <= t <= hi + 1e-9 else check(label, a, t)


shown = ta["accounts"] + ta["disconnected"]
if erows is None:
    check("accounts mode is the labelled portfolio total", "PORTFOLIO_TOTAL", ta["mode"])
    n, on = int(p1.get("accounts") or 0), int(p1.get("online") or 0)
    check("one entry when SignalMesh reports accounts, none otherwise", 1 if n >= 1 else 0, len(shown))
    check("selectable only when an account is online", 1 if (n >= 1 and on >= 1) else 0, len(ta["accounts"]))
    if shown:
        a = shown[0]
        check("a total over several accounts is marked COMBINED", n > 1, a["combined"])
        for ek, tk in (("balance", "balance"), ("equity", "equity"), ("free_margin", "free_margin"), ("floating_pnl", "floating_pnl")):
            moving(f"account.{tk} = engine portfolio.{ek}", p1.get(ek), p2.get(ek), a[tk])
        for k in ("used_margin", "margin_level", "broker", "server"):
            check(f"account.{k} not in the portfolio -> NOT AVAILABLE (null), never computed", None, a[k])
        check("DEMO/LIVE not in the portfolio -> UNKNOWN", "UNKNOWN", a["environment"])
else:
    check("accounts mode is per account", "PER_ACCOUNT", ta["mode"])
    check("one terminal account per engine row", len(erows), len(shown))
    by_tail = {str(a.get("login_masked") or "")[-4:]: a for a in shown}
    for r in erows:
        login = str(next((r[k] for k in ("login", "account", "account_id") if r.get(k) not in (None, "")), ""))
        a = by_tail.get(login[-4:])
        if not a:
            check(f"engine account ••{login[-4:]} is shown", True, False)
            continue
        check(f"••{login[-4:]} balance", r.get("balance"), a["balance"], tol=0.005)
        check(f"••{login[-4:]} full account number is never sent to the browser", True, login not in json.dumps(ta) or len(login) <= 4)
        for ek, tk in (("margin", "used_margin"), ("margin_level", "margin_level")):
            if r.get(ek) is None and r.get(tk) is None:
                check(f"••{login[-4:]} {tk} not reported -> null", None, a[tk])
for a in ta["accounts"]:
    d = term("/api/terminal/account", id=a["id"])
    check(f"account {a.get('login_masked') or a['id']}: detail is the same account", a["id"], d["account"]["id"])
    if erows is None and not a["combined"]:
        et_open = sm("/api/v1/trades", status="open", limit=200)
        check("open positions = engine journal rows with status open", len(et_open), len(d["positions"]))
        et_pend = sm("/api/v1/trades", status="pending", limit=200)
        check("pending orders = engine journal rows with status pending", len(et_pend), len(d["orders"]))

# 7. V2 — a signal is a recommendation unless a broker journal row names it
print("\n== signals are not executions (V2) ==")
_tr = sm("/api/v1/trades", limit=200)
print(f"  NOTE engine trade rows carry: {', '.join(k + ('' if any(k in t for t in _tr) else ' (ABSENT)') for k in ('ticket', 'account_login', 'signal_id'))} — a signal can be tied to a broker trade only when signal_id is present")
linked = {str(t.get("signal_id")) for t in _tr if t.get("signal_id")}
for sid, s in list(es.items())[:25]:
    d = term(f"/api/terminal/signals/{urllib.parse.quote(sid)}")
    if d["is_broker_execution"] != (sid in linked):
        check(f"signal {sid} is a broker execution only when a journal row names it", sid in linked, d["is_broker_execution"])
    if d["origin"]["originating_engine"]["value"] != (s.get("system") or "UNKNOWN"):
        check(f"signal {sid} originating engine", s.get("system") or "UNKNOWN", d["origin"]["originating_engine"]["value"])
checks += 1
print(f"  OK   {min(len(es), 25)} signals: origin read from the engine row; none called an execution without a linked journal row (differences listed above)")
_lv = term("/api/terminal/live", symbol=(SYMBOLS[0] if SYMBOLS else "GOLD"), tf="15m")
print(f"  NOTE forming bar (display only, no browser login in this run): state {_lv.get('state')} · source {_lv.get('source')} · bridge {_lv.get('bridge_state', _lv.get('state'))}{' · ' + _lv['error'][:110] if _lv.get('error') else ''}")
check("a forming bar is never inside the closed series", True, not ({b["time"] for b in _lv.get("bars", [])} & {c["time"] for c in term("/api/terminal/candles", symbol=(SYMBOLS[0] if SYMBOLS else "GOLD"), tf="15m", n=20)["candles"]}))
_sm = term("/api/terminal/smc", symbol=(SYMBOLS[0] if SYMBOLS else "GOLD"), tf="15m")
print(f"  NOTE Smart Money Concepts (terminal display-only studies, not engine output): state {_sm.get('state')} · {_sm.get('bars_used')} closed 15m bars · "
      + " ".join(f"{k} {len(_sm.get(k) or [])}" for k in ("structure", "fvg", "order_blocks", "liquidity", "inducement", "sr")))
check("no study is dated after the last closed bar it used", True, all((r.get("confirmed_at") or 0) <= (_sm.get("through_close") or 0) for k in ("structure", "fvg", "order_blocks", "inducement") for r in (_sm.get(k) or [])))

# 8. forecast journal — the terminal's OWN store (never SignalMesh's database); append-only; scored from closed bars
print("\n== forecast journal (terminal study, own store) ==")
_j = term("/api/terminal/journal", limit=1000)
_st, _rc = _j.get("store") or {}, _j.get("recorder") or {}
print(f"  NOTE journal state {_j.get('state')} · {_st.get('forecasts')} forecasts · {_st.get('outcomes')} outcome marks · recorder {'running' if _rc.get('running') else 'NOT running'} · modules {', '.join(_rc.get('modules') or []) or 'none yet'}"
      + (f" · last pass errors: {'; '.join((_rc.get('last_pass') or {}).get('errors') or [])[:160]}" if (_rc.get("last_pass") or {}).get("errors") else ""))
check("the journal store is ready", "READY", _j.get("state"))
check("the journal is append-only (the database refuses edits and deletions)", True, _st.get("append_only"))
check("the server-side recorder is running", True, _rc.get("running"))
check("no test-fixture module records outside test fixtures", False, "fixture-demo" in (_rc.get("modules") or []) and not term("/api/terminal/health")["provider"]["is_fixture"])
check("every forecast has entry, SL, TP1, TP2, invalidation and horizon fixed", True, all(all(r.get(k) is not None for k in ("entry_low", "entry_high", "sl", "tp1", "tp2", "invalidation", "horizon_bars", "made_bar")) for r in _j["rows"]))
check("no outcome is dated at or before its forecast's own bar (ENTRY at close excepted)", True, all(o["bar"] > r["made_bar"] or (o["event"] == "ENTRY" and r["entry_mode"] == "at_close") for r in _j["rows"] for o in r["outcomes"]))
check("hit-rate groups add up and never pool symbols", True, all(g["recorded"] == g["open"] + g["never_entered"] + g["finished"] for g in _j["stats"]) and len({(g["module"], g["method_version"], g["symbol"], g["timeframe"], g["origin"]) for g in _j["stats"]}) == len(_j["stats"]))

# 9. forecasting studies — the terminal's own display-only studies, recomputed here from the ENGINE's closed candles
print("\n== forecasting studies (terminal studies: daily forecast, asset ranking) ==")
_inst = {i["symbol"]: i for i in term("/api/terminal/instruments")["instruments"]}
for _s in [x for x in (SYMBOLS or ["GOLD", "SILVER"]) if x in ("GOLD", "SILVER")] or (SYMBOLS or [])[:1]:
    _f = term("/api/terminal/forecast/daily", symbol=_s)
    if _f.get("state") != "OK":
        print(f"  NOTE {_s} daily forecast: {_f.get('state')} — {_f.get('note')}")
        continue
    _ed = sorted(sm("/api/v1/market/candles", symbol=_s, tf="1d", n=60)["candles"], key=lambda k: ts_epoch(k["ts"]))
    _ed = [k for k in _ed if ts_epoch(k["ts"]) < _f["day_start"]][-14:]
    _adr = sum(k["high"] - k["low"] for k in _ed) / len(_ed)
    check(f"{_s} ADR = mean range of the engine's last 14 completed daily bars", round(_adr, 6), round(_f["adr"], 6))
    _ei = [k for k in sm("/api/v1/market/candles", symbol=_s, tf=_f["intraday_tf"], n=500)["candles"] if _f["day_start"] <= ts_epoch(k["ts"]) <= _f["through_bar"]]
    check(f"{_s} today's high = highest closed {_f['intraday_tf']} bar since the broker day started", max(k["high"] for k in _ei), _f["day_high"])
    check(f"{_s} today's low = lowest closed {_f['intraday_tf']} bar since the broker day started", min(k["low"] for k in _ei), _f["day_low"])
    check(f"{_s} forecast top is never below today's high, bottom never above today's low", True, _f["top"] >= _f["day_high"] and _f["bottom"] <= _f["day_low"])
    check(f"{_s} unsnapped top = day low + ADR and bottom = day high - ADR", True, abs(_f["top_raw"] - (_f["day_low"] + _f["adr"])) < 1e-6 and abs(_f["bottom_raw"] - (_f["day_high"] - _f["adr"])) < 1e-6)
    check(f"{_s} every scenario level is labelled hypothetical and confidence is not a made-up number", True, all(x["level_label"] == "HYPOTHETICAL ANALYSIS LEVEL" and x["confidence"] == "UNKNOWN" for x in _f["scenarios"]))
    print(f"  NOTE {_s} daily forecast: broker day from {_f['day_start_utc']} · ADR {_f['adr']:.{_f['decimals']}f} · used {_f['used_pct']:.0f}% · top {_f['top']:.{_f['decimals']}f} · bottom {_f['bottom']:.{_f['decimals']}f} · {_f['status']} · scenarios {len(_f['scenarios'])} · "
          + " ".join(f"{k}:{v['state']}" for k, v in _f["outlooks"].items()))
_rk = term("/api/terminal/forecast/ranking")
check("the ranking lists every instrument in the market watch, once", sorted(term("/api/terminal/instruments")["watch"]), sorted(r["symbol"] for r in _rk["rows"]))
check("an instrument without enough history is NOT AVAILABLE, never ranked on a guess", True, all((r["rank"] is None) == (r["used_pct"] is None) for r in _rk["rows"]))
print(f"  NOTE asset ranking: {sum(1 for r in _rk['rows'] if r['rank'])} ranked, {sum(1 for r in _rk['rows'] if not r['rank'])} not available · {_rk['go_trade']}")
check("only the daily-forecast, Wolfe and Elliott modules record", True, set((term("/api/terminal/journal").get("recorder") or {}).get("modules") or []) <= {"daily-forecast", "wolfe-wave", "elliott-wave", "fixture-demo"})

# 10. pattern studies — Fibonacci extension, anchored VWAP, Wolfe, Elliott, volume profile: display only; Wolfe and Elliott are journalled.
#     Every price they are built on is looked up in the ENGINE's own closed candles, and the sums are redone here.
print("\n== pattern studies (terminal studies: Fibonacci, anchored VWAP, Wolfe, Elliott, volume profile) ==")
for _s in [x for x in (SYMBOLS or ["GOLD", "SILVER"]) if x in ("GOLD", "SILVER")] or (SYMBOLS or [])[:1]:
    for _tf in ("15m", "1h", "4h", "1d"):
        if _tf not in (_inst.get(_s, {}).get("timeframes") or []):
            print(f"  NOTE {_s} {_tf} pattern studies: NOT TESTED — SignalMesh stores no {_tf} bars for {_s}")
            NOT_TESTED.append(f"{_s} {_tf} pattern studies (no {_tf} bars stored)")
            continue

        def _both():
            p_ = term("/api/terminal/studies", symbol=_s, tf=_tf)
            e_ = sorted(sm("/api/v1/market/candles", symbol=_s, tf=_tf, n=500)["candles"], key=lambda k: ts_epoch(k["ts"]))
            return p_, e_

        _p, _ec = _both()
        if _p.get("state") == "OK" and _ec and ts_epoch(_ec[-1]["ts"]) != _p["through_bar"]:
            time.sleep(16)                      # a bar closed between the two reads (the terminal reuses one answer for 15 s): read both again
            _p, _ec = _both()
        if _p.get("state") != "OK":
            print(f"  NOTE {_s} {_tf} pattern studies: {_p.get('state')} — {_p.get('note')}")
            NOT_TESTED.append(f"{_s} {_tf} pattern studies ({_p.get('state')}: {_p.get('note')})")
            continue
        _by = {ts_epoch(k["ts"]): k for k in _ec}
        check(f"{_s} {_tf} pattern studies are through the engine's newest closed bar", ts_epoch(_ec[-1]["ts"]), _p["through_bar"])
        check(f"{_s} {_tf} pattern studies are labelled display only; only Wolfe and Elliott are recorded", True, _p["recorded"] == {"wolfe": True, "elliott": True, "fib": False, "avwap": False, "vp": False} and "not SignalMesh engine output" in _p["kind"] and _p["level_label"] == "HYPOTHETICAL ANALYSIS LEVEL")

        def _on_engine(pt):                     # a pivot's price is the engine bar's own high / low at that time
            k = _by.get(pt["time"])
            return k is not None and abs((k["high"] if pt["kind"] == "H" else k["low"]) - pt["price"]) < 1e-9

        _pts = []
        _fb, _av, _ww, _el, _vp = _p["fib"], _p["avwap"], _p["wolfe"], _p["elliott"], _p["vp"]
        if _fb["state"] == "OK":
            _pts += [_fb["a"], _fb["b"], _fb["c"]]
            _leg = _fb["b"]["price"] - _fb["a"]["price"]
            check(f"{_s} {_tf} Fibonacci levels = C + ratio x (B - A)", True, all(abs(l["price"] - (_fb["c"]["price"] + l["ratio"] * _leg)) < 1e-6 for l in _fb["levels"]))
            _after = [k for k in _ec if _fb["c"]["time"] < ts_epoch(k["ts"]) <= _p["through_bar"]]
            _up = _fb["direction"] == "UP"
            check(f"{_s} {_tf} a Fibonacci level reads reached only when an engine bar after C traded it", True,
                  all(l["reached"] == (bool(_after) and (max(k["high"] for k in _after) >= l["price"] if _up else min(k["low"] for k in _after) <= l["price"])) for l in _fb["levels"]))
        for _w in [x for x in (_ww["pattern"], _ww["last_finished"]) if x]:
            _pts += _w["points"]
            check(f"{_s} {_tf} Wolfe {_w['direction']}: TP1 / TP2 are point 4 and the EPA, SL is beyond point 5", True,
                  {round(_w["tp1"], 6), round(_w["tp2"], 6)} == {round(_w["points"][3]["price"], 6), round(_w["epa"], 6)}
                  and (_w["sl"] < _w["points"][4]["price"] if _w["side"] == "LONG" else _w["sl"] > _w["points"][4]["price"]) and _w["level_label"] == "HYPOTHETICAL ANALYSIS LEVEL")
        if _ww["developing"]:
            _pts += _ww["developing"]["points"]
            check(f"{_s} {_tf} a four-point Wolfe is DEVELOPING and carries no entry, stop or target", True, "NOT confirmed" in _ww["developing"]["status"] and not ({"entry", "sl", "tp1"} & set(_ww["developing"])))
        for _c in [x for x in (_el["count"], _el["alternative"]) if x]:
            _pts += _c["points"]
        if _el["count"]:
            _c = _el["count"]
            check(f"{_s} {_tf} Elliott: a count is called COMPLETE only with five waves, otherwise PARTIAL — never 'confirmed'", True,
                  _c["count_status"].startswith("COMPLETE IMPULSE" if _c["wave"] == 6 else "PARTIAL COUNT") and "CONFIRMED" not in _c["count_status"])
            if _c["wave"] == 3:
                _aft = [k for k in _ec if _c["points"][2]["time"] < ts_epoch(k["ts"]) <= _p["through_bar"]]
                _broke = any((k["close"] - _c["break_level"]) * _c["dir"] > 0 for k in _aft)
                check(f"{_s} {_tf} Elliott wave-3 setup reads TRIGGERED only if an engine bar closed beyond the wave-1 end", _broke, _c["setup"] == "TRIGGERED")
            else:
                check(f"{_s} {_tf} Elliott wave {_c['wave']}: a setup exists only for a finished five", _c["wave"] == 6, _c["setup"] == "RECORDED")
        check(f"{_s} {_tf} the studies carry the engine's own freshness word for these bars", str((sm("/api/v1/market/candles", symbol=_s, tf=_tf, n=1).get("freshness") or {}).get("state") or "UNKNOWN"), _p["freshness"]["state"])
        check(f"{_s} {_tf} every pivot the studies use is an engine bar's own high / low ({len(_pts)} points)", True, all(_on_engine(x) for x in _pts))
        if _av["state"] == "OK":
            for _a in _av["anchors"]:
                _seg = [k for k in _ec if _a["anchor_time"] <= ts_epoch(k["ts"]) <= _p["through_bar"]]
                _vv = sum(float(k.get("tick_volume") or 0) for k in _seg)
                _want = sum((k["high"] + k["low"] + k["close"]) / 3 * float(k.get("tick_volume") or 0) for k in _seg) / _vv if _vv else None
                check(f"{_s} {_tf} anchored VWAP ({_a['id']}) = sum(typical x tick volume) / sum(tick volume) over the engine's bars since the anchor", None if _want is None else round(_want, 6), round(_a["value"], 6))
        if _vp["state"] == "OK":
            check(f"{_s} {_tf} volume profile holds exactly the engine's tick volume of the loaded bars", round(sum(float(k.get("tick_volume") or 0) for k in _ec), 1), round(sum(r["volume"] for r in _vp["rows"]), 1), tol=1.0)
            check(f"{_s} {_tf} POC is inside the value area and the value area holds at least 70%", True, _vp["val"] <= _vp["poc"] <= _vp["vah"] and _vp["value_area_pct"] >= 70 and "tick volume" in _vp["volume_kind"])
        print(f"  NOTE {_s} {_tf} pattern studies: Fibonacci {_fb['state']}{' ' + _fb['direction'] + ' ' + _fb['status'] if _fb['state'] == 'OK' else ''} · anchored VWAP {_av['state']} ({len(_av['anchors'])} anchors) · "
              f"Wolfe {_ww['state']} ({len(_ww['log'])} in the loaded bars) · Elliott {_el['state']}{' — ' + _el['count']['text'] if _el['count'] else ' — ' + str(_el.get('note'))} · "
              f"volume profile {_vp['state']}{' POC ' + format(_vp['poc'], '.' + str(_p['decimals']) + 'f') if _vp['state'] == 'OK' else ''}")
_jr = term("/api/terminal/journal", limit=1000)
_pat = [r for r in _jr["rows"] if r["module"] in ("wolfe-wave", "elliott-wave")]
check("Fibonacci, anchored VWAP and the volume profile record nothing: only Wolfe and Elliott rows beside the daily forecast", True, all(r["module"] in ("daily-forecast", "wolfe-wave", "elliott-wave", "fixture-demo") for r in _jr["rows"]))
check("no developing Wolfe, wave-4 or unclear Elliott count is in the journal", True, all(r["status"] == "confirmed" and "DEVELOPING" not in r["pattern"] and "WAVE 4" not in r["pattern"] and "alt" not in r["pattern"].lower() for r in _pat))
check("every Wolfe / Elliott journal row has its levels in order and a result in R only from recorded events", True,
      all(((r["sl"] < r["entry_low"] <= r["entry_high"] < r["tp1"] <= r["tp2"]) if r["direction"] == "LONG" else (r["sl"] > r["entry_high"] >= r["entry_low"] > r["tp1"] >= r["tp2"]))
          and (r["r_multiple"] is None or any(o["event"] in ("TP1", "TP2", "SL") for o in r["outcomes"])) for r in _pat))
check("forecast ids are unique", len(_jr["rows"]), len({r["id"] for r in _jr["rows"]}))
check("every Wolfe / Elliott row names its bar, expiry, method and origin", True, all(r.get("made_bar_utc") and r.get("expires_utc") and r.get("method_version") and r.get("origin") in ("LIVE", "BACKFILL") for r in _pat))
check("Elliott rows of the current method are triggered wave-3 setups or finished fives only", True,
      all(("WAVE 3 triggered" in r["pattern"] or "5 WAVES DONE" in r["pattern"]) for r in _pat if r["module"] == "elliott-wave" and r["method_version"] == "elliott-setups-v2"))
_old = [r for r in _pat if r["module"] == "elliott-wave" and r["method_version"] != "elliott-setups-v2"]
if _old:
    print(f"  NOTE {len(_old)} Elliott rows were recorded by 2.7.0's first method (pattern-studies-v1: stages, not triggered setups). They are kept — the journal is append-only — and their hit rate is shown apart, under that method name")
print(f"  NOTE Wolfe / Elliott in the journal: {len(_pat)} rows shown · " + (" · ".join(f"{g['module']} {g['symbol']} {g['timeframe']} {g['origin']}: {g['finished']} finished, avg R {g['r_avg']}" for g in _jr["stats"] if g["module"] in ("wolfe-wave", "elliott-wave"))[:300] or "none yet"))
check("execution stays disabled", False, term("/api/terminal/execution/modes")["can_place"])

# 11. data state and safety — what the terminal says about a price that is not live
print("\n== data state and safety ==")
_mw = term("/api/terminal/market-watch")
_hl = term("/api/terminal/health")
check("every market-watch row says why it is or is not live (feed_state)", True, all(r.get("feed_state") in ("LIVE", "MARKET QUIET", "FEED STALE", "DISCONNECTED", "NO DATA") and r.get("feed_note") for r in _mw["rows"]))
check("a row reads LIVE only when the engine's own freshness word is LIVE", True, all((r["feed_state"] == "LIVE") == (r["freshness"]["state"] == "LIVE" and not r.get("error")) for r in _mw["rows"]))
check("every price carries the bar it comes from and its source", True, all(r.get("price") is None or (r.get("price_ts") and r.get("bar_close_ts") and r.get("price_kind") == "last_closed_1m") for r in _mw["rows"]))
check("this is production data, not test fixtures", False, bool(_hl["provider"]["is_fixture"]))
check("the build names its version, commit and environment", True, all(_hl["build"].get(k) for k in ("version", "commit", "environment")))
check("execution cannot place an order", False, term("/api/terminal/execution/modes")["can_place"])
_states = {}
for r in _mw["rows"]:
    _states.setdefault(r["feed_state"], []).append(r["symbol"])
print("  NOTE data state now: " + " · ".join(f"{k}: {len(v)} ({', '.join(v[:6])}{'…' if len(v) > 6 else ''})" for k, v in sorted(_states.items())))
for _s in ("GOLD", "SILVER"):
    _r = next((r for r in _mw["rows"] if r["symbol"] == _s), None)
    if _r:
        _dv = term("/api/terminal/decision", symbol=_s)
        print(f"  NOTE {_s}: header price {_r['price']} = close of the 1m bar ending {_r['bar_close_ts']} · {_r['feed_state']} · engine freshness {_r['freshness']['state']} · engine decision {_dv.get('summary')} ({_dv.get('engine_status')})")
        if _r["freshness"]["state"] != "LIVE":
            check(f"{_s} is not live, so the decision shown is not READY", True, _dv.get("summary") != "READY")
for _k in ("LIVE", "MARKET QUIET", "FEED STALE", "DISCONNECTED"):
    if _k not in _states:
        NOT_TESTED.append(f"data state {_k}: no instrument was in that state during this run")
_store = (term("/api/terminal/journal").get("store") or {})
if _store.get("first_recorded_at") and _hl["build"].get("started_at") and ts_epoch(_store["first_recorded_at"]) < ts_epoch(_hl["build"]["started_at"]):
    check("the journal holds records older than this deployment: it survived the redeploy", True, _store["forecasts"] > 0)
else:
    NOT_TESTED.append("journal persistence across a redeploy: no record older than this deployment exists yet")
NOT_TESTED += ["chart zoom / scroll / crosshair / full screen on PRODUCTION: see the UI PASS / FAIL lines of scripts/screenshots.sh, which runs after this",
               "a Wolfe or Elliott forecast recorded LIVE (at its own bar) and scored to a final result: a separate performance milestone, it needs time to pass",
               "journal restore rehearsal: see the lines of scripts/journal_restore_test.sh, which runs right after this"]

# why a 15m chart can end before the 1m price: which closed bars the ENGINE itself holds, and where they stop
print("\n== candle coverage (GOLD, SILVER) ==")
for _s in ("GOLD", "SILVER"):
    try:
        _m1 = sorted(sm("/api/v1/market/candles", symbol=_s, tf="1m", n=120)["candles"], key=lambda k: ts_epoch(k["ts"]))
        _m15 = sorted(sm("/api/v1/market/candles", symbol=_s, tf="15m", n=200)["candles"], key=lambda k: ts_epoch(k["ts"]))
    except Exception as _exc:  # noqa: BLE001
        NOT_TESTED.append(f"{_s} candle coverage ({_exc})")
        continue
    if not _m1 or not _m15:
        NOT_TESTED.append(f"{_s} candle coverage (no 1m or 15m bars)")
        continue
    _l1, _l15 = ts_epoch(_m1[-1]["ts"]), ts_epoch(_m15[-1]["ts"])
    _iso = lambda t: datetime.utcfromtimestamp(t).strftime("%Y-%m-%d %H:%M")   # noqa: E731
    _want = (_l1 + 60) // 900 * 900 - 900            # the newest 15m bar that is fully covered by closed 1m bars
    _gaps = [(ts_epoch(a["ts"]), ts_epoch(b["ts"])) for a, b in zip(_m15, _m15[1:]) if ts_epoch(b["ts"]) - ts_epoch(a["ts"]) > 900]
    _in15 = [k for k in _m1 if _l15 + 900 <= ts_epoch(k["ts"]) < _l15 + 1800]
    print(f"  NOTE {_s}: engine's newest closed 1m bar opens {_iso(_l1)} UTC, newest closed 15m bar opens {_iso(_l15)} UTC. "
          + (f"The 15m bar {_iso(_l15 + 900)} is NOT stored although {len(_in15)} of its fifteen 1m bars are (last {_iso(ts_epoch(_in15[-1]['ts']))}): "
             "the engine holds a 15m bar only once the reporter has sent it as closed — the terminal draws what the engine holds and builds no 15m bar of its own."
             if _in15 else "The 15m series reaches as far as the closed 1m bars cover."))
    print(f"  NOTE {_s}: gaps inside the last {len(_m15)} stored 15m bars: " + (", ".join(f"{_iso(a + 900)} to {_iso(b)}" for a, b in _gaps[-6:]) + f" ({len(_gaps)} in all — a gap is a time with no stored bar: a daily break, a weekend, or a bar that was never sent)" if _gaps else "none"))
    check(f"{_s} the terminal's 15m chart ends on the engine's newest closed 15m bar (nothing invented, nothing dropped)", _l15, term("/api/terminal/candles", symbol=_s, tf="15m", n=10)["candles"][-1]["time"])

# the US500 fix (2.7.0): a failed read of SignalMesh is never remembered as "no candles"
print("\n== US500 fix ==")
_il = term("/api/terminal/instruments")
_u = next((i for i in _il["instruments"] if i["symbol"] == "US500"), None)
check("the instrument list is complete: no failed read of SignalMesh is hidden in it", True, _il.get("complete") is True and not _il.get("failed_reads"))
if _u:
    _eng = sorted(tf for tf in TFS if sm("/api/v1/market/candles", symbol="US500", tf=tf, n=1)["count"] > 0)
    check("US500: every timeframe the engine stores is listed by the terminal, 1m included", _eng, sorted(_u["timeframes"]))
    print(f"  NOTE US500: engine stores {' '.join(_eng) or 'nothing'} · terminal lists {' '.join(_u['timeframes']) or 'nothing'} · list complete={_il.get('complete')}")
else:
    NOT_TESTED.append("US500 fix: US500 is not in the instrument list")
NOT_TESTED.append("US500 fix under a real failed read: the failure cannot be produced on purpose on production; the unit test produces it")

GATES = {"GATE 1 — data and safety": ("instruments", "signals", "trades", "performance", "accounts", "signals are not executions", "data state and safety", "candle coverage", "US500 fix", "start"),
         "GATE 2 — pattern studies (GOLD, SILVER · 15m 1h 4h 1d)": ("pattern studies", "forecasting studies"),
         "GATE 3 — journal and production": ("forecast journal",)}
print("\n== RELEASE GATES (this run, on this box, against the live engine) ==")
_used = set()
for _g, _keys in GATES.items():
    _a = [(n, v) for n, v in AREAS.items() if any(n.startswith(k) for k in _keys)]
    _used |= {n for n, _ in _a}
    _c, _f = sum(v[0] for _, v in _a), sum(v[1] for _, v in _a)
    print(f"  GATE {'PASS' if _c and not _f else 'FAIL' if _f else 'NOT TESTED'}  {_g}: {_c} checks, {_f} FAIL")
_rest = [(n, v) for n, v in AREAS.items() if n not in _used]
if _rest:
    _c, _f = sum(v[0] for _, v in _rest), sum(v[1] for _, v in _rest)
    print(f"  GATE {'PASS' if not _f else 'FAIL'}  per-instrument engine parity (counts toward GATE 1): {_c} checks, {_f} FAIL")
for _n in NOT_TESTED:
    print(f"  NOT TESTED  {_n}")

# every combination, by name: symbol x timeframe x study
print("\n== PATTERN STUDY MATRIX (production data, this run) ==")
_KEYS = {"Fibonacci": ("Fibonacci", "a Fibonacci"), "Anchored VWAP": ("anchored VWAP",), "Wolfe": ("Wolfe", "a four-point Wolfe"), "Elliott": ("Elliott",), "Volume profile": ("volume profile", "POC")}
for _s in ("GOLD", "SILVER"):
    for _tf in ("15m", "1h", "4h", "1d"):
        _mine = [(l, ok) for l, ok in RESULTS if l.startswith(f"{_s} {_tf} ")]
        _cells = []
        for _name, _kw in _KEYS.items():
            _c = [ok for l, ok in _mine if l[len(f"{_s} {_tf} "):].startswith(_kw)]
            _cells.append(f"{_name} {'NOT TESTED' if not _c else 'PASS' if all(_c) else 'FAIL'}{'' if not _c else f' ({len(_c)})'}")
        _piv = [ok for l, ok in _mine if "every pivot" in l]
        print(f"  MATRIX {_s:6} {_tf:4} " + " · ".join(_cells) + (f" · pivots on engine bars {'PASS' if all(_piv) else 'FAIL'}" if _piv else "") + ("" if _mine else "   (no bars stored or study not available: nothing could be tested)"))
print("  NOTE in the matrix, NOT TESTED beside a study means it had nothing to verify in this run (for example no Wolfe wedge present, or no Fibonacci set): the study said NONE and drew nothing")

print(f"\n{checks} checks, {fails} FAIL")
sys.exit(1 if fails else 0)
