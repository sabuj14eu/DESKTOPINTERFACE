/**
 * The Limit Checklist tab (limit-checklist-v1) and the moving averages on the chart.
 * A terminal study: it shows the seven steps and the levels they give; it is not a signal and nothing in it can be pressed.
 */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import type { Candle } from '../api/types';
import { INDICATORS } from '../indicators';
import { LimitChecklistView, type LimitChecklist } from '../components/LimitChecklistTab';

afterEach(cleanup);
const base: LimitChecklist = {
  symbol: 'BTC', state: 'OK', note: '', kind: 'TERMINAL STUDY — display only, not a signal', method_version: 'limit-checklist-v1', methodology: { step_1_trend: 'daily close against the averages' },
  recorded: false, source: 'SignalMesh closed 1d and 4h bars', daily_bars: 320, h4_bars: 120, side: 'SELL', verdict: 'WAIT', verdict_why: 'step 5: TP2 gives 1:1.57, under 1:2',
  steps: [{ n: 1, name: 'Trend (daily)', status: 'PASS', text: 'BEARISH — below all three' }, { n: 5, name: 'Targets', status: 'FAIL', text: 'TP2 … under 1:2: skip the trade' }, { n: 6, name: 'Size', status: 'BY HAND', text: 'risk at most 1%' }],
  plan: { price: 60143.3, price_basis: 'newest closed 4h close', atr_4h: 410, side: 'SELL', order_type: 'SELL LIMIT', zone_low: 61800, zone_high: 62102, entry: 61951, sl: 62350.4, risk_per_unit: 399.4,
    entry_distance_r: 4.53, tp1: 59850, tp2: 59324, rr1: 5.26, rr2: 1.57, zone_levels: [{ zone_kind: 'round number', name: 'round number above', value: 62000 }, { zone_kind: 'moving average (50 or 100-day)', name: '50-day EMA', value: 62102 }] },
  averages: { ema50: 62102, ema100: 64800, ema200: 70150, daily_close: 60336 }, calculated_at: '2026-11-22T13:20:00+00:00', through_daily_utc: '2026-11-22T00:00:00+00:00',
  through_h4_utc: '2026-11-22T12:00:00+00:00', level_label: 'HYPOTHETICAL ANALYSIS LEVEL', decimals: 1,
};

describe('Limit Checklist tab', () => {
  it('says what it is first, shows each step with its own word, and the levels as hypothetical', () => {
    render(<LimitChecklistView d={base} />);
    const t = screen.getByTestId('limit-checklist').textContent!;
    expect(t).toContain('TERMINAL STUDY · NOT A SIGNAL');
    expect(t).toContain('In plain words');
    expect(screen.getByTestId('lc-word').textContent).toBe('WAIT');
    expect(screen.getByTestId('lc-steps').querySelectorAll('tbody tr').length).toBe(3);
    expect(screen.getByTestId('lc-plan').textContent).toContain('HYPOTHETICAL ANALYSIS LEVELs, not an order');
    expect(screen.getByTestId('lc-plan').textContent).toContain('61951.0');
    expect(screen.getByTestId('lc-plan').textContent).toContain('1:5.26 / 1:1.57');
  });

  it('offers nothing to press and never says buy now or sell now', () => {
    render(<LimitChecklistView d={{ ...base, verdict: 'CHECKLIST HOLDS', verdict_why: 'every measured step holds for a hypothetical SELL LIMIT at 61951. Not a signal: nothing here was tested against outcomes' }} />);
    const el = screen.getByTestId('limit-checklist');
    expect(el.querySelectorAll('button, input, select, a').length).toBe(0);
    expect(el.textContent).not.toMatch(/sell now|buy now|place the order|enter now/i);
    expect(el.textContent).toContain('Not a signal');
  });

  it('a refused series and a closed market are said in words, with no level', () => {
    render(<LimitChecklistView d={{ ...base, state: 'SERIES_FAULT', note: 'the daily series is not one clean series: 5 place(s) where two bars sit in one slot', steps: [], plan: null, averages: null, side: null, verdict: 'NOT AVAILABLE' }} />);
    expect(screen.getByTestId('lc-state').textContent).toContain('SERIES FAULT — the daily series is not one clean series');
    expect(screen.queryByTestId('lc-plan')).toBeNull();
    cleanup();
    render(<LimitChecklistView d={{ ...base, market_status: { open: false, why: 'weekend — closed Fri 22:00 UTC to Sun 22:00 UTC', reopens_in: '8h 40m' } }} />);
    expect(screen.getByTestId('lc-closed').textContent).toContain('MARKET CLOSED — weekend');
    expect(screen.getByTestId('lc-closed').textContent).toContain('reopens in 8h 40m');
  });
});

describe('moving averages on the chart', () => {
  it('offers the 20, 50, 100 and 200 exponential averages, each from the candles shown', () => {
    const ids = INDICATORS.map((d) => d.id);
    for (const id of ['ema20', 'ema50', 'ema100', 'ema200']) expect(ids).toContain(id);
    const candles = Array.from({ length: 250 }, (_, i) => ({ time: i * 60, open: 100, high: 100, low: 100, close: 100, volume: 1 })) as unknown as Candle[];
    for (const n of [20, 50, 100, 200]) {
      const pts = INDICATORS.find((d) => d.id === `ema${n}`)!.compute(candles);
      expect(pts.length).toBe(250 - n + 1);                 // nothing is drawn before the average has its bars
      expect(pts[pts.length - 1].value).toBeCloseTo(100);   // the average of a flat series is the series
    }
  });
});
