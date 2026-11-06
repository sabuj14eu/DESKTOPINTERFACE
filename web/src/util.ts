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
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    // the inputs changed (symbol, timeframe, ...): forget the previous answer at once, so
    // nothing from the old inputs is ever shown under the new label
    setData(null); setError(''); setAt(0);
    let timer: number | undefined;
    const tick = async () => {
      try {
        const v = await loader();
        if (!alive.current) return;
        setData(v); setError(''); setAt(Date.now());
      } catch (e) {
        if (!alive.current) return;
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (alive.current) { setLoading(false); timer = window.setTimeout(tick, intervalMs); }
      }
    };
    setLoading(true);
    void tick();
    return () => { alive.current = false; if (timer) window.clearTimeout(timer); };
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
