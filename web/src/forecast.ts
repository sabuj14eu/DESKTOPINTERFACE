// FORECASTING STUDIES — the terminal's own DISPLAY-ONLY studies that appear in the chart's "indicators"
// menu (step 2: daily forecast top / bottom and the asset ranking table). They are calculated by the
// adapter from SignalMesh's stored CLOSED candles (forecast.py), ported from Shyam's Pine scripts.
// They are not SignalMesh engine output, they feed nothing, and every entry / stop / target they
// show is a HYPOTHETICAL ANALYSIS LEVEL. All are OFF by default and remembered in the workspace.
export interface ForecastStudy { id: string; name: string; short: string; color: string; what: string }
export const FORECAST_STUDIES: ForecastStudy[] = [
  { id: 'fc-daily', name: 'Daily forecast — top / bottom (ADR)', short: 'Daily forecast', color: '#fbbf24', what: 'two lines on the chart: today\'s projected top and bottom from the average daily range, plus a report' },
  { id: 'fc-ranking', name: 'Asset ranking table — room left today', short: 'Asset ranking', color: '#38bdf8', what: 'a table ranking every instrument by unused daily range, with a GO TRADE line' },
];
export const FORECAST_IDS = FORECAST_STUDIES.map((s) => s.id);
export const FORECAST_NOTE = 'terminal studies · display only · from stored CLOSED candles · not SignalMesh engine output · levels are HYPOTHETICAL ANALYSIS LEVELS';

export interface FcSettings { side: 'both' | 'top' | 'bottom'; history: boolean; report: boolean }
export const FC_DEFAULT: FcSettings = { side: 'both', history: false, report: true };
export const fcSanitize = (raw: unknown): FcSettings => {
  const r = (raw && typeof raw === 'object' ? raw : {}) as Partial<FcSettings>;
  return { side: r.side === 'top' || r.side === 'bottom' ? r.side : 'both', history: r.history === true, report: r.report !== false };
};

export interface FcScenario {
  module: string; side: 'bullish' | 'bearish'; direction: 'LONG' | 'SHORT'; pattern: string; entry: number; sl: number; tp1: number; tp2: number; invalidation: number;
  rr1: number | null; rr2: number | null; horizon: string; horizon_bars: number; made_bar: number; made_bar_utc: string; status: string; confidence: string; level_label: string; rule: string;
}
export interface FcOutlook { state: string; note?: string; avg_range?: number; top?: number; bottom?: number; high?: number; low?: number; used_pct?: number | null; top_done?: boolean; bottom_done?: boolean }
export interface FcHistoryDay { day_start: number; day_end: number; adr: number; high: number; low: number; top: number; bottom: number; top_done: boolean; bottom_done: boolean; used_pct: number }
export interface DailyForecast {
  symbol: string; state: string; note?: string; kind: string; method_version: string; methodology: Record<string, string>; level_label: string; confidence: string; confidence_rule?: string;
  decimals: number; intraday_tf?: string; as_of: string; calculated_at?: string; source?: string;
  adr?: number; adr_days?: number; day_open?: number; day_high?: number; day_low?: number; last?: number; prev_close?: number; prev_high?: number; prev_low?: number;
  top_raw?: number; bottom_raw?: number; top?: number; bottom?: number; top_snapped_to?: string | null; bottom_snapped_to?: string | null; top_done?: boolean; bottom_done?: boolean;
  completed_by?: { side: 'TOP' | 'BOTTOM'; bar: number } | null; used_pct?: number; move_pct?: number; status?: string; room_up?: number; room_down?: number;
  day_start?: number; day_start_utc?: string; day_end_utc?: string; through_close?: number; through_close_utc?: string; bars_today?: number;
  scenarios: FcScenario[]; history: FcHistoryDay[]; outlooks: Record<string, FcOutlook>;
  journal?: { timeframe: string; origin: string; recorded: number; open: number; finished: number; tp1: number; tp2: number; tp1_rate_pct: number | null; tp2_rate_pct: number | null; sample: string; judgeable: boolean }[];
}
export interface RankingRow { rank: number | null; symbol: string; used_pct: number | null; move_pct: number | null; state: string; action: string; session_ok: boolean | null; score: number | null; note?: string }
export interface Ranking {
  kind: string; method_version: string; methodology: Record<string, string>; sessions: { asia: boolean; london: boolean; ny: boolean };
  rows: RankingRow[]; go_trade: string; go_symbol: string | null; note: string; as_of: string;
}
