"""PATTERN STUDIES — Fibonacci extension, anchored VWAP, Wolfe wave, Elliott wave, volume profile.

The terminal's own DISPLAY-ONLY chart studies (pattern-studies-v1). They are NOT SignalMesh
engine output. They produce no signal and no order, feed nothing, and — on Shyam's word — are
NOT recorded in the forecast journal: they are calculated when the chart asks and kept nowhere.
Every entry / stop / target they show is a HYPOTHETICAL ANALYSIS LEVEL.

RULES EVERY FUNCTION OBEYS

  * CLOSED CANDLES ONLY, NO LOOKAHEAD. Each study is a walk forward over the closed bars; what
    it reports at bar j is made from bars 0..j alone. A swing pivot needs L closed bars after
    it, so it is known L bars late.
  * WHAT WAS REPORTED IS NOT REWRITTEN. A Wolfe pattern, an Elliott stage and a Fibonacci set
    are each logged with the bar that made them; the log of the first n bars is the beginning
    of the log of all bars (tests/test_studies.py compares every prefix). Only a status moves
    forward (LIVE -> TP1 HIT -> ...), and the newest pivot may be replaced by a more extreme
    one of the same kind — that makes a NEW logged entry, it never edits an old one.
  * UNCLEAR IS SAID, NOT GUESSED: no valid pattern reads NONE / UNKNOWN, too few bars or no
    tick volume reads NOT_AVAILABLE with the reason.

WHERE IT COMES FROM. Wolfe and the Elliott impulse rules start from Shyam's Pine scripts
(Metal Hunter V15 §27, MH15 PLUS §27B) with the same thresholds. Shyam asked for more than
Pine: the terminal adds a DEVELOPING Wolfe (four points, where point 5 has to print), the
point-5 zone, an Elliott ALTERNATIVE count in the other direction, wave ratios, A-B-C labels,
and three studies Pine does not have (Fibonacci extension, anchored VWAP, volume profile).
Each addition is named in `methodology` as the terminal's own.

VOLUME. SignalMesh stores MT5 TICK volume (price changes per bar), not traded size. Anchored
VWAP and the volume profile are therefore TICK-VOLUME ACTIVITY studies and say so everywhere.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .smc import _epoch, pivots

VERSION = "pattern-studies-v1"
LEVEL_LABEL = "HYPOTHETICAL ANALYSIS LEVEL"
MIN_BARS = 60
TF_SEC = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400}
STUDY_TFS = tuple(TF_SEC)

FIB_L = 5                                   # pivot strength of the Fibonacci anchors and the VWAP anchors
FIB_RATIOS = (0.618, 1.0, 1.272, 1.618, 2.0, 2.618)
WW_L, WW_TOL_PCT, WW_SL_ATR, WW_MAX_APEX = 10, 15.0, 0.5, 1.0        # Pine wwLen, wwTolPct, wwSLATR, wwMaxApex
EW_L, EW_MIN_ATR, EW_MIN_W2 = 8, 3.0, 23.6                           # Pine ewLen, ewMinATR, ewMinW2
VP_ROWS, VP_VALUE_AREA = 40, 70.0

METHODOLOGY = {
    "all": "display-only terminal studies from SignalMesh's stored CLOSED candles of the chart's timeframe; walked forward bar by bar, "
           "no lookahead; a swing pivot is confirmed L bars after it; nothing is recorded or stored; not SignalMesh engine output",
    "fibonacci_extension": f"terminal's own: the last three alternating swing pivots (strength {FIB_L}) are A, B, C when C is a pullback that holds inside A-B (when the newest pivot went beyond A, the three before it); levels = C + ratio x (B - A) for "
                           f"{', '.join(str(r) for r in FIB_RATIOS)}; upward when A is a low. A level is REACHED when a later closed bar trades it; "
                           "the set is INVALIDATED when a bar closes beyond C. A new pivot makes a new set",
    "anchored_vwap": f"terminal's own: sum(typical price x tick volume) / sum(tick volume) from the anchor bar onward, typical = (high + low + close) / 3. "
                     f"Anchors: the highest confirmed swing high and the lowest confirmed swing low (strength {FIB_L}) in the loaded bars, and the start of "
                     "the broker day. Band = one tick-volume-weighted standard deviation. TICK volume, not traded volume",
    "wolfe_wave": f"from Pine §27: the last 5 alternating pivots (strength {WW_L}); bullish wedge = 1 low, 3 below 1, 5 below 3, 4 below 2 and above 1, "
                  f"line 2-4 falling faster than line 1-3, point 5 within {WW_TOL_PCT:.0f}% of the pattern height of line 1-3; bearish is the mirror. Apex = where "
                  f"1-3 and 2-4 meet, no further than {WW_MAX_APEX:g} x the pattern length after point 5. Entry = close of the detecting bar, SL = point 5 "
                  f"-/+ {WW_SL_ATR} ATR, TP1 = nearer of point 4 and EPA (line 1-4 at the apex), TP2 = the further. Expires one pattern length after the apex. "
                  "Terminal's addition: DEVELOPING when points 1-4 fit and point 5 has not printed, with the zone where it must print — never shown as confirmed",
    "elliott_wave": f"from Pine §27B: impulse count on the last 6 alternating pivots (strength {EW_L}); wave 1 at least {EW_MIN_ATR:g} ATR, wave 2 retraces at "
                    f"least {EW_MIN_W2}% and never passes the start of wave 1, wave 3 ends beyond wave 1, wave 4 never enters wave 1, wave 3 is never the "
                    "shortest. Stages and targets as in Pine. Terminal's additions: an ALTERNATIVE count in the other direction when the same rules allow "
                    "one, wave ratios, and A / B / C labels on the pivots after a finished five. No valid count reads UNKNOWN",
    "volume_profile": f"terminal's own: each bar's TICK volume is spread evenly over its high-low range into {VP_ROWS} price rows across the loaded bars. "
                      f"POC = the busiest row; value area = rows added outward from the POC until {VP_VALUE_AREA:.0f}% of the activity is inside (VAH / VAL). "
                      "HVN / LVN = local peaks / troughs. Tick-volume ACTIVITY, not traded volume",
}


def _iso(t: int | float | None) -> str | None:
    return None if t is None else datetime.fromtimestamp(int(t), timezone.utc).isoformat()


def bars_from(payload: dict | None) -> list[dict]:
    """SignalMesh candle payload -> [{t, o, h, l, c, v}] ascending; v = MT5 tick volume (0 when not stored)."""
    out = []
    for k in (payload or {}).get("candles") or []:
        t = _epoch(k.get("ts", k.get("time")))
        try:
            v = k.get("tick_volume", k.get("volume"))
            out.append({"t": t, "o": float(k["open"]), "h": float(k["high"]), "l": float(k["low"]), "c": float(k["close"]),
                        "v": float(v) if v not in (None, "") else 0.0})
        except (KeyError, TypeError, ValueError):
            continue
    out = [b for b in out if b["t"] is not None]
    out.sort(key=lambda b: b["t"])
    return out


def atr_rma(b: list[dict], n: int = 14) -> list[float | None]:
    """Wilder's ATR, as Pine's ta.atr: the mean of the first n true ranges, then smoothed."""
    out: list[float | None] = []
    a = None
    s = 0.0
    for i, k in enumerate(b):
        tr = k["h"] - k["l"] if i == 0 else max(k["h"] - k["l"], abs(k["h"] - b[i - 1]["c"]), abs(k["l"] - b[i - 1]["c"]))
        if i < n:
            s += tr
            a = s / n if i == n - 1 else None
        else:
            a = (a * (n - 1) + tr) / n
        out.append(a)
    return out


def _by_confirmation(b: list[dict], L: int) -> dict[int, list[dict]]:
    """Confirmed pivots grouped by the bar that confirms them; lows before highs, as Pine adds them."""
    out: dict[int, list[dict]] = {}
    for p in pivots(b, L):
        out.setdefault(p["ci"], []).append(p)
    for v in out.values():
        v.sort(key=lambda p: 0 if p["kind"] == "L" else 1)
    return out


def _add(lst: list[dict], p: dict, keep: int) -> int:
    """Pine's alternating-pivot list: 0 nothing, 1 newest replaced by a more extreme one, 2 new pivot added."""
    if lst and lst[-1]["kind"] == p["kind"]:
        if (p["kind"] == "H" and p["price"] > lst[-1]["price"]) or (p["kind"] == "L" and p["price"] < lst[-1]["price"]):
            lst[-1] = p
            return 1
        return 0
    lst.append(p)
    if len(lst) > keep:
        lst.pop(0)
    return 2


