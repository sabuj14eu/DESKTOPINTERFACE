"""CHART READ — one table and one set of chart labels that gather what the terminal already knows about a chart.

Asked for by Shyam (2026-11-19): what his Metal Hunter indicator shows him on TradingView — the swing labels on the
candles and the information table beside them — on the terminal's own chart, behind one on/off switch. It is NOT a new
signal: it generates no BUY / SELL, records nothing, feeds nothing, and places no order. It is a READ of closed bars.

WHERE EACH ROW COMES FROM (the `source` of every row says so on screen)
  * structure, trend, support / resistance, FVG, order blocks, liquidity, inducement  -> smc-v1, the terminal's existing
    Smart Money study, read on each timeframe. Nothing is recalculated here.
  * day forecast, ADR                                                                -> daily-forecast-v1, existing.
  * engine bias / regime                                                             -> SignalMesh's own snapshot, verbatim.
  * newest Pine signal                                                               -> the signal SignalMesh received, verbatim.
  * momentum (RSI, MACD), volatility, volume, price zone, swing labels, candle patterns, the condition count
                                                                                     -> chart-read-v1, calculated here.

RULES (the same as every terminal study)
  * CLOSED CANDLES ONLY. A swing label is known L bars after its bar; a candle pattern is known when its own bar closes.
  * NOTHING IS RESTATED. A label, once reported, is reported identically by every later analysis (tests/test_chartread.py
    compares every prefix, on series with and without daily breaks).
  * A row the data cannot support reads NOT AVAILABLE with the reason. TradingView's strategy-tester numbers (trades, win
    rate, average R) do not exist here and are not imitated.
  * The terminal's values will not always equal TradingView's: Pine runs on TradingView's bars and day; this reads
    SignalMesh's stored broker bars.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .smc import pivots
from .studies import TF_SEC, atr_rma

VERSION = "chart-read-v1"
SWING_L = 5                     # the same strength as smc-v1's external swings
PATTERN_LOOKBACK = 10           # a rejection must be at the extreme of this many bars
PATTERN_RECENT = 8              # a candle pattern counts for the condition table for this many closed bars
REJ_WICK_X_BODY = 2.0           # rejection: the wick is at least this many times the body
REJ_CLOSE_FRAC = 0.4            # ... and the close is within this fraction of the range from the far end
REJ_MIN_ATR = 0.6               # ... and the bar's range is at least this many ATR
ENG_MIN_ATR = 0.5               # engulfing: the engulfing body is at least this many ATR
RSI_N, EMA_FAST, EMA_SLOW = 14, 20, 50
MACD = (12, 26, 9)
VOL_N = 20
# what a condition is worth: structure and rejection outweigh a moving-average relation (Shyam, 2026-11-19)
WEIGHTS = {"bos": 3, "choch": 3, "rejection": 3, "engulfing": 2, "swing": 2, "ema": 1}

METHODOLOGY = {
    "what_it_is": "a READ of closed bars for the operator: a table and chart labels. Not a signal, not recorded, never an input to SignalMesh, no order",
    "swing_labels": f"confirmed swing pivots (strength {SWING_L}, known {SWING_L} bars later): a high above the previous confirmed high is HH, below it LH; "
                    "a low above the previous confirmed low is HL, below it LL",
    "rejection": f"a closed bar whose wick beyond the body is at least {REJ_WICK_X_BODY:g} x the body, which closes in the far {int(REJ_CLOSE_FRAC * 100)}% of its range, "
                 f"whose range is at least {REJ_MIN_ATR:g} ATR, and whose high (bearish) or low (bullish) is the extreme of the last {PATTERN_LOOKBACK} bars",
    "engulfing": f"a closed bar whose body covers the previous bar's body in the other direction and is at least {ENG_MIN_ATR:g} ATR",
    "momentum": f"RSI({RSI_N}) Wilder; MACD({MACD[0]},{MACD[1]},{MACD[2]}) line against its signal line; EMA{EMA_FAST} against EMA{EMA_SLOW}; closes of closed bars",
    "volatility": "ATR(14) Wilder against its own mean over the last 100 bars: under 0.8 LOW, over 1.25 HIGH, else NORMAL",
    "volume": f"the newest closed bar's MT5 TICK volume against the mean of the {VOL_N} before it — activity, not traded volume",
    "price_zone": "where the last close sits between the newest confirmed swing low and swing high: above the middle PREMIUM, below it DISCOUNT",
    "conditions": "six conditions per side, each CONFIRMED / WAITING / FAILED / NOT APPLICABLE with its reason and bar; weights "
                  + ", ".join(f"{k} {v}" for k, v in WEIGHTS.items()) + ". A count of conditions, not a probability and not an instruction",
    "structure_rows": "trend, BOS / CHoCH, support / resistance, FVG, order blocks, liquidity, inducement are read from smc-v1 on each timeframe — nothing is recalculated",
    "not_available": "TradingView strategy-tester statistics (trades, win rate, average R) and Pine's own trade models are not reproduced; the newest Pine signal SignalMesh received is shown verbatim",
}


def _iso(t) -> str | None:
    return None if t is None else datetime.fromtimestamp(int(t), timezone.utc).isoformat()


def ema(vals: list[float], n: int) -> list[float | None]:
    out: list[float | None] = []
    k, e = 2 / (n + 1), None
    for i, v in enumerate(vals):
        e = v if e is None else v * k + e * (1 - k)
        out.append(e if i >= n - 1 else None)
    return out


def rsi(closes: list[float], n: int = RSI_N) -> list[float | None]:
    out: list[float | None] = [None] * len(closes)
    up = dn = 0.0
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        g, l = max(d, 0.0), max(-d, 0.0)
        if i <= n:
            up, dn = up + g, dn + l
            if i == n:
                up, dn = up / n, dn / n
        else:
            up, dn = (up * (n - 1) + g) / n, (dn * (n - 1) + l) / n
        if i >= n:
            out[i] = 100.0 if dn == 0 else 100 - 100 / (1 + up / dn)
    return out


def macd(closes: list[float]) -> tuple[list[float | None], list[float | None]]:
    f, s = ema(closes, MACD[0]), ema(closes, MACD[1])
    line = [None if a is None or b is None else a - b for a, b in zip(f, s)]
    vals = [x for x in line if x is not None]
    sig = ema(vals, MACD[2])
    pad = len(line) - len(vals)
    return line, [None] * pad + sig


def swing_labels(b: list[dict], step: int) -> list[dict]:
    """HH / LH / HL / LL on confirmed pivots. A label compares a pivot with the previous confirmed pivot of its own kind."""
    out, last = [], {"H": None, "L": None}
    for p in sorted(pivots(b, SWING_L), key=lambda p: (p["i"], p["kind"])):
        prev = last[p["kind"]]
        if p["kind"] == "H":
            lab = "H" if prev is None else "HH" if p["price"] > prev else "LH"
        else:
            lab = "L" if prev is None else "HL" if p["price"] > prev else "LL"
        last[p["kind"]] = p["price"]
        out.append({"kind": "swing", "label": lab, "side": "high" if p["kind"] == "H" else "low", "price": p["price"], "time": b[p["i"]]["t"],
                    "confirmed_at": b[p["ci"]]["t"] + step,
                    "reason": f"confirmed swing {'high' if p['kind'] == 'H' else 'low'}" + ("" if prev is None else f" against the previous one at {prev:.6g}")})
    return out


def candle_patterns(b: list[dict], atr: list[float | None], step: int) -> list[dict]:
    """Rejection and engulfing candles, each from its own closed bar and the bars before it."""
    out = []
    for i in range(PATTERN_LOOKBACK, len(b)):
        k, a = b[i], atr[i]
        rng = k["h"] - k["l"]
        if not a or rng <= 0:
            continue
        body = abs(k["c"] - k["o"])
        top, bot = k["h"] - max(k["o"], k["c"]), min(k["o"], k["c"]) - k["l"]
        win = b[i - PATTERN_LOOKBACK + 1:i + 1]
        if rng >= REJ_MIN_ATR * a:
            if top >= REJ_WICK_X_BODY * max(body, rng * 0.02) and (k["c"] - k["l"]) / rng <= REJ_CLOSE_FRAC and k["h"] >= max(x["h"] for x in win):
                out.append({"kind": "pattern", "label": "BEAR REJECTION", "dir": "bear", "type": "rejection", "side": "high", "price": k["h"], "time": k["t"], "confirmed_at": k["t"] + step,
                            "reason": f"upper wick {top / max(body, 1e-12):.1f} x the body, closed in the lower {int((k['c'] - k['l']) / rng * 100)}% of its range, at the high of the last {PATTERN_LOOKBACK} bars"})
            if bot >= REJ_WICK_X_BODY * max(body, rng * 0.02) and (k["h"] - k["c"]) / rng <= REJ_CLOSE_FRAC and k["l"] <= min(x["l"] for x in win):
                out.append({"kind": "pattern", "label": "BULL REJECTION", "dir": "bull", "type": "rejection", "side": "low", "price": k["l"], "time": k["t"], "confirmed_at": k["t"] + step,
                            "reason": f"lower wick {bot / max(body, 1e-12):.1f} x the body, closed in the upper {int((k['h'] - k['c']) / rng * 100)}% of its range, at the low of the last {PATTERN_LOOKBACK} bars"})
        p = b[i - 1]
        if body >= ENG_MIN_ATR * a:
            if p["c"] > p["o"] and k["c"] < k["o"] and k["o"] >= p["c"] and k["c"] <= p["o"]:
                out.append({"kind": "pattern", "label": "BEAR ENGULF", "dir": "bear", "type": "engulfing", "side": "high", "price": k["h"], "time": k["t"], "confirmed_at": k["t"] + step,
                            "reason": f"a down bar whose body covers the previous up bar's body ({body / a:.1f} ATR)"})
            if p["c"] < p["o"] and k["c"] > k["o"] and k["o"] <= p["c"] and k["c"] >= p["o"]:
                out.append({"kind": "pattern", "label": "BULL ENGULF", "dir": "bull", "type": "engulfing", "side": "low", "price": k["l"], "time": k["t"], "confirmed_at": k["t"] + step,
                            "reason": f"an up bar whose body covers the previous down bar's body ({body / a:.1f} ATR)"})
    return out


def _cond(name, status, reason, at=None):
    return {"name": name, "weight": WEIGHTS[name], "status": status, "reason": reason, "bar": at, "bar_utc": _iso(at)}


def conditions(b: list[dict], labels: list[dict], smc_tf: dict | None, e_fast, e_slow, step: int) -> dict:
    """Six conditions per side. CONFIRMED / WAITING / FAILED / NOT APPLICABLE — a count, never an instruction."""
    out = {}
    recent_from = b[max(0, len(b) - PATTERN_RECENT)]["t"] if b else 0
    events = [e for e in ((smc_tf or {}).get("structure") or []) if e.get("status") == "confirmed"]
    for side, d, swing_ok, swing_bad, kind in (("SELL", "bear", "LH", "HH", "high"), ("BUY", "bull", "HL", "LL", "low")):
        rows = []
        for typ in ("rejection", "engulfing"):
            hit = next((x for x in reversed(labels) if x["kind"] == "pattern" and x["type"] == typ and x["dir"] == d and x["time"] >= recent_from), None)
            rows.append(_cond(typ, "CONFIRMED", f"{hit['label']} on a closed bar: {hit['reason']}", hit["time"]) if hit
                        else _cond(typ, "WAITING", f"no {'bearish' if d == 'bear' else 'bullish'} {typ} on the last {PATTERN_RECENT} closed bars"))
        sw = next((x for x in reversed(labels) if x["kind"] == "swing" and x["side"] == kind), None)
        if sw is None or sw["label"] in ("H", "L"):
            rows.append(_cond("swing", "NOT APPLICABLE", f"fewer than two confirmed swing {kind}s in the loaded bars"))
        elif sw["label"] == swing_ok:
            rows.append(_cond("swing", "CONFIRMED", f"the newest confirmed swing {kind} is a {swing_ok} at {sw['price']:.6g}", sw["time"]))
        else:
            rows.append(_cond("swing", "FAILED", f"the newest confirmed swing {kind} is a {sw['label']} at {sw['price']:.6g}, not a {swing_ok}", sw["time"]))
        for typ, nm in (("BOS", "bos"), ("CHoCH", "choch")):
            if smc_tf is None or smc_tf.get("state") != "OK":
                rows.append(_cond(nm, "NOT APPLICABLE", "the structure study has no result for this timeframe"))
                continue
            ev = next((e for e in reversed(events) if e.get("type") == typ), None)
            if ev is None:
                rows.append(_cond(nm, "WAITING", f"no confirmed {typ} in the loaded bars"))
            elif ev.get("dir") == d:
                rows.append(_cond(nm, "CONFIRMED", f"the newest {typ} is {'down' if d == 'bear' else 'up'} ({ev.get('scope')}): a close beyond {ev.get('level'):.6g}", ev.get("time")))
            else:
                rows.append(_cond(nm, "FAILED", f"the newest {typ} is {'up' if d == 'bear' else 'down'} ({ev.get('scope')}), against this side", ev.get("time")))
        if e_fast is None or e_slow is None:
            rows.append(_cond("ema", "NOT APPLICABLE", f"fewer than {EMA_SLOW} closed bars"))
        else:
            ok = e_fast < e_slow if d == "bear" else e_fast > e_slow
            rows.append(_cond("ema", "CONFIRMED" if ok else "FAILED", f"EMA{EMA_FAST} {e_fast:.6g} is {'below' if e_fast < e_slow else 'above'} EMA{EMA_SLOW} {e_slow:.6g}", b[-1]["t"]))
        met = [r for r in rows if r["status"] == "CONFIRMED"]
        out[side] = {"conditions": rows, "confirmed": len(met), "of": len(rows), "weight": sum(r["weight"] for r in met), "weight_of": sum(WEIGHTS.values()),
                     "structural": sum(1 for r in met if r["name"] in ("bos", "choch", "rejection"))}
    return out


def _row(key, label, value, source, tone="", note=""):
    return {"key": key, "label": label, "value": value, "tone": tone, "source": source, "note": note}


def _na(key, label, why, source="chart-read-v1"):
    return _row(key, label, "NOT AVAILABLE", source, "dim", why)


def _tone(word) -> str:
    w = str(word or "").lower()
    return "bad" if "bear" in w or w in ("sell", "short") else "good" if "bull" in w or w in ("buy", "long") else "dim"


def analyse(symbol: str, tf: str, b: list[dict], smc_by_tf: dict[str, dict | None] | None = None, daily: dict | None = None,
            engine: dict | None = None, pine: dict | None = None, source: str = "") -> dict:
    """`b` = closed bars of the chart timeframe [{t,o,h,l,c,v}]; `smc_by_tf` = smc-v1 results keyed by timeframe (1w, 1d, 4h, 1h and `tf`);
    `daily` = daily-forecast-v1; `engine` = {bias, regime, structure} from SignalMesh's snapshot; `pine` = the newest signal row."""
    step = TF_SEC.get(tf, 900)
    smc_by_tf = smc_by_tf or {}
    base = {"symbol": symbol, "tf": tf, "kind": "TERMINAL STUDY — a read of closed bars, not SignalMesh engine output and not a signal", "method_version": VERSION,
            "methodology": METHODOLOGY, "recorded": False, "source": source, "bars_used": len(b), "calculated_at": datetime.now(timezone.utc).isoformat(),
            "through_bar": b[-1]["t"] if b else None, "through_close": b[-1]["t"] + step if b else None, "through_close_utc": _iso(b[-1]["t"] + step) if b else None,
            "note_tradingview": "values can differ from TradingView: Pine runs on TradingView's bars and day, this reads SignalMesh's stored broker bars"}
    if len(b) < 60:
        return {**base, "state": "NOT_AVAILABLE", "note": f"{len(b)} closed {tf} bars stored; the chart read needs at least 60", "rows": [], "labels": [], "conditions": None}
    atr = atr_rma(b)
    closes = [k["c"] for k in b]
    labels = sorted(swing_labels(b, step) + candle_patterns(b, atr, step), key=lambda x: (x["confirmed_at"], x["time"], x["label"]))
    ef, es = ema(closes, EMA_FAST)[-1], ema(closes, EMA_SLOW)[-1]
    here = smc_by_tf.get(tf)
    cond = conditions(b, labels, here, ef, es, step)
    last = closes[-1]
    rows = []

    def trend_of(t):
        r = smc_by_tf.get(t)
        return (r.get("trend") or {}).get("external") if r and r.get("state") == "OK" else None

    def last_event(t):
        r = smc_by_tf.get(t)
        ev = [e for e in (r or {}).get("structure") or [] if e.get("status") == "confirmed"] if r and r.get("state") == "OK" else []
        return ev[-1] if ev else None

    for key, lab, t in (("weekly", "WEEKLY", "1w"), ("daily", "DAILY", "1d"), ("h4", "4H", "4h"), ("h1", "1H TREND", "1h")):
        tr = trend_of(t)
        if t not in smc_by_tf or smc_by_tf[t] is None:
            rows.append(_na(key, lab, f"no {t} bars stored for {symbol}", "smc-v1"))
        elif tr is None:
            rows.append(_row(key, lab, "UNKNOWN", "smc-v1", "dim", (smc_by_tf[t] or {}).get("note") or "no confirmed break of structure yet on this timeframe"))
        else:
            ev = last_event(t)
            rows.append(_row(key, lab, f"{tr.upper()}ISH" + (f" | {ev['type']} {'DN' if ev['dir'] == 'bear' else 'UP'}" if ev else ""), "smc-v1", _tone(tr),
                             f"external trend on closed {t} bars" + (f"; newest break {ev['type']} at {ev['level']:.6g}" if ev else "")))
    sw = [x for x in labels if x["kind"] == "swing"]
    hi = next((x for x in reversed(sw) if x["side"] == "high"), None)
    lo = next((x for x in reversed(sw) if x["side"] == "low"), None)
    tr_here = trend_of(tf)
    rows.append(_row("swing", "SWING STRUCTURE", f"{(tr_here or 'unknown').upper()} | {hi['label'] if hi else '—'} / {lo['label'] if lo else '—'}", "smc-v1 + chart-read-v1", _tone(tr_here),
                     f"chart timeframe {tf}: trend, then the newest confirmed swing high and swing low"))
    ev = last_event(tf)
    rows.append(_row("last_confirm", "LAST CONFIRM", f"{ev['type']} {'DOWN' if ev['dir'] == 'bear' else 'UP'} {ev['level']:.6g}" if ev else "NONE", "smc-v1", _tone(ev["dir"]) if ev else "dim",
                     f"newest confirmed break on {tf}" + (f", on the bar of {_iso(ev.get('time'))}" if ev else "")))
    sr = [z for z in (here or {}).get("sr") or [] if z.get("status", "active") == "active"] if here and here.get("state") == "OK" else None
    if sr is None:
        rows += [_na("resistance", "RESISTANCE", "the structure study has no result for this timeframe", "smc-v1"), _na("support", "SUPPORT", "the structure study has no result for this timeframe", "smc-v1")]
    else:
        above = min((z for z in sr if z["level"] > last), key=lambda z: z["level"], default=None)
        below = max((z for z in sr if z["level"] < last), key=lambda z: z["level"], default=None)
        rows.append(_row("resistance", "RESISTANCE", f"{above['level']:.6g}" if above else "NONE ABOVE", "smc-v1", "bad" if above else "dim", f"nearest above the last close; {above['strength']}, {above['touches']} touch(es)" if above else "no swing cluster above the last close in the loaded bars"))
        rows.append(_row("support", "SUPPORT", f"{below['level']:.6g}" if below else "NONE BELOW", "smc-v1", "good" if below else "dim", f"nearest below the last close; {below['strength']}, {below['touches']} touch(es)" if below else "no swing cluster below the last close in the loaded bars"))
    r_, (ml, ms) = rsi(closes)[-1], macd(closes)
    if r_ is None or ml[-1] is None or ms[-1] is None:
        rows.append(_na("momentum", "MOMENTUM", "too few closed bars for RSI / MACD"))
    else:
        up = ml[-1] > ms[-1]
        rows.append(_row("momentum", "MOMENTUM", f"RSI {r_:.1f} | MACD {'UP' if up else 'DOWN'}", "chart-read-v1", "good" if up and r_ >= 50 else "bad" if (not up) and r_ < 50 else "dim",
                         f"RSI({RSI_N}) on closes; MACD line {ml[-1]:.5g} {'above' if up else 'below'} its signal {ms[-1]:.5g}; EMA{EMA_FAST} {'above' if ef > es else 'below'} EMA{EMA_SLOW}" if ef is not None and es is not None else "RSI / MACD on closes"))
    a_now, a_hist = atr[-1], [x for x in atr[-100:] if x]
    if not a_now or len(a_hist) < 20:
        rows.append(_na("volatility", "VOLATILITY", "too few closed bars for ATR"))
    else:
        ratio = a_now / (sum(a_hist) / len(a_hist))
        rows.append(_row("volatility", "VOLATILITY", f"{'LOW' if ratio < 0.8 else 'HIGH' if ratio > 1.25 else 'NORMAL'} | ATR {a_now:.5g}", "chart-read-v1", "warn" if ratio > 1.25 else "", f"ATR(14) is {ratio:.2f} x its mean of the last {len(a_hist)} bars"))
    if hi and lo and hi["price"] > lo["price"]:
        pos = (last - lo["price"]) / (hi["price"] - lo["price"])
        rows.append(_row("price_zone", "PRICE ZONE", "PREMIUM" if pos > 0.5 else "DISCOUNT", "chart-read-v1", "bad" if pos > 0.5 else "good",
                         f"the last close is {pos * 100:.0f}% of the way from the newest confirmed swing low {lo['price']:.6g} to the swing high {hi['price']:.6g}" + (" (outside that range)" if not 0 <= pos <= 1 else "")))
    else:
        rows.append(_na("price_zone", "PRICE ZONE", "no confirmed swing high and low to measure between"))
    vols = [k.get("v", 0.0) for k in b]
    if len(vols) > VOL_N and sum(vols[-VOL_N - 1:-1]) > 0:
        x = vols[-1] / (sum(vols[-VOL_N - 1:-1]) / VOL_N)
        rows.append(_row("volume", "VOLUME", f"{x:.1f}x average", "chart-read-v1", "warn" if x >= 1.5 else "", f"the newest closed bar's tick volume against the mean of the {VOL_N} bars before it — MT5 tick volume (activity), not traded volume"))
    else:
        rows.append(_na("volume", "VOLUME", "no tick volume stored for these bars"))
    if engine:
        rows.append(_row("engine", "ENGINE BIAS", f"{str(engine.get('bias') or 'UNKNOWN').upper()} | {engine.get('regime') or 'regime unknown'}", "SignalMesh engine (verbatim)", _tone(engine.get("bias")),
                         f"the engine's own validated bias and regime; its 15m structure word: {engine.get('structure') or 'UNKNOWN'}"))
    else:
        rows.append(_na("engine", "ENGINE BIAS", "the engine snapshot could not be read", "SignalMesh engine"))
    for c in ("SELL", "BUY"):
        k = cond[c]
        rows.append(_row(f"cond_{c.lower()}", f"{c} CONDITIONS", f"{k['confirmed']}/{k['of']} · weight {k['weight']}/{k['weight_of']}", "chart-read-v1", "bad" if c == "SELL" and k["structural"] else "good" if c == "BUY" and k["structural"] else "dim",
                         "confirmed: " + (", ".join(r["name"] for r in k["conditions"] if r["status"] == "CONFIRMED") or "none") + " · a count of conditions on closed bars, not an instruction"))
    if here and here.get("state") == "OK":
        def near(items, d, lvl=lambda z: (z["low"] + z["high"]) / 2):
            xs = [z for z in items if z.get("dir") == d and z.get("status") in ("fresh", "partial", "tested")]
            return min(xs, key=lambda z: abs(lvl(z) - last), default=None)
        fb, fs = near(here.get("fvg") or [], "bull"), near(here.get("fvg") or [], "bear")
        rows.append(_row("fvg", "FVG BULL | BEAR", f"{f'{fb['low']:.6g}–{fb['high']:.6g}' if fb else '—'} | {f'{fs['low']:.6g}–{fs['high']:.6g}' if fs else '—'}", "smc-v1", "", "nearest unfilled fair value gap on each side"))
        ob, os_ = near(here.get("order_blocks") or [], "bull"), near(here.get("order_blocks") or [], "bear")
        rows.append(_row("order_block", "ORDER BLOCK", f"{f'bull {ob['low']:.6g}–{ob['high']:.6g} {ob['strength']}' if ob else 'bull —'} | {f'bear {os_['low']:.6g}–{os_['high']:.6g} {os_['strength']}' if os_ else 'bear —'}", "smc-v1", "", "nearest order block not yet invalidated, with its strength"))
        liq = [z for z in here.get("liquidity") or [] if z.get("status") == "unswept"]
        bs = min((z for z in liq if z.get("side") == "BSL" and z["level"] > last), key=lambda z: z["level"], default=None)
        ss = max((z for z in liq if z.get("side") == "SSL" and z["level"] < last), key=lambda z: z["level"], default=None)
        rows.append(_row("liquidity", "LIQUIDITY", f"BUY-SIDE {f'{bs['level']:.6g}' if bs else '—'} | SELL-SIDE {f'{ss['level']:.6g}' if ss else '—'}", "smc-v1", "", "nearest unswept swing liquidity above and below the last close"))
        idm = next((z for z in reversed(here.get("inducement") or []) if z.get("status") == "potential"), None)
        rows.append(_row("inducement", "INDUCEMENT", f"{'low' if idm['dir'] == 'bull' else 'high'} {idm['level']:.6g} may be swept first" if idm else "NONE", "smc-v1", "warn" if idm else "dim", (idm or {}).get("note") or "no resting inducement in the loaded bars"))
    else:
        for key, lab in (("fvg", "FVG BULL | BEAR"), ("order_block", "ORDER BLOCK"), ("liquidity", "LIQUIDITY"), ("inducement", "INDUCEMENT")):
            rows.append(_na(key, lab, "the structure study has no result for this timeframe", "smc-v1"))
    if daily and daily.get("state") == "OK":
        rows.append(_row("day_forecast", "DAY FORECAST", f"TOP {daily['top']:.6g} | BOT {daily['bottom']:.6g}", "daily-forecast-v1", "", f"broker day from {daily.get('day_start_utc')}; ADR {daily.get('adr'):.6g}"))
        rows.append(_row("adr", "ADR STATUS", f"ADR {daily.get('used_pct', 0):.0f}% used | room {daily.get('room_up', 0):.6g} up / {daily.get('room_down', 0):.6g} down", "daily-forecast-v1", "warn" if (daily.get("used_pct") or 0) >= 85 else "", str(daily.get("status") or "")))
    else:
        why = (daily or {}).get("note") or "the daily forecast is not available for this instrument"
        rows += [_na("day_forecast", "DAY FORECAST", why, "daily-forecast-v1"), _na("adr", "ADR STATUS", why, "daily-forecast-v1")]
    if pine:
        rows.append(_row("pine", "NEWEST SIGNAL (SIGNALMESH)", f"{pine.get('direction')} · {pine.get('grade') or 'no grade'} · {pine.get('status')}" + (" · EXPIRED" if pine.get("stale") else ""), "the signal SignalMesh received (verbatim)",
                         "dim" if pine.get("stale") else _tone(pine.get("direction")), f"{pine.get('system')} · {pine.get('signal_id')} · {pine.get('age_h')}h old — a SignalMesh recommendation, not a broker order"))
    else:
        rows.append(_row("pine", "NEWEST SIGNAL (SIGNALMESH)", "NONE", "the signal SignalMesh received", "dim", f"SignalMesh holds no signal for {symbol} in its newest 200"))
    rows.append(_na("tester", "TRADES W/L · WIN % · AVG R", "TradingView's strategy-tester statistics do not exist outside TradingView; the terminal's own measured record is the Forecast Journal", "TradingView"))
    return {**base, "state": "OK", "note": "", "atr": atr[-1], "last_close": last, "rows": rows, "labels": labels, "conditions": cond,
            "ema": {"fast": ef, "slow": es, "fast_n": EMA_FAST, "slow_n": EMA_SLOW}}
