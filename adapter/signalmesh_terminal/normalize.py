"""RESHAPE, never recompute.

Each function takes SignalMesh's own JSON (the /api/v1 mirror) and returns
a contract model. Rules of this file:

  * a value the engine did not send stays None / UNKNOWN — never defaulted;
  * freshness states pass through verbatim — never upgraded;
  * the only "logic" is display selection, and each such rule is named in
    the output (`rule`) and mirrors the platform's own page code:
      - levels: chart._levels — newest signal with status in
        (pending, approved, executed); EXPIRED after SIGNAL_TTL_H (12h);
      - summary word: READY -> READY, WAIT -> WAIT, NO TRADE -> INVALIDATED;
      - lane confirmation wording: chart._WAIT_CONF, copied verbatim.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .contract import (BarRef, Candle, CandleSeries, DecisionView, ExpiredPlan, Freshness, LaneState, Level,
                       MarketWatchRow, PriceContract, Provenance, SideState, SignalRef, TradeRow)

# app/services/precision.py — the platform's one decimals table (copied; display only).
SYMBOL_DECIMALS = {
    "GOLD": 2, "SILVER": 3,
    "EURUSD": 5, "GBPUSD": 5, "AUDUSD": 5, "NZDUSD": 5, "USDCAD": 5, "USDCHF": 5, "EURGBP": 5,
    "USDJPY": 3, "EURJPY": 3, "GBPJPY": 3,
    "US100": 1, "US30": 1, "US500": 1, "GER40": 1,
    "BTC": 1, "ETH": 2, "SOL": 3, "ADA": 5, "LINK": 3, "XRP": 5, "LTC": 2, "DOGE": 6, "DOT": 3, "BNB": 2,
    "OIL": 2, "DXY": 2,
}

# app/routers/chart.py _WAIT_CONF — the platform's fixed vocabulary, verbatim.
WAIT_CONF = {
    "STRUCTURE_MIXED": ("STRUCTURE_CONFIRMATION", "NOT CONFIRMED",
                        "wait for structure confirmation — 15m must print HH/HL (for a BUY) or LH/LL (for a SELL); mixed structure builds nothing."),
    "STRUCTURE_UNKNOWN": ("STRUCTURE_CONFIRMATION", "NOT CONFIRMED",
                          "wait for structure to be MEASURED — not enough confirmed 15m swing points yet; this is UNKNOWN, not mixed: nothing was measured."),
    "NEWS_HIGH": ("NEWS_WINDOW", "NOT CONFIRMED", "wait for the high-impact news window to pass."),
    "DATA_STALE": ("DATA_FRESHNESS", "NOT CONFIRMED", "wait for fresh closed candles — stale data builds nothing."),
    "NO_LEVELS": ("DATA_FRESHNESS", "NOT CONFIRMED", "no stored structural levels yet — nothing to anchor an entry to."),
}

SUMMARY = {"READY": "READY", "WAIT": "WAIT", "NO TRADE": "INVALIDATED"}
LEVELS_RULE = ("current levels only: the READY plan's levels, else the newest signal with status in (pending, approved, executed) "
               "that is INSIDE the engine's 12h lifecycle (planner.SIGNAL_FRESH_H). An expired signal is history (expired_plan), never a level")
SIDE_RULE = ("per side, from the engine plan only: READY = plan READY and its order type is this side; "
             "INVALID = plan NO TRADE (both sides), or plan WAIT because this side's own plan expired or conflicts with bias; "
             "WAIT = otherwise. The reason is the engine's reason verbatim")
TF_MIN = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440}


def source_kind(src: str | None) -> tuple[str, str]:
    """Classify a per-candle source string. The per-candle `source` is the
    authority on provenance; SignalMesh's static price_source line is a label."""
    s = (src or "").strip().lower()
    if not s:
        return "unstated", "candle carries no source — provenance unknown"
    if s.startswith("mt5"):
        return "mt5_reporter", ""
    if "fixture" in s or "synthetic" in s or "demo" in s or "seed" in s:
        return "fixture", f"candle source is '{src}' — FIXTURE/SYNTHETIC, not broker data"
    if "bridge" in s:
        return "bridge", f"candle source is '{src}' — the display-only live bridge, not the stored reporter feed"
    return "other", f"candle source is '{src}' — not an MT5 reporter feed"


