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

from . import __version__, accounts as acct
from .brokers.base import GATES, ExecutionRefused, PlanForTicket
from .brokers.ctrader import CTraderBroker
from .brokers.manual import ManualBroker
from .brokers.mt5 import MT5Broker
from .cache import TTLCache
from .config import get_settings
from .contract import jsonable
from .discovery import discover
from .normalize import (candle_series, decimals_for, decision_view, market_watch_row, signal_ref, source_kind, trade_row)
from .providers.base import ProviderError
from .providers.fixture import FixtureProvider
from .providers.signalmesh import SignalMeshProvider
from .transparency import signal_detail

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


def _signals_raw():
    return _cached("signals", lambda: provider().signals(200))


def _signals():
    s = get_settings()
    return [signal_ref(x, s.signal_ttl_h) for x in _signals_raw()]


def _trades_raw():
    return _cached("trades", lambda: provider().trades(200))


def _trades_status(status: str):
    """Every journal row in ONE status, asked for by status: the newest-200 list is ordered by
    open time, so an old position that is still open could fall off it."""
    return _cached(f"trades:{status}", lambda: provider().trades(200, status))


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


def _discovered() -> dict:
    s = get_settings()
    return _cached("discovery", lambda: discover(provider(), cache(), s.symbol_list, decimals_for), ttl=300)


def watch_symbols() -> list[str]:
    """What the Market Watch lists: every AVAILABLE discovered instrument; SMT_SYMBOLS, when
    set, restricts the list to those (and only those with data)."""
    d = _discovered()
    s = get_settings()
    avail = d["available"]
    if s.symbol_list:
        return [x for x in s.symbol_list if x in avail]
    return avail


@router.get("/instruments")
def instruments():
    s = get_settings()
    d = _discovered()
    return {"as_of": _now(), "watch": watch_symbols(), "pinned": s.symbol_list, "source": d["source"],
            "instruments": d["instruments"]}


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
            # the list refreshes the engine's verdict once a minute; the selected symbol's own
            # /decision carries the fresh one
            sn = _cached(f"snapshot:{sym}", lambda: p.snapshot(sym), ttl=60)
        except ProviderError as exc:
            err = (err + " · " if err else "") + f"snapshot: {exc}"
        return market_watch_row(sym, c, sn, dk, err)

    try:
        syms = watch_symbols()
    except ProviderError as exc:
        raise _err(exc)
    with ThreadPoolExecutor(max_workers=4) as ex:
        rows = list(ex.map(one, syms))
    try:
        portfolio = _cached("portfolio", lambda: p.portfolio())
    except ProviderError as exc:
        portfolio = {"error": str(exc)}
    cats = {i["symbol"]: i["category"] for i in _discovered()["instruments"]}
    out_rows = jsonable(rows)
    for r in out_rows:
        r["category"] = cats.get(r["symbol"], "other")
    return {"as_of": _now(), "provider": p.name, "is_fixture": p.is_fixture, "rows": out_rows, "portfolio": portfolio,
            "price_rule": "price-contract-v1: last CLOSED 1m bar close, with its bar span and age since close — SignalMesh stores no bid/ask/tick",
            "source_rule": "provenance = the per-candle `source` field (authority); SignalMesh's static price_source line is a label only",
            "instrument_rule": "Every instrument SignalMesh stores is drawable; the list and the venue are SignalMesh's, the terminal adds none of its own."}


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
    inst = next((i for i in _discovered()["instruments"] if i["symbol"] == sym), None)
    if inst is not None:
        rows = inst["coverage"]
    else:
        def one(tf):
            try:
                c = _cached(f"cov:{sym}:{tf}", lambda: p.candles(sym, tf, 2), ttl=120)
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
    rows = _news_rows([sym])
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
            "kind": "SIGNALMESH RECOMMENDATIONS — not broker orders. A signal is an execution only when a broker journal row names its signal_id.",
            "rows": jsonable(rows)}


