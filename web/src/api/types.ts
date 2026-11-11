// Mirrors adapter/signalmesh_terminal/contract.py. Keep in sync by hand; the
// parity script (scripts/verify_parity.py) checks the adapter against the engine.
export type FreshState = 'LIVE' | 'STALE' | 'UNKNOWN' | 'INVALID';

export interface Freshness { state: FreshState; age_min: number | null; limit_min: number | null; detail: string }
export interface Provenance { provider: string; source: string; engine_as_of: string | null; adapter_as_of: string; read_only: boolean }

export interface BarRef {
  price: number | null; tf: string; bar_open_ts: string | null; bar_close_ts: string | null;
  since_open_min: number | null; since_close_min: number | null; freshness: Freshness;
  source: string; source_kind: 'mt5_reporter' | 'bridge' | 'fixture' | 'unstated' | 'other'; source_warning: string;
}
export interface PriceContract {
  rule: string; tick: { state: string; price: number | null; note: string };
  last_closed_1m: BarRef | null; engine_reference: BarRef | null;
  drift: { state?: string; snapshot_price?: number; current_price?: number; drift_atr?: number; delta?: number; latest_bar_ts?: string; latest_bar_tf?: string; reason?: string; rule?: string };
}
export interface SideState { side: 'BUY' | 'SELL'; state: 'READY' | 'WAIT' | 'INVALID'; reason: string; lane: string }
export interface ExpiredPlan { signal: SignalRef; levels: Level[]; note: string }

export interface Candle { time: number; open: number; high: number; low: number; close: number; volume: number | null; spread: number | null; source: string }
export interface CandleSeries {
  symbol: string; tf: string; count: number; closed_only: boolean; candles: Candle[]; freshness: Freshness; freshness_basis: string; newest_bar: string;
  last_bar: BarRef | null; provenance: Provenance; platform_label: string; source_kind: string; source_warning: string; decimals: number;
}

export interface Level { key: string; label: string; kind: 'entry' | 'sl' | 'tp'; value: number; stale: boolean; origin: string }

export interface SignalRef {
  signal_id: string; system: string; symbol: string; tf: string; direction: string;
  entry: number | null; sl: number | null; tp1: number | null; tp2: number | null; rr: number | null;
  grade: string; status: string; confidence: number | null; council_approve: number | null; council_total: number | null;
  created_at: string | null; age_h: number | null; stale: boolean; bucket: 'ACTIVE' | 'PENDING' | 'EXPIRED' | 'REJECTED' | 'OTHER'; reason: string;
  market_structure: string; pine: Record<string, string | number | boolean>;
}

export interface LaneState {
  engine: string; decision: string; reasons: string[]; structure: string | null; confirmation_text: string; confirmation_status: string;
  stage: string; entry: number | null; sl: number | null; tp1: number | null; tp2: number | null; rr1: number | null; validity: string;
}

export interface DecisionView {
  symbol: string; decimals: number; provenance: Provenance; session: string; exchanges: { name: string; state: string; holiday_note?: string }[];
  engine_status: string; summary: 'READY' | 'WAIT' | 'INVALIDATED' | 'UNKNOWN'; color: string; order_type: string | null;
  entry: number | null; sl: number | null; tp1: number | null; tp2: number | null; rr1: number | null; rr2: number | null;
  grade: string | null; score: number | null; reason: string; why: string[]; conflicts: string[]; lifecycle: string | null; distance_atr: number | null;
  gates: { gate: string; ok: boolean; detail: string; first_block?: boolean }[];
  bias: string | null; structure: string | null; regime: string | null; atr: number | null; last_close: number | null; last_bar_ts: string | null;
  tradeability: number | null; session_change_pct: number | null; levels_ladder: { name?: string; value?: number; tf?: string; lookback?: number; source?: string }[];
  recent_high: number | null; recent_low: number | null; session_high: number | null; session_low: number | null;
  news_risk: string; news_events: { title: string; impact: string; in_min: number }[]; news_state: Record<string, unknown>;
  macro: Record<string, { trend: string | null; state: string }>; freshness: Record<string, Freshness>; exposure: Record<string, unknown>;
  drift: Record<string, unknown>; signal: SignalRef | null; levels: Level[]; levels_rule: string; expired_plan: ExpiredPlan | null;
  lane: LaneState; invalidation: string[]; price: PriceContract; sides: Record<'BUY' | 'SELL', SideState>; side_rule: string;
}

export interface MarketWatchRow {
  symbol: string; decimals: number; price: number | null; price_kind: string; price_ts: string | null; bar_close_ts: string | null; price_tf: string;
  age_min: number | null; since_close_min: number | null; freshness: Freshness; source: string; source_kind: string; source_warning: string;
  change_pct: number | null; change_basis: string; bias: string | null;
  engine_status: string; summary: string; direction: string | null; lane_decision: string; error: string; category?: string;
}

