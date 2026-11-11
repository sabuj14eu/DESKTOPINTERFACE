"""SMART MONEY CONCEPTS — the terminal's own DISPLAY-ONLY chart studies.

These are NOT SignalMesh engine output and NOT the Pine sensor's structure. They are a
separate, transparent calculation made here, from the stored CLOSED candles of one timeframe,
for the user to look at. They feed nothing: no decision, no level, no signal, no confidence,
no statistic (see docs/DATA_CONTRACT.md, smc-v1).

RULES EVERY FUNCTION OBEYS

  * CLOSED CANDLES ONLY, AND NO LOOKAHEAD. A structure is created by bars up to some bar j and
    carries `confirmed_at` = the close time of bar j. Nothing dated before its confirmation
    exists on the chart. A swing pivot needs L closed bars AFTER it, so it is confirmed L bars
    late — that delay is the price of not repainting.
  * CONFIRMED STRUCTURES DO NOT REPAINT. What bars 0..j establish is the same whether bar j is
    the newest bar or history (tests/test_smc.py computes on every prefix and compares).
    Only the STATUS of a structure moves forward in time (fresh -> tested -> invalidated …),
    and each status carries the bar that caused it.
  * A CLOSE BREAKS, A WICK SWEEPS. Price closing beyond a swing is a break of structure
    (BOS / CHoCH). Price trading beyond a swing and closing back inside is a liquidity sweep.
    They are never the same event.
  * NOTHING IS INVENTED. Too few bars, or no bars, is a stated state with no structures.

METHOD (smc-v1), also returned to the UI as `methodology`
  swings      fractal pivots: a swing high is a bar whose high is above the L bars before it and
              not below the L bars after it. External structure L=5, internal L=2.
  BOS/CHoCH   walking forward: a close above the newest confirmed, unbroken swing high is a
              bullish break — CHoCH if the trend so far was bearish, else BOS; mirrored for lows.
  FVG         three-candle imbalance: bullish when low[i] > high[i-2] (zone high[i-2]..low[i]),
              bearish when high[i] < low[i-2]; kept when at least 0.2 x ATR(14) wide.
              fresh -> partially mitigated (price entered) -> mitigated (price crossed it).
  order block the last opposite-coloured candle before the leg that produced a BOS/CHoCH
              (within 10 bars of the leg's origin). strength = leg size in ATR.
              fresh -> tested (price returned into it) -> invalidated (a close through it).
  liquidity   every confirmed swing high is buy-side (BSL), every swing low sell-side (SSL);
              two or more within 0.1 x ATR are EQUAL highs/lows. unswept -> swept (wick beyond,
              close back) or broken (close beyond). Plus previous day / week / session extremes.
  inducement  in a trend, the newest internal swing against it that sits inside the external
              range: potential -> swept (wick through, close back) or broken (close through).
  S/R         external swing prices clustered within 0.3 x ATR: 1 touch = weak (a previous
              swing), 2 = normal, 3+ = strong. Below the last close = support, above = resistance.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

RULE = ("smc-v1: display-only studies computed by the terminal from stored CLOSED candles; no lookahead; "
        "confirmed structures do not repaint; a close breaks, a wick sweeps; never an input to the SignalMesh "
        "engine, its levels, signals or statistics; not the Pine sensor's structure")
TF_MIN = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440, "1w": 10080}
ANALYSIS_TFS = ("5m", "15m", "30m", "1h", "4h", "1d", "1w")
L_EXTERNAL, L_INTERNAL = 5, 2
MIN_BARS = 30
METHODOLOGY = {
    "swings": f"fractal pivots on closed bars: external L={L_EXTERNAL}, internal L={L_INTERNAL}; confirmed L bars after the pivot (no repaint)",
    "structure": "a CLOSE beyond the newest confirmed unbroken swing = break: CHoCH when it is against the trend so far, else BOS; "
                 "external (L=5) and internal (L=2) tracked separately; `pending` = the level whose break would be the next BOS / CHoCH",
    "fvg": "3-candle imbalance, bullish low[i] > high[i-2], bearish high[i] < low[i-2]; kept when >= 0.2 x ATR(14); "
           "fresh / partial (price entered) / mitigated (price crossed the whole gap)",
    "order_blocks": "last opposite-coloured candle within 10 bars before the origin of the leg that made a BOS/CHoCH; strength = leg size in ATR; "
                    "fresh / tested (price returned into it) / invalidated (a close through it)",
    "liquidity": "confirmed swing highs = buy-side (BSL), swing lows = sell-side (SSL); 2+ within 0.1 x ATR = equal highs/lows; "
                 "swept = wick beyond and close back; broken = close beyond. Previous day/week from closed daily bars, sessions from closed 1h bars",
    "inducement": "newest internal swing against the external trend, inside the external range; potential / swept / broken",
    "sr": "external swing prices clustered within 0.3 x ATR; 1 touch weak, 2 normal, 3+ strong; below last close support, above resistance",
}


def _epoch(v) -> int | None:
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return int((dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).timestamp())


def bars_from(payload: dict | None) -> list[dict]:
    """SignalMesh candle payload -> [{t, o, h, l, c}] ascending, bar-open epoch seconds."""
    out = []
    for k in (payload or {}).get("candles") or []:
        t = _epoch(k.get("ts", k.get("time")))
        try:
            out.append({"t": t, "o": float(k["open"]), "h": float(k["high"]), "l": float(k["low"]), "c": float(k["close"])})
        except (KeyError, TypeError, ValueError):
            continue
    out = [b for b in out if b["t"] is not None]
    out.sort(key=lambda b: b["t"])
    return out


def weekly_from_daily(daily: list[dict], now: datetime | None = None) -> list[dict]:
    """CLOSED ISO weeks (Monday 00:00 UTC) aggregated from closed daily bars; the running week is left out."""
    now = now or datetime.now(timezone.utc)
    this_monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    weeks: dict[int, dict] = {}
    for b in daily:
        d = datetime.fromtimestamp(b["t"], timezone.utc)
        monday = (d - timedelta(days=d.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        if monday >= this_monday:
            continue
        k = int(monday.timestamp())
        w = weeks.get(k)
        if w is None:
            weeks[k] = {"t": k, "o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"]}
        else:
            w["h"], w["l"], w["c"] = max(w["h"], b["h"]), min(w["l"], b["l"]), b["c"]
    return [weeks[k] for k in sorted(weeks)]


def atr_series(b: list[dict], n: int = 14) -> list[float | None]:
    out: list[float | None] = []
    trs: list[float] = []
    for i, k in enumerate(b):
        tr = k["h"] - k["l"] if i == 0 else max(k["h"] - k["l"], abs(k["h"] - b[i - 1]["c"]), abs(k["l"] - b[i - 1]["c"]))
        trs.append(tr)
        out.append(sum(trs[-n:]) / n if len(trs) >= n else None)
    return out


def pivots(b: list[dict], L: int) -> list[dict]:
    """Confirmed swing pivots. `ci` is the index of the bar whose close confirms the pivot."""
    out = []
    for i in range(L, len(b) - L):
        hi, lo = b[i]["h"], b[i]["l"]
        if all(hi > b[k]["h"] for k in range(i - L, i)) and all(hi >= b[k]["h"] for k in range(i + 1, i + L + 1)):
            out.append({"i": i, "ci": i + L, "kind": "H", "price": hi})
        if all(lo < b[k]["l"] for k in range(i - L, i)) and all(lo <= b[k]["l"] for k in range(i + 1, i + L + 1)):
            out.append({"i": i, "ci": i + L, "kind": "L", "price": lo})
    return out


def _fate(b: list[dict], p: dict) -> tuple[str, int | None]:
    """What later bars did to a swing: ('unswept', None) | ('swept', j) | ('broken', j). First touch decides."""
    for j in range(p["ci"] + 1, len(b)):
        if p["kind"] == "H" and b[j]["h"] > p["price"]:
            return ("broken" if b[j]["c"] > p["price"] else "swept"), j
        if p["kind"] == "L" and b[j]["l"] < p["price"]:
            return ("broken" if b[j]["c"] < p["price"] else "swept"), j
    return "unswept", None


def structure(b: list[dict], pv: list[dict], scope: str) -> tuple[list[dict], str | None, list[dict]]:
    """Walk forward: (events, trend, pending). Only pivots already confirmed at bar j are used at bar j."""
    by_ci: dict[int, list[dict]] = {}
    for p in pv:
        by_ci.setdefault(p["ci"], []).append(p)
    events: list[dict] = []
    trend: str | None = None
    last = {"H": None, "L": None}          # newest confirmed swing of each kind
    broken = set()
    for j in range(len(b)):
        for p in by_ci.get(j, []):
            last[p["kind"]] = p
        for kind, direction in (("H", "bull"), ("L", "bear")):
            p = last[kind]
            if p is None or id(p) in broken:
                continue
            beyond = b[j]["c"] > p["price"] if kind == "H" else b[j]["c"] < p["price"]
            if not beyond:
                continue
            opposite = "bear" if direction == "bull" else "bull"
            events.append({"type": "CHoCH" if trend == opposite else "BOS", "dir": direction, "scope": scope, "level": p["price"],
                           "swing_i": p["i"], "break_i": j})
            trend = direction
            broken.add(id(p))
    pending = []
    for kind, direction in (("H", "bull"), ("L", "bear")):
        p = last[kind]
        if p is not None and id(p) not in broken:
            opposite = "bear" if direction == "bull" else "bull"
            pending.append({"type": "CHoCH" if trend == opposite else "BOS", "dir": direction, "scope": scope, "level": p["price"], "swing_i": p["i"]})
    return events, trend, pending


def analyse(symbol: str, tf: str, b: list[dict], source: str = "") -> dict:
    """Every smc-v1 structure of one timeframe, from its closed bars `b`."""
    step = TF_MIN[tf] * 60
    base = {"symbol": symbol, "tf": tf, "rule": RULE, "methodology": METHODOLOGY, "source": source, "bars_used": len(b),
            "calculated_at": datetime.now(timezone.utc).isoformat(), "through_bar": b[-1]["t"] if b else None,
            "through_close": (b[-1]["t"] + step) if b else None,
            "swings": [], "structure": [], "pending": [], "fvg": [], "order_blocks": [], "liquidity": [], "inducement": [], "sr": [],
            "trend": {"external": None, "internal": None}, "atr": None}
    if len(b) < MIN_BARS:
        return {**base, "state": "NO_CANDLES" if not b else "TOO_FEW_BARS",
                "note": f"{len(b)} closed {tf} bars stored — at least {MIN_BARS} are needed; nothing is drawn rather than guessed"}
    atr = atr_series(b)
    a_last = next((x for x in reversed(atr) if x), None) or (max(k["h"] for k in b) - min(k["l"] for k in b)) / max(len(b), 1)
    T = lambda i: b[i]["t"]                    # noqa: E731  bar open
    C = lambda i: b[i]["t"] + step             # noqa: E731  bar close = when bar i's facts are known
    ext, internal = pivots(b, L_EXTERNAL), pivots(b, L_INTERNAL)

    # ---- swings + liquidity (every confirmed swing is resting liquidity until swept or broken)
    swings, liquidity = [], []
    fates = {}
    for scope, pv in (("external", ext), ("internal", internal)):
        for p in pv:
            st, j = _fate(b, p)
            fates[(scope, p["i"], p["kind"])] = (st, j)
            swings.append({"scope": scope, "kind": "high" if p["kind"] == "H" else "low", "price": p["price"], "time": T(p["i"]),
                           "confirmed_at": C(p["ci"]), "status": st, "status_at": C(j) if j is not None else None})
    tol = 0.1 * a_last
    for kind, side in (("H", "BSL"), ("L", "SSL")):
        pts = sorted((p for p in ext if p["kind"] == kind), key=lambda p: p["i"])
        used = set()
        for n, p in enumerate(pts):
            if n in used:
                continue
            group = [p]
            for m in range(n + 1, len(pts)):
                if m not in used and abs(pts[m]["price"] - p["price"]) <= tol:
                    group.append(pts[m])
                    used.add(m)
            newest = max(group, key=lambda q: q["i"])
            level = max(q["price"] for q in group) if kind == "H" else min(q["price"] for q in group)
            st, j = _fate(b, {**newest, "price": level})
            liquidity.append({"side": side, "kind": ("EQH" if kind == "H" else "EQL") if len(group) > 1 else ("swing high" if kind == "H" else "swing low"),
                              "level": level, "touches": len(group), "time": T(min(q["i"] for q in group)), "confirmed_at": C(newest["ci"]),
                              "status": st, "status_at": C(j) if j is not None else None, "dir": "bear" if kind == "H" else "bull"})

    # ---- BOS / CHoCH
    ev_ext, trend_ext, pend_ext = structure(b, ext, "external")
    ev_int, trend_int, pend_int = structure(b, internal, "internal")
    events = []
    for e in ev_ext + ev_int:
        events.append({"type": e["type"], "dir": e["dir"], "scope": e["scope"], "level": e["level"], "swing_time": T(e["swing_i"]),
                       "time": T(e["break_i"]), "confirmed_at": C(e["break_i"]), "status": "confirmed"})
    pending = [{"type": p["type"], "dir": p["dir"], "scope": p["scope"], "level": p["level"], "swing_time": T(p["swing_i"]),
                "status": "unconfirmed", "note": f"a close {'above' if p['dir'] == 'bull' else 'below'} this level would be a {p['dir']}ish {p['type']}"}
               for p in pend_ext + pend_int]

    # ---- FVG
    fvg = []
    for i in range(2, len(b)):
        a = atr[i]
        if a is None:                                # before ATR exists the size filter cannot be applied: nothing is kept
            continue
        if b[i]["l"] > b[i - 2]["h"]:
            direction, lo, hi = "bull", b[i - 2]["h"], b[i]["l"]
        elif b[i]["h"] < b[i - 2]["l"]:
            direction, lo, hi = "bear", b[i]["h"], b[i - 2]["l"]
        else:
            continue
        if hi - lo < 0.2 * a:
            continue
        status, at, fill = "fresh", None, 0.0
        for j in range(i + 1, len(b)):
            depth = (hi - b[j]["l"]) if direction == "bull" else (b[j]["h"] - lo)
            if depth <= 0:
                continue
            f = min(depth / (hi - lo), 1.0)
            if f > fill:
                fill, at = f, j
            if fill >= 1.0:
                break
        status = "mitigated" if fill >= 1.0 else "partial" if fill > 0 else "fresh"
        fvg.append({"dir": direction, "low": lo, "high": hi, "time": T(i - 1), "confirmed_at": C(i), "status": status,
                    "filled_pct": round(fill * 100), "status_at": C(at) if at is not None else None})

    # ---- order blocks (from the legs that broke structure)
    obs, seen = [], set()
    # in TIME order: the first break that points at a candle owns it for ever. (Taking external breaks
    # first let a LATER external break re-date a block an earlier internal break had already made —
    # a repaint, caught by the prefix test.)
    for e in sorted(ev_ext + ev_int, key=lambda e: (e["break_i"], e["scope"])):
        s, j = e["swing_i"], e["break_i"]
        if e["dir"] == "bull":
            origin = min(range(s, j + 1), key=lambda k: b[k]["l"])
            k = next((k for k in range(origin, max(origin - 10, -1), -1) if b[k]["c"] < b[k]["o"]), None)
        else:
            origin = max(range(s, j + 1), key=lambda k: b[k]["h"])
            k = next((k for k in range(origin, max(origin - 10, -1), -1) if b[k]["c"] > b[k]["o"]), None)
        if k is None or (k, e["dir"]) in seen:
            continue
        seen.add((k, e["dir"]))
        lo, hi = b[k]["l"], b[k]["h"]
        a = atr[j]                                   # ATR at the break bar: fixed for ever, so strength never repaints
        strength = round(((b[j]["c"] - hi) if e["dir"] == "bull" else (lo - b[j]["c"])) / a, 1) if a else None
        status, at = "fresh", None
        for m in range(j + 1, len(b)):
            if (e["dir"] == "bull" and b[m]["c"] < lo) or (e["dir"] == "bear" and b[m]["c"] > hi):
                status, at = "invalidated", m
                break
            if status == "fresh" and ((e["dir"] == "bull" and b[m]["l"] <= hi) or (e["dir"] == "bear" and b[m]["h"] >= lo)):
                status, at = "tested", m
        obs.append({"dir": e["dir"], "low": lo, "high": hi, "time": T(k), "confirmed_at": C(j), "from": f"{e['scope']} {e['type']}",
                    "scope": e["scope"], "strength_atr": strength, "strength": "strong" if (strength or 0) >= 2 else "normal",
                    "status": status, "mitigation": "unmitigated" if status == "fresh" else "mitigated", "status_at": C(at) if at is not None else None})

    # ---- inducement (newest internal swing against each external break, inside the range)
    inducement = []
    for e in ev_ext:
        j = e["break_i"]
        want = "L" if e["dir"] == "bull" else "H"
        cand = [p for p in internal if p["kind"] == want and p["ci"] <= j and p["i"] > e["swing_i"] - 60]
        cand = [p for p in cand if (p["price"] < e["level"] if want == "L" else p["price"] > e["level"])]
        if not cand:
            continue
        p = max(cand, key=lambda q: q["i"])
        status, at = "potential", None
        for m in range(j + 1, len(b)):
            if want == "L" and b[m]["l"] < p["price"]:
                status, at = ("broken" if b[m]["c"] < p["price"] else "swept"), m
                break
            if want == "H" and b[m]["h"] > p["price"]:
                status, at = ("broken" if b[m]["c"] > p["price"] else "swept"), m
                break
        row = {"dir": e["dir"], "level": p["price"], "time": T(p["i"]), "confirmed_at": C(j), "status": status,
               "status_at": C(at) if at is not None else None,
               "note": {"potential": "potential inducement — liquidity resting, not yet taken", "swept": "confirmed liquidity sweep of the inducement level",
                        "broken": "closed through — the inducement level failed"}[status]}
        if not any(r["level"] == row["level"] and r["time"] == row["time"] for r in inducement):
            inducement.append(row)

    # ---- support / resistance (clusters of external swings)
    sr = []
    last_close = b[-1]["c"]
    tol_sr = 0.3 * a_last
    pts = sorted(ext, key=lambda p: p["price"])
    cluster: list[dict] = []
    def flush():
        if not cluster:
            return
        lo, hi = min(p["price"] for p in cluster), max(p["price"] for p in cluster)
        mid = (lo + hi) / 2
        n = len(cluster)
        newest = max(cluster, key=lambda p: p["i"])
        sr.append({"kind": "support" if mid < last_close else "resistance", "low": lo - 0.05 * a_last, "high": hi + 0.05 * a_last, "level": mid,
                   "touches": n, "strength": "strong" if n >= 3 else "normal" if n == 2 else "weak",
                   "time": T(min(p["i"] for p in cluster)), "last_touch": T(newest["i"]), "confirmed_at": C(newest["ci"]), "status": "active"})
    for p in pts:
        if cluster and p["price"] - cluster[-1]["price"] > tol_sr:
            flush()
            cluster = []
        cluster.append(p)
    flush()

    for row in swings + events + pending + fvg + obs + liquidity + inducement + sr:
        row["tf"] = tf
    return {**base, "state": "OK", "atr": a_last, "last_close": last_close, "trend": {"external": trend_ext, "internal": trend_int},
            "swings": swings, "structure": events, "pending": pending, "fvg": fvg, "order_blocks": obs, "liquidity": liquidity,
            "inducement": inducement, "sr": sr}


# ---------------------------------------------------------------- previous day / week / session extremes
SESSIONS = (("ASIA", 0, 7), ("LONDON", 7, 13), ("NEW YORK", 13, 21))      # the platform's fixed UTC windows (market_time.SESSIONS)


def key_levels(daily: list[dict], hourly: list[dict], now: datetime | None = None) -> list[dict]:
    """PDH/PDL, PWH/PWL and the previous completed session's high/low, each with its swept state
    against the closed 1h bars that came after the period. From closed bars only."""
    now = now or datetime.now(timezone.utc)
    out = []

    def fate(level: float, high: bool, after: int) -> tuple[str, int | None]:
        for k in hourly:
            if k["t"] < after:
                continue
            if (high and k["h"] > level) or (not high and k["l"] < level):
                closed_beyond = k["c"] > level if high else k["c"] < level
                return ("broken" if closed_beyond else "swept"), k["t"] + 3600
        return "unswept", None

    def add(name: str, level: float, high: bool, start: int, end: int, tf: str):
        st, at = fate(level, high, end)
        out.append({"side": "BSL" if high else "SSL", "kind": name, "level": level, "touches": 1, "time": start, "confirmed_at": end,
                    "status": st, "status_at": at, "dir": "bear" if high else "bull", "tf": tf})

    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    closed_days = [d for d in daily if d["t"] < int(today.timestamp())]
    if closed_days:
        d = closed_days[-1]
        add("PDH", d["h"], True, d["t"], d["t"] + 86400, "1d")
        add("PDL", d["l"], False, d["t"], d["t"] + 86400, "1d")
    weeks = weekly_from_daily(daily, now)
    if weeks:
        w = weeks[-1]
        add("PWH", w["h"], True, w["t"], w["t"] + 7 * 86400, "1w")
        add("PWL", w["l"], False, w["t"], w["t"] + 7 * 86400, "1w")
    for name, h0, h1 in SESSIONS:
        end = today + timedelta(hours=h1)
        if end > now:
            end -= timedelta(days=1)
        start = end - timedelta(hours=h1 - h0)
        rows = [k for k in hourly if int(start.timestamp()) <= k["t"] < int(end.timestamp())]
        if len(rows) < (h1 - h0) // 2:              # a session with most of its bars missing is not summarised
            continue
        add(f"{name} high", max(k["h"] for k in rows), True, int(start.timestamp()), int(end.timestamp()), "1h")
        add(f"{name} low", min(k["l"] for k in rows), False, int(start.timestamp()), int(end.timestamp()), "1h")
    return out