def _pt(b: list[dict], p: dict, name: str = "") -> dict:
    return {"name": name, "kind": p["kind"], "price": p["price"], "time": b[p["i"]]["t"]}


# ------------------------------------------------------------------ Fibonacci extension
def fib_extension(b: list[dict], step: int) -> dict:
    conf = _by_confirmation(b, FIB_L)
    piv: list[dict] = []
    log: list[dict] = []
    cur = None
    ident = None
    for j in range(len(b)):
        chg = 0
        for p in conf.get(j, []):
            chg = max(chg, _add(piv, p, 4))
        if not chg or len(piv) < 3:
            continue
        # C must be a pullback that holds inside A-B. The newest three pivots first; when the newest pivot went
        # beyond A it is not a pullback but the move itself, and the three pivots before it are the set it is running from.
        pick = None
        for tri in ([piv[-3:]] + ([piv[-4:-1]] if len(piv) == 4 else [])):
            A, B, C = tri
            leg = B["price"] - A["price"]
            if leg and abs(B["price"] - C["price"]) < abs(leg):
                pick = tri
                break
        if pick is None:
            if ident is not None:
                log.append({"direction": "NONE", "made_bar": b[j]["t"], "confirmed_at": b[j]["t"] + step})
            cur, ident = None, None
            continue
        A, B, C = pick
        key = (A["i"], B["i"], C["i"])
        if key == ident:
            continue
        ident = key
        up = A["kind"] == "L"
        leg = B["price"] - A["price"]
        cur = {"direction": "UP" if up else "DOWN", "a": _pt(b, A, "A"), "b": _pt(b, B, "B"), "c": _pt(b, C, "C"), "leg": abs(leg), "c_index": C["i"],
               "made_bar": b[j]["t"], "confirmed_at": b[j]["t"] + step,
               "retrace_pct": round(abs(B["price"] - C["price"]) / abs(leg) * 100, 1),
               "levels": [{"ratio": r, "price": C["price"] + r * leg} for r in FIB_RATIOS]}
        log.append({k: cur[k] for k in ("direction", "a", "b", "c", "made_bar", "confirmed_at")})
    if not cur:
        return {"state": "NONE", "note": f"no A-B-C on the confirmed swing pivots (strength {FIB_L}) where C is a pullback that holds inside A-B", "log": log}
    up = cur["direction"] == "UP"
    after = b[cur["c_index"] + 1:]
    hi = max((k["h"] for k in after), default=None)
    lo = min((k["l"] for k in after), default=None)
    for lv in cur["levels"]:
        lv["reached"] = bool(after) and (hi >= lv["price"] if up else lo <= lv["price"])
    c_price = cur["c"]["price"]
    broke = next((k for k in after if (k["c"] < c_price if up else k["c"] > c_price)), None)
    nxt = next((lv for lv in cur["levels"] if not lv["reached"]), None)
    out = {**cur, "state": "OK", "status": "INVALIDATED" if broke else "ACTIVE", "invalidation": c_price,
           "invalidated_bar": broke["t"] if broke else None, "next_level": nxt, "level_label": LEVEL_LABEL, "log": log,
           "rule": "invalid on a close beyond C" + (" (below)" if up else " (above)")}
    out.pop("c_index")
    return out


