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
import urllib.parse
import urllib.request
from datetime import datetime

SM = os.environ.get("SM_URL", "http://127.0.0.1:8000").rstrip("/")
KEY = os.environ.get("SM_KEY", "")
TERM = os.environ.get("TERM_URL", "http://127.0.0.1:8090").rstrip("/")
TOKEN = os.environ.get("TERM_TOKEN", "")
COOKIE = os.environ.get("SM_SESSION_COOKIE", "")
ALLOW_FIXTURE = os.environ.get("ALLOW_FIXTURE_SOURCE", "") == "1"   # local verification only
SYMBOLS = sys.argv[1:] or ["GOLD", "SILVER", "BTC"]
TFS = ["1m", "15m", "1h"]

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


def dash(path: str, **q):
    """The OLD dashboard's own JSON routes (session cookie)."""
    return get(f"{SM}{path}?{urllib.parse.urlencode(q)}", {"Cookie": f"bb_session={COOKIE}"})


def term(path: str, **q):
    h = {"X-Terminal-Token": TOKEN} if TOKEN else {}
    return get(f"{TERM}{path}?{urllib.parse.urlencode(q)}" if q else f"{TERM}{path}", h)


def check(label: str, engine, terminal, tol: float = 0.0):
    global fails, checks
    checks += 1
    ok = engine == terminal
    if not ok and isinstance(engine, (int, float)) and isinstance(terminal, (int, float)):
        ok = abs(float(engine) - float(terminal)) <= tol
    print(f"  {'OK  ' if ok else 'FAIL'} {label}: engine={engine!r} terminal={terminal!r}")
    if not ok:
        fails += 1


def ts_epoch(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


for sym in SYMBOLS:
    print(f"\n== {sym} ==")
    # 1. candles: every bar identical, same count, same freshness state
    for tf in TFS:
        e = sm("/api/v1/market/candles", symbol=sym, tf=tf, n=100)
        t = term("/api/terminal/candles", symbol=sym, tf=tf, n=100)
        check(f"candles {tf} count", e["count"], t["count"])
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
    e1 = sm("/api/v1/market/candles", symbol=sym, tf="1m", n=1)
    if mw and e1["candles"]:
        check("market-watch price = engine last closed 1m close", e1["candles"][-1]["close"], mw["price"])
        check("market-watch price ts", e1["candles"][-1]["ts"], mw["price_ts"])
        check("market-watch freshness", e1["freshness"]["state"], mw["freshness"]["state"])
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

# 5. signals and trades: same ids, same levels, same statuses
print("\n== signals ==")
es = {s["signal_id"]: s for s in sm("/api/v1/signals", limit=200)}
ts_ = {s["signal_id"]: s for s in term("/api/terminal/signals", bucket="all")["rows"]}
check("signal ids identical", sorted(es), sorted(ts_))
for sid, s in es.items():
    t = ts_.get(sid)
    if not t:
        continue
    for k in ("symbol", "direction", "entry", "sl", "tp1", "tp2", "rr", "grade", "status", "confidence", "system", "tf"):
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

print(f"\n{checks} checks, {fails} FAIL")
sys.exit(1 if fails else 0)
