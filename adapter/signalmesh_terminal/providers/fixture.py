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

    def candles(self, symbol: str, tf: str, n: int) -> dict:
        """Synthesises a deterministic closed series around the fixture's
        snapshot price so the chart has something to draw. Labelled."""
        base = self._load("candles_gold_15m")
        snap = self._snapshot_for(symbol)
        last = (snap.get("snapshot", {}).get("market", {}) or {}).get("last_close") or 100.0
        step = max(abs(last) * 0.0008, 1e-5)
        mins = TF_MIN.get(tf, 15)
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        end = now - timedelta(minutes=now.minute % mins) - timedelta(minutes=mins)
        import math
        rows, price = [], last - sum(math.sin(i / 17.0) for i in range(n)) * step
        for i in range(n, 0, -1):
            ts = end - timedelta(minutes=mins * (i - 1))
            o = price
            c = o + math.sin(i / 17.0) * step + (((i * 7919) % 13) - 6) * step * 0.1
            h = max(o, c) + abs(((i * 31) % 7)) * step * 0.1
            l = min(o, c) - abs(((i * 17) % 5)) * step * 0.1
            rows.append({"ts": ts.isoformat(), "open": o, "high": h, "low": l, "close": c,
                         "tick_volume": float(((i * 97) % 800) + 50), "spread": step * 0.3,
                         "source": "FIXTURE — not a market"})
            price = c
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

    def trades(self, limit: int = 200) -> list[dict]:
        return self._load("trades")[:limit]

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
