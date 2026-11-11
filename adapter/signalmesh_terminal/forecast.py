"""FORECASTING STUDIES, step 2 — DAILY FORECAST TOP / BOTTOM and the ASSET RANKING TABLE.

The terminal's own DISPLAY-ONLY studies (daily-forecast-v1, rotation-v1), ported from Shyam's
TradingView scripts: "SMC METAL HUNTER V15.0" section 13D (daily forecast) and "MH15 PLUS"
section 13H (money rotation ladder). They are NOT SignalMesh engine output, they feed no
decision, level, signal or statistic, and they place no order. Every entry / stop / target
shown is a HYPOTHETICAL ANALYSIS LEVEL.

CLOSED CANDLES ONLY, NO LOOKAHEAD
  * ADR = the mean high-low range of the last 14 COMPLETED daily bars before the day in question.
  * "Today" is the broker's own day: it starts where SignalMesh's stored daily bars start
    (the MT5 server day), not at TradingView's 17:00 New York. Today's high / low / last price
    come from CLOSED intraday bars since that start — never from a forming bar.
  * A value for bar T uses bars up to and including T only (tests/test_forecast.py recomputes on
    every prefix).

DAILY FORECAST (Pine 13D, same formulas)
  top_raw    = today's low  + ADR          bottom_raw = today's high - ADR
  top        = max(snap(top_raw), today's high)      bottom = min(snap(bottom_raw), today's low)
  snap       = move the raw level onto the newest confirmed 4h swing high / low, or the previous
               day's high / low, when one lies within 0.5 x ATR(14, 4h) of it (nearest wins)
  top done   = today's high >= top_raw      bottom done = today's low <= bottom_raw
  status     words as in Pine: ADR n% used / NEAR FULL ADR (>= 85 %) / BOTH SIDES DONE
  NOTE       "top done" and "bottom done" are ONE condition (high >= low + ADR is the same as low <= high - ADR):
             both become true on the same bar, so Pine's separate "TOP IN" and "BOTTOM IN" texts can never appear.
             The terminal keeps Pine's status and adds WHICH extreme completed the range (a new high or a new low).

ROTATION LADDER (Pine 13H, same thresholds)
  used %     = today's range / ADR x 100          move % = (last close - previous day's close) / ADR x 100
  state      < 35 FRESH (quiet) · >= 35 MOVING UP / DOWN · >= 85 NEAR FULL · >= 100 DONE - sleep
  score      = (room x 0.5 + min(|move|, 60)) x (1 inside the asset's active session, else 0.5); room = 100 - used, 0 when done
  GO TRADE   = the asset with the highest score

WHERE THE TERMINAL DIFFERS FROM PINE (each one is also in `methodology`)
  * the day is the broker's (see above); * the newest bar is always a closed one;
  * the ladder ranks the instruments SignalMesh stores, not seven fixed TradingView symbols;
  * HTF resistance / support for the snap are the terminal's own confirmed 4h swings (smc-v1, L=5);
  * Pine's event mode needs a hand-set clock and is not ported: a full day reads DONE, never EXPANSION;
  * Pine gives no stop or target for "top in / bottom in". So that the statement can be MEASURED in
    the forecast journal, the terminal adds its own fixed, labelled scenario (see FADE below).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from . import smc
from .discovery import category

DAILY_VERSION = "daily-forecast-v1"
ROTATION_VERSION = "rotation-v1"
LEVEL_LABEL = "HYPOTHETICAL ANALYSIS LEVEL"
ADR_LEN = 14                # Pine fcLen
NEAR_PCT = 85.0             # Pine fcNearPct
FULL_PCT = 100.0            # Pine rotFullPct
AWAKE_PCT = 35.0            # Pine rotAwakePct
MAGNET_ATR = 0.5            # Pine fcMagnetATR
DAY = 86400
# FADE — the terminal's own rule for scoring "ADR full: fade, no chase" (Pine has none): on the first closed
# bar where the day's range reaches ADR, the scenario fades the extreme that bar made, from its close; it is wrong (stop and
# invalidation) a quarter of an ADR beyond the day's extreme; targets a quarter and a half ADR back;
# it expires at the end of the broker day. Needs at least FADE_MIN_BARS bars left in the day.
FADE_STOP_ADR, FADE_TP1_ADR, FADE_TP2_ADR, FADE_MIN_BARS = 0.25, 0.25, 0.5, 4
NY = ZoneInfo("America/New_York")

METHODOLOGY = {
    "adr": f"ADR = mean (high - low) of the last {ADR_LEN} COMPLETED daily bars before the day (SignalMesh's stored 1d bars; the running day is never in it)",
    "day": "the day is the BROKER's: it starts where the stored daily bars start (MT5 server day). TradingView's OANDA day starts 17:00 New York, so "
           "ADR, 'today' and the previous day can differ from the Pine script by the hours between the two day starts",
    "today": "today's high, low and last price come from CLOSED intraday bars since the day started (15m, else 1h); a forming bar is never read",
    "top_bottom": "top_raw = today's low + ADR · bottom_raw = today's high - ADR · top = max(snapped top_raw, today's high) · bottom = min(snapped bottom_raw, today's low). "
                  "Both move during the day while the extremes extend",
    "snap": f"a raw level within {MAGNET_ATR} x ATR(14, 4h) of the newest confirmed 4h swing high / low (terminal smc-v1, L=5) or of the previous day's high / low "
            "is moved onto it (nearest wins). No stored 4h bars = no snap",
    "done": "ADR FULL when today's range >= ADR. Pine's 'top done' (high >= low + ADR) and 'bottom done' (low <= high - ADR) are the same condition, so both turn true "
            "on the same bar and Pine's separate TOP IN / BOTTOM IN texts never appear; the terminal adds which extreme completed the range (a new high = top in, a new low = bottom in)",
    "status": f"ADR n% used · NEAR FULL ADR from {NEAR_PCT:.0f}% · BOTH SIDES DONE (range > ADR, expansion day) — Pine's own words",
    "fade_scenario": f"TERMINAL'S OWN RULE, not Pine's (Pine names no stop or target): on the first closed 15m bar where the day's range reaches ADR, the scenario fades the extreme that bar made, from that "
                     f"bar's close; stop and invalidation {FADE_STOP_ADR} x ADR beyond the day's extreme at that bar; TP1 {FADE_TP1_ADR} x ADR and TP2 {FADE_TP2_ADR} x ADR back; "
                     f"expires at the end of the broker day; needs {FADE_MIN_BARS}+ bars left; one per day. It exists so the journal can measure 'ADR full: fade, no chase'",
    "ladder": f"used % = today's range / ADR · move % = (last close - previous day's close) / ADR · FRESH < {AWAKE_PCT:.0f} · MOVING UP/DOWN · NEAR FULL >= {NEAR_PCT:.0f} · "
              f"DONE >= {FULL_PCT:.0f} · score = (room x 0.5 + min(|move|, 60)) x (1 in the asset's session, else 0.5) · GO TRADE = highest score. It ranks ROOM LEFT; it does not predict where money goes",
    "sessions": "New York time: Asia 19:00-03:00, London 03:00-08:00, New York 08:00-17:00. Metals, energy and FX: London or New York (JPY pairs: Asia or New York); "
                "indices and stocks: New York; crypto: always",
    "not_ported": "Pine's event mode (hand-set event clock) is not ported: a full day reads DONE, never EXPANSION",
    "outlooks": "weekly / monthly / 3-month ranges use the same formula on closed ISO weeks, months and quarters built from stored daily bars (terminal's extension, not in Pine); "
                f"a period with fewer than {ADR_LEN} completed periods of history reads UNKNOWN (6-month does)",
    "confidence": "UNKNOWN until the forecast journal holds enough scored forecasts for this module, symbol and timeframe; then the measured hit rate with its sample size",
}


def _iso(t: int | None) -> str | None:
    return None if t is None else datetime.fromtimestamp(int(t), timezone.utc).isoformat()


def _mean_range(bars: list[dict]) -> float | None:
    return sum(b["h"] - b["l"] for b in bars) / len(bars) if bars else None


def split_day(daily: list[dict], intraday: list[dict], step: int) -> dict:
    """Which closed intraday bars belong to the running broker day. `daily` = closed 1d bars."""
    if len(daily) < ADR_LEN + 1:
        return {"state": "NOT_AVAILABLE", "note": f"{len(daily)} closed daily bars stored — {ADR_LEN + 1} are needed for ADR; nothing is shown rather than guessed"}
    if not intraday:
        return {"state": "NOT_AVAILABLE", "note": "no closed intraday bars stored for this instrument"}
    last = daily[-1]["t"]
    k = (intraday[-1]["t"] - last) // DAY
    if k < 1:
        return {"state": "NOT_AVAILABLE", "note": "the newest intraday bar is not newer than the last closed daily bar — the new day has not started in the stored data"}
    start = last + k * DAY
    stray = [b for b in intraday if last + DAY <= b["t"] < start]
    if k > 4 or len(stray) > (DAY // step) // 2:
        return {"state": "NOT_AVAILABLE", "note": "the stored daily bars are behind the intraday bars (a closed day is missing) — ADR and 'today' would be wrong, so nothing is shown"}
    today = [b for b in intraday if b["t"] >= start]
    if not today:
        return {"state": "NOT_AVAILABLE", "note": "no closed intraday bar yet in the running day"}
    return {"state": "OK", "start": start, "bars": today}


def evaluate(prior_daily: list[dict], day_bars: list[dict], snap_levels: dict | None = None) -> dict:
    """The daily forecast as of the LAST bar of `day_bars` (closed intraday bars of one broker day),
    from the completed daily bars before that day. Pure: nothing else is read."""
    adr = _mean_range(prior_daily[-ADR_LEN:])
    prev = prior_daily[-1]
    hi, lo, last = max(b["h"] for b in day_bars), min(b["l"] for b in day_bars), day_bars[-1]["c"]
    if not adr or adr <= 0:
        return {"state": "NOT_AVAILABLE", "note": "ADR is zero — no forecast"}
    top_raw, bot_raw = lo + adr, hi - adr
    sn = snap_levels or {}
    tol = (sn.get("atr") or 0) * MAGNET_ATR

    def snap(raw, a, a_name, b, b_name):
        da = abs(a - raw) if a is not None else None
        db = abs(b - raw) if b is not None else None
        if tol and da is not None and da <= tol and (db is None or da <= db):
            return a, a_name
        if tol and db is not None and db <= tol:
            return b, b_name
        return raw, None

    top_s, top_to = snap(top_raw, sn.get("res"), "4h swing high", prev["h"], "previous day's high")
    bot_s, bot_to = snap(bot_raw, sn.get("sup"), "4h swing low", prev["l"], "previous day's low")
    top, bottom = max(top_s, hi), min(bot_s, lo)
    top_done, bot_done = hi >= top_raw, lo <= bot_raw
    used = (hi - lo) / adr * 100.0
    move = (last - prev["c"]) / adr * 100.0
    if top_done and bot_done:
        status = "BOTH SIDES DONE: range > ADR, expansion day"
    elif top_done:
        status = "TOP IN (ADR FULL): fade rallies, no chase up"
    elif bot_done:
        status = "BOTTOM IN (ADR FULL): fade dips, no chase down"
    elif used >= NEAR_PCT:
        status = f"NEAR FULL ADR {used:.0f}%: extremes likely in"
    else:
        status = f"ADR {used:.0f}% used: room left on both sides"
    done_by = None
    if top_done:
        h = l = None
        for b in day_bars:
            nh, nl = h is None or b["h"] > h, l is None or b["l"] < l
            h, l = (b["h"] if h is None else max(h, b["h"])), (b["l"] if l is None else min(l, b["l"]))
            if h - l >= adr:
                done_by = {"side": "TOP" if (nh and not nl) or (nh and nl and b["c"] >= b["o"]) else "BOTTOM", "bar": b["t"]}
                break
    return {"state": "OK", "completed_by": done_by, "adr": adr, "adr_days": min(len(prior_daily), ADR_LEN), "day_open": day_bars[0]["o"], "day_high": hi, "day_low": lo, "last": last,
            "prev_close": prev["c"], "prev_high": prev["h"], "prev_low": prev["l"], "top_raw": top_raw, "bottom_raw": bot_raw, "top": top, "bottom": bottom,
            "top_snapped_to": top_to if top_s != top_raw and top == top_s else None, "bottom_snapped_to": bot_to if bot_s != bot_raw and bottom == bot_s else None,
            "top_done": top_done, "bottom_done": bot_done, "used_pct": used, "move_pct": move, "status": status,
            "room_up": max(top - last, 0.0), "room_down": max(last - bottom, 0.0)}


def htf_snap(h4: list[dict], before: int | None = None) -> dict:
    """Newest confirmed 4h swing high / low and ATR(14, 4h), known by time `before` (no lookahead)."""
    if before is not None:
        h4 = [b for b in h4 if b["t"] + 4 * 3600 <= before]
    if len(h4) < smc.MIN_BARS:
        return {}
    piv = smc.pivots(h4, smc.L_EXTERNAL)
    atr = next((x for x in reversed(smc.atr_series(h4)) if x), None)
    res = next((p["price"] for p in reversed(piv) if p["kind"] == "H"), None)
    sup = next((p["price"] for p in reversed(piv) if p["kind"] == "L"), None)
    return {"res": res, "sup": sup, "atr": atr}


def fade_scenarios(symbol: str, prior_daily: list[dict], day_bars: list[dict], day_start: int, step: int, day_end: int | None = None) -> list[dict]:
    """The fade scenario of ONE broker day (at most one): made at the first closed bar on which the day's
    range reached ADR. Walks the day's bars forward, so it depends only on bars up to its own."""
    adr = _mean_range(prior_daily[-ADR_LEN:])
    if not adr or adr <= 0 or len(prior_daily) < ADR_LEN:
        return []
    end = day_end or day_start + DAY
    hi = lo = None
    for b in day_bars:
        new_high, new_low = hi is None or b["h"] > hi, lo is None or b["l"] < lo
        hi, lo = (b["h"] if hi is None else max(hi, b["h"])), (b["l"] if lo is None else min(lo, b["l"]))
        if hi - lo < adr:
            continue
        # the day's range has just reached ADR. Pine's "top done" and "bottom done" are the same condition
        # (high >= low + ADR is low <= high - ADR), so the side that is "in" is the extreme THIS bar made.
        side = "TOP" if (new_high and not new_low) or (new_high and new_low and b["c"] >= b["o"]) else "BOTTOM"
        left = (end - (b["t"] + step)) // step
        if left < FADE_MIN_BARS:
            return []
        c = b["c"]
        d = -1 if side == "TOP" else 1
        extreme = hi if side == "TOP" else lo
        stop = extreme - d * FADE_STOP_ADR * adr
        f = {"direction": "SHORT" if d == -1 else "LONG", "pattern": f"ADR FULL — {side} IN (fade)", "status": "confirmed", "entry_mode": "at_close",
             "entry_low": c, "entry_high": c, "sl": stop, "invalidation": stop, "tp1": c + d * FADE_TP1_ADR * adr, "tp2": c + d * FADE_TP2_ADR * adr,
             "horizon_bars": int(left), "made_bar": b["t"], "made_price": c,
             "detail": {"adr": round(adr, 8), "day_start": day_start, "day_high": hi, "day_low": lo, "side": side, "rule": "terminal's own fade rule — Pine names no stop or target"}}
        return [f] if c != stop else []
    return []


