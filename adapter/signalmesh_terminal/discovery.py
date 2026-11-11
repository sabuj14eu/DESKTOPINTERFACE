"""INSTRUMENT DISCOVERY — what SignalMesh supports, read from SignalMesh.

Authoritative sources, all read-only and all already in SignalMesh's /api/v1:
  1. the platform's instrument universe, DEFAULT_SYMBOLS in app/models/trading.py,
     reachable as the rows of /api/v1/news/state when no symbol filter is given;
  2. symbols the brain actually signalled, from /api/v1/signals;
  3. the platform's canonical symbol table (app/services/precision.py SYMBOL_DECIMALS,
     mirrored in normalize.py) and its macro symbols (scanner.MACRO_SYMBOLS): every name
     SignalMesh itself knows how to display, probed for stored candles - this is how a
     symbol the MT5 reporter pushes but the brain never signalled still appears;
  4. SMT_SYMBOLS from the terminal's own .env, if set (pins; never adds a symbol
     that SignalMesh has no data for).
Availability is MEASURED, never assumed: /api/v1/market/candles per symbol and
timeframe says whether closed candles are stored (the MT5 reporter pushes only its
BB_CANDLE_TFS). An instrument with no candles on any timeframe is listed as
unavailable and cannot be charted. No instrument is invented here.

A read that FAILED measured nothing: it is not "no candles". The result then says
complete=False with the failed reads listed, and the caller keeps it only for
RETRY_TTL_S instead of the full lifetime; the reads that did answer stay cached, so
the retry asks SignalMesh only for what is missing.

Asset category mirrors SignalMesh's own constants (market_time.CRYPTO_247,
SINGLE_STOCKS, precision.SYMBOL_DECIMALS groups) and is DISPLAY ONLY.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from .normalize import SYMBOL_DECIMALS
from .providers.base import ProviderError

MACRO_SYMBOLS = ("DXY", "US10Y", "VIX")      # app/services/scanner.py MACRO_SYMBOLS
SINGLE_STOCKS = ("NVDA",)                    # app/services/market_time.py SINGLE_STOCKS
# canonical targets of app/routers/webhooks.py SYMBOL_ALIASES not already in the tables above
ALIAS_TARGETS = ("US30Y",)

TFS = ("1m", "5m", "15m", "30m", "1h", "4h", "1d")
FULL_TTL_S = 300.0      # a complete instrument list
RETRY_TTL_S = 15.0      # a list with a failed read in it: asked again after this

# app/services/market_time.py CRYPTO_247 + WEEKEND_247, app/services/precision.py groups
_CRYPTO = ("BTC", "ETH", "XRP", "SOL", "DOGE", "ADA", "LTC", "BNB", "DOT", "LINK")
_METALS = {"GOLD", "SILVER", "XAUUSD", "XAGUSD"}
_INDICES = {"US100", "NAS100", "US30", "US500", "GER40", "DXY", "US10Y", "VIX"}
_ENERGY = {"OIL"}
_STOCKS = {"NVDA"}      # market_time.SINGLE_STOCKS


def category(symbol: str) -> str:
    s = (symbol or "").upper()
    if s in _METALS:
        return "metals"
    if s in _INDICES:
        return "indices"
    if s in _ENERGY:
        return "energy"
    if s in _STOCKS:
        return "stocks"
    if any(s.startswith(c) for c in _CRYPTO):
        return "crypto"
    if len(s) == 6 and s.isalpha():
        return "forex"
    return "other"


def registry(provider, pinned: list[str], failed: list[str] | None = None) -> tuple[list[str], dict[str, list[str]]]:
    """The candidate symbol set and, per symbol, where it came from. A source that
    could not be read is appended to `failed`."""
    origins: dict[str, list[str]] = {}
    failed = [] if failed is None else failed

    def add(sym, origin):
        sym = (sym or "").strip().upper()
        if sym:
            origins.setdefault(sym, [])
            if origin not in origins[sym]:
                origins[sym].append(origin)

    try:
        for r in (provider.news_state([]).get("rows") or []):
            add(r.get("symbol"), "DEFAULT_SYMBOLS (news/state)")
    except ProviderError as exc:
        failed.append(f"news/state: {exc}")
    try:
        for s in provider.signals(200):
            add(s.get("symbol"), "signals")
    except ProviderError as exc:
        failed.append(f"signals: {exc}")
    for s in list(SYMBOL_DECIMALS) + list(MACRO_SYMBOLS) + list(SINGLE_STOCKS) + list(ALIAS_TARGETS):
        add(s, "platform symbol table (precision/macro)")
    for s in pinned:
        add(s, "SMT_SYMBOLS")
    return list(origins), origins


def discover(provider, cache, pinned: list[str], decimals_for, ttl_s: float = FULL_TTL_S) -> dict:
    failed: list[str] = []
    syms, origins = registry(provider, pinned, failed)

    def probe(sym):
        rows = []
        for tf in TFS:
            try:
                # OWN cache key: the header and market watch read "candles:{sym}:1m:2" with a short
                # lifetime; a discovery probe stored under that key would freeze the live price
                c = cache.get_or_compute(f"disc:{sym}:{tf}", lambda tf=tf: provider.candles(sym, tf, 2), ttl_s)
                last = (c.get("candles") or [{}])[-1]
                rows.append({"tf": tf, "stored": bool(c.get("candles")), "last_ts": last.get("ts"),
                             "state": (c.get("freshness") or {}).get("state", "UNKNOWN"),
                             "source": last.get("source") or ""})
            except ProviderError as exc:
                rows.append({"tf": tf, "stored": False, "last_ts": None, "state": exc.state, "source": "", "error": str(exc)})
        stored = [r["tf"] for r in rows if r["stored"]]
        return {"symbol": sym, "category": category(sym), "decimals": decimals_for(sym),
                "available": bool(stored), "timeframes": stored, "coverage": rows,
                "origins": origins[sym], "pinned": sym in pinned}

    with ThreadPoolExecutor(max_workers=8) as ex:
        items = list(ex.map(probe, syms))
    order = {"metals": 0, "indices": 1, "forex": 2, "crypto": 3, "energy": 4, "stocks": 5, "other": 6}
    items.sort(key=lambda i: (not i["available"], not i["pinned"], order.get(i["category"], 9), i["symbol"]))
    failed += [f"{i['symbol']} {r['tf']}: {r['error']}" for i in items for r in i["coverage"] if "error" in r]
    return {"instruments": items, "available": [i["symbol"] for i in items if i["available"]],
            "complete": not failed, "failed_reads": failed,
            "source": ("DEFAULT_SYMBOLS via /api/v1/news/state (no filter) ∪ symbols seen in /api/v1/signals ∪ the platform's own "
                       "symbol table (precision + macro) ∪ SMT_SYMBOLS pins; availability measured per timeframe through "
                       "/api/v1/market/candles; nothing invented")}
