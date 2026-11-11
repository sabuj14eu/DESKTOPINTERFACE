// THE WORKSPACE — which panels are open, how big they are, and what the chart shows.
// Saved in the browser (localStorage) on every change and restored on load; "reset layout"
// returns to DEFAULT. Display state only: nothing here reaches SignalMesh.
import { useCallback, useEffect, useState } from 'react';

export interface Workspace {
  v: 2;
  left: { open: boolean; w: number };       // Market Watch
  right: { open: boolean; w: number };      // SignalMesh decision
  bottom: { open: boolean; h: number };     // Toolbox
  full: boolean;                            // full-screen chart: every panel hidden, sizes kept
  tab: string;                              // Toolbox tab
  bars: number;                             // candles requested
  indicators: string[];                     // active indicator ids (see indicators.ts)
  chart: { ladder: boolean; markers: boolean; history: boolean; expired: boolean; volume: boolean; log: boolean; magnet: boolean };
  account: string;                          // selected broker account key
}

export const KEY = 'smt_workspace_v2';
export const LIMITS = { left: [200, 620], right: [240, 640], bottom: [120, 720] } as const;
export const DEFAULT: Workspace = {
  v: 2, left: { open: true, w: 300 }, right: { open: true, w: 330 }, bottom: { open: true, h: 250 }, full: false,
  tab: 'Active Signals', bars: 500, indicators: [],
  chart: { ladder: true, markers: true, history: false, expired: false, volume: true, log: false, magnet: false }, account: '',
};
const clamp = (v: number, [lo, hi]: readonly [number, number]) => Math.round(Math.max(lo, Math.min(hi, Number.isFinite(v) ? v : lo)));

export function load(): Workspace {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || 'null') as Partial<Workspace> | null;
    if (!raw || raw.v !== 2) return DEFAULT;
    return {
      ...DEFAULT, ...raw,
      left: { open: raw.left?.open ?? true, w: clamp(raw.left?.w ?? DEFAULT.left.w, LIMITS.left) },
      right: { open: raw.right?.open ?? true, w: clamp(raw.right?.w ?? DEFAULT.right.w, LIMITS.right) },
      bottom: { open: raw.bottom?.open ?? true, h: clamp(raw.bottom?.h ?? DEFAULT.bottom.h, LIMITS.bottom) },
      chart: { ...DEFAULT.chart, ...(raw.chart ?? {}) },
      indicators: Array.isArray(raw.indicators) ? raw.indicators.filter((x) => typeof x === 'string') : [],
      bars: [300, 500, 1000].includes(raw.bars as number) ? (raw.bars as number) : DEFAULT.bars,
    };
  } catch { return DEFAULT; }
}

export function useWorkspace() {
  const [ws, setWs] = useState<Workspace>(load);
  useEffect(() => { try { localStorage.setItem(KEY, JSON.stringify(ws)); } catch { /* private window */ } }, [ws]);
  const patch = useCallback((p: Partial<Workspace>) => setWs((w) => ({ ...w, ...p })), []);
  const toggle = useCallback((side: 'left' | 'right' | 'bottom') => setWs((w) => ({ ...w, full: false, [side]: { ...w[side], open: w.full ? true : !w[side].open } })), []);
  const resize = useCallback((side: 'left' | 'right' | 'bottom', px: number) => setWs((w) => (side === 'bottom'
    ? { ...w, bottom: { ...w.bottom, h: clamp(px, LIMITS.bottom) } } : { ...w, [side]: { ...w[side], w: clamp(px, LIMITS[side]) } })), []);
  const setChart = useCallback((p: Partial<Workspace['chart']>) => setWs((w) => ({ ...w, chart: { ...w.chart, ...p } })), []);
  const reset = useCallback(() => setWs((w) => ({ ...DEFAULT, account: w.account })), []);
  return { ws, patch, toggle, resize, setChart, reset };
}