@router.get("/signals/{signal_id}")
def signal_one(signal_id: str):
    """Everything SignalMesh says about ONE signal: origin, validation, invalidation, and
    how far it really got (generated / approved / submitted / filled / closed)."""
    try:
        raws = _signals_raw()
    except ProviderError as exc:
        raise _err(exc)
    raw = next((x for x in raws if str(x.get("signal_id")) == signal_id), None)
    if raw is None:
        raise HTTPException(404, f"signal {signal_id} is not among the newest {len(raws)} signals SignalMesh returns")
    try:
        trades = _trades_raw()
        trades_note = ""
    except ProviderError as exc:
        trades, trades_note = [], f"trade journal unavailable: {exc}"
    ttl = get_settings().signal_ttl_h
    out = signal_detail(signal_ref(raw, ttl), raw, trades, ttl)
    out["as_of"] = _now()
    out["execution"]["adapters"] = [b.describe() for b in BROKERS.values()]
    if trades_note:
        out["execution"]["link_note"] = trades_note
    return jsonable(out)


@router.get("/trades")
def trades(status: str = "all"):
    try:
        raw = _trades_raw()
    except ProviderError as exc:
        raise _err(exc)
    rows = [trade_row(t) for t in raw]
    st = status.lower()
    if st == "open":
        rows = [r for r in rows if r.status in ("open", "pending")]
    elif st == "closed":
        rows = [r for r in rows if r.status in ("closed", "cancelled")]
    return {"as_of": _now(), "source": "SignalMesh trade journal (reporter heartbeats, MT5 truth)",
            "kind": "BROKER TRADES — what the MT5 reporter saw on the account. Not SignalMesh recommendations.",
            "scope": "every reporting account together (the journal's own scope); per-account rows are under Account Information",
            "rows": jsonable(rows)}


# ------------------------------------------------------------------ broker accounts
def _reporter_logins() -> list[str]:
    """Account numbers the reporter stamps on candles (`mt5:<login>`), from what is already cached
    for the market watch. Used only to NAME a single account; never to split a total."""
    out = []
    try:
        for sym in watch_symbols()[:3]:
            c = _cached(f"candles:{sym}:1m:2", lambda sym=sym: provider().candles(sym, "1m", 2))
            for k in c.get("candles") or []:
                src = str(k.get("source") or "")
                if src.lower().startswith("mt5:") and src[4:].strip() and src[4:].strip() not in out:
                    out.append(src[4:].strip())
    except ProviderError:
        pass
    return out


def _accounts() -> dict:
    def fn():
        try:
            pf = _cached("portfolio", lambda: provider().portfolio())
        except ProviderError as exc:
            pf = {"error": str(exc)}
        d = acct.build(provider(), get_settings().accounts_path, pf, _reporter_logins())
        d["read_at"] = _now()
        if pf.get("error"):
            d["note"] += f" · portfolio: {pf['error']}"
        return d
    return _cached("accounts", fn)


def _public(d: dict) -> dict:
    return {k: v for k, v in d.items() if not k.startswith("_")}


@router.get("/accounts")
def accounts():
    """Broker accounts that are genuinely connected (reporting heartbeats). Selectable one at
    a time; the terminal never adds two accounts together."""
    d = _accounts()
    out = jsonable(_public(d))
    out["as_of"] = _now()
    out["default"] = d["accounts"][0].id if d["accounts"] else None
    return out


def _position_row(r: dict, kind: str) -> dict:
    """A reporter position / pending-order row, verbatim under the terminal's column names."""
    g = lambda *ks: next((r[k] for k in ks if r.get(k) not in (None, "")), None)  # noqa: E731
    return {"ticket": g("ticket", "position_id", "order_id", "id"), "symbol": g("symbol"),
            "direction": str(g("direction", "side", "type") or "").upper() or None, "order_type": g("order_type") if kind == "order" else None,
            "lots": g("lots", "volume"), "entry": g("entry", "price_open", "price"), "sl": g("sl"), "tp": g("tp"),
            "profit": g("profit") if kind == "position" else None, "time": g("open_time", "placed_time", "time_setup", "time"),
            "signal_id": g("signal_id", "comment") if g("signal_id") else None}