# ------------------------------------------------------------------ anchored VWAP
def _avwap(b: list[dict], start: int) -> tuple[list[dict], float | None]:
    pv = vv = pv2 = 0.0
    pts = []
    sd = None
    for k in b[start:]:
        tp = (k["h"] + k["l"] + k["c"]) / 3
        pv += tp * k["v"]
        vv += k["v"]
        pv2 += tp * tp * k["v"]
        if vv > 0:
            m = pv / vv
            sd = max(pv2 / vv - m * m, 0.0) ** 0.5
            pts.append({"t": k["t"], "v": m})
    return pts, sd


def anchored_vwap(b: list[dict], atr: float | None, day_start: int | None = None) -> dict:
    if not any(k["v"] > 0 for k in b):
        return {"state": "NOT_AVAILABLE", "note": "no tick volume is stored for these bars, so a volume-weighted price cannot be calculated", "anchors": []}
    piv = pivots(b, FIB_L)
    highs, lows = [p for p in piv if p["kind"] == "H"], [p for p in piv if p["kind"] == "L"]
    cands: list[tuple[str, str, int]] = []
    if highs:
        cands.append(("swing-high", "highest confirmed swing high", max(highs, key=lambda p: (p["price"], p["i"]))["i"]))
    if lows:
        cands.append(("swing-low", "lowest confirmed swing low", min(lows, key=lambda p: (p["price"], -p["i"]))["i"]))
    if day_start is not None:
        i = next((n for n, k in enumerate(b) if k["t"] >= day_start), None)
        if i is not None and b[0]["t"] <= day_start:
            cands.append(("day", "start of the broker day", i))
    last = b[-1]["c"]
    anchors = []
    for aid, name, i in cands:
        pts, sd = _avwap(b, i)
        if not pts:
            continue
        v = pts[-1]["v"]
        anchors.append({"id": aid, "name": name, "anchor_time": b[i]["t"], "anchor_price": b[i]["h"] if aid == "swing-high" else b[i]["l"] if aid == "swing-low" else b[i]["o"],
                        "bars": len(b) - i, "value": v, "sd": sd, "upper": v + (sd or 0), "lower": v - (sd or 0),
                        "side": "ABOVE" if last > v else "BELOW" if last < v else "AT", "distance": last - v,
                        "distance_atr": round((last - v) / atr, 2) if atr else None, "points": pts})
    if not anchors:
        return {"state": "NONE", "note": "no confirmed swing and no day start inside the loaded bars to anchor from", "anchors": []}
    sides = {a["side"] for a in anchors}
    read = ("price is ABOVE every anchored VWAP: buyers since each anchor are in profit on average" if sides == {"ABOVE"}
            else "price is BELOW every anchored VWAP: buyers since each anchor are at a loss on average" if sides == {"BELOW"}
            else "price is between the anchored VWAPs: mixed")
    return {"state": "OK", "anchors": anchors, "last": last, "reading": read, "volume_kind": "MT5 tick volume (activity), not traded volume"}


