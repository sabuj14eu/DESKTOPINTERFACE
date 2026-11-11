"""THE TERMINAL DATA CONTRACT — what the UI is allowed to know.

Every model here is a RESHAPE of a SignalMesh response. Field names map to
the engine field they come from (see docs/DATA_CONTRACT.md). Nothing is a
new calculation; where a display selection rule exists (which signal's
levels to draw, when a plan counts as expired) it mirrors the rule the
platform's own chart page uses, and says so in `rule`.

Every price-bearing block carries: source, timestamp, freshness. A number
with none of these is not allowed out of this module (Freshness Law).
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

FreshState = Literal["LIVE", "STALE", "UNKNOWN", "INVALID"]


class Freshness(BaseModel):
    state: FreshState = "UNKNOWN"
    age_min: float | None = None
    limit_min: float | None = None
    detail: str = ""


class Provenance(BaseModel):
    provider: str                      # signalmesh | fixture
    source: str                        # the engine's own price_source words
    engine_as_of: str | None = None    # the engine's as_of stamp
    adapter_as_of: str                 # when this adapter read it
    read_only: bool = True


class Candle(BaseModel):
    time: int                          # epoch seconds, bar OPEN, UTC
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None        # MT5 tick volume, not traded size
    spread: float | None = None
    source: str = ""


class CandleSeries(BaseModel):
    symbol: str
    tf: str
    count: int
    closed_only: bool = True
    candles: list[Candle]
    freshness: Freshness
    freshness_basis: str = ""          # engine bar-clock: "since_open"
    newest_bar: str = ""               # engine's "HH:MM–HH:MM UTC" span
    last_bar: BarRef | None = None
    provenance: Provenance
    platform_label: str = ""           # SignalMesh's static price_source words
    source_kind: str = "unstated"      # derived from the per-candle source (authority)
    source_warning: str = ""
    decimals: int


class BarRef(BaseModel):
    """ONE bar, named completely: which bar, when it opened and closed, how old
    on both clocks, and where it came from. The price-contract unit."""
    price: float | None = None
    tf: str = ""
    bar_open_ts: str | None = None
    bar_close_ts: str | None = None
    since_open_min: float | None = None
    since_close_min: float | None = None
    freshness: Freshness = Field(default_factory=Freshness)
    source: str = ""                   # the per-candle source string, verbatim
    source_kind: Literal["mt5_reporter", "bridge", "fixture", "unstated", "other"] = "unstated"
    source_warning: str = ""


class PriceContract(BaseModel):
    """price-contract-v1 — every price the terminal shows is ONE of these,
    and each is labelled with its kind. They are never blended.

      tick              — a live quote. SignalMesh stores none: UNAVAILABLE.
      last_closed_1m    — the newest CLOSED 1-minute bar's close (header price).
      engine_reference  — the close of the last closed 15m bar the engine's
                          decision/ATR/structure were measured on
                          (snapshot.market.last_close / last_bar_ts).
      chart_last_bar    — the newest closed bar of the chart's own timeframe.
      drift             — the engine's own reconciliation of engine_reference
                          vs the newest 1m bar (desk ref-drift-v1).
    """
    rule: str = "price-contract-v1"
    tick: dict = Field(default_factory=lambda: {"state": "UNAVAILABLE", "price": None,
                                                "note": "SignalMesh stores no bid/ask/tick; nothing here is a live quote"})
    last_closed_1m: BarRef | None = None
    engine_reference: BarRef | None = None
    drift: dict = Field(default_factory=dict)


class SideState(BaseModel):
    side: Literal["BUY", "SELL"]
    state: Literal["READY", "WAIT", "INVALID"]
    reason: str = ""
    lane: str = ""                     # desk intraday lane note for this side, if any


class Level(BaseModel):
    key: str                           # entry | sl | tp1 | tp2
    label: str
    kind: Literal["entry", "sl", "tp"]
    value: float
    stale: bool = False
    origin: str                        # "plan" | "signal <id>"


class ExpiredPlan(BaseModel):
    """A plan past the engine's 12h lifecycle. HISTORY, never a level."""
    signal: "SignalRef"
    levels: list[Level] = Field(default_factory=list)
    note: str = ""


