// INDICATOR SLOT — how a study gets onto the chart. Add an entry to INDICATORS and it appears
// in the chart's "Indicators" menu; nothing else needs to change.
//
// An indicator here is DISPLAY-ONLY: it is computed in the browser from the candles already on
// the chart, it is labelled as such, and it never reaches the SignalMesh decision, the levels or
// the signals. SignalMesh's own values (ATR, structure, bias) stay the engine's and are shown
// where they always were. All indicators are OFF by default.
import type { Candle } from './api/types';

export interface IndicatorPoint { time: number; value: number }
export interface IndicatorDef {
  id: string;
  name: string;             // menu label
  short: string;            // legend label
  pane: 'overlay';          // drawn on the price scale (separate panes: a later addition)
  color: string;
  compute: (candles: Candle[]) => IndicatorPoint[];
}

const sma = (n: number) => (c: Candle[]): IndicatorPoint[] => {
  const out: IndicatorPoint[] = []; let sum = 0;
  for (let i = 0; i < c.length; i++) { sum += c[i].close; if (i >= n) sum -= c[i - n].close; if (i >= n - 1) out.push({ time: c[i].time, value: sum / n }); }
  return out;
};
const ema = (n: number) => (c: Candle[]): IndicatorPoint[] => {
  const out: IndicatorPoint[] = []; const k = 2 / (n + 1); let e = 0;
  for (let i = 0; i < c.length; i++) { e = i === 0 ? c[i].close : c[i].close * k + e * (1 - k); if (i >= n - 1) out.push({ time: c[i].time, value: e }); }
  return out;
};

export const INDICATORS: IndicatorDef[] = [
  { id: 'sma20', name: 'Moving Average — simple, 20', short: 'SMA 20', pane: 'overlay', color: '#eab308', compute: sma(20) },
  { id: 'ema50', name: 'Moving Average — exponential, 50', short: 'EMA 50', pane: 'overlay', color: '#f472b6', compute: ema(50) },
];
export const INDICATOR_NOTE = 'display-only · computed in this browser from the candles shown · not a SignalMesh value and not used by any decision';