def bar_ref(symbol: str, tf: str, candles_payload: dict | None, now: datetime | None = None) -> BarRef | None:
    """The newest closed bar of one series, named completely."""
    if not candles_payload or not candles_payload.get("candles"):
        return None
    now = now or _now()
    last = candles_payload["candles"][-1]
    o = _aware(last.get("ts"))
    if o is None:
        return None
    c = o + timedelta(minutes=TF_MIN.get(tf, 15))
    kind, warn = source_kind(last.get("source"))
    since_open = round((now - o).total_seconds() / 60, 1)
    return BarRef(price=last.get("close"), tf=tf, bar_open_ts=o.isoformat(), bar_close_ts=c.isoformat(),
                  since_open_min=since_open, since_close_min=round(since_open - TF_MIN.get(tf, 15), 1),
                  freshness=_fresh(candles_payload.get("freshness")), source=str(last.get("source") or ""),
                  source_kind=kind, source_warning=warn)


def decimals_for(symbol: str, value=None) -> int:
    d = SYMBOL_DECIMALS.get((symbol or "").upper())
    if d is not None:
        return d
    try:
        a = abs(float(value))
    except (TypeError, ValueError):
        return 2
    return 5 if a < 20 else 3 if a < 1000 else 2


def _aware(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fresh(d: dict | None) -> Freshness:
    d = d or {}
    state = str(d.get("state") or "UNKNOWN").upper()
    if state not in ("LIVE", "STALE", "UNKNOWN", "INVALID"):
        state = "UNKNOWN"
    return Freshness(state=state, age_min=d.get("age_min"), limit_min=d.get("limit_min"),
                     detail=str(d.get("detail") or d.get("note") or ""))


def _prov(provider_name: str, payload: dict, source: str | None = None) -> Provenance:
    return Provenance(provider=provider_name, source=source or str(payload.get("price_source") or "unstated"),
                      engine_as_of=payload.get("as_of"), adapter_as_of=_now().isoformat())


# ---------------------------------------------------------------- candles
def candle_series(provider_name: str, symbol: str, tf: str, payload: dict) -> CandleSeries:
    rows = []
    for c in payload.get("candles") or []:
        ts = _aware(c.get("ts"))
        if ts is None:
            continue
        rows.append(Candle(time=int(ts.timestamp()), open=float(c["open"]), high=float(c["high"]),
                           low=float(c["low"]), close=float(c["close"]),
                           volume=c.get("tick_volume"), spread=c.get("spread"), source=str(c.get("source") or "")))
    rows.sort(key=lambda r: r.time)
    fr = payload.get("freshness") or {}
    last = bar_ref(symbol, tf, payload)
    kind, warn = (last.source_kind, last.source_warning) if last else ("unstated", "")
    return CandleSeries(symbol=symbol, tf=tf, count=len(rows), closed_only=True, candles=rows,
                        freshness=_fresh(fr), freshness_basis=str(fr.get("basis") or ""), newest_bar=str(fr.get("newest_bar") or ""),
                        last_bar=last, provenance=_prov(provider_name, payload, source=(last.source if last else None) or payload.get("price_source")),
                        platform_label=str(payload.get("price_source") or ""), source_kind=kind, source_warning=warn,
                        decimals=decimals_for(symbol, rows[-1].close if rows else None))


# ---------------------------------------------------------------- signals
# Pine alert fields the chart shows verbatim (BrotherSniper v18 alert payload; see pine/ in Sniper-System).
PINE_KEYS = ("trend", "choch", "inducement", "sweep", "trap_bias", "loc_zone", "killzone", "level_src", "htf_align",
             "htf_full", "ny_regime", "session", "method", "mode", "score", "adj_score", "macro_score", "rsi", "adx",
             "atr_expand", "news_window", "trend_day", "dxy_dir", "oil_spike", "mkt_entry", "pending_entry",
             "entry_dist_atr", "dist_ideal", "sensor_system", "route", "engine", "gate", "stance", "kind", "plan_kind")


def pine_words(raw) -> dict:
    """Only keys the sensor actually sent, values verbatim (scalars kept, others stringified)."""
    out = {}
    if not isinstance(raw, dict):
        return out
    for k in PINE_KEYS:
        v = raw.get(k)
        if v not in (None, ""):
            out[k] = v if isinstance(v, (int, float, bool)) else str(v)
    return out


def signal_ref(s: dict, ttl_h: float, now: datetime | None = None) -> SignalRef:
    now = now or _now()
    created = _aware(s.get("created_at"))
    age_h = round((now - created).total_seconds() / 3600, 1) if created else None
    stale = age_h is not None and age_h > ttl_h
    status = str(s.get("status") or "")
    if status in ("approved", "executed"):
        bucket = "EXPIRED" if stale else "ACTIVE"
    elif status == "pending":
        bucket = "EXPIRED" if stale else "PENDING"
    elif status == "rejected":
        bucket = "REJECTED"
    else:
        bucket = "OTHER"
    council = s.get("council") or s.get("council_votes") or {}
    return SignalRef(signal_id=str(s.get("signal_id") or "?"), system=str(s.get("system") or ""),
                     symbol=str(s.get("symbol") or ""), tf=str(s.get("tf") or ""),
                     direction=str(s.get("direction") or "").upper(), entry=s.get("entry"), sl=s.get("sl"),
                     tp1=s.get("tp1"), tp2=s.get("tp2"), rr=s.get("rr"), grade=str(s.get("grade") or ""),
                     status=status, confidence=s.get("confidence"),
                     council_approve=council.get("approve"), council_total=council.get("total"),
                     created_at=created.isoformat() if created else None, age_h=age_h, stale=stale,
                     bucket=bucket, reason=str(s.get("reason") or ""),
                     market_structure=str(s.get("market_structure") or ""), pine=pine_words(s.get("raw_payload")))


def _signal_levels(sig: SignalRef, stale: bool) -> list[Level]:
    out = []
    for key, label, kind in (("entry", "Entry", "entry"), ("sl", "SL", "sl"), ("tp1", "TP1", "tp"), ("tp2", "TP2", "tp")):
        v = getattr(sig, key)
        if v is not None:
            out.append(Level(key=key, label=("EXPIRED " if stale else "") + label, kind=kind, value=float(v),
                             stale=stale, origin=f"signal {sig.signal_id}"))
    return out


def levels_for(symbol: str, decision: dict, signals: list[SignalRef]) -> tuple[list[Level], SignalRef | None, ExpiredPlan | None]:
    """CURRENT levels (READY plan, else a live signal) and, separately, the
    expired plan as history. An expired plan never returns in `levels`."""
    out: list[Level] = []
    if decision.get("status") == "READY" and decision.get("entry") is not None:
        for key, label, kind in (("entry", "Entry", "entry"), ("sl", "SL", "sl"), ("tp1", "TP1", "tp"), ("tp2", "TP2", "tp")):
            v = decision.get(key)
            if v is not None:
                out.append(Level(key=key, label=label, kind=kind, value=float(v), stale=False, origin="plan"))
    sig = next((s for s in signals if s.symbol == symbol and s.status in ("pending", "approved", "executed")), None)
    if sig is None:
        return out, None, None
    if sig.stale:
        exp = ExpiredPlan(signal=sig, levels=_signal_levels(sig, True),
                          note=f"plan {sig.signal_id} is {sig.age_h}h old — past the engine's 12h lifecycle; HISTORY, not a level. See Trade History.")
        return out, (sig if out else None), exp
    if not out:
        out = _signal_levels(sig, False)
    return out, sig, None


# ---------------------------------------------------------------- lane
def lane_state(desk_payload: dict | None) -> LaneState:
    desk = (desk_payload or {}).get("desk") or {}
    lane = next((l for l in desk.get("lanes") or [] if "Intraday" in str(l.get("label") or "")), None) or {}
    c = lane.get("c") or {}
    reasons = [str(r) for r in (c.get("reasons") or [])]
    decision = str(c.get("decision") or "UNKNOWN").upper()
    confirmed = decision in ("BUY", "SELL") and c.get("entry") is not None
    if confirmed:
        ctype, cstatus, text, stage = ("PULLBACK_TO_LEVEL", "WAITING",
                                       f"{decision} only if price returns to entry and no 15m candle closes beyond SL before the fill — a close beyond SL kills the setup, it does not wait.",
                                       "DEVELOPING")
    else:
        stage = "NO SETUP"
        first = reasons[0] if reasons else ""
        if first in WAIT_CONF:
            ctype, cstatus, text = WAIT_CONF[first]
        else:
            ctype, cstatus = "NONE", "NOT CONFIRMED"
            text = ("no actionable structure — " + first.lower()) if first else "no actionable structure."
    validity = (lane.get("validity") or {}).get("verdict") or ""
    return LaneState(engine=str(c.get("engine") or ""), decision=decision, reasons=reasons,
                     structure=c.get("structure"), confirmation_text=text, confirmation_status=cstatus,
                     stage=stage, entry=c.get("entry"), sl=c.get("sl"), tp1=c.get("tp1"), tp2=c.get("tp2"),
                     rr1=c.get("rr1"), validity=str(validity))


# ---------------------------------------------------------------- decision
def side_states(status: str, order_type: str | None, reason: str, conflicts: list[str], sig: SignalRef | None,
                lane: LaneState) -> dict[str, SideState]:
    plan_dir = (order_type or "").split()[0].upper() if order_type else ""
    out = {}
    for side in ("BUY", "SELL"):
        lane_note = f"desk lane {side} · {lane.stage}" if lane.decision == side else ""
        if status == "READY":
            if side == plan_dir:
                out[side] = SideState(side=side, state="READY", reason=reason, lane=lane_note)
            else:
                out[side] = SideState(side=side, state="WAIT", reason=f"engine plan is {order_type}; no {side} plan", lane=lane_note)
        elif status == "NO TRADE":
            out[side] = SideState(side=side, state="INVALID", reason=reason, lane=lane_note)
        elif status == "WAIT":
            own = sig is not None and sig.direction == side and (sig.stale or bool(conflicts) or "EXPIRED" in reason.upper() or "conflict" in reason.lower())
            out[side] = SideState(side=side, state="INVALID" if own else "WAIT",
                                  reason=reason if own else (reason if not sig or sig.direction == side else f"no {side} plan — {reason}"), lane=lane_note)
        else:
            out[side] = SideState(side=side, state="WAIT", reason=f"engine status {status or 'UNKNOWN'}", lane=lane_note)
    return out


def price_contract(symbol: str, snap_payload: dict, candles_1m: dict | None, desk_payload: dict | None) -> PriceContract:
    snap = snap_payload.get("snapshot") or {}
    market = snap.get("market") or {}
    ref = None
    if market.get("last_close") is not None and market.get("last_bar_ts"):
        o = _aware(market["last_bar_ts"])
        c = o + timedelta(minutes=15) if o else None
        now = _now()
        ref = BarRef(price=market["last_close"], tf="15m", bar_open_ts=o.isoformat() if o else None,
                     bar_close_ts=c.isoformat() if c else None,
                     since_open_min=round((now - o).total_seconds() / 60, 1) if o else None,
                     since_close_min=round((now - c).total_seconds() / 60, 1) if c else None,
                     freshness=_fresh((snap.get("freshness") or {}).get("candles")),
                     source="engine snapshot (scanner.build_snapshot, 15m closed bars)", source_kind="other", source_warning="")
    return PriceContract(last_closed_1m=bar_ref(symbol, "1m", candles_1m), engine_reference=ref,
                         drift=((desk_payload or {}).get("desk") or {}).get("drift") or {})


def decision_view(provider_name: str, symbol: str, snap_payload: dict, signals: list[SignalRef],
                  desk_payload: dict | None = None, news_row: dict | None = None,
                  candles_1m: dict | None = None) -> DecisionView:
    snap = snap_payload.get("snapshot") or {}
    dec = snap.get("decision") or {}
    market = snap.get("market") or {}
    levels_blk = market.get("levels") or {}
    meta = snap.get("meta") or {}
    plan = snap.get("_plan") or {}
    plan_snap = plan.get("snap") or {}
    freshness = {k: _fresh(v) for k, v in (snap.get("freshness") or {}).items()}
    lv, sig, expired = levels_for(symbol, dec, signals)
    # the snapshot's own plan signal carries raw_payload (Pine's words); adopt it when it is the same signal
    if isinstance(plan.get("signal"), dict):
        ps_full = signal_ref(plan["signal"], ttl_h=12.0)
        if sig is not None and sig.signal_id == ps_full.signal_id:
            sig = ps_full
        if expired is not None and expired.signal.signal_id == ps_full.signal_id:
            expired = ExpiredPlan(signal=ps_full, levels=expired.levels, note=expired.note)
    if sig is None and expired is None and isinstance(plan.get("signal"), dict):
        ps = signal_ref(plan["signal"], ttl_h=12.0)
        if ps.stale and ps.status in ("pending", "approved", "executed"):
            expired = ExpiredPlan(signal=ps, levels=_signal_levels(ps, True),
                                  note=f"plan {ps.signal_id} is {ps.age_h}h old — past the engine's 12h lifecycle; HISTORY, not a level.")
        elif not ps.stale:
            sig = ps
    status = str(dec.get("status") or "UNKNOWN")
    lane = lane_state(desk_payload)
    plan_sig = sig or (expired.signal if expired else None)
    sides = side_states(status, dec.get("order_type"), str(dec.get("reason") or ""), [str(c) for c in dec.get("conflicts") or []], plan_sig, lane)
    inval = []
    if status == "NO TRADE":
        inval.append(str(dec.get("reason") or "engine: NO TRADE"))
    for c in dec.get("conflicts") or []:
        inval.append(str(c))
    if freshness.get("plan") and freshness["plan"].state == "STALE":
        inval.append("plan STALE — " + freshness["plan"].detail)
    if freshness.get("candles") and freshness["candles"].state != "LIVE":
        inval.append("candles " + freshness["candles"].state + " — " + freshness["candles"].detail)
    for s in lv:
        if s.kind == "sl" and sig is not None and sig.direction in ("BUY", "SELL"):
            beyond = "below" if sig.direction == "BUY" else "above"
            inval.append(f"a 15m close {beyond} SL {s.value} kills the setup (engine life rule)")
    if expired is not None:
        inval.append(expired.note)
    ladder = ((snap_payload.get("levels") or {}).get("ladder")) or []
    return DecisionView(
        symbol=symbol, decimals=decimals_for(symbol, market.get("last_close")),
        provenance=_prov(provider_name, snap_payload), session=str(meta.get("session") or ""),
        exchanges=meta.get("exchanges") or [],
        engine_status=status, summary=SUMMARY.get(status, "UNKNOWN"), color=str(dec.get("color") or ""),
        order_type=dec.get("order_type"), entry=dec.get("entry"), sl=dec.get("sl"), tp1=dec.get("tp1"),
        tp2=dec.get("tp2"), rr1=dec.get("rr1"), rr2=dec.get("rr2"), grade=dec.get("grade"), score=dec.get("score"),
        reason=str(dec.get("reason") or ""), why=[str(w) for w in dec.get("why") or []],
        conflicts=[str(c) for c in dec.get("conflicts") or []], lifecycle=dec.get("lifecycle"),
        distance_atr=dec.get("distance_atr"), gates=plan.get("gates") or [],
        bias=market.get("validated_bias"), structure=market.get("structure"), regime=plan_snap.get("regime"),
        atr=market.get("atr"), last_close=market.get("last_close"), last_bar_ts=market.get("last_bar_ts"),
        tradeability=market.get("tradeability"), session_change_pct=market.get("session_change_pct"),
        levels_ladder=ladder, recent_high=levels_blk.get("recent_high"), recent_low=levels_blk.get("recent_low"),
        session_high=market.get("session_high"), session_low=market.get("session_low"),
        news_risk=str((snap.get("news") or {}).get("risk") or "UNKNOWN"),
        news_events=(snap.get("news") or {}).get("events_next_12h") or [], news_state=news_row or {},
        macro=snap.get("macro") or {}, freshness=freshness, exposure=snap.get("exposure") or {},
        drift=((desk_payload or {}).get("desk") or {}).get("drift") or {},
        signal=sig, levels=lv, levels_rule=LEVELS_RULE, expired_plan=expired, lane=lane, invalidation=inval,
        price=price_contract(symbol, snap_payload, candles_1m, desk_payload), sides=sides, side_rule=SIDE_RULE,
    )


# ---------------------------------------------------------------- market watch
def market_watch_row(symbol: str, candles_1m: dict | None, snap_payload: dict | None,
                     desk_payload: dict | None, error: str = "") -> MarketWatchRow:
    price = ts = close_ts = since_close = None
    fresh = Freshness()
    source, kind, warn = "", "unstated", ""
    br = bar_ref(symbol, "1m", candles_1m)
    if br is not None:
        price, ts, close_ts, since_close = br.price, br.bar_open_ts, br.bar_close_ts, br.since_close_min
        source, kind, warn, fresh = br.source, br.source_kind, br.source_warning, br.freshness
    snap = (snap_payload or {}).get("snapshot") or {}
    dec = snap.get("decision") or {}
    market = snap.get("market") or {}
    status = str(dec.get("status") or "UNKNOWN")
    direction = None
    if status == "READY" and dec.get("order_type"):
        direction = str(dec["order_type"]).split()[0]
    lane = lane_state(desk_payload) if desk_payload else LaneState()
    return MarketWatchRow(symbol=symbol, decimals=decimals_for(symbol, price), price=price, price_ts=ts, bar_close_ts=close_ts,
                          price_tf="1m", age_min=fresh.age_min, since_close_min=since_close, freshness=fresh, source=source,
                          source_kind=kind, source_warning=warn,
                          change_pct=market.get("session_change_pct"), bias=market.get("validated_bias"),
                          engine_status=status, summary=SUMMARY.get(status, "UNKNOWN"), direction=direction,
                          lane_decision=lane.decision, error=error)


# ---------------------------------------------------------------- trades
def trade_row(t: dict) -> TradeRow:
    return TradeRow(id=int(t.get("id") or 0), symbol=str(t.get("symbol") or ""), direction=str(t.get("direction") or ""),
                    lots=float(t.get("lots") or 0), entry=t.get("entry"), exit=t.get("exit"), sl=t.get("sl"), tp=t.get("tp"),
                    status=str(t.get("status") or ""), profit=t.get("profit"), session=str(t.get("session") or ""),
                    open_time=t.get("open_time"), close_time=t.get("close_time"),
                    signal_id=_opt(t, ("signal_id", "signal", "signal_ref")), ticket=_opt(t, ("ticket", "position_id", "order_id")),
                    account_masked=_mask(_opt(t, ("account", "account_id", "login", "account_login"))))


def _opt(t: dict, keys) -> str | None:
    """A journal field that exists only on some platform versions: verbatim, or None."""
    for k in keys:
        if t.get(k) not in (None, ""):
            return str(t[k])
    return None


def _mask(v: str | None) -> str | None:
    if not v:
        return None
    return ("•" * max(len(v) - 4, 2) + v[-4:]) if len(v) > 4 else "••" + v[-2:]