def days_in(daily: list[dict], intraday: list[dict], step: int) -> list[tuple[int, int, list[dict], list[dict]]]:
    """Every broker day the intraday series covers COMPLETELY FROM ITS START: (start, end, prior daily bars, that day's bars).
    Completed days are bounded by their own stored daily bar; the running day by split_day()."""
    out = []
    first = intraday[0]["t"] if intraday else 0
    for i, d in enumerate(daily):
        if i < ADR_LEN or d["t"] < first:
            continue
        end = daily[i + 1]["t"] if i + 1 < len(daily) else d["t"] + DAY
        end = min(end, d["t"] + DAY)
        bars = [b for b in intraday if d["t"] <= b["t"] < end]
        if bars and bars[0]["t"] - d["t"] <= 2 * 3600:        # the day's first bars are in the series (not cut off on the left)
            out.append((d["t"], end, daily[:i], bars))
    run = split_day(daily, intraday, step)
    if run["state"] == "OK" and run["bars"][0]["t"] - run["start"] <= 2 * 3600 and run["start"] >= first:
        out.append((run["start"], run["start"] + DAY, daily, run["bars"]))
    return out


def daily_forecast(symbol: str, daily: list[dict], intraday: list[dict], intraday_tf: str, h4: list[dict] | None = None, history_days: int = 5) -> dict:
    """The full display payload for one instrument."""
    step = smc.TF_MIN[intraday_tf] * 60
    base = {"symbol": symbol, "kind": "TERMINAL STUDY — not SignalMesh engine output", "method_version": DAILY_VERSION, "methodology": METHODOLOGY,
            "level_label": LEVEL_LABEL, "levels_are": "CALCULATED", "horizons_are": "ESTIMATES", "confidence": "UNKNOWN",
            "confidence_rule": METHODOLOGY["confidence"], "intraday_tf": intraday_tf, "calculated_at": datetime.now(timezone.utc).isoformat(),
            "scenarios": [], "history": [], "outlooks": outlooks(daily, None)}
    run = split_day(daily, intraday, step)
    if run["state"] != "OK":
        return {**base, **run}
    start, today = run["start"], run["bars"]
    sn = htf_snap(h4 or [], before=today[-1]["t"] + step)
    ev = evaluate(daily, today, sn)
    if ev["state"] != "OK":
        return {**base, **ev}
    through = today[-1]["t"]
    scen = []
    for f in fade_scenarios(symbol, daily, today, start, step):
        risk = abs(f["made_price"] - f["sl"])
        scen.append({"module": "daily-forecast", "side": "bearish" if f["direction"] == "SHORT" else "bullish", "direction": f["direction"], "pattern": f["pattern"],
                     "entry": f["made_price"], "sl": f["sl"], "tp1": f["tp1"], "tp2": f["tp2"], "invalidation": f["invalidation"],
                     "rr1": round(abs(f["tp1"] - f["made_price"]) / risk, 2) if risk else None, "rr2": round(abs(f["tp2"] - f["made_price"]) / risk, 2) if risk else None,
                     "horizon": f"until the broker day ends ({_iso(start + DAY)}) — ESTIMATE", "horizon_bars": f["horizon_bars"], "made_bar": f["made_bar"], "made_bar_utc": _iso(f["made_bar"]),
                     "status": "confirmed", "confidence": "UNKNOWN", "level_label": LEVEL_LABEL, "rule": "terminal's own fade rule (Pine names no stop or target)"})
    hist = []
    for i in range(max(ADR_LEN, len(daily) - history_days), len(daily)):
        d, adr = daily[i], _mean_range(daily[i - ADR_LEN:i])
        if not adr:
            continue
        hist.append({"day_start": d["t"], "day_end": min(daily[i + 1]["t"] if i + 1 < len(daily) else d["t"] + DAY, d["t"] + DAY), "adr": adr, "high": d["h"], "low": d["l"],
                     "top": max(d["l"] + adr, d["h"]), "bottom": min(d["h"] - adr, d["l"]), "top_done": d["h"] >= d["l"] + adr, "bottom_done": d["l"] <= d["h"] - adr,
                     "used_pct": (d["h"] - d["l"]) / adr * 100.0})
    return {**base, **ev, "day_start": start, "day_start_utc": _iso(start), "day_end_utc": _iso(start + DAY), "through_bar": through, "through_close": through + step,
            "through_close_utc": _iso(through + step), "bars_today": len(today), "snap": {"used": bool(sn), **{k: sn.get(k) for k in ("res", "sup", "atr")}},
            "scenarios": scen, "history": hist, "outlooks": outlooks(daily, {"high": ev["day_high"], "low": ev["day_low"], "last": ev["last"], "start": start}),
            "source": f"SignalMesh closed 1d bars (ADR, previous day) + closed {intraday_tf} bars (today){' + closed 4h bars (snap)' if sn else ''}"}