# ------------------------------------------------------------------ Wolfe wave
def wolfe(b: list[dict], atr: list[float | None], step: int) -> dict:
    conf = _by_confirmation(b, WW_L)
    piv: list[dict] = []
    log: list[dict] = []
    cur: dict | None = None
    last_eval = None
    tm = lambda x: b[x]["t"] if x < len(b) else b[-1]["t"] + (x - (len(b) - 1)) * step      # noqa: E731  a bar index -> time, estimated past the newest bar
    for j in range(len(b)):
        for p in conf.get(j, []):
            _add(piv, p, 5)
        if len(piv) == 5 and piv[4]["i"] != last_eval:
            last_eval = piv[4]["i"]
            q = [p["price"] for p in piv]
            x = [p["i"] for p in piv]
            s13, s24, s14 = (q[2] - q[0]) / (x[2] - x[0]), (q[3] - q[1]) / (x[3] - x[1]), (q[3] - q[0]) / (x[3] - x[0])
            hgt = abs(q[1] - q[0])
            l13 = q[0] + s13 * (x[4] - x[0])
            first_low = piv[0]["kind"] == "L"
            bull = first_low and q[2] < q[0] and q[4] < q[2] and q[3] < q[1] and q[3] > q[0] and s24 < s13 and q[4] <= l13 + hgt * WW_TOL_PCT / 100
            bear = (not first_low) and q[2] > q[0] and q[4] > q[2] and q[3] > q[1] and q[3] < q[0] and s24 > s13 and q[4] >= l13 - hgt * WW_TOL_PCT / 100
            a = atr[j]
            if (bull or bear) and s13 != s24 and a:
                xa = (q[1] - q[0] + s13 * x[0] - s24 * x[1]) / (s13 - s24)
                epa = q[0] + s14 * (xa - x[0])
                if xa > x[4] and xa - x[4] <= (x[4] - x[0]) * WW_MAX_APEX and (epa > q[4] if bull else epa < q[4]):
                    if cur and not cur["done"]:
                        cur["status"], cur["done"], cur["status_bar"] = "SUPERSEDED by a newer pattern", True, b[j]["t"]
                    entry, sl = b[j]["c"], (q[4] - a * WW_SL_ATR if bull else q[4] + a * WW_SL_ATR)
                    tp1, tp2 = (min(q[3], epa), max(q[3], epa)) if bull else (max(q[3], epa), min(q[3], epa))
                    risk = abs(entry - sl)
                    apex = int(round(xa))
                    cur = {"direction": "BULLISH" if bull else "BEARISH", "side": "LONG" if bull else "SHORT",
                           "points": [_pt(b, p, str(n + 1)) for n, p in enumerate(piv)],
                           "entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2, "epa": epa, "invalidation": sl,
                           "rr1": round(abs(tp1 - entry) / risk, 2) if risk else None, "rr2": round(abs(tp2 - entry) / risk, 2) if risk else None,
                           "apex_time": tm(apex), "expires_time": tm(apex + (x[4] - x[0])), "line_13_at_5": l13,
                           "zone_5": sorted([l13, l13 + hgt * WW_TOL_PCT / 100 * (1 if bull else -1)]),
                           "made_bar": b[j]["t"], "confirmed_at": b[j]["t"] + step, "status": "LIVE", "status_bar": b[j]["t"], "done": False,
                           "_j": j, "_apex": apex, "_len": x[4] - x[0], "level_label": LEVEL_LABEL}
                    log.append(cur)
                    continue
        if cur and not cur["done"] and j > cur["_j"]:
            k, up = b[j], cur["side"] == "LONG"
            hit_sl = k["l"] <= cur["sl"] if up else k["h"] >= cur["sl"]
            hit2 = k["h"] >= cur["tp2"] if up else k["l"] <= cur["tp2"]
            hit1 = k["h"] >= cur["tp1"] if up else k["l"] <= cur["tp1"]
            if hit_sl:
                cur["status"], cur["done"], cur["status_bar"] = "STOPPED beyond point 5", True, k["t"]
            elif hit2:
                cur["status"], cur["done"], cur["status_bar"] = "TP2 (EPA) HIT", True, k["t"]
            elif hit1 and cur["status"] == "LIVE":
                cur["status"], cur["status_bar"] = "TP1 (point 4) HIT", k["t"]
            elif j > cur["_apex"] + cur["_len"]:
                cur["status"], cur["done"], cur["status_bar"] = "EXPIRED", True, k["t"]
    clean = [{k: v for k, v in p.items() if not k.startswith("_")} for p in log]
    live = clean[-1] if clean and not clean[-1]["done"] else None
    developing = None
    if not live and len(piv) >= 4 and b:
        p4 = piv[-4:]
        q, x = [p["price"] for p in p4], [p["i"] for p in p4]
        s13, s24 = (q[2] - q[0]) / (x[2] - x[0]), (q[3] - q[1]) / (x[3] - x[1])
        first_low = p4[0]["kind"] == "L"
        bull = first_low and q[2] < q[0] and q[3] < q[1] and q[3] > q[0] and s24 < s13
        bear = (not first_low) and q[2] > q[0] and q[3] > q[1] and q[3] < q[0] and s24 > s13
        if bull or bear:
            now = len(b) - 1
            l13 = q[0] + s13 * (now - x[0])
            tol = abs(q[1] - q[0]) * WW_TOL_PCT / 100
            lim = min(q[2], l13 + tol) if bull else max(q[2], l13 - tol)
            developing = {"direction": "BULLISH" if bull else "BEARISH", "status": "DEVELOPING — 4 of 5 points, NOT confirmed",
                          "points": [_pt(b, p, str(n + 1)) for n, p in enumerate(p4)], "line_13_now": l13, "point_5_limit": lim,
                          "waiting_for": (f"a confirmed swing {'low' if bull else 'high'} {'at or below' if bull else 'at or above'} the limit "
                                          f"(beyond point 3 and within {WW_TOL_PCT:.0f}% of the pattern height of line 1-3)")}
    return {"state": "OK" if live else "DEVELOPING" if developing else "NONE", "pattern": live, "developing": developing,
            "last_finished": next((p for p in reversed(clean) if p["done"]), None), "log": clean,
            "note": "" if live or developing else "no Wolfe wedge on the last five confirmed pivots"}


