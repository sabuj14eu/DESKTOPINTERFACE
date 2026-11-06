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
    provenance: Provenance
    decimals: int


class Level(BaseModel):
    key: str                           # entry | sl | tp1 | tp2
    label: str
    kind: Literal["entry", "sl", "tp"]
    value: float
    stale: bool = False
    origin: str                        # "plan" | "signal <id>"


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
    levels: list[Level] = Field(default_factory=list)
    levels_rule: str = ""
    lane: LaneState = Field(default_factory=LaneState)
    invalidation: list[str] = Field(default_factory=list)


class MarketWatchRow(BaseModel):
    symbol: str
    decimals: int
    price: float | None = None         # last CLOSED bar close (engine rule)
    price_ts: str | None = None
    price_tf: str = "1m"
    age_min: float | None = None
    freshness: Freshness
    source: str = ""
    change_pct: float | None = None    # engine session_change_pct
    change_basis: str = "session (engine)"
    bias: str | None = None
    engine_status: str = "UNKNOWN"
    summary: str = "UNKNOWN"
    direction: str | None = None
    lane_decision: str = "UNKNOWN"
    error: str = ""


class TradeRow(BaseModel):
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
