"""/api/terminal/* — the read-only terminal contract.

Every GET here = one or more GETs to SignalMesh (cached) + a reshape.
Two POSTs exist and neither reaches a broker:
  /execution/ticket  — Mode A manual order text, built from a READY plan
  /execution/place   — ALWAYS 403 in this phase
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from . import __version__, accounts as acct
from . import build as build_info
from . import forecast as fc
from . import journal as fj
from . import live as live_bar
from . import recorder as rec
from . import smc as smc_study
from .brokers.base import GATES, ExecutionRefused, PlanForTicket
from .brokers.ctrader import CTraderBroker
from .brokers.manual import ManualBroker
from .brokers.mt5 import MT5Broker
from .cache import TTLCache
from .config import get_settings
from .contract import jsonable
from .discovery import FULL_TTL_S, RETRY_TTL_S, discover
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
_journal: fj.Journal | None = None
_recorder: rec.Recorder | None = None


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
    global _provider, _cache, _journal, _recorder
    if _recorder is not None:
        _recorder.stop()
    if _journal is not None:
        _journal.close()
    _provider, _cache, _journal, _recorder = None, None, None, None
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
            "build": build_info.identity(s.env, p.is_fixture),
            "provider": {"name": p.name, "is_fixture": p.is_fixture, "configured": getattr(p, "configured", True),
                         "url": s.signalmesh_url if p.name == "signalmesh" else None},
            "upstream": up,
            "execution": {"enabled": s.execution_enabled, "phase": s.execution_phase,
                          "can_place": False, "modes": [b.describe() for b in BROKERS.values()]},
            "symbols": s.symbol_list, "default_symbol": s.default_symbol, "timeframes": list(TFS)}


@router.get("/version")
def version():
    """Which terminal is running — from the build itself — and its release history."""
    s = get_settings()
    return {"as_of": _now(), "build": build_info.identity(s.env, provider().is_fixture), "releases": build_info.releases(),
            "rule": "version = the VERSION file (tied to docs/RELEASES.md by a test); commit, build number and build time are computed "
                    "from the git checkout when the image is built; started_at is this process's start = the last deployment"}


def _discovered() -> dict:
    s = get_settings()
    # a list with a failed read in it is kept only briefly: a failed read is not "no candles"
    return cache().get_or_compute("discovery", lambda: discover(provider(), cache(), s.symbol_list, decimals_for),
                                  ttl_for=lambda d: FULL_TTL_S if d["complete"] else RETRY_TTL_S)


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
            "complete": d["complete"], "failed_reads": d["failed_reads"], "instruments": d["instruments"]}


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


@router.get("/live")
def live(request: Request, symbol: str, tf: str = "15m"):
    """THE FORMING BAR (display only): the bar after the newest stored closed bar, from the
    SignalMesh live bridge when it is LIVE, else built from stored closed 1m bars. Polled every
    couple of seconds by the chart; one upstream read is shared for 1.5 s."""
    sym, tf = symbol.strip().upper(), tf.strip().lower()
    if tf not in TFS:
        raise HTTPException(400, f"tf must be one of {', '.join(TFS)}")
    p = provider()
    cookie = request.cookies.get("bb_session", "")

    def fn():
        try:
            closed = _cached(f"live:closed:{sym}:{tf}", lambda: p.candles(sym, tf, 2), ttl=5)
        except ProviderError as exc:
            return live_bar._empty(sym, tf, exc.state, "none", f"closed candles: {exc}")
        last = (closed.get("candles") or [{}])[-1].get("ts")
        last_closed = live_bar._epoch(last)
        try:
            out = live_bar.from_bridge(sym, tf, p.live_candles(sym, live_bar.BRIDGE_TF[tf], 3, cookie), last_closed)
        except ProviderError as exc:
            out = live_bar._empty(sym, tf, exc.state, "bridge", str(exc))
        if out["state"] == "LIVE":
            return out
        why = f"live bridge {out['state']}" + (f" ({out['error']})" if out.get("error") else "")
        c1 = None
        if tf not in ("1m", "1d"):
            try:
                c1 = _cached(f"live:1m:{sym}", lambda: p.candles(sym, "1m", 250), ttl=10)
            except ProviderError:
                c1 = None
        alt = live_bar.from_1m(sym, tf, c1, last_closed, why)
        alt["bridge_state"] = out["state"]
        return alt
    out = dict(_cached(f"live:{sym}:{tf}:{'s' if cookie else 'n'}", fn, ttl=1.5))
    out["decimals"] = decimals_for(sym, (out["bars"][-1]["close"] if out["bars"] else None))
    return out


def _smc_bars(sym: str, tf: str) -> tuple[list[dict], str]:
    """Closed bars of one ANALYSIS timeframe. A week is the closed ISO weeks built from closed daily bars."""
    p = provider()
    if tf == "1w":
        raw = _cached(f"candles:{sym}:1d:1000", lambda: p.candles(sym, "1d", 1000), ttl=300)
        bars = smc_study.weekly_from_daily(smc_study.bars_from(raw))
        return bars, "closed ISO weeks aggregated from SignalMesh's closed 1d bars"
    raw = _cached(f"candles:{sym}:{tf}:500", lambda: p.candles(sym, tf, 500))
    last = (raw.get("candles") or [{}])[-1]
    return smc_study.bars_from(raw), f"SignalMesh closed {tf} bars · per-candle source {last.get('source') or 'unstated'}"


@router.get("/smc")
def smc(symbol: str, tf: str = "15m"):
    """SMART MONEY CONCEPTS — the terminal's own display-only studies of one timeframe's closed
    bars (smc-v1). Never an engine input; see smc.py for the method and its no-lookahead rules."""
    sym, tf = symbol.strip().upper(), tf.strip().lower()
    if tf not in smc_study.ANALYSIS_TFS:
        raise HTTPException(400, f"tf must be one of {', '.join(smc_study.ANALYSIS_TFS)}")
    try:
        bars, source = _smc_bars(sym, tf)
    except ProviderError as exc:
        raise _err(exc)
    key = f"smc:{sym}:{tf}:{bars[-1]['t'] if bars else 0}:{len(bars)}"
    out = dict(_cached(key, lambda: smc_study.analyse(sym, tf, bars, source), ttl=600))     # changes only when a bar closes
    out["decimals"] = decimals_for(sym, bars[-1]["c"] if bars else None)
    return out


@router.get("/smc/key-levels")
def smc_key_levels(symbol: str):
    """Previous day / week / session highs and lows with their swept state — closed 1d and 1h bars only."""
    sym = symbol.strip().upper()
    p = provider()
    try:
        daily = smc_study.bars_from(_cached(f"candles:{sym}:1d:60", lambda: p.candles(sym, "1d", 60), ttl=300))
        hourly = smc_study.bars_from(_cached(f"candles:{sym}:1h:400", lambda: p.candles(sym, "1h", 400), ttl=60))
    except ProviderError as exc:
        raise _err(exc)
    return {"symbol": sym, "as_of": _now(), "rule": smc_study.RULE, "levels": smc_study.key_levels(daily, hourly),
            "source": "SignalMesh closed 1d bars (day, week) and closed 1h bars (sessions, swept state)",
            "note": "" if daily and hourly else "closed 1d and 1h bars are both needed; a missing one means no level, not a guessed one"}


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


# ------------------------------------------------------------------ forecast journal (the terminal's own store)
def journal() -> fj.Journal | None:
    """The terminal's own SQLite file (SMT_JOURNAL_PATH). None when no path is configured."""
    global _journal
    if _journal is None and get_settings().journal_path:
        _journal = fj.Journal(get_settings().journal_path)
    return _journal