# ------------------------------------------------------------------ Elliott wave
def _ew_valid(piv: list[dict], k: int, a: float | None) -> bool:
    n = len(piv)
    if n < k or not a:
        return False
    sg = 1.0 if piv[n - k]["kind"] == "L" else -1.0
    q = [piv[n - k + i]["price"] * sg for i in range(k)]
    w1 = q[1] - q[0]
    ok = w1 > 0 and w1 >= a * EW_MIN_ATR and q[0] < q[2] < q[1] and (q[1] - q[2]) >= w1 * EW_MIN_W2 / 100
    if ok and k >= 4:
        ok = q[3] > q[1]
    if ok and k >= 5:
        ok = q[1] < q[4] < q[3]
    if ok and k == 6:
        ok = q[5] > q[3] and (q[3] - q[2]) >= min(w1, q[5] - q[4])
    return ok


def _ew_count(b: list[dict], piv: list[dict], k: int) -> dict:
    """The stage, levels and ratios of a valid k-pivot count (Pine's stage table)."""
    n = len(piv)
    pts = piv[n - k:]
    d = 1.0 if pts[0]["kind"] == "L" else -1.0
    a = [p["price"] for p in pts]
    w1 = abs(a[1] - a[0])
    side = "BULL" if d > 0 else "BEAR"
    ratios = {"wave2_retrace_pct": round(abs(a[1] - a[2]) / w1 * 100, 1)}
    if k >= 4:
        ratios["wave3_vs_wave1"] = round(abs(a[3] - a[2]) / w1, 2)
    if k >= 5:
        ratios["wave4_retrace_pct"] = round(abs(a[3] - a[4]) / abs(a[3] - a[2]) * 100, 1)
    if k == 6:
        ratios["wave5_vs_wave1"] = round(abs(a[5] - a[4]) / w1, 2)
    if k == 3:
        wave, inv, brk, t1, t2 = 3, a[2], a[1], a[2] + d * w1, a[2] + d * w1 * 1.618
        text, t1n, t2n = f"{side} WAVE 3 setup (1-2 done)", "wave 3 = wave 1", "wave 3 = 1.618 x wave 1"
    elif k == 4:
        wave, inv, brk, t1, t2 = 4, a[1], a[3], a[3] - d * abs(a[3] - a[2]) * 0.382, a[3] - d * abs(a[3] - a[2]) * 0.5
        text, t1n, t2n = f"{side} WAVE 4 pullback (3 done): {'buy' if d > 0 else 'sell'} zone, then wave 5", "38.2% of wave 3", "50% of wave 3"
    elif k == 5:
        ta_, tb = a[4] + d * w1, a[4] + d * abs(a[3] - a[0]) * 0.618
        wave, inv, brk = 5, a[4], a[3]
        t1, t2 = (min(ta_, tb), max(ta_, tb)) if d > 0 else (max(ta_, tb), min(ta_, tb))
        text, t1n, t2n = f"{side} WAVE 5 running (last push, do not add late)", "nearer wave-5 target", "further wave-5 target"
    else:
        wave, inv, brk, t1, t2 = 6, a[5], a[5], a[5] - d * abs(a[5] - a[0]) * 0.382, a[5] - d * abs(a[5] - a[0]) * 0.618
        text, t1n, t2n = f"{side} 5 WAVES DONE: expect A-B-C {'down' if d > 0 else 'up'}, no chase", "38.2% of the whole move", "61.8% of the whole move"
    names = ["0", "1", "2", "3", "4", "5"]
    return {"direction": "BULLISH" if d > 0 else "BEARISH", "dir": 1 if d > 0 else -1, "wave": wave, "text": text, "invalidation": inv, "break_level": brk,
            "target_1": t1, "target_2": t2, "target_1_name": t1n, "target_2_name": t2n, "ratios": ratios, "rules_met": f"{k - 2} of 4 impulse checks passed so far",
            "points": [_pt(b, p, names[i]) for i, p in enumerate(pts)], "level_label": LEVEL_LABEL}


