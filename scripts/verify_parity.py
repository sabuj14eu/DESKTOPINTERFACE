#!/usr/bin/env python3
"""PHASE 3 — PARITY CHECK: does the terminal show exactly what the engine says?

Reads the SAME instant from both sides:
  * SignalMesh directly   (/api/v1/..., the engine's own mirror, with the API key)
  * the terminal adapter  (/api/terminal/..., what the UI renders)
and compares every displayed price, entry, SL, TP, status and freshness field by
field. Any difference is a FAIL with both values printed. Exit code 1 on any FAIL.

Usage:
  SM_URL=https://app.yourdomain.com SM_KEY=bb_... TERM_URL=http://127.0.0.1:8090 \
  [TERM_TOKEN=...] python3 scripts/verify_parity.py [SYMBOL ...]

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
SYMBOLS = sys.argv[1:] or ["GOLD", "SILVER", "BTC"]
TFS = ["1m", "15m", "1h"]

fails = 0
checks = 0


def get(url: str, headers: dict) -> dict | list:
    req = urllib.request.Request(url, headers={"Accept": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def sm(path: str, **q):
    return get(f"{SM}{path}?{urllib.parse.urlencode(q)}" if q else f"{SM}{path}", {"Authorization": f"Bearer {KEY}"})


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
