"""NO-LOOKAHEAD / NO-REPAINT AUDITS of the forecasting modules, shared by the test suite (seeded
series) and by scripts/history_check.py (recorded Gold and Silver history, on the box).

The idea is always the same as tests/test_smc.py: run the module on every prefix of the series —
what a live terminal would have seen at that moment — and require that every forecast a prefix
reports is reported IDENTICALLY by the full series, and that the full series reports no forecast
dated inside a prefix that the prefix itself did not report.
"""
from __future__ import annotations

from . import forecast as fc
from . import journal as fj
from . import studies as ps


def daily_forecast_audit(symbol: str, daily: list[dict], intraday: list[dict], tf: str = "15m", stride: int = 3) -> dict:
    """`daily` = closed 1d bars, `intraday` = closed bars of `tf`, both ascending."""
    step = fj.TF_SECONDS[tf]
    m = fc.DailyForecastModule()

    def run(bars, upto):
        closed = [d for d in daily if d["t"] + fc.DAY <= upto]          # the daily bars that had closed by then
        return {f["made_bar"]: f for f in m.forecasts(symbol, tf, bars, lambda s, t: closed)}

    end = intraday[-1]["t"] + step if intraday else 0
    full = run(intraday, end)
    checks = bad = 0
    for cut in range(max(1, len(intraday) % stride), len(intraday) + 1, stride):
        part_bars = intraday[:cut]
        upto = part_bars[-1]["t"] + step
        part = run(part_bars, upto)
        checks += 1
        if any(full.get(t) != f for t, f in part.items()):               # a forecast seen live must be the same forecast later
            bad += 1
        elif any(t < upto and t not in part for t in full if t >= part_bars[0]["t"] and _covered(full[t], part_bars)):
            bad += 1                                                     # the full series must not invent one the live view never had
    refused = 0
    for f in full.values():
        try:
            fj.validate({**f, "symbol": symbol, "timeframe": tf, "module": m.name, "method_version": m.method_version})
        except fj.ForecastRefused:
            refused += 1
    return {"forecasts": len(full), "checks": checks, "disagreements": bad, "refused": refused,
            "sides": sorted({f["detail"]["side"] for f in full.values()})}


def _covered(f: dict, part_bars: list[dict]) -> bool:
    """A prefix can only be asked about a day it holds from that day's start."""
    return part_bars[0]["t"] <= f["detail"]["day_start"] + 2 * 3600


_WOLFE_DEF = ("direction", "points", "entry", "sl", "tp1", "tp2", "epa", "apex_time", "expires_time", "made_bar", "confirmed_at")


def pattern_studies_audit(symbol: str, bars: list[dict], tf: str = "15m", stride: int = 25) -> dict:
    """pattern-studies-v1 on every prefix of `bars` ([{t,o,h,l,c,v}] ascending): the Wolfe, Elliott and
    Fibonacci logs of a prefix must be the beginning of the logs of the whole series, and nothing a prefix
    reports may be dated after its own last bar."""
    full = ps.analyse(symbol, tf, bars)
    if full["state"] != "OK":
        return {"state": full["state"], "note": full["note"], "checks": 0, "disagreements": 0, "wolfe": 0, "elliott": 0, "fib": 0}
    step = ps.TF_SEC[tf]
    wdef = lambda rows: [tuple(repr(r[k]) for k in _WOLFE_DEF) for r in rows]      # noqa: E731
    checks = bad = 0
    for n in range(ps.MIN_BARS, len(bars), stride):
        part = ps.analyse(symbol, tf, bars[:n])
        upto = bars[n - 1]["t"]
        checks += 1
        ok = (wdef(part["wolfe"]["log"]) == wdef([p for p in full["wolfe"]["log"] if p["made_bar"] <= upto])
              and part["elliott"]["log"] == [e for e in full["elliott"]["log"] if e["bar"] <= upto]
              and part["fib"]["log"] == [e for e in full["fib"]["log"] if e["made_bar"] <= upto]
              and part["through_close"] == upto + step
              and all(a["anchor_time"] <= upto and a["points"][-1]["t"] == upto for a in (part["avwap"] or {}).get("anchors", [])))
        bad += 0 if ok else 1
    return {"state": "OK", "checks": checks, "disagreements": bad, "wolfe": len(full["wolfe"]["log"]), "elliott": len(full["elliott"]["log"]),
            "fib": len(full["fib"]["log"]), "avwap": full["avwap"]["state"], "vp": full["vp"]["state"]}