def _journal_row(t: dict, kind: str) -> dict:
    return {"ticket": t.get("ticket") or t.get("id"), "symbol": t.get("symbol"), "direction": str(t.get("direction") or "").upper() or None,
            "order_type": None, "lots": t.get("lots"), "entry": t.get("entry"), "sl": t.get("sl"), "tp": t.get("tp"),
            "profit": t.get("profit") if kind == "position" else None, "time": t.get("open_time"), "signal_id": t.get("signal_id")}


@router.get("/account")
def account(id: str = ""):
    """ONE account: the broker's own figures, its open positions, pending orders and closed
    trades. Rows of another account are never included."""
    d = _accounts()
    every = d["accounts"] + d["disconnected"]
    a = next((x for x in every if x.id == id), None) if id else (d["accounts"][0] if d["accounts"] else None)
    if a is None:
        if id:
            raise HTTPException(404, "no such account (it may have disconnected)")
        return {"as_of": _now(), "account": None, "mode": d["mode"], "note": d["note"], "rule": d["rule"],
                "positions": [], "orders": [], "closed": [], "disconnected": jsonable(d["disconnected"])}
    try:
        seen, trades = set(), []
        for t in _trades_status("open") + _trades_status("pending") + _trades_raw():
            if t.get("id") not in seen:
                seen.add(t.get("id"))
                trades.append(t)
        jerr = ""
    except ProviderError as exc:
        trades, jerr = [], str(exc)
    mine, attribution = acct.journal_for(a, d["_logins"].get(a.id, ""), d["_total"], trades)
    emb = d["_embedded"].get(a.id) or {}
    if isinstance(emb.get("positions"), list):
        positions, psrc = [_position_row(r, "position") for r in emb["positions"] if isinstance(r, dict)], "account row · positions (reporter heartbeat)"
    else:
        positions, psrc = [_journal_row(t, "position") for t in mine if str(t.get("status")) == "open"], "SignalMesh trade journal, status open · " + attribution
    if isinstance(emb.get("orders"), list):
        orders, osrc = [_position_row(r, "order") for r in emb["orders"] if isinstance(r, dict)], "account row · orders (reporter heartbeat)"
    else:
        orders, osrc = [_journal_row(t, "order") for t in mine if str(t.get("status")) == "pending"], "SignalMesh trade journal, status pending · " + attribution
    closed = [trade_row(t) for t in mine if str(t.get("status")) in ("closed", "cancelled")]
    return jsonable({"as_of": _now(), "read_at": d["read_at"], "mode": d["mode"], "note": d["note"], "rule": d["rule"], "account": a,
                     "positions": positions, "positions_source": psrc, "orders": orders, "orders_source": osrc,
                     "closed": closed, "closed_source": "SignalMesh trade journal, status closed/cancelled · " + attribution,
                     "counts": {"positions": len(positions), "orders": len(orders), "closed": len(closed)},
                     "journal_error": jerr, "kind": "BROKER ACCOUNT — broker-reported values. Not SignalMesh calculations, not recommendations."})


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
    syms = watch_symbols()
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
    for sym in watch_symbols():
        for tf in TFS:
            try:
                c = _cached(f"src:{sym}:{tf}", lambda: p.candles(sym, tf, 2), ttl=60)
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
            "gates": [{"gate": g, "state": "NOT BUILT"} for g in GATES],
            "architecture": "one SignalMesh signal -> one broker-neutral OrderIntent -> MT5 or cTrader adapter translate(); place() refuses in every adapter",
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
