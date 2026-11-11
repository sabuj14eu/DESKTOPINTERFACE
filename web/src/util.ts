import { useEffect, useRef, useState } from 'react';

export const px = (v: number | null | undefined, d = 2) => (v === null || v === undefined || Number.isNaN(v) ? '—' : Number(v).toFixed(d));
export const pct = (v: number | null | undefined) => (v === null || v === undefined ? '—' : `${v > 0 ? '+' : ''}${Number(v).toFixed(2)}%`);
export const fmtTs = (iso: string | null | undefined) => {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toISOString().slice(0, 16).replace('T', ' ') + ' UTC';
};
export const fmtAge = (min: number | null | undefined) => {
  if (min === null || min === undefined) return '—';
  if (min < 1) return `${Math.round(min * 60)}s`;
  if (min < 90) return `${Math.round(min)}m`;
  if (min < 48 * 60) return `${(min / 60).toFixed(1)}h`;
  return `${(min / 1440).toFixed(1)}d`;
};
export const toneOf = (s: string | null | undefined) => {
  const u = (s || '').toUpperCase();
  if (['LIVE', 'READY', 'BUY', 'BULLISH', 'CLEAR', 'OK', 'ACTIVE', 'CONFIRMED', 'POSITIVE', 'HH/HL', 'WIN'].some((k) => u.includes(k))) return 'good';
  if (['STALE', 'WAIT', 'PENDING', 'ELEVATED', 'DEVELOPING', 'MEDIUM', 'NOT CONFIRMED', 'EXPIRED', 'MIXED', 'DISABLED'].some((k) => u.includes(k))) return 'warn';
  if (['INVALID', 'NO TRADE', 'SELL', 'BEARISH', 'BLOCK', 'HIGH', 'DOWN', 'REJECTED', 'FAILED', 'LOSS', 'LH/LL', 'ERROR', 'UNAUTHORIZED'].some((k) => u.includes(k))) return 'bad';
  return 'muted';
};

/** Poll an async loader on an interval; keeps the last good value and the last error separately. */
export function usePoll<T>(loader: () => Promise<T>, intervalMs: number, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string>('');
  const [at, setAt] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  // Every (re)start of the poll gets its own run id. A response that comes back after the
  // inputs changed carries the OLD run id and is dropped, so a slow answer for the previous
  // symbol can never overwrite the new symbol's data. (A shared boolean cannot do this: the
  // new run re-arms it before the old answer arrives.)
  const run = useRef(0);
  useEffect(() => {
    const myRun = ++run.current;
    // the inputs changed (symbol, timeframe, ...): forget the previous answer at once, so
    // nothing from the old inputs is ever shown under the new label
    setData(null); setError(''); setAt(0); setLoading(true);
    let timer: number | undefined;
    const tick = async () => {
      try {
        const v = await loader();
        if (run.current !== myRun) return;
        setData(v); setError(''); setAt(Date.now());
      } catch (e) {
        if (run.current !== myRun) return;
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (run.current === myRun) { setLoading(false); timer = window.setTimeout(tick, intervalMs); }
      }
    };
    void tick();
    return () => { if (run.current === myRun) run.current++; if (timer) window.clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs, ...deps]);
  return { data, error, at, loading };
}

export const fmtHM = (iso: string | null | undefined) => {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toISOString().slice(11, 16);
};
export const sourceTone = (kind: string | undefined) => (kind === 'mt5_reporter' ? 'good' : kind === 'bridge' ? 'warn' : 'bad');
export const sourceWord = (kind: string | undefined) => (kind === 'mt5_reporter' ? 'MT5 REPORTER' : kind === 'fixture' ? 'FIXTURE' : kind === 'bridge' ? 'BRIDGE' : kind === 'unstated' ? 'SOURCE UNSTATED' : 'NOT MT5');

// MT5-style timeframe names for the toolbar; the API keeps SignalMesh's own (1m … 1d)
export const TF_LABEL: Record<string, string> = { '1m': 'M1', '5m': 'M5', '15m': 'M15', '30m': 'M30', '1h': 'H1', '4h': 'H4', '1d': 'D1' };
export const tfLabel = (tf: string) => TF_LABEL[tf] ?? tf.toUpperCase();
export const NA = 'NOT AVAILABLE';
/** A broker-reported amount, or NOT AVAILABLE when the reporter did not send it. Never a computed stand-in. */
export const money = (v: number | null | undefined, ccy?: string | null) =>
  (v === null || v === undefined ? NA : `${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}${ccy ? ' ' + ccy : ''}`);
export const orNA = (v: string | number | null | undefined) => (v === null || v === undefined || v === '' ? NA : String(v));

export function useMedia(query: string) {
  const [on, setOn] = useState(() => typeof window !== 'undefined' && !!window.matchMedia && window.matchMedia(query).matches);
  useEffect(() => {
    if (!window.matchMedia) return;
    const m = window.matchMedia(query);
    const f = () => setOn(m.matches);
    f(); m.addEventListener('change', f);
    return () => m.removeEventListener('change', f);
  }, [query]);
  return on;
}
