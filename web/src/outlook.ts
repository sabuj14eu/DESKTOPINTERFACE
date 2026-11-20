// OUTLOOK VIEWS (outlook-views-v1) — the shapes of /api/terminal/outlook, /call-ledger and /turning-points.
// Every word, level, state, count, rate and verdict below is SignalMesh's own (platform 5.210), reshaped by the adapter and
// never calculated here. The only thing the terminal adds is `decimals` (how a price is printed). Optional = the platform
// may not have sent it; an absent value is printed NOT AVAILABLE or left out, never guessed.
export type ViewState = 'OK' | 'NOT_BUILT';
interface ViewBase { state: ViewState; note?: string; route?: string; terminal_rule: string; read_at?: string; is_fixture?: boolean }

export interface OutlookLevel { value: number; name: string; names?: string[]; date?: string; dist?: number; dist_pct?: number | null; dist_atr?: number | null }
export interface OutlookInteresting { kind: string; text: string; level: OutlookLevel; then?: OutlookLevel | null }
export interface OutlookWrong { side: string; value: number; text: string; dist_pct?: number | null; dist_atr?: number | null }
export interface OutlookRead {
  rule?: string; symbol?: string; tf?: string; as_of?: string; state: string; reason?: string; structure?: string; structure_rule?: string; bars?: number;
  bar_ts?: string | null; bar_day?: string | null; bar_age_days?: number | null; close?: number | null; atr?: number | null; above?: OutlookLevel[]; below?: OutlookLevel[];
  heading?: { word: string; why: string } | null; interesting?: OutlookInteresting[]; wrong?: OutlookWrong | null; series_fault?: string; swing_highs?: number[]; swing_lows?: number[];
}
export interface OutlookOverviewRow { symbol: string; state: string; structure?: string; close?: number | null; bar_ts?: string | null; bar_day?: string | null; reason?: string;
  above?: OutlookLevel | null; below?: OutlookLevel | null; wrong?: OutlookWrong | null; decimals: number }
// the platform's scoreboard (analyst_ledger.scoreboard): counts, the share that continued, and a verdict in words
export interface Scoreboard { calls?: number; pending?: number; resolved?: number; hits?: number; invalidated?: number; expired?: number; both?: number; void?: number;
  hit_rate?: number | null; label?: string; verdict?: string }
export interface OpenCall { direction?: string; ref_price?: number; target?: number; invalidation?: number | null; recorded_at?: string }
export interface OutlookTrack { rule?: string; analyst?: string; board?: Scoreboard; here?: Scoreboard; open?: OpenCall | null; atr_mult?: number; days?: number; fault?: string }
export interface MarketOutlook extends ViewBase { rule?: string; symbol?: string; as_of?: string; plain?: string; authority?: string; decimals?: number;
  read?: OutlookRead | null; overview?: OutlookOverviewRow[]; track?: OutlookTrack | null }

export interface LedgerRow { id: number; symbol: string; direction: string; ref_price: number; target: number; invalidation: number | null; recorded_at: string; expires_at?: string;
  daily_bar_close?: string | null; why?: string; outcome: string; outcome_at?: string | null; r?: number | null; stored?: boolean; decimals: number }
export interface CallLedger extends ViewBase { rule?: string; scoring_rule?: string; analyst?: string; as_of?: string; definition?: string; board?: Scoreboard; authority?: string; plain?: string; rows?: LedgerRow[] }

export interface TpWord { n: number; hits: number; hit_rate: number | null; base_rate: number | null; lift: number | null; lift_needed: number; label?: string; verdict: string }
export interface TpSegment { points: number; independent: number; base?: { down: number; up: number; none: number }; words?: Record<string, TpWord>;
  brier_down?: number | null; brier_up?: number | null; brier_ref_down?: number | null; brier_ref_up?: number | null; first_as_of?: string; last_as_of?: string;
  example?: { as_of: string; price: number; atr: number; down_at: number; up_at: number } | null; rows_hidden?: number }
export interface TpCell { symbol: string; tf: string; model_repo?: string; model_revision?: string; config_hash?: string; readable?: boolean; rows?: number; word: string;
  candidate_words?: string[]; held_words?: string[]; holdout_word?: string | null; holdout_state?: string; computed_from?: string; computed_to?: string;
  search?: TpSegment | null; holdout?: TpSegment | null; decimals: number }
export interface TurningPoints extends ViewBase { rule?: string; as_of?: string; authority?: string; plain?: string; config_hash?: string;
  question?: { horizon_bars?: number; atr_mult?: number; threshold?: number; touch_on?: string; holdout_share?: number };
  total_rows?: number; skill_rows?: number; shadow_rows?: number; fake_rows?: number;
  overall?: { word: string; why: string; cells?: number }; gate?: { open?: boolean; why: string; steps: { name: string; passed: boolean; note?: string }[] };
  words?: { top?: string; bottom?: string }; cells?: TpCell[] }
