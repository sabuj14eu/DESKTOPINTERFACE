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
        import math
        # Every bar is a DETERMINISTIC function of its own timestamp (not of how many bars were
        # asked for), exactly like a stored series: any request length returns the same bars,
        # and the newest bar's close is the fixture snapshot's last_close.
        k_end = int(end.timestamp()) // (mins * 60)

        def price(k: int) -> float:
            d = k - k_end
            return last + step * (14 * math.sin(d / 40.0) + 4 * math.sin(d / 7.0) + 1.5 * math.sin(d / 2.3))

        rows = []
        for i in range(n, 0, -1):
            ts = end - timedelta(minutes=mins * (i - 1))
            k = k_end - (i - 1)
            o, c = price(k - 1), price(k)
            h = max(o, c) + step * (0.3 + 0.2 * abs(math.sin(k / 3.0)))
            l = min(o, c) - step * (0.3 + 0.2 * abs(math.cos(k / 5.0)))
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

    def desk(self, symbol: str) -> dict:
        d = self._load("desk_gold")
        d["symbol"] = symbol
        return d

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