# ------------------------------------------------------------------ longer outlooks (terminal's extension of the same formula)
def _period_key(t: int, kind: str) -> tuple:
    d = datetime.fromtimestamp(t, timezone.utc) + timedelta(hours=3)        # a bar opening 21:00-22:00 UTC belongs to the next calendar day
    if kind == "week":
        y, w, _ = d.isocalendar()
        return (y, w)
    if kind == "month":
        return (d.year, d.month)
    if kind == "quarter":
        return (d.year, (d.month - 1) // 3)
    return (d.year, (d.month - 1) // 6)


def outlooks(daily: list[dict], today: dict | None) -> dict:
    """Weekly / monthly / 3-month / 6-month ranges by the daily formula on completed periods built from
    stored daily bars. UNKNOWN wherever fewer than ADR_LEN completed periods exist."""
    out = {}
    for name, kind in (("weekly", "week"), ("monthly", "month"), ("3-month", "quarter"), ("6-month", "half")):
        groups: dict[tuple, dict] = {}
        for b in daily:
            g = groups.setdefault(_period_key(b["t"], kind), {"h": b["h"], "l": b["l"], "n": 0})
            g["h"], g["l"], g["n"] = max(g["h"], b["h"]), min(g["l"], b["l"]), g["n"] + 1
        keys = sorted(groups)
        cur_key = _period_key(today["start"], kind) if today else (keys[-1] if keys else None)
        done = [groups[k] for k in keys if k != cur_key]
        if keys and done and groups[keys[0]] is done[0]:
            done = done[1:]                                                  # the oldest period is probably cut off on the left
        if len(done) < ADR_LEN or not today:
            out[name] = {"state": "UNKNOWN", "note": f"{len(done)} completed {kind} periods in the stored daily history — {ADR_LEN} are needed" if today else "today's data is not available"}
            continue
        avg = sum(g["h"] - g["l"] for g in done[-ADR_LEN:]) / ADR_LEN
        cur = groups.get(cur_key)
        hi = max(cur["h"], today["high"]) if cur else today["high"]
        lo = min(cur["l"], today["low"]) if cur else today["low"]
        out[name] = {"state": "OK", "avg_range": avg, "periods": ADR_LEN, "high": hi, "low": lo, "top": max(lo + avg, hi), "bottom": min(hi - avg, lo),
                     "top_done": hi >= lo + avg, "bottom_done": lo <= hi - avg, "used_pct": (hi - lo) / avg * 100.0 if avg else None,
                     "levels_are": "CALCULATED", "horizon_is": "ESTIMATE", "confidence": "UNKNOWN"}
    return out


# ------------------------------------------------------------------ rotation ladder
def sessions_at(t: int) -> dict:
    hm = datetime.fromtimestamp(t, NY)
    m = hm.hour * 60 + hm.minute
    return {"asia": m >= 19 * 60 or m < 3 * 60, "london": 3 * 60 <= m < 8 * 60, "ny": 8 * 60 <= m < 17 * 60}


def session_ok(symbol: str, ses: dict) -> bool:
    cat = category(symbol)
    if cat == "crypto":
        return True
    if cat in ("indices", "stocks"):
        return ses["ny"]
    if cat == "forex" and "JPY" in symbol.upper():
        return ses["asia"] or ses["ny"]
    return ses["london"] or ses["ny"]


def rot_state(used: float, move: float) -> tuple[str, str]:
    if used >= FULL_PCT:
        return "DONE - sleep", "no chase: fade / trap only"
    if used >= NEAR_PCT:
        return "NEAR FULL", "late: small targets"
    if used >= AWAKE_PCT:
        return ("MOVING UP", "buy pullbacks") if move >= 0 else ("MOVING DOWN", "sell rallies")
    return "FRESH (quiet)", "wait break / session open"


def rot_score(used: float, move: float, ses_ok: bool) -> float:
    room = 0.0 if used >= FULL_PCT else 100.0 - used
    return 0.0 if room <= 0 else (room * 0.5 + min(abs(move), 60.0)) * (1.0 if ses_ok else 0.5)


def ranking(rows_in: list[dict], now: int, current: str = "") -> dict:
    """rows_in: [{symbol, forecast}] where forecast is evaluate()-shaped or a NOT_AVAILABLE state."""
    ses = sessions_at(now)
    rows = []
    for r in rows_in:
        f = r["forecast"]
        if f.get("state") != "OK":
            rows.append({"symbol": r["symbol"], "state": "NOT AVAILABLE", "action": "-", "note": f.get("note"), "score": None, "used_pct": None, "move_pct": None, "session_ok": None})
            continue
        ok = session_ok(r["symbol"], ses)
        st, act = rot_state(f["used_pct"], f["move_pct"])
        rows.append({"symbol": r["symbol"], "used_pct": round(f["used_pct"], 1), "move_pct": round(f["move_pct"], 1), "state": st, "action": act, "session_ok": ok,
                     "score": round(rot_score(f["used_pct"], f["move_pct"], ok), 1), "adr": f["adr"], "through_close_utc": r.get("through_close_utc")})
    ranked = sorted((r for r in rows if r["score"] is not None), key=lambda r: (-r["score"], r["symbol"]))
    for i, r in enumerate(ranked):
        r["rank"] = i + 1
    rest = sorted((r for r in rows if r["score"] is None), key=lambda r: r["symbol"])
    for r in rest:
        r["rank"] = None
    best = ranked[0] if ranked and ranked[0]["score"] > 0 else None
    me = next((r for r in ranked if r["symbol"] == current.upper()), None)
    if not best:
        go = "No asset shows clear room now: wait for the next session open"
    elif me and best["symbol"] == me["symbol"]:
        go = f"STAY on {me['symbol']}: most room is here ({me['used_pct']:.0f}% of ADR used)"
    elif me and me["used_pct"] >= FULL_PCT:
        go = f"{me['symbol']} move DONE ({me['used_pct']:.0f}% ADR): let it sleep -> GO TRADE {best['symbol']} ({best['used_pct']:.0f}% used, {best['state']}: {best['action']})"
    else:
        go = f"Most room: {best['symbol']} ({best['used_pct']:.0f}% of ADR used, {best['state']}: {best['action']})"
    return {"kind": "TERMINAL STUDY — not SignalMesh engine output", "method_version": ROTATION_VERSION, "methodology": {k: METHODOLOGY[k] for k in ("adr", "day", "today", "ladder", "sessions", "not_ported")},
            "sessions": ses, "rows": ranked + rest, "go_trade": go, "go_symbol": best["symbol"] if best else None,
            "note": "A ranking of ROOM LEFT in today's normal range. It does not predict where money will go, it is not a signal, and it is not recorded in the forecast journal.",
            "calculated_at": datetime.now(timezone.utc).isoformat()}


class DailyForecastModule:
    """Journal module: the fade scenario of every broker day the stored 15m bars cover from its start."""
    name = "daily-forecast"
    method_version = DAILY_VERSION
    timeframes = ("15m",)

    def forecasts(self, symbol: str, timeframe: str, bars: list[dict], get=None) -> list[dict]:
        daily = get(symbol, "1d") if get else []
        step = smc.TF_MIN[timeframe] * 60
        out = []
        for start, end, prior, day_bars in days_in(daily, bars, step):
            out.extend(fade_scenarios(symbol, prior, day_bars, start, step, end if end - start == DAY else start + DAY))
        return out