def elliott(b: list[dict], atr: list[float | None], step: int) -> dict:
    conf = _by_confirmation(b, EW_L)
    piv: list[dict] = []
    log: list[dict] = []
    cur: dict | None = None
    note = "no clear count yet"
    cnt = done_cnt = made = 0
    key = ""
    for j in range(len(b)):
        chg = 0
        for p in conf.get(j, []):
            chg = max(chg, _add(piv, p, 6))
        if chg == 2:
            cnt += 1
        c = b[j]["c"]
        if cur and 3 <= cur["wave"] <= 5 and (c - cur["invalidation"]) * cur["dir"] < 0:
            note = f"{'BULL' if cur['dir'] == 1 else 'BEAR'} count FAILED: closed beyond {cur['invalidation']:.6g}"
            log.append({"event": "FAILED", "bar": b[j]["t"], "text": note})
            cur, key = None, ""
        if cur and cur["wave"] == 6 and ((c - cur["invalidation"]) * cur["dir"] > 0 or cnt - done_cnt >= 3):
            note = (f"wave 5 EXTENDING beyond {cur['invalidation']:.6g}" if (c - cur["invalidation"]) * cur["dir"] > 0
                    else "A-B-C correction likely done: watch for a new impulse")
            log.append({"event": "ENDED", "bar": b[j]["t"], "text": note})
            cur, key = None, ""
        if chg > 0 and not (cur and cur["wave"] == 6):
            k = next((n for n in (6, 5, 4, 3) if _ew_valid(piv, n, atr[j])), 0)
            if k == 0:
                if cur:
                    note = "no clear count (range / complex correction)"
                    log.append({"event": "UNCLEAR", "bar": b[j]["t"], "text": note})
                cur, key = None, ""
            else:
                cur = _ew_count(b, piv, k)
                if cur["wave"] == 6:
                    done_cnt = cnt
                nk = f"{cur['dir']}/{cur['wave']}/{cur['points'][0]['price']}"
                if nk != key:
                    key = nk
                    made = b[j]["t"]
                    cur["made_bar"], cur["confirmed_at"] = made, made + step
                    log.append({"event": "STAGE", "bar": b[j]["t"], "text": cur["text"], "direction": cur["direction"], "wave": cur["wave"],
                                "points": cur["points"], "invalidation": cur["invalidation"], "target_1": cur["target_1"], "target_2": cur["target_2"]})
                else:
                    cur["made_bar"], cur["confirmed_at"] = made, made + step
    if not cur:
        return {"state": "UNKNOWN", "note": note, "count": None, "alternative": None, "abc": [], "log": log}
    last = b[-1]["c"]
    if cur["wave"] == 3:
        cur["confirmation"] = ("CONFIRMED: closed beyond the wave-1 end" if (last - cur["break_level"]) * cur["dir"] > 0
                               else "DEVELOPING: needs a close beyond the wave-1 end")
    else:
        cur["confirmation"] = "CONFIRMED pivots" if cur["wave"] != 6 else "five waves counted"
    t5 = cur["points"][-1]["time"]
    abc = [_pt(b, p, n) for p, n in zip([p for p in piv if b[p["i"]]["t"] > t5], "ABC")] if cur["wave"] == 6 else []
    # terminal's own: the best valid count in the OTHER direction on the same pivots (stateless, shown beside the main one)
    alt = None
    for n in (6, 5, 4, 3):
        if len(piv) >= n and (piv[len(piv) - n]["kind"] == "L") != (cur["dir"] == 1) and _ew_valid(piv, n, atr[-1]):
            alt = _ew_count(b, piv, n)
            break
    return {"state": "OK", "count": cur, "alternative": alt, "abc": abc, "log": log,
            "note": "" if alt else "no valid count in the other direction on these pivots"}