def _journal_bars(sym: str, tf: str) -> list[dict]:
    """Closed bars for the recorder and the forecasting studies. One upstream read a minute per series
    at most (a closed bar does not change), shared by the recorder, the ranking and the chart study."""
    if tf == "1w":
        return _smc_bars(sym, tf)[0]
    p = provider()
    if tf == "1d":
        return smc_study.bars_from(_cached(f"candles:{sym}:1d:1000", lambda: p.candles(sym, "1d", 1000), ttl=300))
    return smc_study.bars_from(_cached(f"fc:{sym}:{tf}", lambda: p.candles(sym, tf, 500), ttl=55))


def _stored_tfs(sym: str) -> list[str]:
    return next((i.get("timeframes") or [] for i in _discovered()["instruments"] if i["symbol"] == sym), [])


def _daily_forecast(sym: str) -> dict:
    """daily-forecast-v1 for one instrument, from closed 1d + closed 15m (else 1h) bars, 4h for the snap."""
    def fn():
        import time as _t
        tfs = _stored_tfs(sym)
        itf = next((t for t in ("15m", "1h") if t in tfs), None)
        if "1d" not in tfs or itf is None:
            return {"symbol": sym, "state": "NOT_AVAILABLE", "note": f"SignalMesh stores no {'daily' if '1d' not in tfs else '15m / 1h'} bars for {sym}",
                    "method_version": fc.DAILY_VERSION, "methodology": fc.METHODOLOGY, "scenarios": [], "history": [], "outlooks": {}, "confidence": "UNKNOWN"}
        now = _t.time()
        daily = rec.closed_only(_journal_bars(sym, "1d"), "1d", now)
        intra = rec.closed_only(_journal_bars(sym, itf), itf, now)
        h4 = rec.closed_only(_journal_bars(sym, "4h"), "4h", now) if "4h" in tfs else []
        return fc.daily_forecast(sym, daily, intra, itf, h4)
    return _cached(f"fcd:{sym}", fn, ttl=30)