class SignalRef(BaseModel):
    signal_id: str
    system: str = ""
    symbol: str
    tf: str = ""
    direction: str = ""
    entry: float | None = None
    sl: float | None = None
    tp1: float | None = None
    tp2: float | None = None
    rr: float | None = None
    grade: str = ""
    status: str = ""
    confidence: float | None = None
    council_approve: int | None = None
    council_total: int | None = None
    created_at: str | None = None
    age_h: float | None = None
    stale: bool = False                # older than the engine's 12h lifecycle
    bucket: Literal["ACTIVE", "PENDING", "EXPIRED", "REJECTED", "OTHER"] = "OTHER"
    reason: str = ""
    market_structure: str = ""
    # The sensor's own words, verbatim from Signal.raw_payload (append-only contract):
    # trend, choch, inducement, sweep, trap_bias, loc_zone, killzone, level_src, htf_align,
    # ny_regime, session, method, mode, score ... whatever Pine sent.
    pine: dict = Field(default_factory=dict)


class LaneState(BaseModel):
    """The desk's intraday lane (engine auto-v1), as the platform's chart
    page shows it: decision + reasons verbatim, confirmation wording from
    the platform's fixed vocabulary."""
    engine: str = ""
    decision: str = "UNKNOWN"
    reasons: list[str] = Field(default_factory=list)
    structure: str | None = None
    confirmation_text: str = ""
    confirmation_status: str = "UNKNOWN"
    stage: str = "UNKNOWN"
    entry: float | None = None
    sl: float | None = None
    tp1: float | None = None
    tp2: float | None = None
    rr1: float | None = None
    validity: str = ""


class LaneCard(BaseModel):
    """One desk lane (Scalp / Intraday / Session / Swing) as the platform's /desk page shows it,
    reduced to the plan: order type and Entry / SL / TP1 / TP2. PAPER research — never an order."""
    label: str = ""
    engine: str = ""
    tf: str = ""
    decision: str = "UNKNOWN"          # BUY | SELL | WAIT | ... verbatim
    order_type: str | None = None
    entry: float | None = None
    sl: float | None = None
    tp1: float | None = None
    tp2: float | None = None
    rr1: float | None = None
    reasons: list[str] = Field(default_factory=list)   # why it waits, verbatim
    verdict: str = ""                  # the lane's own validity verdict
    paper: bool = True


class BrainPlan(BaseModel):
    """The platform's "Latest brain plan" (/brain-view): the newest signal for the symbol with
    status pending / approved / executed. LIVE inside the 12h lifecycle, STALE after it,
    NEVER_POSTED when there is none. A recommendation — never a broker order."""
    state: Literal["LIVE", "STALE", "NEVER_POSTED"] = "NEVER_POSTED"
    signal: "SignalRef | None" = None
    note: str = ""
    rule: str = ""


class DecisionView(BaseModel):
    symbol: str
    decimals: int
    provenance: Provenance
    session: str = ""
    exchanges: list[dict] = Field(default_factory=list)
    # planner.build_plan verbatim
    engine_status: str = "UNKNOWN"     # READY | WAIT | NO TRADE
    summary: Literal["READY", "WAIT", "INVALIDATED", "UNKNOWN"] = "UNKNOWN"
    color: str = ""
    order_type: str | None = None
    entry: float | None = None
    sl: float | None = None
    tp1: float | None = None
    tp2: float | None = None
    rr1: float | None = None
    rr2: float | None = None
    grade: str | None = None
    score: float | None = None
    reason: str = ""
    why: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    lifecycle: str | None = None
    distance_atr: float | None = None
    gates: list[dict] = Field(default_factory=list)
    # market block from the snapshot
    bias: str | None = None
    structure: str | None = None
    regime: str | None = None
    atr: float | None = None
    last_close: float | None = None
    last_bar_ts: str | None = None
    tradeability: float | None = None
    session_change_pct: float | None = None
    levels_ladder: list[dict] = Field(default_factory=list)
    recent_high: float | None = None
    recent_low: float | None = None
    session_high: float | None = None
    session_low: float | None = None
    # news / macro / freshness / exposure
    news_risk: str = "UNKNOWN"
    news_events: list[dict] = Field(default_factory=list)
    news_state: dict = Field(default_factory=dict)      # news-state-v1 row
    macro: dict = Field(default_factory=dict)
    freshness: dict[str, Freshness] = Field(default_factory=dict)
    exposure: dict = Field(default_factory=dict)
    drift: dict = Field(default_factory=dict)
    # the signal the plan is built on (if any), and the chart lines
    signal: SignalRef | None = None
    levels: list[Level] = Field(default_factory=list)      # CURRENT levels only
    levels_rule: str = ""
    expired_plan: ExpiredPlan | None = None                 # history, shown apart
    lane: LaneState = Field(default_factory=LaneState)
    lanes: list[LaneCard] = Field(default_factory=list)     # every desk lane, plan only (PAPER)
    brain_plan: BrainPlan = Field(default_factory=BrainPlan)
    invalidation: list[str] = Field(default_factory=list)
    price: PriceContract = Field(default_factory=PriceContract)
    sides: dict[str, SideState] = Field(default_factory=dict)
    side_rule: str = ""


