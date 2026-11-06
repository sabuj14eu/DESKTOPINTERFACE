"""/api/terminal/* — the read-only terminal contract.

Every GET here = one or more GETs to SignalMesh (cached) + a reshape.
Two POSTs exist and neither reaches a broker:
  /execution/ticket  — Mode A manual order text, built from a READY plan
  /execution/place   — ALWAYS 403 in this phase
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from . import __version__
from .brokers.base import ExecutionRefused, PlanForTicket
from .brokers.ctrader import CTraderBroker
from .brokers.manual import ManualBroker
from .brokers.mt5 import MT5Broker
from .cache import TTLCache
from .config import get_settings
from .contract import jsonable
from .normalize import (candle_series, decimals_for, decision_view, market_watch_row, signal_ref, source_kind, trade_row)
from .providers.base import ProviderError
from .providers.fixture import FixtureProvider
from .providers.signalmesh import SignalMeshProvider

router = APIRouter(prefix="/api/terminal", tags=["terminal"])
TFS = ("1m", "5m", "15m", "30m", "1h", "4h", "1d")
BROKERS = {b.mode: b for b in (ManualBroker(), MT5Broker(), CTraderBroker())}

_provider = None
_cache: TTLCache | None = None


def provider():
    global _provider, _cache
    if _provider is None:
        s = get_settings()
        if s.provider == "fixture":
            _provider = FixtureProvider()
        elif s.provider == "signalmesh":
            _provider = SignalMeshProvider(s.signalmesh_url, s.signalmesh_api_key, s.signalmesh_timeout_s)
        else:
            raise RuntimeError(f"unknown SMT_PROVIDER {s.provider!r} (signalmesh | fixture)")
        _cache = TTLCache(s.cache_ttl_s)
    return _provider


def cache() -> TTLCache:
    provider()
    assert _cache is not None
    return _cache


def reset_for_tests():
    global _provider, _cache
    _provider, _cache = None, None
    get_settings.cache_clear()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _err(exc: ProviderError) -> HTTPException:
    return HTTPException(status_code=503 if exc.state in ("DOWN", "NOT_CONFIGURED") else 502,
                         detail={"state": exc.state, "error": str(exc)})


def _cached(key: str, fn, ttl=None):
    return cache().get_or_compute(key, fn, ttl)


def _signals():
    s = get_settings()
    raw = _cached("signals", lambda: provider().signals(200))
    return [signal_ref(x, s.signal_ttl_h) for x in raw]


def _snapshot(symbol):
    return _cached(f"snapshot:{symbol}", lambda: provider().snapshot(symbol))


def _desk(symbol):
    return _cached(f"desk:{symbol}", lambda: provider().desk(symbol))


def _news_rows(symbols):
    def fn():
        try:
            d = provider().news_state(symbols)
        except ProviderError as exc:
            return {"error": str(exc), "rows": []}
        return d
    return _cached("news_state:" + ",".join(symbols), fn)


# ------------------------------------------------------------------ health
@router.get("/health")
def health():
    s = get_settings()
    p = provider()
    up = p.readiness()
    return {"adapter": {"version": __version__, "as_of": _now(), "env": s.env, "poll_s": s.poll_s,
                        "cache": cache().stats(), "auth": s.auth if s.auth in ("signalmesh", "token", "open") else "open",
                        "login_url": s.login_path},
            "provider": {"name": p.name, "is_fixture": p.is_fixture, "configured": getattr(p, "configured", True),
                         "url": s.signalmesh_url if p.name == "signalmesh" else None},
            "upstream": up,
            "execution": {"enabled": s.execution_enabled, "phase": s.execution_phase,
                          "can_place": False, "modes": [b.describe() for b in BROKERS.values()]},
            "symbols": s.symbol_list, "default_symbol": s.default_symbol, "timeframes": list(TFS)}


@router.get("/instruments")
def instruments():
    s = get_settings()
    known = list(s.symbol_list)
    try:
        for sig in _signals():
            if sig.symbol and sig.symbol not in known:
                known.append(sig.symbol)
    except ProviderError:
        pass
    return {"as_of": _now(), "watch": s.symbol_list,
            "instruments": [{"symbol": x, "decimals": decimals_for(x), "in_watch": x in s.symbol_list} for x in known]}


# ------------------------------------------------------------------ market
@router.get("/market-watch")
def market_watch():
    s = get_settings()
    p = provider()

    def one(sym):
        err = ""
        c = sn = dk = None
        try:
            c = _cached(f"candles:{sym}:1m:2", lambda: p.candles(sym, "1m", 2))
        except ProviderError as exc:
            err = f"candles: {exc}"
        try:
            sn = _snapshot(sym)
        except ProviderError as exc:
            err = (err + " · " if err else "") + f"snapshot: {exc}"
        try:
            dk = _desk(sym)
        except ProviderError as exc:
            err = (err + " · " if err else "") + f"desk: {exc}"
        return market_watch_row(sym, c, sn, dk, err)

    with ThreadPoolExecutor(max_workers=4) as ex:
        rows = list(ex.map(one, s.symbol_list))
    try:
        portfolio = _cached("portfolio", lambda: p.portfolio())
    except ProviderError as exc:
        portfolio = {"error": str(exc)}
    return {"as_of": _now(), "provider": p.name, "is_fixture": p.is_fixture, "rows": jsonable(rows), "portfolio": portfolio,
            "price_rule": "price-contract-v1: last CLOSED 1m bar close, with its bar span and age since close — SignalMesh stores no bid/ask/tick",
            "source_rule": "provenance = the per-candle `source` field (authority); SignalMesh's static price_source line is a label only"}


@router.get("/candles")
def candles(symbol: str, tf: str = "15m", n: int = Query(300, ge=10, le=1000)):
    sym, tf = symbol.strip().upper(), tf.strip().lower()
    if tf not in TFS:
        raise HTTPException(400, f"tf must be one of {', '.join(TFS)}")
    try:
        raw = _cached(f"candles:{sym}:{tf}:{n}", lambda: provider().candles(sym, tf, n))
    except ProviderError as exc:
        raise _err(exc)
    return jsonable(candle_series(provider().name, sym, tf, raw))


@router.get("/coverage")
def coverage(symbol: str):
    """Which timeframes SignalMesh actually stores for one symbol (newest closed bar per tf).
    The MT5 reporter pushes only the timeframes in its BB_CANDLE_TFS; the terminal can draw
    those and no others. Cached 120 s."""
    sym = symbol.strip().upper()
    p = provider()

    def one(tf):
        try:
            c = _cached(f"candles:{sym}:{tf}:2", lambda: p.candles(sym, tf, 2), ttl=120)
            last = (c.get("candles") or [{}])[-1]
            return {"tf": tf, "stored": bool(c.get("candles")), "last_ts": last.get("ts"),
                    "state": (c.get("freshness") or {}).get("state", "UNKNOWN")}
        except ProviderError as exc:
            return {"tf": tf, "stored": False, "last_ts": None, "state": exc.state, "error": str(exc)}

    with ThreadPoolExecutor(max_workers=4) as ex:
        rows = list(ex.map(one, TFS))
    return {"as_of": _now(), "symbol": sym, "timeframes": rows,
            "note": "SignalMesh stores only the timeframes the MT5 reporter pushes (its BB_CANDLE_TFS setting, default 15m,1h,4h,1d). Nothing is interpolated."}


@router.get("/decision")
def decision(symbol: str):
    sym = symbol.strip().upper()
    try:
        snap = _snapshot(sym)
        sigs = _signals()
    except ProviderError as exc:
        raise _err(exc)
    try:
        desk = _desk(sym)
    except ProviderError:
        desk = None
    rows = _news_rows(get_settings().symbol_list if sym in get_settings().symbol_list else [sym])
    row = next((r for r in rows.get("rows") or [] if r.get("symbol") == sym), None)
    try:
        c1 = _cached(f"candles:{sym}:1m:2", lambda: provider().candles(sym, "1m", 2))
    except ProviderError:
        c1 = None
    return jsonable(decision_view(provider().name, sym, snap, sigs, desk, row, c1))


# ------------------------------------------------------------------ records
@router.get("/signals")
def signals(bucket: str = "all", symbol: str = ""):
    try:
        rows = _signals()
    except ProviderError as exc:
        raise _err(exc)
    if symbol.strip():
        rows = [r for r in rows if r.symbol == symbol.strip().upper()]
    b = bucket.upper()
    if b == "ACTIVE":
        rows = [r for r in rows if r.bucket == "ACTIVE"]
    elif b == "PENDING":
        rows = [r for r in rows if r.bucket == "PENDING"]
    elif b == "HISTORY":
        rows = [r for r in rows if r.bucket in ("EXPIRED", "REJECTED", "OTHER")]
    return {"as_of": _now(), "bucket": b, "ttl_h": get_settings().signal_ttl_h,
            "rule": "ACTIVE = approved/executed within 12h · PENDING = pending within 12h · EXPIRED past 12h (planner.SIGNAL_FRESH_H) · REJECTED = brain rejected",
            "rows": jsonable(rows)}


@router.get("/trades")
def trades(status: str = "all"):
    try:
        raw = _cached("trades", lambda: provider().trades(200))
    except ProviderError as exc:
        raise _err(exc)
    rows = [trade_row(t) for t in raw]
    st = status.lower()
    if st == "open":
        rows = [r for r in rows if r.status in ("open", "pending")]
    elif st == "closed":
        rows = [r for r in rows if r.status in ("closed", "cancelled")]
    return {"as_of": _now(), "source": "SignalMesh trade journal (reporter heartbeats, MT5 truth)", "rows": jsonable(rows)}


@router.get("/performance")
def performance():
    try:
        stats = _cached("stats", lambda: provider().stats())
        portfolio = _cached("portfolio", lambda: provider().portfolio())
    except ProviderError as exc:
        raise _err(exc)
    ea = {}
    try:
        ea = _cached("ea_perf", lambda: provider().ea_performance())
    except ProviderError as exc:
        ea = {"error": str(exc)}
    return {"as_of": _now(), "stats": stats, "portfolio": portfolio, "ea_performance": ea,
            "evidence_law": "n<20 = luck, ~100 to judge (SignalMesh Evidence Law) — stats.low_sample says so"}


@router.get("/news")
def news(symbol: str = ""):
    s = get_settings()
    syms = s.symbol_list
    out = {"as_of": _now(), "state": _news_rows(syms)}
    sym = symbol.strip().upper() or s.default_symbol
    try:
        out["facts"] = _cached(f"news_facts:{sym}", lambda: provider().news_facts(sym))
    except ProviderError as exc:
        out["facts"] = {"error": str(exc)}
    try:
        sc = _cached("macro_scorecard", lambda: provider().macro_scorecard(), ttl=120)
        out["macro"] = {k: sc.get(k) for k in ("rule", "as_of", "calendar", "usd_rows", "coverage", "direction_rule", "authority") if k in sc}
    except ProviderError as exc:
        out["macro"] = {"error": str(exc)}
    try:
        out["events_next_12h"] = ((_snapshot(sym).get("snapshot") or {}).get("news") or {}).get("events_next_12h") or []
    except ProviderError:
        out["events_next_12h"] = []
    return out


@router.get("/sources")
def sources():
    s = get_settings()
    p = provider()
    out = {"as_of": _now(), "provider": {"name": p.name, "is_fixture": p.is_fixture}, "feeds": [], "evidence": {}}
    for sym in s.symbol_list:
        for tf in ("1m", "15m", "1h", "1d"):
            try:
                c = _cached(f"candles:{sym}:{tf}:2", lambda: p.candles(sym, tf, 2))
                last = (c.get("candles") or [{}])[-1]
                out["feeds"].append({"symbol": sym, "tf": tf, "state": (c.get("freshness") or {}).get("state", "UNKNOWN"),
                                     "age_min": (c.get("freshness") or {}).get("age_min"), "limit_min": (c.get("freshness") or {}).get("limit_min"),
                                     "newest_bar": (c.get("freshness") or {}).get("newest_bar"), "last_ts": last.get("ts"),
                                     "source": last.get("source") or "", "source_kind": source_kind(last.get("source"))[0],
                                     "source_warning": source_kind(last.get("source"))[1],
                                     "platform_label": c.get("price_source"), "count_known": c.get("count")})
            except ProviderError as exc:
                out["feeds"].append({"symbol": sym, "tf": tf, "state": exc.state, "error": str(exc)})
    try:
        out["evidence"] = _cached("sources_evidence", lambda: p.sources_evidence(), ttl=120)
    except ProviderError as exc:
        out["evidence"] = {"error": str(exc)}
    kinds = {f.get("source_kind") for f in out["feeds"] if f.get("source_kind")}
    out["source_rule"] = "provenance = the per-candle `source` field (authority); the platform_label is SignalMesh's static price_source line"
    out["verdict"] = ("ALL MT5 REPORTER" if kinds == {"mt5_reporter"} else
                      "NO FEEDS" if not kinds else f"NOT ALL BROKER DATA — kinds seen: {', '.join(sorted(kinds))}")
    return out


@router.get("/system")
def system():
    s = get_settings()
    p = provider()
    out = {"as_of": _now(), "adapter": {"version": __version__, "env": s.env, "provider": p.name, "is_fixture": p.is_fixture,
                                          "cache": cache().stats(), "poll_s": s.poll_s, "signalmesh_url": s.signalmesh_url if p.name == "signalmesh" else None},
           "upstream": p.readiness(), "execution": {"enabled": s.execution_enabled, "phase": s.execution_phase, "can_place": False}}
    try:
        out["portfolio"] = _cached("portfolio", lambda: p.portfolio())
    except ProviderError as exc:
        out["portfolio"] = {"error": str(exc)}
    try:
        me = _cached("macro_engine", lambda: p.macro_engine(), ttl=60)
        # scalar summary only — the full engine context is tens of KB
        out["macro_engine"] = {k: v for k, v in me.items() if not isinstance(v, (dict, list))}
        out["macro_engine"]["sections"] = sorted(k for k, v in me.items() if isinstance(v, (dict, list)))
    except ProviderError as exc:
        out["macro_engine"] = {"error": str(exc)}
    return out


# ------------------------------------------------------------------ execution (dark)
@router.get("/execution/modes")
def execution_modes():
    s = get_settings()
    return {"as_of": _now(), "enabled": s.execution_enabled, "phase": s.execution_phase, "can_place": False,
            "modes": [b.describe() for b in BROKERS.values()],
            "rules": ["explicit user approval per order", "duplicate-order protection on signal_id",
                      "position reconciliation before placing", "SignalMesh risk checks", "no automatic trading"]}


class TicketRequest(BaseModel):
    symbol: str
    mode: str = "MANUAL"


@router.post("/execution/ticket")
def execution_ticket(req: TicketRequest):
    sym = req.symbol.strip().upper()
    broker = BROKERS.get(req.mode.upper())
    if broker is None:
        raise HTTPException(400, f"unknown mode {req.mode}")
    try:
        snap = _snapshot(sym)
        sigs = _signals()
    except ProviderError as exc:
        raise _err(exc)
    dv = decision_view(provider().name, sym, snap, sigs)
    plan = PlanForTicket(symbol=sym, direction=(dv.order_type or "").split()[0] if dv.order_type else "",
                         order_type=dv.order_type or "", entry=dv.entry or 0.0, sl=dv.sl or 0.0, tp1=dv.tp1, tp2=dv.tp2,
                         rr1=dv.rr1, signal_id=dv.signal.signal_id if dv.signal else "", engine_status=dv.engine_status)
    try:
        return broker.ticket(plan, dv.decimals)
    except ExecutionRefused as exc:
        raise HTTPException(403, str(exc))


class PlaceRequest(BaseModel):
    symbol: str
    mode: str
    approval: str = ""


@router.post("/execution/place")
def execution_place(req: PlaceRequest):
    broker = BROKERS.get(req.mode.upper())
    if broker is None:
        raise HTTPException(400, f"unknown mode {req.mode}")
    plan = PlanForTicket(symbol=req.symbol.upper(), direction="", order_type="", entry=0.0, sl=0.0, tp1=None, tp2=None,
                         rr1=None, signal_id="", engine_status="")
    try:
        broker.place(plan, req.approval)
    except ExecutionRefused as exc:
        raise HTTPException(403, str(exc))
    raise HTTPException(403, "execution is disabled in this phase")   # unreachable by design
