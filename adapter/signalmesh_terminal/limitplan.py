"""LIMIT CHECKLIST (limit-checklist-v1) — Shyam's seven-step checklist for a PENDING LIMIT order, read on closed bars.

Asked for by Shyam on 2026-11-22: "show only, also this is not a trade signal". It is the terminal's own display-only study,
like chart-read: it reads SignalMesh's stored CLOSED daily and 4h bars for one instrument and says, step by step, whether
his checklist holds right now, with the levels the checklist itself produces. Every level is a HYPOTHETICAL ANALYSIS LEVEL.

    1 trend (daily)        price against the 50 / 100 / 200-day EMAs, and the last daily swing high and low
    2 bounce (4h)          how far price has come back against the trend, in percent
    3 entry zone           two or more DIFFERENT kinds of level overlapping; the limit goes in the middle of the zone
    4 stop                 beyond the furthest level of the zone plus a buffer; no other level may sit just past it
    5 targets              TP1 just before the nearest level in the trend's direction, TP2 before the next; TP2 must give 1:2
    6 size                 the risk per unit; lots need the broker's contract size, which the terminal does not have
    7 cancel               a 4h close beyond the stop before the fill, or no fill within 24 to 48 hours

WHAT IT IS NOT. Not a signal, not SignalMesh engine output, not recorded in the forecast journal, never an input to a
decision, and it places no order. Nothing here was tested against outcomes: it is a checklist made visible, not an edge.

LAWS. Closed bars only. A step that cannot be measured is NOT AVAILABLE, never assumed to pass. A daily or 4h series
that carries two bars in one slot is refused (a moving average over a doubled series is a wrong number that looks right).
Every constant below is one of Shyam's own numbers or is named as the terminal's choice in METHODOLOGY.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

from .chartread import ema, swing_labels
from .smc import atr_series

VERSION = "limit-checklist-v1"
MAS = (50, 100, 200)            # step 1: "the 50, 100 and 200-day MAs" — exponential, the same averages the chart draws
MIN_DAILY = 200                 # the 200-day average needs 200 closed daily bars
MIN_H4 = 60
BOUNCE_LOOKBACK = 60            # 4h bars (about ten trading days) searched for the extreme the bounce is measured from
BOUNCE_MIN, BOUNCE_MAX = 3.0, 8.0     # step 2: "usually 3–8%"
ZONE_ATR = 1.0                  # step 3: levels "overlap" when they lie within this many 4h ATR of each other
SL_BUFFER = 0.004               # step 4: "a buffer of about 0.3–0.5% for wicks" — the middle, 0.4%
SL_CLEAR = 0.005                # step 4: no level may sit within 0.5% past the stop ("62,000 sat under the MA at 62,102")
TP_OFFSET_ATR = 0.1             # step 5: "just above it" — a tenth of a 4h ATR before the level
TP2_GAP_ATR = 1.0               # step 5: the "next major" level is at least one 4h ATR beyond the first
RR2_MIN = 2.0                   # step 5: "skip the trade if TP2 gives less than 1:2"
RISK_PCT = 1.0                  # step 6: "risk is 1% of the account at most"
EXPIRY_H = (24, 48)             # step 7

METHODOLOGY = {
    "what_it_is": "Shyam's seven-step checklist for a pending limit order, read on SignalMesh's stored CLOSED daily and 4h bars. Display only: not a signal, "
                  "not recorded, not SignalMesh engine output, no order. Not tested against outcomes",
    "step_1_trend": "daily close against the 50, 100 and 200-day exponential averages, and the newest confirmed daily swing high and swing low "
                    "(LH and LL = bearish, HH and HL = bullish). Below all three with LH/LL: only sells. Above all three with HH/HL: only buys. Anything else: MIXED, no trade",
    "step_2_bounce": f"for a sell: the rise from the lowest low of the last {BOUNCE_LOOKBACK} closed 4h bars to the newest 4h close, in percent (mirror for a buy). "
                     f"The checklist's own range is {BOUNCE_MIN:g}–{BOUNCE_MAX:g}%: it was written for crypto-sized moves and a currency pair may never reach it",
    "step_3_zone": f"levels on the entry side of price: the newest 4h and daily swing high, a broken swing low now above price, the 50 and 100-day EMA, the next round number, "
                   f"the daily pivots R1 and R2 (mirror for a buy). A zone = the nearest group of two or more DIFFERENT kinds within {ZONE_ATR:g} × the 4h ATR. "
                   "The limit is the middle of the zone. It must be at least 1R from price",
    "step_4_stop": f"beyond the furthest level of the zone plus {SL_BUFFER * 100:g}% (the checklist says 0.3–0.5%). If any known level sits within {SL_CLEAR * 100:g}% past the stop, "
                   "the stop is moved beyond that level too, and the row says which",
    "step_5_targets": f"TP1 = {TP_OFFSET_ATR:g} × 4h ATR before the nearest level in the trend's direction (swing, prior day extreme, round number, pivot S1 / S2); "
                      f"TP2 = the same before the next level at least {TP2_GAP_ATR:g} × 4h ATR further. TP2 must give at least 1:{RR2_MIN:g}",
    "step_6_size": f"risk at most {RISK_PCT:g}% of the account. Units = (account × {RISK_PCT:g}%) ÷ the distance from entry to stop. Lots are NOT AVAILABLE: "
                   "the terminal does not know the broker's contract size for the instrument",
    "step_7_cancel": f"a 4h candle closes beyond the stop before the order fills, or the order is unfilled after {EXPIRY_H[0]}–{EXPIRY_H[1]} hours. "
                     "The terminal places and tracks no order, so these are printed as the rules to apply by hand",
    "round_number": "the next multiple of one tenth of the price's power of ten (60,143 → 61,000; 3,537 → 3,600; 1.0965 → 1.1000)",
    "pivots": "classic daily pivots from the newest closed daily bar: P = (H + L + C) ÷ 3, R1 = 2P − L, R2 = P + (H − L), S1 = 2P − H, S2 = P − (H − L)",
    "refused": "fewer than 200 closed daily bars or 60 closed 4h bars; a daily or 4h series with two bars in one slot",
}


def _iso(t) -> str | None:
    return None if t is None else datetime.fromtimestamp(int(t), timezone.utc).isoformat()


def series_fault(b: list[dict], step: int) -> str:
    """Two bars in one slot: consecutive bars closer than half a bar apart. (A broker day that shifts by an hour at a
    clock change is 23 or 25 hours long and is not a fault.)"""
    n = sum(1 for i in range(1, len(b)) if b[i]["t"] - b[i - 1]["t"] < step / 2)
    return f"{n} place(s) where two bars sit in one slot" if n else ""


def round_step(price: float) -> float:
    return 10.0 ** (math.floor(math.log10(abs(price))) - 1) if price else 0.0


def _step(n: int, name: str, status: str, text: str, **extra) -> dict:
    return {"n": n, "name": name, "status": status, "text": text, **extra}


def _empty(symbol: str, state: str, note: str, d_n: int, h_n: int, source: str) -> dict:
    return {"symbol": symbol, "state": state, "note": note, "kind": "TERMINAL STUDY — display only, not a signal", "method_version": VERSION,
            "methodology": METHODOLOGY, "recorded": False, "source": source, "daily_bars": d_n, "h4_bars": h_n, "side": None, "verdict": "NOT AVAILABLE",
            "verdict_why": note, "steps": [], "plan": None, "averages": None, "calculated_at": datetime.now(timezone.utc).isoformat(),
            "through_daily_utc": None, "through_h4_utc": None, "level_label": "HYPOTHETICAL ANALYSIS LEVEL"}


def analyse(symbol: str, daily: list[dict], h4: list[dict], source: str = "") -> dict:
    """The seven steps for one instrument, from closed daily and 4h bars only. Pure: the same bars give the same answer."""
    if len(daily) < MIN_DAILY:
        return _empty(symbol, "NOT_AVAILABLE", f"only {len(daily)} closed daily bars are stored — {MIN_DAILY} are needed for the 200-day average", len(daily), len(h4), source)
    if len(h4) < MIN_H4:
        return _empty(symbol, "NOT_AVAILABLE", f"only {len(h4)} closed 4h bars are stored — {MIN_H4} are needed", len(daily), len(h4), source)
    for name, b, step in (("daily", daily, 86400), ("4h", h4, 14400)):
        f = series_fault(b, step)
        if f:
            return _empty(symbol, "SERIES_FAULT", f"the {name} series is not one clean series: {f}. An average over it would be wrong, so nothing is read from it", len(daily), len(h4), source)

    out = _empty(symbol, "OK", "", len(daily), len(h4), source)
    out["through_daily_utc"], out["through_h4_utc"] = _iso(daily[-1]["t"] + 86400), _iso(h4[-1]["t"] + 14400)
    closes = [k["c"] for k in daily]
    close_d = closes[-1]
    e = {n: ema(closes, n)[-1] for n in MAS}
    out["averages"] = {f"ema{n}": e[n] for n in MAS} | {"daily_close": close_d}
    dl = swing_labels(daily, 86400)
    last_h = next((x for x in reversed(dl) if x["side"] == "high"), None)
    last_l = next((x for x in reversed(dl) if x["side"] == "low"), None)
    struct = f"{last_h['label'] if last_h else '—'} / {last_l['label'] if last_l else '—'}"
    below, above = all(close_d < e[n] for n in MAS), all(close_d > e[n] for n in MAS)
    ma_txt = "daily close " + f"{close_d:.6g} against EMA50 {e[50]:.6g}, EMA100 {e[100]:.6g}, EMA200 {e[200]:.6g}"
    steps = out["steps"]
    if below and last_h and last_l and last_h["label"] == "LH" and last_l["label"] == "LL":
        side = "SELL"
    elif above and last_h and last_l and last_h["label"] == "HH" and last_l["label"] == "HL":
        side = "BUY"
    else:
        side = None
    if side is None:
        where = "below all three" if below else "above all three" if above else "between the averages"
        steps.append(_step(1, "Trend (daily)", "MIXED", f"{ma_txt}: {where}; last daily swings {struct}. A mixed picture means no trade"))
        for n, name in ((2, "Bounce (4h)"), (3, "Entry zone"), (4, "Stop"), (5, "Targets"), (6, "Size"), (7, "Cancel conditions")):
            steps.append(_step(n, name, "NOT APPLICABLE", "no side to read: step 1 is mixed"))
        out.update(verdict="NO TRADE", verdict_why="step 1: the daily trend is mixed, and the checklist takes no trade on a mixed picture")
        return out

    out["side"] = side
    s = 1 if side == "SELL" else -1                 # +1: the entry side is ABOVE price (a sell limit); −1: below (a buy limit)
    steps.append(_step(1, "Trend (daily)", "PASS", f"{'BEARISH' if s > 0 else 'BULLISH'} — {ma_txt}: {'below' if s > 0 else 'above'} all three; last daily swings {struct}. "
                                                    f"Only {'sells' if s > 0 else 'buys'}"))
    price = h4[-1]["c"]
    atr = atr_series(h4)[-1]
    fails: list[str] = []

    # ---- 2. the bounce against the trend
    win = h4[-BOUNCE_LOOKBACK:]
    ext = min(win, key=lambda k: k["l"]) if s > 0 else max(win, key=lambda k: k["h"])
    ref = ext["l"] if s > 0 else ext["h"]
    bounce = s * (price - ref) / ref * 100
    b_ok = BOUNCE_MIN <= bounce <= BOUNCE_MAX
    word = "IN RANGE" if b_ok else "TOO SMALL" if bounce < BOUNCE_MIN else "LARGER THAN USUAL"
    steps.append(_step(2, "Bounce (4h)", "PASS" if b_ok else "WAIT",
                       f"{word} — price is {bounce:.1f}% {'above the low' if s > 0 else 'below the high'} {ref:.6g} of the {_iso(ext['t'])[:16].replace('T', ' ')} UTC 4h bar; "
                       f"the checklist waits for {BOUNCE_MIN:g}–{BOUNCE_MAX:g}%", bounce_pct=round(bounce, 2), from_price=ref, from_bar_utc=_iso(ext["t"])))
    if not b_ok:
        fails.append(f"step 2: the bounce is {bounce:.1f}%, outside {BOUNCE_MIN:g}–{BOUNCE_MAX:g}%")

    # ---- every level the checklist names, with its kind
    hl = swing_labels(h4, 14400)
    piv_bar = daily[-1]
    pp = (piv_bar["h"] + piv_bar["l"] + piv_bar["c"]) / 3
    rng = piv_bar["h"] - piv_bar["l"]
    rs = round_step(price)
    levels: list[dict] = []

    def add(kind, name, value, bar_t=None):
        if value is not None and value > 0:
            levels.append({"kind": kind, "name": name, "value": float(value), "bar_utc": _iso(bar_t)})

    for tf, labs in (("4h", hl), ("daily", dl)):
        for side_name, kind in (("high", "swing high"), ("low", "swing low")):
            for x in [y for y in labs if y["side"] == side_name][-3:]:
                add(kind, f"{tf} swing {side_name}", x["price"], x["time"])
    add("moving average", "50-day EMA", e[50]), add("moving average", "100-day EMA", e[100]), add("moving average (200)", "200-day EMA", e[200])
    if rs:
        add("round number", "round number above", math.floor(price / rs + 1e-9) * rs + rs)
        add("round number", "round number below", math.ceil(price / rs - 1e-9) * rs - rs)
    add("pivot", "pivot R1", 2 * pp - piv_bar["l"], piv_bar["t"]), add("pivot", "pivot R2", pp + rng, piv_bar["t"])
    add("pivot", "pivot S1", 2 * pp - piv_bar["h"], piv_bar["t"]), add("pivot", "pivot S2", pp - rng, piv_bar["t"])
    add("prior day extreme", "prior day high", piv_bar["h"], piv_bar["t"]), add("prior day extreme", "prior day low", piv_bar["l"], piv_bar["t"])

    def entry_kind(lv):
        """What a level on the ENTRY side is called by the checklist (for a sell: resistance above price)."""
        with_side, against = ("swing high", "swing low") if s > 0 else ("swing low", "swing high")
        if lv["kind"] == with_side:
            return "last swing " + ("high" if s > 0 else "low")
        if lv["kind"] == against:
            return "broken " + ("support, now resistance" if s > 0 else "resistance, now support")
        if lv["kind"] == "moving average":
            return "moving average (50 or 100-day)"
        if lv["kind"] == "round number":
            return "round number"
        if lv["kind"] == "pivot" and lv["name"] in (("pivot R1", "pivot R2") if s > 0 else ("pivot S1", "pivot S2")):
            return "pivot"
        return None

    cands = sorted(({**lv, "zone_kind": entry_kind(lv)} for lv in levels if s * (lv["value"] - price) > 0 and entry_kind(lv)), key=lambda lv: s * (lv["value"] - price))
    plan: dict = {"price": price, "price_basis": f"newest closed 4h close ({_iso(h4[-1]['t'] + 14400)[:16].replace('T', ' ')} UTC)", "atr_4h": atr, "side": side,
                  "order_type": f"{side} LIMIT", "level_label": "HYPOTHETICAL ANALYSIS LEVEL"}
    out["plan"] = plan

    # ---- 3. the entry zone: the nearest group of two or more different kinds within ZONE_ATR × ATR
    zone = None
    if atr:
        for i, first in enumerate(cands):
            grp = [c for c in cands[i:] if s * (c["value"] - first["value"]) <= ZONE_ATR * atr]
            if len({c["zone_kind"] for c in grp}) >= 2:
                zone = grp
                break
    if zone is None:
        steps.append(_step(3, "Entry zone", "WAIT", (f"no two different kinds of level overlap within {ZONE_ATR:g} × the 4h ATR ({atr:.6g}) on the "
                                                     f"{'resistance' if s > 0 else 'support'} side of {price:.6g}" if atr else "the 4h ATR is not available"),
                           candidates=[{k: c[k] for k in ("zone_kind", "name", "value", "bar_utc")} for c in cands[:8]]))
        for n, name in ((4, "Stop"), (5, "Targets"), (6, "Size")):
            steps.append(_step(n, name, "NOT APPLICABLE", "no entry zone to measure from"))
        steps.append(_step(7, "Cancel conditions", "NOT APPLICABLE", "no order level to cancel"))
        out.update(verdict="WAIT", verdict_why="; ".join(fails + ["step 3: no entry zone — two different kinds of level do not overlap"]))
        return out
    near, far = zone[0]["value"], zone[-1]["value"]
    entry = (near + far) / 2
    plan.update(zone_low=min(near, far), zone_high=max(near, far), zone_levels=[{k: c[k] for k in ("zone_kind", "name", "value", "bar_utc")} for c in zone], entry=entry)

    # ---- 4. the stop: beyond the furthest level of the zone, plus the buffer; no level may sit just past it
    edge, moved = far, []
    for _ in range(6):
        sl = edge * (1 + s * SL_BUFFER)
        just_past = [lv for lv in levels if 0 < s * (lv["value"] - sl) <= sl * SL_CLEAR]
        if not just_past:
            break
        edge = max(just_past, key=lambda lv: s * lv["value"])["value"]
        moved += [f"{lv['name']} {lv['value']:.6g}" for lv in just_past]
    still = [lv for lv in levels if 0 < s * (lv["value"] - sl) <= sl * SL_CLEAR]
    risk = s * (sl - entry)
    away = s * (entry - price)
    plan.update(sl=sl, risk_per_unit=risk, entry_distance_r=round(away / risk, 2) if risk > 0 else None)
    sl_txt = (f"{sl:.6g} = {SL_BUFFER * 100:g}% beyond {edge:.6g}" + (f"; moved beyond {', '.join(dict.fromkeys(moved))}, which sat just past the first stop" if moved else "")
              + "; no known level sits within " + f"{SL_CLEAR * 100:g}% past it")
    if still:
        steps_4 = _step(4, "Stop", "FAIL", f"{sl:.6g} — a level still sits just past it: " + ", ".join(f"{lv['name']} {lv['value']:.6g}" for lv in still))
        fails.append("step 4: a level sits just past the stop")
    else:
        steps_4 = _step(4, "Stop", "PASS", sl_txt)
    z_ok = risk > 0 and away >= risk
    steps.append(_step(3, "Entry zone", "PASS" if z_ok else "WAIT",
                       f"zone {min(near, far):.6g} – {max(near, far):.6g}: " + " + ".join(f"{c['zone_kind']} ({c['name']} {c['value']:.6g})" for c in zone)
                       + f". Limit in the middle: {entry:.6g}, {away / risk:.1f}R from price" + ("" if z_ok else " — closer than 1R: noise would fill it")))
    if not z_ok:
        fails.append(f"step 3: the limit is only {away / risk:.1f}R from price")
    steps.append(steps_4)

    # ---- 5. the targets: just before the nearest level in the trend's direction, then the next one
    tk = ("swing low", "prior day extreme", "round number", "pivot") if s > 0 else ("swing high", "prior day extreme", "round number", "pivot")
    tnames = ("prior day low", "round number below", "pivot S1", "pivot S2") if s > 0 else ("prior day high", "round number above", "pivot R1", "pivot R2")
    targets = sorted((lv for lv in levels if s * (price - lv["value"]) > 0 and lv["kind"] in tk and (lv["kind"] in ("swing low", "swing high") or lv["name"] in tnames)),
                     key=lambda lv: s * (price - lv["value"]))
    off = TP_OFFSET_ATR * atr
    if not targets:
        steps.append(_step(5, "Targets", "NOT AVAILABLE", f"no measured level on the {'support' if s > 0 else 'resistance'} side of price in the bars read"))
        fails.append("step 5: no target level")
    else:
        t1 = targets[0]
        t2 = next((t for t in targets[1:] if s * (t1["value"] - t["value"]) >= TP2_GAP_ATR * atr), None)
        tp1 = t1["value"] + s * off
        plan.update(tp1=tp1, tp1_level={k: t1[k] for k in ("name", "value", "bar_utc")}, rr1=round(s * (entry - tp1) / risk, 2) if risk > 0 else None)
        txt = f"TP1 {tp1:.6g}, just {'above' if s > 0 else 'below'} {t1['name']} {t1['value']:.6g} (1:{plan['rr1']}) — close half there and move the stop to breakeven"
        if t2 is None:
            steps.append(_step(5, "Targets", "NOT AVAILABLE", txt + f". No further level at least {TP2_GAP_ATR:g} × 4h ATR beyond it for TP2"))
            fails.append("step 5: no second target")
        else:
            tp2 = t2["value"] + s * off
            rr2 = round(s * (entry - tp2) / risk, 2) if risk > 0 else None
            plan.update(tp2=tp2, tp2_level={k: t2[k] for k in ("name", "value", "bar_utc")}, rr2=rr2)
            ok5 = rr2 is not None and rr2 >= RR2_MIN
            steps.append(_step(5, "Targets", "PASS" if ok5 else "FAIL",
                               txt + f". TP2 {tp2:.6g}, just {'above' if s > 0 else 'below'} {t2['name']} {t2['value']:.6g} (1:{rr2})" + ("" if ok5 else f" — under 1:{RR2_MIN:g}: skip the trade")))
            if not ok5:
                fails.append(f"step 5: TP2 gives 1:{rr2}, under 1:{RR2_MIN:g}")

    # ---- 6 and 7: rules to apply by hand
    steps.append(_step(6, "Size", "BY HAND", f"risk at most {RISK_PCT:g}% of the account. Risk per unit = {risk:.6g} (entry to stop). Units = (account × {RISK_PCT:g}%) ÷ {risk:.6g}. "
                                             "Lots: NOT AVAILABLE — the terminal does not know the broker's contract size"))
    steps.append(_step(7, "Cancel conditions", "BY HAND", f"cancel if a 4h candle closes {'above' if s > 0 else 'below'} {sl:.6g} before the order fills, or if it is unfilled after "
                                                          f"{EXPIRY_H[0]}–{EXPIRY_H[1]} hours. The terminal places and tracks no order"))
    if fails:
        out.update(verdict="WAIT", verdict_why="; ".join(fails))
    else:
        out.update(verdict="CHECKLIST HOLDS", verdict_why=f"every measured step holds for a hypothetical {side} LIMIT at {entry:.6g}. Not a signal: nothing here was tested against outcomes")
    return out
