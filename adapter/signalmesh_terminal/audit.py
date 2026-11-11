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
