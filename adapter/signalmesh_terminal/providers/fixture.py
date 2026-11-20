"""FIXTURE PROVIDER — development and tests only.

Serves recorded SignalMesh responses from disk (captured from a local
SignalMesh instance through the same /api/v1 routes). Every payload it
hands out is marked `is_fixture`, the UI paints a banner across the top,
and /api/terminal/health says FIXTURE. It must never run in production:
`SMT_PROVIDER=fixture` with `SMT_ENV=production` refuses to start.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .base import ProviderError

HERE = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures"
TF_MIN = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440}


class FixtureProvider:
    name = "fixture"
    is_fixture = True
    configured = True

    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else HERE

    def _load(self, name: str):
        p = self.root / f"{name}.json"
        if not p.exists():
            raise ProviderError(f"fixture {name} missing", state="ERROR")
        with p.open() as f:
            return json.load(f)

    def readiness(self) -> dict:
        return {"reachable": True, "http": 200, **self._load("readyz"), "fixture": True}

    STORED = {"GOLD": ("1m", "15m", "1h", "1d"), "SILVER": ("1m", "15m", "1h", "1d"), "BTC": ("1m", "5m", "15m", "30m", "1h", "4h", "1d")}

    def candles(self, symbol: str, tf: str, n: int) -> dict:
        """Synthesises a deterministic closed series around the fixture's
        snapshot price so the chart has something to draw. Labelled. Mirrors a
        real reporter: only some symbols / timeframes are stored."""
        base = self._load("candles_gold_15m")
        if tf not in self.STORED.get(symbol.upper(), ()):
            return {**base, "symbol": symbol, "tf": tf, "count": 0, "candles": [],
                    "freshness": {"state": "UNKNOWN", "age_min": None, "limit_min": None, "note": f"no closed {tf} candles stored for {symbol}"}}
        snap = self._snapshot_for(symbol)
        last = (snap.get("snapshot", {}).get("market", {}) or {}).get("last_close") or 100.0
        step = max(abs(last) * 0.0008, 1e-5)
        mins = TF_MIN.get(tf, 15)
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        end = now - timedelta(minutes=now.minute % mins) - timedelta(minutes=mins)
        amp = 1.0
        if mins >= 240:
            # 4h and daily bars sit on a broker-style grid (the day opens 22:00 UTC, as an MT5 server day does)
            # and are as tall as a day of the 15m path, so ADR-based studies have realistic proportions
            off, span = 22 * 3600 % (mins * 60), mins * 60
            end = datetime.fromtimestamp(((int(now.timestamp()) - off) // span - 1) * span + off, timezone.utc)
            amp = 40.0 if mins >= 1440 else 3.0
        import math
        # Every bar is a DETERMINISTIC function of its own timestamp (not of how many bars were
        # asked for), exactly like a stored series: any request length returns the same bars,
        # and the newest bar's close is the fixture snapshot's last_close.
        k_end = int(end.timestamp()) // (mins * 60)

        ph = (sum(map(ord, symbol.upper())) % 11) * 0.57

        # yesterday's close differs from the newest intraday close, so 'day move' is not zero
        shift = (step * (9 if ph < 3 else -7)) if mins >= 1440 else 0.0

        def price(k: int) -> float:
            d = k - k_end
            # each symbol sits at its own point of the same wave (so instruments differ), and the newest close is still `last`
            return last + shift + amp * step * (14 * (math.sin(d / 40.0 + ph) - math.sin(ph)) + 4 * math.sin(d / 7.0) + 1.5 * math.sin(d / 2.3))

        rows = []
        for i in range(n, 0, -1):
            ts = end - timedelta(minutes=mins * (i - 1))
            k = k_end - (i - 1)
            o, c = price(k - 1), price(k)
            h = max(o, c) + amp * step * (0.3 + 0.2 * abs(math.sin(k / 3.0)))
            l = min(o, c) - amp * step * (0.3 + 0.2 * abs(math.cos(k / 5.0)))
            rows.append({"ts": ts.isoformat(), "open": o, "high": h, "low": l, "close": c,
                         "tick_volume": float(50 + (k * 97) % 800), "spread": step * 0.3,
                         "source": "FIXTURE — not a market"})
        return {**base, "symbol": symbol, "tf": tf, "count": len(rows), "candles": rows,
                "as_of": now.isoformat(), "price_source": "FIXTURE — recorded shapes, synthetic bars",
                "freshness": {"state": "LIVE", "age_min": mins, "limit_min": mins * 3, "rule": "bar-clock-v1",
                              "basis": "since_open", "note": "fixture"}}

    def _snapshot_for(self, symbol: str) -> dict:
        name = f"snapshot_{symbol.lower()}"
        if (self.root / f"{name}.json").exists():
            return self._load(name)
        d = self._load("snapshot_gold")
        d["symbol"] = symbol
        d["snapshot"]["meta"]["symbol"] = symbol
        return d

    def snapshot(self, symbol: str) -> dict:
        return self._snapshot_for(symbol)

    # which platform build each fixture symbol imitates on GET /api/v1/market/desk (every shape the terminal must show)
    DESK_FAULT = ("SILVER",)                    # a board the platform could not build
    DESK_COLD = ("ETH",)                        # platform 5.206 just restarted: the history cells are not loaded yet
    DESK_STOCKS = ("NVDA", "AAPL", "ANT")       # platform 5.211 (lane-history-v2): a single stock's cell is never pooled
    # BTC and every other symbol: an old platform — lane-history-v1, no cell state, no verdict_board key

    def desk(self, symbol: str) -> dict:
        """The recorded desk plus the evidence keys of platform 5.202 to 5.211, in every shape the terminal must show:
        GOLD a full verdict board on loaded cells (a lane holding a setup with a backed-off cell, a stale lane with its
        break word); SILVER a board the platform could not build (fault); ETH the minute after a platform restart (cells
        COMPUTING, the board not ready); NVDA / AAPL / ANT a single stock whose small cell is its own and never pooled;
        BTC and anything else a platform before 5.203 (lane-history-v1, no cell state, no verdict_board key)."""
        d = self._load("desk_gold")
        d["symbol"] = symbol
        sym = symbol.upper()
        d["caller_scope"] = {"caller": "api_key", "user_scope": True}
        lanes = d["desk"]["lanes"]
        cold, stock = sym in self.DESK_COLD, sym in self.DESK_STOCKS
        modern = sym == "GOLD" or sym in self.DESK_FAULT or cold or stock      # a platform that sends the 5.206 / 5.211 keys
        rule = "lane-history-v2" if modern else "lane-history-v1"

        def words(n, exp, lo, hi):
            if n < 20:
                unk = {"verdict": "UNKNOWN", "icon": "?", "tone": "unknown", "why": f"n={n} is under 20: luck, not evidence", "ok": None, "n": n}
                return ({"rule": "evidence-verdict-v1", **unk},
                        {"rule": "evidence-verdict-v2", **unk, "floor": 20, "expectancy_r": exp, "sd_r": None, "lo_r": None, "hi_r": None, "level_pct": 90})
            sign = "POSITIVE" if exp > 0 else "NEGATIVE"
            v1 = {"rule": "evidence-verdict-v1", "verdict": sign, "icon": "✓" if exp > 0 else "✗", "tone": "good" if exp > 0 else "bad",
                  "why": f"n={n} and the mean is {'above' if exp > 0 else 'below'} zero", "ok": exp > 0, "n": n}
            sep = lo > 0 or hi < 0
            v2 = {"rule": "evidence-verdict-v2", "verdict": sign if sep else "CANNOT SEPARATE", "icon": v1["icon"] if sep else "?",
                  "tone": v1["tone"] if sep else "unknown", "why": f"the 90% interval {lo:+.3f}R … {hi:+.3f}R {'excludes' if sep else 'contains'} zero",
                  "ok": (exp > 0) if sep else None, "n": n, "floor": 20, "expectancy_r": exp, "sd_r": 1.02, "lo_r": lo, "hi_r": hi, "level_pct": 90}
            return v1, v2

        def cell(engine, structure, direction, n, symbol_n, exp, lo, hi):
            key = f"{structure}-{direction}"
            base = {"rule": rule, "engine": engine, "symbol": sym, "key": key,
                    "population": f"this lane's own engine: resolved paper fills in lane_observations ({engine}, lane-resolve-v1: TP1 / SL / TIMEOUT)",
                    "authority": "PAPER — a hypothesis generator, never a gate authority"}
            if cold:        # desk.lane_history with no snapshot: never n of anything, a state and a sentence
                return {**base, "state": "COMPUTING", "cells_age_s": None,
                        "level": f"{engine} × {sym} × {key} — history cells COMPUTING: computed off the page, ready within a minute of a restart",
                        "backed_off": False, "symbol_n": 0, "n": 0, "expectancy": None, "expectancy_r": None, "sd": None, "wins": 0, "losses": 0,
                        "verdict": "LUCK", "_ci": (None, None)}
            backed = symbol_n < 20 <= n and not stock
            level = (f"{engine} × all symbols × {key} — the {sym} cell holds n={symbol_n}, under 20" if backed else
                     f"{engine} × {sym} × {key}" + (f" — n={n}, under 20; a single stock is never pooled with other assets" if stock and n < 20 else ""))
            return {**base, **({"state": "FRESH", "cells_age_s": 240} if modern else {}), "level": level,
                    "backed_off": backed, "symbol_n": symbol_n, "n": n,
                    "expectancy": round(exp, 2) if n else None, "expectancy_r": exp if n else None, "sd": 1.02 if n > 1 else None,
                    "wins": int(n * 0.48), "losses": n - int(n * 0.48), "verdict": "LUCK" if n < 20 else "SMALL SAMPLE", "_ci": (lo, hi)}

        table = {("scalp-v1", "HH/HL", "BUY"): (132, 132, 0.047, -0.099, 0.193), ("scalp-v1", "LH/LL", "SELL"): (140, 140, -0.212, -0.354, -0.070),
                 ("auto-v1", "HH/HL", "BUY"): (88, 88, 0.301, 0.122, 0.480), ("auto-v1", "LH/LL", "SELL"): (61, 61, -0.038, -0.253, 0.177),
                 ("session-v1", "HH/HL", "BUY"): (47, 9, 0.118, -0.127, 0.363), ("session-v1", "LH/LL", "SELL"): (12, 12, 0.250, None, None),
                 ("swing-v1", "HH/HL", "BUY"): (0, 0, None, None, None), ("swing-v1", "LH/LL", "SELL"): (23, 23, 0.410, 0.060, 0.760)}
        if stock:           # a young series: every cell is the stock's own and small — nothing is borrowed from FX, metals or crypto
            table = {k: ((3, 3, 0.333, None, None) if k == ("session-v1", "HH/HL", "BUY") else (0, 0, None, None, None)) for k in table}
        cells = {k: cell(k[0], k[1], k[2], *v) for k, v in table.items()}
        for lane in lanes:
            c = lane["c"]
            lane["history"] = {**(lane.get("history") if isinstance(lane.get("history"), dict) else {}), "engine": "auto-v1",
                               "population": "the comparison lab (auto-v1), not this lane's own engine", "applies_to_lane": c.get("engine") == "auto-v1"}
            if c.get("decision") in ("BUY", "SELL") and c.get("structure"):
                h = cells[(c["engine"], c["structure"], c["decision"])]
                lo, hi = h["_ci"]
                v1, v2 = words(h["n"], h["expectancy_r"], lo, hi)
                lane["own_history"] = {k: v for k, v in h.items() if k != "_ci"}
                checks = lane.setdefault("validity", {}).setdefault("checks", [])
                checks[:] = [k for k in checks if not (isinstance(k, dict) and k.get("label") == "Measured history")]
                checks.append(
                    {"label": "Measured history", "ok": None if cold else v2["ok"], "verdict": v1, "verdict_v2": None if cold else v2, "population": h["population"],
                     "detail": (f"{h['level']}: NOT LOADED YET — reload in a minute; no verdict is drawn from an unloaded cell" if cold else
                                f"n={h['n']} · {h['expectancy_r']:+.3f}R · verdict {v2['verdict']} {v2['icon']} · v1 beside it: {v1['verdict']} {v1['icon']}")})
            else:
                lane["own_history"] = None
        # the Scalp lane is stale, and the learned clock says the silence is the timetable
        lanes[0]["c"]["reasons"] = ["DATA_STALE"]
        lanes[0]["c"]["stale_context"] = {"rule": "stale-context-v1", "word": "SCHEDULED BREAK", "of": sym, "tf": "15m", "limit_min": 45, "open_age_min": 12,
                                          "clock": "learned", "in_break_now": True, "gate": "unchanged: the lane is still DATA_STALE and WAIT",
                                          "note": f"{sym}'s newest 15m bar is inside its limit once the learned break hours are left out — the silence is the timetable"}
        if sym in self.DESK_FAULT:
            d["verdict_board"] = {"rule": "verdict-board-v1", "symbol": sym, "rows": [], "fault": "OperationalError: (fixture) lane_observations could not be read"}
        elif modern:
            rows = []
            labels = {"scalp-v1": ("⚡ Scalp", "15m"), "auto-v1": ("🟩 Intraday", "15m"), "session-v1": ("🕐 Session", "1h"), "swing-v1": ("🟪 Swing", "4h")}
            held = {(l["c"]["engine"], l["c"].get("structure"), l["c"]["decision"]) for l in lanes if l["c"].get("decision") in ("BUY", "SELL")}
            for k, h in cells.items():
                lo, hi = h["_ci"]
                v1, v2 = words(h["n"], h["expectancy_r"], lo, hi)
                a, b2 = v1["verdict"], v2["verdict"]
                change = ("UNDER THE FLOOR" if a == b2 == "UNKNOWN" else "SAME WORD" if a == b2 else
                          ("TICK WITHDRAWN" if a == "POSITIVE" else "CROSS WITHDRAWN") if b2 == "CANNOT SEPARATE" else "DIFFERENT WORD")
                rows.append({"engine": k[0], "label": labels[k[0]][0], "tf": labels[k[0]][1], "key": h["key"], "structure": k[1], "direction": k[2],
                             "current": k in held, "n": h["n"], "symbol_n": h["symbol_n"], "backed_off": h["backed_off"], "level": h["level"],
                             "expectancy_r": h["expectancy_r"], "sd": h["sd"], "wins": h["wins"], "losses": h["losses"], "lo_r": v2["lo_r"], "hi_r": v2["hi_r"],
                             "v1": v1, "v2": v2, "cells_state": h["state"], "cells_age_s": h["cells_age_s"],
                             "v1_class": "text-emerald-400", "v2_class": "text-slate-400", "change": change, "change_class": "text-amber-300",
                             "change_why": (f"n={h['n']} is under 20: neither rule speaks — luck, not evidence" if change == "UNDER THE FLOOR" else f"v1 says {a}, v2 says {b2}")})
            cnt = lambda rule, w: sum(1 for r in rows if r[rule]["verdict"] == w)      # noqa: E731
            d["verdict_board"] = {"rule": "verdict-board-v1", "symbol": sym, "rows": rows,
                                  "cells_ready": not cold,
                                  "cells_note": ("HISTORY CELLS NOT LOADED YET (COMPUTING) — they are computed off the page after a restart; every row below reads "
                                                 "UNKNOWN until they land. Reload in a minute." if cold else
                                                 "history cells computed 4 min ago off the page (lane-cells-v1), refreshed about every 10 minutes"),
                                  "summary": {"cells": 8, "measured": sum(1 for r in rows if r["n"] >= 20), "under_floor": sum(1 for r in rows if r["n"] < 20),
                                              "backed_off": sum(1 for r in rows if r["backed_off"]), "v1_positive": cnt("v1", "POSITIVE"), "v1_negative": cnt("v1", "NEGATIVE"),
                                              "v2_positive": cnt("v2", "POSITIVE"), "v2_negative": cnt("v2", "NEGATIVE"), "v2_cannot_separate": cnt("v2", "CANNOT SEPARATE"),
                                              "ticks_withdrawn": sum(1 for r in rows if r["change"] == "TICK WITHDRAWN"), "crosses_withdrawn": sum(1 for r in rows if r["change"] == "CROSS WITHDRAWN")},
                                  "rules": {"v1": "evidence-verdict-v1 — n ≥ 20 and the sign of the mean", "v2": "evidence-verdict-v2 — n ≥ 20 and the 90% interval of the mean excludes zero",
                                            "cell": f"{rule} — each engine's own resolved paper fills, never pooled across engines"},
                                  "not": "a comparison of two WORDS on the same numbers — not of which rule performs better; that needs the outcomes that followed each word, scored out of sample, and nothing has collected them yet",
                                  "authority": "PAPER — a hypothesis generator, never a gate authority; nothing reads this board, and no lane decision, level or gate depends on it"}
        return d

    # platform 5.210 — the three outlook read routes, recorded from a local SignalMesh on seeded candles
    OUTLOOK_FILES = {"GOLD": "gold", "SILVER": "silver", "BTC": "btc", "US100": "us100"}   # DOWN, UP, NO CLEAR TREND, SERIES FAULT

    def market_outlook(self, symbol: str) -> dict:
        """GOLD reads DOWN, SILVER UP, BTC NO CLEAR TREND, US100 a SERIES FAULT (two daily bars on one date); every
        other symbol UNKNOWN for want of daily bars — each exactly as the platform answers it, with a 200."""
        sym = symbol.upper()
        d = self._load(f"market_outlook_{self.OUTLOOK_FILES.get(sym, 'unknown')}")
        if sym not in self.OUTLOOK_FILES:
            d["symbol"] = d["read"]["symbol"] = sym
            if not any(x.get("symbol") == sym for x in d["overview"]):
                d["overview"].append({"symbol": sym, "state": d["read"]["state"], "structure": d["read"]["structure"], "close": None, "bar_ts": None,
                                      "bar_day": None, "reason": d["read"]["reason"], "above": None, "below": None, "wrong": None})
        return d

    def ledger_system(self) -> dict:
        return self._load("ledger_system")

    def turning_points(self) -> dict:
        return self._load("turning_points")

    def signals(self, limit: int = 200) -> list[dict]:
        return self._load("signals")[:limit]

    def trades(self, limit: int = 200, status: str = "") -> list[dict]:
        return [t for t in self._load("trades") if not status or t.get("status") == status][:limit]

    def stats(self) -> dict:
        return self._load("stats")

    def portfolio(self) -> dict:
        return self._load("portfolio")

    def news_state(self, symbols: list[str]) -> dict:
        return self._load("news_state")

    def news_facts(self, symbol: str) -> dict:
        return self._load("news_facts_gold")

    def macro_scorecard(self) -> dict:
        return self._load("macro_scorecard")

    def macro_engine(self) -> dict:
        return self._load("macro_engine")

    def sources_evidence(self) -> dict:
        return self._load("sources_evidence")

    def ea_performance(self) -> dict:
        return self._load("ea_performance")

    def live_candles(self, symbol: str, tf_minutes: str, n: int, session_cookie: str = "") -> dict:
        """A bridge-shaped reply with a forming bar that MOVES with the clock, so the UI's live
        path can be exercised. Fixture: not a market."""
        import math
        import time as _t
        tf = next((k for k, v in TF_MIN.items() if str(v) == str(tf_minutes)), "15m")
        if tf not in self.STORED.get(symbol.upper(), ()):
            return {"feed": "live", "state": "EMPTY", "candles": [], "error": "fixture: nothing for this timeframe"}
        closed = self.candles(symbol, tf, 2)["candles"]
        last = closed[-1]
        step = TF_MIN[tf] * 60
        t0 = int(datetime.fromisoformat(last["ts"]).timestamp()) + step
        o = last["close"]
        wig = abs(o) * 0.0006
        now = _t.time()
        c = o + wig * math.sin(now / 3.0)
        return {"feed": "live", "state": "LIVE", "forming_last": True, "closed_only": False, "age_s": int(now - t0),
                "bid": c, "ask": c + wig * 0.05, "spread": wig * 0.05, "source": "FIXTURE live feed — not a market",
                "candles": [{"time": t0, "open": o, "high": max(o, c) + wig * 0.2, "low": min(o, c) - wig * 0.2, "close": c, "forming": True}]}

    def accounts(self, path: str):
        if not (self.root / "accounts.json").exists():
            raise ProviderError(f"fixture has no {path}", state="ERROR", status=404)
        return self._load("accounts")
