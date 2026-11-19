// CHART READ — one table and one set of chart labels gathering what the terminal already knows about a chart (chart-read-v1).
// Asked for by Shyam: what his TradingView indicator shows him, on the terminal's own chart, behind one switch. It is a READ of
// closed bars: not a signal, not recorded, never an input to SignalMesh, no order. Every row names its source.
import type { PShape } from './patterns';

export const CHART_READ_ID = 'cr-read';
export const CHART_READ = { id: CHART_READ_ID, name: 'Chart read — structure table and labels', short: 'Chart read', color: '#f0abfc',
  what: 'swing labels (HH / HL / LH / LL) and rejection / engulfing candles on the chart, and one table: trend per timeframe, structure, levels, momentum, conditions' };
export const CHART_READ_NOTE = 'a read of closed bars for you · not a signal · not recorded · not SignalMesh engine output · each row names its source';

export interface CrRow { key: string; label: string; value: string; tone: string; source: string; note: string }
export interface CrLabel { kind: 'swing' | 'pattern'; label: string; side: 'high' | 'low'; price: number; time: number; confirmed_at: number; reason: string; dir?: string; type?: string }
export interface CrCondition { name: string; weight: number; status: 'CONFIRMED' | 'WAITING' | 'FAILED' | 'NOT APPLICABLE'; reason: string; bar: number | null; bar_utc: string | null }
export interface CrSide { conditions: CrCondition[]; confirmed: number; of: number; weight: number; weight_of: number; structural: number }
export interface ChartReadData {
  symbol: string; tf: string; state: string; note: string; kind: string; method_version: string; methodology: Record<string, string>; recorded: boolean; source: string;
  bars_used: number; calculated_at: string; through_close_utc: string | null; note_tradingview: string; decimals: number;
  rows: CrRow[]; labels: CrLabel[]; conditions: Record<'SELL' | 'BUY', CrSide> | null; freshness?: { state: string; age_min: number | null; limit_min: number | null; note: string };
}

const C = { up: '74,222,128', dn: '248,113,113', pat: '240,171,252' };
const SHORT: Record<string, string> = { 'BEAR REJECTION': '▼ REJ', 'BULL REJECTION': '▲ REJ', 'BEAR ENGULF': '▼ ENG', 'BULL ENGULF': '▲ ENG' };

/** The newest labels only: a chart with a label on every swing of 500 bars reads as noise. */
export function buildChartReadShapes(d: ChartReadData | null): { shapes: PShape[]; drawn: { swings: number; patterns: number } } {
  const shapes: PShape[] = [];
  if (!d || d.state !== 'OK') return { shapes, drawn: { swings: 0, patterns: 0 } };
  const swings = d.labels.filter((x) => x.kind === 'swing').slice(-28);
  const pats = d.labels.filter((x) => x.kind === 'pattern').slice(-14);
  for (const x of swings) shapes.push({ k: 'mark', study: CHART_READ_ID, t: x.time, p: x.price, text: x.label, color: x.label === 'HH' || x.label === 'HL' ? C.up : x.label === 'LH' || x.label === 'LL' ? C.dn : '148,163,184', above: x.side === 'high' });
  for (const x of pats) shapes.push({ k: 'mark', study: CHART_READ_ID, t: x.time, p: x.price, text: SHORT[x.label] ?? x.label, color: C.pat, above: x.side === 'high' });
  return { shapes, drawn: { swings: swings.length, patterns: pats.length } };
}