export interface TradeRow {
  id: number; symbol: string; direction: string; lots: number; entry: number | null; exit: number | null; sl: number | null; tp: number | null;
  status: string; profit: number | null; session: string; open_time: string | null; close_time: string | null;
  signal_id?: string | null; account_masked?: string | null; ticket?: string | null;
}

// account-contract-v1 — broker-reported values; null = the reporter did not send it (NOT AVAILABLE)
export interface AccountView {
  id: string; platform: 'MT5' | 'CTRADER'; environment: 'DEMO' | 'LIVE' | 'UNKNOWN'; broker: string | null; server: string | null;
  login_masked: string | null; currency: string | null; leverage: number | null; connection: 'ONLINE' | 'OFFLINE' | 'UNKNOWN';
  last_heartbeat: string | null; last_update: string | null; balance: number | null; equity: number | null; floating_pnl: number | null;
  used_margin: number | null; free_margin: number | null; margin_level: number | null; combined: boolean; accounts_in_total: number;
  online_in_total: number | null; source: string; field_sources: Record<string, string>; notes: string[];
}
export interface Accounts { as_of: string; read_at?: string; mode: 'PER_ACCOUNT' | 'PORTFOLIO_TOTAL'; note: string; rule: string; accounts: AccountView[]; disconnected: AccountView[]; supported_types: string[]; default: string | null }
export interface BrokerRow { ticket: string | number | null; symbol: string | null; direction: string | null; order_type: string | null; lots: number | null; entry: number | null; sl: number | null; tp: number | null; profit: number | null; time: string | null; signal_id: string | null }
export interface AccountDetail {
  as_of: string; read_at?: string; mode: string; note: string; rule: string; account: AccountView | null;
  positions: BrokerRow[]; positions_source?: string; orders: BrokerRow[]; orders_source?: string; closed: TradeRow[]; closed_source?: string;
  counts?: { positions: number; orders: number; closed: number }; journal_error?: string; kind?: string; disconnected?: AccountView[];
}

export interface Sourced { value: string | number | boolean; source: string }
export interface LifecycleStage { key: string; label: string; state: 'DONE' | 'NOT_DONE' | 'NOT_RECORDED' | 'REPORTED' | 'REJECTED' | 'UNKNOWN'; detail: string; source: string; at: string | null }
export interface SignalDetail {
  as_of: string; signal: SignalRef; headline: string; is_broker_execution: boolean; origin: Record<string, Sourced>;
  validation: { structure: Sourced & { sensor_words: Record<string, string | number | boolean>; sensor_source: string }; news: Sourced; council: Sourced; brain_reason: Sourced };
  invalidation: string[]; lifecycle: LifecycleStage[];
  execution: { status: string; is_broker_execution: boolean; broker_source: Sourced; account: Sourced; execution_price: Sourced; exit_price: Sourced; lots: Sourced; profit: Sourced;
    journal_row: number | null; link_rule: string; link_note: string; adapters: ExecutionMode[] };
  sensor_payload: Record<string, string | number | boolean>; fields_seen: { signal: string[]; raw_payload: string[] }; rule: string;
}

export interface ExecutionMode { mode: 'MANUAL' | 'MT5' | 'CTRADER'; label: string; state: 'AVAILABLE' | 'DISABLED' | 'NOT_CONFIGURED'; note: string; platform?: string; account_types?: string[]; can_place?: boolean }

export interface BuildIdentity {
  name: string; version: string; label: string; commit: string; build: number | null; shallow: boolean; dirty: boolean; commit_time: string | null;
  built_at: string | null; started_at: string; environment: 'PRODUCTION' | 'STAGING' | 'LOCAL'; data: string; source: string;
}
export interface Release { version: string; date: string; changes: string[]; fixed: string[]; outstanding: string[] }

export interface Health {
  build?: BuildIdentity;
  adapter: { version: string; as_of: string; env: string; poll_s: number; cache: Record<string, number>; auth: string; login_url?: string };
  provider: { name: string; is_fixture: boolean; configured: boolean; url: string | null };
  upstream: { reachable: boolean; ok?: boolean; http?: number; schema?: string; error?: string; state?: string };
  execution: { enabled: boolean; phase: string; can_place: boolean; modes: ExecutionMode[] };
  symbols: string[]; default_symbol: string; timeframes: string[];
}

export interface Ticket {
  mode: string; available: boolean; sent_to_broker: boolean; note: string; text?: string; symbol?: string; order_type?: string;
  entry?: number; sl?: number; tp1?: number | null; tp2?: number | null; rr1?: number | null; signal_id?: string;
}

export interface Coverage { as_of: string; symbol: string; timeframes: { tf: string; stored: boolean; last_ts: string | null; state: string; error?: string }[]; note: string }

export interface Instrument { symbol: string; category: string; decimals: number; available: boolean; timeframes: string[]; coverage: Coverage['timeframes']; origins: string[]; pinned: boolean }
export interface Instruments { as_of: string; watch: string[]; pinned: string[]; source: string; instruments: Instrument[] }