# ------------------------------------------------------------------ volume profile
def volume_profile(b: list[dict]) -> dict:
    total = sum(k["v"] for k in b)
    if total <= 0:
        return {"state": "NOT_AVAILABLE", "note": "no tick volume is stored for these bars", "rows": []}
    lo, hi = min(k["l"] for k in b), max(k["h"] for k in b)
    if hi <= lo:
        return {"state": "NOT_AVAILABLE", "note": "the loaded bars have no price range", "rows": []}
    h = (hi - lo) / VP_ROWS
    vol = [0.0] * VP_ROWS
    for k in b:
        if k["v"] <= 0:
            continue
        a, z = min(int((k["l"] - lo) / h), VP_ROWS - 1), min(int((k["h"] - lo) / h), VP_ROWS - 1)
        rng = k["h"] - k["l"]
        for r in range(a, z + 1):
            part = 1.0 if rng <= 0 else max(0.0, min(k["h"], lo + (r + 1) * h) - max(k["l"], lo + r * h)) / rng
            vol[r] += k["v"] * part
    poc = max(range(VP_ROWS), key=lambda r: (vol[r], -r))
    a = z = poc
    inside = vol[poc]
    while inside < total * VP_VALUE_AREA / 100 and (a > 0 or z < VP_ROWS - 1):
        up, dn = (vol[z + 1] if z < VP_ROWS - 1 else -1), (vol[a - 1] if a > 0 else -1)
        if up >= dn:
            z += 1
            inside += vol[z]
        else:
            a -= 1
            inside += vol[a]
    mx = vol[poc]
    mid = lambda r: lo + (r + 0.5) * h      # noqa: E731
    hvn = [r for r in range(1, VP_ROWS - 1) if r != poc and vol[r] > vol[r - 1] and vol[r] >= vol[r + 1] and vol[r] >= 0.6 * mx]
    lvn = [r for r in range(a + 1, z) if vol[r] < vol[r - 1] and vol[r] <= vol[r + 1] and vol[r] <= 0.35 * mx]
    last = b[-1]["c"]
    vah, val = lo + (z + 1) * h, lo + a * h
    return {"state": "OK", "rows": [{"low": lo + r * h, "high": lo + (r + 1) * h, "volume": round(vol[r], 2), "pct_of_max": round(vol[r] / mx * 100, 1),
                                     "in_value_area": a <= r <= z, "poc": r == poc} for r in range(VP_ROWS)],
            "poc": mid(poc), "vah": vah, "val": val, "value_area_pct": round(inside / total * 100, 1), "total_tick_volume": round(total, 2),
            "hvn": [mid(r) for r in sorted(hvn, key=lambda r: -vol[r])[:3]], "lvn": [mid(r) for r in sorted(lvn, key=lambda r: vol[r])[:3]],
            "from_time": b[0]["t"], "to_time": b[-1]["t"], "bars": len(b), "last": last,
            "position": "ABOVE the value area" if last > vah else "BELOW the value area" if last < val else "INSIDE the value area",
            "reading": ("above value: accepted higher, the value area high is the first support" if last > vah
                        else "below value: accepted lower, the value area low is the first resistance" if last < val
                        else "inside value: balance, the POC is the magnet"),
            "volume_kind": "MT5 tick volume (activity), not traded volume"}


