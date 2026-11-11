"""SERVER-SIDE FORECAST RECORDER — runs inside the adapter, whether or not a chart is open.

Each pass: (1) every registered forecasting module is run on the CLOSED bars of every
instrument SignalMesh stores, on that module's own timeframes, and every forecast it reports
is written to the journal (once — the journal ignores a forecast it already holds);
(2) every forecast without a final result is scored from the closed bars that came after it.

Recording from the server, not the browser, is what keeps the record honest: a forecast is
recorded because it was made, not because somebody was watching that chart, and losing
forecasts are recorded exactly like winning ones.

Reads SignalMesh candles through the adapter's GET-only provider and its cache. Writes only to
the terminal's own journal file. With no module registered and no open forecast, a pass asks
SignalMesh for nothing.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Callable, Protocol

from .journal import TERMINAL, TF_SECONDS, ForecastRefused, Journal, score

log = logging.getLogger("signalmesh_terminal.recorder")


class ForecastModule(Protocol):
    """A forecasting study. `forecasts` must use closed bars only and must never look ahead:
    a forecast it reports with made_bar = T may depend only on bars up to and including T."""
    name: str
    method_version: str
    timeframes: tuple[str, ...]

    def forecasts(self, symbol: str, timeframe: str, bars: list[dict]) -> list[dict]: ...


# Forecasting modules register here, one release at a time. Empty in the journal release.
MODULES: list[ForecastModule] = []


def closed_only(bars: list[dict], timeframe: str, now: float | None = None) -> list[dict]:
    """Belt and braces: drop any bar whose own period has not ended yet."""
    step, now = TF_SECONDS[timeframe], time.time() if now is None else now
    return [b for b in bars if b["t"] + step <= now]


def run_once(journal: Journal, bars_for: Callable[[str, str], list[dict]], symbols_for: Callable[[str], list[str]],
             modules: list | None = None, now: float | None = None) -> dict:
    """One recorder pass. `bars_for(symbol, tf)` returns closed bars ascending (may raise);
    `symbols_for(tf)` returns the instruments that have that timeframe stored."""
    modules = MODULES if modules is None else modules
    out = {"at": datetime.now(timezone.utc).isoformat(), "modules": [m.name for m in modules], "recorded": 0, "already_held": 0,
           "refused": 0, "outcomes_added": 0, "open": 0, "not_covered": 0, "errors": []}
    series: dict[tuple[str, str], list[dict]] = {}

    def bars(sym: str, tf: str) -> list[dict]:
        if (sym, tf) not in series:
            series[(sym, tf)] = closed_only(bars_for(sym, tf), tf, now)
        return series[(sym, tf)]

    for m in modules:
        for tf in m.timeframes:
            try:
                symbols = symbols_for(tf)
            except Exception as exc:  # noqa: BLE001 — a failed pass is reported, never fatal
                out["errors"].append(f"{m.name} {tf}: instruments: {exc}")
                continue
            for sym in symbols:
                try:
                    bb = bars(sym, tf)
                    for f in m.forecasts(sym, tf, bb):
                        f = {**f, "symbol": sym, "timeframe": tf, "module": m.name, "method_version": m.method_version}
                        if not any(b["t"] == f.get("made_bar") for b in bb):
                            out["refused"] += 1          # a forecast must name a closed bar that exists
                            continue
                        lag = sum(1 for b in bb if b["t"] > f["made_bar"])
                        try:
                            _, new = journal.record(f, lag_bars=lag)
                            out["recorded" if new else "already_held"] += 1
                        except ForecastRefused as exc:
                            out["refused"] += 1
                            log.warning("forecast refused (%s %s %s): %s", m.name, sym, tf, exc)
                except Exception as exc:  # noqa: BLE001
                    out["errors"].append(f"{m.name} {sym} {tf}: {type(exc).__name__}: {exc}")

    for f in journal.open_forecasts():
        out["open"] += 1
        try:
            bb = bars(f["symbol"], f["timeframe"])
        except Exception as exc:  # noqa: BLE001
            out["errors"].append(f"score {f['symbol']} {f['timeframe']}: {type(exc).__name__}: {exc}")
            continue
        if not bb or bb[0]["t"] > f["made_bar"]:
            out["not_covered"] += 1                      # the stored series no longer reaches back to the forecast's bar
            continue
        out["outcomes_added"] += advance(journal, f, score(f, bb))
    return out


def advance(journal: Journal, f: dict, events: list[dict]) -> int:
    """Status only moves forward: keep what is stored, add only later events, never past a final one."""
    held = journal.events_of(f["id"])
    names = {e["event"] for e in held}
    if names & set(TERMINAL):
        return 0
    last = max((e["bar"] for e in held), default=-1)
    return journal.add_outcomes(f["id"], [e for e in events if e["event"] not in names and e["bar"] >= last])


class Recorder:
    """The background loop: one daemon thread, one pass a minute."""

    def __init__(self, journal: Journal, bars_for, symbols_for, interval_s: float = 60.0, modules: list | None = None):
        self.journal, self.bars_for, self.symbols_for, self.interval_s, self.modules = journal, bars_for, symbols_for, interval_s, modules
        self.last: dict | None = None
        self.passes = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def pass_once(self) -> dict:
        self.last = run_once(self.journal, self.bars_for, self.symbols_for, self.modules)
        self.passes += 1
        return self.last

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        def loop():
            while not self._stop.is_set():
                try:
                    self.pass_once()
                except Exception as exc:  # noqa: BLE001 — the loop must survive anything
                    log.exception("recorder pass failed")
                    self.last = {"at": datetime.now(timezone.utc).isoformat(), "errors": [f"{type(exc).__name__}: {exc}"]}
                self._stop.wait(self.interval_s)

        self._thread = threading.Thread(target=loop, name="forecast-recorder", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def status(self) -> dict:
        return {"running": bool(self._thread and self._thread.is_alive()), "interval_s": self.interval_s, "passes": self.passes,
                "modules": [m.name for m in (MODULES if self.modules is None else self.modules)], "last_pass": self.last}


class FixtureDemoModule:
    """TEST FIXTURES ONLY — registered only when the fixture provider is running (which is refused
    in production). It is NOT a study and predicts nothing: every 24th bar it writes a made-up
    long or short with ATR-sized levels, so the journal, scorer and tab can be exercised without
    a market. Uses bars up to and including the forecast bar only."""
    name = "fixture-demo"
    method_version = "fixture-demo-v1"
    timeframes = ("15m",)

    def forecasts(self, symbol: str, timeframe: str, bars: list[dict]) -> list[dict]:
        step, out = TF_SECONDS[timeframe], []
        for i, b in enumerate(bars):
            k = b["t"] // step
            if i < 14 or k % 24:
                continue
            atr = sum(x["h"] - x["l"] for x in bars[i - 13:i + 1]) / 14
            if atr <= 0:
                continue
            d = 1 if (k // 24) % 2 == 0 else -1
            c = b["c"]
            zone = (k // 24) % 3 == 0
            lo, hi = (min(c, c - d * 0.5 * atr), max(c, c - d * 0.5 * atr)) if zone else (c, c)
            edge = lo if d == 1 else hi
            out.append({"direction": "LONG" if d == 1 else "SHORT", "pattern": "DEMO — test fixtures, not a study", "status": "confirmed",
                        "entry_mode": "zone" if zone else "at_close", "entry_low": lo, "entry_high": hi,
                        "sl": edge - d * 1.5 * atr, "invalidation": edge - d * 1.5 * atr, "tp1": c + d * 1.5 * atr, "tp2": c + d * 3.0 * atr,
                        "horizon_bars": 16, "made_bar": b["t"], "made_price": c, "detail": {"atr14": round(atr, 6)}})
        return out