@router.get("/forecast/daily")
def forecast_daily(symbol: str):
    """DAILY FORECAST TOP / BOTTOM (daily-forecast-v1) — the terminal's own display-only study, ported from
    Shyam's Pine script (ADR projection). Closed bars only. Never an engine input; places no order."""
    sym = symbol.strip().upper()
    try:
        out = dict(_daily_forecast(sym))
    except ProviderError as exc:
        raise _err(exc)
    out["as_of"] = _now()
    out["decimals"] = decimals_for(sym, out.get("last"))
    j = journal()
    out["journal"] = [g for g in (j.stats() if j else []) if g["module"] == "daily-forecast" and g["symbol"] == sym]
    return out


@router.get("/forecast/ranking")
def forecast_ranking(symbol: str = ""):
    """ASSET RANKING TABLE (rotation-v1) — every instrument SignalMesh stores, ranked by the room left in
    today's normal range, as in Shyam's rotation ladder. A ranking, not a signal; not journalled."""
    import time as _t

    def fn():
        syms = watch_symbols()

        def one(s):
            try:
                f = _daily_forecast(s)
            except ProviderError as exc:
                f = {"state": "NOT_AVAILABLE", "note": str(exc)}
            return {"symbol": s, "forecast": f, "through_close_utc": f.get("through_close_utc")}
        with ThreadPoolExecutor(max_workers=6) as ex:
            return list(ex.map(one, syms))
    try:
        rows = _cached("fc:ranking-rows", fn, ttl=30)
    except ProviderError as exc:
        raise _err(exc)
    out = fc.ranking(rows, int(_t.time()), symbol.strip().upper())
    out["as_of"] = _now()
    return out


def _journal_symbols(tf: str) -> list[str]:
    """Every instrument SignalMesh stores this timeframe for (a week is built from stored daily bars)."""
    need = "1d" if tf == "1w" else tf
    watch = set(watch_symbols())
    return [i["symbol"] for i in _discovered()["instruments"] if i["symbol"] in watch and need in (i.get("timeframes") or [])]


def recorder() -> rec.Recorder | None:
    global _recorder
    j = journal()
    if _recorder is None and j is not None:
        s = get_settings()
        # the demo module exists only beside the fixture provider, which production refuses
        modules = [fc.DailyForecastModule()] + ([rec.FixtureDemoModule()] if provider().is_fixture else [])
        _recorder = rec.Recorder(j, _journal_bars, _journal_symbols, s.journal_interval_s, modules)
    return _recorder


def start_recorder() -> None:
    """Called once when the server starts. No journal path, or SMT_JOURNAL_RECORDER=false: nothing runs."""
    r = recorder()
    if r is not None and get_settings().journal_recorder:
        r.start()


_JOURNAL_WALL = ("TERMINAL STUDIES — forecast journal. Display-only analysis recorded by the terminal in its own store. "
                 "Not SignalMesh signals, not broker orders, an input to nothing. Every entry, stop and target is a HYPOTHETICAL ANALYSIS LEVEL.")


@router.get("/journal")
def journal_view(module: str = "", symbol: str = "", tf: str = "", limit: int = Query(200, ge=1, le=1000)):
    """FORECAST JOURNAL (journal-v1, score-v1): the append-only record of the terminal's own
    display-only forecasts, each with what closed candles later did to it, and hit rates per
    module / symbol / timeframe WITH the sample size. Reading this route writes nothing."""
    base = {"as_of": _now(), "kind": "TERMINAL STUDY — not SignalMesh engine output", "wall": _JOURNAL_WALL, "level_label": fj.LEVEL_LABEL,
            "rules": fj.RULES, "sample_rule": {"luck_below": fj.LUCK_BELOW, "judge_from": fj.JUDGE_FROM},
            "journal_version": fj.JOURNAL_VERSION, "score_version": fj.SCORE_VERSION}
    j = journal()
    if j is None:
        return {**base, "state": "NOT_CONFIGURED", "note": "no journal file is configured (SMT_JOURNAL_PATH) — nothing is recorded",
                "store": None, "recorder": None, "stats": [], "rows": []}
    r = recorder()
    info = j.info()
    return {**base, "state": info["state"], "store": info, "recorder": r.status() if r else None,
            "stats": j.stats(), "rows": j.forecasts(module, symbol, tf, limit),
            "filter": {"module": module, "symbol": symbol.upper(), "tf": tf, "limit": limit}}


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