# ------------------------------------------------------------------ all five, one payload
def analyse(symbol: str, tf: str, b: list[dict], source: str = "", day_start: int | None = None) -> dict:
    step = TF_SEC.get(tf, 900)
    base = {"symbol": symbol, "tf": tf, "kind": "TERMINAL STUDY — display only, not SignalMesh engine output", "method_version": VERSION,
            "methodology": METHODOLOGY, "level_label": LEVEL_LABEL, "stored": False,
            "stored_note": "not recorded in the forecast journal and kept nowhere: calculated from the closed bars each time the chart asks",
            "source": source, "bars_used": len(b), "calculated_at": datetime.now(timezone.utc).isoformat(),
            "through_bar": b[-1]["t"] if b else None, "through_close": b[-1]["t"] + step if b else None,
            "through_close_utc": _iso(b[-1]["t"] + step) if b else None}
    if len(b) < MIN_BARS:
        return {**base, "state": "NOT_AVAILABLE", "note": f"{len(b)} closed {tf} bars stored; the studies need at least {MIN_BARS}",
                "atr": None, "fib": None, "avwap": None, "wolfe": None, "elliott": None, "vp": None}
    atr = atr_rma(b)
    return {**base, "state": "OK", "note": "", "atr": atr[-1], "last_close": b[-1]["c"],
            "fib": fib_extension(b, step), "avwap": anchored_vwap(b, atr[-1], day_start if step < 86400 else None),
            "wolfe": wolfe(b, atr, step), "elliott": elliott(b, atr, step), "vp": volume_profile(b)}
