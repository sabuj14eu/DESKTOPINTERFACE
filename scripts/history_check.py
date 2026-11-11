"""No-lookahead check of the forecast scorer on RECORDED market history — runs ON THE BOX, inside
the terminal container, so production candles never have to leave it.

    python /srv/terminal/scripts/history_check.py < history-export/GOLD_15m.json          (the scorer)
    ... < a document {"intraday": <GOLD_15m.json>, "daily": <GOLD_1d.json>}              (the daily-forecast module)
    ... < a document {"studies": <GOLD_15m.json>}                                        (the pattern studies)

Reads one exported candle file from stdin (scripts/export_history.sh), writes nothing, asks
SignalMesh for nothing. For every test forecast placed on the real bars it scores every prefix
of the series and requires exactly the first events of scoring the whole series. Prints one line.
The forecasts come from the fixture demo generator (made-up levels every 24th bar): the point is
to exercise the SCORER on real bars, not to judge any study.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "adapter"))   # the adapter package sits beside scripts/, in the image and in the checkout

from signalmesh_terminal import journal as fj
from signalmesh_terminal import recorder as rec

d = json.load(sys.stdin)
if "intraday" in d and "daily" in d:
    # the DAILY-FORECAST module on recorded bars: every prefix of the 15m series must report the same forecasts as the whole series
    from signalmesh_terminal import audit

    conv = lambda doc: [{"t": k["t"], "o": k["open"], "h": k["high"], "l": k["low"], "c": k["close"]} for k in doc["candles"]]  # noqa: E731
    sym, tf = d["intraday"]["symbol"], d["intraday"]["tf"]
    a = audit.daily_forecast_audit(sym, conv(d["daily"]), conv(d["intraday"]), tf, stride=2)
    ok = a["disagreements"] == 0 and a["refused"] == 0 and a["forecasts"] > 0
    print(f"{'OK  ' if ok else 'FAIL'} {sym:7}{tf:4} daily-forecast no-lookahead / no-repaint on recorded bars: {a['forecasts']} forecasts ({', '.join(a['sides']) or 'none'}), "
          f"{a['checks']} prefix checks, {a['disagreements']} disagreements, {a['refused']} refused")
    sys.exit(0 if ok else 1)
if "studies" in d:
    # the PATTERN STUDIES (Fibonacci, anchored VWAP, Wolfe, Elliott, volume profile) on recorded bars: every prefix must agree with the whole series
    from signalmesh_terminal import audit

    doc = d["studies"]
    sym, tf = doc["symbol"], doc["tf"]
    bars = [{"t": k["t"], "o": k["open"], "h": k["high"], "l": k["low"], "c": k["close"], "v": float(k.get("tick_volume") or 0)} for k in doc["candles"]][-1200:]
    a = audit.pattern_studies_audit(sym, bars, tf, stride=40)
    ok = a["state"] == "OK" and a["disagreements"] == 0 and a["checks"] > 0
    print(f"{'OK  ' if ok else 'FAIL'} {sym:7}{tf:4} pattern studies no-lookahead / no-repaint on recorded bars: {len(bars)} bars, {a['checks']} prefix checks, "
          f"{a['disagreements']} disagreements · logged: {a['wolfe']} Wolfe, {a['elliott']} Elliott events, {a['fib']} Fibonacci sets · "
          f"anchored VWAP {a.get('avwap', a.get('note'))} · volume profile {a.get('vp', '')}")
    sys.exit(0 if ok else 1)
tf, sym = d["tf"], d["symbol"]
bars = [{"t": k["t"], "o": k["open"], "h": k["high"], "l": k["low"], "c": k["close"]} for k in d["candles"]][-1500:]
m = rec.FixtureDemoModule()
forecasts, refused = [], 0
for f in m.forecasts(sym, tf, bars):
    try:
        forecasts.append(fj.validate({**f, "symbol": sym, "timeframe": tf, "module": m.name, "method_version": m.method_version}))
    except fj.ForecastRefused:
        refused += 1
bad, cuts, results = 0, 0, {}
for f in forecasts:
    full = fj.score(f, bars)
    results[fj.result_of([e["event"] for e in full])] = results.get(fj.result_of([e["event"] for e in full]), 0) + 1
    for cut in range(0, len(bars) + 1, 5):
        cuts += 1
        part = fj.score(f, bars[:cut])
        late = [e for e in full[len(part):] if cut and e["bar"] <= bars[cut - 1]["t"]]
        if part != full[:len(part)] or late:
            bad += 1
ok = bad == 0 and len(forecasts) > 0
print(f"{'OK  ' if ok else 'FAIL'} {sym:7}{tf:4} scorer no-lookahead on recorded bars: {len(bars)} bars, {len(forecasts)} test forecasts"
      f"{f' ({refused} refused)' if refused else ''}, {cuts} prefix checks, {bad} disagreements · "
      + ", ".join(f"{k} {v}" for k, v in sorted(results.items())))
sys.exit(0 if ok else 1)