class MarketWatchRow(BaseModel):
    symbol: str
    decimals: int
    price: float | None = None         # last CLOSED 1m bar close (price-contract-v1: last_closed_1m)
    price_kind: str = "last_closed_1m"
    price_ts: str | None = None        # bar OPEN
    bar_close_ts: str | None = None
    price_tf: str = "1m"
    age_min: float | None = None       # engine gate age (since open)
    since_close_min: float | None = None
    freshness: Freshness
    source: str = ""
    source_kind: str = "unstated"
    source_warning: str = ""
    change_pct: float | None = None    # engine session_change_pct
    change_basis: str = "session (engine)"
    bias: str | None = None
    engine_status: str = "UNKNOWN"
    summary: str = "UNKNOWN"
    direction: str | None = None
    lane_decision: str = "UNKNOWN"
    error: str = ""


class TradeRow(BaseModel):
    """One row of SignalMesh's trade journal (MT5 reporter heartbeats): BROKER truth.
    `signal_id` / `account_masked` / `ticket` are present only when the journal row carries them."""
    id: int
    symbol: str
    direction: str
    lots: float
    entry: float | None = None
    exit: float | None = None
    sl: float | None = None
    tp: float | None = None
    status: str
    profit: float | None = None
    session: str = ""
    open_time: str | None = None
    close_time: str | None = None
    signal_id: str | None = None
    account_masked: str | None = None
    ticket: str | None = None


class AccountView(BaseModel):
    """account-contract-v1 — ONE broker account (or, flagged `combined`, SignalMesh's own
    total over several). Every money field is the broker's as the reporter sent it; None
    means the reporter did not send it and the UI prints NOT AVAILABLE. Nothing is derived."""
    id: str                                  # opaque selector key (never the account number)
    platform: Literal["MT5", "CTRADER"] = "MT5"
    environment: Literal["DEMO", "LIVE", "UNKNOWN"] = "UNKNOWN"
    broker: str | None = None
    server: str | None = None
    login_masked: str | None = None
    currency: str | None = None
    leverage: float | None = None
    connection: Literal["ONLINE", "OFFLINE", "UNKNOWN"] = "UNKNOWN"
    last_heartbeat: str | None = None
    last_update: str | None = None
    balance: float | None = None
    equity: float | None = None
    floating_pnl: float | None = None
    used_margin: float | None = None
    free_margin: float | None = None
    margin_level: float | None = None
    combined: bool = False                   # True = a total over several accounts, not one account
    accounts_in_total: int = 1
    online_in_total: int | None = None
    source: str = ""
    field_sources: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ExecutionMode(BaseModel):
    mode: Literal["MANUAL", "MT5", "CTRADER"]
    label: str
    state: Literal["AVAILABLE", "DISABLED", "NOT_CONFIGURED"]
    note: str


class OrderTicket(BaseModel):
    """Mode A output: the pending order the USER places by hand. Never sent."""
    mode: Literal["MANUAL"] = "MANUAL"
    symbol: str
    direction: str
    order_type: str
    entry: float
    sl: float
    tp1: float | None = None
    tp2: float | None = None
    rr1: float | None = None
    signal_id: str = ""
    engine_status: str = ""
    text: str
    sent_to_broker: bool = False
    note: str


def jsonable(obj: Any) -> Any:
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [jsonable(v) for v in obj]
    return obj
